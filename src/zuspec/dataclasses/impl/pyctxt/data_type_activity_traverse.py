#****************************************************************************
#* data_type_activity_traverse.py
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

import zuspec.impl.context as ctxt_api
import vsc_dataclasses.impl.context as vsc_ctxt

class DataTypeActivityTraverse(ctxt_api.DataTypeActivityTraverse):

    def __init__(self, target, with_c):
        self._target = target
        self._with_c = with_c

    def getTarget(self) -> vsc_ctxt.TypeExprFieldRef:
        return self._target

    def getWithC(self) -> 'vsc_ctxt.TypeConstraint':
        return self._with_c

    def setWithC(self, c : 'vsc_ctxt.TypeConstraint'):
        self._with_c = c

    def accept(self, v):
        v.visitDataTypeActivityTraverse(self)

