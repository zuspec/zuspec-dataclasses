"""Utilities for parsing action-level ``__bind__`` declarations.

An action's ``__bind__`` method returns a tuple-of-tuples::

    def __bind__(self):
        return (
            (self.rs1, self.comp.gpr),
            (self.rs2, self.comp.gpr),
        )

Because ``self.rs1`` is ``None`` at constraint-build time (not yet acquired),
we call ``__bind__`` with an :class:`ActionBindProxy` as ``self``.  Accessing
a ``resource_ref`` field on the proxy returns a :class:`_FieldRef` sentinel
that records the field name; other field accesses (e.g. ``self.comp``) fall
through to the real action value so that ``self.comp.gpr`` resolves to the
actual pool.

:func:`parse_action_bind` returns a ``{field_name: pool}`` dict.
"""
from __future__ import annotations

import dataclasses as _dc
from typing import Any, Dict, Optional


class _FieldRef:
    """Sentinel returned by :class:`ActionBindProxy` for resource_ref fields."""

    __slots__ = ("_name",)

    def __init__(self, name: str) -> None:
        self._name = name

    def __repr__(self) -> str:
        return f"_FieldRef({self._name!r})"


class ActionBindProxy:
    """Proxy for action ``__bind__`` that intercepts resource_ref field reads.

    When ``__bind__`` is evaluated with this proxy as ``self``:

    * Accessing a ``resource_ref`` field (``zdc.lock()`` / ``zdc.share()``)
      returns a :class:`_FieldRef` sentinel carrying the field name.
    * Accessing any other field (e.g. ``comp``) returns the real value from
      the underlying action so that ``self.comp.gpr`` still resolves.
    """

    def __init__(self, action: Any) -> None:
        object.__setattr__(self, "_action", action)
        # Pre-build set of resource_ref field names for fast lookup.
        try:
            names = frozenset(
                f.name
                for f in _dc.fields(type(action))
                if f.metadata.get("kind") == "resource_ref"
            )
        except TypeError:
            names = frozenset()
        object.__setattr__(self, "_resource_names", names)

    def __getattr__(self, name: str) -> Any:
        resource_names: frozenset = object.__getattribute__(self, "_resource_names")
        if name in resource_names:
            return _FieldRef(name)
        action = object.__getattribute__(self, "_action")
        return getattr(action, name)


def parse_action_bind(action: Any) -> Dict[str, Any]:
    """Call *action*'s ``__bind__`` via a proxy and return ``{field_name: pool}``.

    Returns an empty dict if the action has no ``__bind__``, if the call raises,
    or if the return value cannot be parsed.
    """
    bind_fn = type(action).__dict__.get("__bind__")
    if bind_fn is None:
        return {}

    proxy = ActionBindProxy(action)
    try:
        result = bind_fn(proxy)
    except Exception:
        return {}

    if result is None:
        return {}

    # Already a dict — pass through (legacy dict format).
    if isinstance(result, dict):
        return result

    # Tuple-of-tuples: ((FieldRef("rs1"), pool), ...)
    mapping: Dict[str, Any] = {}
    try:
        for item in result:
            if isinstance(item, (tuple, list)) and len(item) == 2:
                ref, pool = item
                if isinstance(ref, _FieldRef):
                    mapping[ref._name] = pool
    except TypeError:
        pass

    return mapping
