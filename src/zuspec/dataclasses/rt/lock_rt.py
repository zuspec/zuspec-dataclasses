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
import dataclasses as dc

@dc.dataclass
class LockRT:
    """Runtime implementation of Lock protocol.
    
    This is a zuspec-aware wrapper around asyncio.Lock that can be
    used in component fields and is properly handled by the data model.
    """
    _lock: asyncio.Lock = dc.field(default_factory=asyncio.Lock)
    
    async def acquire(self):
        """Acquire the lock. Blocks until the lock is available."""
        await self._lock.acquire()
    
    def release(self):
        """Release the lock."""
        self._lock.release()
    
    async def __aenter__(self):
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False
