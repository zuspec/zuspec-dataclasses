#****************************************************************************
#* type_info_extend_action.py
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

from .type_kind_e import TypeKindE
import vsc_dataclasses.impl as vsc_impl
from .typeinfo_extend_base import TypeInfoExtendBase

class TypeInfoExtendAction(TypeInfoExtendBase):

    def __init__(self, info, kind=TypeKindE.ExtendAction):
        super().__init__(info, kind)
        self.activities = []

    def addActivity(self, activity_t):
        self.activities.append(activity_t)

    def applyExtension(self, target):
        super().applyExtension(target)

        for activity in self.activities:
            target.addActivity(activity)

    @staticmethod
    def get(info) -> 'TypeInfoExtendAction':
        if not hasattr(info, vsc_impl.TypeInfoRandClass.ATTR_NAME):
            setattr(info, vsc_impl.TypeInfoRandClass.ATTR_NAME, TypeInfoExtendAction(info))
        return getattr(info, vsc_impl.TypeInfoRandClass.ATTR_NAME)
