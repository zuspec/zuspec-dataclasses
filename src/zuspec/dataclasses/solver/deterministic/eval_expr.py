"""EvalExpr — immutable expression IR for deterministic constraint evaluation.

These nodes form the intermediate representation used by ConstraintAnalyser
(to represent the results of constraint inversion) and consumed by both
PythonFunctionEmitter and SVFunctionEmitter.

All nodes are frozen dataclasses (immutable).  Visitor dispatch is provided
by EvalExprVisitor.  A ConstFold pass reduces constant-only sub-trees to
ExprConst nodes.
"""
from __future__ import annotations

import enum
import dataclasses
from typing import Any, Tuple

from zuspec.ir.core.expr import BinOp, UnaryOp


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class EvalExpr:
    """Abstract base for all EvalExpr nodes."""


# ---------------------------------------------------------------------------
# Leaf nodes
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class ExprConst(EvalExpr):
    """An integer constant."""
    value: int


@dataclasses.dataclass(frozen=True)
class ExprVar(EvalExpr):
    """A reference to a named variable (field or local).

    ``name`` is a dotted path relative to the action object, e.g.
    ``"fetch.instr"`` for a bound field or ``"_opcode"`` for a rand field.
    """
    name: str


# ---------------------------------------------------------------------------
# Composite nodes
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class ExprBinOp(EvalExpr):
    """Binary arithmetic / bitwise / comparison operator."""
    op: BinOp
    left: EvalExpr
    right: EvalExpr


@dataclasses.dataclass(frozen=True)
class ExprUnary(EvalExpr):
    """Unary operator (Invert, USub, Not)."""
    op: UnaryOp
    operand: EvalExpr


@dataclasses.dataclass(frozen=True)
class ExprCbit(EvalExpr):
    """Boolean reification: ``1 if expr else 0``."""
    expr: EvalExpr


@dataclasses.dataclass(frozen=True)
class ExprSigned(EvalExpr):
    """Treat *expr* as a signed ``width``-bit integer (two's complement view)."""
    expr: EvalExpr
    width: int


@dataclasses.dataclass(frozen=True)
class ExprSext(EvalExpr):
    """Sign-extend *expr* from *bits*-bit to full integer."""
    expr: EvalExpr
    bits: int


@dataclasses.dataclass(frozen=True)
class ExprIf(EvalExpr):
    """Conditional expression: ``then_ if cond else else_``."""
    cond: EvalExpr
    then_: EvalExpr
    else_: EvalExpr


@dataclasses.dataclass(frozen=True)
class ExprLookup(EvalExpr):
    """Dict-lookup expression.

    Emits ``_TABLE.get(key_expr, default_expr)`` in Python and a ``case``
    block in SystemVerilog.

    ``table_name`` is the module-level identifier for the dict literal.
    ``key`` is a tuple of EvalExpr nodes (single-element for single-key
    lookups, multi-element for tuple-key lookups).
    ``default_expr`` is the fallback when the key is absent.
    """
    table_name: str
    key: Tuple[EvalExpr, ...]
    default_expr: EvalExpr


@dataclasses.dataclass(frozen=True)
class ExprBoolMask(EvalExpr):
    """Sign-extend a boolean/1-bit value to -1 (truthy) or 0 (falsy).

    Equivalent to ``-int(bool(expr))``.  Used when a Python comparison result
    or a 1-bit field value participates in a bitwise AND/OR/XOR expression to
    emulate the RTL semantics where a width-1 boolean is all-ones (true) or
    all-zeros (false) before being used as a multiplexer mask.
    """
    expr: EvalExpr


@dataclasses.dataclass(frozen=True)
class ExprMask(EvalExpr):
    """Extract the low *width* bits of *expr*: ``expr & ((1 << width) - 1)``."""
    expr: EvalExpr
    width: int


# ---------------------------------------------------------------------------
# Visitor
# ---------------------------------------------------------------------------

class EvalExprVisitor:
    """Dispatch visitor for EvalExpr trees.

    Subclass and override ``visit_<ClassName>`` methods.  Unhandled node
    types fall back to ``visit_generic``, which raises ``NotImplementedError``
    by default.
    """

    def visit(self, node: EvalExpr) -> Any:
        """Dispatch to the appropriate ``visit_*`` method."""
        method_name = f"visit_{type(node).__name__}"
        method = getattr(self, method_name, None)
        if method is None:
            return self.visit_generic(node)
        return method(node)

    def visit_generic(self, node: EvalExpr) -> Any:
        raise NotImplementedError(
            f"{type(self).__name__} has no handler for {type(node).__name__}"
        )

    # Provide empty stubs so subclasses only override what they need.
    def visit_ExprConst(self, node: ExprConst) -> Any: return self.visit_generic(node)
    def visit_ExprVar(self, node: ExprVar) -> Any: return self.visit_generic(node)
    def visit_ExprBinOp(self, node: ExprBinOp) -> Any: return self.visit_generic(node)
    def visit_ExprUnary(self, node: ExprUnary) -> Any: return self.visit_generic(node)
    def visit_ExprCbit(self, node: ExprCbit) -> Any: return self.visit_generic(node)
    def visit_ExprSigned(self, node: ExprSigned) -> Any: return self.visit_generic(node)
    def visit_ExprSext(self, node: ExprSext) -> Any: return self.visit_generic(node)
    def visit_ExprIf(self, node: ExprIf) -> Any: return self.visit_generic(node)
    def visit_ExprLookup(self, node: ExprLookup) -> Any: return self.visit_generic(node)
    def visit_ExprMask(self, node: ExprMask) -> Any: return self.visit_generic(node)
    def visit_ExprBoolMask(self, node: ExprBoolMask) -> Any: return self.visit_generic(node)


