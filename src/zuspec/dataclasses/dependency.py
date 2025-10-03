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
import dataclasses as dc
from typing import List

class DependencyProvider(abc.ABC): pass

class Pool[T](DependencyProvider): pass

class TrackingDependencyProvider[T](DependencyProvider):
    """
    Dependency provider that tracks its dependencies. 
    This is typically used by a component that must use
    dependency information to properly build itself.
    """

    @abc.abstractmethod
    def dependents(self) -> List[T]:
        """
        List of dependencies bound to this provider
        """
        pass
