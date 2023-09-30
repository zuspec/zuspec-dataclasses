#****************************************************************************
#* type_proc_stmt_scope.py
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

class TypeProcStmtScope(ctxt_api.TypeProcStmtScope):

    def __init__(self):
        self._statements = []
        self._variables = []

    def addStatement(self, s):
        self._statements.append(s)
    
    def addVariable(self, v):
        self._variables.append(v)

    def getStatements(self):
        return self._statements

    def getVariables(self):
        return self._variables
    
    def accept(self, v):
        v.visitTypeProcStmtScope(self)


