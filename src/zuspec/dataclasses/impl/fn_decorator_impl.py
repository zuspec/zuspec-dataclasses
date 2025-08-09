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
from .fn_impl import FnImpl
from .method_proxy_fn import MethodProxyFn

class FnDecoratorImpl(typeworks.MethodDecoratorBase):

    def __init__(self, is_import, kwargs):
        super().__init__([], kwargs)
        self._is_import = is_import
        pass

    def get_category(self):
        return TypeKindE.Function
    
    def pre_decorate(self, T):
        # Ensure everything that needs a type hint has one
        self.validate_hints()
        super().pre_decorate(T)

    def decorate(self, T):
        return MethodProxyFn(T)

    def post_decorate(self, T, Tp):
        is_method, rtype, params = self.get_signature()
        Tp._is_import = self._is_import
        Tp._is_method = is_method
        Tp._rtype = rtype
        Tp._params = params

    def pre_register(self):
        return super().pre_register()
    

    




