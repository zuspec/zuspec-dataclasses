"""Tier 1 tests for zdc.IfProtocol (Phase 1 DSL layer)."""
import pytest
import zuspec.dataclasses as zdc
from zuspec.ir.core.data_type import IfProtocolProperties


# ---------------------------------------------------------------------------
# Basic property capture
# ---------------------------------------------------------------------------

class TestIfProtocolBasicProperties:
    def test_defaults(self):
        class Iface(zdc.IfProtocol):
            async def get(self) -> zdc.u32: ...

        p = Iface._get_properties()
        assert p["req_always_ready"] is False
        assert p["max_outstanding"] == 1
        assert p["in_order"] is True
        assert p["fixed_latency"] is None

    def test_kwarg_override(self):
        class AXI(zdc.IfProtocol, max_outstanding=4, in_order=False):
            async def read(self, addr: zdc.u32, id: zdc.u4) -> zdc.u32: ...

        p = AXI._get_properties()
        assert p["max_outstanding"] == 4
        assert p["in_order"] is False

    def test_all_kwargs(self):
        class Full(zdc.IfProtocol,
                   req_always_ready=True,
                   req_registered=True,
                   resp_always_valid=True,
                   fixed_latency=4,
                   resp_has_backpressure=False,
                   max_outstanding=1,
                   in_order=True,
                   initiation_interval=2):
            async def op(self) -> zdc.u32: ...

        p = Full._get_properties()
        assert p["req_always_ready"] is True
        assert p["fixed_latency"] == 4
        assert p["initiation_interval"] == 2


# ---------------------------------------------------------------------------
# Inheritance
# ---------------------------------------------------------------------------

class TestIfProtocolInheritance:
    def test_subclass_inherits_props(self):
        class Base(zdc.IfProtocol, max_outstanding=4):
            async def read(self) -> zdc.u32: ...

        class Sub(Base):
            async def write(self, v: zdc.u32) -> None: ...

        assert Sub._get_properties()["max_outstanding"] == 4

    def test_subclass_can_override(self):
        class Base(zdc.IfProtocol, max_outstanding=4):
            async def read(self) -> zdc.u32: ...

        class Sub(Base, max_outstanding=8):
            async def read(self) -> zdc.u32: ...

        assert Sub._get_properties()["max_outstanding"] == 8
        assert Base._get_properties()["max_outstanding"] == 4


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

class TestIfProtocolValidation:
    def test_resp_always_valid_requires_fixed_latency(self):
        with pytest.raises(ValueError, match="fixed_latency"):
            class Bad(zdc.IfProtocol, resp_always_valid=True):
                async def op(self) -> zdc.u32: ...

    def test_fixed_latency_and_backpressure_mutually_exclusive(self):
        with pytest.raises(ValueError, match="mutually exclusive"):
            class Bad(zdc.IfProtocol,
                      resp_always_valid=True, fixed_latency=4,
                      resp_has_backpressure=True):
                async def op(self) -> zdc.u32: ...

    def test_max_outstanding_must_be_positive(self):
        with pytest.raises(ValueError, match="max_outstanding"):
            class Bad(zdc.IfProtocol, max_outstanding=0):
                async def op(self) -> None: ...

    def test_initiation_interval_must_be_positive(self):
        with pytest.raises(ValueError, match="initiation_interval"):
            class Bad(zdc.IfProtocol, initiation_interval=0):
                async def op(self) -> None: ...

    def test_valid_fixed_latency(self):
        # Should not raise
        class Good(zdc.IfProtocol, resp_always_valid=True, fixed_latency=4):
            async def op(self) -> zdc.u32: ...

        assert Good._get_properties()["fixed_latency"] == 4


# ---------------------------------------------------------------------------
# IR properties dataclass
# ---------------------------------------------------------------------------

class TestIfProtocolIRProperties:
    def test_get_ir_properties_returns_correct_type(self):
        class Iface(zdc.IfProtocol, max_outstanding=2, in_order=False):
            async def read(self) -> zdc.u32: ...

        props = Iface._get_ir_properties()
        assert isinstance(props, IfProtocolProperties)
        assert props.max_outstanding == 2
        assert props.in_order is False


# ---------------------------------------------------------------------------
# @zdc.call() per-method decorator
# ---------------------------------------------------------------------------

class TestZdcCallDecorator:
    def test_call_decorator_attaches_kwargs(self):
        class Iface(zdc.IfProtocol, max_outstanding=4):
            @zdc.call(max_outstanding=1)
            async def store(self, addr: zdc.u32, data: zdc.u32) -> None: ...

        assert Iface.store._zdc_call_kwargs == {"max_outstanding": 1}

    def test_call_decorator_preserves_function(self):
        class Iface(zdc.IfProtocol):
            @zdc.call(max_outstanding=2)
            async def load(self, addr: zdc.u32) -> zdc.u32: ...

        assert callable(Iface.load)
        assert Iface.load.__name__ == "load"
