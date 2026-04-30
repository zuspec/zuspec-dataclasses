"""Deterministic constraint analyser.

Converts IR constraint function bodies into a ConstraintEvalPlan via the
iterative closure algorithm described in DETERMINISTIC_CONSTRAINT_DESIGN.md §2.

The public entry point is ``ConstraintAnalyser.analyse()``.
"""
from __future__ import annotations

import dataclasses
import warnings
from typing import Any, Dict, List, Optional, Set, Tuple

from zuspec.ir.core.expr import (
    Expr, ExprConstant, ExprBin, ExprUnary as IRExprUnary, ExprBool,
    ExprCompare, ExprAttribute, ExprRef, ExprRefField, ExprRefParam,
    ExprRefLocal, ExprRefBottomUp, ExprSubscript, ExprSlice, ExprIfExp,
    ExprIn, ExprCall, ExprSext as IRExprSext, ExprZext, ExprCbit as IRExprCbit,
    ExprSigned as IRExprSigned,
    TypeExprRefSelf,
    BinOp, UnaryOp, BoolOp, CmpOp,
)
from zuspec.ir.core.stmt import (
    Stmt, StmtExpr, StmtAssert, StmtIf, StmtReturn, StmtPass,
    StmtAnnAssign, StmtAssign, StmtAugAssign,
)

from .eval_expr import (
    EvalExpr, ExprConst, ExprVar, ExprBinOp, ExprUnary, ExprCbit,
    ExprSigned, ExprSext, ExprIf, ExprLookup, ExprMask, ExprBoolMask,
    ConstFold, collect_vars,
)
from .eval_plan import CheckNode, AssignNode, CoverageGap, ConstraintEvalPlan
from .variable_status import VarStatus, VarStatusMap


# ---------------------------------------------------------------------------
# Internal raw constraint representation (analyser-private)
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class _RawEq:
    """Top-level equality: lhs == rhs (to invert)."""
    lhs: EvalExpr
    rhs: EvalExpr
    source_loc: str


@dataclasses.dataclass
class _RawCheck:
    """Top-level boolean check: the expression must be truthy."""
    expr: EvalExpr
    source_loc: str


@dataclasses.dataclass
class _RawIf:
    """Conditional constraint: if cond: [body_constraints]."""
    cond: EvalExpr
    body: List[Any]   # List[_RawConstraint]
    source_loc: str


_RawConstraint = (_RawEq, _RawCheck, _RawIf)


_CMPOPS = frozenset((BinOp.Eq, BinOp.NotEq, BinOp.Lt, BinOp.LtE, BinOp.Gt, BinOp.GtE))


def _is_one_bit(node: EvalExpr, one_bit_vars: Set[str]) -> bool:
    """Return True if *node* evaluates to a 1-bit boolean (0 or 1, or -1 or 0 after masking).

    Used to decide whether to wrap a sub-expression in ExprBoolMask when it
    appears as a bitwise AND/OR/XOR operand, replicating the RTL sign-extension
    semantics of the constraint solver.
    """
    if isinstance(node, ExprBinOp):
        if node.op in _CMPOPS:
            return True
        if node.op in (BinOp.BitAnd, BinOp.BitOr, BinOp.BitXor):
            return _is_one_bit(node.left, one_bit_vars) and _is_one_bit(node.right, one_bit_vars)
    if isinstance(node, ExprBoolMask):
        return True
    # ExprCbit is NOT 1-bit for masking purposes: cbit() explicitly converts to 0/1
    # integer, and (-1) & (-1) & cbit_result = cbit_result (0 or 1). Wrapping in
    # ExprBoolMask would turn 1 → -1 which corrupts the result for SLT/SLTU.
    if isinstance(node, ExprUnary) and node.op in (UnaryOp.Invert, UnaryOp.Not):
        return _is_one_bit(node.operand, one_bit_vars)
    if isinstance(node, ExprVar):
        return node.name in one_bit_vars
    return False


# ---------------------------------------------------------------------------
# IR → EvalExpr converter
# ---------------------------------------------------------------------------

