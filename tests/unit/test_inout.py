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

    class MyTransform(api.Visitor):
        _result : str = ""

        def transform(self, t) -> str:
            self._result = ""
            self.visit(t)
            return self._result

        def visitComponentType(self, t):
            self.print("MyV.visitComponentType")
            return super().visitComponentType(t)
        
        def visitInput(self, f):
            self.print("visitInput: %s" % f.name)

        def visitOutput(self, f):
            self.print("visitOutput: %s" % f.name)

        def visitExec(self, name, e):
            self.print("visitExec: %s" % name)

        def print(self, m):
            self._result += m + "\n"


    result = MyTransform().transform(Counter)

    print("Result:\n%s" % result)
