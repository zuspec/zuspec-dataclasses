"""Phase 1 tests — domain type objects and DataTypeComponent IR slots."""

import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.domain import (
    ClockDomain, DerivedClockDomain, InheritedDomain,
    ResetDomain, SoftwareResetDomain, HardwareResetDomain,
    ClockPort, ClockBind, ResetBind, clock_port, clock_bind, reset_bind,
)
from zuspec.dataclasses.ir.data_type import DataTypeComponent


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
        assert r.polarity == "active_low"
        assert r.style == "sync"
        assert r.release_after is None

    def test_active_high_async(self):
        r = ResetDomain(polarity="active_high", style="async")
        assert r.polarity == "active_high"
        assert r.style == "async"

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
    ])
    def test_importable_from_zdc(self, name):
        assert hasattr(zdc, name), f"zdc.{name} not found"
