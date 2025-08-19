import pytest
import zuspec.dataclasses as zdc
import zuspec.dataclasses.api as api

def test_smoke():

    @zdc.dataclass
    class Counter(zdc.Component):
        clock : zdc.Bit = zdc.input()
        reset : zdc.Bit = zdc.input()
        count : zdc.Bit[8] = zdc.output()

        @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
        def inc(self):
            if self.reset:
                self.count = 0
            else:
                self.count += 1

    class MyV(api.Visitor):
        def visitComponentType(self, t):
            print("MyV.visitComponentType")
            return super().visitComponentType(t)
        
        def visitField(self, f):
            print("visitField: %s" % f.name)
            t = f.type
            print("Type: %s" % str(t))


    MyV().visit(Counter)