class _IRConverter:
    """Converts an IR ``Expr`` tree to an ``EvalExpr`` tree.

    All field references (both BOUND and OPEN) are kept as symbolic
    ``ExprVar`` nodes with their dotted path names.  No folding of bound
    fields to constants is performed here; that is handled by the analyser
    using the VarStatusMap.

    Parameters
    ----------
    fields_by_index:
        Mapping from ``ExprRefField.index`` → field name string.  Built
        from the struct's ``fields`` list by ``ConstraintAnalyser.analyse``.
    """

    def __init__(self, fields_by_index: Optional[Dict[int, str]] = None,
                 one_bit_field_names: Optional[Set[str]] = None):
        self._fields_by_index: Dict[int, str] = fields_by_index or {}
        self._one_bit_field_names: Set[str] = one_bit_field_names or set()

    def convert(self, expr: Expr) -> EvalExpr:
        """Convert *expr* to an EvalExpr node."""
        return self._convert(expr)

    def _convert(self, expr: Expr) -> EvalExpr:
        if isinstance(expr, ExprConstant):
            if isinstance(expr.value, bool):
                return ExprConst(int(expr.value))
            if isinstance(expr.value, int):
                return ExprConst(expr.value)
            # Enum constants — try to get integer value
            try:
                return ExprConst(int(expr.value))
            except (TypeError, ValueError):
                # Non-integer constant; represent as opaque constant 0 (best-effort)
                warnings.warn(
                    f"DeterministicAnalyser: non-integer constant {expr.value!r}; using 0"
                )
                return ExprConst(0)

        if isinstance(expr, ExprBin):
            return self._convert_binop(expr)

        if isinstance(expr, IRExprUnary):
            operand = self._convert(expr.operand)
            # Sign-extend 1-bit operand before Invert so ~True=0, ~False=-1
            if expr.op == UnaryOp.Invert and _is_one_bit(operand, self._one_bit_field_names):
                operand = ExprBoolMask(operand)
            return ExprUnary(expr.op, operand)

        if isinstance(expr, ExprBool):
            # BoolOp.And / Or over a list → nested ExprBinOp with mask-wrapped parts
            parts = [self._convert(v) for v in expr.values]
            op = BinOp.BitAnd if expr.op == BoolOp.And else BinOp.BitOr
            masked = [ExprBoolMask(p) if _is_one_bit(p, self._one_bit_field_names) else p
                      for p in parts]
            result2 = masked[0]
            for p in masked[1:]:
                result2 = ExprBinOp(op, result2, p)
            return result2

        if isinstance(expr, ExprCompare):
            return self._convert_compare(expr)

        if isinstance(expr, ExprAttribute):
            return ExprVar(self._resolve_attr_path(expr))

        if isinstance(expr, ExprRef):
            name = self._resolve_ref_name(expr)
            return ExprVar(name)

        if isinstance(expr, ExprIfExp):
            cond = self._convert(expr.test)
            then_ = self._convert(expr.body)
            else_ = self._convert(expr.orelse)
            return ExprIf(cond, then_, else_)

        if isinstance(expr, ExprSubscript):
            return self._convert_subscript(expr)

        if isinstance(expr, IRExprSext):
            inner = self._convert(expr.value)
            return ExprSext(inner, expr.bits)

        if isinstance(expr, ExprZext):
            # Zero-extend: mask to expr.bits wide
            inner = self._convert(expr.value)
            return ExprMask(inner, expr.bits)

        if isinstance(expr, IRExprCbit):
            inner = self._convert(expr.value)
            return ExprCbit(inner)

        if isinstance(expr, IRExprSigned):
            inner = self._convert(expr.value)
            return ExprSigned(inner, 32)  # default width; ExprSigned propagates through

        if isinstance(expr, ExprIn):
            # Return as a boolean expression using ExprBinOp composition;
            # simplified to a check (not invertible)
            val = self._convert(expr.value)
            container = expr.container
            # ExprRangeList / ExprRange: emit val >= lo and val <= hi chain
            # For simplicity, convert to a non-invertible check expression.
            # We return a placeholder that counts the contained vars.
            return self._convert_in(val, container)

        if isinstance(expr, ExprCall):
            return self._convert_call(expr)

        # Fallthrough: unsupported expression type; warn and return a sentinel
        warnings.warn(
            f"DeterministicAnalyser: unsupported IR expr type "
            f"{type(expr).__name__}; treating as opaque constant"
        )
        return ExprConst(0)

    def _convert_binop(self, expr: ExprBin) -> EvalExpr:
        left = self._convert(expr.lhs)
        right = self._convert(expr.rhs)
        op = expr.op
        # For bitwise ops, sign-extend any 1-bit operand to RTL mask semantics.
        if op in (BinOp.BitAnd, BinOp.BitOr, BinOp.BitXor):
            if _is_one_bit(left, self._one_bit_field_names):
                left = ExprBoolMask(left)
            if _is_one_bit(right, self._one_bit_field_names):
                right = ExprBoolMask(right)
        return ExprBinOp(op, left, right)

    def _convert_compare(self, expr: ExprCompare) -> EvalExpr:
        """Convert ExprCompare (a < b < c style or simple a cmp b)."""
        # Map CmpOp → BinOp
        _cmpop_to_binop = {
            CmpOp.Eq:    BinOp.Eq,
            CmpOp.NotEq: BinOp.NotEq,
            CmpOp.Lt:    BinOp.Lt,
            CmpOp.LtE:   BinOp.LtE,
            CmpOp.Gt:    BinOp.Gt,
            CmpOp.GtE:   BinOp.GtE,
        }
        if len(expr.ops) == 1:
            binop = _cmpop_to_binop.get(expr.ops[0])
            if binop is not None:
                left = self._convert(expr.left)
                right = self._convert(expr.comparators[0])
                return ExprBinOp(binop, left, right)
        # Multi-comparison chain: emit as And of pairwise comparisons
        parts: List[EvalExpr] = []
        prev = self._convert(expr.left)
        for op, comp_expr in zip(expr.ops, expr.comparators):
            curr = self._convert(comp_expr)
            binop = _cmpop_to_binop.get(op, BinOp.Eq)
            parts.append(ExprBinOp(binop, prev, curr))
            prev = curr
        result: EvalExpr = ExprBoolMask(parts[0])
        for p in parts[1:]:
            result = ExprBinOp(BinOp.BitAnd, result, ExprBoolMask(p))
        return result

    def _convert_subscript(self, expr: ExprSubscript) -> EvalExpr:
        """Convert a bit-slice or array subscript."""
        from zuspec.ir.core.expr import ExprSlice
        base = self._convert(expr.value)
        slc = expr.slice
        if isinstance(slc, ExprSlice) and slc.is_bit_slice:
            # Bit-slice [upper:lower] → (base >> lower) & ((1 << (upper-lower+1))-1)
            lower_val = slc.lower.value if isinstance(slc.lower, ExprConstant) else None
            upper_val = slc.upper.value if isinstance(slc.upper, ExprConstant) else None
            if lower_val is not None and upper_val is not None:
                width = upper_val - lower_val + 1
                shifted = ExprBinOp(BinOp.RShift, base, ExprConst(lower_val))
                return ExprMask(shifted, width)
            # Fall back: just mask by width if we can figure it out
            return base
        if isinstance(slc, ExprConstant):
            # Array subscript — represent as ExprBinOp(index_access)?
            # For now, just return base (simplified; not invertible)
            return base
        return base

    def _convert_in(self, val: EvalExpr, container) -> EvalExpr:
        """Convert `val in container` to a boolean EvalExpr."""
        from zuspec.ir.core.expr import ExprRangeList, ExprRange, ExprList
        if hasattr(container, 'ranges'):
            # ExprRangeList: chain of ranges/values
            parts: List[EvalExpr] = []
            for item in container.ranges:
                if isinstance(item, ExprRange) if hasattr(item, '__class__') else False:
                    lo = self._convert(item.lower) if hasattr(item, 'lower') else ExprConst(0)
                    hi = self._convert(item.upper) if hasattr(item, 'upper') else ExprConst(0)
                    # val >= lo && val <= hi
                    parts.append(ExprBinOp(BinOp.BitAnd,
                                           ExprBoolMask(ExprBinOp(BinOp.GtE, val, lo)),
                                           ExprBoolMask(ExprBinOp(BinOp.LtE, val, hi))))
                else:
                    # Single value
                    v = self._convert(item) if hasattr(item, '__class__') else ExprConst(0)
                    parts.append(ExprBoolMask(ExprBinOp(BinOp.Eq, val, v)))
            if not parts:
                return ExprConst(0)
            result = parts[0]
            for p in parts[1:]:
                result = ExprBinOp(BinOp.BitOr, result, p)
            return result
        elif hasattr(container, 'elts'):
            # ExprList: explicit set
            parts = [ExprBoolMask(ExprBinOp(BinOp.Eq, val, self._convert(e)))
                     for e in container.elts]
            if not parts:
                return ExprConst(0)
            result = parts[0]
            for p in parts[1:]:
                result = ExprBinOp(BinOp.BitOr, result, p)
            return result
        # Fallback
        return ExprConst(1)

    def _convert_call(self, expr: ExprCall) -> EvalExpr:
        """Convert a function call (e.g. zdc.sext(), zdc.cbit())."""
        # Try to resolve function name
        func = expr.func
        name = None
        if isinstance(func, ExprAttribute):
            try:
                name = self._resolve_attr_path(func)
            except Exception:
                pass
        elif isinstance(func, ExprRef):
            try:
                name = self._resolve_ref_name(func)
            except Exception:
                pass

        if name:
            short = name.split('.')[-1]
            if short == 'sext' and len(expr.args) >= 2:
                inner = self._convert(expr.args[0])
                bits_arg = expr.args[1]
                bits_val = bits_arg.value if isinstance(bits_arg, ExprConstant) else 0
                return ExprSext(inner, bits_val)
            if short == 'cbit' and len(expr.args) >= 1:
                inner = self._convert(expr.args[0])
                return ExprCbit(inner)
            if short == 'zext' and len(expr.args) >= 2:
                inner = self._convert(expr.args[0])
                bits_arg = expr.args[1]
                bits_val = bits_arg.value if isinstance(bits_arg, ExprConstant) else 0
                return ExprMask(inner, bits_val)

        # Unknown call — return a "contains the same vars" placeholder
        if expr.args:
            return self._convert(expr.args[0])
        return ExprConst(0)

    def _resolve_attr_path(self, expr) -> str:
        """Recursively resolve an ExprAttribute chain to a dotted name."""
        if isinstance(expr, TypeExprRefSelf):
            return "self"
        if isinstance(expr, ExprAttribute):
            base = self._resolve_attr_path(expr.value)
            if base == "self":
                return expr.attr
            return f"{base}.{expr.attr}"
        if isinstance(expr, ExprRef):
            return self._resolve_ref_name(expr)
        raise ValueError(f"Cannot resolve path from {type(expr).__name__}")

    def _resolve_ref_name(self, expr: ExprRef) -> str:
        if isinstance(expr, TypeExprRefSelf):
            return "self"
        if isinstance(expr, ExprRefParam):
            return expr.name
        if isinstance(expr, ExprRefLocal):
            return expr.name
        if isinstance(expr, (ExprRefField, ExprRefBottomUp)):
            # Resolve to field name via pre-built index map
            name = self._fields_by_index.get(expr.index)
            if name is not None:
                return name
            return f"__field_{expr.index}"
        raise ValueError(f"Cannot resolve ref {type(expr).__name__}")


