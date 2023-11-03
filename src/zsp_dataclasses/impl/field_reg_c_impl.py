#****************************************************************************
#* field_reg_c_impl.py
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
from vsc_dataclasses.impl.ctor import Ctor as VscCtor
import vsc_dataclasses.impl.context as vsc_ctxt
from vsc_dataclasses.impl.expr import Expr
from .ctor import Ctor

class FieldRegCImpl(object):

    def __init__(self, modelinfo_p, name, idx):
        self._modelinfo_p = modelinfo_p
        self._name = name
        self._idx = idx
        pass

    def read(self):
        ctor = Ctor.inst()
        reg_read = ctor.ctxt().findDataTypeFunction("pss::core::reg_read")

        call_expr = ctor.ctxt().mkTypeExprMethodCallContext(
            reg_read,
            self.mkRef(),
            [])
        return Expr(call_expr)

    def write(self, value):
        ctor = Ctor.inst()
        vsc_ctor = VscCtor.inst()

        reg_write = Ctor.inst().ctxt().findDataTypeFunction("pss::core::reg_write")
        value_e = Expr.toExpr(value)
        value_e = vsc_ctor.pop_expr(value_e)

        return Expr(ctor.ctxt().mkTypeExprMethodCallContext(
                    reg_write,
                    self.mkRef(),
                    [value_e]))

    def read_val(self):
        ctor = Ctor.inst()
        reg_read_val = Ctor.inst().ctxt().findDataTypeFunction("pss::core::reg_read_val")
        return Expr(ctor.ctxt().mkTypeExprMethodCallContext(
                    reg_read_val,
                    self.mkRef(),
                    []))

    def write_val(self, value):
        ctor = Ctor.inst()
        reg_write_val = Ctor.inst().ctxt().findDataTypeFunction("pss::core::reg_write_val")
        ctor.proc_scope().addStatement(
            ctor.ctxt().mkTypeProcStmtExpr(
                ctor.ctxt().mkTypeExprMethodCallContext(
                    reg_write_val,
                    self.mkRef(),
                    [])))
        pass

    def mkRef(self):
        ctor = Ctor.inst()

        # TODO: must determine whether we're in a top-down or bottom-up scope
        kind = vsc_ctxt.TypeExprFieldRefKind.TopDownScope
        root_off = 0

        mi = self._modelinfo_p

        offset_l = [self._idx]
        while mi is not None and mi._idx != -1:
            print("MI: %s %d %s" % (str(mi), mi._idx, mi._name))
            offset_l.insert(0, mi._idx)
            mi = mi._parent


        return ctor.ctxt().mkTypeExprFieldRef(
            kind,
            root_off,
            offset_l
        )


