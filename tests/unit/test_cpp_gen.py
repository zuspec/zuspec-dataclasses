#****************************************************************************
#* test_cpp_gen.py
#*
#* Copyright 2022 Matthew Ballance and Contributors
#*
#* Licensed under the Apache License, Version 2.0 (the "License"); you may 
#* not use this file except in compliance with the License.  
#* You may obtain a copy of the License at:
#*
#*   http://www.apache.org/licenses/LICENSE-2.0
#*
#* Unless required by applicable law or agreed to in writing, software 
#* distributed under the License is distributed on an "AS IS" BASIS, 
#* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  
#* See the License for the specific language governing permissions and 
#* limitations under the License.
#*
#* Created on:
#*     Author: 
#*
#****************************************************************************
import zsp_dataclasses as zdc
from zsp_dataclasses.impl.generators.zsp_data_model_cpp_gen import ZspDataModelCppGen
from .test_base import TestBase

class TestCppGen(TestBase):


    def test_smoke(self):
        @zdc.fn
        def my_fn(a : int, b : int = 2) -> int:
            print("my_fn")
            pass

        @zdc.component
        class pss_top(object):
            pass

            # @zdc.action
            # class MyA(object):

            #     @zdc.exec.body
            #     def body(self):
            #         pass

            #     @zdc.activity
            #     def activity(self):
            #         pass

            @zdc.action
            class Entry(object):

                @zdc.fn
                def my_method(self, a: int):
                    print("my_method")

                @zdc.exec.body
                def body(self):
                    print("== body ==")
                    my_fn(10, 12)
                    pass
                # @zdc.activity
                # def activity(self):
                #     a = pss_top.MyA()

                #     a()

        ctor = zdc.impl.Ctor.inst()

        action_t = ctor.ctxt().findDataTypeAction(pss_top.Entry.__qualname__)
        comp_t = ctor.ctxt().findDataTypeComponent(pss_top.__qualname__)

        ctor.elab()

        self.assertIsNotNone(comp_t)
        self.assertIsNotNone(action_t)

        cpp = ZspDataModelCppGen().generate(
            comp_t,
            action_t)
        print("Cpp:\n%s\n" % cpp)

    def test_single_action_exec(self):
        @zdc.import_fn
        def my_fn(a : int, b : int = 2) -> int:
            print("my_fn")

        @zdc.component
        class pss_top(object):

            @zdc.action
            class Entry(object):

                @zdc.exec.body
                def body(self):
                    print("== body ==")
                    my_fn(10, 12)

        ctor = zdc.impl.Ctor.inst()

        action_t = ctor.ctxt().findDataTypeAction(pss_top.Entry.__qualname__)
        comp_t = ctor.ctxt().findDataTypeComponent(pss_top.__qualname__)

        print("Test: Field[0]: %s" % action_t.getField(0).name())
        ctor.elab()
        print("Test: Field[0]: %s" % action_t.getField(0).name())

        self.assertIsNotNone(comp_t)
        print("Test: Field[0]: %s" % action_t.getField(0).name())
        self.assertIsNotNone(action_t)
        print("Test: Field[0]: %s" % action_t.getField(0).name())

        cpp = ZspDataModelCppGen().generate(
            comp_t,
            action_t,
            ctor.ctxt().getDataTypeFunctions())
        print("Cpp:\n%s\n" % cpp)


# Issue: Anonymous type, so pool binding rules are unclear
# Resolution: with fully-specified binding, is a pool mandatory?
# Resolution: Pool comes from the source and destination
#
# - Doesn't, itself, have a component scope
# - Can reference the component of the containing action
# let mux = (output T dat_o, input T dat_i...) -> {
#    select {
#      replicate (i : T.size) {
#          bind dat_o dat_i[i];
#      }
#    }
# }
#
# mux(a.dat_i, b.dat_o, c.dat_o, d.dat_o);
#
#


        