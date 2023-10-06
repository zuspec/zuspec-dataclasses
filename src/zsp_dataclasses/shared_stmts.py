#****************************************************************************
#* shared_stmts.py
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
#* Defines statements used in multiple contexts. For example, if/else is 
#* supported in constraint, activity, and procedural context.
#****************************************************************************
import zsp_dataclasses.impl.context as ctxt_api
from vsc_dataclasses.impl.expr import Expr
from vsc_dataclasses.impl.ctor import Ctor as VscCtor
from vsc_dataclasses.impl.field_scalar_impl import FieldScalarImpl
from vsc_dataclasses.impl.typeinfo_scalar import TypeInfoScalar
from .impl.ctor import Ctor, CtxtE

class if_then(object):

    def __init__(self, e):
        ctor_a = Ctor.inst()
        ctor = VscCtor.inst()

        ctxt_t = ctor_a.ctxt_type()

        cond_e = Expr.toExpr(e)
        ctor.pop_expr(cond_e)
        print("Cond: %s" % str(cond_e.model))

        # Have constraint, proc, and activity
        if ctxt_t == CtxtE.Activity:
            print("Activity")
            pass
        elif ctxt_t == CtxtE.Constraint:
            print("Constraint")
            pass
        elif ctxt_t == CtxtE.Exec:
            scope = ctor_a.proc_scope()
            true_s = ctor_a.ctxt().mkTypeProcStmtScope()
            scope.addStatement(ctor_a.ctxt().mkTypeProcStmtIfElse(
                cond_e.model, true_s, None))
            ctor_a.push_proc_scope(true_s)
        else:
            raise Exception("Unknown context %s" % ctxt_t)

#        if in_srcinfo_mode():
#            self.stmt.srcinfo = SourceInfo.mk()
#        ctor.push_constraint_scope(true_c)
        
    def __enter__(self):
        pass
        
    def __exit__(self, t, v, tb):
        ctor_a = Ctor.inst()
        ctor = VscCtor.inst()

        ctxt_t = ctor_a.ctxt_type()

        # Have constraint, proc, and activity
        if ctxt_t == CtxtE.Activity:
            print("Activity")
            pass
        elif ctxt_t == CtxtE.Constraint:
            print("Constraint")
            pass
        elif ctxt_t == CtxtE.Exec:
            ctor_a.pop_proc_scope()
        else:
            raise Exception("Unknown context %s" % ctxt_t)
#        ctor.pop_constraint_scope()
#        ctor.constraint_scope().addConstraint(self.stmt)

class else_if(object):

    def __init__(self, e):
        ctor_a = Ctor.inst()
        ctor = VscCtor.inst()

        ctxt_t = ctor_a.ctxt_type()

        cond_e = Expr.toExpr(e)
        ctor.pop_expr(cond_e)

        # Have constraint, proc, and activity
        if ctxt_t == CtxtE.Activity:
            print("Activity")
            pass
        elif ctxt_t == CtxtE.Constraint:
            print("Constraint")
            pass
        elif ctxt_t == CtxtE.Exec:
            scope = ctor_a.proc_scope()
            last = scope.getStatements()[-1]

            print("Scope: %s" % str(last))
            if not isinstance(last, ctxt_api.TypeProcStmtIfElse):
                raise Exception("Expecting to find TypeProcStmtIfElse, but found %s" % str(last))
            false_s = ctor_a.ctxt().mkTypeProcStmtScope()

            true_s = ctor_a.ctxt().mkTypeProcStmtScope()
            false_s.addStatement(ctor_a.ctxt().mkTypeProcStmtIfElse(
                cond_e.model, true_s, None))
            last.setFalse(false_s)
            ctor_a.push_proc_scope(false_s)
        else:
            raise Exception("Unknown context %s" % ctxt_t)

#        if in_srcinfo_mode():
#            self.stmt.srcinfo = SourceInfo.mk()
        
    def __enter__(self):
        pass
        
    def __exit__(self, t, v, tb):
        ctor_a = Ctor.inst()
        ctor_a.pop_proc_scope()

