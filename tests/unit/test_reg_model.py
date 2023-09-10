#****************************************************************************
#* test_reg_model.py
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
from .test_base import TestBase
import zsp_dataclasses as zdc

class TestRegModel(TestBase):

    def test_smoke(self):
        @zdc.struct
        class my_reg1(object):
            f1 : zdc.uint8_t
            f2 : zdc.uint8_t
            f3 : zdc.uint8_t
            f4 : zdc.uint8_t

        @zdc.reg_group_c
        class my_regs(object):
            r1 : zdc.reg_c[my_reg1](offset=10)
            r2 : zdc.reg_c[my_reg1](offset=20)
            r3 : zdc.reg_c[my_reg1]
            r4 : zdc.reg_c[my_reg1]

        @zdc.component
        class pss_top(object):
            regs : my_regs
        