def _convert_stmts_to_raw(stmts: List[Stmt], source_prefix: str,
                           fields_by_index: Optional[Dict[int, str]] = None,
                           one_bit_field_names: Optional[Set[str]] = None) -> List[Any]:
    """Convert a list of IR statements to raw constraint items."""
    conv = _IRConverter(fields_by_index=fields_by_index,
                        one_bit_field_names=one_bit_field_names)
    result: List[Any] = []
    for stmt in stmts:
        _convert_stmt(stmt, conv, source_prefix, result)
    return result


def _convert_stmt(stmt: Stmt, conv: _IRConverter, src: str, out: List[Any]) -> None:
    """Convert a single IR statement to raw constraint items, appending to *out*."""
    if isinstance(stmt, StmtExpr):
        expr = stmt.expr
        # Skip string/docstring constants — they appear as StmtExpr at the
        # start of constraint function bodies but carry no constraint meaning.
        if isinstance(expr, ExprConstant) and not isinstance(expr.value, (int, bool)):
            return
        raw = _convert_expr_to_raw(expr, conv, src)
        if raw is not None:
            out.append(raw)
    elif isinstance(stmt, StmtAssert):
        raw = _convert_expr_to_raw(stmt.test, conv, src)
        if raw is not None:
            out.append(raw)
    elif isinstance(stmt, StmtIf):
        cond = conv.convert(stmt.test)
        body_raws: List[Any] = []
        for s in stmt.body:
            _convert_stmt(s, conv, src, body_raws)
        if body_raws:
            out.append(_RawIf(cond, body_raws, src))
        # orelse is ignored for deterministic analysis (conservative)
    elif isinstance(stmt, (StmtReturn, StmtPass)):
        pass  # nothing
    elif isinstance(stmt, (StmtAnnAssign, StmtAssign, StmtAugAssign)):
        pass  # assignments in constraint bodies are not constraint expressions
    else:
        pass  # skip unknown statements


def _convert_expr_to_raw(expr: Expr, conv: _IRConverter, src: str) -> Optional[Any]:
    """Convert a top-level constraint expression to a raw constraint."""
    if isinstance(expr, ExprBin) and expr.op == BinOp.Eq:
        lhs = conv.convert(expr.lhs)
        rhs = conv.convert(expr.rhs)
        return _RawEq(lhs, rhs, src)
    if isinstance(expr, ExprCompare) and len(expr.ops) == 1 and expr.ops[0] == CmpOp.Eq:
        lhs = conv.convert(expr.left)
        rhs = conv.convert(expr.comparators[0])
        return _RawEq(lhs, rhs, src)
    # Other top-level expressions (e.g. x != y, x in {...}) → check
    eval_expr = conv.convert(expr)
    return _RawCheck(eval_expr, src)


# ---------------------------------------------------------------------------
# Algebraic inversion
# ---------------------------------------------------------------------------

