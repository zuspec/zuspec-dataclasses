#****************************************************************************
# Copyright 2019-2025 Matthew Ballance and contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#****************************************************************************
"""AST parser for constraint expressions.

Parses @constraint decorated methods from Python AST and converts them
to IR expressions for the constraint solver.
"""
import ast
import inspect
from typing import Any, Callable, Dict, List, Optional, Tuple


class ConstraintParser:
    """Parser for constraint method AST."""
    
    def __init__(self):
        self.class_name: Optional[str] = None
    
    def extract_constraints(self, cls: type) -> List[Dict[str, Any]]:
        """Extract all constraint methods from a class.
        
        Args:
            cls: Class to extract constraints from
            
        Returns:
            List of constraint info dicts with:
                - name: constraint method name
                - kind: 'fixed' or 'generic'
                - method: the method object
                - ast: parsed AST
                - exprs: list of parsed expressions
        """
        self.class_name = cls.__name__
        constraints = []
        
        for name, value in cls.__dict__.items():
            if hasattr(value, '_is_constraint') and value._is_constraint:
                try:
                    constraint_info = self.parse_constraint(value)
                    constraint_info['name'] = name
                    constraint_info['kind'] = getattr(value, '_constraint_kind', 'fixed')
                    constraint_info['role'] = getattr(value, '_constraint_role', None)
                    constraints.append(constraint_info)
                except Exception as e:
                    raise ValueError(f"Error parsing constraint {cls.__name__}.{name}: {e}") from e
        
        return constraints
    
    def parse_constraint(self, method: Callable) -> Dict[str, Any]:
        """Parse a constraint method from AST.
        
        Args:
            method: Constraint method to parse
            
        Returns:
            Dict with:
                - method: the method object
                - ast: parsed AST
                - exprs: list of parsed expression dicts
        """
        import textwrap
        
        # Get source and parse to AST
        source = inspect.getsource(method)
        # Dedent to handle methods defined inside classes
        source = textwrap.dedent(source)
        tree = ast.parse(source)
        
        # Extract function definition
        func_def = tree.body[0]
        if not isinstance(func_def, ast.FunctionDef):
            raise ValueError(f"Expected FunctionDef, got {type(func_def)}")
        
        # Parse constraint expressions from function body
        exprs = []
        for stmt in func_def.body:
            # Skip docstrings
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                if isinstance(stmt.value.value, str):
                    continue

            # Parse assert statements: `assert expr` → treat expr as constraint
            if isinstance(stmt, ast.Assert):
                expr = self.parse_expr(stmt.test)
                exprs.append(expr)
                continue

            # Parse if statements: `if cond: body` → implication (cond → consequents)
            if isinstance(stmt, ast.If):
                condition = self.parse_expr(stmt.test)
                consequents = []
                for s in stmt.body:
                    if isinstance(s, ast.Expr):
                        consequents.append(self.parse_expr(s.value))
                    elif isinstance(s, ast.Assert):
                        consequents.append(self.parse_expr(s.test))
                exprs.append({
                    'type': 'implies',
                    'antecedent': condition,
                    'consequent': consequents,
                })
                if stmt.orelse:
                    raise NotImplementedError(
                        "else branches in @constraint if-statements are not yet supported")
                continue

            # Parse expression statements
            if isinstance(stmt, ast.Expr):
                expr = self.parse_expr(stmt.value)
                exprs.append(expr)
        
        return {
            'method': method,
            'ast': func_def,
            'exprs': exprs
        }
    
    def parse_expr(self, node: ast.expr) -> Dict[str, Any]:
        """Parse an expression node.
        
        Args:
            node: AST expression node
            
        Returns:
            Dict representation of the expression
        """
        if isinstance(node, ast.Compare):
            return self.parse_compare(node)
        elif isinstance(node, ast.BoolOp):
            return self.parse_bool_op(node)
        elif isinstance(node, ast.UnaryOp):
            return self.parse_unary_op(node)
        elif isinstance(node, ast.BinOp):
            return self.parse_bin_op(node)
        elif isinstance(node, ast.Call):
            return self.parse_call(node)
        elif isinstance(node, ast.Attribute):
            return self.parse_attribute(node)
        elif isinstance(node, ast.Name):
            return self.parse_name(node)
        elif isinstance(node, ast.Constant):
            return self.parse_constant(node)
        elif isinstance(node, ast.Subscript):
            return self.parse_subscript(node)
        elif isinstance(node, ast.List):
            return self.parse_list(node)
        else:
            raise ValueError(f"Unsupported expression type: {type(node).__name__}")
    
    def parse_compare(self, node: ast.Compare) -> Dict[str, Any]:
        """Parse comparison expression (a < b, a == b, etc.)."""
        op_map = {
            ast.Lt: '<',
            ast.LtE: '<=',
            ast.Gt: '>',
            ast.GtE: '>=',
            ast.Eq: '==',
            ast.NotEq: '!=',
            ast.In: 'in',
            ast.NotIn: 'not_in',
        }
        
        return {
            'type': 'compare',
            'left': self.parse_expr(node.left),
            'ops': [op_map[type(op)] for op in node.ops],
            'comparators': [self.parse_expr(c) for c in node.comparators]
        }
    
    def parse_bool_op(self, node: ast.BoolOp) -> Dict[str, Any]:
        """Parse boolean operation (and, or)."""
        op_map = {
            ast.And: 'and',
            ast.Or: 'or',
        }
        
        return {
            'type': 'bool_op',
            'op': op_map[type(node.op)],
            'values': [self.parse_expr(v) for v in node.values]
        }
    
    def parse_unary_op(self, node: ast.UnaryOp) -> Dict[str, Any]:
        """Parse unary operation (not, -, +)."""
        op_map = {
            ast.Not: 'not',
            ast.USub: '-',
            ast.UAdd: '+',
        }
        
        return {
            'type': 'unary_op',
            'op': op_map[type(node.op)],
            'operand': self.parse_expr(node.operand)
        }
    
    def parse_bin_op(self, node: ast.BinOp) -> Dict[str, Any]:
        """Parse binary operation (+, -, *, /, %, etc.)."""
        op_map = {
            ast.Add: '+',
            ast.Sub: '-',
            ast.Mult: '*',
            ast.Div: '/',
            ast.FloorDiv: '//',
            ast.Mod: '%',
            ast.Pow: '**',
            ast.LShift: '<<',
            ast.RShift: '>>',
            ast.BitOr: '|',
            ast.BitXor: '^',
            ast.BitAnd: '&',
        }
        
        return {
            'type': 'bin_op',
            'op': op_map[type(node.op)],
            'left': self.parse_expr(node.left),
            'right': self.parse_expr(node.right)
        }
    
    def parse_call(self, node: ast.Call) -> Dict[str, Any]:
        """Parse function call (helper functions like implies, dist, etc.)."""
        func_name = self.get_call_name(node.func)
        
        # Special handling for constraint helpers
        if func_name == 'implies':
            return self.parse_implies(node)
        elif func_name == 'soft':
            return self.parse_soft(node)
        elif func_name == 'dist':
            return self.parse_dist(node)
        elif func_name == 'unique':
            return self.parse_unique(node)
        elif func_name == 'solve_order':
            return self.parse_solve_order(node)
        elif func_name == 'range':
            return self.parse_range(node)
        elif func_name == 'valid':
            return self.parse_valid(node)
        elif func_name == 'internal':
            return self.parse_internal(node)
        
        # Generic function call
        return {
            'type': 'call',
            'func': func_name,
            'args': [self.parse_expr(arg) for arg in node.args],
            'keywords': {kw.arg: self.parse_expr(kw.value) for kw in node.keywords}
        }
    
    def parse_implies(self, node: ast.Call) -> Dict[str, Any]:
        """Parse implies(antecedent, consequent)."""
        if len(node.args) != 2:
            raise ValueError(f"implies() requires 2 arguments, got {len(node.args)}")
        
        return {
            'type': 'implies',
            'antecedent': self.parse_expr(node.args[0]),
            'consequent': self.parse_expr(node.args[1])
        }
    
    def parse_soft(self, node: ast.Call) -> Dict[str, Any]:
        """Parse soft(expr) — a soft constraint that may be violated under conflict."""
        if len(node.args) != 1:
            raise ValueError(f"soft() requires 1 argument, got {len(node.args)}")
        return {
            'type': 'soft',
            'expr': self.parse_expr(node.args[0]),
        }
    
    def parse_dist(self, node: ast.Call) -> Dict[str, Any]:
        """Parse dist(var, weights)."""
        if len(node.args) != 2:
            raise ValueError(f"dist() requires 2 arguments, got {len(node.args)}")
        
        var = self.parse_expr(node.args[0])
        
        # Parse weights dictionary
        weights_node = node.args[1]
        if not isinstance(weights_node, ast.Dict):
            raise ValueError("dist() weights must be a dictionary")
        
        weights = []
        for key, value in zip(weights_node.keys, weights_node.values):
            weight_entry = {
                'key': self.parse_expr(key),
                'weight': self.parse_expr(value)
            }
            weights.append(weight_entry)
        
        return {
            'type': 'dist',
            'var': var,
            'weights': weights
        }
    
    def parse_unique(self, node: ast.Call) -> Dict[str, Any]:
        """Parse unique([vars])."""
        if len(node.args) != 1:
            raise ValueError(f"unique() requires 1 argument, got {len(node.args)}")
        
        vars_node = node.args[0]
        if not isinstance(vars_node, ast.List):
            raise ValueError("unique() argument must be a list")
        
        return {
            'type': 'unique',
            'vars': [self.parse_expr(elem) for elem in vars_node.elts]
        }
    
    def parse_solve_order(self, node: ast.Call) -> Dict[str, Any]:
        """Parse solve_order(var1, var2, ...)."""
        if len(node.args) < 2:
            raise ValueError(f"solve_order() requires at least 2 arguments, got {len(node.args)}")
        
        return {
            'type': 'solve_order',
            'vars': [self.parse_expr(arg) for arg in node.args]
        }
    
    def parse_range(self, node: ast.Call) -> Dict[str, Any]:
        """Parse range(start, stop[, step])."""
        if len(node.args) < 1 or len(node.args) > 3:
            raise ValueError(f"range() requires 1-3 arguments, got {len(node.args)}")
        
        if len(node.args) == 1:
            start = {'type': 'constant', 'value': 0}
            stop = self.parse_expr(node.args[0])
            step = {'type': 'constant', 'value': 1}
        elif len(node.args) == 2:
            start = self.parse_expr(node.args[0])
            stop = self.parse_expr(node.args[1])
            step = {'type': 'constant', 'value': 1}
        else:
            start = self.parse_expr(node.args[0])
            stop = self.parse_expr(node.args[1])
            step = self.parse_expr(node.args[2])
        
        return {
            'type': 'range',
            'start': start,
            'stop': stop,
            'step': step
        }
    
    def parse_valid(self, node: ast.Call) -> Dict[str, Any]:
        """Parse zdc.valid(field) — observability declaration.

        Records which field is being declared observable.  The enclosing
        ``if`` guard (antecedent of the surrounding ``implies``) becomes the
        observability condition; this method captures only the field argument.
        The constraint compiler correlates validity_decl nodes with their
        enclosing guard in ``_build_validity_decls()``.
        """
        if len(node.args) != 1:
            raise ValueError(f"zdc.valid() requires exactly 1 argument, got {len(node.args)}")
        return {
            'type': 'validity_decl',
            'field': self.parse_expr(node.args[0]),
        }

    def parse_internal(self, node: ast.Call) -> Dict[str, Any]:
        """Parse zdc.internal(field) — internal-field declaration."""
        if len(node.args) != 1:
            raise ValueError(f"zdc.internal() requires exactly 1 argument, got {len(node.args)}")
        return {
            'type': 'internal_decl',
            'field': self.parse_expr(node.args[0]),
        }

    def parse_attribute(self, node: ast.Attribute) -> Dict[str, Any]:
        """Parse attribute access (self.field)."""
        return {
            'type': 'attribute',
            'value': self.parse_expr(node.value),
            'attr': node.attr
        }
    
    def parse_name(self, node: ast.Name) -> Dict[str, Any]:
        """Parse name reference (variable)."""
        return {
            'type': 'name',
            'id': node.id
        }
    
    def parse_constant(self, node: ast.Constant) -> Dict[str, Any]:
        """Parse constant value."""
        return {
            'type': 'constant',
            'value': node.value
        }
    
    def parse_subscript(self, node: ast.Subscript) -> Dict[str, Any]:
        """Parse subscript access (array[index] or bit slice)."""
        return {
            'type': 'subscript',
            'value': self.parse_expr(node.value),
            'slice': self.parse_slice(node.slice)
        }
    
    def parse_slice(self, node: ast.expr) -> Dict[str, Any]:
        """Parse slice expression."""
        if isinstance(node, ast.Slice):
            return {
                'type': 'slice',
                'lower': self.parse_expr(node.lower) if node.lower else None,
                'upper': self.parse_expr(node.upper) if node.upper else None,
                'step': self.parse_expr(node.step) if node.step else None
            }
        else:
            # Simple index
            return {
                'type': 'index',
                'value': self.parse_expr(node)
            }
    
    def parse_list(self, node: ast.List) -> Dict[str, Any]:
        """Parse list literal."""
        return {
            'type': 'list',
            'elts': [self.parse_expr(elt) for elt in node.elts]
        }
    
    def get_call_name(self, func_node: ast.expr) -> str:
        """Extract function name from call node."""
        if isinstance(func_node, ast.Name):
            return func_node.id
        elif isinstance(func_node, ast.Attribute):
            return func_node.attr
        else:
            return str(func_node)

    def extract_method_contracts(self, method) -> dict:
        """Extract requires/ensures blocks from an async method body.

        Scans the function's AST for:
          - ``with zdc.requires:`` (or ``with requires:``) blocks at the TOP
            (before the first non-contract statement)
          - ``with zdc.ensures:`` (or ``with ensures:``) blocks at the BOTTOM
            (after the last non-contract statement)

        Returns:
            {
              'requires': [list of parsed expr dicts],  # may be empty
              'ensures':  [list of parsed expr dicts],  # may be empty
            }

        Raises ValueError if a requires block appears after non-contract
        statements, or if an ensures block appears before non-contract
        statements (i.e. ordering constraint is violated).
        """
        import textwrap

        source = inspect.getsource(method)
        source = textwrap.dedent(source)
        tree = ast.parse(source)

        func_def = tree.body[0]
        if not isinstance(func_def, (ast.FunctionDef, ast.AsyncFunctionDef)):
            raise ValueError(f"Expected function definition, got {type(func_def)}")

        requires_exprs: list = []
        ensures_exprs: list = []

        # Phase A = collecting leading requires blocks
        # Phase B = in body (non-contract stmts)
        # Phase C = collecting trailing ensures blocks
        phase = 'A'

        for stmt in func_def.body:
            # Skip docstrings
            if (isinstance(stmt, ast.Expr) and
                    isinstance(stmt.value, ast.Constant) and
                    isinstance(stmt.value.value, str)):
                continue

            role = self._get_with_role(stmt)

            if role == 'requires':
                if phase == 'B':
                    raise ValueError(
                        f"'with requires/zdc.requires:' block found after non-contract "
                        f"statements in {method.__name__}. requires blocks must precede the body.")
                if phase == 'C':
                    raise ValueError(
                        f"'with requires/zdc.requires:' block found after ensures block "
                        f"in {method.__name__}.")
                requires_exprs.extend(self._harvest_with_body(stmt))
            elif role == 'ensures':
                phase = 'C'
                ensures_exprs.extend(self._harvest_with_body(stmt))
            else:
                # Non-contract statement
                if phase == 'C':
                    raise ValueError(
                        f"Non-contract statement found after 'with ensures/zdc.ensures:' "
                        f"block in {method.__name__}. ensures blocks must be at the end.")
                phase = 'B'

        return {
            'requires': requires_exprs,
            'ensures':  ensures_exprs,
        }

    def _get_with_role(self, stmt) -> 'str | None':
        """Return 'requires' or 'ensures' if stmt is a matching with-block, else None."""
        if not isinstance(stmt, ast.With):
            return None
        if not stmt.items:
            return None
        ctx_expr = stmt.items[0].context_expr
        if isinstance(ctx_expr, ast.Name) and ctx_expr.id in ('requires', 'ensures'):
            return ctx_expr.id
        if (isinstance(ctx_expr, ast.Attribute) and
                isinstance(ctx_expr.value, ast.Name) and
                ctx_expr.value.id == 'zdc' and
                ctx_expr.attr in ('requires', 'ensures')):
            return ctx_expr.attr
        return None

    def _harvest_with_body(self, stmt: ast.With) -> list:
        """Parse bare expression statements inside a with-block."""
        exprs = []
        for s in stmt.body:
            if isinstance(s, ast.Pass):
                continue
            if isinstance(s, ast.Expr):
                if isinstance(s.value, ast.Constant) and isinstance(s.value.value, str):
                    continue
                exprs.append(self.parse_expr(s.value))
            elif isinstance(s, ast.Assert):
                exprs.append(self.parse_expr(s.test))
        return exprs


def extract_rand_fields(cls: type) -> List[Dict[str, Any]]:
    """Extract all rand/randc fields from a dataclass.
    
    Args:
        cls: Dataclass to extract from
        
    Returns:
        List of field info dicts with:
            - name: field name
            - kind: 'rand' or 'randc'
            - domain: optional (min, max) tuple or list of allowed values
            - size: optional array size
    """
    import dataclasses
    
    if not dataclasses.is_dataclass(cls):
        return []
    
    rand_fields = []
    for field in dataclasses.fields(cls):
        metadata = field.metadata
        if not metadata and isinstance(field.type, dataclasses.Field):
            metadata = field.type.metadata

        if metadata.get('rand') or metadata.get('randc'):
            field_info = {
                'name': field.name,
                'kind': metadata.get('rand_kind', 'randc' if metadata.get('randc') else 'rand'),
            }

            if 'domain' in metadata:
                field_info['domain'] = metadata['domain']

            if 'size' in metadata:
                field_info['size'] = metadata['size']

            rand_fields.append(field_info)
    
    return rand_fields


# Export public API
__all__ = [
    'ConstraintParser',
    'extract_rand_fields',
]
