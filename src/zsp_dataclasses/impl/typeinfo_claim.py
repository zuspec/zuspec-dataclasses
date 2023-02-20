#****************************************************************************
#* type_info_claim.py
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

import vsc_dataclasses.impl as vsc_impl

class TypeInfoClaim(vsc_impl.TypeInfoRef):

    def __init__(self, name, target_ti, is_lock):
        super().__init__(target_ti)
        self._name = name
        self._is_lock = is_lock

    @property
    def name(self):
        return self._name

    @property
    def is_lock(self):
        return self._is_lock

    def createInst(
        self,
        modelinfo_p,
        name,
        idx):
        ctor = vsc_impl.Ctor.inst()

        if ctor.is_type_mode():
            # Create a field corresponding to the target type
            # in order to construct type reference expressions
            field = self.target_ti.createTypeInst()
            field._modelinfo.name = name
            field._modelinfo.idx = idx
            modelinfo_p.addSubfield(field._modelinfo)
            ret = field
        else:
            ret = super().createInst(modelinfo_p, name, idx)

        return ret