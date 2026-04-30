"""Python function emitter for deterministic constraint evaluation.

Converts a ``ConstraintEvalPlan`` into a compiled Python function that applies
all field assignments directly to the action object.

The emitted function has the signature::

    def _solve_<ClassName>(self_obj):
        ...

It is ``compile()``d to a code object, executed in a controlled namespace, and
cached as ``ActionClass._zdc_compiled_solve``.
"""
from __future__ import annotations

import ast
import os
import textwrap
import types
from typing import Any, Dict, List, Optional, Set

from zuspec.ir.core.expr import BinOp, UnaryOp

from .eval_expr import (
    EvalExpr, ExprConst, ExprVar, ExprBinOp, ExprUnary, ExprCbit,
    ExprSigned, ExprSext, ExprIf, ExprLookup, ExprMask, ExprBoolMask,
    EvalExprVisitor,
)
from .eval_plan import AssignNode, CheckNode, ConstraintEvalPlan
from .exceptions import PreconditionViolation


# ---------------------------------------------------------------------------
# EvalExpr → Python ast.expr visitor
# ---------------------------------------------------------------------------

class PythonExprEmitter(EvalExprVisitor):
    """Walk an EvalExpr tree and produce Python ``ast.expr`` nodes.

    Parameters
    ----------
    bound_path_locals:
        Mapping of dotted-path name → local variable name (``_p_<mangled>``).
        BOUND field references in the tree are replaced with these locals.
    open_var_prefix:
        Prefix for OPEN variable locals (default ``"_"``).
    """

    def __init__(
        self,
        bound_path_locals: Dict[str, str],
        open_var_prefix: str = "",
    ):
        self._bound_locals = bound_path_locals
        self._prefix = open_var_prefix

    def emit(self, expr: EvalExpr) -> ast.expr:
        return self.visit(expr)

    def visit_ExprConst(self, node: ExprConst) -> ast.expr:
        return ast.Constant(value=node.value)

    def visit_ExprVar(self, node: ExprVar) -> ast.expr:
        # BOUND path → use pre-cached local
        if node.name in self._bound_locals:
            return ast.Name(id=self._bound_locals[node.name], ctx=ast.Load())
        # OPEN variable or unknown → use local name directly
        local_name = node.name.replace('.', '_')
        return ast.Name(id=local_name, ctx=ast.Load())

    def visit_ExprBinOp(self, node: ExprBinOp) -> ast.expr:
        left = self.emit(node.left)
        right = self.emit(node.right)
        ast_op = _binop_to_ast(node.op)
        if ast_op is None:
            # Comparison operator → return ast.Compare
            cmp_op = _binop_to_cmp_ast(node.op)
            return ast.Compare(left=left, ops=[cmp_op()], comparators=[right])
        return ast.BinOp(left=left, op=ast_op(), right=right)

    def visit_ExprUnary(self, node: ExprUnary) -> ast.expr:
        operand = self.emit(node.operand)
        if node.op == UnaryOp.Invert:
            return ast.UnaryOp(op=ast.Invert(), operand=operand)
        if node.op == UnaryOp.USub:
            return ast.UnaryOp(op=ast.USub(), operand=operand)
        if node.op == UnaryOp.Not:
            return ast.UnaryOp(op=ast.Not(), operand=operand)
        # UAdd — no-op
        return operand

    def visit_ExprCbit(self, node: ExprCbit) -> ast.expr:
        # cbit(x) → (1 if x else 0)
        inner = self.emit(node.expr)
        return ast.IfExp(
            test=inner,
            body=ast.Constant(value=1),
            orelse=ast.Constant(value=0),
        )

    def visit_ExprSigned(self, node: ExprSigned) -> ast.expr:
        # signed(x, width) → treat x as a width-bit signed integer.
        # Equivalent to: (x - (1 << width)) if x >= (1 << (width-1)) else x
        bits = node.width
        half = 1 << (bits - 1)
        inner = self.emit(node.expr)
        return ast.IfExp(
            test=ast.Compare(
                left=inner,
                ops=[ast.GtE()],
                comparators=[ast.Constant(value=half)],
            ),
            body=ast.BinOp(
                left=inner,
                op=ast.Sub(),
                right=ast.Constant(value=1 << bits),
            ),
            orelse=inner,
        )

    def visit_ExprSext(self, node: ExprSext) -> ast.expr:
        # sext(x, bits) → Python: (x & mask) - (1<<bits) if (x & mask) >= (1<<(bits-1)) else (x & mask)
        bits = node.bits
        mask = (1 << bits) - 1
        half = 1 << (bits - 1)
        inner = self.emit(node.expr)
        # masked = inner & mask
        masked = ast.BinOp(
            left=inner,
            op=ast.BitAnd(),
            right=ast.Constant(value=mask),
        )
        # (masked - (1<<bits)) if masked >= half else masked
        return ast.IfExp(
            test=ast.Compare(
                left=masked,
                ops=[ast.GtE()],
                comparators=[ast.Constant(value=half)],
            ),
            body=ast.BinOp(
                left=masked,
                op=ast.Sub(),
                right=ast.Constant(value=1 << bits),
            ),
            orelse=masked,
        )

    def visit_ExprIf(self, node: ExprIf) -> ast.expr:
        cond  = self.emit(node.cond)
        then_ = self.emit(node.then_)
        else_ = self.emit(node.else_)
        return ast.IfExp(test=cond, body=then_, orelse=else_)

    def visit_ExprLookup(self, node: ExprLookup) -> ast.expr:
        # _TABLE.get(key, default)
        if len(node.key) == 1:
            key_ast = self.emit(node.key[0])
        else:
            # Tuple key
            elts = [self.emit(k) for k in node.key]
            key_ast = ast.Tuple(elts=elts, ctx=ast.Load())

        default_ast = self.emit(node.default_expr)
        return ast.Call(
            func=ast.Attribute(
                value=ast.Name(id=node.table_name, ctx=ast.Load()),
                attr='get',
                ctx=ast.Load(),
            ),
            args=[key_ast, default_ast],
            keywords=[],
        )

    def visit_ExprMask(self, node: ExprMask) -> ast.expr:
        inner = self.emit(node.expr)
        mask = (1 << node.width) - 1
        return ast.BinOp(
            left=inner,
            op=ast.BitAnd(),
            right=ast.Constant(value=mask),
        )

    def visit_ExprBoolMask(self, node: ExprBoolMask) -> ast.expr:
        inner = self.emit(node.expr)
        # -int(bool(inner)) → -1 for truthy, 0 for falsy; idempotent
        return ast.UnaryOp(
            op=ast.USub(),
            operand=ast.Call(
                func=ast.Name(id='int', ctx=ast.Load()),
                args=[ast.Call(func=ast.Name(id='bool', ctx=ast.Load()),
                               args=[inner], keywords=[])],
                keywords=[],
            ),
        )


