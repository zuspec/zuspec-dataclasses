#****************************************************************************
#* extend_action_decorator_impl.py
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
from .activity_decl import ActivityDecl
from .extend_base_decorator_impl import ExtendBaseDecoratorImpl
from .extend_kind_e import ExtendKindE
from .type_kind_e import TypeKindE
from .typeinfo_extend_action import TypeInfoExtendAction

class ExtendActionDecoratorImpl(ExtendBaseDecoratorImpl):

    def __init__(self, target, *args, **kwargs):
        super().__init__(target, args, kwargs)
        pass

    def get_type_category(self):
        return TypeKindE.ExtendAction

    def pre_decorate(self, T):
        action_ti : TypeInfoExtendAction = TypeInfoExtendAction.get(self.get_typeinfo())

        for activity_t in typeworks.DeclRgy.pop_decl(ActivityDecl, typeworks.scopename(T)):
            action_ti.addActivity(activity_t)

        # Only thing to avoid is re-adding special fields (eg comp)
        return super().pre_decorate(T)

    def pre_register(self):
        # Note: Don't want to register this as an ActionType
        return super().pre_register()

