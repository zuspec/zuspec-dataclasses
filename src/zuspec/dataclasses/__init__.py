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
``zuspec.dataclasses`` — RTL behavioral modeling and async pipeline DSL.

This package provides a Python-native way to describe hardware components,
processes, and pipelines for both behavioral simulation and RTL synthesis.

Core API
--------
``@zdc.dataclass`` / ``@zdc.field``
    Declare a hardware component with typed ports and fields.

``@zdc.sync`` / ``@zdc.comb``
    Synchronous (clocked) and combinational process decorators.

``zdc.pipeline``
    Async pipeline DSL singleton — the entry point for the behavioral
    pipeline model.  Replaces the removed ``@zdc.stage`` API.

Async Pipeline Quick-Start
--------------------------
::

    @zdc.dataclass
    class Adder(zdc.Component):
        clock: zdc.bit = zdc.input()
        a_in:  zdc.u32 = zdc.input()
        b_in:  zdc.u32 = zdc.input()
        out:   zdc.u32 = zdc.output()

        @zdc.pipeline(clock=lambda s: s.clock)
        async def run(self):
            async with zdc.pipeline.stage() as FETCH:
                a, b = self.a_in, self.b_in
            async with zdc.pipeline.stage() as COMPUTE:
                result = a + b
            async with zdc.pipeline.stage() as WB:
                self.out = result

Hazard Tracking
---------------
::

    rf = zdc.pipeline.resource(32, lock=zdc.BypassLock())

    # Inside a @zdc.pipeline method:
    await zdc.pipeline.reserve(self.rf[rd])     # claim write slot (IF)
    val = await zdc.pipeline.block(self.rf[rs]) # wait for RAW hazard (ID)
    zdc.pipeline.write(self.rf[rd], result)     # bypass forward (EX)
    zdc.pipeline.release(self.rf[rd])           # relinquish claim (WB)

Lock strategies: :class:`QueueLock` (stall, no bypass),
:class:`BypassLock` (stall + bypass network), :class:`RenameLock`
(Tomasulo-style out-of-order rename).

Trace / Observer
----------------
After ``asyncio.run(comp.wait(...))``, access ``comp.<method>_trace`` for a
:class:`~zuspec.dataclasses.rt.pipeline_rt.PipelineTrace` with Gantt output::

    comp.run_trace.add_observer(lambda tok, ev, **kw: ...)
    comp.run_trace.print_trace()
