"""``zdc.Completion[T]`` — one-shot result synchronization token.

At simulation time a ``Completion[T]()`` instance is backed by an asyncio
Future.  At synthesis time the IR extractor treats it as a typed
synchronization primitive that maps to a response register / signal.

Usage::

    done: zdc.Completion[zdc.u32] = zdc.Completion[zdc.u32]()
    done.set(42)           # non-blocking — sets the result
    result = await done    # suspends caller until set() is called
"""
from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")


class Completion(Generic[T]):
    """One-shot result synchronization token.

    The DSL class acts as both the type annotation and the factory.
    At runtime a ``CompletionRT`` instance is returned; at synthesis
    the IR extractor records the creation site and payload type.
    """

    def __class_getitem__(cls, item):
        """Support ``Completion[T]`` generic subscript notation."""
        return _CompletionAlias(cls, item)

    def __new__(cls, *args, **kwargs):
        from zuspec.dataclasses.rt.completion_rt import CompletionRT
        return CompletionRT.__new__(CompletionRT)

    def __init__(self):
        # Delegation happens in __new__; this is a no-op at DSL level.
        pass

    def set(self, value: T) -> None:
        """Set the result value.  Non-blocking; must be called exactly once."""
        raise NotImplementedError

    def __await__(self):
        """Suspend the caller until ``set()`` is called."""
        raise NotImplementedError

    @property
    def is_set(self) -> bool:
        """True after ``set()`` has been called."""
        raise NotImplementedError


class _CompletionAlias:
    """``Completion[T]`` subscript result — behaves like the class for instantiation."""

    def __init__(self, origin, item):
        self._origin = origin
        self._item = item

    def __call__(self, *args, **kwargs):
        from zuspec.dataclasses.rt.completion_rt import CompletionRT
        return CompletionRT()

    def __repr__(self):
        return f"Completion[{self._item!r}]"

    # Allow isinstance checks against the origin class
    def __instancecheck__(self, instance):
        from zuspec.dataclasses.rt.completion_rt import CompletionRT
        return isinstance(instance, (self._origin, CompletionRT))
