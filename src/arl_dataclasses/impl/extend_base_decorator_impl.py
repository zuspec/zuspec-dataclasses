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
from .exec_type import ExecType
from .typeinfo_extend_base import TypeInfoExtendBase
from vsc_dataclasses.impl import ExtendRandClassDecoratorImpl

class ExtendBaseDecoratorImpl(ExtendRandClassDecoratorImpl):

    def __init__(self, target, *args, **kwargs):
        super().__init__(target, args, kwargs)
        pass

    def pre_decorate(self, T):
        typeinfo_ti = TypeInfoExtendBase.get(self.get_typeinfo())

        # collect exec blocks registers in this scope
        for exec_ti in typeworks.DeclRgy.pop_decl(ExecType, typeworks.scopename(T)):
            print("Add exec block %s %s" % (str(exec_ti), str(T)))
            print("  annotations: %s" % str(exec_ti.func.__annotations__))
            typeinfo_ti.addExec(exec_ti)
        
        # Now, link up the 'super' relationships
#        super_ti = self._get_super_ti(T)
#        if super_ti is not None:
#            typeinfo_ti.setExecSuper(super_ti)

        self.target_ti.addExtension(typeinfo_ti)

        super().pre_decorate(T)


    def _get_super_ti(self, T):
        if len(T.__bases__) > 0:
            ti = typeworks.TypeInfo.get(T.__bases__[0], False)
            if ti is not None:
                super_ti = TypeInfo.get(ti, True)
                if super_ti is not None:
                    # Have an actual base here
                    return super_ti
        return None