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

import zsp_dataclasses.impl.context as ctxt_api
from vsc_dataclasses.impl.generators.vsc_data_model_cpp_gen import VscDataModelCppGen
from vsc_dataclasses.impl.pyctxt.data_type_struct import DataTypeStruct
from .collect_type_deps import CollectTypeDeps
from ..context import DataTypeAction, DataTypeComponent, DataTypeFunction, TypeExec, TypeExprMethodCallContext, TypeExprMethodCallStatic, TypeFieldReg, TypeFieldRegGroup, TypeProcStmtExpr, TypeProcStmtIfElse, TypeProcStmtScope
from ..context import DataTypeFunctionFlags, TypeProcStmtAssign, TypeProcStmtAssignOp
from ..pyctxt.visitor_base import VisitorBase

class ZspDataModelCppGen(VscDataModelCppGen,VisitorBase):

    def __init__(self):
        VscDataModelCppGen.__init__(self)
        self._define_func = False
        pass

    def generate(self, 
                 root_comp : DataTypeComponent, 
                 root_action : DataTypeAction,
                 functions,
                 extra_types=None):
        # TODO: likely need both root component and action type
        if functions is not None and len(functions) > 0:
            # First, declare all functions
            self._define_func = False
            for f in functions:
#                if f.hasFlags(DataTypeFunctionFlags.Core):
#                    continue

                self.println("{")
                self.inc_indent()
                f.accept(self)
                self.dec_indent()
                self.println("}")
            self._define_func = True
            for f in functions:
                if f.hasFlags(DataTypeFunctionFlags.Core):
                    continue

                self.println("{")
                self.inc_indent()
                self.println("zsp::arl::dm::IDataTypeFunction *%s_t = %s->findDataTypeFunction(\"%s\");" % (
                    self.identifier(f.name()),
                    self._ctxt,
                    f.name()))
                if len(f.getImportSpecs()) > 0:
                    self.println("%s_t->addImportSpec(" % ( self.identifier(f.name())))
                    self.inc_indent()
                    self.println("%s->mkDataTypeFunctionImport(\"%s\", false, false)" % (
                        self._ctxt,
                        "X",
                    ))
                    self.dec_indent()
                    self.println(");")
                else:
                    self.println("%s_t->setBody(" % f.name())
                    self.inc_indent()
                    f.getBody().accept(self)
                    self.dec_indent()
                    self.println(");")
                self.dec_indent()
                self.println("}")

        if extra_types is not None:
            for et in extra_types:
                print("ET: %s" % str(et))
                self.println("{")
                self.inc_indent()
                et.accept(self)
                self.dec_indent()
                self.println("}")

        types = CollectTypeDeps().collect(root_comp, root_action)

        print("types: %s" % str(types))
        for t in types:
            t.accept(self)

        # Should result in RootComp and RootAction type handles
        # self.println("{")
        # self.inc_indent()
        # root_comp.accept(self)
        # self.dec_indent()
        # self.println("}")
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
            self.println("{")
            self.inc_indent()
            self.println("zsp::arl::dm::IDataTypeComponent *%s_t = %s->mkDataTypeComponent(\"%s\");" % (
                self.leaf_name(i.name()),
                self._ctxt,
                i.name()))
            self.println("%s->addDataTypeComponent(%s_t);" % (
                self._ctxt, 
                self.leaf_name(i.name())))

            self._type_s.append(i)
            for f in i.getFields():
                f.accept(self)
            for c in i.getConstraints():
                c.accept(self)
            for e in i.getExecs():
                e.accept(self)

