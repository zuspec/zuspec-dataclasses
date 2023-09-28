#****************************************************************************
#* type_expr_method_call_static.py
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
from typing import List
import zsp_dataclasses.impl.context as ctxt

class TypeExprMethodCallStatic(ctxt.TypeExprMethodCallStatic):

    def __init__(self, target : 'DataTypeFunction', params):
        self._target = target
        self._params = params.copy()
        pass

    def getTarget(self) -> 'DataTypeFunction':
        return self._target
    
    def getParameters(self) -> List['vsc_ctxt.TypeExpr']:
        return self._params
    
    def accept(self, v):
        v.visitTypeExprMethodCallStatic(self)
