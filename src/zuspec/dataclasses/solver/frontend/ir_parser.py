"""IR Expression Parser - converts IR expressions to solver constraints"""

from typing import Dict, Optional, List
from zuspec.dataclasses.ir.expr import (
    Expr, ExprConstant, ExprBin, ExprUnary, ExprBool, ExprCompare,
    ExprRef, ExprRefField, ExprRefParam, ExprRefLocal, ExprRefBottomUp,
    ExprSlice, ExprSubscript, ExprIfExp, ExprIn,
    BinOp, UnaryOp, BoolOp, CmpOp,
    TypeExprRefSelf
)
from zuspec.dataclasses.ir.data_type import DataType
from ..core.variable import Variable
from ..core.constraint import Constraint, SourceLocation
from ..core.constraints import (
    ConstantConstraint, VariableRefConstraint, BinaryOpConstraint,
    UnaryOpConstraint, BoolOpConstraint, CompareConstraint,
    CompareChainConstraint, InConstraint, BitSliceConstraint,
    ImplicationConstraint
)
from ..core.type_mapper import TypeMapper, TypeInference


class ParseError(Exception):
    """Exception raised when parsing fails"""
    pass


class IRExpressionParser:
    """Parses IR expressions into solver constraints"""
    
    def __init__(self):
        # Map from IR variable identifiers to solver Variables
        self.variable_map: Dict[str, Variable] = {}
        
        # Map from field indices to variable names (for ExprRefField)
        self.field_map: Dict[int, str] = {}
        
        # Source location for error reporting
        self.current_source: Optional[SourceLocation] = None
    
    def register_variable(self, name: str, variable: Variable):
        """Register a solver variable for use in parsing"""
        self.variable_map[name] = variable
    
    def register_field(self, index: int, name: str):
        """Register a field index to variable name mapping"""
        self.field_map[index] = name
    
    def parse(self, expr: Expr, source_location: Optional[SourceLocation] = None) -> Constraint:
        """
        Parse an IR expression into a solver constraint.
        
        Args:
            expr: IR expression to parse
            source_location: Optional source location for error reporting
            
        Returns:
            Parsed constraint
            
        Raises:
            ParseError: If expression cannot be parsed
        """
        self.current_source = source_location
        return self._parse_expr(expr)
    
    def _parse_expr(self, expr: Expr) -> Constraint:
        """Internal recursive expression parser"""
        
        if isinstance(expr, ExprConstant):
            return self._parse_constant(expr)
        
        elif isinstance(expr, ExprBin):
            return self._parse_binary(expr)
        
        elif isinstance(expr, ExprUnary):
            return self._parse_unary(expr)
        
        elif isinstance(expr, ExprBool):
            return self._parse_bool(expr)
        
        elif isinstance(expr, ExprCompare):
            return self._parse_compare(expr)
        
        elif isinstance(expr, ExprRef):
            return self._parse_ref(expr)
        
        elif isinstance(expr, ExprSubscript):
            return self._parse_subscript(expr)
        
        elif isinstance(expr, ExprIfExp):
            return self._parse_ifexp(expr)
        
        elif isinstance(expr, ExprIn):
            return self._parse_in(expr)
        
        else:
            raise ParseError(
                f"Unsupported expression type: {expr.__class__.__name__}"
            )
    
    def _parse_constant(self, expr: ExprConstant) -> ConstantConstraint:
        """Parse a constant value"""
        if not isinstance(expr.value, int):
            raise ParseError(f"Only integer constants are supported, got {type(expr.value)}")
        
        return ConstantConstraint(
            value=expr.value,
            source_location=self.current_source
        )
    
    def _parse_binary(self, expr: ExprBin) -> Constraint:
        """Parse a binary operation"""
        left = self._parse_expr(expr.lhs)
        right = self._parse_expr(expr.rhs)
        
        # Check if this is a comparison operation
        if expr.op in (BinOp.Eq, BinOp.NotEq, BinOp.Lt, BinOp.LtE, BinOp.Gt, BinOp.GtE):
            # Convert BinOp to CmpOp
            cmp_op = self._binop_to_cmpop(expr.op)
            return CompareConstraint(
                left=left,
                op=cmp_op,
                right=right,
                source_location=self.current_source
            )
        
        # Regular binary operation
        return BinaryOpConstraint(
            op=expr.op,
            left=left,
            right=right,
            source_location=self.current_source
        )
    
    def _binop_to_cmpop(self, binop: BinOp) -> CmpOp:
        """Convert BinOp comparison to CmpOp"""
        mapping = {
            BinOp.Eq: CmpOp.Eq,
            BinOp.NotEq: CmpOp.NotEq,
            BinOp.Lt: CmpOp.Lt,
            BinOp.LtE: CmpOp.LtE,
            BinOp.Gt: CmpOp.Gt,
            BinOp.GtE: CmpOp.GtE,
        }
        return mapping[binop]
    
    def _parse_unary(self, expr: ExprUnary) -> UnaryOpConstraint:
        """Parse a unary operation"""
        operand = self._parse_expr(expr.operand)
        
        return UnaryOpConstraint(
            op=expr.op,
            operand=operand,
            source_location=self.current_source
        )
    
    def _parse_bool(self, expr: ExprBool) -> BoolOpConstraint:
        """Parse a boolean operation (AND, OR)"""
        values = [self._parse_expr(v) for v in expr.values]
        
        return BoolOpConstraint(
            op=expr.op,
            values=values,
            source_location=self.current_source
        )
    
    def _parse_compare(self, expr: ExprCompare) -> Constraint:
        """Parse a comparison or comparison chain"""
        left = self._parse_expr(expr.left)
        comparators = [self._parse_expr(c) for c in expr.comparators]
        
        # Single comparison
        if len(expr.ops) == 1:
            return CompareConstraint(
                left=left,
                op=expr.ops[0],
                right=comparators[0],
                source_location=self.current_source
            )
        
        # Comparison chain (e.g., a < b < c)
        return CompareChainConstraint(
            left=left,
            ops=expr.ops,
            comparators=comparators,
            source_location=self.current_source
        )
    
    def _parse_ref(self, expr: ExprRef) -> Constraint:
        """Parse a variable reference"""
        var_name = self._resolve_ref(expr)
        
        if var_name not in self.variable_map:
            raise ParseError(
                f"Unknown variable: {var_name}. "
                f"Available variables: {list(self.variable_map.keys())}"
            )
        
        variable = self.variable_map[var_name]
        return VariableRefConstraint(
            variable=variable,
            source_location=self.current_source
        )
    
    def _resolve_ref(self, expr: ExprRef) -> str:
        """Resolve a reference to a variable name"""
        if isinstance(expr, TypeExprRefSelf):
            return "self"
        
        elif isinstance(expr, ExprRefField):
            # Look up field by index
            if expr.index not in self.field_map:
                raise ParseError(f"Unknown field index: {expr.index}")
            return self.field_map[expr.index]
        
        elif isinstance(expr, ExprRefParam):
            return expr.name
        
        elif isinstance(expr, ExprRefLocal):
            return expr.name
        
        elif isinstance(expr, ExprRefBottomUp):
            # Look up field by index
            if expr.index not in self.field_map:
                raise ParseError(f"Unknown field index: {expr.index}")
            return self.field_map[expr.index]
        
        else:
            raise ParseError(f"Unsupported reference type: {expr.__class__.__name__}")
    
    def _parse_subscript(self, expr: ExprSubscript) -> Constraint:
        """Parse a subscript (bit-slice or bit-select)"""
        # Get the base variable
        if not isinstance(expr.value, ExprRef):
            raise ParseError("Subscript base must be a variable reference")
        
        var_name = self._resolve_ref(expr.value)
        if var_name not in self.variable_map:
            raise ParseError(f"Unknown variable: {var_name}")
        
        variable = self.variable_map[var_name]
        
        # Check if this is a slice or single index
        if isinstance(expr.slice, ExprSlice):
            # Bit slice (e.g., addr[7:0])
            slice_expr = expr.slice
            
            # Evaluate bounds (must be constants)
            if not isinstance(slice_expr.lower, ExprConstant):
                raise ParseError("Slice lower bound must be a constant")
            if not isinstance(slice_expr.upper, ExprConstant):
                raise ParseError("Slice upper bound must be a constant")
            
            lower = slice_expr.lower.value
            upper = slice_expr.upper.value
            
            return BitSliceConstraint(
                variable=variable,
                lower=lower,
                upper=upper,
                source_location=self.current_source
            )
        else:
            # Single bit select (e.g., addr[3])
            # Treat as slice [i:i]
            if not isinstance(expr.slice, ExprConstant):
                raise ParseError("Bit select index must be a constant")
            
            index = expr.slice.value
            return BitSliceConstraint(
                variable=variable,
                lower=index,
                upper=index,
                source_location=self.current_source
            )
    
    def _parse_ifexp(self, expr: ExprIfExp) -> ImplicationConstraint:
        """Parse a conditional expression (ternary operator)"""
        condition = self._parse_expr(expr.test)
        then_constraint = self._parse_expr(expr.body)
        else_constraint = self._parse_expr(expr.orelse)
        
        return ImplicationConstraint(
            condition=condition,
            then_constraint=then_constraint,
            else_constraint=else_constraint,
            source_location=self.current_source
        )
    
    def _parse_in(self, expr: ExprIn) -> Constraint:
        """Parse an 'in' constraint (membership test)"""
        # Get the variable
        if not isinstance(expr.value, ExprRef):
            raise ParseError("'in' expression left side must be a variable")
        
        var_name = self._resolve_ref(expr.value)
        if var_name not in self.variable_map:
            raise ParseError(f"Unknown variable: {var_name}")
        
        variable = self.variable_map[var_name]
        
        # Extract the set of values
        # For now, we'll support simple cases
        # More complex range expressions will be added later
        values = self._extract_value_set(expr.container)
        
        return InConstraint(
            variable=variable,
            values=values,
            source_location=self.current_source
        )
    
    def _extract_value_set(self, container: Expr) -> set:
        """Extract a set of values from a container expression"""
        # This is a placeholder - will be expanded to handle:
        # - ExprRangeList
        # - ExprList
        # - etc.
        raise ParseError(f"Value set extraction not yet implemented for {container.__class__.__name__}")
