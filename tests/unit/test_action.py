from __future__ import annotations
import asyncio
import zuspec.dataclasses as zdc

def test_action():

    @zdc.dataclass
    class MyC(zdc.Component):
        val: zdc.u32 = zdc.field()
        pass

    @zdc.dataclass
    class Top(zdc.Component):
        c1: MyC = zdc.inst()
        c2: MyC = zdc.inst()

        def __post_init__(self):
            self.c1.val = 21
            self.c2.val = 22

    @zdc.dataclass
    class MyA(zdc.Action[MyC]):
        val: zdc.u32 = zdc.field()

        async def body(self):
            print("Hello World")
            assert self.comp.val in [21, 22]
            self.val = 15

    top = Top()

    async def run():
        nonlocal top

        a = await MyA()(top)

        assert a.comp.val in [21, 22]
        assert a.val == 15

    asyncio.run(run())

