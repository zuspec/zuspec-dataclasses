"""
Clock and Reset Domain types for zuspec-dataclasses.

These objects are declared at **class level** on a Component subclass —
not as dataclass fields — so they are available before the component
metaclass/factory machinery runs.

Typical usage::

    @zdc.dataclass
    class MyTop(zdc.Component):
        clk_domain = zdc.ClockDomain(period=zdc.Time.ns(10), name="sys")
        rst_domain = zdc.ResetDomain(polarity="active_low", style="sync")

        sub : MySubsystem = zdc.inst()   # inherits clk_domain / rst_domain

    @zdc.dataclass
    class Counter(zdc.Component):
        enable : zdc.bit = zdc.input()
        count  : zdc.b32 = zdc.output(reset=0)

        @zdc.sync          # binds to inherited clock_domain by default
        def _count(self):
            if self.enable:
                self.count = self.count + 1
"""

from __future__ import annotations

import asyncio
import dataclasses as dc
from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# Clock domain types
# ---------------------------------------------------------------------------

@dc.dataclass
class ClockDomain:
    """Root clock domain.

    :param period: Clock period (e.g. ``zdc.Time.ns(10)``).  ``None`` means the
        period is unknown and will be provided at synthesis time.  SDC export
        and STA require a concrete period.
    :param name: Hint for the generated clock port/net name.  Auto-derived from
        the attribute name on the component class if not set.
    """
    period: Optional[Any] = None   # Time | None; Any avoids circular import with types.py
    name:   Optional[str] = None

    # Runtime hook — set by the pipeline runtime to delegate wait_cycle()
    # to the actual timebase.  None at Level 0 (functional simulation).
    _timebase: Any = dc.field(default=None, init=False, repr=False, compare=False)
    _rt_domain: Any = dc.field(default=None, init=False, repr=False, compare=False)

    async def wait_cycle(self, n: int = 1) -> None:
        """Wait *n* clock cycles.

        At Level 0 (functional/NOP): returns immediately.
        At Level 1 (behavioral timing): delegates to the runtime timebase so
        actual simulated time passes.

        Args:
            n: Number of cycles.  Must be >= 1.
        """
        if self._timebase is not None and self._rt_domain is not None:
            await self._timebase.wait_cycles(n, self._rt_domain)

    async def wait_cycles(self, n: int) -> None:
        """Alias for :meth:`wait_cycle` with explicit count."""
        await self.wait_cycle(n)

    @property
    def period_ns(self) -> Optional[float]:
        """Clock period in nanoseconds, or ``None`` if no period is set."""
        if self.period is None:
            return None
        if hasattr(self.period, "as_ns"):
            return float(self.period.as_ns())
        return float(self.period)

    @staticmethod
    def from_port(port_lambda: Callable) -> "ClockDomain":
        """Create a domain whose clock is driven by an explicit ClockPort field.

        :param port_lambda: Lambda ``lambda s: s.clk_in`` referencing a
            ``ClockPort``-typed field on the component.

        Used for clock dividers, PLLs, and other components that receive or
        generate physical clock signals::

            @zdc.dataclass
            class ClockDivider(zdc.Component):
                clk_in  : zdc.ClockPort = zdc.clock_port()
                clk_domain = zdc.ClockDomain.from_port(lambda s: s.clk_in)
        """
        d = ClockDomain()
        d._port_lambda = port_lambda
        return d


@dc.dataclass
class InheritedDomain:
    """Sentinel: use whatever domain the parent component provides.

    Pass as the ``source`` of a :class:`DerivedClockDomain` when the derived
    domain should be relative to the parent's default domain rather than to a
    named peer domain on this component.
    """
    pass


@dc.dataclass
class DerivedClockDomain(ClockDomain):
    """A clock domain derived from another by integer ratio or gating.

    :param source: The source domain.  Use :class:`InheritedDomain` to derive
        from the parent's default domain, or a lambda ``lambda s: s.sys_clk``
        to derive from a named domain on the same component.
    :param div: Divide ratio (output = source / div).  Default 1.
    :param mul: Multiply ratio (output = source * mul).  Default 1.
    :param phase: Phase offset in units of the source period.  Default 0.
    :param gate: Lambda ``lambda s: s.pll_locked`` giving a 1-bit enable
        signal.  When the signal is 0, the derived clock is gated off.
    """
    source: Any = dc.field(default_factory=InheritedDomain)
    div:    int = 1
    mul:    int = 1
    phase:  int = 0
    gate:   Optional[Callable] = None


