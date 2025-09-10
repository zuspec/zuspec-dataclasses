
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
import dataclasses as dc
import enum
from typing import Callable, Optional

class ExecKind(enum.Enum):
    Sync = enum.auto()
    Proc = enum.auto()

@dc.dataclass
class Exec(object):
    method : Callable = dc.field()
    kind : ExecKind = dc.field()
    bind : Optional[Callable] = dc.field(default=None)
