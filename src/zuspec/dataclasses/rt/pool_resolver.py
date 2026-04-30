"""Component and pool resolution for the PSS activity runner.

Example::

    >>> # PoolResolver.build(root) indexes all component instances by type.
"""
from __future__ import annotations

import dataclasses as dc
import functools as _functools

@_functools.lru_cache(maxsize=None)
def _dc_fields(cls):
    """Cached dataclasses.fields() per class."""
    return dc.fields(cls)

import random
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ..types import Component


# ---------------------------------------------------------------------------
# Structural template: records the path-spec for PoolResolver.build() results
# so that subsequent builds for the same root type can avoid recursive walks.
# ---------------------------------------------------------------------------

class _PRTemplate:
    """Replay spec for fast PoolResolver construction from a same-typed root."""
    __slots__ = ('comp_paths', 'pool_paths', 'wildcard_bind_paths')

    def __init__(self):
        # comp_paths: [(accessor_sequence, comp_type)]
        # accessor_sequence: list of (attr_name, index_or_None)
        self.comp_paths = []        # (accessor_seq, comp_type)
        # pool_paths: [(accessor_seq_to_comp, pool_field_name)]
        self.pool_paths = []
        # wildcard_bind_paths: [(accessor_seq_to_comp, resource_type)]
        self.wildcard_bind_paths = []


_pr_template_cache: dict = {}  # type(root) -> _PRTemplate | None


def _follow_path(root, path: tuple):
    """Navigate from root following (attr, index_or_None) steps."""
    obj = root
    for attr, idx in path:
        obj = getattr(obj, attr, None)
        if obj is None:
            return None
        if idx is not None:
            try:
                obj = obj[idx]
            except (IndexError, TypeError):
                return None
    return obj