# ---------------------------------------------------------------------------
# PythonFunctionEmitter
# ---------------------------------------------------------------------------

class PythonFunctionEmitter:
    """Emit and compile a ``_solve_<ClassName>(self_obj)`` function.

    Parameters
    ----------
    debug_postconditions:
        When True, postcondition checks are emitted as ``assert`` statements.
        Defaults to the value of the ``ZDC_DETERMINISTIC_DEBUG`` environment
        variable.
    """

    def __init__(self, debug_postconditions: Optional[bool] = None):
        if debug_postconditions is None:
            debug_postconditions = bool(os.environ.get('ZDC_DETERMINISTIC_DEBUG'))
        self._debug = debug_postconditions

    def emit(self, plan: ConstraintEvalPlan) -> types.FunctionType:
        """Compile a solve function from *plan* and return it.

        The returned function can be stored as::

            plan.action_class._zdc_compiled_solve = emitted_fn

        Parameters
        ----------
        plan:
            A ConstraintEvalPlan with no ``underdetermined`` entries.

        Returns
        -------
        Compiled Python function.
        """
        cls_name = getattr(plan.action_class, '__name__', 'Unknown')
        func_name = f"_solve_{cls_name}"

        # ---- Build bound-path → local name map --------------------------
        bound_path_locals: Dict[str, str] = {}
        for path in plan.bound_paths:
            mangled = "_p_" + path.replace('.', '__')
            bound_path_locals[path] = mangled

        expr_emitter = PythonExprEmitter(bound_path_locals)

        # ---- Build AST body --------------------------------------------
        body: List[ast.stmt] = []

        # 0. Bound-path inlining locals
        for path, local_name in bound_path_locals.items():
            # _p_fetch__instr = self_obj.fetch.instr
            attr_expr = _make_attr_chain('self_obj', path.split('.'))
            body.append(ast.Assign(
                targets=[ast.Name(id=local_name, ctx=ast.Store())],
                value=attr_expr,
                lineno=1, col_offset=0,
            ))

        # 1. Preconditions
        for check in plan.preconditions:
            cond_ast = expr_emitter.emit(check.expr)
            # if not cond: raise PreconditionViolation(name, self_obj)
            body.append(ast.If(
                test=ast.UnaryOp(op=ast.Not(), operand=cond_ast),
                body=[
                    ast.Raise(
                        exc=ast.Call(
                            func=ast.Name(id='PreconditionViolation', ctx=ast.Load()),
                            args=[
                                ast.Constant(value=check.source_loc),
                                ast.Name(id='self_obj', ctx=ast.Load()),
                            ],
                            keywords=[],
                        ),
                        cause=None,
                    )
                ],
                orelse=[],
            ))

        # 2. Assignments (in topological order)
        for assign in plan.assignments:
            # Side-check preconditions
            for check in assign.checks:
                cond_ast = expr_emitter.emit(check.expr)
                body.append(ast.If(
                    test=ast.UnaryOp(op=ast.Not(), operand=cond_ast),
                    body=[
                        ast.Raise(
                            exc=ast.Call(
                                func=ast.Name(id='PreconditionViolation', ctx=ast.Load()),
                                args=[
                                    ast.Constant(value=check.source_loc),
                                    ast.Name(id='self_obj', ctx=ast.Load()),
                                ],
                                keywords=[],
                            ),
                            cause=None,
                        )
                    ],
                    orelse=[],
                ))

            # local_name = expr
            local_name = assign.var_name.replace('.', '_')
            val_ast = expr_emitter.emit(assign.expr)
            body.append(ast.Assign(
                targets=[ast.Name(id=local_name, ctx=ast.Store())],
                value=val_ast,
                lineno=1, col_offset=0,
            ))

        # 3. Write-back
        for assign in plan.assignments:
            if not assign.write_back:
                continue
            local_name = assign.var_name.replace('.', '_')
            # self_obj.<var_name> = <local>
            target_ast = _make_attr_store('self_obj', assign.var_name.split('.'))
            body.append(ast.Assign(
                targets=[target_ast],
                value=ast.Name(id=local_name, ctx=ast.Load()),
                lineno=1, col_offset=0,
            ))

        # 4. Postconditions (optional debug)
        if self._debug:
            for check in plan.postconditions:
                cond_ast = expr_emitter.emit(check.expr)
                body.append(ast.Assert(
                    test=cond_ast,
                    msg=ast.Constant(value=f"Postcondition failed: {check.source_loc}"),
                ))

        if not body:
            body.append(ast.Pass())

        # ---- Wrap in function def --------------------------------------
        func_ast = ast.FunctionDef(
            name=func_name,
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg='self_obj')],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=body,
            decorator_list=[],
            returns=None,
        )

        module_ast = ast.Module(body=[func_ast], type_ignores=[])
        ast.fix_missing_locations(module_ast)

        # ---- Build module-level namespace with lookup tables -----------
        globs: Dict[str, Any] = {
            'PreconditionViolation': PreconditionViolation,
        }
        for tname, tdict in plan.lookup_tables.items():
            globs[tname] = tdict

        code = compile(module_ast, filename=f"<{func_name}>", mode='exec')
        exec(code, globs)  # noqa: S102 — controlled namespace
        fn = globs[func_name]

        return fn


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def _make_attr_chain(base: str, parts: List[str]) -> ast.expr:
    """Build an attribute-chain AST: ``base.part1.part2`` etc."""
    result: ast.expr = ast.Name(id=base, ctx=ast.Load())
    for part in parts:
        result = ast.Attribute(value=result, attr=part, ctx=ast.Load())
    return result


