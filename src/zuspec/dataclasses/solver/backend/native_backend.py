"""Native C solver back-end.

Translates the constraint AST produced by ``ConstraintSystemBuilder`` into
calls to the C ``SolveProblemBuilder`` API, compiles with ``SolveCtx``, and
reads back the solution.
"""
from __future__ import annotations

import ctypes as _ctypes
import math
import weakref
from typing import Any, Dict, List, Optional, Tuple

from zuspec.ir.core.expr import BinOp, UnaryOp, BoolOp, CmpOp

from ..core.constraint import Constraint
from ..core.constraints import (
    ConstantConstraint, VariableRefConstraint, BinaryOpConstraint,
    UnaryOpConstraint, BoolOpConstraint, CompareConstraint,
    CompareChainConstraint, ImplicationConstraint, InConstraint,
    UniqueConstraint, SextConstraint, CbitConstraint, SignedViewConstraint,
)

# ------------------------------------------------------------------ #
# BinOp mapping: Python IR enum  →  C BIN_* int                      #
# Must match the BinOp enum in zsp_problem.h                         #
# ------------------------------------------------------------------ #
_BINOP_MAP = {
    BinOp.Add:    0,   # BIN_ADD
    BinOp.Sub:    1,   # BIN_SUB
    BinOp.Mult:   2,   # BIN_MUL
    BinOp.Div:    3,   # BIN_DIV
    BinOp.Mod:    4,   # BIN_MOD
    BinOp.BitAnd: 5,   # BIN_BAND
    BinOp.BitOr:  6,   # BIN_BOR
    BinOp.BitXor: 7,   # BIN_BXOR
    BinOp.LShift: 8,   # BIN_LSHIFT
    BinOp.RShift: 9,   # BIN_RSHIFT
    BinOp.Eq:     10,  # BIN_EQ
    BinOp.NotEq:  11,  # BIN_NEQ
    BinOp.Lt:     12,  # BIN_LT
    BinOp.LtE:    13,  # BIN_LTE
    BinOp.Gt:     14,  # BIN_GT
    BinOp.GtE:    15,  # BIN_GTE
    BinOp.And:    16,  # BIN_AND
    BinOp.Or:     17,  # BIN_OR
}

_CMPOP_TO_BINOP = {
    CmpOp.Eq:    10,
    CmpOp.NotEq: 11,
    CmpOp.Lt:    12,
    CmpOp.LtE:   13,
    CmpOp.Gt:    14,
    CmpOp.GtE:   15,
}

_UNARYOP_MAP = {
    UnaryOp.USub:   0,  # UN_NEG
    UnaryOp.Not:    1,  # UN_NOT
    UnaryOp.Invert: 2,  # UN_INVERT
}


# Per-class cache: struct_type + native problem bytes
_class_cache: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def bench_native_loop(cls, n, seed=1):
    """Run *n* solves of *cls* in a tight native loop.

    Returns ``(elapsed_ns, n_ok, solutions)`` where each solution is a
    dict mapping field names to values.  The compile cost is excluded
    from the timing.

    This is the benchmark-specific fast path: one Python call for N
    randomizations.
    """
    import time
    from .._core_solve import _extract_struct_type, RandomizationError
    from ..frontend.constraint_system_builder import ConstraintSystemBuilder
    from dv_solve.builder import SolveProblemBuilder
    from dv_solve.ctx import SolveCtx, SOLVE_OK

    # Build
    struct_type = _extract_struct_type(cls(
        **{f["name"]: f.get("default", 0)
           for f in __import__("zuspec.dataclasses", fromlist=["extract_rand_fields"]).extract_rand_fields(cls)}
    ))
    builder = ConstraintSystemBuilder()
    system = builder.build_from_struct(struct_type)

    pb, var_map = _build_native_problem(system)
    problem_bytes, _sz = pb.finalize()

    # Identify field-only variables (exclude compiler temps)
    import zuspec.dataclasses as zdc
    field_names = [f["name"] for f in zdc.extract_rand_fields(cls)]
    ordered_fields = [f for f in field_names if f in var_map]
    n_vars = len(ordered_fields)
    var_ids = (_ctypes.c_uint32 * n_vars)(*(var_map[f] for f in ordered_fields))

    # Compile once
    try:
        ctx = SolveCtx(problem_bytes)
    except Exception as exc:
        raise RuntimeError(
            f"Native compile failed ({exc}); "
            "this constraint set may require features not yet supported "
            "by the C solver."
        ) from exc

    # Timed loop
    t0 = time.perf_counter_ns()
    # Adaptive shave: skip for small problems, scale with var count
    if n_vars <= 3:
        shave = 0
    elif n_vars <= 8:
        shave = n_vars * 2
    else:
        shave = min(n_vars * 4, 100)
    n_ok, raw = ctx.solve_n(n, var_ids, n_vars, base_seed=seed,
                            max_shave_iters=shave)
    elapsed = time.perf_counter_ns() - t0

    # Convert to dicts
    solutions = [dict(zip(ordered_fields, vals)) for vals in raw]

    ctx.destroy()
    return elapsed, n_ok, solutions