# ---------------------------------------------------------------------------
# Constant folder
# ---------------------------------------------------------------------------

class ConstFold(EvalExprVisitor):
    """Reduce constant-only sub-trees to ExprConst.

    Walks the tree bottom-up; if all children of a node are ExprConst after
    folding, the node itself is replaced with an ExprConst.
    """

    def visit_ExprConst(self, node: ExprConst) -> EvalExpr:
        return node

    def visit_ExprVar(self, node: ExprVar) -> EvalExpr:
        return node

    def visit_ExprBinOp(self, node: ExprBinOp) -> EvalExpr:
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(left, ExprConst) and isinstance(right, ExprConst):
            return ExprConst(_eval_binop(node.op, left.value, right.value))
        return ExprBinOp(node.op, left, right)

    def visit_ExprUnary(self, node: ExprUnary) -> EvalExpr:
        operand = self.visit(node.operand)
        if isinstance(operand, ExprConst):
            return ExprConst(_eval_unary(node.op, operand.value))
        return ExprUnary(node.op, operand)

    def visit_ExprCbit(self, node: ExprCbit) -> EvalExpr:
        expr = self.visit(node.expr)
        if isinstance(expr, ExprConst):
            return ExprConst(1 if expr.value else 0)
        return ExprCbit(expr)

    def visit_ExprSigned(self, node: ExprSigned) -> EvalExpr:
        expr = self.visit(node.expr)
        if isinstance(expr, ExprConst):
            v = expr.value
            if v >= (1 << (node.width - 1)):
                v -= (1 << node.width)
            return ExprConst(v)
        return ExprSigned(expr, node.width)

    def visit_ExprSext(self, node: ExprSext) -> EvalExpr:
        expr = self.visit(node.expr)
        if isinstance(expr, ExprConst):
            mask = (1 << node.bits) - 1
            v = expr.value & mask
            if v >= (1 << (node.bits - 1)):
                v -= (1 << node.bits)
            return ExprConst(v)
        return ExprSext(expr, node.bits)

    def visit_ExprIf(self, node: ExprIf) -> EvalExpr:
        cond = self.visit(node.cond)
        then_ = self.visit(node.then_)
        else_ = self.visit(node.else_)
        if isinstance(cond, ExprConst):
            return then_ if cond.value else else_
        return ExprIf(cond, then_, else_)

    def visit_ExprLookup(self, node: ExprLookup) -> EvalExpr:
        key = tuple(self.visit(k) for k in node.key)
        default = self.visit(node.default_expr)
        return ExprLookup(node.table_name, key, default)

    def visit_ExprMask(self, node: ExprMask) -> EvalExpr:
        expr = self.visit(node.expr)
        if isinstance(expr, ExprConst):
            mask = (1 << node.width) - 1
            return ExprConst(expr.value & mask)
        return ExprMask(expr, node.width)

    def visit_ExprBoolMask(self, node: ExprBoolMask) -> EvalExpr:
        expr = self.visit(node.expr)
        if isinstance(expr, ExprConst):
            return ExprConst(-int(bool(expr.value)))
        if isinstance(expr, ExprBoolMask):
            return expr  # idempotent
        return ExprBoolMask(expr)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _eval_binop(op: BinOp, a: int, b: int) -> int:
    """Evaluate a binary operation on two integer constants."""
    if op == BinOp.Add:    return a + b
    if op == BinOp.Sub:    return a - b
    if op == BinOp.Mult:   return a * b
    if op == BinOp.Div:    return a // b if b != 0 else 0
    if op == BinOp.Mod:    return a % b if b != 0 else 0
    if op == BinOp.BitAnd: return a & b
    if op == BinOp.BitOr:  return a | b
    if op == BinOp.BitXor: return a ^ b
    if op == BinOp.LShift: return a << b
    if op == BinOp.RShift: return a >> b
    if op == BinOp.Eq:     return int(a == b)
    if op == BinOp.NotEq:  return int(a != b)
    if op == BinOp.Lt:     return int(a < b)
    if op == BinOp.LtE:    return int(a <= b)
    if op == BinOp.Gt:     return int(a > b)
    if op == BinOp.GtE:    return int(a >= b)
    raise ValueError(f"Unsupported BinOp for constant folding: {op}")


def _eval_unary(op: UnaryOp, a: int) -> int:
    """Evaluate a unary operation on an integer constant."""
    if op == UnaryOp.Invert: return ~a
    if op == UnaryOp.USub:   return -a
    if op == UnaryOp.Not:    return int(not a)
    if op == UnaryOp.UAdd:   return a
    raise ValueError(f"Unsupported UnaryOp for constant folding: {op}")


def collect_vars(expr: EvalExpr) -> set:
    """Return the set of all ExprVar.name values reachable from *expr*."""
    names: set = set()

    class _Collect(EvalExprVisitor):
        def visit_ExprConst(self, n):    pass
        def visit_ExprVar(self, n):      names.add(n.name)
        def visit_ExprBinOp(self, n):    self.visit(n.left); self.visit(n.right)
        def visit_ExprUnary(self, n):    self.visit(n.operand)
        def visit_ExprCbit(self, n):     self.visit(n.expr)
        def visit_ExprSigned(self, n):   self.visit(n.expr)
        def visit_ExprSext(self, n):     self.visit(n.expr)
        def visit_ExprIf(self, n):       self.visit(n.cond); self.visit(n.then_); self.visit(n.else_)
        def visit_ExprLookup(self, n):
            for k in n.key: self.visit(k)
            self.visit(n.default_expr)
        def visit_ExprMask(self, n):     self.visit(n.expr)
        def visit_ExprBoolMask(self, n): self.visit(n.expr)

    _Collect().visit(expr)
    return names
