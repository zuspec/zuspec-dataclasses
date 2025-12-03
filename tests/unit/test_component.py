import asyncio
import zuspec.dataclasses as zdc
from typing import Final

def test_smoke():

    @zdc.dataclass
    class MySubC(zdc.Component):
        pass

    @zdc.dataclass
    class MyC(zdc.Component):
        c1 : MySubC = zdc.field(default_factory=MySubC)
#        c2 : MySubC = zdc.field(default_factory=MySubC)

        def __post_init__(self):
            print("MyC.__post_init__: %s" % str(self), flush=True)
#            super().__post_init__()

    print("--> MyC()")
    c = MyC()
    print("<-- MyC()")

    asyncio.run(c.wait(10))