"""

# Datamodel Mapping
# 

from asyncio import Event as aEvent
from typing import Callable
from .decorators import (
    dataclass, field, process, input, output, reg, array,
    const, bundle, mirror, monitor,
    port, export, bind, Exec, ExecKind, ExecProc,
    Input, Output, RegField, sync, comb, ExecSync, ExecComb, invariant,
    inst, tuple, view, constraint, rand, randc,
    lock, share, extend, pool, flow_output, flow_input,
    indexed_regfile,
    indexed_pool,

)
from .constraint_helpers import implies, dist, unique, sum, ascending, descending, solve_order
from .constraint_parser import ConstraintParser, extract_rand_fields
from .activity_parser import ActivityParser, ActivityParseError
from .pragma import scan_pragmas, parse_pragma_str, scan_line_comments
from .activity_dsl import (
    do, parallel, schedule, sequence, atomic, select, branch,
    do_while, while_do, replicate, constraint as activity_constraint, bind as activity_bind
)
from .types import *
from .tlm import *
# Re-import after `from .types import *` to ensure our decorator wins over
# the stdlib `enum` module that `types.py` imports into its namespace.
from .decorators import enum
from . import ir
from . import profiles
from . import transform
from .data_model_factory import DataModelFactory
from .rt.edge import posedge, negedge, edge
from .rt.gather import gather
from .rt.scenario_runner import ScenarioRunner, run_action, run_action_sync, DeadlockError
from .rt.resource_rt import get_resource_fields, acquire_resources, release_resources, make_resource
from .rt.binding_solver import BindingSolver
from .rt.flow_obj_rt import BufferInstance, StreamInstance, StatePool
from .rt.activity_runner import ScheduleGraph
from .rt.indexed_regfile_rt import IndexedRegFileRT, IndexedRegFileClaim
from .rt.indexed_pool_rt import IndexedPoolRT
from .rt.memory_rt import MemoryRT
from .rt.simulate import simulate
from .rt.sim_domain import SimDomain
from .solver.api import randomize, randomize_with, RandomizationError
from .errors import (
    ZuspeccError, ZuspeccCDCError, ZuspeccWidthError,
    ZuspeccSynthError, ZuspeccConflictError,
)
from .coverage import (
    Covergroup, coverpoint, cross,
    binsof, cross_bins, cross_ignore, cross_illegal
)
from .domain import (
    ClockDomain, DerivedClockDomain, InheritedDomain,
    ResetDomain, SoftwareResetDomain, HardwareResetDomain,
    ClockPort, ClockBind, ResetBind,
    clock_port, clock_bind, reset_bind,
    clock_domain,
)
from .cdc import TwoFFSync, AsyncFIFO, cdc_unchecked
from .pipeline_ns import pipeline, _StageHandle, _Snap
from .pipeline_locks import HazardLock, QueueLock, BypassLock, RenameLock
from .pipeline_resource import PipelineResource
from .method_port import InPort, OutPort, in_port, out_port
from typing import Type

__all__ = [
    # From asyncio
    'aEvent',
    # From decorators
    'dataclass', 'field', 'process', 'input', 'output', 'reg', 'array',
    'const', 'bundle', 'mirror', 'monitor',
    'port', 'export', 'bind', 'Exec', 'ExecKind', 'ExecProc',
    'Input', 'Output', 'RegField', 'sync', 'comb', 'ExecSync', 'ExecComb', 'invariant',
    'inst', 'tuple', 'view', 'constraint', 'rand', 'randc',
    'lock', 'share', 'extend', 'pool', 'flow_output', 'flow_input',
    'enum',
    # Pipeline process API — new async API
    'pipeline', '_StageHandle', '_Snap',
    'HazardLock', 'QueueLock', 'BypassLock', 'RenameLock',
    'PipelineResource',
    # Method ports
    'InPort', 'OutPort', 'in_port', 'out_port',
    # Clock domain field factory
    'clock_domain',
    # From solver API
    'randomize', 'randomize_with', 'RandomizationError',
    # From errors
    'ZuspeccError', 'ZuspeccCDCError', 'ZuspeccWidthError',
    'ZuspeccSynthError', 'ZuspeccConflictError',
    # From coverage
    'Covergroup', 'coverpoint', 'cross',
    # From constraint_helpers
    'implies', 'dist', 'unique', 'sum', 'ascending', 'descending', 'solve_order',
    # From constraint_parser
    'ConstraintParser', 'extract_rand_fields',
    # From activity_parser
    'ActivityParser', 'ActivityParseError',
    'scan_pragmas', 'parse_pragma_str', 'scan_line_comments',
    # From activity_dsl
    'do', 'parallel', 'schedule', 'sequence', 'atomic', 'select', 'branch',
    'do_while', 'while_do', 'replicate',
    # From types (re-exported via *)
    'Action',
    'Buffer', 'Stream', 'State', 'Resource',
    'AddrHandle', 'AddressSpace', 'Array', 'BackdoorMemory', 'BackdoorRegFile',
    'Bundle', 'ClaimContext', 'ClaimPool', 'CompImpl', 'Component',
    'Extern', 'ListPool', 'Lock', 'MemIF', 'Memory', 'PackedStruct', 'Pool',
    'Reg', 'RegFifo', 'RegFile', 'SignWidth', 'Struct', 'Time', 'TimeUnit',
    'Timebase', 'TypeBase', 'Uptr', 'XtorComponent',
    'bit', 'bit1', 'bit16', 'bit2', 'bit3', 'bit32', 'bit4', 'bit5', 'bit6',
    'bit64', 'bit7', 'bit8', 'bitv', 'bv',
    'b', 'b2', 'b3', 'b4', 'b8', 'b16', 'b32', 'b64',
    'bv1', 'bv2', 'bv3', 'bv4', 'bv5', 'bv6', 'bv7', 'bv8',
    'bv9', 'bv10', 'bv11', 'bv12', 'bv13', 'bv14', 'bv15', 'bv16',
    'bv17', 'bv18', 'bv19', 'bv20', 'bv21', 'bv22', 'bv23', 'bv24',
    'bv25', 'bv26', 'bv27', 'bv28', 'bv29', 'bv30', 'bv31', 'bv32',
    'bv64', 'bv128',
    'concat',
    'i128', 'i16', 'i32', 'i64', 'i8',
    's8', 's16', 's32', 's64', 's128',
    'sext', 'zext',
    'int128_t', 'int16_t', 'int32_t', 'int64_t', 'int8_t',
    'u1', 'u10', 'u11', 'u12', 'u128', 'u13', 'u14', 'u15', 'u16', 'u17', 'u18',
    'u19', 'u2', 'u20', 'u21', 'u22', 'u23', 'u24', 'u25', 'u26', 'u27', 'u28',
    'u29', 'u3', 'u30', 'u31', 'u32', 'u4', 'u5', 'u6', 'u64', 'u7', 'u8', 'u9',
    'uint10_t', 'uint11_t', 'uint128_t', 'uint12_t', 'uint13_t', 'uint14_t',
    'uint15_t', 'uint16_t', 'uint17_t', 'uint18_t', 'uint19_t', 'uint1_t',
    'uint20_t', 'uint21_t', 'uint22_t', 'uint23_t', 'uint24_t', 'uint25_t',
    'uint26_t', 'uint27_t', 'uint28_t', 'uint29_t', 'uint2_t', 'uint30_t',
    'uint31_t', 'uint32_t', 'uint3_t', 'uint4_t', 'uint5_t', 'uint64_t',
    'uint6_t', 'uint7_t', 'uint8_t', 'uint9_t', 'uptr', 'width',
    # From tlm (re-exported via *)
    'Channel', 'GetIF', 'PutIF', 'ReqRspChannel', 'ReqRspIF', 'Transport',
    # From rt.edge
    'posedge', 'negedge', 'edge',
    # From rt.scenario_runner
    'ScenarioRunner', 'run_action', 'run_action_sync', 'DeadlockError',
    # From rt.flow_obj_rt
    'BufferInstance', 'StreamInstance', 'StatePool',
    # From rt.activity_runner
    'ScheduleGraph',
    # From rt.indexed_regfile_rt
    'IndexedRegFileRT', 'IndexedRegFileClaim',
    # From rt.memory_rt
    'MemoryRT',
    # From rt.simulate
    'simulate',
    # From rt.sim_domain
    'SimDomain',
    # From domain
    'ClockDomain', 'DerivedClockDomain', 'InheritedDomain',
    'ResetDomain', 'SoftwareResetDomain', 'HardwareResetDomain',
    'ClockPort', 'ClockBind', 'ResetBind',
    'clock_port', 'clock_bind', 'reset_bind',
    # From cdc
    'TwoFFSync', 'AsyncFIFO', 'cdc_unchecked',
    # Submodules
    'ir', 'profiles',
    # Other exports
    'DataModelFactory', 'Event', 'cycles',
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


class _CyclesAwaitable:
    """Awaitable object representing a wait for N clock cycles.
    
    This is used in sync processes to introduce state boundaries:
        await zdc.cycles(1)  # Wait one clock cycle
        await zdc.cycles(4)  # Wait four clock cycles
    
    The SPRTL transformation pass converts these to FSM state transitions.
    """
    def __init__(self, n: int):
        if n < 1:
            raise ValueError(f"cycles() requires n >= 1, got {n}")
        self.n = n
    
    def __await__(self):
        # This is a placeholder for synthesis - actual runtime would need
        # an event loop integration. For now, just yield control.
        yield self
        return None
    
    def __repr__(self):
        return f"cycles({self.n})"


def cycles(n: int = 1) -> _CyclesAwaitable:
    """Wait for N clock cycles in a synchronous process.
    
    Used within @zdc.sync decorated methods to introduce explicit
    clock cycle boundaries, which translate to FSM state transitions.
    
    Args:
        n: Number of clock cycles to wait (default: 1)
        
    Returns:
        An awaitable that represents waiting for N cycles
        
    Example:
        @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
        async def process(self):
            while True:
                self.data = self.input
                await zdc.cycles(1)  # State boundary
                self.output = self.data * 2
                await zdc.cycles(1)  # Another state boundary
    """
    return _CyclesAwaitable(n)



