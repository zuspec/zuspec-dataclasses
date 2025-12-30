#****************************************************************************
# Copyright 2019-2025 Matthew Ballance and contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#****************************************************************************
"""
Docstring for src.zuspec.dataclasses
"""

# Datamodel Mapping
# 

from asyncio import Event as aEvent
from typing import Callable
from .decorators import (
    dataclass, field, process, input, output, 
    port, export, bind, Exec, ExecKind, ExecProc,
    Input, Output, sync, comb, ExecSync, ExecComb, invariant,
    inst, tuple
)
from .types import *
from .tlm import *
from . import ir
from . import profiles
from .data_model_factory import DataModelFactory
from typing import Type

@dc.dataclass
class Event(aEvent):
    """Supports interrupt functionality in Zuspec"""

    # Specifies a method that is invoked when the event is set.
    # Use 'bind' to associate a callback with this
    at : Callable = dc.field(init=False)
    
    def __new__(cls, **kwargs):
        from .config import Config
        ret = Config.inst().factory.mkEvent(cls, **kwargs)
        return ret





