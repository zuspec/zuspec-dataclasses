#****************************************************************************
#* visitor_base.py
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

from vsc_dataclasses.impl.pyctxt.visitor_base import VisitorBase as VscVisitorBase
from ..context import DataTypeAction, DataTypeActivity, DataTypeActivityScope
from ..context import DataTypeActivityTraverse
from ..context import DataTypeComponent, DataTypeArlStruct

class VisitorBase(VscVisitorBase):

    def __init__(self):
        pass

    def visitDataTypeAction(self, i : DataTypeAction):
        self.visitDataTypeStruct(i)

    def visitDataTypeActivity(self, i : DataTypeActivity):
        pass

    def visitDataTypeActivityScope(self, i : DataTypeActivityScope):
        for a in i.getActivities():
            a.accept(self)

    def visitDataTypeActivityTraverse(self, i : DataTypeActivityTraverse):
        i.getTarget().accept(self)

        if i.getWithC() is not None:
            i.getWithC().accept(self)

    def visitDataTypeArlStruct(self, i : DataTypeArlStruct):
        super().visitDataTypeStruct()
        for e in i.getExecs():
            e.accept(self)
        for f in i.getFunctions():
            f.accept(self)

    def visitDataTypeComponent(self, i : DataTypeComponent):
        self.visitDataTypeStruct(i)

