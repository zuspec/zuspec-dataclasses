"""Import resolver — routes a model's package-scope ``import`` calls outward.

A PSS ``import target`` / ``import solve`` function is a call *out* of the model
to the surrounding environment (the Python analogue of the SystemVerilog
``import_api_if``).  :class:`ImportResolver` binds each import name to a method on
a user-supplied implementation object and is made active for the duration of a
scenario run via :func:`use_resolver`, so the interpreter can dispatch a model's
``self.<import>()`` call to it instead of silently evaluating it to ``0``.
"""
from __future__ import annotations

import contextlib
import contextvars
import dataclasses as dc
import inspect
from typing import Any, Dict, Optional


class PssImportError(RuntimeError):
    """A model called an import that the supplied object does not provide, or
    that cannot be executed on the current path."""


@dc.dataclass(frozen=True)
class ImportSpec:
    """Describes one package-scope import the model may call."""

    name: str
    is_target: bool = False   # ``import target`` — may consume time (SV task)
    is_solve: bool = False    # ``import solve``  — pure/value (SV function)


class ImportResolver:
    """Dispatches import calls to a user-supplied implementation object."""

    def __init__(self, impl: Any, specs: Dict[str, ImportSpec]):
        self._impl = impl
        self._specs = dict(specs)

    @property
    def specs(self) -> Dict[str, ImportSpec]:
        return self._specs

    def has(self, name: str) -> bool:
        return name in self._specs

    def _bound(self, name: str):
        fn = getattr(self._impl, name, None) if self._impl is not None else None
        if fn is None or not callable(fn):
            owner = type(self._impl).__name__ if self._impl is not None else None
            raise PssImportError(
                f"import '{name}' is not supplied by the import object ({owner})")
        return fn

    def call(self, name: str, args) -> Any:
        """Synchronously invoke an import; used by the interpreter path.

        ``import solve`` functions are pure and always synchronous.  A
        synchronous ``import target`` works here too; an *async* target returns a
        coroutine the synchronous interpreter cannot await — that surfaces as a
        clear error pending async-execution support.
        """
        result = self._bound(name)(*args)
        if inspect.iscoroutine(result):
            result.close()
            raise PssImportError(
                f"import target '{name}' is async; async import execution is not "
                f"yet supported by the interpreter path — supply a synchronous "
                f"implementation for now")
        return result

    async def call_async(self, name: str, args) -> Any:
        """Invoke an import, awaiting it if the implementation is async."""
        result = self._bound(name)(*args)
        if inspect.isawaitable(result):
            return await result
        return result


# --- run-scoped activation -------------------------------------------------

_current: "contextvars.ContextVar[Optional[ImportResolver]]" = \
    contextvars.ContextVar("zsp_import_resolver", default=None)


def current_resolver() -> Optional[ImportResolver]:
    """Return the import resolver active for the current scenario run, if any."""
    return _current.get()


@contextlib.contextmanager
def use_resolver(resolver: Optional[ImportResolver]):
    """Activate *resolver* for the dynamic extent of the ``with`` block.

    Set within an async run, the value propagates across ``await`` boundaries and
    is inherited by child tasks (e.g. parallel activity branches), since
    ``contextvars`` are copied into tasks at creation time.
    """
    token = _current.set(resolver)
    try:
        yield resolver
    finally:
        _current.reset(token)
