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
import dataclasses as dc
from typing import List, Tuple, Any
from .addr_handle_rt import AddrHandleRT
from .memory_rt import MemoryRT
from .regfile_rt import RegFileRT

@dc.dataclass
class AddressSpaceRT:
    """Runtime implementation of AddressSpace.
    
    Maps address ranges to storage (Memory instances).
    """
    mmap: List[Tuple[int, int, Any]] = dc.field(default_factory=list)
    base: AddrHandleRT = dc.field(default=None)
    
    def __post_init__(self):
        if self.base is None:
            self.base = AddrHandleRT(_aspace=self, _base_addr=0)
    
    def add_mapping(self, base_addr: int, storage: Any) -> None:
        """Add a storage mapping at the specified base address.
        
        Args:
            base_addr: Base address where storage is mapped
            storage: Storage object (MemoryRT or RegFileRT instance)
        """
        if isinstance(storage, MemoryRT):
            size = storage.size * (storage.width // 8)
            self.mmap.append((base_addr, size, storage))
            self.mmap.sort(key=lambda x: x[0])
        elif isinstance(storage, RegFileRT):
            size = storage.size
            self.mmap.append((base_addr, size, storage))
            self.mmap.sort(key=lambda x: x[0])
    
    def _find_storage(self, addr: int, size: int) -> Tuple[Any, int]:
        """Find storage for the given address and size.
        
        Args:
            addr: Address to access
            size: Size of access in bytes
            
        Returns:
            Tuple of (storage, offset_in_storage)
            
        Raises:
            RuntimeError: If address is not mapped
        """
        for base_addr, region_size, storage in self.mmap:
            if base_addr <= addr < base_addr + region_size:
                if addr + size > base_addr + region_size:
                    raise RuntimeError(
                        f"Access at 0x{addr:x} size {size} crosses region boundary at 0x{base_addr + region_size:x}"
                    )
                offset = addr - base_addr
                return storage, offset
        
        raise RuntimeError(
            f"Address 0x{addr:x} is not mapped in address space"
        )
    
    async def read(self, addr: int, size: int) -> int:
        """Read from the address space.
        
        Args:
            addr: Address to read from
            size: Size in bytes (1, 2, 4, or 8)
            
        Returns:
            Value read
            
        Raises:
            RuntimeError: If address is not mapped
        """
        storage, offset = self._find_storage(addr, size)
        
        if isinstance(storage, MemoryRT):
            element_size_bytes = storage.width // 8
            element_index = offset // element_size_bytes
            byte_offset = offset % element_size_bytes
            
            if size == element_size_bytes and byte_offset == 0:
                return storage.read(element_index)
            else:
                value = 0
                for i in range(size):
                    byte_addr = offset + i
                    elem_idx = byte_addr // element_size_bytes
                    byte_in_elem = byte_addr % element_size_bytes
                    elem_val = storage.read(elem_idx)
                    byte_val = (elem_val >> (byte_in_elem * 8)) & 0xFF
                    value |= (byte_val << (i * 8))
                return value
        elif isinstance(storage, RegFileRT):
            return storage.read(offset)
        
        raise RuntimeError(f"Unsupported storage type: {type(storage)}")
    
    async def write(self, addr: int, data: int, size: int) -> None:
        """Write to the address space.
        
        Args:
            addr: Address to write to
            data: Value to write
            size: Size in bytes (1, 2, 4, or 8)
            
        Raises:
            RuntimeError: If address is not mapped
        """
        storage, offset = self._find_storage(addr, size)
        
        if isinstance(storage, MemoryRT):
            element_size_bytes = storage.width // 8
            element_index = offset // element_size_bytes
            byte_offset = offset % element_size_bytes
            
            if size == element_size_bytes and byte_offset == 0:
                storage.write(element_index, data)
            else:
                for i in range(size):
                    byte_addr = offset + i
                    elem_idx = byte_addr // element_size_bytes
                    byte_in_elem = byte_addr % element_size_bytes
                    byte_val = (data >> (i * 8)) & 0xFF
                    
                    elem_val = storage.read(elem_idx)
                    mask = ~(0xFF << (byte_in_elem * 8))
                    new_val = (elem_val & mask) | (byte_val << (byte_in_elem * 8))
                    storage.write(elem_idx, new_val)
        elif isinstance(storage, RegFileRT):
            storage.write(offset, data)
        else:
            raise RuntimeError(f"Unsupported storage type: {type(storage)}")
