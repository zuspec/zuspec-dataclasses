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
from typing import TypeVar, Generic, Union, get_args, get_origin
import dataclasses as dc

T = TypeVar('T')

@dc.dataclass
class MemoryRT(Generic[T]):
    """Runtime implementation of Memory type.
    
    Provides direct memory access with read/write methods.
    The memory is implemented as a dictionary for sparse storage.
    """
    _size: int = dc.field()
    _data: dict = dc.field(default_factory=dict)
    _element_type: type = dc.field(default=None)
    _width: int = dc.field(default=32)
    
    def read(self, addr: int) -> T:
        """Read a value from the memory at the specified address.
        
        Args:
            addr: Memory address (element index)
            
        Returns:
            The value at the specified address, or 0 if not written yet
            
        Raises:
            IndexError: If address is out of bounds
        """
        if addr < 0 or addr >= self._size:
            raise IndexError(f"Memory address {addr} out of bounds (size={self._size})")
        
        return self._data.get(addr, 0)
    
    def write(self, addr: int, data: T) -> None:
        """Write a value to the memory at the specified address.
        
        Args:
            addr: Memory address (element index)
            data: Value to write
            
        Raises:
            IndexError: If address is out of bounds
        """
        if addr < 0 or addr >= self._size:
            raise IndexError(f"Memory address {addr} out of bounds (size={self._size})")
        
        # Mask the data to the width of the memory element type
        if self._width < 64:
            mask = (1 << self._width) - 1
            data = data & mask
            
        self._data[addr] = data
    
    # ------------------------------------------------------------------
    # BackdoorMemory protocol
    # ------------------------------------------------------------------

    def read_bytes(self, addr: int, length: int) -> bytes:
        """Read *length* bytes starting at byte address *addr*.

        Converts byte addresses to element indices using ``_width`` as the
        element size in bits.  Works correctly for sub-element and
        cross-element accesses.
        """
        result = bytearray(length)
        element_bytes = self._width // 8
        for i in range(length):
            elem_idx = (addr + i) // element_bytes
            byte_in_elem = (addr + i) % element_bytes
            elem_val = self._data.get(elem_idx, 0)
            result[i] = (elem_val >> (byte_in_elem * 8)) & 0xFF
        return bytes(result)

    def write_bytes(self, addr: int, data: "Union[bytes, bytearray]") -> None:
        """Write *data* bytes starting at byte address *addr*.

        Merges individual bytes into the underlying element storage using a
        read-modify-write on each touched element.
        """
        element_bytes = self._width // 8
        elem_mask = (1 << self._width) - 1 if self._width < 64 else (1 << 64) - 1
        for i, byte_val in enumerate(data):
            elem_idx = (addr + i) // element_bytes
            byte_in_elem = (addr + i) % element_bytes
            existing = self._data.get(elem_idx, 0)
            shift = byte_in_elem * 8
            existing = (existing & ~(0xFF << shift)) | ((byte_val & 0xFF) << shift)
            self._data[elem_idx] = existing & elem_mask

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        """Get the size of the memory (number of elements)."""
        return self._size

    @property
    def width(self) -> int:
        """Get the width of each memory element in bits."""
        return self._width
