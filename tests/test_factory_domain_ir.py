"""DataModelFactory writes a component's ClockDomain/ResetDomain as the
domain IR (``domain_ir.py``; fw-hdl core-domains-plan "D8 design")."""

import zuspec.dataclasses as zdc
import zuspec.ir.core as ir
from zuspec.dataclasses.data_model_factory import DataModelFactory
from zuspec.ir.core.deserializer import IRDeserializer
from zuspec.ir.core.serializer import IRSerializer


def _build(cls):
    ctx = DataModelFactory().build(cls)
    t = next(v for k, v in ctx.type_m.items()
             if isinstance(v, ir.DataTypeComponent) and cls.__name__ in k)
    return ctx, t


def _vals(d):
    return {k: v.value for k, v in d.items()}


@zdc.dataclass
class Dom(zdc.Component):
    clock_domain = zdc.ClockDomain(period=zdc.Time.ns(4), name="fast_clk")
    reset_domain = zdc.ResetDomain(polarity="active_high", style="async")
    count: zdc.b8 = zdc.output(reset=0)

    @zdc.sync
    def _count(self):
        self.count = self.count + 1


def test_clock_and_reset():
    ctx, t = _build(Dom)
    assert isinstance(ctx.type_m["fw_clock_kind"], ir.DataTypeDomainKind)
    assert ctx.type_m["fw_reset_kind"].polarity == "active_low"
    clk, rst = t.domains
    assert (clk.name, clk.kind, clk.deriv) == ("clock_domain", "fw_clock_kind", "root")
    assert _vals(clk.params) == {"div": 1, "mul": 1, "phase_deg": 0, "period": 4_000_000}
    assert (rst.name, rst.kind, _vals(rst.params)) == ("reset_domain", "fw_reset_kind",
                                                       {"style": 0})
    assert [(a.target, a.kind, a.assoc, a.domain.decl) for a in t.domain_assocs] == [
        ([], "fw_clock_kind", "", "clock_domain"), ([], "fw_reset_kind", "", "reset_domain")]
    dclk, drst = t.domain_drivers
    assert (dclk.domain.decl, dclk.signal, dclk.attr) == ("clock_domain", ["fast_clk"], {})
    assert (drst.domain.decl, drst.signal) == ("reset_domain", ["rst"])
    assert _vals(drst.attr) == {"active_low": 0, "style": 2}


def test_defaults_and_no_reset_pin():
    """A clock without a name or period; a reset of style none has no
    driver (no pin)."""
    @zdc.dataclass
    class NoPin(zdc.Component):
        clock_domain = zdc.ClockDomain()
        reset_domain = zdc.ResetDomain(style="none")

    _, t = _build(NoPin)
    assert "period" not in t.domains[0].params
    assert _vals(t.domains[1].params) == {"style": 1}
    assert [(d.domain.decl, d.signal) for d in t.domain_drivers] == [("clock_domain", ["clk"])]


def test_inherited_and_sync_component():
    """A subclass carries its base's domain, named after the base's
    attribute; SyncComponent's default reset is active low and sync."""
    @zdc.dataclass
    class Base(zdc.Component):
        sys = zdc.ClockDomain(name="sys")

    @zdc.dataclass
    class Sub(Base):
        pass

    _, t = _build(Sub)
    assert [d.name for d in t.domains] == ["sys"]

    @zdc.dataclass
    class S(zdc.SyncComponent):
        pass

    _, t = _build(S)
    rst = next(d for d in t.domain_drivers if d.domain.decl == "reset_domain")
    assert rst.signal == ["rst_n"] and _vals(rst.attr)["active_low"] == 1
    assert _vals(next(d for d in t.domains if d.name == "reset_domain").params) == {"style": 1}


def test_derived_clock():
    @zdc.dataclass
    class Div(zdc.Component):
        clock_domain = zdc.DerivedClockDomain(source=zdc.super(), div=2)

    _, t = _build(Div)
    d = t.domains[0]
    assert d.deriv == "derived" and d.sources == []
    assert _vals(d.params) == {"div": 2, "mul": 1, "phase_deg": 0}


def test_no_domain():
    @zdc.dataclass
    class Plain(zdc.Component):
        a: zdc.bit = zdc.input()

    ctx, t = _build(Plain)
    assert t.domains == [] and t.domain_drivers == []
    assert "fw_clock_kind" not in ctx.type_m


def test_serialized_form_is_the_domain_ir():
    """The serialized component has the domain IR, not zdc's objects."""
    ctx, _ = _build(Dom)
    text = IRSerializer().serialize(ctx, None)
    assert "ClockDomain" not in text and "ResetDomain" not in text
    d = IRDeserializer()
    d.auto_register(ir)
    back, _ = d.deserialize(text)
    t = next(v for k, v in back.type_m.items() if "Dom" in k)
    assert t.clock_domain is None
    assert [x.name for x in t.domains] == ["clock_domain", "reset_domain"]
    assert t.domain_drivers[0].signal == ["fast_clk"]
    assert back.type_m["fw_reset_kind"].severities["related"] is ir.DomainSeverity.WARNING