def _try_invert(
    target_var: str,
    lhs: EvalExpr,
    rhs: EvalExpr,
    source_loc: str,
) -> Optional[Tuple[EvalExpr, List[CheckNode]]]:
    """Attempt to invert ``lhs == rhs`` for *target_var*.

    Returns ``(value_expr, side_checks)`` if successful, or ``None`` if the
    expression is not invertible.
    """
    lhs_vars = collect_vars(lhs)
    rhs_vars = collect_vars(rhs)

    target_in_lhs = target_var in lhs_vars
    target_in_rhs = target_var in rhs_vars

    if not target_in_lhs and not target_in_rhs:
        return None  # target not in this equality

    if target_in_lhs and target_in_rhs:
        return None  # target on both sides — not simply invertible

    if target_in_lhs:
        return _invert_expr(target_var, lhs, rhs, source_loc)
    else:
        return _invert_expr(target_var, rhs, lhs, source_loc)


def _invert_expr(
    target: str,
    expr_with_target: EvalExpr,
    opposite: EvalExpr,
    source_loc: str,
    checks: Optional[List[CheckNode]] = None,
) -> Optional[Tuple[EvalExpr, List[CheckNode]]]:
    """Recursively isolate *target* in *expr_with_target* == *opposite*.

    Parameters
    ----------
    target:
        Variable name to isolate.
    expr_with_target:
        The side of the equality containing *target*.
    opposite:
        The other side (may also contain bound vars, but not *target*).
    source_loc:
        For side-check source_loc fields.
    checks:
        Accumulated side-checks (divisibility, etc.).

    Returns
    -------
    ``(result_expr, checks)`` on success, or ``None`` on failure.
    """
    if checks is None:
        checks = []

    # Base case: we've reached the target variable
    if isinstance(expr_with_target, ExprVar) and expr_with_target.name == target:
        folded = ConstFold().visit(opposite)
        return (folded, checks)

    # --- ExprSext(inner, bits) == opposite  →  inner = opposite & mask
    if isinstance(expr_with_target, ExprSext):
        bits = expr_with_target.bits
        mask = ExprConst((1 << bits) - 1)
        new_rhs = ConstFold().visit(ExprBinOp(BinOp.BitAnd, opposite, mask))
        # Side check: sext(new_rhs, bits) == opposite (sign bit consistency)
        check_expr = ExprBinOp(BinOp.Eq,
                                ExprSext(new_rhs, bits),
                                opposite)
        checks = checks + [CheckNode(check_expr,
                                     f"{source_loc} [sext-sign-check]")]
        return _invert_expr(target, expr_with_target.expr, new_rhs,
                            source_loc, checks)

    # --- ExprMask(inner, bits) == opposite  →  inner bits are known (PARTIAL)
    # Conservative: not invertible (loses high bits)
    if isinstance(expr_with_target, ExprMask):
        return None

    # --- ExprUnary ---
    if isinstance(expr_with_target, ExprUnary):
        op = expr_with_target.op
        if op == UnaryOp.Invert:
            # ~f(x) == opp  →  f(x) == ~opp
            new_rhs = ConstFold().visit(ExprUnary(UnaryOp.Invert, opposite))
            return _invert_expr(target, expr_with_target.operand, new_rhs,
                                source_loc, checks)
        if op == UnaryOp.USub:
            # -f(x) == opp  →  f(x) == -opp
            new_rhs = ConstFold().visit(ExprUnary(UnaryOp.USub, opposite))
            return _invert_expr(target, expr_with_target.operand, new_rhs,
                                source_loc, checks)
        if op == UnaryOp.Not:
            # not f(x) == opp  →  f(x) == not opp
            new_rhs = ConstFold().visit(ExprUnary(UnaryOp.Not, opposite))
            return _invert_expr(target, expr_with_target.operand, new_rhs,
                                source_loc, checks)
        return None  # UAdd or unknown

    # --- ExprCbit ---
    if isinstance(expr_with_target, ExprCbit):
        # cbit(f(x)) == opp  →  f(x) == opp (assuming opp is 0 or 1)
        return _invert_expr(target, expr_with_target.expr, opposite,
                            source_loc, checks)

    # --- ExprSigned ---
    if isinstance(expr_with_target, ExprSigned):
        # Transparent: just propagate through
        return _invert_expr(target, expr_with_target.expr, opposite,
                            source_loc, checks)

    # --- ExprBinOp ---
    if isinstance(expr_with_target, ExprBinOp):
        op = expr_with_target.op
        left = expr_with_target.left
        right = expr_with_target.right
        t_in_left  = target in collect_vars(left)
        t_in_right = target in collect_vars(right)

        # target must be on exactly one side
        if t_in_left == t_in_right:
            return None  # both or neither — not invertible here

        if t_in_left:
            # f(x) op k == opp  →  f(x) == opp inv_op k
            if op == BinOp.Add:
                # x + k == opp  →  x = opp - k
                new_rhs = ConstFold().visit(ExprBinOp(BinOp.Sub, opposite, right))
                return _invert_expr(target, left, new_rhs, source_loc, checks)
            if op == BinOp.Sub:
                # x - k == opp  →  x = opp + k
                new_rhs = ConstFold().visit(ExprBinOp(BinOp.Add, opposite, right))
                return _invert_expr(target, left, new_rhs, source_loc, checks)
            if op == BinOp.BitXor:
                # x ^ k == opp  →  x = opp ^ k
                new_rhs = ConstFold().visit(ExprBinOp(BinOp.BitXor, opposite, right))
                return _invert_expr(target, left, new_rhs, source_loc, checks)
            if op == BinOp.Mult:
                # x * k == opp  →  x = opp // k, check opp % k == 0
                check = CheckNode(
                    ConstFold().visit(ExprBinOp(BinOp.Eq,
                                                ExprBinOp(BinOp.Mod, opposite, right),
                                                ExprConst(0))),
                    f"{source_loc} [divisibility-check]"
                )
                new_rhs = ConstFold().visit(ExprBinOp(BinOp.FloorDiv, opposite, right))
                return _invert_expr(target, left, new_rhs, source_loc,
                                    checks + [check])
            if op == BinOp.LShift:
                # x << n == opp  →  x = opp >> n, check opp & ((1<<n)-1) == 0
                n = right
                mask = ExprBinOp(BinOp.Sub,
                                 ExprBinOp(BinOp.LShift, ExprConst(1), n),
                                 ExprConst(1))
                check = CheckNode(
                    ConstFold().visit(ExprBinOp(BinOp.Eq,
                                                ExprBinOp(BinOp.BitAnd, opposite, mask),
                                                ExprConst(0))),
                    f"{source_loc} [lshift-alignment-check]"
                )
                new_rhs = ConstFold().visit(ExprBinOp(BinOp.RShift, opposite, n))
                return _invert_expr(target, left, new_rhs, source_loc,
                                    checks + [check])
            # BitAnd / BitOr / RShift — PARTIAL, not invertible
            return None

        else:  # t_in_right
            # k op f(x) == opp
            if op == BinOp.Add:
                # k + x == opp  →  x = opp - k
                new_rhs = ConstFold().visit(ExprBinOp(BinOp.Sub, opposite, left))
                return _invert_expr(target, right, new_rhs, source_loc, checks)
            if op == BinOp.Sub:
                # k - x == opp  →  x = k - opp
                new_rhs = ConstFold().visit(ExprBinOp(BinOp.Sub, left, opposite))
                return _invert_expr(target, right, new_rhs, source_loc, checks)
            if op == BinOp.BitXor:
                # k ^ x == opp  →  x = opp ^ k
                new_rhs = ConstFold().visit(ExprBinOp(BinOp.BitXor, opposite, left))
                return _invert_expr(target, right, new_rhs, source_loc, checks)
            if op == BinOp.Mult:
                # k * x == opp  →  x = opp // k
                check = CheckNode(
                    ConstFold().visit(ExprBinOp(BinOp.Eq,
                                                ExprBinOp(BinOp.Mod, opposite, left),
                                                ExprConst(0))),
                    f"{source_loc} [divisibility-check]"
                )
                new_rhs = ConstFold().visit(ExprBinOp(BinOp.FloorDiv, opposite, left))
                return _invert_expr(target, right, new_rhs, source_loc,
                                    checks + [check])
            # BitAnd / BitOr / LShift of (k op x) — not invertible
            return None

    # No other forms are invertible
    return None


