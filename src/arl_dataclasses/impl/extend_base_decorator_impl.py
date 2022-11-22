#****************************************************************************
#* extend_base_decorator_impl.py
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

import typeworks
from .type_info import TypeInfo
from vsc_dataclasses.impl import ExtendRandClassDecoratorImpl

class ExtendBaseDecoratorImpl(ExtendRandClassDecoratorImpl):

    def __init__(self, target, *args, **kwargs):
        super().__init__(target, args, kwargs)
        pass

    def pre_decorate(self, T):
        typeinfo_ti = TypeInfo.get(self.get_typeinfo())

        self.target_ti.addExtension(typeinfo_ti)

        super().pre_decorate(T)
