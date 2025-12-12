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
from typing import TypeVar, Generic, Dict
import dataclasses as dc

T = TypeVar('T')

@dc.dataclass
class RegRT(Generic[T]):
    """Runtime implementation of Reg type.
    
    Provides async read/write methods for register access.
    """
    _value: int = dc.field(default=0)
    _width: int = dc.field(default=32)
    
    async def read(self) -> T:
        """Read the register value.
        
        Returns:
            The current register value
        """
        return self._value
    
    async def write(self, val: T) -> None:
        """Write the register value.
        
        Args:
            val: Value to write
        """
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
