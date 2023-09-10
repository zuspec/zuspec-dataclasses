#****************************************************************************
#* test_function.py
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
from .test_base import TestBase

class TestFunction(TestBase):

    def test_smoke(self):

        @zdc.fn
        def my_function(a : int, b : int):
            pass

        @zdc.component
        class my_component(object):

            @zdc.fn
            def my_method(self, a : int, b : int):
                with zdc.if_then():
                    pass
                with zdc.else_if():
                    pass
                with zdc.else:
                    pass

