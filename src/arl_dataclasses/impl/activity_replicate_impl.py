#****************************************************************************
#* activity_replicate_impl.py
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

import vsc_dataclasses.impl as vsc_impl
from .ctor import Ctor
from .modelinfo_activity import ModelinfoActivity

class ActivityReplicateImpl(object):

    def __init__(self, count, label=None):
        # TODO: expression-ify
        ctor = vsc_impl.Ctor.inst()
        self._count = vsc_impl.Expr.toExpr(count)
        ctor.pop_expr(self._count)

    def __enter__(self):
        ctor_a = Ctor.inst()
        scope_dt = ctor_a.ctxt().mkDataTypeActivityReplicate(self._count.model)
        scope_ft = ctor_a.ctxt().mkTypeFieldActivity(
            "",
            scope_dt,
            True)
        scope_mi = ModelinfoActivity(scope_dt)
        
        ctor_a.add_activity(scope_ft)
        ctor_a.push_activity_scope_mi(scope_mi)

        pass

    def __exit__(self, t, v, tb):
        ctor_a = Ctor.inst()
        ctor_a.pop_activity_scope_mi()
        pass