_RESOLVE_SENTINEL = object()  # used in resolve_pool memoisation


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
    # id(comp) → parent comp (for ancestor pool walk — WI-6d)
    _comp_parent: dict = dc.field(default_factory=dict, init=False)
    # (id(comp), action_type, field_name) → pool  (explicit binds)
    _explicit_binds: dict = dc.field(default_factory=dict, init=False)
    # (id(comp), resource_type) → pool  (wildcard binds)
    _wildcard_binds: dict = dc.field(default_factory=dict, init=False)

    @classmethod
    def build(cls, root: "Component") -> "PoolResolver":
        """Walk the component tree and index all component instances by type.

        On first call for a given root type, performs a full recursive walk and
        records a structural template.  Subsequent calls for the same type replay
        the template with O(depth) attribute accesses instead of a recursive scan.
        """
        root_type = type(root)
        template = _pr_template_cache.get(root_type)

        pr = cls()
        pr._resolve_cache = {}
        pr._type_pool_cache = {}

        if template is None:
            # Full build + record template
            tmpl = _PRTemplate()
            pr._walk(root)
            pr._index_pools(root)
            pr._index_binds(root)
            # Record structure for next calls
            for (comp_id, field_name), pool in pr._pool_index.items():
                # Find the path to this comp
                pass  # will reconstruct from _walk_with_paths below
            # Re-build using instrumented walk to capture paths
            pr2 = cls()
            pr2._resolve_cache = {}
            pr2._type_pool_cache = {}
            pr2._walk_instrumented(root, (), tmpl)
            pr2._index_pools_instrumented(root, (), tmpl)
            pr2._index_binds_instrumented(root, (), tmpl)
            _pr_template_cache[root_type] = tmpl
            # Use the instrumented build result
            pr._comp_instances = pr2._comp_instances
            pr._comp_parent = pr2._comp_parent
            pr._pool_index = pr2._pool_index
            pr._explicit_binds = pr2._explicit_binds
            pr._wildcard_binds = pr2._wildcard_binds
        else:
            # Fast replay: just follow recorded paths
            for path, comp_type in template.comp_paths:
                comp = _follow_path(root, path)
                if comp is None:
                    continue
                pr._comp_instances.setdefault(comp_type, []).append(comp)
                parent_path = path[:-1]
                parent = _follow_path(root, parent_path) if parent_path else None
                pr._comp_parent[id(comp)] = parent
            for comp_path, pool_field in template.pool_paths:
                comp = _follow_path(root, comp_path)
                if comp is None:
                    continue
                pool = getattr(comp, pool_field, None)
                if pool is not None:
                    pr._pool_index[(id(comp), pool_field)] = pool
            for comp_path, resource_type in template.wildcard_bind_paths:
                comp = _follow_path(root, comp_path)
                if comp is None:
                    continue
                pool_names, _ = _comp_child_field_names(type(comp))
                for pname in pool_names:
                    pool = getattr(comp, pname, None)
                    if pool is None:
                        continue
                    resources = getattr(pool, "resources", None) or getattr(pool, "items", None)
                    if resources:
                        rt = type(resources[0])
                        if rt is resource_type or (isinstance(rt, type) and issubclass(rt, resource_type)):
                            pr._wildcard_binds[(id(comp), resource_type)] = pool
                            break


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
        # Memoisation: within one PoolResolver instance, results are stable.
        _memo_key = (comp_id, action_type, field_name)
        _cached = self._resolve_cache.get(_memo_key, _RESOLVE_SENTINEL)
        if _cached is not _RESOLVE_SENTINEL:
            return _cached

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

        # 3. Type-based scan: recurse into action.comp's subtree first (existing
        # behaviour), then walk UP the ancestor chain to find pools declared on
        # parent or grandparent components (WI-6d — supports padring pattern).
        result = None
        if isinstance(field_type, type):
            # Check the type-level pool cache (comp_id, resource_type) — shared
            # across all field names that reference the same resource type.
            _type_key = (comp_id, field_type)
            if _type_key in self._type_pool_cache:
                result = self._type_pool_cache[_type_key]
            else:
                pool = self._scan_pool(comp, field_type)
                if pool is not None:
                    result = pool
                else:
                    # Ancestor walk: look for a pool on parent/grandparent components
                    ancestor = self._comp_parent.get(id(comp))
                    while ancestor is not None:
                        wkey = (id(ancestor), field_type)
                        if wkey in self._wildcard_binds:
                            result = self._wildcard_binds[wkey]
                            break
                        pool = self._scan_pool_direct(ancestor, field_type)
                        if pool is not None:
                            result = pool
                            break
                        ancestor = self._comp_parent.get(id(ancestor))
                self._type_pool_cache[_type_key] = result

        self._resolve_cache[_memo_key] = result
        return result

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
            # Use shared type-pool cache to avoid repeated ancestor scan.
            if wkey in self._type_pool_cache:
                return self._type_pool_cache[wkey]
            result = self._scan_pool(comp, field_type)
            if result is None:
                ancestor = self._comp_parent.get(comp_id)
                while ancestor is not None:
                    awk = (id(ancestor), field_type)
                    if awk in self._wildcard_binds:
                        result = self._wildcard_binds[awk]
                        break
                    result = self._scan_pool_direct(ancestor, field_type)
                    if result is not None:
                        break
                    ancestor = self._comp_parent.get(id(ancestor))
            self._type_pool_cache[wkey] = result
            return result
        return None

    def _scan_pool_direct(self, comp: "Component", resource_type: type) -> Optional[Any]:
        """Scan *comp*'s own pool fields only (no descent into children)."""
        try:
            fields = _dc_fields(type(comp))
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
        return None

    def _scan_pool(self, comp: "Component", resource_type: type) -> Optional[Any]:
        """Return first pool whose elements match *resource_type*, searching comp tree."""
        try:
            fields = _dc_fields(type(comp))
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
        """Collect all pool instances in the component tree (uses cached field lists)."""
        pool_names, candidate_names = _comp_child_field_names(type(comp))
        comp_id = id(comp)
        for name in pool_names:
            val = getattr(comp, name, None)
            if val is not None:
                self._pool_index[(comp_id, name)] = val
        for name in candidate_names:
            val = getattr(comp, name, None)
            if val is None:
                continue
            if _is_component(val):
                self._index_pools(val)
            elif isinstance(val, list):
                for item in val:
                    if item is not None and _is_component(item):
                        self._index_pools(item)

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

        _, candidate_names = _comp_child_field_names(type(comp))
        for name in candidate_names:
            val = getattr(comp, name, None)
            if val is not None and _is_component(val):
                self._index_binds(val)
            elif isinstance(val, list):
                for item in val:
                    if item is not None and _is_component(item):
                        self._index_binds(item)

    # ------------------------------------------------------------------
    # Instrumented build helpers (called once to populate the template)
    # ------------------------------------------------------------------

    def _walk_instrumented(self, comp, path: tuple, tmpl: "_PRTemplate") -> None:
        t = type(comp)
        self._comp_instances.setdefault(t, []).append(comp)
        parent_path = path[:-1]
        parent = _follow_path(self._comp_instances.get(t, [comp])[0], parent_path) if parent_path else None
        # Record parent via the already-registered comp
        self._comp_parent[id(comp)] = None  # set below
        if path:  # root has no parent
            parent_path = path[:-1]
            # Resolve parent from our registry via parent comp_id
            # We'll update _comp_parent normally during the walk
            pass
        tmpl.comp_paths.append((path, t))
        _, candidate_names = _comp_child_field_names(t)
        for name in candidate_names:
            val = getattr(comp, name, None)
            if val is None:
                continue
            if _is_component(val):
                child_path = path + ((name, None),)
                self._walk_instrumented(val, child_path, tmpl)
            elif isinstance(val, list):
                for idx, item in enumerate(val):
                    if item is not None and _is_component(item):
                        child_path = path + ((name, idx),)
                        self._walk_instrumented(item, child_path, tmpl)
        # Fix up _comp_parent
        if path:
            parent_obj = _follow_path(comp, ())  # = comp; parent is via path[:-1]
            # Use the instrumented path to derive parent
        self._comp_parent[id(comp)] = (
            _follow_path(self._find_root(), path[:-1]) if path else None
        )

    def _find_root(self):
        """Return the root comp (first registered comp instance)."""
        for instances in self._comp_instances.values():
            if instances:
                return instances[0]
        return None

    def _index_pools_instrumented(self, comp, path: tuple, tmpl: "_PRTemplate") -> None:
        pool_names, candidate_names = _comp_child_field_names(type(comp))
        for name in pool_names:
            val = getattr(comp, name, None)
            if val is not None:
                self._pool_index[(id(comp), name)] = val
                tmpl.pool_paths.append((path, name))
        for name in candidate_names:
            val = getattr(comp, name, None)
            if val is None:
                continue
            if _is_component(val):
                self._index_pools_instrumented(val, path + ((name, None),), tmpl)
            elif isinstance(val, list):
                for idx, item in enumerate(val):
                    if item is not None and _is_component(item):
                        self._index_pools_instrumented(item, path + ((name, idx),), tmpl)

    def _index_binds_instrumented(self, comp, path: tuple, tmpl: "_PRTemplate") -> None:
        bind_fn = comp.__class__.__dict__.get("__bind__")
        if bind_fn is not None:
            try:
                bind_map = bind_fn(comp)
            except Exception:
                bind_map = None
            if isinstance(bind_map, dict):
                for lhs, rhs in bind_map.items():
                    self._register_bind(comp, lhs, rhs)
                    if rhs == "*":
                        resources = getattr(lhs, "resources", None) or getattr(lhs, "items", None)
                        if resources:
                            tmpl.wildcard_bind_paths.append((path, type(resources[0])))
        _, candidate_names = _comp_child_field_names(type(comp))
        for name in candidate_names:
            val = getattr(comp, name, None)
            if val is None:
                continue
            if _is_component(val):
                self._index_binds_instrumented(val, path + ((name, None),), tmpl)
            elif isinstance(val, list):
                for idx, item in enumerate(val):
                    if item is not None and _is_component(item):
                        self._index_binds_instrumented(item, path + ((name, idx),), tmpl)

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

    def _walk(self, comp: "Component", parent: Optional["Component"] = None) -> None:
        t = type(comp)
        self._comp_instances.setdefault(t, []).append(comp)
        self._comp_parent[id(comp)] = parent  # WI-6d: record parent for ancestor walk
        _, candidate_names = _comp_child_field_names(t)
        for name in candidate_names:
            val = getattr(comp, name, None)
            if val is None:
                continue
            if _is_component(val):
                self._walk(val, parent=comp)
            elif isinstance(val, list):
                for item in val:
                    if item is not None and _is_component(item):
                        self._walk(item, parent=comp)

    def _instances_in(self, root: "Component", comp_type: type) -> list:
        """Return all instances of *comp_type* in *root*'s subtree (depth-first)."""
        result = []
        if isinstance(root, comp_type):
            result.append(root)
        try:
            for f in _dc_fields(type(root)):
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


