#****************************************************************************
#* zsp_data_model_cpp_gen.py
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

from vsc_dataclasses.impl.generators.vsc_data_model_cpp_gen import VscDataModelCppGen
from vsc_dataclasses.impl.pyctxt.data_type_struct import DataTypeStruct
from ..context import DataTypeAction, DataTypeComponent
from ..pyctxt.visitor_base import VisitorBase

class ZspDataModelCppGen(VscDataModelCppGen,VisitorBase):

    def __init__(self):
        VscDataModelCppGen.__init__(self)
        pass

    def generate(self, root_comp : DataTypeComponent, root_action : DataTypeAction):
        # TODO: likely need both root component and action type

        # Should result in RootComp and RootAction type handles
        self.println("{")
        self.inc_indent()
        root_comp.accept(self)
        self.dec_indent()
        self.println("}")
        self.println("")
        self.println("zsp::arl::dm::IDataTypeComponent *%s_t = %s->findDataTypeComponent(\"%s\");" % (
            self.leaf_name(root_comp.name()),
            self._ctxt,
            root_comp.name()))
        self.println("zsp::arl::dm::IDataTypeAction *%s_t = %s->findDataTypeAction(\"%s\");" % (
            self.leaf_name(root_action.name()),
            self._ctxt,
            root_action.name()))

        # TODO: find RootAction handle

        return self._out.getvalue()
    
    def visitDataTypeComponent(self, i: DataTypeComponent):
        if self._emit_type_mode > 0:
            self.write("%s->findDataTypeComponent(\"%s\")" % (
                self._ctxt,
                i.name()))
        else:
            self.println("zsp::arl::dm::IDataTypeComponent *%s_t = %s->mkDataTypeComponent(\"%s\");" % (
                self.leaf_name(i.name()),
                self._ctxt,
                i.name()))

            self._type_s.append(i)
            for f in i.getFields():
                f.accept(self)
            for c in i.getConstraints():
                c.accept(self)

            for a in i.getActionTypes():
                a.accept(self)
            self._type_s.pop()

            self.println("%s->addDataTypeComponent(%s_t);" % (
                self._ctxt, 
                self.leaf_name(i.name())))

    def visitTypeConstraint(self, i : 'TypeConstraint'):
        pass

    def visitTypeConstraintBlock(self, i : 'TypeConstraintBlock'):
        for c in i.getConstraints():
            c.accept(self)

    def visitTypeConstraintExpr(self, i : 'TypeConstraintExpr'):
        i.expr().accept(self)

    def visitTypeExprBin(self, i : 'TypeExprBin'):
        i._lhs.accept(self)
        i._rhs.accept(self)

    def visitTypeExprFieldRef(self, i : 'TypeExprFieldRef'):
        pass

    def visitTypeField(self, i : 'TypeField'):
        super().visitTypeFieldPhy(i)
#        pass

#    def visitTypeFieldPhy(self, i : 'TypeFieldPhy'):
#        self.visitTypeField(i)
#        pass


#        super().visitDataTypeComponent(i)
#        # Now, generate the action types
#        for a in i.getActionTypes():
#            a.accept(self)

    
    def visitDataTypeAction(self, i: DataTypeAction):
        if self._emit_type_mode > 0:
            self.write("%s->findDataTypeAction(\"%s\")" % (
                self._ctxt,
                i.name()
            ))
        else:
            self.println("{")
            self.inc_indent()
            self.println("zsp::arl::dm::IDataTypeAction *%s_t = %s->mkDataTypeAction(\"%s\");" % (
                self.leaf_name(i.name()),
                self._ctxt,
                i.name()))
            self._type_s.append(i)
            for f in i.getFields():
                f.accept(self)
            for c in i.getConstraints():
                c.accept(self)
            for e in i.getExecs():
                pass
            self._type_s.pop()
            self.println("%s_t->addActionType(%s_t);" % (
                self.leaf_name(self._type_s[-1].name()),
                self.leaf_name(i.name())
            ))
            self.dec_indent()
            self.println("}")

    

