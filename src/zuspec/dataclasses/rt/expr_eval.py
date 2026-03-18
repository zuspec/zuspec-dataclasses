"""Runtime evaluator for dict-based expression IR nodes.

The activity parser (via ``ConstraintParser.parse_expr``) produces nested dicts
representing expressions:

    {'type': 'constant', 'value': 3}
    {'type': 'attribute', 'value': {'type': 'name', 'id': 'self'}, 'attr': 'count'}
    {'type': 'compare', 'left': ..., 'ops': ['<'], 'comparators': [...]}

``ExprEval.eval()`` recursively evaluates these dicts against the fields of
the action in the current ``ActionContext``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .action_context import ActionContext


_OP_MAP = {
    '+':  lambda a, b: a + b,
    '-':  lambda a, b: a - b,
    '*':  lambda a, b: a * b,
    '/':  lambda a, b: a / b,
    '//': lambda a, b: a // b,
    '%':  lambda a, b: a % b,
    '**': lambda a, b: a ** b,
    '<<': lambda a, b: a << b,
    '>>': lambda a, b: a >> b,
    '|':  lambda a, b: a | b,
    '^':  lambda a, b: a ^ b,
    '&':  lambda a, b: a & b,
}

_CMP_MAP = {
    '==':     lambda a, b: a == b,
    '!=':     lambda a, b: a != b,
    '<':      lambda a, b: a < b,
    '<=':     lambda a, b: a <= b,
    '>':      lambda a, b: a > b,
    '>=':     lambda a, b: a >= b,
    'in':     lambda a, b: a in b,
    'not_in': lambda a, b: a not in b,
    'is':     lambda a, b: a is b,
    'is not': lambda a, b: a is not b,
}


class ExprEval:
    """Evaluate dict-based expression IR nodes against an ``ActionContext``."""

    def __init__(self, ctx: "ActionContext") -> None:
        self._ctx = ctx

    def eval(self, expr: Any) -> Any:
        """Evaluate *expr* (a dict or plain Python value) in ctx.action's scope."""
        if not isinstance(expr, dict):
            return expr

        kind = expr.get("type")

        if kind == "constant":
            return expr["value"]

        elif kind == "name":
            name = expr["id"]
            if name == "self":
                return self._ctx.action
            if name == "True":
                return True
            if name == "False":
                return False
            if name == "None":
                return None
            action = self._ctx.action
            if action is not None and hasattr(action, name):
                return getattr(action, name)
            raise RuntimeError(f"ExprEval: unknown name '{name}'")

        elif kind == "attribute":
            obj = self.eval(expr["value"])
            return getattr(obj, expr["attr"])

        elif kind == "bin_op":
            lhs = self.eval(expr["left"])
            rhs = self.eval(expr["right"])
            op = expr["op"]
            fn = _OP_MAP.get(op)
            if fn is None:
                raise RuntimeError(f"ExprEval: unknown binary op '{op}'")
            return fn(lhs, rhs)

        elif kind == "compare":
            lhs = self.eval(expr["left"])
            ops = expr["ops"]
            comparators = [self.eval(c) for c in expr["comparators"]]
            result = True
            prev = lhs
            for op, rhs in zip(ops, comparators):
                fn = _CMP_MAP.get(op)
                if fn is None:
                    raise RuntimeError(f"ExprEval: unknown compare op '{op}'")
                result = result and fn(prev, rhs)
                prev = rhs
            return result

        elif kind == "bool_op":
            op = expr["op"]
            values = expr["values"]
            if op == "and":
                result = True
                for v in values:
                    result = result and bool(self.eval(v))
                    if not result:
                        return False
                return result
            elif op == "or":
                for v in values:
                    if bool(self.eval(v)):
                        return True
                return False
            raise RuntimeError(f"ExprEval: unknown bool op '{op}'")

        elif kind == "unary_op":
            val = self.eval(expr["operand"])
            op = expr["op"]
            if op == "not":
                return not val
            elif op == "-":
                return -val
            elif op == "+":
                return +val
            elif op == "~":
                return ~val
            raise RuntimeError(f"ExprEval: unknown unary op '{op}'")

        elif kind == "subscript":
            obj = self.eval(expr["value"])
            slc = expr["slice"]
            if slc.get("type") == "index":
                return obj[self.eval(slc["value"])]
            if slc.get("type") == "slice":
                lower = self.eval(slc["lower"]) if slc.get("lower") else None
                upper = self.eval(slc["upper"]) if slc.get("upper") else None
                step = self.eval(slc["step"]) if slc.get("step") else None
                return obj[slice(lower, upper, step)]
            return obj[self.eval(slc)]

        elif kind == "list":
            return [self.eval(e) for e in expr.get("elts", [])]

        elif kind == "range":
            start = self.eval(expr["start"])
            stop = self.eval(expr["stop"])
            step = self.eval(expr["step"])
            return range(int(start), int(stop), int(step))

        elif kind == "call":
            # Support len() and a few builtins needed in activity conditions
            func = expr.get("func")
            args = [self.eval(a) for a in expr.get("args", [])]
            if func == "len":
                return len(args[0])
            if func == "int":
                return int(args[0])
            if func == "bool":
                return bool(args[0])
            raise RuntimeError(f"ExprEval: unsupported call to '{func}'")

        elif kind == "if_exp":
            cond = self.eval(expr["test"])
            return self.eval(expr["body"]) if cond else self.eval(expr["orelse"])

        else:
            raise RuntimeError(
                f"ExprEval: unhandled expression type '{kind}': {expr!r}"
            )
