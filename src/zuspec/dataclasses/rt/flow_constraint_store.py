"""Flow-object constraint back-propagation store.

In PSS, when a producer action creates a buffer/stream/state flow object,
the consumer's constraints on that flow object's fields must be satisfied.
The correct direction (per LRM §5.4 / §16.4.3) is:

    consumer constraints → shape what the producer creates

This module provides :class:`FlowObjectConstraintStore`, which holds
consumer constraint callables keyed by flow slot.  During schedule-graph
construction the store is populated with each consumer's constraints on its
flow-input fields.  Before the producer's ``randomize()`` call these
constraints are retrieved and injected so the producer's solve satisfies
both its own constraints AND the consumer's flow-object constraints.

Phase P1 establishes the architecture and scaffolding.  Full joint solving
(extending the solver to treat nested struct fields as rand variables) is
implemented in Phase P2.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple


# Key that uniquely identifies a producer/consumer/field triple.
# Using types (not instances) makes the key stable across multiple runs.
FlowSlotKey = Tuple[type, type, str]


class FlowObjectConstraintStore:
    """Registry of consumer constraints for flow-object fields.

    The store maps each ``(producer_type, consumer_type, field_name)`` key to
    a list of *constraint callables*.  A constraint callable is any zero-arg
    function that, when invoked with the flow object set on a temporary
    consumer instance, returns an expression that the solver can evaluate.

    Currently used as a scaffolding placeholder.  Constraint injection into
    the producer's solve is activated in Phase P2 once the solver gains
    support for nested struct rand variables.
    """

    def __init__(self) -> None:
        self._store: Dict[FlowSlotKey, List[Callable]] = {}

    # ------------------------------------------------------------------
    # Registration (called during ScheduleGraph.build())
    # ------------------------------------------------------------------

    def register_consumer(
        self,
        key: FlowSlotKey,
        constraints: List[Callable],
    ) -> None:
        """Register *constraints* that the consumer places on the flow object.

        Args:
            key: ``(producer_type, consumer_type, field_name)`` identifying the
                 flow slot.
            constraints: List of constraint callables extracted from the
                 consumer action type that reference the flow-input field.
        """
        existing = self._store.setdefault(key, [])
        existing.extend(constraints)

    # ------------------------------------------------------------------
    # Retrieval (called before producer's randomize())
    # ------------------------------------------------------------------

    def consumer_constraints_for(
        self,
        key: FlowSlotKey,
    ) -> List[Callable]:
        """Return the consumer constraints registered for *key*.

        Returns an empty list when no constraints have been registered (i.e.,
        the consumer places no additional requirements on the flow object).
        """
        return list(self._store.get(key, []))

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    def clear(self, key: Optional[FlowSlotKey] = None) -> None:
        """Clear constraints.  If *key* is given, clears only that slot."""
        if key is None:
            self._store.clear()
        else:
            self._store.pop(key, None)

    def __len__(self) -> int:
        return sum(len(v) for v in self._store.values())

    def __repr__(self) -> str:  # pragma: no cover
        return f"FlowObjectConstraintStore({dict(self._store)!r})"
