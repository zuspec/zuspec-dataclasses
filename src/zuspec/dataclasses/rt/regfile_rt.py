#****************************************************************************
# Copyright 2019-2025 Matthew Ballance and contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#****************************************************************************
from __future__ import annotations
import asyncio
from typing import TypeVar, Generic, Dict, Type, Optional, Any, get_args
import dataclasses as dc

T = TypeVar('T')

def unpack_int_to_struct(value: int, struct_type: Type) -> object:
    """Unpack an integer value into a packed struct instance.
    
    Args:
        value: Integer value containing packed fields
        struct_type: The PackedStruct type to unpack into
        
    Returns:
        An instance of struct_type with fields extracted from value
    """
    from ..types import U, S
    
    # Create instance using object.__new__ to bypass TypeBase.__new__
    instance = object.__new__(struct_type)
    
    # Get all fields and extract their bit values
    bit_offset = 0
    
    for field in dc.fields(struct_type):
        # Get field width from metadata
        width = 32  # default
        field_type = field.type
        
        # Check if type has __metadata__ (for Annotated types)
        if hasattr(field_type, '__metadata__'):
            for item in field_type.__metadata__:
                if isinstance(item, (U, S)):
                    width = item.width
                    break
        # Check for get_args (for newer style annotations)
        elif hasattr(field_type, '__args__'):
            args = get_args(field_type)
            if args:
                for item in args:
                    if isinstance(item, (U, S)):
                        width = item.width
                        break
        
        # Extract the field value from the packed integer
        mask = (1 << width) - 1
        field_value = (value >> bit_offset) & mask
        setattr(instance, field.name, field_value)
        bit_offset += width
    
    return instance

@dc.dataclass
class RegRT(Generic[T]):
    """Runtime implementation of Reg type.
    
    Provides async read/write methods for register access.
    """
    _value: int = dc.field(default=0)
    _width: int = dc.field(default=32)
    _element_type: Optional[Type] = dc.field(default=None)
    _write_event: asyncio.Event = dc.field(default_factory=asyncio.Event)

    async def wait_written(self) -> None:
        """Suspend until the next time this register is written.

        Zero simulation time — purely event-driven.  Useful for hardware
        processes that want to wait for software to program a register without
        burning simulation cycles in a polling loop.
        """
        self._write_event.clear()
        await self._write_event.wait()

    async def when(self, cond) -> None:
        """Suspend until *cond(value)* is true.

        Re-checks the condition immediately (in case it is already satisfied),
        then waits for each successive write and re-evaluates.
        """
        while True:
            val = await self.read()
            if cond(val):
                return
            self._write_event.clear()
            await self._write_event.wait()

    async def read(self) -> T:
        """Read the register value.
        
        Returns:
            The current register value (unpacked if element_type is a PackedStruct)
        """
        from ..types import PackedStruct
        import inspect
        
        # If element type is a PackedStruct, unpack the value
        if self._element_type is not None and inspect.isclass(self._element_type) and issubclass(self._element_type, PackedStruct):
            return unpack_int_to_struct(self._value, self._element_type)
        
        return self._value
    
    async def write(self, val: T) -> None:
        """Write the register value.
        
        Args:
            val: Value to write (can be int or PackedStruct)
        """
        from ..types import PackedStruct
        
        # If val is a PackedStruct, convert it to int
        if isinstance(val, PackedStruct):
            # Pack the struct fields into an integer
            int_val = 0
            bit_offset = 0
            
            for field in dc.fields(type(val)):
                field_value = getattr(val, field.name)
                int_val |= (field_value << bit_offset)
                
                # Get field width
                from ..types import U, S
                width = 32
                field_type = field.type
                if hasattr(field_type, '__metadata__'):
                    for item in field_type.__metadata__:
                        if isinstance(item, (U, S)):
                            width = item.width
                            break
                elif hasattr(field_type, '__args__'):
                    args = get_args(field_type)
                    if args:
                        for item in args:
                            if isinstance(item, (U, S)):
                                width = item.width
                                break
                
                bit_offset += width
            val = int_val
        
        if self._width < 64:
            mask = (1 << self._width) - 1
            self._value = val & mask
        else:
            self._value = val
        self._write_event.set()

