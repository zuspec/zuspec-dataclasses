"""``zdc.IfProtocol`` — interface protocol base class.

An ``IfProtocol`` subclass declares a named set of async methods that describe
a hardware port's request/response contract together with protocol properties
(``max_outstanding``, ``in_order``, ``fixed_latency``, …).

Example::

    class AXIReadIface(zdc.IfProtocol, max_outstanding=4, in_order=False):
        async def read(self, addr: zdc.u32, id: zdc.u4) -> zdc.u32: ...

The class can then be used as a port type::

    @zdc.dataclass
    class Cache(zdc.Component):
        mem: AXIReadIface = zdc.port()
"""
from __future__ import annotations

from typing import Optional


def call(**protocol_kwargs):
    """Per-method protocol property override inside an ``IfProtocol`` class.

    Example::

        class Iface(zdc.IfProtocol, max_outstanding=4):
            @zdc.call(max_outstanding=1)
            async def store(self, addr: zdc.u32, data: zdc.u32) -> None: ...
    """
    def decorator(fn):
        fn._zdc_call_kwargs = protocol_kwargs
        return fn
    return decorator


_PROTOCOL_PROPS = (
    "req_always_ready",
    "req_registered",
    "resp_always_valid",
    "fixed_latency",
    "resp_has_backpressure",
    "max_outstanding",
    "in_order",
    "initiation_interval",
)

_PROP_DEFAULTS = {
    "req_always_ready":      False,
    "req_registered":        False,
    "resp_always_valid":     False,
    "fixed_latency":         None,
    "resp_has_backpressure": False,
    "max_outstanding":       1,
    "in_order":              True,
    "initiation_interval":   1,
}


def _validate_props(props: dict, cls_name: str) -> None:
    """Raise ValueError for invalid property combinations."""
    if props["resp_always_valid"] and props["fixed_latency"] is None:
        raise ValueError(
            f"{cls_name}: resp_always_valid=True requires fixed_latency to be set"
        )
    if props["fixed_latency"] is not None and props["resp_has_backpressure"]:
        raise ValueError(
            f"{cls_name}: fixed_latency and resp_has_backpressure=True are mutually exclusive"
        )
    if props["max_outstanding"] < 1:
        raise ValueError(
            f"{cls_name}: max_outstanding must be >= 1, got {props['max_outstanding']}"
        )
    if props["initiation_interval"] < 1:
        raise ValueError(
            f"{cls_name}: initiation_interval must be >= 1, got {props['initiation_interval']}"
        )


class IfProtocolMeta(type):
    """Metaclass that captures protocol keyword arguments at class definition."""

    def __new__(mcs, name, bases, namespace, **kwargs):
        # Inherit default props from IfProtocol base (or first IfProtocol parent)
        inherited = {}
        for base in bases:
            if hasattr(base, "_zdc_protocol_props"):
                inherited = dict(base._zdc_protocol_props)
                break

        # Build props: start from defaults, then inherited, then kwargs
        props = dict(_PROP_DEFAULTS)
        props.update(inherited)
        for k, v in kwargs.items():
            if k in _PROTOCOL_PROPS:
                props[k] = v

        cls = super().__new__(mcs, name, bases, namespace)
        cls._zdc_protocol_props = props

        # Validate (skip the bare IfProtocol class itself)
        if any(hasattr(b, "_zdc_protocol_props") for b in bases):
            _validate_props(props, name)

        return cls

    def __init__(cls, name, bases, namespace, **kwargs):
        # Consume the kwargs so type.__init__ does not see them
        super().__init__(name, bases, namespace)


class IfProtocol(metaclass=IfProtocolMeta):
    """Base class for interface protocol definitions.

    Subclass and declare abstract async methods (body ``...``) to specify the
    contract::

        class DatIface(zdc.IfProtocol, max_outstanding=1):
            async def get(self) -> zdc.u32: ...

    Protocol properties (class keyword args):

    * ``req_always_ready``      – requester-side ready is permanently asserted
    * ``req_registered``        – request is registered (one-cycle delay)
    * ``resp_always_valid``     – response is valid every cycle (implies fixed_latency)
    * ``fixed_latency``         – response arrives exactly N cycles after request
    * ``resp_has_backpressure`` – response channel has a ready signal
    * ``max_outstanding``       – max simultaneous in-flight requests (default 1)
    * ``in_order``              – responses arrive in request order (default True)
    * ``initiation_interval``   – min cycles between requests (default 1)
    """

    @classmethod
    def _get_properties(cls) -> dict:
        """Return the resolved protocol properties dict."""
        return cls._zdc_protocol_props

    @classmethod
    def _get_ir_properties(cls):
        """Return an ``IfProtocolProperties`` IR dataclass instance."""
        from zuspec.ir.core.data_type import IfProtocolProperties
        p = cls._zdc_protocol_props
        return IfProtocolProperties(
            req_always_ready=p["req_always_ready"],
            req_registered=p["req_registered"],
            resp_always_valid=p["resp_always_valid"],
            fixed_latency=p["fixed_latency"],
            resp_has_backpressure=p["resp_has_backpressure"],
            max_outstanding=p["max_outstanding"],
            in_order=p["in_order"],
            initiation_interval=p["initiation_interval"],
        )
