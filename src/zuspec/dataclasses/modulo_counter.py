"""ModuloCounter — counts 0..PERIOD-1 and wraps.

Usage::

    @zdc.dataclass
    class MyComp(zdc.Component):
        baud_cnt: zdc.ModuloCounter = zdc.inst(zdc.ModuloCounter, PERIOD=868)

        @zdc.proc
        async def uart_tick(self):
            while True:
                await self.baud_cnt.wait_next()   # fires every 868 cycles
                self.tx = ~self.tx
"""
from __future__ import annotations

import dataclasses as dc

from .counter import Counter
from .decorators import dataclass as _zdcdc, const, proc as _proc


@_zdcdc
class ModuloCounter(Counter):
    """Counter that counts 0 .. PERIOD-1 and wraps.

    Unlike the base :class:`Counter` (whose modulus is ``2**WIDTH``), a
    ``ModuloCounter`` uses ``PERIOD`` as its rollover point.  This avoids
    the power-of-two constraint, making it suitable for frequency dividers,
    baud-rate generators, and similar periodic tasks.

    Parameters
    ----------
    PERIOD:
        Number of cycles per period (rollover point).  Defaults to 256.
    """

    PERIOD: int = const(default=256)

    @property
    def modulus(self) -> int:
        """Rollover point: ``PERIOD`` (overrides ``2**WIDTH``)."""
        return self.PERIOD

    @_proc
    async def on_rollover(self) -> None:
        """Override or bind: called every ``PERIOD`` cycles.

        Default implementation is a no-op; sub-class to react to rollovers
        without creating a separate proc.
        """
        while True:
            await self.wait_next()
