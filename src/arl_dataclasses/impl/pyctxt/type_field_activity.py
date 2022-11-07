#****************************************************************************
#* type_field_activity.py
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

import arl_dataclasses.impl.context as ctxt_api
from vsc_dataclasses.impl.pyctxt.type_field_phy import TypeFieldPhy

class TypeFieldActivity(ctxt_api.TypeFieldActivity,TypeFieldPhy):

    def __init__(self,
        name,
        type : ctxt_api.DataTypeActivity):
        TypeFieldPhy.__init__(self, name, type, False, None)

    def mkActivity(self, ctxt: ctxt_api.ModelBuildContext):
        return self.getDataType().mkActivity(ctxt, self)



