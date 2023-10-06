#****************************************************************************
#* reg_group_decorator_impl.py
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
from vsc_dataclasses.impl.typeinfo_field import TypeInfoField
from .component_decorator_impl import ComponentDecoratorImpl
from .reg_c import RegC
from .type_info import TypeInfo
from .typeinfo_component import TypeInfoComponent
from .typeinfo_field_reg_c import TypeInfoFieldRegC
from .typeinfo_reg_group import TypeInfoRegGroup
from .type_utils import TypeUtils
from .ctor import Ctor

class RegGroupDecoratorImpl(ComponentDecoratorImpl):

    def pre_decorate(self, T):
        reg_group_ti = TypeInfoRegGroup.get(self.get_typeinfo())

        super().pre_decorate(T)

    def init_annotated_field(self, key, value, has_init, init):
        component_ti = TypeInfoComponent.get(self.get_typeinfo())

        print("key: %s value: %s" % (str(key), str(value)))
        if issubclass(value, RegC):

            print("RegC.T=%s" % str(value.T))
            reg_ti = TypeUtils().val2TypeInfo(value.T)

            if reg_ti is None:
                raise Exception("Failed to get reg type")

#            value_ti = typeworks.TypeInfo.get(value, False)
#            value_base_ti = TypeInfo.get(value_ti, False)

            ctor = Ctor.inst()
            print("RegC")
            field_type_obj = ctor.ctxt().mkTypeFieldReg(
                key,
                reg_ti.lib_typeobj,
                False)
            
            if has_init:
                field_type_obj.setOffset(init["offset"])


            # TODO: handle offsets (if present)

            # TODO: Hmm... This might not be right either...
            # Maybe we need a TypeInfoReg()?
            field_fi = TypeInfoFieldRegC(key, reg_ti)
            component_ti.addField(field_fi, field_type_obj)
#            component_ti.addField(field_ti, )

            # Clean up to keep 'dataclasses' happy
            self.set_field_initial(key, None)
        else:
            # Delegate to Component decorator
            super().init_annotated_field(key, value, has_init, init)



