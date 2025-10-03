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

def test_smoke():

    @zdc.dataclass
    class Counter(zdc.Component):
        count : zdc.Bit[8] = zdc.output()

        @zdc.sync
        def inc(self):
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