# ---------------------------------------------------------------------------
# Reset domain types
# ---------------------------------------------------------------------------

@dc.dataclass
class ResetDomain:
    """Hardware reset domain.

    :param polarity: ``"active_low"`` (default, signal name ``rst_n``) or
        ``"active_high"`` (signal name ``rst``).
    :param style: ``"sync"`` (default) — reset is sampled at the clock edge;
        ``"async"`` — reset takes effect immediately regardless of clock;
        ``"none"`` — no reset logic generated (reset-free design).
    :param release_after: Another :class:`ResetDomain` that must be released
        first.  Used by :class:`SDCEmitPass` to order reset de-assertion.
    """
    polarity:      str  = "active_low"   # "active_low" | "active_high"
    style:         str  = "sync"         # "sync" | "async" | "none"
    release_after: Optional["ResetDomain"] = None


@dc.dataclass
class SoftwareResetDomain(ResetDomain):
    """Reset domain controlled (partially or wholly) by a register bit.

    The synthesis engine OR-combines the hardware reset signal with the
    software reset bit to produce the effective reset condition::

        wire _sw_rst  = ctrl_reg[0];
        wire _rst_comb = !rst_n | _sw_rst;

    :param hw_reset: If ``True`` (default), the domain also responds to the
        parent hardware reset.  If ``False``, only the software bit causes a
        reset (no hardware reset input on this domain).
    :param sw_source: Lambda ``lambda s: s.ctrl_reg & 1`` producing a 1-bit
        expression.  The lambda receives the component instance as ``s`` and
        must return a 1-bit value that is 1 when reset is requested.
    """
    hw_reset:   bool              = True
    sw_source:  Optional[Callable] = None


@dc.dataclass
class HardwareResetDomain(ResetDomain):
    """Reset domain that responds only to the root hardware reset.

    Use this on a child component that must be immune to intermediate software
    resets in the hierarchy (e.g., a sticky error register)::

        @zdc.dataclass
        class ErrorLog(zdc.Component):
            rst_domain = zdc.HardwareResetDomain()
            errors : zdc.b32 = zdc.reg(reset=0)
    """
    pass


# ---------------------------------------------------------------------------
# Clock port type
# ---------------------------------------------------------------------------

@dc.dataclass
class ClockPort:
    """Explicit physical clock port on a component.

    Most components do not need this — they inherit a domain and the synthesis
    engine generates the clock port automatically.  Use ``ClockPort`` only
    when the component must expose or generate a physical clock signal (e.g. a
    clock divider or PLL wrapper).

    :param output: ``True`` if this component *drives* the clock
        (e.g. a clock divider output).  Default ``False`` (input).
    """
    output: bool = False


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------

def clock_port(output: bool = False) -> ClockPort:
    """Declare an explicit physical clock port field on a component.

    :param output: Set ``True`` if this component drives the clock.

    Usage::

        @zdc.dataclass
        class ClockDivider(zdc.Component):
            clk_in  : zdc.ClockPort = zdc.clock_port()
            clk_out : zdc.ClockPort = zdc.clock_port(output=True)
    """
    return ClockPort(output=output)


# ---------------------------------------------------------------------------
# Bind helpers for blackbox wrappers (O-DOM-2a)
# ---------------------------------------------------------------------------

@dc.dataclass
class ClockBind:
    """Binds a ClockDomain to a physical ClockPort field.

    Returned by :func:`clock_bind`; used in ``__bind__`` for components that
    wrap existing HDL where the clock appears as an explicit port.
    """
    domain: ClockDomain
    port:   Any     # ClockPort field reference (lambda result)


