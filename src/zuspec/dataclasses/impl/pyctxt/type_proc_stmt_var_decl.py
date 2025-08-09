#****************************************************************************
#* type_proc_stmt_var_decl.py
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
import vsc_dataclasses.impl.context as vsc_ctxt

class TypeProcStmtVarDecl(object):

    def __init__(self, name, type, init):
        self._name = name
        self._type = type
        self._init = init

    def name(self) -> str:
        return self._name
    
    def getDataType(self) -> vsc_ctxt.DataType:
        return self._type
    
    def getInit(self):
        return self._init
    
    def accept(self, v):
        v.visitTypeProcStmtVarDecl(self)
