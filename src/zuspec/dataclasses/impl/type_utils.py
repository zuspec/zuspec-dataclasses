#****************************************************************************
#* type_utils.py
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
from vsc_dataclasses.impl.type_utils import TypeUtils as VscTypeUtils

class TypeUtils(VscTypeUtils):

    def __init__(self):
        super().__init__()
        pass

    def val2TypeInfo(self, value):
        from .ctor import Ctor
        from .pool_t import PoolT
        from .pool_meta_sz_t import PoolMetaSzT
        from .reg_c import RegC
        from .type_info import TypeInfo

        if issubclass(value, (PoolT,PoolMetaSzT)):
            pool_t_ti = typeworks.TypeInfo.get(value.T, False)
            return TypeInfo.get(pool_t_ti, False)
        elif issubclass(value, RegC):
            value_ti = typeworks.TypeInfo.get(value, False)
            return TypeInfo.get(value_ti, False)
        else:
            return super().val2TypeInfo(value)


