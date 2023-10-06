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
import vsc_dataclasses.impl.context as vsc_ctxt
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
        print("READ: %s %d" % (self._name, self._idx))

        ctor.proc_scope().addStatement(
            ctor.ctxt().mkTypeProcStmtExpr(
                ctor.ctxt().mkTypeExprMethodCallContext(
                    reg_read,
                    self.mkRef(),
                    [])))

    def write(self, value):
        m = Ctor.inst().ctxt().findDataTypeFunction("pss::core::reg_write")
        pass

    def read_val(self):
        m = Ctor.inst().ctxt().findDataTypeFunction("pss::core::reg_read_val")
        pass

    def write_val(self, value):
        m = Ctor.inst().ctxt().findDataTypeFunction("pss::core::reg_write_val")
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


