"""Helpers for runtime resource field introspection and acquisition."""
from __future__ import annotations

import dataclasses as dc
from typing import TYPE_CHECKING, Any, NamedTuple, Optional

if TYPE_CHECKING:
    from .action_context import ActionContext


class ResourceFieldInfo(NamedTuple):
    name: str        # field name on the action
    claim: str       # "lock" or "share"
    field_type: type # the Resource subclass


def make_resource(cls: type) -> Any:
    """Instantiate a ``@zdc.dataclass`` Resource without going through the PSS
    factory (which requires a configured object-model context).

    Uses ``object.__new__`` and populates all dataclass field defaults directly.
    This is the correct way to create resource instances for :class:`ClaimPool`
    in test and runtime code.
    """
    obj = object.__new__(cls)
    try:
        fields = dc.fields(cls)
    except TypeError:
        return obj
    for f in fields:
        if f.default is not dc.MISSING:
            object.__setattr__(obj, f.name, f.default)
        elif f.default_factory is not dc.MISSING:
            object.__setattr__(obj, f.name, f.default_factory())
        else:
            object.__setattr__(obj, f.name, None)
    if not hasattr(obj, 'instance_id'):
        object.__setattr__(obj, 'instance_id', 0)
    return obj


class ResourceFieldInfo(NamedTuple):
    name: str        # field name on the action
    claim: str       # "lock" or "share"
    field_type: type # the Resource subclass


import functools as _functools


@_functools.lru_cache(maxsize=None)
def get_resource_fields(action_type: type) -> list:
    """Return all lock/share fields declared on *action_type* (cached per class)."""
    try:
        fields = dc.fields(action_type)
    except TypeError:
        return []

    result = []
    # Collect raw annotations from MRO to resolve types without triggering
    # get_type_hints() (which fails on Action[T] generic base).
    ann_map: dict[str, Any] = {}
    for klass in reversed(action_type.__mro__):
        ann_map.update(klass.__dict__.get("__annotations__", {}))

    for f in fields:
        meta = f.metadata if f.metadata else {}
        if meta.get("kind") != "resource_ref":
            continue
        claim = meta.get("claim", "lock")
        field_type = ann_map.get(f.name, type(None))
        if not isinstance(field_type, type):
            field_type = type(None)
        result.append(ResourceFieldInfo(f.name, claim, field_type))
    return result


async def acquire_resources(
    action: Any,
    ctx: "ActionContext",
    extra_hints: Optional[dict] = None,
) -> list[tuple]:
    """Acquire all resource claims on *action* in canonical (deadlock-free) order.

    Returns a list of (pool, claim) pairs for later release via
    :func:`release_resources`.

    *extra_hints* supplements ``ctx.head_resource_hints`` with resource-id
    values solved by the constraint solver (stored in
    ``action._zdc_resource_hints`` and passed here by the activity runner).
    These override any hints already in *ctx* for the same field name.
    """
    resource_fields = get_resource_fields(type(action))
    if not resource_fields:
        return []

    # Per-field filter predicates optionally set by action.pre_solve() via
    # the _resource_filters dict: maps field_name -> callable(resource, index) -> bool.
    action_filters: dict = getattr(action, '_resource_filters', {})

    # Merge context hints with solver-solved hints; solver hints take priority.
    hints: dict = dict(ctx.head_resource_hints)
    if extra_hints:
        hints.update(extra_hints)

    entries = []
    for fi in resource_fields:
        pool = ctx.pool_resolver.resolve_pool(action, fi.name)
        if pool is None:
            continue
        # Use pre-assigned instance_id hint from BindingSolver or constraint solver
        instance_id = hints.get(fi.name)
        entries.append((pool, fi, instance_id))

    # Sort by (pool identity, instance_id) for deadlock-free ordering
    entries.sort(key=lambda e: (id(e[0]), e[2] if e[2] is not None else -1))

    claims: list[tuple] = []
    for pool, fi, instance_id in entries:
        filter_fn: Optional[Any] = None
        user_filter = action_filters.get(fi.name)
        if user_filter is not None:
            # Per-field filter from _resource_filters (e.g. set by post_solve from a
            # PSS constraint x in comp.valid_list).  This is authoritative: it
            # specifies exactly which resource satisfies the constraint, so it takes
            # precedence over the BindingSolver's instance_id hint (which was a random
            # AllDifferent pre-allocation that may not respect the filter domain).
            filter_fn = user_filter
        elif instance_id is not None:
            filter_fn = lambda _r, i, _iid=instance_id: i == _iid
        if fi.claim == "lock":
            claim = await pool.lock(filter=filter_fn)
            # Apply solver-determined write-back: if a constraint assigned a new
            # value to this lock() resource (e.g. assert self.pc.t == next_pc),
            # the solved value is stored in hints as "field.t".
            write_val = hints.get(f"{fi.name}.t")
            if write_val is not None:
                claim.t = write_val
        else:
            claim = await pool.share(filter=filter_fn)
        setattr(action, fi.name, claim)
        claims.append((pool, claim))

    return claims


def release_resources(claims: list[tuple]) -> None:
    """Release all resource claims in reverse acquisition order."""
    for pool, claim in reversed(claims):
        pool.drop(claim)
