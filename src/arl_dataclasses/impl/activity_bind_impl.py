#****************************************************************************
#* activity_bind_impl.py
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

import itertools
from vsc_dataclasses.impl.field_ref_impl import FieldRefImpl
from .typeinfo_action import TypeInfoAction
from .typeinfo_claim import TypeInfoClaim
from .typeinfo_flow_obj_ref import TypeInfoFlowObjRef

class ActivityBindImpl(object):

    def __init__(self, *args):

        # First, do a bit of sanity checking...

        # These had better all be claims or references
        input = []
        output = []
        lock = []
        share = []

        for a in args:
            if not hasattr(a, "_modelinfo"):
                raise Exception("Bind reference %s is not a modeling field" % str(a))
            modelinfo = a._modelinfo


            # Obtain the original type-info field 
            parent = modelinfo.parent

            if not isinstance(parent.info, TypeInfoAction):
                raise Exception("Bind target %s is not within an action" % modelinfo.name)

            field_ti = parent.info.getField(modelinfo.idx)

            if isinstance(field_ti, TypeInfoFlowObjRef):
                if field_ti.is_input:
                    input.append(field_ti)
                else:
                    output.append(field_ti)
            elif isinstance(field_ti, TypeInfoClaim):
                if field_ti.is_lock:
                    lock.append(field_ti)
                else:
                    share.append(field_ti)
            else:
                raise Exception("Bind reference %s is not a reference field (%s)" % str(modelinfo.name, str(field_ti)))

        if len(input) > 0 or len(output) > 0:
            if len(lock) > 0 or len(share) > 0:
                raise Exception("Mix of lock/share and input/output")
            
            # Confirm that all have the same type
            t = None
            for f in itertools.chain(input, output):
                if t is None:
                    t = f.target_ti
                elif t is not f.target_ti:
                    raise Exception("Type mismatch")
        else:
            if len(input) > 0 or len(output) > 0:
                raise Exception("Mix of lock/share and input/output")

            t = None
            for f in itertools.chain(input, output):
                if t is None:
                    t = f.target_ti
                elif t is not f.target_ti:
                    raise Exception("Type mismatch")


        pass

