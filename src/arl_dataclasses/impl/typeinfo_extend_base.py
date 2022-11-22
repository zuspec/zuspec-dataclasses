#****************************************************************************
#* type_info_extend_base.py
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

from typing import Dict
from vsc_dataclasses.impl import TypeInfoExtendRandClass
from .exec_kind_e import ExecKindE
from .exec_group import ExecGroup
from .exec_type import ExecType

class TypeInfoExtendBase(TypeInfoExtendRandClass):

    def __init__(self, info, kind):
        super().__init__(info, kind)

        # Dict of exec kind to list of exec blocks
        self._exec_m : Dict[ExecKindE,ExecGroup] = {}


    def addExec(self, exec_t : ExecType):
        if exec_t.kind not in self._exec_m.keys():
            self._exec_m[exec_t.kind] = ExecGroup(exec_t.kind)
        self._exec_m[exec_t.kind].add_exec(exec_t)

    def applyExtension(self, target):
        super().applyExtension(target)

        # Propagate any exec blocks added via extension
        for kind,group in self._exec_m.items():
            for exec in group.execs:
                target.addExec(exec)

