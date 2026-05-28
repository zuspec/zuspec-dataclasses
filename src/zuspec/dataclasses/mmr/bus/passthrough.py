"""PassthroughPort — synchronous bus adapter for tests and SW drivers."""
from __future__ import annotations

from .base import BusPort


class PassthroughPort(BusPort):
    """Synchronous read/write adapter; routes directly to the register file.

    Suitable for software-driver tests and any context where bus transactions
    are modelled as synchronous function calls rather than timed protocol
    transactions.

    Example::

        port = zdc.PassthroughPort()
        regs.connect(port)
        port.write(0x04, 0x2)          # bus write
        value = port.read(0x04)        # bus read
    """

    def __init__(self):
        self._regfile = None

    def bind(self, regfile) -> None:
        self._regfile = regfile

    def read(self, offset: int) -> int:
        """Synchronous bus-side read."""
        assert self._regfile is not None, "PassthroughPort not bound"
        return self._regfile.bus_read(offset)

    def write(self, offset: int, data: int, strobe: int = 0xF) -> None:
        """Synchronous bus-side write."""
        assert self._regfile is not None, "PassthroughPort not bound"
        self._regfile.bus_write(offset, data, strobe)
