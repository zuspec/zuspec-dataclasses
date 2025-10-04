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
import asyncio
import zuspec.dataclasses as zdc
from typing import Self

def test_analysis():
    @zdc.dataclass
    class MyC(zdc.Component):
        clock : zdc.Bit = zdc.input()
        reset : zdc.Bit = zdc.input()
        count : zdc.Bit[16] = zdc.output()

        @zdc.sync(clock=lambda s:s.clock, reset=lambda s:s.reset)
        def _inc(self):
            if self.reset:
                self.count = 0
            else:
                self.count += 3

    tb = TimebaseRoot()
    impl = BuildImpl(tb).build(MyC)

    def clock(count=1):
        nonlocal tb, impl
        for _ in range(count):
            impl.clock = 1
            asyncio.run(tb.wait(10, -9))
            impl.clock = 0
            asyncio.run(tb.wait(10, -9))

    # Simple(istic) testbench
    impl.clock = 0
    impl.reset = 1
    asyncio.run(tb.wait(10, -9))
    impl.reset = 0
    asyncio.run(tb.wait(10, -9))

    clock(10)
    print("Count: %d" % impl.count)

    impl.reset = 1
    clock(10)
    impl.reset = 0

    print("Count: %d" % impl.count)

def test_analysis2():
    @zdc.dataclass
    class MyC(zdc.Component):
        clock : zdc.Bit = zdc.input()
        reset : zdc.Bit = zdc.input()
        count : zdc.Bit[16] = zdc.output()
        value : int = zdc.output()

        @zdc.sync(clock=lambda s:s.clock, reset=lambda s:s.reset)
        def _inc(self):
            if self.reset:
                self.count = 0
            else:
                self.count += 3
                self.count += 3

    tb = TimebaseRoot()
    impl = BuildImpl(tb).build(MyC)

    def clock(count=1):
        nonlocal tb, impl
        for _ in range(count):
            impl.clock = 1
            asyncio.run(tb.wait(10, -9))
            impl.clock = 0
            asyncio.run(tb.wait(10, -9))

    # Simple(istic) testbench
    impl.clock = 0
    impl.reset = 1
    asyncio.run(tb.wait(10, -9))
    impl.reset = 0
    asyncio.run(tb.wait(10, -9))

    clock(10)
    print("Count: %d" % impl.count)

    impl.reset = 1
    clock(10)
    impl.reset = 0

    print("Count: %d" % impl.count)

def test_analysis3():
    @zdc.dataclass
    class MyC(zdc.Component):
        clock : zdc.Bit = zdc.input()
        reset : zdc.Bit = zdc.input()
        count : zdc.Bit[16] = zdc.output()
        value : int = zdc.output()

        @zdc.sync(clock=lambda s:s.clock, reset=lambda s:s.reset)
        def _inc(self):
            if self.reset:
                self.count = 0
            else:
                self.count += 3
                self.count += 3

    @zdc.dataclass
    class Consumer(zdc.Component):
        clock : zdc.Bit = zdc.input()
        reset : zdc.Bit = zdc.input()
        count : zdc.Bit = zdc.input()

        @zdc.sync(clock=lambda s:s.clock, reset=lambda s:s.reset)
        def _mon(self):
            if self.reset == 0:
                print("count: %d" % self.count)

    @zdc.dataclass
    class Top(zdc.Component):
        clock : zdc.Bit = zdc.input()
        reset : zdc.Bit = zdc.input()
        counter : MyC = zdc.field(bind=zdc.bind[Self](lambda s: {
            s.counter.clock : s.clock,
            s.counter.reset : s.reset
        }))
        monitor : Consumer = zdc.field(bind=zdc.bind[Self](lambda s: {
            s.monitor.clock : s.clock,
            s.monitor.reset : s.reset,
            s.monitor.count : s.counter.count
        }))

    tb = TimebaseRoot()
    impl = BuildImpl(tb).build(Top)

    def clock(count=1):
        nonlocal tb, impl
        for _ in range(count):
            impl.clock = 1
            asyncio.run(tb.wait(10, -9))
            impl.clock = 0
            asyncio.run(tb.wait(10, -9))

    # Simple(istic) testbench
    impl.clock = 0
    impl.reset = 1
    asyncio.run(tb.wait(10, -9))
    impl.reset = 0
    asyncio.run(tb.wait(10, -9))

    clock(10)
    print("Count: %d" % impl.monitor.count)

    impl.reset = 1
    clock(10)
    impl.reset = 0

    print("Count: %d" % impl.monitor.count)





def test_analysis4():
    @zdc.dataclass
    class MyC(zdc.Component):
        clock : zdc.Bit = zdc.input()
        reset : zdc.Bit = zdc.input()
        count : zdc.Bit[16] = zdc.output()
        value : int = zdc.output()

        @zdc.sync(clock=lambda s:s.clock, reset=lambda s:s.reset)
        def _inc(self):
            if self.reset:
                self.count = 0
            else:
                self.count -= 1
                self.count += 1

    @zdc.dataclass
    class Consumer(zdc.Component):
        clock : zdc.Bit = zdc.input()
        reset : zdc.Bit = zdc.input()
        count : zdc.Bit[16] = zdc.input()
        result : zdc.Bit[16] = zdc.output()

        @zdc.sync(clock=lambda s:s.clock, reset=lambda s:s.reset)
        def _mon(self):
            if self.reset == 0:
                print("count: %d" % self.count)

        @zdc.comb()
        def _mod(self):
            if self.count < 5:
                self.result = self.count
            else:
                self.result = self.count - 5

    @zdc.dataclass
    class Top(zdc.Component):
        clock : zdc.Bit = zdc.input()
        reset : zdc.Bit = zdc.input()
        counter : MyC = zdc.field(bind=zdc.bind[Self](lambda s: {
            s.counter.clock : s.clock,
            s.counter.reset : s.reset
        }))
        monitor : Consumer = zdc.field(bind=zdc.bind[Self](lambda s: {
            s.monitor.clock : s.clock,
            s.monitor.reset : s.reset,
            s.monitor.count : s.counter.count
        }))

    tb = zdc.std.TimeBase()
    f = zdc.api.FactoryExec()
    impl = f.build(Top)

    def clock(count=1):
        nonlocal tb, impl
        for _ in range(count):
            impl.clock = 1
            asyncio.run(tb.wait(10, -9))
            impl.clock = 0
            asyncio.run(tb.wait(10, -9))

    # Simple(istic) testbench
    impl.clock = 0
    impl.reset = 1
    asyncio.run(tb.wait(10, -9))
    impl.reset = 0
    asyncio.run(tb.wait(10, -9))

    clock(10)
    print("Count: %d" % impl.monitor.count)
    print("Result: %d" % impl.monitor.result)

    impl.reset = 1
    clock(10)
    impl.reset = 0

    print("Count: %d" % impl.monitor.count)
    print("Result: %d" % impl.monitor.result)
