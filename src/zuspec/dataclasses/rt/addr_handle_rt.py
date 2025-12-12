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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .address_space_rt import AddressSpaceRT

@dc.dataclass
class AddrHandleRT:
    """Runtime implementation of AddrHandle.
    
    Provides async read/write methods that map addresses to storage.
    """
    _aspace: 'AddressSpaceRT' = dc.field()
    _base_addr: int = dc.field(default=0)
    
    async def read8(self, addr: int) -> int:
        """Read an 8-bit value from the address space."""
        return await self._aspace.read(self._base_addr + addr, 1)
    
    async def read16(self, addr: int) -> int:
        """Read a 16-bit value from the address space."""
        return await self._aspace.read(self._base_addr + addr, 2)
    
    async def read32(self, addr: int) -> int:
        """Read a 32-bit value from the address space."""
        return await self._aspace.read(self._base_addr + addr, 4)
    
    async def read64(self, addr: int) -> int:
        """Read a 64-bit value from the address space."""
        return await self._aspace.read(self._base_addr + addr, 8)
    
    async def write8(self, addr: int, data: int) -> None:
        """Write an 8-bit value to the address space."""
        await self._aspace.write(self._base_addr + addr, data, 1)
    
    async def write16(self, addr: int, data: int) -> None:
        """Write a 16-bit value to the address space."""
        await self._aspace.write(self._base_addr + addr, data, 2)
    
    async def write32(self, addr: int, data: int) -> None:
        """Write a 32-bit value to the address space."""
        await self._aspace.write(self._base_addr + addr, data, 4)
    
    async def write64(self, addr: int, data: int) -> None:
        """Write a 64-bit value to the address space."""
        await self._aspace.write(self._base_addr + addr, data, 8)
