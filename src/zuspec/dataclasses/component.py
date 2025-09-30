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
import abc
from typing import TYPE_CHECKING
from .decorators import dataclass, field
from .struct import Struct

if TYPE_CHECKING:
    from .std.timebase import TimeBase

@dataclass
class Component(Struct):
    """
    Component classes are structural in nature. 
    The lifecycle of a component tree is as follows:
    - The root component and fields of component type are constructed
    - The 'init_down' method is invoked in a depth-first manner
    - The 'init_up' method is invoked
    """
#    timebase : 'TimeBase' = field()

    def build(self): pass

    @abc.abstractmethod
    async def wait(self, amt : float, units):
        pass

    @abc.abstractmethod
    async def wait_next(self, count : int = 1):
        pass
