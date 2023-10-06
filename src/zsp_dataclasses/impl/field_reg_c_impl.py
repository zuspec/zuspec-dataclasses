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

class FieldRegCImpl(object):

    def __init__(self, modelinfo_p, name, idx):
        self._modelinfo_p = modelinfo_p
        self._name = name
        self._idx = idx
        pass

    def read(self):
        print("READ: %s %d" % (self._name, self._idx))
        mi = self._modelinfo_p

        offset_l = [self._idx]
        while mi is not None and mi._idx != -1:
            print("MI: %s %d %s" % (str(mi), mi._idx, mi._name))
            offset_l.insert(0, mi._idx)
            mi = mi._parent
        print("Offset: %s" % str(offset_l))

    def write(self, value):
        pass

    def read_val(self):
        pass

    def write_val(self, value):
        pass

