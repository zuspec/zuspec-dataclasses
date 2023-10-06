#****************************************************************************
#* data_type_function.py
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
import zsp_dataclasses.impl.context as ctxt
from typing import List

class DataTypeFunction(object):

    def __init__(self,
                 name,
                 rtype,
                 flags):
        self._name = name
        self._rtype = rtype
        self._flags = flags
        self._params = []
        self._body = None
        self._imp_specs = []

    def name(self):
        return self._name
    
    def getReturnType(self) -> 'vsc_ctxt.DataType':
        return self._rtype
    
    def getParameters(self) -> List['DataTypeFunctionParamDecl']:
        return self._params
    
    def addParameter(self, p : 'DataTypeFunctionParamDecl'):
        self._params.append(p)

    def getBody(self):
        return self._body
    
    def setBody(self, b):
        self._body = b

    def addImportSpec(self, spec : 'DataTypeFunctionImport'):
        self._imp_specs.append(spec)
    
    def getImportSpecs(self) -> List['DataTypeFunctionImport']:
        return self._imp_specs
    
    def getFlags(self):
        return self._flags
    
    def hasFlags(self, f):
        print("hasFlags: %s %s %d" % (
            str(self._flags),
            str(f),
            (self._flags & f)
        ))
        return (self._flags & f) != 0

    def accept(self, v):
        v.visitDataTypeFunction(self)