def _make_attr_store(base: str, parts: List[str]) -> ast.expr:
    """Build a store-target attribute chain: ``base.p1.p2 = ...``."""
    if not parts:
        return ast.Name(id=base, ctx=ast.Store())
    # Navigate to the second-to-last part with Load context
    result: ast.expr = ast.Name(id=base, ctx=ast.Load())
    for part in parts[:-1]:
        result = ast.Attribute(value=result, attr=part, ctx=ast.Load())
    return ast.Attribute(value=result, attr=parts[-1], ctx=ast.Store())


_BINOP_MAP = {
    BinOp.Add:    ast.Add,
    BinOp.Sub:    ast.Sub,
    BinOp.Mult:   ast.Mult,
    BinOp.Div:    ast.Div,
    BinOp.FloorDiv: ast.FloorDiv,
    BinOp.Mod:    ast.Mod,
    BinOp.BitAnd: ast.BitAnd,
    BinOp.BitOr:  ast.BitOr,
    BinOp.BitXor: ast.BitXor,
    BinOp.LShift: ast.LShift,
    BinOp.RShift: ast.RShift,
}

_CMPOP_MAP = {
    BinOp.Eq:    ast.Eq,
    BinOp.NotEq: ast.NotEq,
    BinOp.Lt:    ast.Lt,
    BinOp.LtE:   ast.LtE,
    BinOp.Gt:    ast.Gt,
    BinOp.GtE:   ast.GtE,
}


def _binop_to_ast(op: BinOp):
    return _BINOP_MAP.get(op)


def _binop_to_cmp_ast(op: BinOp):
    return _CMPOP_MAP.get(op, ast.Eq)
