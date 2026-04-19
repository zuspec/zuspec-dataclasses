"""IR Expression Parser - converts IR expressions to solver constraints"""

from typing import Dict, Optional, List, Tuple, Union
from zuspec.ir.core.expr import (
    Expr, ExprConstant, ExprBin, ExprUnary, ExprBool, ExprCompare,
    ExprRef, ExprRefField, ExprRefParam, ExprRefLocal, ExprRefBottomUp, ExprRefUnresolved,
    ExprSlice, ExprSubscript, ExprIfExp, ExprIn, ExprCall, ExprAttribute,
    ExprRange, ExprRangeList,
    BinOp, UnaryOp, BoolOp, CmpOp,
    TypeExprRefSelf
)
import warnings
from zuspec.ir.core.stmt import Stmt, StmtFor, StmtAssert, StmtExpr, StmtIf, StmtReturn, StmtUnique, StmtForeach
from zuspec.ir.core.data_type import DataType
from ..core.variable import Variable
from ..core.constraint import Constraint, SourceLocation
from ..core.constraints import (
    ConstantConstraint, VariableRefConstraint, BinaryOpConstraint,
    UnaryOpConstraint, BoolOpConstraint, CompareConstraint,
    CompareChainConstraint, InConstraint, BitSliceConstraint,
    ImplicationConstraint, UniqueConstraint
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
        
        # Array field metadata: field_name -> {'size': N, 'element_names': [...]}
        self.array_fields: Dict[str, dict] = {}
        
        # Loop variable substitution: var_name -> current_value
        # Used during for-loop expansion
        self.loop_variables: Dict[str, int] = {}
        
        # Bound (non-rand) field values: dotted path -> int constant
        # e.g. {'next_.domain_A': 3, 'prev.domain_A': 2}
        # Used to constant-fold bound field references in constraints.
        self.bound_values: Dict[str, int] = {}
        
        # Source location for error reporting
        self.current_source: Optional[SourceLocation] = None
    
    def register_variable(self, name: str, variable: Variable):
        """Register a solver variable for use in parsing"""
        self.variable_map[name] = variable
    
    def register_field(self, index: int, name: str):
        """Register a field index to variable name mapping"""
        self.field_map[index] = name
    
    def register_array_fields(self, array_metadata: Dict[str, dict]):
        """Register array field metadata for array indexing support"""
        self.array_fields = array_metadata
    
    def register_bound_value(self, path: str, value: int):
        """Register a concrete value for a bound (non-rand) field path.
        
        The path is a dotted name relative to self, e.g. 'next_.domain_A'.
        During constraint parsing, references to this path are folded to the
        given integer constant, enabling constraints like
        ``self.next_.domain_A == self.prev.domain_A + self.step`` to be
        evaluated by the solver when the flow-object fields are already known.
        """
        self.bound_values[path] = value
    
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
        
        elif isinstance(expr, ExprAttribute):
            return self._parse_attribute(expr)
        
        elif isinstance(expr, ExprSubscript):
            return self._parse_subscript(expr)
        
        elif isinstance(expr, ExprIfExp):
            return self._parse_ifexp(expr)
        
        elif isinstance(expr, ExprIn):
            return self._parse_in(expr)
        
        elif isinstance(expr, ExprCall):
            return self._parse_call(expr)
        
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
        
        # Check if this is a logical boolean operation (&&, ||)
        if expr.op in (BinOp.And, BinOp.Or):
            bool_op = BoolOp.And if expr.op == BinOp.And else BoolOp.Or
            return BoolOpConstraint(
                op=bool_op,
                values=[left, right],
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
    
    def _parse_attribute(self, expr: ExprAttribute) -> Constraint:
        """Parse an attribute access (PSS-style field reference: self.field or obj.field).

        The PSS translator emits ``ExprAttribute(value=TypeExprRefSelf(), attr='name')``
        for field references inside constraint bodies.  We resolve this by looking up
        the field name directly in the variable map.
        """
        # Drill down through any chain to find the leaf attribute name
        # e.g. ExprAttribute(value=TypeExprRefSelf(), attr='addr') → 'addr'
        attr_name = expr.attr
        base = expr.value

        # If base is 'self' (TypeExprRefSelf), the attr is a plain field name
        if isinstance(base, TypeExprRefSelf):
            var_name = attr_name
        else:
            # Nested: resolve base first and build dotted name (e.g. "sub.field")
            try:
                base_name = self._resolve_attribute_name(base)
                var_name = f"{base_name}.{attr_name}"
            except ParseError:
                raise ParseError(
                    f"Unsupported attribute base expression: {base.__class__.__name__}"
                )

        if var_name not in self.variable_map:
            # Try bound values: non-rand fields whose concrete value is known at
            # randomization time (e.g. flow-object fields like self.next_.domain_A).
            if var_name in self.bound_values:
                return ConstantConstraint(
                    value=self.bound_values[var_name],
                    source_location=self.current_source
                )
            raise ParseError(
                f"Unknown variable: {var_name}. "
                f"Available variables: {list(self.variable_map.keys())}"
            )

        variable = self.variable_map[var_name]
        return VariableRefConstraint(
            variable=variable,
            source_location=self.current_source
        )

    def _resolve_attribute_name(self, expr) -> str:
        """Recursively resolve an expression to a dotted name string."""
        if isinstance(expr, TypeExprRefSelf):
            return "self"
        elif isinstance(expr, ExprAttribute):
            base = self._resolve_attribute_name(expr.value)
            return f"{base}.{expr.attr}"
        elif isinstance(expr, ExprRef):
            return self._resolve_ref(expr)
        else:
            raise ParseError(f"Cannot resolve attribute name from {expr.__class__.__name__}")


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
        """Parse a subscript (bit-slice, bit-select, or array indexing)"""
        # Get the base variable or field name.  The PSS front-end emits
        # ExprAttribute(TypeExprRefSelf, attr='field') for field references inside
        # constraint bodies, so accept ExprAttribute in addition to ExprRef.
        if isinstance(expr.value, ExprAttribute):
            var_name = self._resolve_attribute_name(expr.value)
            # Strip leading "self." prefix that _resolve_attribute_name may add
            if var_name.startswith("self."):
                var_name = var_name[len("self."):]
        elif isinstance(expr.value, ExprRef):
            var_name = self._resolve_ref(expr.value)
        else:
            raise ParseError("Subscript base must be a variable/field reference")
        
        # Check if this is an array field (for array indexing)
        if var_name in self.array_fields:
            return self._parse_array_subscript(var_name, expr.slice)
        
        # Otherwise, it's bit-slicing on a scalar variable
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
    
    def _parse_array_subscript(self, field_name: str, index_expr: Expr) -> Constraint:
        """
        Parse array subscript: self.field[index]
        
        Converts to variable reference for array element.
        Example: self.buffer[0] → VariableRefConstraint(buffer[0])
        
        Args:
            field_name: Name of the array field
            index_expr: Index expression (constant, loop variable, or simple arithmetic)
            
        Returns:
            Constraint representing the array element variable
            
        Raises:
            ParseError: If index is invalid, out of bounds, or unsupported
        """
        # Try to evaluate the index expression to an integer
        index = self._evaluate_index_expr(index_expr)
        
        # Validate index bounds
        array_size = self.array_fields[field_name]['size']
        if index < 0 or index >= array_size:
            raise ParseError(
                f"Array index {index} out of bounds for '{field_name}' "
                f"(size={array_size}, valid range: 0-{array_size-1})"
            )
        
        # Construct variable name for array element
        var_name = f"{field_name}[{index}]"
        
        # Look up variable (should have been created during extraction)
        if var_name not in self.variable_map:
            raise ParseError(f"Array element variable not found: {var_name}")
        
        # Return variable reference constraint
        variable = self.variable_map[var_name]
        return VariableRefConstraint(
            variable=variable,
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
        # Resolve the variable — accepts ExprRef, ExprAttribute (PSS field ref), or ExprRefUnresolved
        var_name = None
        if isinstance(expr.value, ExprRef):
            var_name = self._resolve_ref(expr.value)
        elif isinstance(expr.value, ExprAttribute):
            var_name = expr.value.attr
        elif isinstance(expr.value, ExprRefUnresolved):
            var_name = expr.value.name

        if var_name is None or var_name not in self.variable_map:
            raise ParseError(f"'in' expression: cannot resolve variable from {expr.value!r}")

        variable = self.variable_map[var_name]

        values = self._extract_value_set(expr.container)

        return InConstraint(
            variable=variable,
            values=values,
            source_location=self.current_source
        )

    def _extract_value_set(self, container: Expr) -> set:
        """Extract a set of integer values from a range-list container."""
        if isinstance(container, ExprRangeList):
            result = set()
            for r in container.ranges:
                if not isinstance(r, ExprRange):
                    raise ParseError(f"Unsupported range element: {r!r}")
                lo_expr = r.lower
                hi_expr = r.upper
                if not isinstance(lo_expr, ExprConstant):
                    raise ParseError(f"Range lower bound must be a constant, got {lo_expr!r}")
                lo = int(lo_expr.value)
                if hi_expr is None:
                    # Single value
                    result.add(lo)
                else:
                    if not isinstance(hi_expr, ExprConstant):
                        raise ParseError(f"Range upper bound must be a constant, got {hi_expr!r}")
                    hi = int(hi_expr.value)
                    result.update(range(lo, hi + 1))
            return result
        raise ParseError(f"Value set extraction not yet implemented for {container.__class__.__name__}")
    
    def _parse_call(self, expr: ExprCall) -> Constraint:
        """
        Parse a call expression (method call or function call).
        
        Supports:
        - .implies() method for implication constraints
        - sum() helper function for array summation
        """
        # Check if this is an attribute access (method call)
        if isinstance(expr.func, ExprAttribute):
            method_name = expr.func.attr
            
            if method_name == "implies":
                # Parse: condition.implies(consequence)
                # This becomes: condition -> consequence
                if len(expr.args) != 1:
                    raise ParseError(f"implies() expects 1 argument, got {len(expr.args)}")
                
                # Parse condition (the object the method is called on)
                condition = self._parse_expr(expr.func.value)
                
                # Parse consequence (the argument)
                then_constraint = self._parse_expr(expr.args[0])
                
                return ImplicationConstraint(
                    condition=condition,
                    then_constraint=then_constraint,
                    else_constraint=None,  # Simple implication, no else branch
                    source_location=self.current_source
                )
            else:
                raise ParseError(f"Unsupported method call: {method_name}")
        
        # Check if this is a helper function call
        elif isinstance(expr.func, (ExprRefLocal, ExprRefUnresolved)):
            func_name = expr.func.name
            
            if func_name == "sum":
                return self._expand_sum_call(expr)
            elif func_name == "len":
                # len() should be handled specially - convert to length variable reference
                return self._parse_len_call(expr)
            elif func_name == "implies":
                # PSS-style free function: implies(condition, consequence)
                if len(expr.args) != 2:
                    raise ParseError(f"implies() expects 2 arguments, got {len(expr.args)}")
                condition = self._parse_expr(expr.args[0])
                then_constraint = self._parse_expr(expr.args[1])
                return ImplicationConstraint(
                    condition=condition,
                    then_constraint=then_constraint,
                    else_constraint=None,
                    source_location=self.current_source
                )
            else:
                raise ParseError(f"Unsupported function call: {func_name}")
        
        else:
            raise ParseError(f"Unsupported call expression: {expr.func.__class__.__name__}")
    
    def _expand_sum_call(self, expr: ExprCall) -> Constraint:
        """
        Expand sum(array) to array[0] + array[1] + ... + array[N-1]
        
        For variable-size arrays, only sums elements within actual length.
        
        Args:
            expr: ExprCall representing sum(array)
            
        Returns:
            BinaryOpConstraint chain representing the sum
        """
        if len(expr.args) != 1:
            raise ParseError(f"sum() expects 1 argument, got {len(expr.args)}")
        
        array_arg = expr.args[0]
        
        # Get array name and metadata
        if isinstance(array_arg, ExprRefField):
            array_name = self._resolve_ref(array_arg)
        elif isinstance(array_arg, ExprRefLocal):
            array_name = array_arg.name
        else:
            raise ParseError(f"sum() argument must be an array field reference, got {array_arg.__class__.__name__}")
        
        if array_name not in self.array_fields:
            raise ParseError(f"sum() argument must be an array field, got: {array_name}")
        
        array_metadata = self.array_fields[array_name]
        size = array_metadata['size']
        is_variable_size = array_metadata.get('is_variable_size', False)
        
        if size == 0:
            # Edge case: empty array sums to 0
            return ConstantConstraint(0, source_location=self.current_source)
        
        if not is_variable_size:
            # Fixed-size array - sum all elements directly
            sum_expr = self._parse_array_element(array_arg, 0)
            for i in range(1, size):
                element = self._parse_array_element(array_arg, i)
                sum_expr = BinaryOpConstraint(
                    op=BinOp.Add,
                    left=sum_expr,
                    right=element,
                    source_location=self.current_source
                )
            return sum_expr
        else:
            # Variable-size array - sum with conditional logic
            # For simplicity, use a loop-like expansion with implications
            # This is more complex - for now, sum all max_size elements
            # TODO: proper handling would require conditional sum
            # For now, sum all elements (they'll be constrained by length separately)
            sum_expr = self._parse_array_element(array_arg, 0)
            for i in range(1, size):
                element = self._parse_array_element(array_arg, i)
                sum_expr = BinaryOpConstraint(
                    op=BinOp.Add,
                    left=sum_expr,
                    right=element,
                    source_location=self.current_source
                )
            return sum_expr
        
        return sum_expr
    
    def _parse_unique_stmt(self, stmt: StmtUnique) -> List[Constraint]:
        """Parse a StmtUnique into a UniqueConstraint."""
        variables = []
        for name in stmt.vars:
            if name not in self.variable_map:
                raise ParseError(f"'unique' constraint references unknown variable '{name}'")
            variables.append(self.variable_map[name])
        return [UniqueConstraint(variables=variables, source_location=self.current_source)]

    def _expand_unique_call(self, expr: ExprCall) -> List[Constraint]:
        """
        Expand unique(array) to nested loop constraints ensuring all elements are distinct.
        
        For fixed-size: for i in range(N): for j in range(i+1, N): assert array[i] != array[j]
        For variable-size: Same but with implications: (i < len and j < len) -> constraint
        
        Args:
            expr: ExprCall representing unique(array)
            
        Returns:
            List of CompareConstraint (or ImplicationConstraint) for all pairs
        """
        if len(expr.args) != 1:
            raise ParseError(f"unique() expects 1 argument, got {len(expr.args)}")
        
        array_arg = expr.args[0]
        
        # Get array name and metadata
        if isinstance(array_arg, ExprRefField):
            array_name = self._resolve_ref(array_arg)
        elif isinstance(array_arg, ExprRefLocal):
            array_name = array_arg.name
        else:
            raise ParseError(f"unique() argument must be an array field reference, got {array_arg.__class__.__name__}")
        
        if array_name not in self.array_fields:
            raise ParseError(f"unique() argument must be an array field, got: {array_name}")
        
        array_metadata = self.array_fields[array_name]
        size = array_metadata['size']
        is_variable_size = array_metadata.get('is_variable_size', False)
        
        # Edge cases
        if size <= 1:
            # Empty array or single element is trivially unique
            return []
        
        # Generate constraints
        constraints = []
        
        if not is_variable_size:
            # Fixed-size: simple constraints
            for i in range(size):
                for j in range(i + 1, size):
                    elem_i = self._parse_array_element(array_arg, i)
                    elem_j = self._parse_array_element(array_arg, j)
                    
                    constraint = CompareConstraint(
                        op=CmpOp.NotEq,
                        left=elem_i,
                        right=elem_j,
                        source_location=self.current_source
                    )
                    constraints.append(constraint)
        else:
            # Variable-size: wrap in implications
            length_var_name = array_metadata.get('length_var_name')
            if not length_var_name:
                raise ParseError(f"Variable-size array {array_name} missing length variable")
            
            for i in range(size):
                for j in range(i + 1, size):
                    elem_i = self._parse_array_element(array_arg, i)
                    elem_j = self._parse_array_element(array_arg, j)
                    
                    # Create arr[i] != arr[j] constraint
                    compare_constraint = CompareConstraint(
                        op=CmpOp.NotEq,
                        left=elem_i,
                        right=elem_j,
                        source_location=self.current_source
                    )
                    
                    # Wrap in implication: (j < len) -> (arr[i] != arr[j])
                    # Note: If j < len, then i < len is automatically true since i < j
                    condition = CompareConstraint(
                        op=CmpOp.Lt,
                        left=ConstantConstraint(j, source_location=self.current_source),
                        right=VariableRefConstraint(
                            self.variable_map[length_var_name],
                            source_location=self.current_source
                        ),
                        source_location=self.current_source
                    )
                    
                    implication = ImplicationConstraint(
                        condition=condition,
                        then_constraint=compare_constraint,
                        else_constraint=None,
                        source_location=self.current_source
                    )
                    constraints.append(implication)
        
        return constraints
    
    def _expand_ascending_call(self, expr: ExprCall) -> List[Constraint]:
        """
        Expand ascending(array) to ensure strictly increasing order.
        
        Expands to:
            for i in range(N-1):
                assert array[i] < array[i+1]
        
        Args:
            expr: ExprCall representing ascending(array)
            
        Returns:
            List of CompareConstraint
        """
        if len(expr.args) != 1:
            raise ParseError(f"ascending() expects 1 argument, got {len(expr.args)}")
        
        array_arg = expr.args[0]
        
        # Get array name and size
        if isinstance(array_arg, ExprRefField):
            array_name = self._resolve_ref(array_arg)
        elif isinstance(array_arg, ExprRefLocal):
            array_name = array_arg.name
        else:
            raise ParseError(f"ascending() argument must be an array field reference, got {array_arg.__class__.__name__}")
        
        if array_name not in self.array_fields:
            raise ParseError(f"ascending() argument must be an array field, got: {array_name}")
        
        size = self.array_fields[array_name]['size']
        
        # Edge cases
        if size <= 1:
            # Empty array or single element is trivially ascending
            return []
        
        # Generate constraints: for i in range(size-1): arr[i] < arr[i+1]
        constraints = []
        for i in range(size - 1):
            elem_i = self._parse_array_element(array_arg, i)
            elem_next = self._parse_array_element(array_arg, i + 1)
            
            # Create arr[i] < arr[i+1] constraint
            constraint = CompareConstraint(
                op=CmpOp.Lt,
                left=elem_i,
                right=elem_next,
                source_location=self.current_source
            )
            constraints.append(constraint)
        
        return constraints
    
    def _expand_descending_call(self, expr: ExprCall) -> List[Constraint]:
        """
        Expand descending(array) to ensure strictly decreasing order.
        
        Expands to:
            for i in range(N-1):
                assert array[i] > array[i+1]
        
        Args:
            expr: ExprCall representing descending(array)
            
        Returns:
            List of CompareConstraint
        """
        if len(expr.args) != 1:
            raise ParseError(f"descending() expects 1 argument, got {len(expr.args)}")
        
        array_arg = expr.args[0]
        
        # Get array name and size
        if isinstance(array_arg, ExprRefField):
            array_name = self._resolve_ref(array_arg)
        elif isinstance(array_arg, ExprRefLocal):
            array_name = array_arg.name
        else:
            raise ParseError(f"descending() argument must be an array field reference, got {array_arg.__class__.__name__}")
        
        if array_name not in self.array_fields:
            raise ParseError(f"descending() argument must be an array field, got: {array_name}")
        
        size = self.array_fields[array_name]['size']
        
        # Edge cases
        if size <= 1:
            # Empty array or single element is trivially descending
            return []
        
        # Generate constraints: for i in range(size-1): arr[i] > arr[i+1]
        constraints = []
        for i in range(size - 1):
            elem_i = self._parse_array_element(array_arg, i)
            elem_next = self._parse_array_element(array_arg, i + 1)
            
            # Create arr[i] > arr[i+1] constraint
            constraint = CompareConstraint(
                op=CmpOp.Gt,
                left=elem_i,
                right=elem_next,
                source_location=self.current_source
            )
            constraints.append(constraint)
        
        return constraints
    
    def _parse_len_call(self, expr: ExprCall) -> Constraint:
        """
        Parse len(array) call and convert to length variable reference.
        
        For variable-size arrays: Maps to _length_{array} variable
        For fixed-size arrays: Returns constant
        
        Args:
            expr: ExprCall representing len(array)
            
        Returns:
            Constraint representing the length (VariableRef or Constant)
            
        Raises:
            ParseError: If invalid arguments or non-array argument
        """
        if len(expr.args) != 1:
            raise ParseError(f"len() expects 1 argument, got {len(expr.args)}")
        
        array_arg = expr.args[0]
        
        # Get array name - handle both ExprRefField (from @constraint) and ExprRefLocal (from randomize_with)
        if isinstance(array_arg, ExprRefField):
            array_name = self._resolve_ref(array_arg)
        elif isinstance(array_arg, ExprRefLocal):
            array_name = array_arg.name
        else:
            raise ParseError(f"len() argument must be an array field reference, got {array_arg.__class__.__name__}")
        
        # Check if this is an array field
        if array_name not in self.array_fields:
            raise ParseError(f"len() argument must be an array, got: {array_name}")
        
        array_metadata = self.array_fields[array_name]
        
        # Check if this is a variable-size array
        if array_metadata.get('is_variable_size', False):
            # Variable-size array - return reference to length variable
            length_var_name = array_metadata.get('length_var_name')
            if not length_var_name:
                raise ParseError(f"Variable-size array {array_name} missing length variable")
            
            if length_var_name not in self.variable_map:
                raise ParseError(f"Length variable not found: {length_var_name}")
            
            return VariableRefConstraint(
                self.variable_map[length_var_name],
                source_location=self.current_source
            )
        else:
            # Fixed-size array - return constant size
            size = array_metadata['size']
            return ConstantConstraint(size, source_location=self.current_source)
    
    def _parse_array_element(self, array_ref: Expr, index: int) -> Constraint:
        """
        Parse an array element reference: array[index]
        
        Args:
            array_ref: ExprRefField or ExprRefLocal for the array
            index: Integer index
            
        Returns:
            VariableRefConstraint for the array element
        """
        # Get array name
        if isinstance(array_ref, ExprRefField):
            array_name = self._resolve_ref(array_ref)
        elif isinstance(array_ref, ExprRefLocal):
            array_name = array_ref.name
        else:
            raise ParseError(f"Invalid array reference: {array_ref.__class__.__name__}")
        
        # Look up the variable for this element
        element_name = f"{array_name}[{index}]"
        if element_name not in self.variable_map:
            raise ParseError(f"Array element not found: {element_name}")
        
        return VariableRefConstraint(
            self.variable_map[element_name],
            source_location=self.current_source
        )
    
    def _evaluate_index_expr(self, expr: Expr) -> int:
        """
        Evaluate an index expression to an integer value.
        
        Supports:
        - Constants: 0, 1, 2, ...
        - Loop variables: i, j, ...
        - Simple arithmetic: i+1, i-1, i*2, i+j, etc.
        
        Args:
            expr: Index expression
            
        Returns:
            Integer index value
            
        Raises:
            ParseError: If expression cannot be evaluated
        """
        # Constant
        if isinstance(expr, ExprConstant):
            if not isinstance(expr.value, int):
                raise ParseError(f"Array index must be integer, got {type(expr.value).__name__}")
            return expr.value
        
        # Loop variable
        if isinstance(expr, ExprRefLocal):
            var_name = expr.name
            if var_name in self.loop_variables:
                return self.loop_variables[var_name]
            else:
                raise ParseError(
                    f"Variable array indices not yet supported. "
                    f"'{var_name}' is not a loop variable."
                )

        # ExprAttribute(TypeExprRefSelf, attr='i') — produced when the foreach
        # iterator variable was translated as a field reference instead of a
        # local variable.  Treat it as a loop variable lookup.
        if isinstance(expr, ExprAttribute) and isinstance(expr.value, TypeExprRefSelf):
            var_name = expr.attr
            if var_name in self.loop_variables:
                return self.loop_variables[var_name]
            else:
                raise ParseError(
                    f"Variable array indices not yet supported. "
                    f"'{var_name}' is not a loop variable."
                )
        
        # Binary operation (e.g., i+1, i*2)
        if isinstance(expr, ExprBin):
            left_val = self._evaluate_index_expr(expr.lhs)
            right_val = self._evaluate_index_expr(expr.rhs)
            
            if expr.op == BinOp.Add:
                return left_val + right_val
            elif expr.op == BinOp.Sub:
                return left_val - right_val
            elif expr.op == BinOp.Mult:
                return left_val * right_val
            elif expr.op == BinOp.Div:
                return left_val // right_val  # Integer division
            elif expr.op == BinOp.Mod:
                return left_val % right_val
            else:
                raise ParseError(f"Unsupported operator in array index: {expr.op}")
        
        # Unary operation (e.g., -1)
        if isinstance(expr, ExprUnary):
            operand_val = self._evaluate_index_expr(expr.operand)
            if expr.op == UnaryOp.USub:
                # Negative index - not supported
                raise ParseError(
                    "Negative array indices not supported. "
                    "Use positive indices: arr[0], arr[1], etc."
                )
            elif expr.op == UnaryOp.UAdd:
                return operand_val
            else:
                raise ParseError(f"Unsupported unary operator in array index: {expr.op}")
        
        raise ParseError(f"Unsupported index expression type: {expr.__class__.__name__}")
    
    # =========================================================================
    # Statement Parsing (for iterative constraints)
    # =========================================================================
    
    def parse_statement(self, stmt: Stmt) -> List[Constraint]:
        """
        Parse a statement into zero or more constraints.
        
        Supports:
        - assert statements
        - expression statements  
        - for loops (iterative constraints)
        - if statements (conditional constraints)
        
        Args:
            stmt: IR statement to parse
            
        Returns:
            List of constraints (empty if statement doesn't generate constraints)
        """
        if isinstance(stmt, StmtAssert):
            # Check if this is a helper function that expands to multiple constraints
            if isinstance(stmt.test, ExprCall):
                func_expr = stmt.test.func
                if isinstance(func_expr, (ExprRefLocal, ExprRefUnresolved)):
                    func_name = func_expr.name
                    
                    if func_name == "unique":
                        return self._expand_unique_call(stmt.test)
                    elif func_name == "ascending":
                        return self._expand_ascending_call(stmt.test)
                    elif func_name == "descending":
                        return self._expand_descending_call(stmt.test)
            
            # Regular constraint
            constraint = self.parse(stmt.test, self.current_source)
            return [constraint]
        
        elif isinstance(stmt, StmtExpr):
            # Skip docstrings
            if isinstance(stmt.expr, ExprConstant) and isinstance(stmt.expr.value, str):
                return []
            constraint = self.parse(stmt.expr, self.current_source)
            return [constraint]
        
        elif isinstance(stmt, StmtUnique):
            return self._parse_unique_stmt(stmt)

        elif isinstance(stmt, StmtFor):
            return self._parse_for_loop(stmt)

        elif isinstance(stmt, StmtForeach):
            return self._parse_foreach_loop(stmt)
        
        elif isinstance(stmt, StmtIf):
            return self._parse_if_statement(stmt)
        
        elif isinstance(stmt, StmtReturn):
            warnings.warn(
                "Constraint method contains a 'return' statement, which is ignored. "
                "Use 'assert expr' instead of 'return expr' in @constraint methods.",
                stacklevel=4
            )
            return []
        
        else:
            # Unsupported statement type for constraints
            return []
    
    def _parse_for_loop(self, stmt: StmtFor) -> List[Constraint]:
        """
        Parse a for loop by expanding it into individual constraints.
        
        Example:
            for i in range(4):
                assert self.arr[i] < 100
        
        Expands to:
            assert self.arr[0] < 100
            assert self.arr[1] < 100
            assert self.arr[2] < 100
            assert self.arr[3] < 100
        
        Supports:
        - Fixed ranges: range(10)
        - Array lengths: range(len(self.arr))
        - Variable bounds: range(self.count) with implications
        - Nested loops (via recursion)
        
        Args:
            stmt: StmtFor node
            
        Returns:
            List of expanded constraints
        """
        # Get loop variable name
        loop_var = self._get_loop_var_name(stmt.target)
        
        # Evaluate iterator to get iteration values and optional bound variable
        values, bound_var = self._evaluate_iterator(stmt.iter)
        
        # Expand loop body for each iteration
        constraints = []
        for i, value in enumerate(values):
            # Set loop variable substitution
            self.loop_variables[loop_var] = value
            
            # Parse body statements (may recursively handle nested loops)
            body_constraints = []
            for body_stmt in stmt.body:
                body_constraints.extend(self.parse_statement(body_stmt))
            
            # If variable-bounded, wrap each constraint in implication
            if bound_var:
                for constraint in body_constraints:
                    # Create: (i >= bound_var) OR (constraint)
                    # This is equivalent to: (i < bound_var) -> constraint
                    impl = self._create_implication(value, bound_var, constraint)
                    constraints.append(impl)
            else:
                constraints.extend(body_constraints)
            
            # Clear loop variable substitution
            del self.loop_variables[loop_var]
        
        return constraints
    
    def _parse_foreach_loop(self, stmt: StmtForeach) -> List[Constraint]:
        """
        Parse a PSS foreach constraint: foreach (data[i]) { data[i] > 0; }
        or element-style: foreach (e : data) { e > 0; }

        In PSS the index-style foreach (foreach (data[i]) { ... }) uses i as an
        integer *index*.  The body references data[i] where i must resolve to an
        integer during constraint expansion.

        Expands by substituting i = 0, 1, ..., N-1 (via loop_variables) so that
        data[i] subscripts can be evaluated by _evaluate_index_expr.

        For element-style (iter_var maps to element variables), we fall back to
        the variable_map substitution for direct uses of the iterator.
        """
        # Get the iterator variable name
        if not isinstance(stmt.target, ExprRefLocal):
            raise ParseError(f"foreach: unsupported target type {stmt.target.__class__.__name__}")
        iter_var = stmt.target.name

        # Resolve the collection — must be an ExprAttribute (self.field) or ExprRefUnresolved
        if isinstance(stmt.iter, ExprAttribute):
            array_name = stmt.iter.attr
        elif isinstance(stmt.iter, (ExprRefLocal, ExprRefUnresolved)):
            array_name = stmt.iter.name
        else:
            raise ParseError(f"foreach: unsupported collection type {stmt.iter.__class__.__name__}")

        # Look up array size from variable map (elements are named array_name[0], ...)
        element_vars = []
        idx = 0
        while True:
            elem_name = f"{array_name}[{idx}]"
            if elem_name in self.variable_map:
                element_vars.append(self.variable_map[elem_name])
                idx += 1
            else:
                break

        if not element_vars:
            raise ParseError(f"foreach: no array elements found for '{array_name}'")

        # Expand constraints.  For each element at index i:
        #   - Set loop_variables[iter_var] = i  (so data[i] subscripts resolve)
        #   - Also set variable_map[iter_var] = element_vars[i]  (so direct uses
        #     of the iterator variable in element-style bodies resolve)
        constraints = []
        for i, elem_var in enumerate(element_vars):
            self.loop_variables[iter_var] = i
            self.variable_map[iter_var] = elem_var
            for body_stmt in stmt.body:
                constraints.extend(self.parse_statement(body_stmt))
            del self.loop_variables[iter_var]
            del self.variable_map[iter_var]

        return constraints

    def _get_loop_var_name(self, target: Expr) -> str:
        """Extract loop variable name from target expression"""
        if isinstance(target, ExprRefLocal):
            return target.name
        else:
            raise ParseError(f"Unsupported loop target: {target.__class__.__name__}")
    
    def _evaluate_iterator(self, expr: Expr) -> Tuple[List[int], Optional[str]]:
        """
        Evaluate iterator expression to get iteration values.
        
        Returns:
            (values, bound_variable_name)
            - values: List of integers to iterate over
            - bound_variable_name: None for constant bounds, variable name for variable bounds
            
        Supports:
            - range(N) - constant bound
            - range(start, stop) - constant bounds
            - range(start, stop, step) - constant bounds
            - range(len(self.arr)) - array length
            - range(self.count) - variable bound
        """
        if isinstance(expr, ExprCall):
            return self._evaluate_call_iterator(expr)
        else:
            raise ParseError(f"Unsupported iterator type: {expr.__class__.__name__}")
    
    def _evaluate_call_iterator(self, expr: ExprCall) -> Tuple[List[int], Optional[str]]:
        """Evaluate range() call"""
        # Check if it's a range() call
        func_ref = expr.func
        is_range = False
        if isinstance(func_ref, ExprRefLocal) and func_ref.name == "range":
            is_range = True
        elif isinstance(func_ref, ExprRefUnresolved) and func_ref.name == "range":
            is_range = True
        
        if not is_range:
            raise ParseError(f"Only range() iterator supported, got: {expr.func}")
        
        # Parse range arguments
        args = expr.args
        if len(args) == 1:
            # range(stop)
            stop, bound_var = self._evaluate_range_arg(args[0])
            start, step = 0, 1
        elif len(args) == 2:
            # range(start, stop)
            start_val, start_var = self._evaluate_range_arg(args[0])
            stop_val, stop_var = self._evaluate_range_arg(args[1])
            if start_var or stop_var:
                raise ParseError("Variable bounds only supported for range(stop) form")
            start, stop, step = start_val, stop_val, 1
            bound_var = None
        elif len(args) == 3:
            # range(start, stop, step)
            start_val, start_var = self._evaluate_range_arg(args[0])
            stop_val, stop_var = self._evaluate_range_arg(args[1])
            step_val, step_var = self._evaluate_range_arg(args[2])
            if start_var or stop_var or step_var:
                raise ParseError("Variable bounds only supported for range(stop) form")
            start, stop, step = start_val, stop_val, step_val
            bound_var = None
        else:
            raise ParseError(f"range() expects 1-3 arguments, got {len(args)}")
        
        # Generate list of values
        values = list(range(start, stop, step))
        return values, bound_var
    
    def _evaluate_range_arg(self, expr: Expr) -> Tuple[int, Optional[str]]:
        """
        Evaluate a single range() argument.
        
        Returns:
            (value, variable_name)
            - value: The evaluated integer value
            - variable_name: None if constant, variable name if variable bound
        """
        # Constant integer
        if isinstance(expr, ExprConstant):
            if not isinstance(expr.value, int):
                raise ParseError(f"Range argument must be integer, got {type(expr.value).__name__}")
            return expr.value, None
        
        # len(array) call
        if isinstance(expr, ExprCall):
            func_ref = expr.func
            is_len = False
            if isinstance(func_ref, ExprRefLocal) and func_ref.name == "len":
                is_len = True
            elif isinstance(func_ref, ExprRefUnresolved) and func_ref.name == "len":
                is_len = True
            
            if is_len:
                if len(expr.args) != 1:
                    raise ParseError("len() expects 1 argument")
                array_arg = expr.args[0]
                # Handle both ExprRefField (from @constraint) and ExprRefLocal (from randomize_with)
                if isinstance(array_arg, (ExprRefField, ExprRefLocal)):
                    if isinstance(array_arg, ExprRefField):
                        array_name = self._resolve_ref(array_arg)
                    else:
                        array_name = array_arg.name
                    
                    if array_name not in self.array_fields:
                        raise ParseError(f"len() argument must be an array field, got: {array_name}")
                    
                    array_metadata = self.array_fields[array_name]
                    
                    # Check if this is a variable-size array
                    if array_metadata.get('is_variable_size', False):
                        # Variable-size array - return max_size and length variable name
                        max_size = array_metadata['size']  # This is max_size for variable arrays
                        length_var_name = array_metadata.get('length_var_name')
                        if not length_var_name:
                            raise ParseError(f"Variable-size array {array_name} missing length variable")
                        return max_size, length_var_name
                    else:
                        # Fixed-size array - return constant size
                        size = array_metadata['size']
                        return size, None
                else:
                    raise ParseError("len() argument must be an array field reference")
            else:
                raise ParseError(f"Unsupported function in range: {expr.func}")
        
        # Variable reference (variable-bounded loop)
        # Handle both ExprRefField (from @constraint) and ExprRefLocal (from randomize_with)
        if isinstance(expr, (ExprRefField, ExprRefLocal)):
            if isinstance(expr, ExprRefField):
                var_name = self._resolve_ref(expr)
            else:
                var_name = expr.name
                
            if var_name not in self.variable_map:
                raise ParseError(f"Unknown variable in range: {var_name}")
            
            # Get the maximum value for expansion
            variable = self.variable_map[var_name]
            # IntDomain has intervals: [(low, high), ...]
            # Get the maximum upper bound
            if variable.domain.intervals:
                max_value = max(high for low, high in variable.domain.intervals)
            else:
                raise ParseError(f"Variable {var_name} has empty domain")
            
            # Return maximum value and variable name
            return max_value, var_name
        
        raise ParseError(f"Unsupported range argument: {expr.__class__.__name__}")
    
    def _create_implication(self, index: int, bound_var: str, constraint: Constraint) -> Constraint:
        """
        Create an implication constraint for variable-bounded loops.
        
        Generates: (index < bound_var) -> constraint
        
        Args:
            index: Current loop iteration index
            bound_var: Name of the variable that bounds the loop
            constraint: The constraint from the loop body
            
        Returns:
            ImplicationConstraint
        """
        # Create constant for index
        index_const = ConstantConstraint(value=index, source_location=self.current_source)
        
        # Create reference to bound variable
        if bound_var not in self.variable_map:
            raise ParseError(f"Bound variable not found: {bound_var}")
        bound_var_ref = VariableRefConstraint(
            variable=self.variable_map[bound_var],
            source_location=self.current_source
        )
        
        # Create condition: index < bound_var
        condition = CompareConstraint(
            left=index_const,
            op=CmpOp.Lt,
            right=bound_var_ref,
            source_location=self.current_source
        )
        
        # Create implication: condition -> constraint
        return ImplicationConstraint(
            condition=condition,
            then_constraint=constraint,
            else_constraint=None,
            source_location=self.current_source
        )
    
    def _parse_if_statement(self, stmt: StmtIf) -> List[Constraint]:
        """
        Parse if statement (conditional constraints).
        
        Currently converts to implications:
            if condition:
                assert expr
        
        Becomes:
            condition -> expr
        
        Args:
            stmt: StmtIf node
            
        Returns:
            List of constraints with implications
        """
        # Parse condition
        condition = self.parse(stmt.test, self.current_source)
        
        # Parse then-branch
        then_constraints = []
        for then_stmt in stmt.body:
            then_constraints.extend(self.parse_statement(then_stmt))
        
        # Parse else-branch if present
        else_constraints = []
        if stmt.orelse:
            for else_stmt in stmt.orelse:
                else_constraints.extend(self.parse_statement(else_stmt))
        
        # Create implications
        result = []
        for then_constraint in then_constraints:
            if else_constraints:
                # if-else: create full implication
                # Note: Need to handle multiple else constraints
                for else_constraint in else_constraints:
                    result.append(ImplicationConstraint(
                        condition=condition,
                        then_constraint=then_constraint,
                        else_constraint=else_constraint,
                        source_location=self.current_source
                    ))
            else:
                # if only: condition -> then_constraint
                result.append(ImplicationConstraint(
                    condition=condition,
                    then_constraint=then_constraint,
                    else_constraint=None,
                    source_location=self.current_source
                ))
        
        return result
