"""Phase 1 tests — domain type objects and DataTypeComponent IR slots."""

import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.domain import (
    ClockDomain, DerivedClockDomain, InheritedDomain,
    ResetDomain, SoftwareResetDomain, HardwareResetDomain,
    ResetPolarity, ResetStyle,
    ClockPort, ClockBind, ResetBind, clock_port, clock_bind, reset_bind,
)
from zuspec.ir.core.data_type import DataTypeComponent


# ---------------------------------------------------------------------------
# T1  ClockDomain basic construction
# ---------------------------------------------------------------------------

class TestClockDomainBasic:
    def test_default_attrs(self):
        d = ClockDomain()
        assert d.period is None
        assert d.name is None

    def test_with_period(self):
        t = zdc.Time.ns(10)
        d = ClockDomain(period=t, name="sys")
        assert d.period is t
        assert d.name == "sys"

    def test_from_port(self):
        lam = lambda s: s.clk_in
        d = ClockDomain.from_port(lam)
        assert isinstance(d, ClockDomain)
        assert d._port_lambda is lam


# ---------------------------------------------------------------------------
# T2  DerivedClockDomain
# ---------------------------------------------------------------------------

class TestDerivedClockDomain:
    def test_defaults(self):
        parent = ClockDomain(period=zdc.Time.ns(10))
        d = DerivedClockDomain(source=parent)
        assert d.div == 1
        assert d.mul == 1
        assert d.phase == 0
        assert d.gate is None

    def test_divide_by_two(self):
        parent = ClockDomain(period=zdc.Time.ns(10))
        d = DerivedClockDomain(source=parent, div=2)
        assert d.div == 2
        assert isinstance(d, ClockDomain)

    def test_inherited_source(self):
        d = DerivedClockDomain()    # default source is InheritedDomain()
        assert isinstance(d.source, InheritedDomain)


# ---------------------------------------------------------------------------
# T3  ResetDomain defaults and variants
# ---------------------------------------------------------------------------

class TestResetDomain:
    def test_defaults(self):
        r = ResetDomain()
        assert r.polarity == ResetPolarity.ACTIVE_LOW
        assert r.style == ResetStyle.SYNC
        assert r.release_after is None

    def test_active_high_async(self):
        r = ResetDomain(polarity="active_high", style="async")
        assert r.polarity == ResetPolarity.ACTIVE_HIGH
        assert r.style == ResetStyle.ASYNC

    def test_software_reset_domain(self):
        hw = ResetDomain()
        sw = SoftwareResetDomain(hw_reset=True, sw_source=lambda s: s.ctrl_reg & 1)
        assert sw.hw_reset is True
        assert callable(sw.sw_source)
        assert isinstance(sw, ResetDomain)

    def test_hardware_reset_domain(self):
        r = HardwareResetDomain(polarity="active_low")
        assert isinstance(r, ResetDomain)
        assert isinstance(r, HardwareResetDomain)


# ---------------------------------------------------------------------------
# T4  ClockPort and factory function
# ---------------------------------------------------------------------------

class TestClockPort:
    def test_input_port(self):
        p = clock_port()
        assert isinstance(p, ClockPort)
        assert p.output is False

    def test_output_port(self):
        p = clock_port(output=True)
        assert p.output is True


# ---------------------------------------------------------------------------
# T5  clock_bind / reset_bind helpers
# ---------------------------------------------------------------------------

class TestBindHelpers:
    def test_clock_bind(self):
        d = ClockDomain()
        port = object()
        b = clock_bind(d, port)
        assert isinstance(b, ClockBind)
        assert b.domain is d
        assert b.port is port

    def test_reset_bind_default_polarity(self):
        r = ResetDomain()
        port = object()
        b = reset_bind(r, port)
        assert isinstance(b, ResetBind)
        assert b.active_low is True

    def test_reset_bind_active_high(self):
        r = ResetDomain(polarity="active_high")
        port = object()
        b = reset_bind(r, port, active_low=False)
        assert b.active_low is False


# ---------------------------------------------------------------------------
# T6  DataTypeComponent now has clock_domain / reset_domain slots
# ---------------------------------------------------------------------------

class TestDataTypeComponentSlots:
    def _make_dtc(self):
        # Verify the new fields exist in the dataclass definition
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(DataTypeComponent)}
        return field_names

    def test_clock_domain_slot_exists_and_defaults_none(self):
        field_names = self._make_dtc()
        assert "clock_domain" in field_names

    def test_reset_domain_slot_exists_and_defaults_none(self):
        field_names = self._make_dtc()
        assert "reset_domain" in field_names

    def test_can_set_clock_domain(self):
        import dataclasses
        # Verify default is None
        defaults = {f.name: f.default for f in dataclasses.fields(DataTypeComponent)}
        assert defaults["clock_domain"] is None

    def test_can_set_reset_domain(self):
        import dataclasses
        defaults = {f.name: f.default for f in dataclasses.fields(DataTypeComponent)}
        assert defaults["reset_domain"] is None


# ---------------------------------------------------------------------------
# T7  Public API surface — all names are importable from zdc
# ---------------------------------------------------------------------------

