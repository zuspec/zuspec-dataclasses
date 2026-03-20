"""Structural inference solver (Phase S).

Resolves unbound flow-object inputs on an action by selecting candidate
producer action types from the ICL table and determining their ordering
relative to the consumer.

LRM ordering rules (§5.4, §16.4.3):
  - Buffer / State inputs  → producer must execute **before** consumer (sequential)
  - Stream inputs          → producer executes **concurrently** with consumer
"""
from __future__ import annotations

import dataclasses as dc
import random
from typing import Any, Dict, List, Literal, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .icl_table import ICLTable, ICLEntry
    from .action_context import ActionContext


class InferenceFeasibilityError(RuntimeError):
    """Raised when no ICL candidate exists for an unbound slot."""


class InferenceLimitError(RuntimeError):
    """Raised when the DFS depth limit is exceeded during inference."""


@dc.dataclass
class InferredAction:
    """An action type inferred to satisfy a consumer's unbound flow slot."""
    action_type: type
    """The action type to instantiate as producer."""
    ordering: Literal["sequential_before", "concurrent"]
    """How to schedule the inferred action relative to the consumer."""
    output_field: str
    """Field name on the producer that supplies the flow object."""
    input_field: str
    """Field name on the consumer that receives the flow object."""
    flow_obj_type: type
    """The shared flow-object type."""


class StructuralSolver:
    """Resolves unbound flow-object inputs by searching the ICL table.

    A depth-first search selects one ICL candidate per unbound slot.
    Cycles are prevented by tracking types already in the current search path.

    Args:
        icl_table: Pre-built ICL table from :class:`ICLTable.build`.
        max_depth: Maximum recursion depth for multi-level inference chains.
        seed: Optional RNG seed for reproducible candidate selection.
    """

    def __init__(
        self,
        icl_table: "ICLTable",
        max_depth: int = 5,
        seed: Optional[int] = None,
    ) -> None:
        self._icl = icl_table
        self._max_depth = max_depth
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def solve(
        self,
        consumer_type: type,
        unbound_slots: List[Tuple[str, type]],
        ctx: "ActionContext",
    ) -> List[InferredAction]:
        """Return inferred actions needed to satisfy *consumer_type*'s unbound slots.

        Args:
            consumer_type: The action type with unbound flow-input fields.
            unbound_slots: List of ``(field_name, flow_obj_type)`` tuples.
            ctx: Current traversal context (used for cycle tracking).

        Returns:
            Ordered list of :class:`InferredAction` instances.  Sequential
            producers come before the consumer; concurrent producers run
            alongside it.

        Raises:
            InferenceFeasibilityError: No candidate exists for a slot.
            InferenceLimitError: DFS depth limit exceeded.
        """
        return self._solve_recursive(
            consumer_type=consumer_type,
            unbound_slots=unbound_slots,
            depth=0,
            seen={consumer_type},
        )

    # ------------------------------------------------------------------
    # Internal DFS
    # ------------------------------------------------------------------

    def _solve_recursive(
        self,
        consumer_type: type,
        unbound_slots: List[Tuple[str, type]],
        depth: int,
        seen: Set[type],
    ) -> List[InferredAction]:
        if depth > self._max_depth:
            raise InferenceLimitError(
                f"Structural inference depth limit ({self._max_depth}) exceeded "
                f"while resolving {consumer_type.__name__}"
            )

        result: List[InferredAction] = []

        for field_name, flow_obj_type in unbound_slots:
            candidates = self._icl.candidates(consumer_type, field_name)
            if not candidates:
                raise InferenceFeasibilityError(
                    f"No ICL candidate found for "
                    f"{consumer_type.__name__}.{field_name} "
                    f"(flow type: {flow_obj_type.__name__})"
                )

            # Filter out types already in the current search path (cycle guard)
            available = [c for c in candidates if c.action_type not in seen]
            if not available:
                raise InferenceFeasibilityError(
                    f"All ICL candidates for "
                    f"{consumer_type.__name__}.{field_name} "
                    f"form a cycle: {[c.action_type.__name__ for c in candidates]}"
                )

            # Choose one candidate (random for variety; deterministic via seed)
            entry = self._rng.choice(available)

            ordering = _ordering_for_flow_type(flow_obj_type)
            ia = InferredAction(
                action_type=entry.action_type,
                ordering=ordering,
                output_field=entry.output_field,
                input_field=field_name,
                flow_obj_type=flow_obj_type,
            )

            # Recursively resolve any unbound slots the inferred action itself has
            sub_unbound = _find_unbound_flow_inputs(entry.action_type, set())
            if sub_unbound:
                new_seen = seen | {entry.action_type}
                sub_actions = self._solve_recursive(
                    consumer_type=entry.action_type,
                    unbound_slots=sub_unbound,
                    depth=depth + 1,
                    seen=new_seen,
                )
                # Sub-actions must precede the inferred action
                result.extend(sub_actions)

            result.append(ia)

        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ordering_for_flow_type(flow_obj_type: type) -> Literal["sequential_before", "concurrent"]:
    """Return the required scheduling relationship for a given flow type."""
    from ..types import Stream
    try:
        if issubclass(flow_obj_type, Stream):
            return "concurrent"
    except TypeError:
        pass
    return "sequential_before"


def _find_unbound_flow_inputs(
    action_type: type,
    already_bound: Set[str],
) -> List[Tuple[str, type]]:
    """Return (field_name, flow_obj_type) tuples for unbound flow-input fields.

    A flow-input field is *unbound* when it is not already present in
    *already_bound* (i.e., not yet provided by the current flow-binding context).
    """
    try:
        fields = dc.fields(action_type)
    except TypeError:
        return []

    ann: Dict[str, Any] = {}
    for klass in action_type.__mro__:
        ann.update(klass.__dict__.get("__annotations__", {}))

    result = []
    for f in fields:
        meta = f.metadata or {}
        if meta.get("kind") != "flow_ref":
            continue
        if meta.get("direction") != "input":
            continue
        if f.name in already_bound:
            continue
        flow_obj_type = ann.get(f.name)
        if isinstance(flow_obj_type, type):
            result.append((f.name, flow_obj_type))
    return result
