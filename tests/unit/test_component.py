import asyncio
import zuspec.dataclasses as zdc
from typing import Final, Protocol

def test_smoke():

    class DataIF(Protocol):
        async def call(self, req : int) -> int: ...

    @zdc.dataclass
    class MyProdC(zdc.Component):
        prod : DataIF = zdc.port()

        @zdc.process
        async def _run(self):
            for i in range(16):
                rsp = await self.prod.call(i)

    @zdc.dataclass
    class MyConsC(zdc.Component):
        # Bind, in this context, must work in one of two ways
        # -  
        cons : DataIF = zdc.export()

        def __bind__(self): return {
            self.cons.call : self.target
        }

        async def target(self, req : int) -> int:
            return req+2

    @zdc.dataclass
    class MyC(zdc.Component):
        p : MyProdC = zdc.field() # default_factory=MySubC)
        c : MyConsC = zdc.field()

        def __post_init__(self):
            print("MyC.__post_init__: %s" % str(self), flush=True)
#            super().__post_init__()

        def __bind__(self): return {
            self.p.prod : self.c.cons
        }

    print("--> MyC()")
    c = MyC()
    print("<-- MyC()")

    asyncio.run(c.wait(10))

    print("c.p.prod: %s" % c.p.prod)
    print(asyncio.run(c.p.prod.call(20)))






