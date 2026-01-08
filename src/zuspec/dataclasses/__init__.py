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
    const, bundle, mirror, monitor,
    port, export, bind, Exec, ExecKind, ExecProc,
    Input, Output, sync, comb, ExecSync, ExecComb, invariant,
    inst, tuple
)
from .types import *
from .tlm import *
from . import ir
from . import profiles
from .data_model_factory import DataModelFactory
from .rt.edge import posedge, negedge, edge
from typing import Type

__all__ = [
    # From asyncio
    'aEvent',
    # From decorators
    'dataclass', 'field', 'process', 'input', 'output',
    'const', 'bundle', 'mirror', 'monitor',
    'port', 'export', 'bind', 'Exec', 'ExecKind', 'ExecProc',
    'Input', 'Output', 'sync', 'comb', 'ExecSync', 'ExecComb', 'invariant',
    'inst', 'tuple',
    # From types (re-exported via *)
    'AddrHandle', 'AddressSpace', 'Bundle', 'ClaimPool', 'CompImpl', 'Component',
    'Extern', 'ListPool', 'Lock', 'MemIF', 'Memory', 'PackedStruct', 'Pool',
    'Reg', 'RegFifo', 'RegFile', 'SignWidth', 'Struct', 'Time', 'TimeUnit',
    'Timebase', 'TypeBase', 'XtorComponent',
    'bit', 'bit1', 'bit16', 'bit2', 'bit3', 'bit32', 'bit4', 'bit5', 'bit6',
    'bit64', 'bit7', 'bit8', 'bitv', 'bv',
    'i128', 'i16', 'i32', 'i64', 'i8',
    'int128_t', 'int16_t', 'int32_t', 'int64_t', 'int8_t',
    'u1', 'u10', 'u11', 'u12', 'u128', 'u13', 'u14', 'u15', 'u16', 'u17', 'u18',
    'u19', 'u2', 'u20', 'u21', 'u22', 'u23', 'u24', 'u25', 'u26', 'u27', 'u28',
    'u29', 'u3', 'u30', 'u31', 'u32', 'u4', 'u5', 'u6', 'u64', 'u7', 'u8', 'u9',
    'uint10_t', 'uint11_t', 'uint128_t', 'uint12_t', 'uint13_t', 'uint14_t',
    'uint15_t', 'uint16_t', 'uint17_t', 'uint18_t', 'uint19_t', 'uint1_t',
    'uint20_t', 'uint21_t', 'uint22_t', 'uint23_t', 'uint24_t', 'uint25_t',
    'uint26_t', 'uint27_t', 'uint28_t', 'uint29_t', 'uint2_t', 'uint30_t',
    'uint31_t', 'uint32_t', 'uint3_t', 'uint4_t', 'uint5_t', 'uint64_t',
    'uint6_t', 'uint7_t', 'uint8_t', 'uint9_t', 'width',
    # From tlm (re-exported via *)
    'Channel', 'GetIF', 'PutIF', 'ReqRspChannel', 'ReqRspIF', 'Transport',
    # From rt.edge
    'posedge', 'negedge', 'edge',
    # Submodules
    'ir', 'profiles',
    # Other exports
    'DataModelFactory', 'Event',
]

@dataclass
class Event(aEvent):
    """Supports interrupt functionality in Zuspec"""

    # Specifies a method that is invoked when the event is set.
    # Use 'bind' to associate a callback with this
    at: Callable = field(init=False)

    def __new__(cls, **kwargs):
        from .config import Config
        ret = Config.inst().factory.mkEvent(cls, **kwargs)
        return ret