class NativeSolverBackend:
    """Back-end that drives the native C constraint solver."""

    @property
    def name(self) -> str:
        return "native"

    @property
    def available(self) -> bool:
        try:
            from dv_solve.lib import _load_lib
            return _load_lib() is not None
        except Exception:
            return False

    def randomize(
        self,
        obj: Any,
        seed: Optional[int] = None,
        timeout_ms: Optional[int] = 1000,
    ) -> None:
        from .._core_solve import (
            _extract_struct_type,
            RandomizationError,
        )
        from ..frontend.constraint_system_builder import (
            ConstraintSystemBuilder,
            BuildError,
        )
        from dv_solve.builder import SolveProblemBuilder
        from dv_solve.ctx import SolveCtx, SOLVE_OK, CompileIncompleteError

        cls = obj.__class__
        cached = _class_cache.get(cls)

        if cached is not None:
            struct_type, var_map, problem_bytes, problem_size = cached
        else:
            struct_type = _extract_struct_type(obj)
            builder = ConstraintSystemBuilder()
            try:
                system = builder.build_from_struct(struct_type)
            except BuildError as exc:
                # Mirror the Python backend: surface build failures (notably the
                # "No random variables found in struct" no-op case) as a
                # RandomizationError, which the activity runner recognizes and
                # tolerates for actions with nothing to randomize.
                raise RandomizationError(
                    f"Native solver: failed to build constraint system: {exc}"
                ) from exc

            # Build the C problem from the constraint system
            try:
                pb, var_map = _build_native_problem(system)
                problem_bytes, problem_size = pb.finalize()
            except Exception as exc:
                raise RandomizationError(
                    f"Native solver: failed to build problem: {exc}"
                ) from exc

            _class_cache[cls] = (struct_type, var_map, problem_bytes, problem_size)

        # Solve
        try:
            ctx = SolveCtx(problem_bytes)
        except CompileIncompleteError:
            # Fall back to Python solver for unsupported constraints
            from .python_backend import PythonSolverBackend
            PythonSolverBackend().randomize(obj, seed, timeout_ms)
            return
        except Exception as exc:
            raise RandomizationError(
                f"Native solver: compile failed: {exc}"
            ) from exc

        with ctx:
            import random as _random
            if seed is None:
                seed = _random.getrandbits(64)
            result = ctx.solve(seed=seed)
            if result != SOLVE_OK:
                raise RandomizationError("No solution found (native UNSAT)")

            # Read values back into the object
            for field_name, var_id in var_map.items():
                if hasattr(obj, field_name):
                    setattr(obj, field_name, ctx.get_value(var_id))

    def randomize_with(
        self,
        obj: Any,
        with_block: Any,
        seed: Optional[int] = None,
        timeout_ms: Optional[int] = 1000,
    ) -> None:
        raise NotImplementedError(
            "randomize_with on NativeSolverBackend is not yet wired"
        )


