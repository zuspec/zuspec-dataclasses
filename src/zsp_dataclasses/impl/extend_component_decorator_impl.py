#****************************************************************************
#* extend_component_decorator_impl.py
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

from .type_kind_e import TypeKindE
from .extend_base_decorator_impl import ExtendBaseDecoratorImpl
from .typeinfo_extend_base import TypeInfoExtendBase

class ExtendComponentDecoratorImpl(ExtendBaseDecoratorImpl):

    def __init__(self, target, *args, **kwargs):
        super().__init__(target, args, kwargs)

    def get_type_category(self):
        return TypeKindE.ExtendComponent

    def pre_decorate(self, T):
        component_ti = TypeInfoExtendBase.get(self.get_typeinfo())
        super().pre_decorate(T)

    
