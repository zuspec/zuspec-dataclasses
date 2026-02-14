"""Constraint System Builder - builds complete ConstraintSystem from IR"""

from typing import Dict, List, Optional, Set, Tuple
from zuspec.dataclasses.ir.data_type import (
    DataType, DataTypeStruct, DataTypeClass, Function
)
from zuspec.dataclasses.ir.stmt import Stmt, StmtExpr, StmtAssert, StmtReturn, StmtFor
from zuspec.dataclasses.ir.expr import Expr
from ..core.constraint_system import ConstraintSystem
from ..core.constraint import Constraint, SourceLocation
from ..core.variable import Variable
from .variable_extractor import VariableExtractor
from .ir_parser import IRExpressionParser, ParseError


class BuildError(Exception):
    """Exception raised when building constraint system fails"""
    pass


class ConstraintSystemBuilder:
    """Builds a complete ConstraintSystem from IR structures"""
    
    def __init__(self):
        # The constraint system being built
        self.system = ConstraintSystem()
        
        # Variable extractor
        self.variable_extractor = VariableExtractor()
        
        # Expression parser
        self.expr_parser = IRExpressionParser()
        
        # Bidirectional mapping for error reporting
        # Function name -> List of solver Constraints
        self.func_to_constraint_map: Dict[str, List[Constraint]] = {}
        # Solver Constraint -> IR Expr
        self.constraint_to_ir_map: Dict[Constraint, Expr] = {}
        
        # Track constraint functions
        self.constraint_functions: List[Function] = []
    
    def build_from_struct(
        self,
        struct_type: DataTypeStruct,
        field_metadata: Optional[Dict[str, Dict]] = None
    ) -> ConstraintSystem:
        """
        Build a complete constraint system from an IR struct/class.
        
        Args:
            struct_type: IR struct/class type
            field_metadata: Optional explicit metadata for fields
            
        Returns:
            Complete ConstraintSystem ready for solving
            
        Raises:
            BuildError: If system cannot be built
        """
        # Reset state
        self.system = ConstraintSystem()
        self.func_to_constraint_map.clear()
        self.constraint_to_ir_map.clear()
        self.constraint_functions.clear()
        
        # Step 1: Extract variables
        if field_metadata:
            variables = self.variable_extractor.extract_with_metadata(
                struct_type, field_metadata
            )
        else:
            variables = self.variable_extractor.extract_from_struct(struct_type)
        
        if not variables:
            raise BuildError("No random variables found in struct")
        
        # Add variables to system
        for var in variables:
            self.system.add_variable(var)
        
        # Copy array metadata from extractor to system
        self.system.array_metadata = self.variable_extractor.array_metadata.copy()
        
        # Register variables in parser
        for var in variables:
            self.expr_parser.register_variable(var.name, var)
        
        # Register field index mappings
        for idx, name in self.variable_extractor.field_index_map.items():
            self.expr_parser.register_field(idx, name)
        
        # Register array field metadata for array indexing support
        self.expr_parser.register_array_fields(self.variable_extractor.array_metadata)
        
        # Step 2: Extract and parse constraint functions
        self._extract_constraint_functions(struct_type)
        
        # Step 3: Parse constraints and add to system
        for func in self.constraint_functions:
            self._parse_constraint_function(func)
        
        # Step 4: Validate the system
        self._validate_system()
        
        # Step 5: Compute metadata
        self.system.compute_connected_components()
        
        return self.system
    
    def _extract_constraint_functions(self, struct_type: DataTypeStruct):
        """Extract functions marked as constraints"""
        for func in struct_type.functions:
            # Check if function is marked as constraint
            if self._is_constraint_function(func):
                self.constraint_functions.append(func)
    
    def _is_constraint_function(self, func: Function) -> bool:
        """Check if function is a constraint"""
        # Check metadata for constraint marker
        if func.metadata.get('_is_constraint', False):
            return True
        
        # Check for is_invariant flag
        if func.is_invariant:
            return True
        
        return False
    
    def _parse_constraint_function(self, func: Function):
        """
        Parse a constraint function and add constraints to system.
        
        Args:
            func: IR Function marked as constraint
        """
        # Track constraints from this function
        func_constraints = []
        
        # Get source location
        source_loc = None
        if func.loc is not None:
            source_loc = SourceLocation(
                file=func.loc.file or "unknown",
                line=func.loc.line,
                column=func.loc.pos
            )
        
        # Parse each statement in function body
        for stmt in func.body:
            try:
                constraints_from_stmt = self._parse_constraint_stmt(stmt, source_loc)
                for constraint in constraints_from_stmt:
                    # Add to system
                    self.system.add_constraint(constraint)
                    func_constraints.append(constraint)
                    
                    # Track mapping for error reporting
                    # Extract the expression from the statement
                    if isinstance(stmt, StmtExpr):
                        self.constraint_to_ir_map[constraint] = stmt.expr
                    elif isinstance(stmt, StmtAssert):
                        self.constraint_to_ir_map[constraint] = stmt.test
                    # For StmtFor, we don't have a single expression
            
            except ParseError as e:
                # Enhance error with function context
                raise BuildError(
                    f"Error parsing constraint in function '{func.name}': {e}"
                ) from e
        
        # Store mapping
        if func_constraints:
            self.func_to_constraint_map[func.name] = func_constraints
    
    def _parse_constraint_stmt(
        self,
        stmt: Stmt,
        source_loc: Optional[SourceLocation]
    ) -> List[Constraint]:
        """
        Parse a constraint statement.
        
        Args:
            stmt: IR statement
            source_loc: Source location for error reporting
            
        Returns:
            List of parsed constraints (may be empty)
        """
        # Set source location in parser
        self.expr_parser.current_source = source_loc
        
        # Use the parser's statement parsing method (handles loops, etc.)
        return self.expr_parser.parse_statement(stmt)
    
    def _validate_system(self):
        """
        Validate the constraint system.
        
        Raises:
            BuildError: If validation fails
        """
        # Check that we have at least one variable
        if not self.system.variables:
            raise BuildError("No random variables found in system")
        
        # Note: We allow systems with no constraints - this just means
        # we're picking random values from variable domains without additional constraints
        
        # Check that all variables are used in at least one constraint
        # (This is a warning, not an error)
        if self.system.constraints:
            used_vars = set()
            for constraint in self.system.constraints:
                used_vars.update(constraint.variables)
            
            unused_vars = set(self.system.variables.values()) - used_vars
            if unused_vars:
                # Just track for now, might want to warn
                pass
    
    def add_ordering_constraint(
        self,
        before_var_name: str,
        after_var_name: str
    ):
        """
        Add a solve...before ordering constraint.
        
        Args:
            before_var_name: Variable to solve before
            after_var_name: Variable to solve after
            
        Raises:
            BuildError: If variables don't exist or creates circular dependency
        """
        before_var = self.system.get_variable(before_var_name)
        after_var = self.system.get_variable(after_var_name)
        
        if before_var is None:
            raise BuildError(f"Unknown variable: {before_var_name}")
        if after_var is None:
            raise BuildError(f"Unknown variable: {after_var_name}")
        
        try:
            self.system.add_ordering_constraint(before_var, after_var)
        except ValueError as e:
            raise BuildError(str(e)) from e
    
    def get_constraint_source(self, constraint: Constraint) -> Optional[Expr]:
        """
        Get the IR expression that produced a constraint.
        
        Args:
            constraint: Solver constraint
            
        Returns:
            IR expression or None
        """
        return self.constraint_to_ir_map.get(constraint)
    
    def get_function_constraints(self, func_name: str) -> List[Constraint]:
        """
        Get all constraints from a given function by name.
        
        Args:
            func_name: Function name
            
        Returns:
            List of constraints from that function
        """
        return self.func_to_constraint_map.get(func_name, [])
    
    def build_simple(
        self,
        variables: List[Variable],
        constraint_exprs: List[Expr],
        ordering_constraints: Optional[List[Tuple[str, str]]] = None
    ) -> ConstraintSystem:
        """
        Build a simple constraint system from variables and expressions.
        
        This is a convenience method for testing and simple use cases.
        
        Args:
            variables: List of solver variables
            constraint_exprs: List of IR expressions representing constraints
            ordering_constraints: Optional list of (before, after) variable name tuples
            
        Returns:
            Complete ConstraintSystem
            
        Raises:
            BuildError: If system cannot be built
        """
        # Reset state
        self.system = ConstraintSystem()
        self.func_to_constraint_map.clear()
        self.constraint_to_ir_map.clear()
        
        # Add variables
        for var in variables:
            self.system.add_variable(var)
            self.expr_parser.register_variable(var.name, var)
        
        # Parse and add constraints
        for expr in constraint_exprs:
            try:
                constraint = self.expr_parser.parse(expr)
                self.system.add_constraint(constraint)
                self.constraint_to_ir_map[constraint] = expr
            except ParseError as e:
                raise BuildError(f"Error parsing constraint: {e}") from e
        
        # Add ordering constraints
        if ordering_constraints:
            for before, after in ordering_constraints:
                self.add_ordering_constraint(before, after)
        
        # Validate
        if not self.system.constraints:
            raise BuildError("No constraints in system")
        
        # Compute metadata
        self.system.compute_connected_components()
        
        return self.system
