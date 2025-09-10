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
from typing import Self, Type, TypeVar
from .decorators import dataclass, field
from .component import Component
from .struct import Struct

CompT = TypeVar('CompT', bound=Component)

@dataclass
class Action[CompT](Struct):
    """
    Action-derived types 

    Valid fields
    - All Struct fields
    - Input / Output fields of Buffer, Stream, and State types
    - Lock / Share fields of Resource types
    Valid sub-regions
    - All Struct sub-regions
    - activity
    """
    comp : Type[CompT] = field()

@dataclass
class MyAction(Action[Component]):
    pass
