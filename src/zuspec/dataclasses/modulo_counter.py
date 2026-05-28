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

    @classmethod
    def elaborate_field(
        cls,
        field_name: str,
        field_index: int,
        inst_kwargs: dict,
        element_type=None,
    ):
        """Build an ``AbstractionFieldIR`` for a ``ModuloCounter`` field.

        Reads ``PERIOD`` from *inst_kwargs* (default 256).  The register width
        is chosen as the minimum number of bits to represent ``PERIOD - 1``.
        """
        from .counter_ir import CounterIR
        from zuspec.ir.core.abstraction_field_ir import AbstractionFieldIR
        period = int(inst_kwargs.get("PERIOD", 256))
        width = max(1, (period - 1).bit_length()) if period > 1 else 1
        ir_node = CounterIR(width=width, period=period, is_free_running=True)
        return AbstractionFieldIR(
            spec_type_name=cls.__name__,
            field_name=field_name,
            field_index=field_index,
            py_cls=cls,
            inst_kwargs=inst_kwargs,
            ir_node=ir_node,
        )

    @_proc
    async def on_rollover(self) -> None:
        """Override or bind: called every ``PERIOD`` cycles.

        Default implementation is a no-op; sub-class to react to rollovers
        without creating a separate proc.
        """
        while True:
            await self.wait_next()
