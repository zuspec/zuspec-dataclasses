#****************************************************************************
#* test_label.py
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

import zsp_dataclasses as arl
from .test_base import TestBase

class TestLabel(TestBase):


    def test_smoke(self):

        @arl.component
        class pss_top(object):

            @arl.action
            class A(object):
#                v : arl.rand_uint8_t
                pass

        
            @arl.action
            class Entry(object):
#                @arl.constraint
#                def a_c(self):
#                    self.a.v < 10

                @arl.activity
                def activity(self):

                    arl.do(label="a")[pss_top.A]

        top = pss_top()