@dc.dataclass
class RegProcRT(Generic[T]):
    """Runtime register for standalone Reg[T] fields on @proc Components.

    read() is synchronous (unlike RegRT which is async).
    write() commits the value and ticks the component's internal cycle clock,
    advancing simulation time by one cycle per call.
    """
    _value: int = dc.field(default=0)
    _width: int = dc.field(default=32)
    _comp_impl: Any = dc.field(default=None)  # CompImplRT, injected after construction

    def read(self) -> T:
        """Synchronous register read — returns current committed value."""
        return self._value

    async def write(self, val: T) -> None:
        """Write value and advance one internal cycle.

        Applies width masking, then ticks the component's cycle counter so
        that external observers waiting via wait_cycles() are unblocked.
        """
        if self._width < 64:
            mask = (1 << self._width) - 1
            self._value = int(val) & mask
        else:
            self._value = int(val)
        if self._comp_impl is not None:
            await self._comp_impl.tick_cycle()
        else:
            await asyncio.sleep(0)  # yield even without comp_impl


@dc.dataclass
class RegFileRT:
    """Runtime implementation of RegFile type.
    
    Contains a collection of registers and provides address-based access.
    Supports nested child RegFileRT instances (for sub-RegFile fields) and
    lists of child RegFileRT instances (for replicated sub-RegFile fields).
    """
    _registers: Dict[str, RegRT] = dc.field(default_factory=dict)
    _reg_offsets: Dict[int, str] = dc.field(default_factory=dict)
    _size: int = dc.field(default=0)
    # child sub-regfiles: list of (base_offset, end_offset, RegFileRT)
    _children: List = dc.field(default_factory=list)

    def add_register(self, name: str, reg: RegRT, offset: int) -> None:
        """Add a register to the register file.
        
        Args:
            name: Register field name
            reg: Register runtime instance
            offset: Byte offset of register in address space
        """
        self._registers[name] = reg
        self._reg_offsets[offset] = name
        # Update size to cover all registers (assuming 4-byte registers)
        max_offset = offset + (reg._width // 8)
        if max_offset > self._size:
            self._size = max_offset

    def add_child(self, base_offset: int, child: "RegFileRT") -> None:
        """Register a child RegFileRT at a given base offset.

        Used to support nested RegFile fields (including replicated arrays).
        The parent's read/write will delegate to children when the address
        falls within [base_offset, base_offset + child.size).
        """
        self._children.append((base_offset, base_offset + child.size, child))
        total = base_offset + child.size
        if total > self._size:
            self._size = total

    def _find_child(self, addr: int):
        """Return (child, relative_addr) if *addr* maps into a child, else None."""
        for base, end, child in self._children:
            if base <= addr < end:
                return child, addr - base
        return None, None

    def read(self, addr: int) -> int:
        """Read from a register at the given byte offset."""
        # Delegate to child if applicable
        child, rel = self._find_child(addr)
        if child is not None:
            return child.read(rel)

        if addr not in self._reg_offsets:
            raise RuntimeError(f"No register at offset 0x{addr:x} in register file")
        
        reg_name = self._reg_offsets[addr]
        reg = self._registers[reg_name]
        return reg._value
    
    def write(self, addr: int, data: int) -> None:
        """Write to a register at the given byte offset."""
        # Delegate to child if applicable
        child, rel = self._find_child(addr)
        if child is not None:
            child.write(rel, data)
            return

        if addr not in self._reg_offsets:
            raise RuntimeError(f"No register at offset 0x{addr:x} in register file")
        
        reg_name = self._reg_offsets[addr]
        reg = self._registers[reg_name]
        
        if reg._width < 64:
            mask = (1 << reg._width) - 1
            reg._value = data & mask
        else:
            reg._value = data
        reg._write_event.set()
    
    @property
    def size(self) -> int:
        """Get the size of the register file in bytes."""
        return self._size
    
    @property
    def width(self) -> int:
        """Get the width of register access (always 32 for now)."""
        return 32

    async def wait(self, regs: list, cond) -> list:
        """Suspend until *cond(values)* is true for the given list of Reg objects.

        Re-checks immediately (in case already satisfied), then races on write
        events — waking when any register is written and re-evaluating.
        Zero simulation time: no timebase cycles are consumed.

        Returns the list of register values that satisfied the condition, so the
        caller can use them directly without a second ``read_all`` call.

        Example::

            ctrls = await self.regs.wait(
                [self.regs.ch[i].ctrl for i in range(N_CHAN)],
                lambda vals: any(v.en for v in vals),
            )
            active_idx = next((i for i, v in enumerate(ctrls) if v.en), -1)
        """
        while True:
            vals = [await r.read() for r in regs]
            if cond(vals):
                return vals
            # Clear events then race-wait: first write wakes us up
            for r in regs:
                r._write_event.clear()
            write_tasks = [
                asyncio.ensure_future(r._write_event.wait()) for r in regs
            ]
            await asyncio.wait(write_tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in write_tasks:
                t.cancel()
    async def read_all(self, regs: list) -> list:
        """Read all registers in *regs* and return their values as a list.

        Reads are issued in order (hardware permitting parallel access in a
        later implementation).  The result can be processed with standard
        Python idioms::

            ctrls = await self.regs.read_all(
                [self.regs.ch[i].ctrl for i in range(N_CHAN)]
            )
            active_idx = next((i for i, v in enumerate(ctrls) if v.en), -1)
        """
        return [await r.read() for r in regs]


# --------------------------------------------------------------------------- #

@dc.dataclass
class MirrorRegRT(Generic[T]):
    """A register mirror that routes reads/writes through a zdc.MemIF bus.

    Each instance represents one register at *_offset* bytes from the base of
    the mirror's bus.  The bus is injected by ``RegFileMirrorRT.bind_bus()``.

    Packing/unpacking of PackedStruct values mirrors ``RegRT`` exactly so that
    the caller sees the same types whether it is using a physical RegRT or a
    software-side MirrorRegRT.
    """
    _offset: int = dc.field(default=0)
    _width: int = dc.field(default=32)
    _element_type: Optional[Type] = dc.field(default=None)
    _bus: object = dc.field(default=None)   # zdc.MemIF (read32/write32)

    async def read(self) -> T:
        assert self._bus is not None, "MirrorRegRT: bus not bound"
        raw = await self._bus.read32(self._offset)
        from ..types import PackedStruct
        import inspect
        if (self._element_type is not None
                and inspect.isclass(self._element_type)
                and issubclass(self._element_type, PackedStruct)):
            return unpack_int_to_struct(raw, self._element_type)
        return raw

    async def write(self, val: T) -> None:
        assert self._bus is not None, "MirrorRegRT: bus not bound"
        from ..types import PackedStruct
        if isinstance(val, PackedStruct):
            int_val = 0
            bit_offset = 0
            from ..types import U, S
            for field in dc.fields(type(val)):
                field_value = getattr(val, field.name)
                int_val |= (field_value << bit_offset)
                width = 32
                ft = field.type
                if hasattr(ft, '__metadata__'):
                    for item in ft.__metadata__:
                        if isinstance(item, (U, S)):
                            width = item.width
                            break
                elif hasattr(ft, '__args__'):
                    from typing import get_args as _ga
                    for item in _ga(ft):
                        if isinstance(item, (U, S)):
                            width = item.width
                            break
                bit_offset += width
            val = int_val
        if self._width < 64:
            val = val & ((1 << self._width) - 1)
        await self._bus.write32(self._offset, val)


@dc.dataclass
class RegFileMirrorRT:
    """Software-side mirror of a RegFile hierarchy.

    Structure is identical to ``RegFileRT`` (same attribute names and list
    layout) but leaf nodes are ``MirrorRegRT`` instances that issue bus
    transactions rather than accessing local state.

    Call ``bind_bus(bus)`` once the zdc.MemIF port is resolved to propagate
    the bus reference to every leaf register.
    """
    _leaves: list = dc.field(default_factory=list)   # flat list of MirrorRegRT
    _size: int = dc.field(default=0)

    def bind_bus(self, bus: object) -> None:
        """Inject the zdc.MemIF bus into every leaf MirrorRegRT."""
        for leaf in self._leaves:
            leaf._bus = bus

    def _add_leaf(self, reg: "MirrorRegRT") -> None:
        self._leaves.append(reg)
        end = reg._offset + (reg._width // 8)
        if end > self._size:
            self._size = end

    @property
    def size(self) -> int:
        return self._size

