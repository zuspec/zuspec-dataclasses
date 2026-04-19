"""ActionInfra — per-component cache of solver infrastructure.

``ActionInfra`` bundles the four objects that are derived purely from the
static component-tree structure and are therefore safe to share across
multiple action traversals on the same component:

* ``PoolResolver``      — indexes resource/flow-object pools by type
* ``ActionRegistry``    — catalogs all action classes visible from the root
* ``ICLTable``          — Phase-E ICL (Input/Consumer/Link) inference table
* ``StructuralSolver``  — resolves unbound flow-object inputs via ICL BFS

Lifecycle
---------
Built once on the first ``await action(comp)`` call via
:func:`get_or_build_infra` and stored on ``comp._impl._action_infra``.
Every subsequent call on the same component retrieves the cached instance.

A fresh :class:`~zuspec.dataclasses.rt.action_context.ActionContext` (with
an independent seed and empty inline-constraint list) is created per call so
that per-traversal mutable state never leaks between calls.

Cache invalidation
------------------
The infra reflects the component tree at the moment of first use.  If the
tree changes (unusual in MLS designs), call::

    comp._impl._action_infra = None

before the next ``await action(comp)`` to force a rebuild.
"""
from __future__ import annotations

import dataclasses as dc
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .pool_resolver import PoolResolver
    from .action_registry import ActionRegistry
    from .icl_table import ICLTable
    from .structural_solver import StructuralSolver
    from ..types import Component


@dc.dataclass
class ActionInfra:
    """Cacheable solver infrastructure derived from a component tree.

    All four fields are stateless with respect to individual traversals;
    only the ``ActionContext`` carries per-call mutable state.

    Attributes:
        resolver:          Resolves resource/flow-object fields to pool instances.
        registry:          Catalogs action types reachable from the root component.
        icl_table:         Phase-E ICL table for structural flow-object inference.
        structural_solver: Resolves unbound flow inputs via ICL BFS search.
    """
    resolver: "PoolResolver"
    registry: "ActionRegistry"
    icl_table: "ICLTable"
    structural_solver: "StructuralSolver"


def get_or_build_infra(comp: "Component") -> ActionInfra:
    """Return the cached :class:`ActionInfra` for *comp*, building it on first use.

    The infra is stored on ``comp._impl._action_infra``.  If *comp* has no
    ``_impl`` attribute (e.g. a bare test double without RT), a fresh
    ``ActionInfra`` is built and returned without caching.

    Args:
        comp: The component instance to build or retrieve infra for.

    Returns:
        An :class:`ActionInfra` instance valid for the lifetime of *comp*.
    """
    from .pool_resolver import PoolResolver
    from .action_registry import ActionRegistry
    from .icl_table import ICLTable
    from .structural_solver import StructuralSolver

    impl = getattr(comp, '_impl', None)
    if impl is not None and impl._action_infra is not None:
        return impl._action_infra

    resolver  = PoolResolver.build(comp)
    registry  = ActionRegistry.build(comp)
    icl_table = ICLTable.build(registry)
    solver    = StructuralSolver(icl_table, seed=0, registry=registry)
    infra     = ActionInfra(
        resolver=resolver,
        registry=registry,
        icl_table=icl_table,
        structural_solver=solver,
    )

    if impl is not None:
        impl._action_infra = infra
    return infra
