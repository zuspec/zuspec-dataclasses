"""Per-traversal context passed through the ActivityRunner call tree.

Example::

    >>> import dataclasses as dc
    >>> # ActionContext is constructed with required fields; defaults handle the rest.
"""
from __future__ import annotations

import dataclasses as dc
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ..types import Component
    from .pool_resolver import PoolResolver
    from .tracer import Tracer
    from .structural_solver import StructuralSolver
    from .forward_constraint_propagator import ForwardConstraintPropagator


@dc.dataclass(kw_only=True)
class ActionContext:
    """Carries all per-traversal state through the ActivityRunner call tree."""

    action: Any
    """The action instance currently being executed (None at root)."""

    comp: "Component"
    """The component instance bound to this action."""

    pool_resolver: "PoolResolver"
    """Resolves resource/flow-object fields to pool instances."""

    parent: Optional["ActionContext"] = None
    """The enclosing traversal context (for super() support)."""

    seed: int = 0
    """RNG seed for this traversal (derived from parent seed XOR action id)."""

    inline_constraints: list = dc.field(default_factory=list)
    """Extra IR constraint expressions from a with-block, applied during solve."""

    flow_bindings: dict = dc.field(default_factory=dict)
    """field_name → FlowObjInstance; injected by schedule-block elaboration."""

    head_resource_hints: dict = dc.field(default_factory=dict)
    """field_name → instance_id pre-assigned by BindingSolver for parallel heads."""

    structural_solver: Optional["StructuralSolver"] = None
    """Resolves unbound flow-object inputs via ICL table search (Phase S)."""

    forward_propagator: Optional["ForwardConstraintPropagator"] = None
    """Propagates concrete field values from predecessor sequential actions (P3)."""

    tracer: Optional["Tracer"] = None
    """Optional tracer receiving action lifecycle events."""

    check_contracts: bool = False
    """When True, evaluate @constraint.requires before body() and @constraint.ensures after."""
