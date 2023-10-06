#****************************************************************************
#* reg_group_meta.py
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

from .reg_group_decorator_impl import RegGroupDecoratorImpl
from .reg_group import RegGroup
from .reg_group_meta_meta import RegGroupMetaMeta

class RegGroupMeta(type):

    def __init__(self, name, bases, dct):
        super().__init__(name, bases, dct)

    def __call__(self, *args, **kwargs):
        if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
            return RegGroupDecoratorImpl(args, kwargs)(args[0])
        else:
            return RegGroupDecoratorImpl(args, kwargs)
    
    # def __getitem__(self, index):
    #     return RegGroupMetaMeta("reg_group[%s]" % str(index), (RegGroup,), {})