import functools as _functools

@_functools.lru_cache(maxsize=None)
def _is_component_type(t: type) -> bool:
    """Cached per-type component check; avoids ABC overhead on every call."""
    from ..types import Component
    return issubclass(t, Component)


@_functools.lru_cache(maxsize=None)
def _comp_child_field_names(cls):
    """Return (pool_field_names, list_field_names) for walking comp children.

    The 'list_field_names' are fields to scan for child component instances
    (could be single Component, a list of components, or unrelated).
    Caching avoids repeated metadata inspection per PoolResolver.build() call.
    """
    pool_names = []
    candidate_names = []  # fields that might hold comp children
    try:
        for f in dc.fields(cls):
            if f.name.startswith('_'):
                continue
            meta = f.metadata or {}
            kind = meta.get('kind')
            if kind == 'pool':
                pool_names.append(f.name)
            elif kind not in ('memory', 'address_space', 'regfile', 'channel',
                              'bundle', 'mirror', 'monitor', 'resource_ref',
                              'flow_ref', 'port'):
                candidate_names.append(f.name)
    except TypeError:
        pass
    return tuple(pool_names), tuple(candidate_names)


@_functools.lru_cache(maxsize=None)
def _pool_and_comp_fields(cls):
    """Return (pool_field_names, comp_field_names, list_field_names) for a class.

    Cached per class so PoolResolver._walk/_index_pools avoid repeated
    dc.fields() + metadata inspection on every instance construction.
    """
    pools = []
    comps = []
    lists = []
    try:
        for f in dc.fields(cls):
            if f.name.startswith('_'):
                continue
            meta = f.metadata or {}
            kind = meta.get('kind')
            if kind == 'pool':
                pools.append(f.name)
            else:
                # We can not determine if it holds a component without an instance;
                # return the name and let the caller check at runtime.
                lists.append(f.name)
    except TypeError:
        pass
    return tuple(pools), tuple(lists)


def _is_component(obj: Any) -> bool:
    return _is_component_type(type(obj))
