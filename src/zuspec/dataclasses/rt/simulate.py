"""Simulation context manager for Zuspec hardware components.

:func:`simulate` is an async context manager that creates a component inside
a configured simulation environment (VCD tracing, etc.) and ensures cleanup
on exit.

Typical usage::

    import asyncio
    import zuspec.dataclasses as zdc

    @zdc.dataclass
    class Counter(zdc.Component):
        clock  : zdc.bit   = zdc.input()
        reset  : zdc.bit   = zdc.input()
        enable : zdc.bit   = zdc.input()
        count  : zdc.bit32 = zdc.output()

        @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
        def _count(self):
            if self.reset:
                self.count = 0
            elif self.enable:
                self.count = self.count + 1

    async def run():
        async with zdc.simulate(Counter, vcd="trace.vcd") as counter:
            # Drive reset
            counter.reset = 1
            counter.clock = 0
            for _ in range(2):
                counter.clock = 1
                await counter.wait(zdc.Time.ns(5))
                counter.clock = 0
                await counter.wait(zdc.Time.ns(5))
            counter.reset = 0
            counter.enable = 1
            # Run 10 cycles
            for _ in range(10):
                counter.clock = 1
                await counter.wait(zdc.Time.ns(5))
                counter.clock = 0
                await counter.wait(zdc.Time.ns(5))
            assert counter.count == 10
        # counter.close() called automatically — VCD flushed

    asyncio.run(run())

The factory is pushed onto the Config stack only for the duration of component
construction inside ``__aenter__``, then immediately popped.  The tracer
reference is captured into the component's runtime at construction time and
remains active for the lifetime of the component.
"""
from __future__ import annotations

from typing import Optional, Type, TypeVar

from ..types import Component

T = TypeVar('T', bound=Component)


class SimulateContext:
    """Async context manager returned by :func:`simulate`.

    Pushes a configured :class:`ObjFactory` onto the Config factory stack,
    constructs the component (factory is popped immediately after construction),
    and calls :meth:`Component.close` on context exit to flush VCD files and
    cancel simulation tasks.
    """

    def __init__(
        self,
        cls: Type[T],
        *args,
        vcd: Optional[str] = None,
        **kwargs,
    ) -> None:
        self._cls = cls
        self._args = args
        self._kwargs = kwargs
        self._vcd = vcd
        self._component: Optional[T] = None

    async def __aenter__(self) -> T:
        from ..config import Config
        from .obj_factory import ObjFactory

        factory = ObjFactory()
        if self._vcd is not None:
            from .vcd_tracer import VCDTracer
            factory.tracer = VCDTracer(self._vcd)
            factory.enable_signal_tracing = True

        config = Config.inst()
        config.push_factory(factory)
        try:
            self._component = self._cls(*self._args, **self._kwargs)
        finally:
            # Factory only needed during construction; tracer reference is
            # captured into CompImplRT._tracer at __comp_build__ time.
            config.pop_factory()

        # Attach SimDomain when the component declares class-level domains
        self._attach_sim_domains(self._component)

        return self._component  # type: ignore[return-value]

    def _attach_sim_domains(self, comp: T) -> None:
        """Attach SimDomain instance(s) to *comp* after construction.

        * If the class declares a single ``clock_domain`` attribute, exposes
          ``comp.domain`` as a convenience shortcut.
        * Named ``ClockDomain`` class attributes are also exposed individually
          (e.g. ``comp.rx_domain``).
        """
        from .sim_domain import SimDomain
        try:
            from ..domain import ClockDomain
        except ImportError:
            return

        cls = type(comp)
        default_domain = getattr(cls, 'clock_domain', None)
        if default_domain is not None and isinstance(default_domain, ClockDomain):
            object.__setattr__(comp, 'domain', SimDomain(comp, default_domain))

        # Expose any additionally named ClockDomain class attributes
        for attr in vars(cls):
            if attr.startswith('_') or attr == 'clock_domain':
                continue
            val = getattr(cls, attr, None)
            if isinstance(val, ClockDomain):
                object.__setattr__(comp, f"{attr}_sim", SimDomain(comp, val))


    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self._component is not None:
            self._component.close()
        return False


def simulate(
    cls: Type[T],
    *args,
    vcd: Optional[str] = None,
    **kwargs,
) -> SimulateContext:
    """Create a simulatable component inside an async context manager.

    The component is constructed using the given class and arguments, with an
    optional VCD tracer attached.  Use as an ``async with`` statement; the
    component is yielded as the context variable and :meth:`Component.close`
    is called automatically on exit.

    :param cls: Component class to instantiate.
    :param vcd: Path for VCD waveform output, or ``None`` (default).
    :type vcd: str or None
    :param kwargs: Additional keyword arguments forwarded to the component
        constructor.

    Example::

        async with zdc.simulate(Counter, vcd="trace.vcd") as counter:
            counter.reset = 1
            for _ in range(2):
                counter.clock = 1
                await counter.wait(zdc.Time.ns(5))
                counter.clock = 0
                await counter.wait(zdc.Time.ns(5))
            counter.reset = 0
            counter.enable = 1
            for _ in range(10):
                counter.clock = 1
                await counter.wait(zdc.Time.ns(5))
                counter.clock = 0
                await counter.wait(zdc.Time.ns(5))
            assert counter.count == 10
    """
    return SimulateContext(cls, *args, vcd=vcd, **kwargs)
