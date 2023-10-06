#****************************************************************************
#* type_field_reg.py
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
import vsc_dataclasses.impl.context as vsc_api
from vsc_dataclasses.impl.pyctxt.type_field import TypeField

class TypeFieldReg(ctxt_api.TypeFieldReg, TypeField):

    def __init__(self, name, type, owned):
        TypeField.__init__(self, name, type, vsc_api.TypeFieldAttr.NoAttr)
        self._offset = -1

    def setOffset(self, off):
        self._offset = off

    def getOffset(self):
        return self._offset

    def accept(self, v):
        v.visitTypeFieldReg(self)