@dc.dataclass
class ResetBind:
    """Binds a ResetDomain to a physical 1-bit reset port field.

    Returned by :func:`reset_bind`; carries an ``active_low`` override so the
    bind can correct for polarity mismatches between the domain declaration and
    the existing port.
    """
    domain:     ResetDomain
    port:       Any     # 1-bit field reference
    active_low: bool = True


def clock_bind(domain: ClockDomain, port: Any) -> ClockBind:
    """Associate a ClockDomain with a physical ClockPort in ``__bind__``.

    Use when wrapping existing HDL that exposes the clock as an explicit input
    port rather than inheriting it from the domain tree::

        @zdc.dataclass
        class ExtIPWrapper(zdc.Component):
            clk_in : zdc.ClockPort = zdc.clock_port()

            def __bind__(self):
                return (
                    zdc.clock_bind(self.clock_domain, self.clk_in),
                    zdc.reset_bind(self.reset_domain, self.rst_n, active_low=True),
                )
    """
    return ClockBind(domain=domain, port=port)


def reset_bind(domain: ResetDomain, port: Any, *, active_low: bool = True) -> ResetBind:
    """Associate a ResetDomain with a physical reset port in ``__bind__``.

    :param active_low: Override the polarity if the existing port's active
        level differs from the domain declaration.
    """
    return ResetBind(domain=domain, port=port, active_low=active_low)


# ---------------------------------------------------------------------------
# clock_domain() — field-level factory for pipeline-attached clock domains
# ---------------------------------------------------------------------------

class _ClockDomainField:
    """Descriptor returned by :func:`clock_domain`.

    Lazily creates a :class:`ClockDomain` instance per component instance,
    storing the clock/reset lambdas for use by the pipeline runtime.

    Markers:
        _zdc_clock_domain_field: True — recognised by the pipeline runtime
            and the synthesis pass.
    """

    _zdc_clock_domain_field: bool = True

    def __init__(
        self,
        clock: Optional[Callable] = None,
        reset: Optional[Callable] = None,
        period: Optional[Any] = None,
    ) -> None:
        self._clock = clock
        self._reset = reset
        self._period = period
        self._attr_name: str = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr_name = name

    def __get__(self, obj, objtype=None) -> "ClockDomain | _ClockDomainField":
        if obj is None:
            return self
        inst_key = f"_cdf_inst_{self._attr_name}"
        cd = obj.__dict__.get(inst_key)
        if cd is None or not isinstance(cd, ClockDomain):
            cd = ClockDomain(period=self._period)
            obj.__dict__[inst_key] = cd
        return cd

    def __set__(self, obj, value: "ClockDomain") -> None:
        # When @zdc.dataclass __init__ sets the field to its default (the
        # descriptor itself), ignore — __get__ creates the real ClockDomain lazily.
        if isinstance(value, _ClockDomainField):
            return
        inst_key = f"_cdf_inst_{self._attr_name}"
        obj.__dict__[inst_key] = value

    @property
    def clock_lambda(self) -> Optional[Callable]:
        return self._clock

    @property
    def reset_lambda(self) -> Optional[Callable]:
        return self._reset


def clock_domain(
    *,
    clock: Optional[Callable] = None,
    reset: Optional[Callable] = None,
    period: Optional[Any] = None,
) -> "_ClockDomainField":
    """Declare a :class:`ClockDomain` field on a component for use by
    ``@zdc.pipeline(clock_domain=...)``.

    Analogous to ``zdc.input()`` / ``zdc.output()`` for clock domains.

    Args:
        clock: Lambda ``lambda self: self.clk`` returning the clock bit field.
        reset: Lambda ``lambda self: self.rst_n`` returning the reset field
               (optional).
        period: Optional clock period hint for future timing analysis.

    Example::

        @zdc.dataclass
        class Cpu(zdc.Component):
            clk: zdc.bit = zdc.input()
            cd:  zdc.ClockDomain = zdc.clock_domain(clock=lambda s: s.clk)

            @zdc.pipeline(clock_domain=lambda s: s.cd)
            async def _fetch(self): ...
    """
    return _ClockDomainField(clock=clock, reset=reset, period=period)
