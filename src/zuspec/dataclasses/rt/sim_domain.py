"""SimDomain — high-level testbench interface for a single clock/reset domain.

Typical usage::

    @zdc.dataclass
    class Counter(zdc.Component):
        clock_domain = zdc.ClockDomain(period=zdc.Time.ns(10))
        reset_domain = zdc.ResetDomain()

        count : zdc.bit32 = zdc.output(reset=0)
        enable : zdc.bit  = zdc.input()

        @zdc.sync
        def _count(self):
            if self.enable:
                self.count = self.count + 1

    async def run():
        async with zdc.simulate(Counter) as c:
            await c.domain.reset(cycles=2)
            c.enable = 1
            await c.domain.tick(5)
            assert c.count == 5
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Callable, Optional, Any

if TYPE_CHECKING:
    from ..types import Component


class SimDomain:
    """High-level testbench interface for a single clock domain.

    Acquired automatically from :func:`~zuspec.dataclasses.simulate` when
    the root component declares class-level ``clock_domain``/``reset_domain``
    attributes::

        async with zdc.simulate(Counter) as c:
            await c.domain.reset(cycles=2)
            c.enable = 1
            await c.domain.tick(5)
            assert c.count == 5

    For multi-domain components the named domains are also exposed::

        async with zdc.simulate(RxTxBridge) as c:
            await c.rx_domain.tick(4)
            await c.tx_domain.tick(2)
    """

    def __init__(self, comp: "Component", domain_obj: Optional[Any] = None) -> None:
        self._comp = comp
        self._domain_obj = domain_obj  # ClockDomain instance or None (= default domain)

    async def tick(self, n: int = 1) -> None:
        """Advance *n* rising edges on this domain.

        Each call triggers all ``@zdc.sync`` methods that are bound to this
        domain (or to the component's default domain when *domain_obj* is
        ``None``).  Deferred writes are committed after each edge.
        """
        for _ in range(n):
            self._comp._impl.domain_clock_edge(self._comp)
            # Yield to the event loop so async processes can run between ticks.
            await asyncio.sleep(0)

    async def reset(self, cycles: int = 2) -> None:
        """Assert reset for *cycles* rising edges, then deassert.

        The reset signal (if any) is driven to its active level, the clock is
        advanced for *cycles* edges, then reset is deasserted and one more
        clock edge is applied so the DUT can exit reset cleanly.

        Fields that declare ``output(reset=N)`` / ``reg(reset=N)`` are forced
        to their reset values *after every tick during the reset window*, so
        the reset state is always stable regardless of what the sync body does.
        """
        self._set_reset_pin(True)
        for _ in range(cycles):
            await self.tick(1)
            self._apply_reset_values()  # enforce reset state after sync body runs
        self._set_reset_pin(False)
        # One clean edge after reset
        await self.tick(1)

    async def pulse_reset(self) -> None:
        """Single-cycle reset pulse (equivalent to ``reset(cycles=1)``)."""
        await self.reset(cycles=1)

    async def wait_until(
        self,
        predicate: Callable[["Component"], bool],
        *,
        timeout_cycles: Optional[int] = None,
    ) -> None:
        """Advance one cycle at a time until *predicate(component)* is ``True``.

        Args:
            predicate: Callable that receives the component and returns ``True``
                when the desired condition is met.
            timeout_cycles: If set, raises :class:`TimeoutError` after this
                many cycles if the predicate has not fired.

        Raises:
            TimeoutError: When *timeout_cycles* is set and the predicate never
                returns ``True`` within that many cycles.
        """
        count = 0
        while not predicate(self._comp):
            if timeout_cycles is not None and count >= timeout_cycles:
                raise TimeoutError(
                    f"Predicate not met within {timeout_cycles} cycle(s)"
                )
            await self.tick(1)
            count += 1

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _active_level(self) -> tuple:
        """Return (assert_level, deassert_level) for the reset pin."""
        reset_domain = getattr(type(self._comp), 'reset_domain', None)
        active_low = True
        if reset_domain is not None:
            try:
                from ..domain import ResetDomain
                if isinstance(reset_domain, ResetDomain):
                    active_low = (reset_domain.polarity == "active_low")
            except ImportError:
                pass
        return (0, 1) if active_low else (1, 0)

    def _set_reset_pin(self, active: bool) -> None:
        """Drive the reset pin to its active or inactive level."""
        assert_lvl, deassert_lvl = self._active_level()
        level = assert_lvl if active else deassert_lvl
        for candidate in ('reset', 'rst_n', 'rst', 'nreset'):
            if hasattr(self._comp, candidate):
                try:
                    object.__setattr__(self._comp, candidate, level)
                    return
                except Exception:
                    pass

    def _apply_reset_values(self) -> None:
        """Force all fields with a declared ``reset_value`` to that value.

        Reads ``output(reset=N)`` / ``reg(reset=N)`` metadata from the
        Python dataclass fields and writes the values directly so the
        component's state reflects the reset condition even when the sync
        body does not contain an explicit ``if self.reset:`` check.
        """
        import dataclasses as _dc
        if not _dc.is_dataclass(self._comp):
            return
        for f in _dc.fields(self._comp):
            rv = (f.metadata or {}).get("reset")
            if rv is not None:
                try:
                    object.__setattr__(self._comp, f.name, int(rv))
                except Exception:
                    pass

    def _assert_reset(self, active: bool) -> None:
        """Convenience wrapper: set pin and apply field reset values when active."""
        self._set_reset_pin(active)
        if active:
            self._apply_reset_values()
