"""SystemVerilog emitter stub for deterministic constraint evaluation.

Converts a ``ConstraintEvalPlan`` into a SystemVerilog ``always @(*)``
combinational block.  Phase 5 — currently a stub; real implementation
follows the PythonFunctionEmitter pattern.
"""
from __future__ import annotations

from typing import List

from zuspec.ir.core.expr import BinOp, UnaryOp

from .eval_expr import (
    EvalExpr, ExprConst, ExprVar, ExprBinOp, ExprUnary, ExprCbit,
    ExprSigned, ExprSext, ExprIf, ExprLookup, ExprMask, ExprBoolMask,
    EvalExprVisitor,
)
from .eval_plan import AssignNode, CheckNode, ConstraintEvalPlan


class SVExprEmitter(EvalExprVisitor):
    """Walk an EvalExpr tree and produce a SystemVerilog expression string.

    Parameters
    ----------
    width:
        Default bit width used for integer literals (e.g. 32).
    """

    def __init__(self, width: int = 32):
        self._width = width

    def emit(self, expr: EvalExpr) -> str:
        return self.visit(expr)

    def visit_ExprConst(self, node: ExprConst) -> str:
        v = node.value
        if v < 0:
            return f"-{self._width}'d{abs(v)}"
        return f"{self._width}'h{v:0{(self._width + 3) // 4}X}"

    def visit_ExprVar(self, node: ExprVar) -> str:
        # Replace dots with underscores for SV identifier
        return node.name.replace('.', '_').replace('-', '_')

    def visit_ExprBinOp(self, node: ExprBinOp) -> str:
        left = self.emit(node.left)
        right = self.emit(node.right)
        op_str = _BINOP_SV.get(node.op, '+')
        return f"({left} {op_str} {right})"

    def visit_ExprUnary(self, node: ExprUnary) -> str:
        operand = self.emit(node.operand)
        if node.op == UnaryOp.Invert:
            return f"(~{operand})"
        if node.op == UnaryOp.USub:
            return f"(-{operand})"
        if node.op == UnaryOp.Not:
            return f"(!{operand})"
        return operand

    def visit_ExprCbit(self, node: ExprCbit) -> str:
        inner = self.emit(node.expr)
        return f"({inner} ? 1'b1 : 1'b0)"

    def visit_ExprSigned(self, node: ExprSigned) -> str:
        inner = self.emit(node.expr)
        return f"$signed({inner})"

    def visit_ExprSext(self, node: ExprSext) -> str:
        # Per sv_codegen convention: $signed($signed(x << (W-bits)) >>> (W-bits))
        inner = self.emit(node.expr)
        n = self._width - node.bits
        return f"$signed($signed({inner} << {n}) >>> {n})"

    def visit_ExprIf(self, node: ExprIf) -> str:
        cond  = self.emit(node.cond)
        then_ = self.emit(node.then_)
        else_ = self.emit(node.else_)
        return f"({cond} ? {then_} : {else_})"

    def visit_ExprLookup(self, node: ExprLookup) -> str:
        # Placeholder — real implementation would emit a case statement
        if len(node.key) == 1:
            key = self.emit(node.key[0])
        else:
            key = '{' + ', '.join(self.emit(k) for k in node.key) + '}'
        return f"/* lookup({node.table_name})[{key}] */"

    def visit_ExprMask(self, node: ExprMask) -> str:
        inner = self.emit(node.expr)
        mask = (1 << node.width) - 1
        return f"({inner} & {self._width}'h{mask:X})"

    def visit_ExprBoolMask(self, node: ExprBoolMask) -> str:
        # In SV, width-1 signals are already single-bit, so bit-replication
        # is done by the concatenation/sign-extension operators.  For now
        # pass the inner expression through; callers must ensure correct
        # SV context (future: emit {W{expr[0]}} or ($signed replication)).
        return self.emit(node.expr)


class SVFunctionEmitter:
    """Emit an ``always @(*)`` combinational block from a ConstraintEvalPlan.

    This is a Phase-5 stub.  The full implementation follows from
    PythonFunctionEmitter — same plan, different target language.
    """

    def emit(self, plan: ConstraintEvalPlan, indent: int = 4) -> str:
        """Return a SV ``always @(*)`` block string.

        Parameters
        ----------
        plan:
            ConstraintEvalPlan with no underdetermined entries.
        indent:
            Number of spaces per indentation level.
        """
        ee = SVExprEmitter()
        pad = " " * indent
        lines: List[str] = ["always @(*) begin"]

        for assign in plan.assignments:
            rhs = ee.emit(assign.expr)
            lines.append(f"{pad}{assign.var_name} = {rhs};")

        lines.append("end")
        return "\n".join(lines)


_BINOP_SV = {
    BinOp.Add:    '+',
    BinOp.Sub:    '-',
    BinOp.Mult:   '*',
    BinOp.Div:    '/',
    BinOp.FloorDiv: '/',
    BinOp.Mod:    '%',
    BinOp.BitAnd: '&',
    BinOp.BitOr:  '|',
    BinOp.BitXor: '^',
    BinOp.LShift: '<<',
    BinOp.RShift: '>>',
    BinOp.Eq:     '==',
    BinOp.NotEq:  '!=',
    BinOp.Lt:     '<',
    BinOp.LtE:    '<=',
    BinOp.Gt:     '>',
    BinOp.GtE:    '>=',
}