class else_then_c(object):

    def __init__(self):
        pass
    
    def __call__(self):
        return self
        
    def __enter__(self):
        ctor_a = Ctor.inst()
        ctor = VscCtor.inst()

        ctxt_t = ctor_a.ctxt_type()
        
        # Have constraint, proc, and activity
        if ctxt_t == CtxtE.Activity:
            print("Activity")
            pass
        elif ctxt_t == CtxtE.Constraint:
            print("Constraint")
            pass
        elif ctxt_t == CtxtE.Exec:
            scope = ctor_a.proc_scope()
            last = scope.getStatements()[-1]

            print("Scope: %s" % str(last))
            if not isinstance(last, ctxt_api.TypeProcStmtIfElse):
                raise Exception("Expecting to find TypeProcStmtIfElse, but found %s" % str(last))
            false_s = ctor_a.ctxt().mkTypeProcStmtScope()
            last.setFalse(false_s)
            ctor_a.push_proc_scope(false_s)
        else:
            raise Exception("Unknown context %s" % ctxt_t)
        # ctor = Ctor.inst()
        # if not ctor.in_constraint_scope():
        #     raise Exception("Attempting to use if_then constraint outside constraint scope")
        
        # last_stmt = ctor.last_constraint_stmt()
        # print("last_stmt=%s" % str(last_stmt))
        # if last_stmt is None or not isinstance(last_stmt, (core.ModelConstraintIfElse,core.TypeConstraintIfElse)):
        #     raise Exception("Attempting to use else_then where it doesn't follow if_then/else_if")
        
        # # Need to find where to think this in
        # while last_stmt.getFalse() is not None:
        #     last_stmt = last_stmt.getFalse()

        # if ctor.is_type_mode():            
        #     stmt = ctor.ctxt().mkTypeConstraintScope()
        # else:
        #     stmt = ctor.ctxt().mkModelConstraintScope()
        # last_stmt.setFalse(stmt)
        # ctor.push_constraint_scope(stmt)
        
    def __exit__(self, t, v, tb):
        ctor_a = Ctor.inst()
        ctor = VscCtor.inst()

        ctxt_t = ctor_a.ctxt_type()

        # Have constraint, proc, and activity
        if ctxt_t == CtxtE.Activity:
            print("Activity")
            pass
        elif ctxt_t == CtxtE.Constraint:
            print("Constraint")
            pass
        elif ctxt_t == CtxtE.Exec:
            ctor_a.pop_proc_scope()
        else:
            raise Exception("Unknown context %s" % ctxt_t)
#        ctor = Ctor.inst()
#        ctor.pop_constraint_scope()

else_then = else_then_c()

class foreach(object):
    def __init__(self, target, idx : bool = True):
        ctor = Ctor.inst()

        if not ctor.in_constraint_scope():
           raise Exception("Attempting to use foreach constraint outside constraint scope")
        
        target_e = Expr.toExpr(target)
        ctor.pop_expr(target_e)

        if ctor.is_type_mode():
            body_c = ctor.ctxt().mkTypeConstraintScope()
            self.stmt = ctor.ctxt().mkTypeConstraintForeach(
                target_e,
                body_c)
        else:
            true_c = ctor.ctxt().mkModelConstraintScope()
            self.stmt = ctor.ctxt().mkModelConstraintIfElse(
                cond_e.model,
                true_c,
                None)

#        if in_srcinfo_mode():
#            self.stmt.srcinfo = SourceInfo.mk()
        ctor.push_constraint_scope(body_c)
        ctor.push_bottom_up_scope(self)

        self.index_f = FieldScalarImpl("__i_%d" % len(ctor.bottom_up_scopes()),
                            TypeInfoScalar(False), 0)
        pass

    def __enter__(self):
        return self.index_f
        
    def __exit__(self, t, v, tb):
        ctor = Ctor.inst()
        ctor.pop_constraint_scope()
        ctor.pop_bottom_up_scope()
        pass

    pass

class repeat(object):

    def __init__(self, count):
        ctor = VscCtor.inst()

        # This scope is a root of its own
        self._parent = None

        self.index = FieldScalarImpl(
            "__index__",
            TypeInfoScalar(ctor.ctxt().findDataTypeInt(True, 32)),
            0
        )
        self.index._modelinfo._is_topdown_scope = False
        self.index._modelinfo._parent = self

        count_e = Expr.toExpr(count)
        ctor.pop_expr(count_e)
        pass

    def __enter__(self):
        ctor = VscCtor.inst()
        ctor.push_bottom_up_scope(self)

        return self.index
    
    def __exit__(self, t, v, tb):
        ctor = VscCtor.inst()
        ctor.pop_bottom_up_scope()

class while_do(object):

    def __init__(self, cond):
        pass

class repeat_while(object):
    pass
