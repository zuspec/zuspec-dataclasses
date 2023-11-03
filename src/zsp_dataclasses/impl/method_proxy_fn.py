#****************************************************************************
#* method_proxy_fn.py
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
import typeworks
from .input_output_t import InputOutputT
from .typeinfo_proc_scope import TypeInfoProcScope
from .type_utils import TypeUtils
from .context import DataTypeFunctionFlags
import zsp_dataclasses.impl.context as ctxt_api


class MethodProxyFn(typeworks.MethodProxy):

    def __init__(self, T):
        super().__init__(T)
        self._is_import = False
        self._is_method = False
        self._rtype = None
        self._params = None
        self._libobj = None

    def elab_decl(self):
        from .ctor import Ctor
        ctxt = Ctor.inst().ctxt()

        print("elab_decl: %s" % self.T.__name__)

        rtype_dt = None
        if self._rtype is not None:
            rtype_dt = TypeUtils().val2TypeInfo(self._rtype)._lib_typeobj

        
        self._libobj = ctxt.mkDataTypeFunction(
            typeworks.localname(self.T),
            rtype_dt,
            False,
            DataTypeFunctionFlags.NoFlags)
        ctxt.addDataTypeFunction(self._libobj)

        dir = ctxt_api.ParamDir.In
        init = None

        for p in self._params:
            t = p[1]
            if issubclass(t, InputOutputT):
                dir = ctxt_api.ParamDir.Out if not t.IsInput else ctxt_api.ParamDir.In
                t = t.T

            p_ti = TypeUtils().val2TypeInfo(t)
            self._libobj.addParameter(
                ctxt.mkDataTypeFunctionParamDecl(
                    p[0], # name
                    dir,
                    p_ti._lib_typeobj, # Type
                    False,
                    init))

        if self._is_import:
            self._libobj.addImportSpec(
                ctxt.mkDataTypeFunctionImport("", False, False))

        # TODO: need to resolve types for rtype and parameters

        print("Elab: %s" % typeworks.localname(self.T))
        pass

    def elab_body(self):
        from .ctor import Ctor, CtxtE
        from vsc_dataclasses.impl.ctor import Ctor as VscCtor
        ctor_a = Ctor.inst()
        ctor = VscCtor.inst()

        if self._is_import:
            print("Elab: %s" % typeworks.localname(self.T))
        else:
            # TODO: need a scope for function parameters
            params = TypeInfoProcScope(None)
            scope = ctor_a.ctxt().mkTypeProcStmtScope()
            ctor.push_bottom_up_scope(TypeInfoProcScope(scope, params))
            ctor_a.push_proc_scope()
            ctor_a.push_ctxt_type(CtxtE.Exec)

            ctor_a.pop_ctxt_type()
            ctor.pop_bottom_up_scope()

            pass
        pass

    def __call__(self, *args, **kwargs):
        from vsc_dataclasses.impl.ctor import Ctor as VscCtor
        from vsc_dataclasses.impl.expr import Expr as VscExpr
        vsc_ctor = VscCtor.inst()
        from .ctor import Ctor
        ctor = Ctor.inst()

        if vsc_ctor.is_type_mode():
            print("Function call in type mode")
            params = []
            for a in args:
                print("a: %s" % str(a))
                e = VscExpr.toExpr(a)
                e = vsc_ctor.pop_expr(e)
                print("Expr: %s" % str(e.model))
                params.append(e.model)
            call_expr = ctor.ctxt().mkTypeExprMethodCallStatic(
                self._libobj,
                params)
            return VscExpr(call_expr)
        else:
            # TODO: 
            raise Exception("Illegal to invoke function outside type mode")
            return self.T(*args, *kwargs)
    

