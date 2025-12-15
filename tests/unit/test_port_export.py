import pytest
import zuspec.dataclasses as zdc
from typing import Protocol

def test_call_through():

    class IApi(Protocol):
        def doit(self, val : zdc.uint32_t): ...

    @zdc.dataclass
    class T(zdc.Component):
        exp : IApi = zdc.export()

        def __bind__(self): return {
            self.exp.doit : self.doit
        }

        def doit(self, val : zdc.uint32_t):
            print("T.doit %d" % val)

    @zdc.dataclass
    class I(zdc.Component):
        p : IApi = zdc.port()

        def doit(self):
            self.p.doit(1)
            self.p.doit(2)

    @zdc.dataclass
    class Top(zdc.Component):
        i : I = zdc.field()
        t : T = zdc.field()

        def __bind__(self): return {
            self.i.p : self.t.exp
        }

    t = Top()
    t.i.doit()

    # TODO: Expect output of 'T.doit 1' 'T.doit 2'

