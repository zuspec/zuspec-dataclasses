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
from typing import TypeVar, Generic, Dict, Type, Optional, get_args
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

@dc.dataclass
class RegFileRT:
    """Runtime implementation of RegFile type.
    
    Contains a collection of registers and provides address-based access.
    """
    _registers: Dict[str, RegRT] = dc.field(default_factory=dict)
    _reg_offsets: Dict[int, str] = dc.field(default_factory=dict)
    _size: int = dc.field(default=0)
    
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
    
    def read(self, addr: int) -> int:
        """Read from a register at the given byte offset.
        
        Args:
            addr: Byte address (offset) within the register file
            
        Returns:
            Register value
            
        Raises:
            RuntimeError: If address doesn't map to a register
        """
        if addr not in self._reg_offsets:
            raise RuntimeError(f"No register at offset 0x{addr:x} in register file")
        
        reg_name = self._reg_offsets[addr]
        reg = self._registers[reg_name]
        return reg._value
    
    def write(self, addr: int, data: int) -> None:
        """Write to a register at the given byte offset.
        
        Args:
            addr: Byte address (offset) within the register file
            data: Value to write
            
        Raises:
            RuntimeError: If address doesn't map to a register
        """
        if addr not in self._reg_offsets:
            raise RuntimeError(f"No register at offset 0x{addr:x} in register file")
        
        reg_name = self._reg_offsets[addr]
        reg = self._registers[reg_name]
        
        if reg._width < 64:
            mask = (1 << reg._width) - 1
            reg._value = data & mask
        else:
            reg._value = data
    
    @property
    def size(self) -> int:
        """Get the size of the register file in bytes."""
        return self._size
    
    @property
    def width(self) -> int:
        """Get the width of register access (always 32 for now)."""
        return 32
