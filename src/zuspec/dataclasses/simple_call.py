"""``zdc.SimpleCall[Args, Ret]`` — convenience alias for single-method protocols.

Expands into a full ``IfProtocol`` subclass with a single ``__call__`` method.

Example::

    # Equivalent to:
    #   class _Iface(zdc.IfProtocol):
    #       async def __call__(self, x: zdc.u32) -> zdc.u32: ...
    dat: zdc.SimpleCall[zdc.u32, zdc.u32] = zdc.port()
"""
from __future__ import annotations

from .if_protocol import IfProtocol


class _SimpleCallMeta(type(IfProtocol)):
    """Metaclass for SimpleCall that supports ``SimpleCall[Args, Ret]`` subscript."""

    def __getitem__(cls, params):
        if not isinstance(params, tuple) or len(params) < 2:
            raise TypeError(
                "SimpleCall requires at least two type parameters: SimpleCall[ArgType, RetType] "
                "or SimpleCall[Arg1, Arg2, ..., RetType]"
            )
        *arg_types, ret_type = params

        # Build a concrete IfProtocol subclass with a single async __call__
        async def __call__(self, *args) -> ret_type:  # type: ignore[return]
            ...

        __call__.__annotations__["return"] = ret_type
        for i, a in enumerate(arg_types):
            __call__.__annotations__[f"arg{i}"] = a

        protocol_cls = _SimpleCallMeta(
            f"SimpleCall[{', '.join(getattr(t, '__name__', repr(t)) for t in params)}]",
            (IfProtocol,),
            {"__call__": __call__},
        )
        return protocol_cls


class SimpleCall(IfProtocol, metaclass=_SimpleCallMeta):
    """Convenience single-method ``IfProtocol`` alias.

    ``SimpleCall[ArgType, RetType]`` produces an ``IfProtocol`` subclass with
    a single ``__call__`` method accepting one argument and returning ``RetType``.

    Multiple argument types can be chained: ``SimpleCall[A, B, Ret]`` produces
    ``__call__(self, arg0: A, arg1: B) -> Ret``.
    """

    async def __call__(self, *args):
        ...
