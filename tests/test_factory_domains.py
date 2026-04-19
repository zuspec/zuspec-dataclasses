"""Phase 3 tests — DataModelFactory extracts ClockDomain/ResetDomain from class attrs."""

import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.domain import ClockDomain, ResetDomain, HardwareResetDomain
from zuspec.dataclasses.data_model_factory import DataModelFactory
from zuspec.ir.core.data_type import DataTypeComponent


def _get_dtc(cls):
    """Return DataTypeComponent by walking ctx types."""
    factory = DataModelFactory()
    ctx = factory.build(cls)
    for key, val in ctx.type_m.items():
        if isinstance(val, DataTypeComponent) and cls.__name__ in key:
            return val
    return None


# ---------------------------------------------------------------------------
# T1  Component without any domain declaration → None
# ---------------------------------------------------------------------------

class TestNoDomain:
    def test_no_domain_clock_is_none(self):
        @zdc.dataclass
        class NoDomainComp(zdc.Component):
            clock : zdc.bit = zdc.input()
            reset : zdc.bit = zdc.input()
            count : zdc.b32 = zdc.output(reset=0)

            @zdc.sync(clock="clock", reset="reset")
            def _count(self):
                if self.reset:
                    self.count = 0
                else:
                    self.count = self.count + 1

        dtc = _get_dtc(NoDomainComp)
        assert dtc is not None
        assert dtc.clock_domain is None

    def test_no_domain_reset_is_none(self):
        @zdc.dataclass
        class NoDomainComp2(zdc.Component):
            clock : zdc.bit = zdc.input()
            count : zdc.b32 = zdc.output(reset=0)

            @zdc.sync(clock="clock")
            def _count(self):
                self.count = self.count + 1

        dtc = _get_dtc(NoDomainComp2)
        assert dtc is not None
        assert dtc.reset_domain is None


# ---------------------------------------------------------------------------
# T2  Component with explicit class-level domain → captured
# ---------------------------------------------------------------------------

class TestExplicitDomain:
    def test_clock_domain_captured(self):
        @zdc.dataclass
        class WithClkDomain(zdc.Component):
            clock_domain = zdc.ClockDomain(period=zdc.Time.ns(10), name="sys")

            clock : zdc.bit = zdc.input()
            count : zdc.b32 = zdc.output(reset=0)

            @zdc.sync(clock="clock")
            def _count(self):
                self.count = self.count + 1

        dtc = _get_dtc(WithClkDomain)
        assert dtc is not None
        assert isinstance(dtc.clock_domain, ClockDomain)
        assert dtc.clock_domain.name == "sys"

    def test_reset_domain_captured(self):
        @zdc.dataclass
        class WithRstDomain(zdc.Component):
            reset_domain = zdc.ResetDomain(polarity="active_low", style="sync")

            clock : zdc.bit = zdc.input()
            reset : zdc.bit = zdc.input()
            count : zdc.b32 = zdc.output(reset=0)

            @zdc.sync(clock="clock", reset="reset")
            def _count(self):
                if self.reset:
                    self.count = 0
                else:
                    self.count = self.count + 1

        dtc = _get_dtc(WithRstDomain)
        assert dtc is not None
        assert isinstance(dtc.reset_domain, ResetDomain)
        assert dtc.reset_domain.polarity == "active_low"

    def test_both_domains_captured(self):
        @zdc.dataclass
        class WithBothDomains(zdc.Component):
            clock_domain = zdc.ClockDomain(period=zdc.Time.ns(20), name="slow")
            reset_domain = zdc.HardwareResetDomain()

            clock : zdc.bit = zdc.input()
            reset : zdc.bit = zdc.input()
            out   : zdc.bit = zdc.output(reset=0)

            @zdc.sync(clock="clock", reset="reset")
            def _proc(self):
                self.out = 1

        dtc = _get_dtc(WithBothDomains)
        assert dtc is not None
        assert isinstance(dtc.clock_domain, ClockDomain)
        assert isinstance(dtc.reset_domain, HardwareResetDomain)


# ---------------------------------------------------------------------------
# T3  Domain on parent class is inherited (MRO walk)
# ---------------------------------------------------------------------------

class TestDomainInheritance:
    def test_child_inherits_parent_domain(self):
        @zdc.dataclass
        class ParentComp(zdc.Component):
            clock_domain = zdc.ClockDomain(period=zdc.Time.ns(10), name="parent_clk")
            clock : zdc.bit = zdc.input()
            count : zdc.b32 = zdc.output(reset=0)

            @zdc.sync(clock="clock")
            def _count(self):
                self.count = self.count + 1

        @zdc.dataclass
        class ChildComp(ParentComp):
            extra : zdc.bit = zdc.output(reset=0)

            @zdc.sync(clock="clock")
            def _extra(self):
                self.extra = 1

        dtc = _get_dtc(ChildComp)
        assert dtc is not None
        assert isinstance(dtc.clock_domain, ClockDomain)
        assert dtc.clock_domain.name == "parent_clk"

    def test_child_overrides_parent_domain(self):
        @zdc.dataclass
        class ParentCompB(zdc.Component):
            clock_domain = zdc.ClockDomain(period=zdc.Time.ns(10), name="slow")
            clock : zdc.bit = zdc.input()
            count : zdc.b32 = zdc.output(reset=0)

            @zdc.sync(clock="clock")
            def _count(self):
                self.count = self.count + 1

        @zdc.dataclass
        class ChildCompB(ParentCompB):
            clock_domain = zdc.ClockDomain(period=zdc.Time.ns(2), name="fast")

        dtc = _get_dtc(ChildCompB)
        assert dtc is not None
        assert dtc.clock_domain.name == "fast"


# ---------------------------------------------------------------------------
# T4  Domain attr does NOT create a dataclass field
# ---------------------------------------------------------------------------

class TestDomainNotAField:
    def test_clock_domain_attr_not_in_fields(self):
        @zdc.dataclass
        class NoFieldDomain(zdc.Component):
            clock_domain = zdc.ClockDomain(period=zdc.Time.ns(5))
            clock : zdc.bit = zdc.input()
            count : zdc.b32 = zdc.output(reset=0)

            @zdc.sync(clock="clock")
            def _count(self):
                self.count = self.count + 1

        import dataclasses
        field_names = {f.name for f in dataclasses.fields(NoFieldDomain)}
        assert "clock_domain" not in field_names
