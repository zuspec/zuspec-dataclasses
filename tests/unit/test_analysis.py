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
import abc
import asyncio
import dataclasses as dc
import pytest
import zuspec.dataclasses as zdc
from typing import Protocol, Self

class Timebase(Protocol):

    @abc.abstractmethod
    async def wait(self, time : int, units : int=0): ...

@dc.dataclass
class ExecFactory(Protocol):

    @abc.abstractmethod
    def build[T](self, t : T) -> T: ...

def test_analysis():

    def inner():
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
    
        tb = Timebase()
        impl = ExecFactory(tb).build(MyC)
    
        async def clock(count=1):
            nonlocal tb, impl
            for _ in range(count):
                impl.clock = 1
                asyncio.run(tb.wait(10, -9))
                impl.clock = 0
                asyncio.run(tb.wait(10, -9))

        async def run():
            nonlocal impl

            # Simple(istic) testbench
            impl.clock = 0
            impl.reset = 1
            await tb.wait(10, -9)
            impl.reset = 0
            await tb.wait(10, -9)
    
            await clock(10)
            print("Count: %d" % impl.count)
    
            impl.reset = 1
            await clock(10)
            impl.reset = 0
    
            print("Count: %d" % impl.count)

    # run_test(
    #     src_elems=[Timebase, ExecFactory, inner],
    #     model="github/gpt-4.1",
    #     expect=[
    #         "Count: 30",
    #         "Count: 0",
    #     ])


def run_test(src_elems, model, expect):
    import json
    import litellm
    import os
    import inspect

    tests_unit_dir = os.path.dirname(os.path.abspath(__file__))
    pkg_dir = os.path.abspath(os.path.join(tests_unit_dir, "../../src/zuspec/dataclasses"))
    with open(os.path.join(pkg_dir, "llms.txt"), "r") as fp:
        llms_txt = fp.read()

    prompt = llms_txt

    prompt += """
    Analyze the following code according to Zuspec semantics and 
    determine what will be printed. Output your explanation under
    an 'Explanation' heading. Output JSON-formatted data containing
    the printed strings under a 'Result' M1 heading (ie # Result).
    """

    for e in src_elems:
        e_src = inspect.getsource(e)
        prompt += e_src

    os.environ["GITHUB_API_KEY"] = os.environ["GITHUB_MODELS_PAT"]

    response = litellm.completion(
        model="github/gpt-4.1",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    print("response: %s" % response)
    content = response.choices[0].message.content
    print("Output:\n%s\n" % content)

    result_idx = content.find("# Result")
    assert result_idx != -1

    json_idx = content.find("```json", result_idx)
    assert json_idx != -1

    json_edx = content.find("```", json_idx+3)
    assert json_edx != -1

    result = content[json_idx+7:json_edx]

    result_j = json.loads(result)
    key = next(iter(result_j.keys()))

    print("Key: %s" % key)
    lines = result_j[key]

    print("lines: %s" % lines)

    ok = 0
    err = 0
    for i in range(max(len(expect), len(lines))):
        if i < len(expect):
            exp = expect[i]
        else:
            exp = ""
        if i < len(lines):
            act = lines[i]
        else:
            act = ""

        print("Exp: %s" % exp)
        print("Act: %s" % act)
        chk = (act == exp)
        print("Chk: %s" % chk)
        if chk:
            ok += 1
        else:
            err += 1

    assert ok and not err



    
@pytest.mark.skip
def test_analysis2():

    def inner():
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
    
        tb = Timebase()
        impl = ExecFactory(tb).build(MyC)
    
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

    run_test(
        src_elems=[Timebase, ExecFactory, inner],
        model="github/gpt-4.1",
        expect=[
            "Count: 30",
            "Count: 0",
        ])

def test_analysis3():

    def inner():
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
                    self.count += 1
    
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
    
        tb = Timebase()
        impl = ExecFactory(tb).build(Top)
    
        async def clock(count=1):
            nonlocal tb, impl
            for _ in range(count):
                impl.clock = 1
                await tb.wait(10, -9)
                impl.clock = 0
                await tb.wait(10, -9)

        async def run():
            nonlocal tb, impl 
            # Simple(istic) testbench
            impl.clock = 0
            impl.reset = 1
            await tb.wait(10, -9)
            impl.reset = 0
            await tb.wait(10, -9)
    
            await clock(10)
            print("Count: %d" % impl.monitor.count)
    
            impl.reset = 1
            await clock(10)
            impl.reset = 0
    
            print("Count: %d" % impl.monitor.count)

    # run_test(
    #     src_elems=[Timebase, ExecFactory, inner],
    #     model="github/gpt-4.1",
    #     expect=[
    # "count: 1",
    # "count: 2",
    # "count: 3",
    # "count: 4",
    # "count: 5",
    # "count: 6",
    # "count: 7",
    # "count: 8",
    # "count: 9",
    # "count: 10",
    # "Count: 10",
    # "Count: 0"
    #     ])


@pytest.mark.skip
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

    tb = Timebase()
    impl = ExecFactory(tb).build(Top)

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