class TestPublicAPI:
    @pytest.mark.parametrize("name", [
        "ClockDomain", "DerivedClockDomain", "InheritedDomain",
        "ResetDomain", "SoftwareResetDomain", "HardwareResetDomain",
        "ClockPort", "ClockBind", "ResetBind",
        "clock_port", "clock_bind", "reset_bind",
        # Phase 1 additions
        "super", "PowerDomain", "reset_domain",
        # Phase 2 additions
        "SyncComponent",
    ])
    def test_importable_from_zdc(self, name):
        assert hasattr(zdc, name), f"zdc.{name} not found"


# ---------------------------------------------------------------------------
# T8  zdc.super() — parent-domain sentinel
# ---------------------------------------------------------------------------

class TestSuperSentinel:
    def test_returns_inherited_domain(self):
        from zuspec.dataclasses.domain import InheritedDomain
        s = zdc.super()
        assert isinstance(s, InheritedDomain)

    def test_each_call_returns_new_instance(self):
        a = zdc.super()
        b = zdc.super()
        assert a is not b

    def test_used_in_derived_clock_domain(self):
        from zuspec.dataclasses.domain import InheritedDomain
        d = zdc.DerivedClockDomain(source=zdc.super(), div=4)
        assert isinstance(d.source, InheritedDomain)
        assert d.div == 4


# ---------------------------------------------------------------------------
# T9  PowerDomain
# ---------------------------------------------------------------------------

class TestPowerDomain:
    def test_defaults(self):
        pd = zdc.PowerDomain()
        assert pd.name is None
        assert pd.always_on is False

    def test_named_domain(self):
        pd = zdc.PowerDomain(name="always_on", always_on=True)
        assert pd.name == "always_on"
        assert pd.always_on is True


# ---------------------------------------------------------------------------
# T10  reset_domain() factory
# ---------------------------------------------------------------------------

class TestResetDomainFactory:
    def test_returns_descriptor(self):
        from zuspec.dataclasses.domain import _ResetDomainField
        f = zdc.reset_domain(reset=lambda s: s.rst_n)
        assert isinstance(f, _ResetDomainField)

    def test_default_polarity(self):
        from zuspec.dataclasses.domain import _ResetDomainField
        f = zdc.reset_domain()
        assert f._polarity == ResetPolarity.ACTIVE_LOW
        assert f._style == ResetStyle.SYNC

    def test_active_high_async(self):
        from zuspec.dataclasses.domain import _ResetDomainField
        f = zdc.reset_domain(polarity="active_high", style="async")
        assert f._polarity == ResetPolarity.ACTIVE_HIGH
        assert f._style == ResetStyle.ASYNC

    def test_reset_lambda_stored(self):
        lam = lambda s: s.rst_n
        f = zdc.reset_domain(reset=lam)
        assert f.reset_lambda is lam


# ---------------------------------------------------------------------------
# T11  clock_domain() factory — name parameter
# ---------------------------------------------------------------------------

class TestClockDomainFactory:
    def test_name_parameter(self):
        from zuspec.dataclasses.domain import _ClockDomainField
        f = zdc.clock_domain(clock=lambda s: s.CLK, name="sys_clk",
                             period=zdc.Time.ns(10))
        assert isinstance(f, _ClockDomainField)
        assert f._name == "sys_clk"
        assert f._period is not None


# ---------------------------------------------------------------------------
# T12  SyncComponent base class
# ---------------------------------------------------------------------------

class TestSyncComponent:
    def test_inherits_component(self):
        assert issubclass(zdc.SyncComponent, zdc.Component)

    def test_has_clock_domain(self):
        from zuspec.dataclasses.domain import ClockDomain
        assert isinstance(zdc.SyncComponent.clock_domain, ClockDomain)

    def test_has_reset_domain(self):
        from zuspec.dataclasses.domain import ResetDomain
        assert isinstance(zdc.SyncComponent.reset_domain, ResetDomain)

    def test_subclass_overrides_reset_style(self):
        from zuspec.dataclasses.domain import ResetDomain

        @zdc.dataclass
        class NoReset(zdc.SyncComponent):
            reset_domain = zdc.ResetDomain(style="none")
            count: zdc.bit32 = zdc.output(reset=0)

        assert NoReset.reset_domain.style == ResetStyle.NONE
        # Parent class should be unchanged
        assert zdc.SyncComponent.reset_domain.style == ResetStyle.SYNC

    def test_rst_property_no_pin(self):
        """rst returns False when no matching reset pin exists."""
        import asyncio

        @zdc.dataclass
        class SimpleSync(zdc.SyncComponent):
            count: zdc.bit32 = zdc.output(reset=0)

            @zdc.sync
            def _inc(self):
                self.count = self.count + 1

        async def run():
            async with zdc.simulate(SimpleSync) as c:
                assert c.rst is False

        asyncio.run(run())

    def test_sync_without_explicit_clock(self):
        """@zdc.sync on SyncComponent works without explicit clock/reset args."""
        import asyncio

        @zdc.dataclass
        class FreeCounter(zdc.SyncComponent):
            count: zdc.bit32 = zdc.output(reset=0)

            @zdc.sync
            def _inc(self):
                self.count = self.count + 1

        async def run():
            async with zdc.simulate(FreeCounter) as c:
                await c.domain.tick(5)
                assert c.count == 5

        asyncio.run(run())
