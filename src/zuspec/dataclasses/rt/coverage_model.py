"""Runtime coverage model for PSS covergroup sampling.

Tracks sampled coverpoint values and cross-product hit counts for
``PssCoverGroup`` instances attached to actions via ``__pss_covergroups__``.
Sampling is triggered after body/activity execution in ``ActivityRunner._traverse``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


class PssCoverageModel:
    """Simple accumulator for PSS covergroup coverage data.

    Coverpoints accumulate all sampled values; crosses accumulate
    a hit-count dict keyed by the tuple of coverpoint values at sample time.
    """

    def __init__(self):
        # (cg_instance_name, cp_name) -> list of sampled values
        self._coverpoints: Dict[Tuple[str, str], List[Any]] = {}
        # (cg_instance_name, cx_name) -> {(v1, v2, ...): count}
        self._crosses: Dict[Tuple[str, str], Dict[tuple, int]] = {}
        # last sampled value per coverpoint (needed for cross sampling)
        self._last_value: Dict[Tuple[str, str], Any] = {}

    # ------------------------------------------------------------------
    # Sampling API
    # ------------------------------------------------------------------

    def sample(self, cg_name: str, cp_name: str, value: Any) -> None:
        """Record a sampled value for coverpoint ``cp_name`` in group ``cg_name``."""
        key = (cg_name, cp_name)
        self._coverpoints.setdefault(key, []).append(value)
        self._last_value[key] = value

    def sample_cross(self, cg_name: str, cx_name: str, values: tuple) -> None:
        """Record a cross hit for the given ``values`` tuple."""
        key = (cg_name, cx_name)
        bucket = self._crosses.setdefault(key, {})
        bucket[values] = bucket.get(values, 0) + 1

    def last_value(self, cg_name: str, cp_name: str) -> Optional[Any]:
        """Return the most recent sampled value for a coverpoint, or ``None``."""
        return self._last_value.get((cg_name, cp_name))

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    @property
    def coverpoints(self) -> Dict[Tuple[str, str], List[Any]]:
        """All sampled coverpoint values keyed by ``(cg_name, cp_name)``."""
        return dict(self._coverpoints)

    @property
    def crosses(self) -> Dict[Tuple[str, str], Dict[tuple, int]]:
        """Cross hit counts keyed by ``(cg_name, cx_name)``."""
        return dict(self._crosses)

    def coverpoint_samples(self, cg_name: str, cp_name: str) -> List[Any]:
        """Return all sampled values for one coverpoint."""
        return list(self._coverpoints.get((cg_name, cp_name), []))

    def cross_hits(self, cg_name: str, cx_name: str) -> Dict[tuple, int]:
        """Return the hit-count dict for one cross."""
        return dict(self._crosses.get((cg_name, cx_name), {}))

    def all_covered(self) -> bool:
        """Return True when every tracked cross has hit all expected bins.

        "Expected bins" for a cross is the Cartesian product of all distinct
        values observed so far for each participating coverpoint.  This
        means the fill loop terminates once no new value combinations remain
        to be hit (every combo of observed values has been sampled).

        Returns False (no coverage) when no crosses have been registered yet.
        """
        if not self._crosses:
            return False
        for (cg_name, cx_name), hits in self._crosses.items():
            # Find the coverpoint names for this cross by inspecting hits keys
            # (we don't store the cross definition here, so infer from observed data)
            # Instead, find all coverpoints in this covergroup and compute expected product
            cp_keys = [(cg_name, cp) for (cg, cp) in self._coverpoints if cg == cg_name]
            if not cp_keys:
                return False
            # Get distinct values observed per coverpoint
            cp_values = [set(self._coverpoints[k]) for k in cp_keys if k in self._coverpoints]
            if not cp_values or any(not v for v in cp_values):
                return False
            # Expected = Cartesian product of all observed values per coverpoint
            from itertools import product as _product
            expected_count = 1
            for vals in cp_values:
                expected_count *= len(vals)
            if len(hits) < expected_count:
                return False
        return True

    def all_covered_for_cross(self, cg_name: str, cx_name: str,
                               coverpoint_names: list) -> bool:
        """Check coverage for one specific cross, given its coverpoint names."""
        hits = self._crosses.get((cg_name, cx_name), {})
        cp_value_sets = []
        for cp_name in coverpoint_names:
            vals = set(self._coverpoints.get((cg_name, cp_name), []))
            cp_value_sets.append(vals)
        if not cp_value_sets or any(not v for v in cp_value_sets):
            return False
        from itertools import product as _product
        expected = set(_product(*cp_value_sets))
        return expected.issubset(hits.keys())


def eval_cover_expr(expr: Any, action_instance: Any) -> Any:
    """Evaluate a PSS coverpoint ``target_expr`` against a live action instance.

    ``target_expr`` is always a simple field-path IR expression rooted at
    ``TypeExprRefSelf()``, so a recursive ``getattr`` walk is sufficient.

    Returns ``None`` if any attribute in the chain is missing.
    """
    from zuspec.ir.core.expr import ExprAttribute, TypeExprRefSelf
    if isinstance(expr, TypeExprRefSelf):
        return action_instance
    if isinstance(expr, ExprAttribute):
        base = eval_cover_expr(expr.value, action_instance)
        if base is None:
            return None
        return getattr(base, expr.attr, None)
    return None