def _build_native_problem(system):
    """Translate a ConstraintSystem into a SolveProblemBuilder.

    Returns (builder, var_map) where var_map maps field names to C var IDs.
    """
    from dv_solve.builder import SolveProblemBuilder

    pb = SolveProblemBuilder()
    var_map: Dict[str, int] = {}  # field_name -> C var_id
    _name_to_id: Dict[str, int] = {}  # all var names (including temps) -> C var_id
    _next_id = 0

    # Add variables
    for name, var in system.variables.items():
        domain = var.domain
        lo = domain.min_val
        hi = domain.max_val
        width = max(domain.width, 8)
        signed = 1 if domain.signed else 0
        var_id = pb.add_var(_next_id, width=width, is_signed=signed, lo=lo, hi=hi)
        _name_to_id[name] = _next_id
        var_map[name] = _next_id
        _next_id += 1

    # Context for linearization: allows _emit_constraint to allocate
    # temporary variables for nested sub-expressions.
    emit_ctx = {"next_id": _next_id, "pb": pb}

    # Add constraints
    for constraint in system.constraints:
        expr_ref = _emit_constraint(pb, constraint, system, _name_to_id, emit_ctx)
        if expr_ref is not None:
            pb.add_constraint(expr_ref)

    return pb, var_map


def _alloc_temp_var(emit_ctx, width=32, lo=-(1 << 30), hi=(1 << 30) - 1):
    """Allocate a temporary variable in the C problem for linearization."""
    vid = emit_ctx["next_id"]
    emit_ctx["next_id"] = vid + 1
    emit_ctx["pb"].add_var(vid, width=max(width, 32), is_signed=1, lo=lo, hi=hi)
    return vid


def _is_leaf(constraint) -> bool:
    """Return True if the constraint is a leaf (var ref or constant)."""
    return isinstance(constraint, (ConstantConstraint, VariableRefConstraint))


