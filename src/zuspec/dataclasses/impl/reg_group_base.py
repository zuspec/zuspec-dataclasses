#****************************************************************************
#* reg_group_base.py
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

from typeworks.impl.typeinfo import TypeInfo
from .typeinfo_reg_group import TypeInfoRegGroup

class RegGroupBase(object):

    def __init__(self):
        pass

RegGroupBase._typeinfo = TypeInfo(RegGroupBase)
TypeInfoRegGroup.get(RegGroupBase._typeinfo)

