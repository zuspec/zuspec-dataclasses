"""ICL (Inferencing Candidate List) table construction.

The ICLTable is the Phase-E output of PSS inference (LRM Annex E).  For each
(consumer_type, input_field_name) pair it lists the action types capable of
satisfying that input slot.
"""
from __future__ import annotations

import dataclasses as dc
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .action_registry import ActionRegistry


@dc.dataclass
class ICLEntry:
    """One candidate producer that can satisfy an unbound consumer flow slot."""
    action_type: type
    """The action type that produces the required flow object."""
    output_field: str
    """Name of the flow-output field on *action_type*."""
    flow_obj_type: type
    """The concrete flow-object type produced."""


class ICLTable:
    """Pre-computed Inferencing Candidate List.

    Maps ``(consumer_action_type, input_field_name)`` → ``list[ICLEntry]``.

    Built once per scenario via :meth:`build` from an
    :class:`~zuspec.dataclasses.rt.action_registry.ActionRegistry`.
    """

    def __init__(self) -> None:
        self._table: Dict[Tuple[type, str], List[ICLEntry]] = {}

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def build(cls, registry: "ActionRegistry") -> "ICLTable":
        """Construct the full ICL table from *registry*.

        For every consumer action type with flow-input fields, find all
        producer action types (via *registry*) whose output type is
        compatible with the consumer's input type.
        """
        table = cls()
        for consumer_info in _all_consumer_infos(registry):
            key = (consumer_info.action_type, consumer_info.field_name)
            producers = registry.producers_for(consumer_info.flow_obj_type)
            entries = [
                ICLEntry(
                    action_type=prod.action_type,
                    output_field=prod.field_name,
                    flow_obj_type=prod.flow_obj_type,
                )
                for prod in producers
                # Don't allow a type to be its own producer (trivial cycle)
                if prod.action_type is not consumer_info.action_type
            ]
            if entries:
                table._table[key] = entries
        return table

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def candidates(self, consumer_type: type, field_name: str) -> List[ICLEntry]:
        """Return ICL candidates for the given consumer slot.

        Returns an empty list when no candidate exists (inference infeasible
        for this slot).
        """
        return list(self._table.get((consumer_type, field_name), []))

    def has_candidates(self, consumer_type: type, field_name: str) -> bool:
        key = (consumer_type, field_name)
        return bool(self._table.get(key))

    def all_keys(self):
        return list(self._table.keys())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_consumer_infos(registry: "ActionRegistry"):
    """Yield ActionFlowInfo for every consumer field in the registry."""
    from .action_registry import ActionFlowInfo
    seen = set()
    for action_type in registry.all_action_types():
        try:
            fields = dc.fields(action_type)
        except TypeError:
            continue
        ann = {}
        for klass in action_type.__mro__:
            ann.update(klass.__dict__.get("__annotations__", {}))
        for f in fields:
            meta = f.metadata or {}
            if meta.get("kind") == "flow_ref" and meta.get("direction") == "input":
                flow_obj_type = ann.get(f.name)
                if not isinstance(flow_obj_type, type):
                    continue
                key = (action_type, f.name)
                if key in seen:
                    continue
                seen.add(key)
                yield ActionFlowInfo(
                    action_type=action_type,
                    field_name=f.name,
                    flow_obj_type=flow_obj_type,
                    direction="input",
                )
