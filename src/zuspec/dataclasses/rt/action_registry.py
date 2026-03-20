"""Action registry: discovers all action types reachable from a component tree.

The registry is the input to :class:`~zuspec.dataclasses.rt.icl_table.ICLTable`;
it maps each flow-object type to the action types that produce or consume it.
"""
from __future__ import annotations

import dataclasses as dc
from typing import Any, Dict, List, Optional, Set, Tuple


@dc.dataclass
class ActionFlowInfo:
    """Flow-object field information for one action type."""
    action_type: type
    field_name: str
    flow_obj_type: type
    direction: str   # "output" or "input"


class ActionRegistry:
    """Enumerates all action types accessible from a component instance tree.

    Built once per scenario via :meth:`build`.  Used by
    :class:`~zuspec.dataclasses.rt.icl_table.ICLTable` to construct the
    Inferencing Candidate List.
    """

    def __init__(self) -> None:
        # All discovered action types
        self._action_types: Set[type] = set()
        # flow_obj_type → list[ActionFlowInfo] for output (producer) side
        self._producers: Dict[type, List[ActionFlowInfo]] = {}
        # flow_obj_type → list[ActionFlowInfo] for input (consumer) side
        self._consumers: Dict[type, List[ActionFlowInfo]] = {}

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def build(cls, root: Any) -> "ActionRegistry":
        """Walk *root*'s component tree and collect all action types.

        Action types are discovered via ``__subclasses__()`` of the
        ``Action`` base class, filtered to those whose component type
        parameter is present anywhere in the tree rooted at *root*.
        """
        registry = cls()
        comp_types = _collect_component_types(root)
        from ..types import Action, Buffer, Stream, State
        registry._discover_action_types(Action, comp_types)
        return registry

    def _discover_action_types(self, action_base: type, comp_types: Set[type]) -> None:
        """Recursively walk Action subclasses; register those bound to *comp_types*."""
        from .pool_resolver import _action_comp_type
        for sub in _all_subclasses(action_base):
            comp_type = _action_comp_type(sub)
            if comp_type is None:
                continue
            # The component tree may contain synthetic runtime subclasses of the
            # user's component type, so check issubclass in both directions.
            if not any(
                _types_compatible(ct, comp_type)
                for ct in comp_types
            ):
                continue
            self._register_action_type(sub)

    def _register_action_type(self, action_type: type) -> None:
        if action_type in self._action_types:
            return
        self._action_types.add(action_type)
        # Inspect flow-ref fields
        try:
            fields = dc.fields(action_type)
        except TypeError:
            return
        ann: Dict[str, Any] = {}
        for klass in action_type.__mro__:
            ann.update(klass.__dict__.get("__annotations__", {}))
        for f in fields:
            meta = f.metadata or {}
            if meta.get("kind") != "flow_ref":
                continue
            direction = meta.get("direction")
            flow_obj_type = ann.get(f.name)
            if not isinstance(flow_obj_type, type):
                continue
            info = ActionFlowInfo(
                action_type=action_type,
                field_name=f.name,
                flow_obj_type=flow_obj_type,
                direction=direction,
            )
            if direction == "output":
                self._producers.setdefault(flow_obj_type, []).append(info)
            elif direction == "input":
                self._consumers.setdefault(flow_obj_type, []).append(info)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def all_action_types(self) -> Set[type]:
        return set(self._action_types)

    def producers_for(self, flow_obj_type: type) -> List[ActionFlowInfo]:
        """Return all action/field pairs that *output* the given flow type."""
        result = list(self._producers.get(flow_obj_type, []))
        # Also include subtypes
        for fot, infos in self._producers.items():
            try:
                if fot is not flow_obj_type and issubclass(fot, flow_obj_type):
                    result.extend(infos)
            except TypeError:
                pass
        return result

    def consumers_for(self, flow_obj_type: type) -> List[ActionFlowInfo]:
        """Return all action/field pairs that *input* the given flow type."""
        result = list(self._consumers.get(flow_obj_type, []))
        for fot, infos in self._consumers.items():
            try:
                if fot is not flow_obj_type and issubclass(fot, flow_obj_type):
                    result.extend(infos)
            except TypeError:
                pass
        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_component_types(root: Any) -> Set[type]:
    """Return the set of all component *types* present in *root*'s subtree."""
    from ..types import Component
    seen: Set[type] = set()
    _walk_comp_types(root, seen)
    return seen


def _types_compatible(runtime_type: type, declared_type: type) -> bool:
    """True when a runtime component instance (which may be a synthetic subclass)
    is compatible with the declared component type on an Action[T] definition."""
    try:
        return issubclass(runtime_type, declared_type) or issubclass(declared_type, runtime_type)
    except TypeError:
        return False


def _walk_comp_types(comp: Any, seen: Set[type]) -> None:
    from ..types import Component
    if not isinstance(comp, Component):
        return
    seen.add(type(comp))
    try:
        for f in dc.fields(comp):
            if f.name.startswith("_"):
                continue
            val = getattr(comp, f.name, None)
            if isinstance(val, Component):
                _walk_comp_types(val, seen)
    except TypeError:
        pass


def _all_subclasses(cls: type) -> List[type]:
    """Recursively collect all (transitive) subclasses of *cls*."""
    result: List[type] = []
    for sub in cls.__subclasses__():
        result.append(sub)
        result.extend(_all_subclasses(sub))
    return result
