from __future__ import annotations
import asyncio
import pytest
import zuspec.dataclasses as zdc

@pytest.mark.skip(reason="zdc.Action is not yet implemented")
def test_smoke():

    @zdc.dataclass
    class MyD(object):
        pass

    @zdc.dataclass
    class MyA(zdc.Action[Top]):
        dat_i: MyD = zdc.input()

        # Need post_init hook

        # Need pre-solve / post-solve
        # Note: these are built-in methods
        # I guess Action IS-NOT a class
        # Need something to fill the role of action executor/evaluator
        # With a class
        # - User 'new's
        # - User assigns any external refs
        # - User calls randomize(obj) 
        # - User

        async def body(self):
            pass

        pass

    @zdc.dataclass
    class Top(zdc.Component):

        async def thread(self, p : zdc.ClaimPool[zdc.u32]):
            rsrc = await p.lock()

            # Variable-delay opeation

            rsrc.drop()

        async def run(self):
            rp: zdc.ClaimPool[zdc.u32] = zdc.field()

            await asyncio.gather(
                self.thread(rp),
                self.thread(rp)
            )

            async with travserse:
                await MyA().body()
            pass


