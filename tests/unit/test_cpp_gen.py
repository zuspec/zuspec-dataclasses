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

    def test_single_layer_reg_group(self):
        ctor = zdc.impl.Ctor.inst()

        @zdc.struct
        class my_reg1(object):
            f1 : zdc.uint8_t
            f2 : zdc.uint8_t
            f3 : zdc.uint8_t
            f4 : zdc.uint8_t

        @zdc.reg_group_c
        class my_regs(object):
            r1 : zdc.reg_c[my_reg1] = dict(offset=0x10)
            r2 : zdc.reg_c[my_reg1] = dict(offset=0x14)
            r3 : zdc.reg_c[my_reg1] = dict(offset=0x18)
            r4 : zdc.reg_c[my_reg1] = dict(offset=0x1c)

        @zdc.component
        class pss_top(object):
            regs : my_regs

            @zdc.action
            class Entry(object):

                @zdc.exec.body
                def body(self):
                    self.comp.regs.r1.read()
                    self.comp.regs.r3.read()

        ctor.elab()

        action_t = ctor.ctxt().findDataTypeAction(pss_top.Entry.__qualname__)
        comp_t = ctor.ctxt().findDataTypeComponent(pss_top.__qualname__)

        cpp = ZspDataModelCppGen().generate(
            comp_t,
            action_t,
            ctor.ctxt().getDataTypeFunctions(),
            [
                ctor.ctxt().findDataTypeComponent(my_regs.__qualname__)
            ])
        print("Cpp:\n%s\n" % cpp)

    def test_proc_stmt_if(self):
        ctor = zdc.impl.Ctor.inst()

        @zdc.import_fn
        def f1():
            pass

        @zdc.import_fn
        def f2():
            pass

        @zdc.component
        class pss_top(object):

            @zdc.action
            class Entry(object):
                f1 : zdc.rand_int16_t

                @zdc.exec.body
                def body(self):
                    with zdc.if_then(self.f1 < 10):
                        f1()
                    with zdc.else_if(self.f1 > 20):
                        f2()
                    with zdc.else_then:
                        f2()
                    pass

        ctor.elab()

        action_t = ctor.ctxt().findDataTypeAction(pss_top.Entry.__qualname__)
        comp_t = ctor.ctxt().findDataTypeComponent(pss_top.__qualname__)

        cpp = ZspDataModelCppGen().generate(
            comp_t,
            action_t,
            ctor.ctxt().getDataTypeFunctions())
        print("Cpp:\n%s\n" % cpp)

    def test_proc_stmt_repeat(self):
        ctor = zdc.impl.Ctor.inst()

        @zdc.import_fn
        def f1(a : zdc.int16_t):
            pass

        @zdc.import_fn
        def f2():
            pass

        @zdc.component
        class pss_top(object):

            @zdc.action
            class Entry(object):
                f1 : zdc.rand_int16_t

                @zdc.exec.body
                def body(self):
                    with zdc.repeat(20) as i:
                        f1(i)
                    pass

        ctor.elab()

        action_t = ctor.ctxt().findDataTypeAction(pss_top.Entry.__qualname__)
        comp_t = ctor.ctxt().findDataTypeComponent(pss_top.__qualname__)

        cpp = ZspDataModelCppGen().generate(
            comp_t,
            action_t,
            ctor.ctxt().getDataTypeFunctions())
        print("Cpp:\n%s\n" % cpp)

    def test_proc_stmt_repeat_nested_2(self):
        ctor = zdc.impl.Ctor.inst()

        @zdc.import_fn
        def f1(a : zdc.int16_t, b : zdc.output[zdc.int16_t]):
            pass

        @zdc.import_fn
        def f2() -> zdc.int32_t:
            pass

        @zdc.component
        class pss_top(object):

            @zdc.action
            class Entry(object):
                f1 : zdc.rand_int16_t

                @zdc.exec.body
                def body(self):
                    with zdc.repeat(20) as i:
                        with zdc.repeat(20) as ii:
                            f1(i, ii)
                    pass

        ctor.elab()

        action_t = ctor.ctxt().findDataTypeAction(pss_top.Entry.__qualname__)
        comp_t = ctor.ctxt().findDataTypeComponent(pss_top.__qualname__)

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


        