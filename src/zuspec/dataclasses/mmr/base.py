"""RegisterFile base class: elaboration, bus access, and named register access."""
from __future__ import annotations

from typing import Dict, List, Optional, Callable

from .field_rt import FieldRT
from .register_rt import RegisterRT
from .descriptor import FieldDescriptor


class RegisterFile:
    """Base class for all abstract register files.

    Subclasses must be decorated with :func:`~.decorators.regfile` and contain
    inner classes decorated with :func:`~.decorators.reg`::

        @zdc.regfile
        class MyRegs(zdc.RegisterFile):

            @zdc.reg(offset=0x00)
            class CTRL:
                START: zdc.u1 = zdc.reg_field(singlepulse=True, default=0)

    Instantiate inside a component::

        regs: MyRegs = zdc.regfile()

    After instantiation, registers are accessible by name::

        self.regs.CTRL           # → RegisterRT
        self.regs.CTRL.START     # → int (current value) in comb/sync context
    """

    def __init__(self):
        # Maps are filled by _elaborate()
        self._reg_map:     Dict[int, RegisterRT]  = {}   # offset → RegisterRT
        self._reg_by_name: Dict[str, RegisterRT]  = {}   # attr_name → RegisterRT
        self._bus_port = None
        self._elaborate()

    def _elaborate(self) -> None:
        """Build FieldRT / RegisterRT instances from class-level metadata."""
        reg_classes = getattr(self.__class__, '_mmr_reg_classes', [])
        for attr_name, inner_cls in reg_classes:
            offset = inner_cls._mmr_offset
            width  = inner_cls._mmr_width
            reg_rt = RegisterRT(attr_name, offset, width)
            for fname, fd in inner_cls._mmr_fields:
                field_rt = FieldRT(fd, fname)
                reg_rt._add_field(fname, field_rt, fd.lsb)
            self._reg_map[offset]     = reg_rt
            self._reg_by_name[attr_name] = reg_rt

    # ------------------------------------------------------------------
    # Named register access
    # ------------------------------------------------------------------

    def __getattribute__(self, name: str):
        # Intercept register names before Python finds the inner class definition
        if not name.startswith('_'):
            try:
                by_name = object.__getattribute__(self, '_reg_by_name')
                if name in by_name:
                    return by_name[name]
            except AttributeError:
                pass
        return object.__getattribute__(self, name)

    # ------------------------------------------------------------------
    # Bus interface
    # ------------------------------------------------------------------

    def bus_write(self, offset: int, data: int, strobe: int = 0xF) -> None:
        """Bus-side write to the register at *offset*.

        *strobe* is a byte-enable mask (AXI WSTRB style).  An unknown offset
        is silently ignored in simulation; it is a decode error in RTL.
        """
        reg = self._reg_map.get(offset)
        if reg is None:
            return
        reg.bus_write(data, strobe)

    def bus_read(self, offset: int) -> int:
        """Bus-side read from the register at *offset*; applies onread effects."""
        reg = self._reg_map.get(offset)
        if reg is None:
            return 0
        return reg.bus_read()

    def connect(self, bus_port) -> None:
        """Bind to a bus port.

        The port's ``bind(regfile)`` method is called; after that, the port
        drives :meth:`bus_write` / :meth:`bus_read` automatically.
        """
        self._bus_port = bus_port
        bus_port.bind(self)

    def reset(self) -> None:
        """Restore all fields in all registers to their declared reset values."""
        for reg in self._reg_map.values():
            reg.reset()

    def read_all(self, regs: List[RegisterRT]):
        """Return list of :class:`~.register_rt.RegisterValue` snapshots."""
        return [r.read() for r in regs]
