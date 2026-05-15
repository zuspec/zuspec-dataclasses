"""Abstract Memory-Mapped Register (MMR) subsystem for zuspec-dataclasses.

Public API::

    import zuspec.dataclasses as zdc

    # Access types
    zdc.SW, zdc.HW

    # Field descriptor factory + presets
    zdc.reg_field(...)
    zdc.FieldAttr.RW, .RO, .W1S, .W1C, .WO, .Pulse, .StickyBit

    # Declaration decorators
    @zdc.reg(offset=0x00)
    @zdc.regfile

    # Base classes
    zdc.RegisterFile

    # Runtime types
    zdc.WriteHandle
    zdc.RegisterValue   # snapshot returned by reg.read()

    # Bus adapters
    zdc.PassthroughPort

    # Free function
    await zdc.wait_until(reg_a, reg_b, lambda a, b: ...)
"""
from .enums      import SW, HW, RegAcc, OnWrite, OnRead, StickyBit, Precedence
from .descriptor import FieldDescriptor, reg_field, FieldAttr
from .decorators import reg, regfile
from .base       import RegisterFile
from .field_rt   import WriteHandle
from .register_rt import RegisterValue
from .bus        import BusPort, PassthroughPort
from .wait       import wait_until

__all__ = [
    'SW', 'HW', 'RegAcc', 'OnWrite', 'OnRead', 'StickyBit', 'Precedence',
    'FieldDescriptor', 'reg_field', 'FieldAttr',
    'reg', 'regfile',
    'RegisterFile',
    'WriteHandle', 'RegisterValue',
    'BusPort', 'PassthroughPort',
    'wait_until',
]