#            for a in i.getActionTypes():
#                a.accept(self)
#            self._type_s.pop()

            self.dec_indent()
            self.println("}")
            
    def visitDataTypeFunction(self, i: DataTypeFunction):
        if self._define_func:
            if len(i.getImportSpecs()) == 0:
                i.getBody().accept(self)
        else:
            self.println("zsp::arl::dm::IDataTypeFunction *%s_t = %s->mkDataTypeFunction(" % (
                self.identifier(i.name()),
                self._ctxt))
            self.inc_indent()
            self.println("\"%s\"," % i.name())
            if i.getReturnType() is None:
                self.println("0,")
            else:
                self.write(self.ind())
                self._emit_type_mode += 1
                i.getReturnType().accept(self)
                self._emit_type_mode -= 1
                self.write(",\n")
            self.println("false,") # own_rtype

            # TODO: Flags
            flags = "zsp::arl::dm::DataTypeFunctionFlags::NoFlags"
            for f in DataTypeFunctionFlags:
                if i.hasFlags(f):
                    flags += "|zsp::arl::dm::DataTypeFunctionFlags::%s" % f.name
            
            self.println("%s" % flags)
            self.dec_indent()
            self.println(");")
            # Add parameter declarations
            for p in i.getParameters():
                self.println("%s_t->addParameter(" % self.leaf_name(i.name()))
                self.inc_indent()
                self.println("%s->mkDataTypeFunctionParamDecl(" % self._ctxt)
                self.inc_indent()
                self.println("\"%s\"," % p.name())
                self.println("zsp::arl::dm::ParamDir::In,")
                self.write(self.ind())
                self._emit_type_mode += 1
                p.getDataType().accept(self)
                self._emit_type_mode -= 1
                self.write(",\n")
                self.println("false,") # 'owned'
                self.println("0") # Default value
                self.dec_indent()
                self.dec_indent()
                self.println("));")
            self.println("%s->addDataTypeFunction(%s_t);" % (
                self._ctxt, 
                self.identifier(i.name())))

    def visitTypeConstraint(self, i : 'TypeConstraint'):
        pass

    def visitTypeConstraintBlock(self, i : 'TypeConstraintBlock'):
        for c in i.getConstraints():
            c.accept(self)

    def visitTypeConstraintExpr(self, i : 'TypeConstraintExpr'):
        i.expr().accept(self)

    def visitTypeExec(self, i: TypeExec):
        exec_kind_m = {
            ctxt_api.ExecKindT.Body : "zsp::arl::dm::ExecKindT::Body",
            ctxt_api.ExecKindT.InitDown : "zsp::arl::dm::ExecKindT::InitDown",
            ctxt_api.ExecKindT.InitUp   : "zsp::arl::dm::ExecKindT::InitUp",
            ctxt_api.ExecKindT.PreSolve : "zsp::arl::dm::ExecKindT::PreSolve",
            ctxt_api.ExecKindT.PostSolve : "zsp::arl::dm::ExecKindT::PostSolve",
        }
        self.println("%s_t->addExec(%s->mkTypeExecProc(" % (
            self.leaf_name(self._type_s[-1].name()),
            self._ctxt
        ))
        self.inc_indent()
        self.println("%s," % exec_kind_m[i.getKind()])
        self.inc_indent()
        i.getBody().accept(self)
        self.dec_indent()
        self.println(")")
        self.dec_indent()
        self.println(");")

    def visitTypeExprMethodCallContext(self, i: TypeExprMethodCallContext):
        self.println("%s->mkTypeExprMethodCallContext(" % self._ctxt)
        self.inc_indent()
        self.println("%s->findDataTypeFunction(\"%s\")," % (
            self._ctxt,
            i.getTarget().name()))
        self.push_comma(True)
        i.getContext().accept(self)
        self.pop_comma()
        self.println("{")
        self.inc_indent()
        for ii,p in enumerate(i.getParameters()):
            self.push_comma(ii+1 < len(i.getParameters()))
            p.accept(self)
            self.pop_comma()
        self.dec_indent()
        self.println("}")
        self.dec_indent()
        self.println(")%s" % self.comma())

    def visitTypeExprMethodCallStatic(self, i: TypeExprMethodCallStatic):
        self.println("%s->mkTypeExprMethodCallStatic(" % self._ctxt)
        self.inc_indent()
        self.println("%s->findDataTypeFunction(\"%s\")," % (
            self._ctxt,
            i.getTarget().name()))
        self.println("{")
        self.inc_indent()
        for ii,p in enumerate(i.getParameters()):
            self.push_comma(ii+1 < len(i.getParameters()))
            p.accept(self)
            self.pop_comma()
        self.dec_indent()
        self.println("}")
        self.dec_indent()
        self.println(")%s" % self.comma())

    def visitTypeField(self, i : 'TypeField'):
        self.println("TODO: hit generic TypeField (%s)" % str(i))

    def visitTypeFieldRegGroup(self, i: TypeFieldRegGroup):
        self.println("{")
        self.inc_indent()
        self.println("zsp::arl::dm::ITypeFieldRegGroup *%s_f = %s->mkTypeFieldRegGroup(" % (
            self.leaf_name(i.name()),
            self._ctxt))
        self.inc_indent()
        self.println("\"%s\"," % i.name())
        self.write(self.ind())
        self._emit_type_mode += 1
        i.getDataType().accept(self)
        self._emit_type_mode -= 1
        self.write(",\n")
        self.println("false);")
        self.dec_indent()
