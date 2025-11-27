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

from asyncio import Event
from .decorators import (
    dataclass, field, export, extern, mirror, process, input, output, 
    sync, const, port, export, bind, Exec, ExecKind, ExecSync, 
    Input, Output, FSM, ExecState, fsm, binder
)
from .types import *
import zuspec.dm as dm
from .transformer import DataclassesTransformer

def transform(*args) -> dm.Context:
    """Accepts one or more class types and returns a datamodel Context."""
    tr = DataclassesTransformer()
    tr.process(*args)
    return tr.result()