def _emit_constraint(pb, constraint, system, name_to_id, emit_ctx) -> Optional[int]:
    """Recursively emit a constraint AST node into the C builder.

    Returns an ExprRef (uint32) or None if the constraint can't be translated.
    """
    if isinstance(constraint, ConstantConstraint):
        return pb.expr_const(constraint.value, 64)

    elif isinstance(constraint, VariableRefConstraint):
        vid = name_to_id.get(constraint.variable.name)
        if vid is None:
            return None
        return pb.expr_var(vid)

    elif isinstance(constraint, BinaryOpConstraint):
        left = _emit_constraint(pb, constraint.left, system, name_to_id, emit_ctx)
        right = _emit_constraint(pb, constraint.right, system, name_to_id, emit_ctx)
        if left is None or right is None:
            return None
        c_op = _BINOP_MAP.get(constraint.op)
        if c_op is None:
            return None

        # For arithmetic ops with non-leaf operands, linearize by
        # introducing a temporary variable: tmp == sub_expr, then use tmp.
        # This ensures the C compiler sees only `var op var` patterns.
        arith_ops = {BinOp.Add, BinOp.Sub, BinOp.Mult, BinOp.Div, BinOp.Mod,
                     BinOp.BitAnd, BinOp.BitOr, BinOp.BitXor,
                     BinOp.LShift, BinOp.RShift}
        if constraint.op == BinOp.Eq and (
            isinstance(constraint.right, BinaryOpConstraint) and
            constraint.right.op in arith_ops and
            not _is_leaf(constraint.right.left) and
            not _is_leaf(constraint.right.right)
        ):
            # Pattern: result == complex_expr
            # Linearize: tmp == inner_lhs OP inner_rhs; result == tmp OP2 ...
            # Actually, linearize the inner non-leaf operand of the right side
            pass  # Fall through to default; the general case below handles it

        if constraint.op in arith_ops:
            # Check if either child is a non-leaf BinaryOp; if so,
            # introduce a temp var for it.
            if (isinstance(constraint.left, BinaryOpConstraint) and
                constraint.left.op in arith_ops and
                not _is_leaf(constraint.left)):
                # Left is complex: tmp = left_expr, then use tmp
                tmp_id = _alloc_temp_var(emit_ctx)
                tmp_ref = pb.expr_var(tmp_id)
                # Emit: tmp == left_expr  (as a constraint)
                eq_ref = pb.expr_binary(10, tmp_ref, left)  # BIN_EQ
                pb.add_constraint(eq_ref)
                left = tmp_ref

            if (isinstance(constraint.right, BinaryOpConstraint) and
                constraint.right.op in arith_ops and
                not _is_leaf(constraint.right)):
                tmp_id = _alloc_temp_var(emit_ctx)
                tmp_ref = pb.expr_var(tmp_id)
                eq_ref = pb.expr_binary(10, tmp_ref, right)  # BIN_EQ
                pb.add_constraint(eq_ref)
                right = tmp_ref

        return pb.expr_binary(c_op, left, right)

    elif isinstance(constraint, UnaryOpConstraint):
        operand = _emit_constraint(pb, constraint.operand, system, name_to_id, emit_ctx)
        if operand is None:
            return None
        c_op = _UNARYOP_MAP.get(constraint.op)
        if c_op is None:
            return None
        return pb.expr_unary(c_op, operand)

    elif isinstance(constraint, BoolOpConstraint):
        # AND / OR of multiple sub-constraints
        c_op = 16 if constraint.op == BoolOp.And else 17  # BIN_AND / BIN_OR
        refs = [_emit_constraint(pb, v, system, name_to_id, emit_ctx) for v in constraint.values]
        if any(r is None for r in refs):
            return None
        # Chain into binary tree
        result = refs[0]
        for r in refs[1:]:
            result = pb.expr_binary(c_op, result, r)
        return result

    elif isinstance(constraint, CompareConstraint):
        left = _emit_constraint(pb, constraint.left, system, name_to_id, emit_ctx)
        right = _emit_constraint(pb, constraint.right, system, name_to_id, emit_ctx)
        if left is None or right is None:
            return None
        c_op = _CMPOP_TO_BINOP.get(constraint.op)
        if c_op is None:
            return None

        # If either side is a non-leaf expression (e.g. var + const),
        # linearize it so the C compiler sees only var op var/const.
        if isinstance(constraint.right, BinaryOpConstraint) and not _is_leaf(constraint.right):
            tmp_id = _alloc_temp_var(emit_ctx)
            tmp_ref = pb.expr_var(tmp_id)
            eq_ref = pb.expr_binary(10, tmp_ref, right)  # BIN_EQ
            pb.add_constraint(eq_ref)
            right = tmp_ref
        if isinstance(constraint.left, BinaryOpConstraint) and not _is_leaf(constraint.left):
            tmp_id = _alloc_temp_var(emit_ctx)
            tmp_ref = pb.expr_var(tmp_id)
            eq_ref = pb.expr_binary(10, tmp_ref, left)  # BIN_EQ
            pb.add_constraint(eq_ref)
            left = tmp_ref

        return pb.expr_binary(c_op, left, right)

    elif isinstance(constraint, CompareChainConstraint):
        # a < b < c  →  (a < b) AND (b < c)
        refs = []
        for i, (op, right_c) in enumerate(zip(constraint.ops, constraint.comparators)):
            left_c = constraint.left if i == 0 else constraint.comparators[i - 1]
            l = _emit_constraint(pb, left_c, system, name_to_id, emit_ctx)
            r = _emit_constraint(pb, right_c, system, name_to_id, emit_ctx)
            if l is None or r is None:
                return None
            c_op = _CMPOP_TO_BINOP.get(op)
            if c_op is None:
                return None
            refs.append(pb.expr_binary(c_op, l, r))
        result = refs[0]
        for r in refs[1:]:
            result = pb.expr_binary(16, result, r)  # BIN_AND
        return result

    elif isinstance(constraint, ImplicationConstraint):
        # condition -> then_body  ≡  !condition OR then_body
        cond = _emit_constraint(pb, constraint.condition, system, name_to_id, emit_ctx)
        then = _emit_constraint(pb, constraint.then_body, system, name_to_id, emit_ctx)
        if cond is None or then is None:
            return None
        not_cond = pb.expr_unary(1, cond)  # UN_NOT
        return pb.expr_binary(17, not_cond, then)  # BIN_OR

    elif isinstance(constraint, UniqueConstraint):
        import ctypes
        var_ids = []
        for var_name in constraint.variables:
            vid = name_to_id.get(var_name)
            if vid is None:
                return None
            var_ids.append(vid)
        n = len(var_ids)
        arr = (ctypes.c_uint32 * n)(*var_ids)
        pb.add_all_different(n, arr)
        return None  # all_different is added directly, not as an expression

    else:
        # Unsupported constraint type — will cause CompileIncompleteError
        return None
