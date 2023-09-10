#****************************************************************************
#* test_type_extension.py
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

class TestTypeExtension(TestBase):

    def test_smoke(self):

        @arl.component
        class PssTop(object):

            @arl.action
            class Entry(object):
                a : arl.rand_int16_t

        @arl.extend.action(PssTop.Entry)
        class ext(object): # Note: really want a way for this to be anonymous
            b : arl.rand_int16_t

#            @arl.constraint
#            def ab_c(self):
#                self.a != self.b

        @arl.extend.action(PssTop.Entry)
        class ext(object): # Note: really want a way for this to be anonymous
            c : arl.rand_int16_t

            # @arl.constraint
            # def ab_c(self):
            #     self.a != self.b

        @arl.extend.component(PssTop)
        class ext(object):
            c : arl.int16_t

        pss_top = PssTop()
        print("pss_top.c=%d" % pss_top.c)



