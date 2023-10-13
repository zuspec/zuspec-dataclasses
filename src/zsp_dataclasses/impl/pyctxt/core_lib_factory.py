#****************************************************************************
#* core_lib_factory.py
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
from ..context import Context
from ..context import DataTypeFunctionFlags

class CoreLibFactory(object):

    def __init__(self, ctxt):
        self._ctxt = ctxt
        pass

    def build(self):
        self._buildRegFuncs()
        pass

    def _buildRegFuncs(self):
        reg_read = self._ctxt.mkDataTypeFunction(
            "pss::core::reg_read",
            self._ctxt.findDataTypeInt(False, 64),
            False,
            DataTypeFunctionFlags.Core)
        reg_read.addImportSpec(
            self._ctxt.mkDataTypeFunctionImport("X", False, False))
        self._ctxt.addDataTypeFunction(reg_read)
        reg_write = self._ctxt.mkDataTypeFunction(
            "pss::core::reg_write",
            None,
            False,
            DataTypeFunctionFlags.Core)
        reg_write.addImportSpec(
            self._ctxt.mkDataTypeFunctionImport("X", False, False))
        self._ctxt.addDataTypeFunction(reg_write)

