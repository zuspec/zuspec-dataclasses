"""Component and pool resolution for the PSS activity runner.

Example::

    >>> # PoolResolver.build(root) indexes all component instances by type.
"""
from __future__ import annotations

import dataclasses as dc
import random
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ..types import Component


@dc.dataclass
class PoolResolver:
    """
    Built once per component-tree root.  Answers two runtime questions:

    1. Which component instances are candidates for a given action type?
    2. Which pool backs a given resource/flow-object field on an action?
    """

    _comp_instances: dict = dc.field(default_factory=dict, init=False)
    # (id(comp), field_name) → pool instance
    _pool_index: dict = dc.field(default_factory=dict, init=False)
    # (id(comp), action_type, field_name) → pool  (explicit binds)
    _explicit_binds: dict = dc.field(default_factory=dict, init=False)
    # (id(comp), resource_type) → pool  (wildcard binds)
    _wildcard_binds: dict = dc.field(default_factory=dict, init=False)

    @classmethod
    def build(cls, root: "Component") -> "PoolResolver":
        """Walk the component tree and index all component instances by type."""
        pr = cls()
        pr._walk(root)
        pr._index_pools(root)
        pr._index_binds(root)
        return pr

    # ------------------------------------------------------------------
    # Component instance selection
    # ------------------------------------------------------------------

    def select_comp(self, action_type: type, context_comp: "Component") -> "Component":
        """Randomly select a component instance of the type required by *action_type*.

        Looks up the ``Action[T]`` type parameter to find *T*, then returns a
        random instance of *T* found within *context_comp*'s subtree.
        """
        comp_type = _action_comp_type(action_type)
        if comp_type is None:
            raise RuntimeError(
                f"Cannot determine component type for {action_type.__name__}"
            )

        candidates = self._instances_in(context_comp, comp_type)
        if not candidates:
            raise RuntimeError(
                f"No instances of {comp_type.__name__} found within "
                f"{type(context_comp).__name__}"
            )
        return random.choice(candidates)

    # ------------------------------------------------------------------
    # Pool resolution
    # ------------------------------------------------------------------

    def resolve_pool(self, action: Any, field_name: str) -> Optional[Any]:
        """Return the pool bound to ``action.<field_name>``.

        Resolution order:
        1. Explicit bind: ``(comp_id, action_type, field_name)``
        2. Wildcard bind: ``(comp_id, field_type)``
        3. Type-based scan: first pool on ``action.comp`` whose element type
           matches the field's annotated type.
        """
        comp = getattr(action, "comp", None)
        if comp is None:
            return None

        comp_id = id(comp)
        action_type = type(action)

        # 1. Explicit bind
        key = (comp_id, action_type, field_name)
        if key in self._explicit_binds:
            return self._explicit_binds[key]

        # 2. Wildcard bind — match by field type
        ann_map: dict[str, Any] = {}
        for klass in reversed(action_type.__mro__):
            ann_map.update(klass.__dict__.get("__annotations__", {}))
        field_type = ann_map.get(field_name)
        if isinstance(field_type, type):
            wkey = (comp_id, field_type)
            if wkey in self._wildcard_binds:
                return self._wildcard_binds[wkey]

        # 3. Type-based scan: find any pool on comp whose element type matches
        if isinstance(field_type, type):
            return self._scan_pool(comp, field_type)

        return None

    def resolve_pool_by_type(
        self, action_type: type, field_name: str, comp: "Component"
    ) -> Optional[Any]:
        """Resolve pool without a concrete action instance (used by BindingSolver)."""
        comp_id = id(comp)

        key = (comp_id, action_type, field_name)
        if key in self._explicit_binds:
            return self._explicit_binds[key]

        ann_map: dict[str, Any] = {}
        for klass in reversed(action_type.__mro__):
            ann_map.update(klass.__dict__.get("__annotations__", {}))
        field_type = ann_map.get(field_name)

        if isinstance(field_type, type):
            wkey = (comp_id, field_type)
            if wkey in self._wildcard_binds:
                return self._wildcard_binds[wkey]
            return self._scan_pool(comp, field_type)
        return None

    def _scan_pool(self, comp: "Component", resource_type: type) -> Optional[Any]:
        """Return first pool whose elements match *resource_type*, searching comp tree."""
        try:
            fields = dc.fields(comp)
        except TypeError:
            return None
        for f in fields:
            if f.name.startswith('_'):
                continue
            meta = f.metadata if f.metadata else {}
            val = getattr(comp, f.name, None)
            if meta.get("kind") == "pool" and val is not None:
                resources = getattr(val, "resources", None) or getattr(val, "items", None)
                if resources and isinstance(resources[0], resource_type):
                    return val
            elif val is not None and _is_component(val):
                found = self._scan_pool(val, resource_type)
                if found is not None:
                    return found
        return None

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def _index_pools(self, comp: "Component") -> None:
        """Collect all pool instances in the component tree."""
        try:
            fields = dc.fields(comp)
        except TypeError:
            return
        for f in fields:
            if f.name.startswith('_'):
                continue
            meta = f.metadata if f.metadata else {}
            val = getattr(comp, f.name, None)
            if meta.get("kind") == "pool" and val is not None:
                self._pool_index[(id(comp), f.name)] = val
            elif val is not None and _is_component(val):
                self._index_pools(val)

    def _index_binds(self, comp: "Component") -> None:
        """Process ``__bind__`` methods to build explicit and wildcard bind maps."""
        bind_fn = comp.__class__.__dict__.get("__bind__")
        if bind_fn is not None:
            try:
                bind_map = bind_fn(comp)
            except Exception:
                bind_map = None
            if isinstance(bind_map, dict):
                for lhs, rhs in bind_map.items():
                    # lhs: pool instance, rhs: action field desc or '*'
                    self._register_bind(comp, lhs, rhs)

        try:
            fields = dc.fields(comp)
        except TypeError:
            return
        for f in fields:
            if f.name.startswith('_'):
                continue
            val = getattr(comp, f.name, None)
            if val is not None and _is_component(val):
                self._index_binds(val)

    def _register_bind(self, comp: "Component", pool: Any, descriptor: Any) -> None:
        """Register one bind entry from a __bind__ result dict."""
        comp_id = id(comp)
        if descriptor == "*":
            # Wildcard: bind pool to any action field of matching type
            resources = getattr(pool, "resources", None) or getattr(pool, "items", None)
            if resources:
                resource_type = type(resources[0])
                self._wildcard_binds[(comp_id, resource_type)] = pool
        elif isinstance(descriptor, tuple) and len(descriptor) == 2:
            action_type, field_name = descriptor
            self._explicit_binds[(comp_id, action_type, field_name)] = pool

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _walk(self, comp: "Component") -> None:
        t = type(comp)
        self._comp_instances.setdefault(t, []).append(comp)
        try:
            fields = dc.fields(comp)
        except TypeError:
            return
        for f in fields:
            if f.name.startswith('_'):
                continue
            val = getattr(comp, f.name, None)
            if val is not None and _is_component(val):
                self._walk(val)

    def _instances_in(self, root: "Component", comp_type: type) -> list:
        """Return all instances of *comp_type* in *root*'s subtree (depth-first)."""
        result = []
        if isinstance(root, comp_type):
            result.append(root)
        try:
            for f in dc.fields(root):
                if f.name.startswith('_'):
                    continue
                val = getattr(root, f.name, None)
                if val is not None and _is_component(val):
                    result.extend(self._instances_in(val, comp_type))
        except TypeError:
            pass
        return result


def _action_comp_type(action_type: type) -> Optional[type]:
    """Extract the ``T`` from ``Action[T]`` for a concrete action subclass."""
    import typing
    from ..types import Action
    for cls in action_type.__mro__:
        for base in getattr(cls, "__orig_bases__", ()):
            origin = typing.get_origin(base)
            if origin is not None:
                try:
                    if issubclass(origin, Action):
                        args = typing.get_args(base)
                        if args:
                            return args[0]
                except TypeError:
                    pass
    return None


def _is_component(obj: Any) -> bool:
    from ..types import Component
    return isinstance(obj, Component)