# ---------------------------------------------------------------------------
# Selector-pattern detection (Phase 4)
# ---------------------------------------------------------------------------

_SELECTOR_THRESHOLD = 3  # minimum implications to collapse to a dict lookup


def _detect_selector_groups(
    implications: List[Tuple[str, EvalExpr, EvalExpr, str]],  # (target, cond, value, src)
    lookup_tables: Dict[str, dict],
    plan_assignments: List[AssignNode],
    plan_coverage_gaps: List[CoverageGap],
    counter: Dict[str, int],
) -> List[AssignNode]:
    """Detect selector patterns and replace ExprIf chains with ExprLookup nodes.

    Parameters
    ----------
    implications:
        List of (target_var, cond_expr, value_expr, source_loc) tuples, where
        ``cond_expr`` is ``BoundExpr == ExprConst(k)`` form.
    lookup_tables:
        Dict to accumulate table_name → {key: value} mappings.
    plan_assignments:
        Existing assignment list (to find any ExprIf chain for the same target).
    plan_coverage_gaps:
        List to append CoverageGap items to.
    counter:
        Mutable counter dict for generating unique table names.

    Returns
    -------
    New list of AssignNodes to replace the existing ones for the affected targets.
    """
    # Group by target variable
    by_target: Dict[str, List[Tuple]] = {}
    for target, cond, value, src in implications:
        by_target.setdefault(target, []).append((cond, value, src))

    replacements: Dict[str, AssignNode] = {}

    for target, items in by_target.items():
        if len(items) < _SELECTOR_THRESHOLD:
            continue

        # Check that all conditions are (key_expr == ExprConst) for the same key_expr
        keys_and_values: List[Tuple] = []
        key_expr_common: Optional[EvalExpr] = None
        valid = True

        for cond, value, src in items:
            # Cond must be ExprBinOp(Eq, key_expr, ExprConst(k))
            # or ExprBinOp(Eq, ExprConst(k), key_expr)
            if not isinstance(cond, ExprBinOp) or cond.op != BinOp.Eq:
                valid = False
                break
            if isinstance(cond.right, ExprConst):
                key_expr = cond.left
                key_val = (cond.right.value,)
            elif isinstance(cond.left, ExprConst):
                key_expr = cond.right
                key_val = (cond.left.value,)
            else:
                # Both sides non-constant: might be tuple-key; accept if ExprBinOp(BitAnd)
                # For now, not a simple single-key selector
                valid = False
                break

            # Normalize key_expr: if all items use the same key_expr, proceed
            if key_expr_common is None:
                key_expr_common = key_expr
            elif key_expr != key_expr_common:
                valid = False
                break

            keys_and_values.append((key_val[0], value, src))

        if not valid or key_expr_common is None:
            continue

        # Build lookup table
        table: Dict[Any, Any] = {}
        src_first = keys_and_values[0][2]
        for k, v, _ in keys_and_values:
            if isinstance(v, ExprConst):
                table[k] = v.value
            else:
                # Value is a non-constant EvalExpr — can't put in a static dict
                valid = False
                break

        if not valid:
            continue

        # Detect a default value from any existing ExprIf else_ branch
        default_val: Optional[int] = None
        # Look for existing assign for this target to extract default
        for a in plan_assignments:
            if a.var_name == target:
                default_val = _extract_else_default(a.expr)
                break

        default_node: EvalExpr = (ExprConst(default_val)
                                  if default_val is not None else ExprConst(0))

        # Generate unique table name
        count = counter.get('n', 0) + 1
        counter['n'] = count
        tname = f"_TABLE_{target.upper().replace('.', '_')}_{count}"
        lookup_tables[tname] = table

        # Build ExprLookup
        lookup_node = ExprLookup(
            table_name=tname,
            key=(key_expr_common,),
            default_expr=default_node,
        )

        # Coverage gap: enumerate missing keys if key is a small-width var
        # (conservative: only report if we can determine the range)
        replacements[target] = AssignNode(
            var_name=target,
            expr=lookup_node,
            checks=[],
            source_loc=src_first,
            write_back=True,  # will be overwritten with correct value below
        )

    return replacements


def _extract_else_default(expr: EvalExpr) -> Optional[int]:
    """Extract the final ``else`` branch constant from an ExprIf chain."""
    if isinstance(expr, ExprConst):
        return expr.value
    if isinstance(expr, ExprIf):
        return _extract_else_default(expr.else_)
    return None


