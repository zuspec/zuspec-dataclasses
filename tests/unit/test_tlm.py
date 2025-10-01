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
import pytest
import zuspec.dataclasses as zdc
import zuspec.dataclasses.api as api
from typing import Awaitable, Callable, Self

def test_producer_consumer():
    
    @zdc.dataclass
    class Producer(zdc.Component):
        dat_o : Callable[[int],Awaitable] = zdc.port()
        dat_i : Callable[[int],Awaitable] = zdc.export(bind=zdc.bind[Self](lambda s:s.recv))
        _recv_ev : zdc.Event = zdc.field(default_factory=zdc.Event)

        async def recv(self, dat):
            self._recv_ev.set(dat)
            pass

        @zdc.process
        async def run(self):
            for i in range(20):
                await self.dat_o(i)
                dat_i = await self._recv_ev.wait()
                self._recv_ev.clear()

    @zdc.dataclass
    class Consumer(zdc.Component):
        dat_o : Callable[[int],Awaitable] = zdc.port()
        dat_i : Callable[[int],Awaitable] = zdc.export(bind=zdc.bind[Self](lambda s:s.recv))

        async def recv(self, dat):
            await self.dat_o(dat)


    @zdc.dataclass
    class Top(zdc.Component):
        p : Producer = zdc.field(bind=zdc.bind[Self](lambda s: {
            s.p.dat_i : s.c.dat_o
        }))
        c : Consumer = zdc.field(bind=zdc.bind[Self](lambda s: {
            s.c.dat_i : s.p.dat_o
        }))
