#****************************************************************************
#* fn_decorator_impl.py
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
from .type_kind_e import TypeKindE

class FnDecoratorImpl(typeworks.MethodDecoratorBase):

    def __init__(self, kwargs):
        super().__init__([], kwargs)
        pass

    def get_category(self):
        return TypeKindE.Function
    
    def pre_decorate(self, T):
        print("Function: pre_decorate")
        super().pre_decorate(T)
    




