#****************************************************************************
#* data_type_function_param_decl.py
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
import zsp_dataclasses.impl.context as ctxt_api
from .type_proc_stmt_var_decl import TypeProcStmtVarDecl

class DataTypeFunctionParamDecl(TypeProcStmtVarDecl):

    def __init__(self, name, dir, type, init):
        super().__init__(name, type, init)
        self._dir = dir

    def getDirection(self) -> ctxt_api.ParamDir:
        return self._dir
    
    def accept(self, v):
        v.visitDataTypeFunctionParamDecl(self)