# ---------------------------------------------------------------------------
# Main analyser
# ---------------------------------------------------------------------------

class ConstraintAnalyser:
    """Analyses action class constraints under design semantics.

    The main entry point is ``analyse()``.  It runs the iterative closure
    algorithm and returns a ``ConstraintEvalPlan``.
    """

    def analyse(
        self,
        action_class: type,
        struct_type,
        status_map: VarStatusMap,
    ) -> ConstraintEvalPlan:
        """Run the closure algorithm on *struct_type*'s constraints.

        Parameters
        ----------
        action_class:
            The Python class being analysed.
        struct_type:
            The IR ``DataTypeStruct`` / ``DataTypeClass`` for the class.
        status_map:
            Initial VarStatusMap (built by ``variable_status.build_from_struct``).
            Will be mutated during analysis.

        Returns
        -------
        ConstraintEvalPlan — the plan, possibly with ``underdetermined`` entries
        if some OPEN variables could not be resolved.
        """
        cls_name = getattr(action_class, '__name__', str(action_class))

        # ---- Build field-index → field-name map for _IRConverter ----------
        fields_by_index: Dict[int, str] = {
            i: f.name for i, f in enumerate(struct_type.fields)
        }

        # ---- Collect 1-bit field names (for ExprBoolMask wrapping) --------
        # Use Python class annotations to find fields declared as zdc.u1 or
        # similar width-1 types.  These are sign-extended to -1/0 when used
        # as operands of bitwise AND/OR/XOR, matching the solver's semantics.
        one_bit_field_names: Set[str] = set()
        if action_class is not None and hasattr(action_class, '__annotations__'):
            import typing
            for fname, ann in action_class.__annotations__.items():
                meta = getattr(ann, '__metadata__', ())
                for m in meta:
                    w = getattr(m, 'width', None)
                    if w == 1:
                        one_bit_field_names.add(fname)
                        break

        # ---- 1. Partition constraint functions by role --------------------
        requires_raws: List[Any] = []
        ensures_raws:  List[Any] = []
        body_raws:     List[Any] = []

        for func in struct_type.functions:
            md = getattr(func, 'metadata', {}) or {}
            if not (md.get('_is_constraint', False) or
                    getattr(func, 'is_invariant', False) or
                    md.get('_constraint_role') is not None):
                continue
            role = md.get('_constraint_role')
            src = f"{cls_name}.{func.name}"
            raws = _convert_stmts_to_raw(func.body, src, fields_by_index,
                                          one_bit_field_names)
            if role == 'requires':
                requires_raws.extend(raws)
            elif role == 'ensures':
                ensures_raws.extend(raws)
            else:
                body_raws.extend(raws)

        # ---- 2. Requires → direct preconditions ---------------------------
        preconditions: List[CheckNode] = []
        for raw in requires_raws:
            preconditions.extend(self._raw_to_checks(raw))

        # ---- 3. Ensures → direct postconditions ---------------------------
        postconditions: List[CheckNode] = []
        for raw in ensures_raws:
            postconditions.extend(self._raw_to_checks(raw))

        # ---- 4. Closure loop on body constraints --------------------------
        assignments: List[AssignNode] = []
        worklist = list(body_raws)
        changed = True

        while changed:
            changed = False
            next_worklist: List[Any] = []
            for raw in worklist:
                # Skip _RawIf in the main loop; handled in phase 4.5
                if isinstance(raw, _RawIf):
                    next_worklist.append(raw)
                    continue
                result = self._try_lower(raw, status_map, cls_name)
                if result is None:
                    # DEFERRED
                    next_worklist.append(raw)
                elif isinstance(result, AssignNode):
                    assignments.append(result)
                    status_map.bind(result.var_name)
                    changed = True
                elif isinstance(result, CheckNode):
                    # Classify as pre- or post-condition
                    if not status_map.open_var_names():
                        postconditions.append(result)
                    else:
                        preconditions.append(result)
                    changed = True
                elif isinstance(result, list):
                    # Multiple items (e.g. an ExprIf implication)
                    for item in result:
                        if isinstance(item, AssignNode):
                            assignments.append(item)
                            if item.var_name:
                                status_map.bind(item.var_name)
                        elif isinstance(item, CheckNode):
                            preconditions.append(item)
                    changed = True
            worklist = next_worklist

        # ---- 4.5. Selector pattern: accumulate _RawIf items ----------------
        # After the equality-based closure converges, process conditional
        # (_RawIf) items in bulk. All conditions whose guard vars are BOUND and
        # whose body is a single equality for an OPEN target are grouped by
        # target and combined into a chained ExprIf, avoiding the early-binding
        # bug that would occur if processed one at a time.
        selector_changed = True
        while selector_changed:
            selector_changed = False
            if_worklist = [r for r in worklist if isinstance(r, _RawIf)]
            other_worklist = [r for r in worklist if not isinstance(r, _RawIf)]

            target_to_cases: Dict[str, List[Tuple[EvalExpr, EvalExpr, str]]] = {}
            unresolved_ifs: List[_RawIf] = []

            for raw in if_worklist:
                cond_vars = collect_vars(raw.cond)
                if any(status_map.is_open(v) for v in cond_vars):
                    unresolved_ifs.append(raw)
                    continue
                # Body must be exactly one equality for a single OPEN target
                if len(raw.body) != 1 or not isinstance(raw.body[0], _RawEq):
                    # Multi-statement body: fall back to _try_lower_if
                    result = self._try_lower_if(raw, status_map, cls_name)
                    if result is None:
                        unresolved_ifs.append(raw)
                    else:
                        for item in (result if isinstance(result, list) else [result]):
                            if isinstance(item, AssignNode):
                                assignments.append(item)
                                if item.var_name:
                                    status_map.bind(item.var_name)
                            elif isinstance(item, CheckNode):
                                preconditions.append(item)
                        selector_changed = True
                    continue
                eq = raw.body[0]
                all_vars = collect_vars(eq.lhs) | collect_vars(eq.rhs)
                open_in_body = [v for v in all_vars if status_map.is_open(v)]
                if len(open_in_body) != 1:
                    # Already all-bound → becomes a conditional check
                    result = self._try_lower_if(raw, status_map, cls_name)
                    if result:
                        for item in (result if isinstance(result, list) else [result]):
                            if isinstance(item, CheckNode):
                                preconditions.append(item)
                        selector_changed = True
                    else:
                        unresolved_ifs.append(raw)
                    continue
                target = open_in_body[0]
                # Determine which side is the target and build value_expr
                lhs_vars = collect_vars(eq.lhs)
                value_expr = eq.rhs if (target in lhs_vars) else eq.lhs
                target_to_cases.setdefault(target, []).append(
                    (raw.cond, value_expr, raw.source_loc)
                )

            # Build chained ExprIf for each grouped target
            for target, cases in target_to_cases.items():
                write_back = status_map.write_back(target)
                chain: EvalExpr = ExprConst(0)
                for cond, val, _src in reversed(cases):
                    chain = ExprIf(ConstFold().visit(cond), val, chain)
                assignments.append(AssignNode(
                    var_name=target,
                    expr=chain,
                    checks=[],
                    source_loc=cases[0][2],
                    write_back=write_back,
                ))
                status_map.bind(target)
                selector_changed = True

            worklist = other_worklist + unresolved_ifs

            # With new BOUND targets, retry equality-based items
            if selector_changed and worklist:
                eq_changed = True
                while eq_changed:
                    eq_changed = False
                    next_wl: List[Any] = []
                    for raw in worklist:
                        if isinstance(raw, _RawIf):
                            next_wl.append(raw)
                            continue
                        result = self._try_lower(raw, status_map, cls_name)
                        if result is None:
                            next_wl.append(raw)
                        elif isinstance(result, AssignNode):
                            assignments.append(result)
                            status_map.bind(result.var_name)
                            eq_changed = True
                        elif isinstance(result, CheckNode):
                            if not status_map.open_var_names():
                                postconditions.append(result)
                            else:
                                preconditions.append(result)
                            eq_changed = True
                        elif isinstance(result, list):
                            for item in result:
                                if isinstance(item, AssignNode):
                                    assignments.append(item)
                                    if item.var_name:
                                        status_map.bind(item.var_name)
                                elif isinstance(item, CheckNode):
                                    preconditions.append(item)
                            eq_changed = True
                    worklist = next_wl

        # ---- 5. Any remaining worklist items → underdetermined ------------
        underdetermined: List[str] = []
        for raw in worklist:
            open_vars = self._collect_open_vars(raw, status_map)
            underdetermined.extend(open_vars)
        # Any OPEN variable never mentioned in any constraint is also underdetermined
        # (e.g. rand fields with only a domain — no explicit @constraint body).
        assigned_var_names: Set[str] = {a.var_name for a in assignments}
        for v in status_map.open_var_names():
            if v not in assigned_var_names:
                underdetermined.append(v)
        # Deduplicate while preserving order
        seen: Set[str] = set()
        ud_dedup: List[str] = []
        for v in underdetermined:
            if v not in seen:
                seen.add(v)
                ud_dedup.append(v)

        # ---- 6. Collect bound paths used in assignment exprs ---------------
        # A "bound path" is a pre-fetched object attribute that is ALREADY bound
        # at the start of the solve function (flow_input, non-rand field, etc.).
        # Variables that are computed as locals during the solve (assignment
        # targets) must NOT be added — they are referenced as Python locals, not
        # as pre-fetched self_obj attributes.
        assigned_vars: Set[str] = {a.var_name for a in assignments}
        bound_paths: Set[str] = set()
        for a in assignments:
            self._collect_bound_paths(a.expr, status_map, bound_paths, assigned_vars)
        for c in preconditions:
            self._collect_bound_paths(c.expr, status_map, bound_paths, assigned_vars)

        # ---- 7. Phase 4: Selector-pattern optimisation --------------------
        lookup_tables: Dict[str, dict] = {}
        coverage_gaps: List[CoverageGap] = []
        implications = self._collect_implications(assignments)
        counter: Dict[str, int] = {}
        replacements = _detect_selector_groups(
            implications, lookup_tables, assignments,
            coverage_gaps, counter
        )
        if replacements:
            new_assignments: List[AssignNode] = []
            for a in assignments:
                if a.var_name in replacements:
                    rep = replacements[a.var_name]
                    new_assignments.append(AssignNode(
                        var_name=rep.var_name,
                        expr=rep.expr,
                        checks=a.checks,
                        source_loc=a.source_loc,
                        write_back=a.write_back,
                    ))
                    del replacements[a.var_name]  # only replace first occurrence
                else:
                    new_assignments.append(a)
            assignments = new_assignments

        return ConstraintEvalPlan(
            action_class=action_class,
            preconditions=preconditions,
            assignments=assignments,
            postconditions=postconditions,
            underdetermined=ud_dedup,
            bound_paths=sorted(bound_paths),
            coverage_gaps=coverage_gaps,
            lookup_tables=lookup_tables,
        )

    # ------------------------------------------------------------------
    # Lowering helpers
    # ------------------------------------------------------------------

    def _try_lower(
        self,
        raw,
        status_map: VarStatusMap,
        cls_name: str,
    ) -> Optional[Any]:
        """Attempt to lower *raw* to an AssignNode, CheckNode, or list thereof.

        Returns
        -------
        AssignNode | CheckNode | list | None
        None means DEFERRED (try again next pass).
        """
        if isinstance(raw, _RawEq):
            return self._try_lower_eq(raw, status_map)
        if isinstance(raw, _RawCheck):
            return self._try_lower_check(raw, status_map)
        if isinstance(raw, _RawIf):
            return self._try_lower_if(raw, status_map, cls_name)
        return None

    def _try_lower_eq(
        self,
        raw: _RawEq,
        status_map: VarStatusMap,
    ) -> Optional[Any]:
        """Try to lower an equality constraint."""
        all_vars = collect_vars(raw.lhs) | collect_vars(raw.rhs)
        open_vars = [v for v in all_vars if status_map.is_open(v)]

        if len(open_vars) == 0:
            # All BOUND → check
            check_expr = ConstFold().visit(ExprBinOp(BinOp.Eq, raw.lhs, raw.rhs))
            return CheckNode(check_expr, raw.source_loc)

        if len(open_vars) == 1:
            target = open_vars[0]
            result = _try_invert(target, raw.lhs, raw.rhs, raw.source_loc)
            if result is not None:
                value_expr, side_checks = result
                write_back = status_map.write_back(target)
                return AssignNode(
                    var_name=target,
                    expr=value_expr,
                    checks=side_checks,
                    source_loc=raw.source_loc,
                    write_back=write_back,
                )
            # Could not invert — DEFERRED
            return None

        # ≥ 2 open vars → DEFERRED
        return None

    def _try_lower_check(
        self,
        raw: _RawCheck,
        status_map: VarStatusMap,
    ) -> Optional[CheckNode]:
        """Try to lower a check expression."""
        open_vars = [v for v in collect_vars(raw.expr) if status_map.is_open(v)]
        if not open_vars:
            folded = ConstFold().visit(raw.expr)
            return CheckNode(folded, raw.source_loc)
        return None  # DEFERRED

    def _try_lower_if(
        self,
        raw: _RawIf,
        status_map: VarStatusMap,
        cls_name: str,
    ) -> Optional[Any]:
        """Try to lower an implication constraint."""
        cond_vars = collect_vars(raw.cond)
        cond_open = [v for v in cond_vars if status_map.is_open(v)]

        if cond_open:
            # Condition contains OPEN vars — deferred until they become BOUND
            return None

        # All condition vars are BOUND → process body
        # Try to lower each body constraint
        result_items: List[Any] = []
        all_resolved = True

        for body_raw in raw.body:
            item = self._try_lower(body_raw, status_map.copy(), cls_name)
            if item is None:
                all_resolved = False
                break
            if isinstance(item, AssignNode):
                # Wrap in ExprIf
                cond_folded = ConstFold().visit(raw.cond)
                wrapped_expr = ExprIf(
                    cond=cond_folded,
                    then_=item.expr,
                    else_=ExprConst(0),  # no-op value for else
                )
                result_items.append(AssignNode(
                    var_name=item.var_name,
                    expr=wrapped_expr,
                    checks=item.checks,
                    source_loc=raw.source_loc,
                    write_back=item.write_back,
                ))
            elif isinstance(item, CheckNode):
                # Wrap check in implication: if cond: assert check
                cond_folded = ConstFold().visit(raw.cond)
                wrapped = CheckNode(
                    ExprIf(cond_folded, item.expr, ExprConst(1)),
                    raw.source_loc,
                )
                result_items.append(wrapped)
            elif isinstance(item, list):
                result_items.extend(item)
            else:
                all_resolved = False

        if not all_resolved:
            return None  # DEFERRED

        return result_items if result_items else None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _raw_to_checks(self, raw) -> List[CheckNode]:
        """Convert a raw constraint directly to check nodes (for requires/ensures)."""
        if isinstance(raw, _RawEq):
            expr = ConstFold().visit(ExprBinOp(BinOp.Eq, raw.lhs, raw.rhs))
            return [CheckNode(expr, raw.source_loc)]
        if isinstance(raw, _RawCheck):
            return [CheckNode(ConstFold().visit(raw.expr), raw.source_loc)]
        if isinstance(raw, _RawIf):
            # Wrap as: cond => check(body)
            checks: List[CheckNode] = []
            for item in raw.body:
                for c in self._raw_to_checks(item):
                    checks.append(CheckNode(
                        ExprIf(raw.cond, c.expr, ExprConst(1)),
                        raw.source_loc,
                    ))
            return checks
        return []

    def _collect_open_vars(self, raw, status_map: VarStatusMap) -> List[str]:
        """Collect all OPEN var names referenced in *raw*."""
        if isinstance(raw, _RawEq):
            all_vars = collect_vars(raw.lhs) | collect_vars(raw.rhs)
        elif isinstance(raw, _RawCheck):
            all_vars = collect_vars(raw.expr)
        elif isinstance(raw, _RawIf):
            all_vars = collect_vars(raw.cond)
            for b in raw.body:
                all_vars |= set(self._collect_open_vars(b, status_map))
        else:
            all_vars = set()
        return [v for v in all_vars if status_map.is_open(v)]

    def _collect_bound_paths(
        self,
        expr: EvalExpr,
        status_map: VarStatusMap,
        paths: Set[str],
        excluded_vars: Optional[Set[str]] = None,
    ) -> None:
        """Walk *expr* and add all BOUND ExprVar paths to *paths*.

        Parameters
        ----------
        excluded_vars:
            Variable names that should NOT be added even if bound — these are
            assignment targets computed as Python locals during the solve, not
            pre-fetched object attributes.
        """
        if isinstance(expr, ExprVar):
            if status_map.is_bound(expr.name):
                if excluded_vars is None or expr.name not in excluded_vars:
                    paths.add(expr.name)
        elif isinstance(expr, ExprBinOp):
            self._collect_bound_paths(expr.left, status_map, paths, excluded_vars)
            self._collect_bound_paths(expr.right, status_map, paths, excluded_vars)
        elif isinstance(expr, ExprUnary):
            self._collect_bound_paths(expr.operand, status_map, paths, excluded_vars)
        elif isinstance(expr, (ExprSext, ExprMask, ExprCbit, ExprSigned, ExprBoolMask)):
            self._collect_bound_paths(expr.expr, status_map, paths, excluded_vars)
        elif isinstance(expr, ExprIf):
            self._collect_bound_paths(expr.cond, status_map, paths, excluded_vars)
            self._collect_bound_paths(expr.then_, status_map, paths, excluded_vars)
            self._collect_bound_paths(expr.else_, status_map, paths, excluded_vars)
        elif isinstance(expr, ExprLookup):
            for k in expr.key:
                self._collect_bound_paths(k, status_map, paths, excluded_vars)
            self._collect_bound_paths(expr.default_expr, status_map, paths, excluded_vars)

    def _collect_implications(
        self,
        assignments: List[AssignNode],
    ) -> List[Tuple[str, EvalExpr, EvalExpr, str]]:
        """Extract (target, cond, value, src) tuples from ExprIf AssignNodes."""
        result: List[Tuple[str, EvalExpr, EvalExpr, str]] = []
        for a in assignments:
            if isinstance(a.expr, ExprIf):
                result.append((a.var_name, a.expr.cond, a.expr.then_, a.source_loc))
        return result
