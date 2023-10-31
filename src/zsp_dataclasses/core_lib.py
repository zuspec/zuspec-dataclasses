#****************************************************************************
#* core_lib.py
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
import sys
from .impl.reg_c_meta import RegCMeta
from .impl.reg_group_meta import RegGroupMeta
from .impl.reg_group_decorator_impl import RegGroupDecoratorImpl

def print(*args):
    from .impl.ctor import Ctor
    ctor = Ctor.inst()
    print_f = ctor.ctxt().findDataTypeFunction("std_pkg::print")
    sys.stdout.write("print_f: %s\n" % str(print_f))

    ctor.proc_scope().addStatement(
        ctor.ctxt().mkTypeProcStmtExpr(
            ctor.ctxt().mkTypeExprMethodCallStatic(
                print_f,
                [])))

class reg_c(metaclass=RegCMeta):
    pass

def reg_group_c(*args, **kwargs):
    if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
        return RegGroupDecoratorImpl(args, kwargs)(args[0])
    else:
        return RegGroupDecoratorImpl(args, kwargs)