#        self.println("%s_f->setOffset(%d);" % (self.leaf_name(i.name()), i.getOffset()))
        self.println("%s_t->addField(%s_f);" % (
            self.leaf_name(self._type_s[-1].name()),
            self.leaf_name(i.name())))
        self.dec_indent()
        self.println("}")

    def visitTypeFieldRef(self, i : 'TypeFieldRef'):
        if i.name() != "comp":
            super().visitTypeFieldRef(i)

    def visitTypeFieldReg(self, i: TypeFieldReg):
        self.println("{")
        self.inc_indent()
        self.println("zsp::arl::dm::ITypeFieldReg *%s_f = %s->mkTypeFieldReg(" % (
            self.leaf_name(i.name()),
            self._ctxt))
        self.inc_indent()
        self.println("\"%s\"," % i.name())
        self.write(self.ind())
        self._emit_type_mode += 1
        i.getDataType().accept(self)
        self._emit_type_mode -= 1
        self.write(",\n")
        self.println("false);")
        self.dec_indent()
        self.println("%s_f->setOffset(%d);" % (self.leaf_name(i.name()), i.getOffset()))
        self.println("%s_t->addField(%s_f);" % (
            self.leaf_name(self._type_s[-1].name()),
            self.leaf_name(i.name())))
        self.dec_indent()
        self.println("}")

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
            self.println("{ // Declare action type %s" % i.name())
            self.inc_indent()
            self.println("zsp::arl::dm::IDataTypeAction *%s_t = %s->mkDataTypeAction(\"%s\");" % (
                self.leaf_name(i.name()),
                self._ctxt,
                i.name()))
            self.println("%s->addDataTypeAction(%s_t);" % (
                self._ctxt,
                self.leaf_name(i.name())
            ))
            self._type_s.append(i)
            for f in i.getFields():
                if f.name() != "comp":
                    f.accept(self)
            for c in i.getConstraints():
                c.accept(self)

            for e in i.getExecs():
                e.accept(self)

            self._type_s.pop()
            self.println("%s_t->setComponentType(%s->findDataTypeComponent(\"%s\"));" % (
                self.leaf_name(i.name()),
                self._ctxt,
                self.leaf_name(i.getComponentType().name())))
            self.println("%s->findDataTypeComponent(\"%s\")->addActionType(%s_t);" % (
                self._ctxt,
                self.leaf_name(i.getComponentType().name()),
                self.leaf_name(i.name())))
            self.dec_indent()
            self.println("}")

    def visitTypeProcStmtAssign(self, i : TypeProcStmtAssign):
        op_m = {
            TypeProcStmtAssignOp.Eq : "zsp::arl::dm::TypeProcStmtAssignOp::Eq"
        }
        self.println("%s->mkTypeProcStmtAssign(" % self._ctxt)
        self.inc_indent()
        self.push_comma(True)
        i.getLhs().accept(self)
        self.pop_comma()

        self.println("%s," % op_m[i.op()])

        self.push_comma(False)
        i.getRhs().accept(self)
        self.pop_comma()

        self.dec_indent()
        self.println(")%s" % self.comma())

    def visitTypeProcStmtExpr(self, i: TypeProcStmtExpr):
        self.println("%s->mkTypeProcStmtExpr(" % self._ctxt)
        self.inc_indent()
        self.push_comma(False)
        i.getExpr().accept(self)
        self.pop_comma()
        self.dec_indent()
        self.println(")%s" % self.comma())

    def visitTypeProcStmtIfElse(self, i: TypeProcStmtIfElse):
        self.println("%s->mkTypeProcStmtIfElse(" % self._ctxt)
        self.inc_indent()
        self.push_comma(True)
        i.getCond().accept(self)
        i.getTrue().accept(self)
        self.pop_comma()
        self.push_comma(False)
        if i.getFalse() is not None:
            i.getFalse().accept(self)
        else:
            self.println("0")
        self.pop_comma()
        self.dec_indent()
        self.println(")%s" % self.comma())

    def visitTypeProcStmtScope(self, i: TypeProcStmtScope):
        self.println("%s->mkTypeProcStmtScope({" % self._ctxt)
        self.inc_indent()
        for ii,s in enumerate(i.getStatements()):
            self.push_comma(ii+1 < len(i.getStatements()))
            s.accept(self)
            self.pop_comma()
        self.dec_indent()
        self.println("})%s" % self.comma())

    def identifier(self, name):
        return name.replace(':', '_')

