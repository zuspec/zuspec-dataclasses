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

#        self._libobj = ctxt.mkDataTypeFunction(
#            typeworks.localname(self.T),
#            None)

        # TODO: need to resolve types for rtype and parameters

        print("Elab: %s" % typeworks.localname(self.T))
        pass

    def elab_body(self):
        if self._is_import:
            from .ctor import Ctor
            print("Elab: %s" % typeworks.localname(self.T))
        else:
            pass
        pass

    def __call__(self, *args, **kwargs):
        # TODO: 
        return self.T(*args, *kwargs)
    

