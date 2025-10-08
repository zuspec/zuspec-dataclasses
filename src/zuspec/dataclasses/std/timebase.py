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
from typing import Protocol, TYPE_CHECKING
from ..decorators import dataclass
from ..types import Bit, Component

class TimeBase(Protocol):
    """
    TimeBase exposes the notion of design time
    """

    @abc.abstractmethod
    async def wait(self, amt : float, units):
        """Scales the time to the timebase and waits"""
        ...

@dataclass
class TimebaseSync(TimeBase):

    @abc.abstractmethod
    async def wait_next(self, count : int = 1):
        """Waits for 'count' timebase events (eg clocks)"""
        ...

