#****************************************************************************
#* collect_type_deps.py
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
from vsc_dataclasses.impl.generators.collect_struct_deps import CollectStructDeps
from vsc_dataclasses.impl.pyctxt.data_type_struct import DataTypeStruct
from zsp_dataclasses.impl.context import DataTypeAction, DataTypeComponent
from ..pyctxt.visitor_base import VisitorBase

class CollectTypeDeps(VisitorBase,CollectStructDeps):

    def __init__(self):
        CollectStructDeps.__init__(self, None)

    def collect(self, root_comp, root_action):
        self._init()
        self.addType(root_action)
        self.push_scope(root_action)
        self.addRef(root_comp)
        self.pop_scope()
        root_comp.accept(self)
        root_action.accept(self)
        
        return self._sort_deps()

    def visitDataTypeAction(self, i: DataTypeAction):
        if self.in_field():
            self.addRef(i)
        else:
            self.addType(i)

        self.push_scope(i)
        for f in i.getFields():
            f.accept(self)
        # TODO: Activities
        self.pop_scope()

    def visitDataTypeComponent(self, i: DataTypeComponent):
        if self.in_field():
            self.addRef(i)
        else:
            self.addType(i)

        self.push_scope(i)
        for f in i.getFields():
            f.accept(self)
        self.pop_scope()

    def visitDataTypeStruct(self, i: DataTypeStruct):
        if self.in_field():
            self.addRef(i)
        else:
            self.addType(i)

        self.push_scope(i)
        for f in i.getFields():
            f.accept(self)
        self.pop_scope()

    