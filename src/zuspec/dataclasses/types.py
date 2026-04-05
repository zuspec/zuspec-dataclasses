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
# distributed under the leverages these projectsLicense is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#****************************************************************************
from __future__ import annotations
import abc
import dataclasses as dc
import enum
import random
import typing
from typing import (
    Callable, cast, ClassVar, Dict, Generic, List, Optional, TypeVar, 
    Literal, Type, Annotated, Protocol, Any, SupportsInt, Union, Tuple, 
    Self, Union, Awaitable)
from .decorators import dataclass, field, export


@dc.dataclass
class TypeBase(object):
    """Marker for all Zuspec types"""
    def __new__(cls, *args, **kwargs):
        pass
    pass

@dc.dataclass
class SignWidth(object):
    width : int = dc.field()
    signed : bool = dc.field(default=True)

# class SignedWidthMeta(type):

#     def __new__(cls, *args, **kwargs):
#         pass

#     def __getitem__(self, v):
#         pass

@dc.dataclass
class S(SignWidth): pass

@dc.dataclass
class U(SignWidth):
    def __post_init__(self):
        # signed for U types is always False
        self.signed = False

@dc.dataclass
class Uptr(object):
    """Marker for platform-sized unsigned pointer type.
    
    The width is determined at runtime based on the platform's pointer size.
    This is equivalent to an unsigned integer large enough to hold an address.
    """
    signed : bool = dc.field(default=False)
    
    @staticmethod
    def get_platform_width() -> int:
        """Get the platform's pointer size in bits."""
        import struct
        return struct.calcsize('P') * 8

class TimeUnit(enum.IntEnum):
    S = 1
    MS = -3
    US = -6
    NS = -9
    PS = -12
    FS = -15

@dc.dataclass
class Time(object):
    unit : TimeUnit = dc.field()
    amt : float = dc.field()
    _delta : ClassVar = None

    @classmethod
    def delta(cls):
        if cls._delta is None:
            cls._delta = Time(TimeUnit.S, 0)
        return cls._delta

    @classmethod
    def s(cls, amt : float):
        return Time(TimeUnit.S, amt)
    
    def as_s(self) -> float:
        return self._convert_to_unit(TimeUnit.S)
    
    def as_ms(self) -> float:
        return self._convert_to_unit(TimeUnit.MS)
    
    def as_us(self) -> float:
        return self._convert_to_unit(TimeUnit.US)
    
    def as_ns(self) -> float:
        return self._convert_to_unit(TimeUnit.NS)
    
    def as_ps(self) -> float:
        return self._convert_to_unit(TimeUnit.PS)
    
    def as_fs(self) -> float:
        return self._convert_to_unit(TimeUnit.FS)

    @classmethod
    def ms(cls, amt : float):
        return Time(TimeUnit.MS, amt)

    @classmethod
    def us(cls, amt : float):
        return Time(TimeUnit.US, amt)

    @classmethod
    def ns(cls, amt : float):
        return Time(TimeUnit.NS, amt)

    @classmethod
    def ps(cls, amt : float):
        return Time(TimeUnit.PS, amt)

    @classmethod
    def fs(cls, amt : float):
        return Time(TimeUnit.FS, amt)
    
    def __mul__(self, o : Union[int, float, 'Time']) -> 'Time':
        """Multiply time by a scalar or another Time value.
        
        Args:
            o: Either a numeric scalar (int/float) or another Time value
            
        Returns:
            New Time value with the result. When multiplying two Time values,
            the result uses the finer (smaller) time unit.
        """
        if isinstance(o, (int, float)):
            # Scalar multiplication: keep same unit, multiply amount
            return Time(self.unit, self.amt * o)
        elif isinstance(o, Time):
            # Time * Time: convert to common unit and multiply
            # Use the finer (smaller) unit for the result
            # Finer unit has smaller exponent (more negative)
            def get_exponent(unit: TimeUnit) -> int:
                if unit == TimeUnit.S:
                    return 0
                return unit.value
            
            self_exp = get_exponent(self.unit)
            o_exp = get_exponent(o.unit)
            
            # Smaller exponent = finer unit
            if self_exp <= o_exp:
                result_unit = self.unit
            else:
                result_unit = o.unit
            
            # Convert both to the result unit and multiply
            self_in_result = self._convert_to_unit(result_unit)
            o_in_result = o._convert_to_unit(result_unit)
            
            return Time(result_unit, self_in_result * o_in_result)
        else:
            return NotImplemented
    
    def __rmul__(self, o : Union[int, float]) -> 'Time':
        """Right multiplication for scalar * Time."""
        return self.__mul__(o)
    
    def _convert_to_unit(self, target_unit: TimeUnit) -> float:
        """Convert this time's amount to a different unit.
        
        Args:
            target_unit: The unit to convert to
            
        Returns:
            The amount in the target unit
        """
        # TimeUnit values: S=1 (represents 10^0), MS=-3 (10^-3), US=-6 (10^-6), etc.
        # S=1 is a special case - treat it as exponent 0
        def get_exponent(unit: TimeUnit) -> int:
            if unit == TimeUnit.S:
                return 0
            return unit.value
        
        self_exp = get_exponent(self.unit)
        target_exp = get_exponent(target_unit)
        power_diff = self_exp - target_exp
        return self.amt * (10 ** power_diff)

    def __str__(self) -> str:
        unit_str = {
            TimeUnit.S: 's',
            TimeUnit.MS: 'ms',
            TimeUnit.US: 'us',
            TimeUnit.NS: 'ns',
            TimeUnit.PS: 'ps',
            TimeUnit.FS: 'fs'
        }
        return f"{self.amt}{unit_str[self.unit]}"

class Timebase(Protocol):
    async def wait(self, amt : Optional[Time] = None): 
        """Suspends the calling coroutine until the specified
        time has elapsed (None==delta)
        """
        ...

    def after(self, amt : Optional[Time], call : Callable): 
        """Schedules 'call' to be invoke at 'amt' in the future"""
        ...

    def time(self) -> Time: 
        """Returns the current time"""
        ...


class CompImpl(Protocol):

    def name(self) -> str: ...

    def parent(self) -> Component: ...

    def post_init(self, comp): ...

    def handle_setattr(self, comp: Component, name: str, value): ...

    def timebase(self) -> Timebase: ... 

    def shutdown(self): ...

    async def wait(self, comp: Component, amt: Time = None): ...

    def time(self) -> Time: ...

class Extern[T](Protocol):
    """Marks an extern ref. The type parameter specifies the
    Zuspec type"""

    def __implementation__(self) -> Dict[str, Any]:
        ...

@dc.dataclass(kw_only=True, frozen=True)
class Attr(object):
    """Base class for attributes"""
    pass

@dc.dataclass(kw_only=True, frozen=True)
class Label(Attr):
    """Attribute class for applying a label"""
    name : str = dc.field()


def attr(attr_t : Attr):
    """Function that can act as a decorator. """
    def _wrapper(*args, **kwargs):
        # In the decorator flavor, return the decorated type
        return args[0]
    # Note: when used as a function, the return isn't useful
    return _wrapper


@dc.dataclass
class AnnotationFileSet(object):
    filetype: str = dc.field()
    basedir: str = dc.field()
    incdirs: Set[str] = dc.field(default_factory=set)
    defines: Set[str] = dc.field(default_factory=set)
    files: List[str] = dc.field(default_factory=list)


class PackedStruct(TypeBase,SupportsInt):

    def __int__(self) -> int:
        return -1

    pass


class Struct(TypeBase):

    def pre_solve(self):
        pass

    def post_solve(self):
        pass

    pass


class Buffer(Struct):
    """PSS buffer flow-object base type.

    A buffer is produced by one action and consumed by another.
    Use ``zdc.output()`` / ``zdc.input()`` to declare buffer fields on actions.
    """
    pass


class Stream(Struct):
    """PSS stream flow-object base type.

    A stream is a directional, ordered sequence of data items between actions.
    Use ``zdc.output()`` / ``zdc.input()`` to declare stream fields on actions.
    """
    pass


class State(Struct):
    """PSS state flow-object base type.

    A state persists across action traversals.  The ``initial`` attribute is
    ``True`` when the state has not yet been written by any action.
    """
    initial: bool = False


class Resource(Struct):
    """PSS resource base type.

    Resources are claimed by actions via ``zdc.lock()`` (exclusive) or
    ``zdc.share()`` (shared).  The ``instance_id`` attribute is assigned by
    the pool when the resource is allocated.
    """
    instance_id: int = 0


class Bundle(TypeBase):
    """Bundle base class for interface/port collections with directionality.
    
    Bundles are used to group related signals (inputs/outputs) that form
    a coherent interface. They support parameterization via const fields.
    
    Example:
        @zdc.dataclass
        class MyBus(zdc.Bundle):
            WIDTH : zdc.u32 = zdc.const(default=32)
            data : zdc.bitv = zdc.output(width=lambda s:s.WIDTH)
            valid : zdc.bit = zdc.output()
    """
    pass

@dc.dataclass
class Component(TypeBase):
    """
    Component classes are structural in nature. 
    The lifecycle of a component tree is as follows:
    - The root component and fields of component type are constructed
    - The 'init_down' method is invoked in a depth-first manner
    - The 'init_up' method is invoked

    A Component class supports the following decorated methods:
    - sync
    - constraint
    - activity
    """

    _impl : Optional[CompImpl] = dc.field(default=None)

    def __post_init__(self):
        if self._impl is not None:
            self._impl.post_init(self)
    
    def __setattr__(self, name: str, value):
        if name.startswith('_'):
            object.__setattr__(self, name, value)
            return
        
        impl = object.__getattribute__(self, '_impl')
        if impl is not None:
            impl.handle_setattr(self, name, value)
        else:
            object.__setattr__(self, name, value)

    def shutdown(self):
        assert self._impl is not None
        self._impl.shutdown()

    @property
    def name(self) -> str:
        assert self._impl is not None
        return self._impl.name

    @property
    def parent(self) -> Optional[Component]:
        assert self._impl is not None
        return self._impl.parent

    def __bind__(self) -> Optional[Union[Dict,Tuple]]: 
        pass

    async def wait(self, amt : Time = None):
        assert self._impl is not None
        await self._impl.wait(self, amt)

    def time(self) -> Time: 
        assert self._impl is not None
        return self._impl.time()

    def __new__(cls, **kwargs):
        from .config import Config
        if "_impl" not in kwargs.keys():
            ret = Config.inst().factory.mkComponent(cls, **kwargs)
        else:
            ret = object.__new__(cls)
        return ret
    
def _find_comp_instances(comp: 'Component', comp_type: type) -> list:
    """Recursively find all instances of comp_type within a component's fields."""
    result = []
    try:
        fields = dc.fields(comp)
    except TypeError:
        return result
    for f in fields:
        if f.name.startswith('_'):
            continue
        val = getattr(comp, f.name, None)
        if val is None:
            continue
        if isinstance(val, comp_type):
            result.append(val)
        elif isinstance(val, Component):
            result.extend(_find_comp_instances(val, comp_type))
    return result


@dc.dataclass
class Action[T]:
    comp: T = field()

    async def __call__(self, comp: Optional['Component'] = None) -> Self:
        from .rt.activity_runner import ActivityRunner
        from .rt.action_context import ActionContext
        from .rt.pool_resolver import PoolResolver
        import dataclasses as dc
        import random

        resolver = PoolResolver.build(comp)
        ctx = ActionContext(
            action=None,
            comp=comp,
            pool_resolver=resolver,
            seed=random.randrange(2**32),
        )
        traversed = await ActivityRunner()._traverse(type(self), [], ctx)
        # Copy fields from the traversed instance back onto self
        try:
            for f in dc.fields(traversed):
                object.__setattr__(self, f.name, getattr(traversed, f.name))
        except TypeError:
            pass
        return self

    async def activity(self) -> None:
        self.pre_solve()
        self.post_solve()
        await self.body()

    def pre_solve(self) -> None:
        pass

    def post_solve(self) -> None:
        pass

    async def body(self) -> None:
        pass


@dc.dataclass
class XtorComponent[T](Component):
    """A Transactor component has a single-level interface and an 
    operation-level interface"""
    xtor_if : T = export()

class Pool[T](Protocol):
    pass

# Selection
# - Allow consumer to filter allowed items (pool determines selection)
# - Allow consumer to select from acceptable items (pool delegates selection)
# - Consumer must deem acceptable
# - Pool 

class BufferPool[T](Pool[T]):

    async def get(self, 
                  where : Optional[Callable[[T],bool]] = None,
                  select : Optional[Callable[[List[T]],Awaitable[T]]] = None) -> T:
        """Get an item from the pool using optional filter and selection functions"""
        ...

    def put(self, item : T):
        """Add a new item to the pool"""
        ...

    @staticmethod
    def fromList(items: List[T]) -> BufferPool[T]:
        from .rt.list_buffer_pool import ListBufferPool
        return ListBufferPool[T](items)


# Various 'policy' classes
# - Must implement 'get'
# - May accept other arguments (pool size, constructor, etc)

class Claim[T](Protocol):
    """Handle to a specific claim managed by a ClaimPool"""

    @property
    def id(self) -> int:
        ...

    @property
    def t(self) -> T:
        ...

    @t.setter
    def t(self, v: T):
        ...

    def drop(self):
        """Release the claimed resource back to the pool"""
        ...


class ClaimContext[T]:
    """Dual-mode claim handle returned by :meth:`ClaimPool.lock` and
    :meth:`ClaimPool.share`.

    Supports two equivalent usage patterns:

    **Explicit await** (manual release required)::

        claim = await comp.alu_pool.lock()
        result = await claim.t.execute(op, rs1, rs2)
        comp.alu_pool.drop(claim)

    **Async context manager** (auto-release on exit, preferred)::

        async with comp.alu_pool.lock() as claim:
            result = await claim.t.execute(op, rs1, rs2)
        # claim released automatically, even if an exception is raised

    Both forms call the same underlying ``_acquire_coro`` coroutine, so
    the two styles are fully interchangeable at the call site.
    """

    def __init__(self, pool: 'ClaimPool[T]', acquire_coro) -> None:
        self._pool = pool
        self._acquire_coro = acquire_coro   # a 0-arg async callable
        self._claim: Optional['Claim[T]'] = None

    # ------------------------------------------------------------------
    # Awaitable protocol — for:  claim = await pool.lock()
    # ------------------------------------------------------------------
    def __await__(self):
        return self._acquire_coro().__await__()

    # ------------------------------------------------------------------
    # Async context-manager protocol — for:  async with pool.lock() as c:
    # ------------------------------------------------------------------
    async def __aenter__(self) -> 'Claim[T]':
        self._claim = await self._acquire_coro()
        return self._claim

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._claim is not None:
            self._pool.drop(self._claim)
            self._claim = None
        return False   # do not suppress exceptions


class ClaimPool[T](Pool[T]):
    """Manages a pool of claimable resources.

    Both ``lock()`` and ``share()`` return a :class:`ClaimContext` that
    supports either ``await`` or ``async with``::

        # explicit await + manual drop
        claim = await pool.lock()
        ...
        pool.drop(claim)

        # async context manager — preferred; auto-drops on exit
        async with pool.lock() as claim:
            ...
    """

    @abc.abstractmethod
    async def _lock_coro(
            self,
            claim_id: Optional[Any] = None,
            filter: Optional[Callable[[T, int], bool]] = None) -> 'Claim[T]':
        """Internal coroutine that performs the exclusive acquire.

        Subclasses implement this; callers use :meth:`lock` instead.
        """
        ...

    @abc.abstractmethod
    async def _share_coro(
            self,
            claim_id: Optional[Any] = None,
            filter: Optional[Callable[[T, int], bool]] = None) -> 'Claim[T]':
        """Internal coroutine that performs the shared acquire.

        Subclasses implement this; callers use :meth:`share` instead.
        """
        ...

    def lock(
            self,
            claim_id: Optional[Any] = None,
            filter: Optional[Callable[[T, int], bool]] = None) -> 'ClaimContext[T]':
        """Acquire a resource exclusively.

        Returns a :class:`ClaimContext` usable as either an awaitable or
        an async context manager (see class docstring).
        """
        return ClaimContext(self, lambda: self._lock_coro(claim_id, filter))

    def share(
            self,
            claim_id: Optional[Any] = None,
            filter: Optional[Callable[[T, int], bool]] = None) -> 'ClaimContext[T]':
        """Acquire a resource non-exclusively (shared read).

        Returns a :class:`ClaimContext` usable as either an awaitable or
        an async context manager.
        """
        return ClaimContext(self, lambda: self._share_coro(claim_id, filter))

    def drop(self, claim: 'Claim[T]'):
        """Release a claim obtained via the explicit-await form.

        Not needed when using ``async with`` — the context manager calls
        this automatically.
        """
        ...

    @staticmethod
    def fromList(resources: List[T]) -> 'ClaimPool[T]':
        """Returns a ClaimPool populated by *resources*."""
        from .rt.list_claim_pool import ListClaimPool
        return ListClaimPool(resources)

class Lock(Protocol):
    """A mutex lock for coordinating access to shared resources.
    
    This is a protocol defining the interface for lock objects.
    The runtime implementation is provided by the ObjFactory.
    """
    
    async def acquire(self):
        """Acquire the lock. Blocks until the lock is available."""
        ...
    
    def release(self):
        """Release the lock."""
        ...

    async def __aenter__(self):
        """Context manager to acquire the lock"""
        ...

    async def __aexit__(self, e, v, tb):
        """Context manager exit"""
        ...


class IndexedClaim(Protocol):
    """Handle to an in-flight register file access.

    ``idx``  — register identity; a constrained-random integer whose value is
               determined by the instruction decoder at elaboration time.
               MLS uses this for hazard comparator generation.
    ``data`` — read result (for reads) or write payload (for writes).
    ``kind`` — ``'read'`` or ``'write'``; determines which hazard category
               applies when this claim overlaps with another.
    """
    idx:  int
    data: int
    kind: str   # 'read' | 'write'


class IndexedRegFile[TIdx, TData](Protocol):
    """Register file resource with explicit port count and topology.

    ``read_ports``  — number of independent read port slots.  Each slot is
                      exclusive per cycle (``lock`` semantics).  Multiple
                      concurrent reads are expressed through slot count, not
                      slot-sharing; ``share`` semantics do not apply to
                      physical register file ports.
    ``write_ports`` — number of independent write port slots.
    ``shared_port`` — if ``True``, read and write claims draw from the *same*
                      slot pool; a read and a write cannot occur in the same
                      cycle (true single-port BRAM mode).
                      if ``False`` (default), reads and writes use independent
                      slot pools and can proceed concurrently on separate
                      physical buses.

    MLS uses ``read_ports`` / ``write_ports`` to generate addr/data wire
    groups on the synthesised register file module, and ``shared_port`` to
    decide whether forwarding muxes (separate ports) or stall logic (shared
    port) are needed for RAW hazard resolution.
    """
    read_ports:  int
    write_ports: int
    shared_port: bool

    def read(self, idx: int) -> Any:
        """Claim one read port slot for register ``idx``.

        Returns an async context manager that yields the register value::

            async with regfile.read(d.rs1) as rs1_val:
                ...  # rs1_val holds the current value of regs[d.rs1]

        Reading register 0 (x0) always yields 0 without consuming a slot.
        """
        ...

    async def read_all(self, *indices: int) -> tuple:
        """Read multiple registers, obeying port-count constraints.

        All reads are launched concurrently via ``asyncio.gather``.  When the
        number of indices exceeds ``read_ports``, the semaphore naturally
        serializes them in batches — so the call always succeeds regardless of
        how many registers are requested::

            rs1v, rs2v = await regfile.read_all(d.rs1, d.rs2)

        Reading register 0 (x0) always yields 0 without consuming a slot.

        Returns a tuple of values in the same order as *indices*.
        """
        ...

    def write(self, idx: int, val: int) -> Any:
        """Claim one write port slot to write ``val`` into register ``idx``.

        Returns an async context manager::

            async with regfile.write(d.rd, result):
                pass  # write is committed when the context exits

        Writing register 0 (x0) is a no-op; no slot is consumed.
        """
        ...


class BackdoorRegFile(Protocol):
    """Backdoor (non-port-constrained) read/write access to a register file.

    Both the Python runtime (``IndexedRegFileRT``) and the C-backed proxy
    (``_RegFileProxy``) implement this protocol.  Tests and testbench code
    should type-annotate against ``BackdoorRegFile`` so they are backend-agnostic.

    Example::

        regfile: BackdoorRegFile = core.regfile
        regfile.set(5, 0xDEAD)
        assert regfile.get(5) == 0xDEAD
        vals = regfile.get_all()   # list of all register values
    """

    def get(self, idx: int) -> int:
        """Read register *idx* directly, bypassing port constraints."""
        ...

    def set(self, idx: int, val: int) -> None:
        """Write *val* into register *idx*, bypassing port constraints.

        Writing register 0 (x0) is a no-op (hardwired-zero convention).
        """
        ...

    def get_all(self) -> "list[int]":
        """Return all register values as a plain list (index 0 first)."""
        ...


class BackdoorMemory(Protocol):
    """Backdoor byte-level read/write access to a memory primitive.

    Both a Python ``MemoryRT`` and the C-backed ``MemoryProxy`` implement this
    protocol so tests can be written once and run against either backend.

    Example::

        mem: BackdoorMemory = testbench.mem
        mem.write_bytes(0x1000, bytes([0x93, 0x00, 0x00, 0x00]))
        data = mem.read_bytes(0x1000, 4)
    """

    def read_bytes(self, addr: int, length: int) -> bytes:
        """Read *length* bytes starting at *addr*."""
        ...

    def write_bytes(self, addr: int, data: "bytes | bytearray") -> None:
        """Write *data* bytes starting at *addr*."""
        ...


class IndexedPool[TIdx](Protocol):
    """Indexed resource pool with per-slot lock / share semantics.

    Models a *scoreboard* or any resource where in-flight operations are
    tracked per index value.  The MLS synthesis engine uses lock / share
    pairs to detect data hazards between concurrent action instances and
    to generate stall or forwarding logic.

    Two access modes:

    ``lock(idx)``
        Exclusive claim on slot *idx*.  Blocks until all current locks and
        shares on *idx* have been released.  Typically used by the producer
        action to reserve a write destination.

    ``share(idx)``
        Shared claim on slot *idx*.  Multiple concurrent shares are allowed;
        a share is blocked only while a lock on the same *idx* is held.
        Typically used by consumer actions to declare a read dependency.

    MLS analysis rules
    ------------------
    Given two concurrent action instances A and B:

    * ``A.lock(a)`` and ``B.share(b)`` where *a* and *b* are constrained-
      random — **RAW hazard**: generate comparator ``a == b``; if true,
      schedule B after A or insert forwarding.
    * ``A.lock(a)`` and ``B.lock(b)`` — **WAW hazard**: generate comparator;
      if true, serialize writes.
    * ``A.share(a)`` and ``B.share(b)`` — no hazard.

    The *noop_idx* parameter designates one index value as a structural no-op
    (e.g. RISC-V ``x0``).  Lock and share on *noop_idx* complete immediately
    without acquiring any slot — no hazard comparators are generated for it.

    Example — RISC-V integer scoreboard::

        # Component declaration
        rd_sched: IndexedPool[zdc.u5] = zdc.indexed_pool(depth=32, noop_idx=0)

        # In ExecuteInstruction.body() — producer reserves rd,
        # consumer reads are gated by prior lock on same register
        async with self.comp.rd_sched.share(d.rs1), \\
                   self.comp.rd_sched.share(d.rs2):
            rs1v, rs2v = await self.comp.regfile.read_all(d.rs1, d.rs2)

        async with self.comp.rd_sched.lock(d.rd):
            result = compute(rs1v, rs2v)
            async with self.comp.regfile.write(d.rd, result):
                pass
    """

    def lock(self, idx: int) -> Any:
        """Exclusive claim on slot *idx*.

        Returns an async context manager::

            async with pool.lock(d.rd):
                ...  # rd is reserved; no other action can lock or share it

        If *idx* equals *noop_idx*, returns immediately without blocking.
        """
        ...

    def share(self, idx: int) -> Any:
        """Shared claim on slot *idx*.

        Returns an async context manager::

            async with pool.share(d.rs1):
                ...  # blocked while another action holds lock(rs1)

        Multiple concurrent shares on the same *idx* are allowed.
        If *idx* equals *noop_idx*, returns immediately without blocking.
        """
        ...


uint1_t = Annotated[int, U(1)]
uint2_t = Annotated[int, U(2)]
uint3_t = Annotated[int, U(3)]
uint4_t = Annotated[int, U(4)]
uint5_t = Annotated[int, U(5)]
uint6_t = Annotated[int, U(6)]
uint7_t = Annotated[int, U(7)]
uint8_t = Annotated[int, U(8)]
uint9_t = Annotated[int, U(9)]
uint10_t = Annotated[int, U(10)]
uint11_t = Annotated[int, U(11)]
uint12_t = Annotated[int, U(12)]
uint13_t = Annotated[int, U(13)]
uint14_t = Annotated[int, U(14)]
uint15_t = Annotated[int, U(15)]
uint16_t = Annotated[int, U(16)]
uint17_t = Annotated[int, U(17)]
uint18_t = Annotated[int, U(18)]
uint19_t = Annotated[int, U(19)]
uint20_t = Annotated[int, U(20)]
uint21_t = Annotated[int, U(21)]
uint22_t = Annotated[int, U(22)]
uint23_t = Annotated[int, U(23)]
uint24_t = Annotated[int, U(24)]
uint25_t = Annotated[int, U(25)]
uint26_t = Annotated[int, U(26)]
uint27_t = Annotated[int, U(27)]
uint28_t = Annotated[int, U(28)]
uint29_t = Annotated[int, U(29)]
uint30_t = Annotated[int, U(30)]
uint31_t = Annotated[int, U(31)]
uint32_t = Annotated[int, U(32)]
uint64_t = Annotated[int, U(64)]
uint128_t = Annotated[int, U(128)]

u1 = uint1_t
u2 = uint2_t
u3 = uint3_t
u4 = uint4_t
u5 = uint5_t
u6 = uint6_t
u7 = uint7_t
u8 = uint8_t
u9 = uint9_t
u10 = uint10_t
u11 = uint11_t
u12 = uint12_t
u13 = uint13_t
u14 = uint14_t
u15 = uint15_t
u16 = uint16_t
u17 = uint17_t
u18 = uint18_t
u19 = uint19_t
u20 = uint20_t
u21 = uint21_t
u22 = uint22_t
u23 = uint23_t
u24 = uint24_t
u25 = uint25_t
u26 = uint26_t
u27 = uint27_t
u28 = uint28_t
u29 = uint29_t
u30 = uint30_t
u31 = uint31_t
u32 = uint32_t
u64 = uint64_t
u128 = uint128_t
uptr = Annotated[int, Uptr()]

int8_t = Annotated[int, S(8)]
int16_t = Annotated[int, S(16)]
int32_t = Annotated[int, S(32)]
int64_t = Annotated[int, S(64)]
int128_t = Annotated[int, S(128)]


i8 = int8_t
i16 = int16_t
i32 = int32_t
i64 = int64_t
i128 = int128_t

# Bit type aliases
bit = uint1_t
bit1 = uint1_t
bit2 = uint2_t
bit3 = uint3_t
bit4 = uint4_t
bit5 = uint5_t
bit6 = uint6_t
bit7 = uint7_t
bit8 = uint8_t
bit16 = uint16_t
bit32 = uint32_t
bit64 = uint64_t

class MyE(enum.IntEnum):
    a = 1
    b = 2

width = Annotated[MyE, U(16)]

# bitv is a special marker type for variable-width unsigned bit vectors.
# The actual width must be supplied via input(width=...) / output(width=...).
bitv = Annotated[int, U(-1)]
bv = Annotated[int, U(-1)]

class RegFile(TypeBase):
    regwidth : Optional[int] = None

    async def when(self, regs : List[Reg], cond: Callable[[List],bool]):
        """Performs a multi-register conditioned wait. A list of register 
        values is passed to the callable
        """
        ...

    def __new__(cls, **kwargs):
        from .config import Config
        ret = Config.inst().factory.mkRegFile(cls, **kwargs)
        return ret

class Reg[T](TypeBase):

    # Register storage and register access...
    # - Use non-blocking access within the device
    # - Use blocking access from an address space

    async def read(self) -> T: ...

    async def write(self, val : Union[T,dict,int]): 
        """Register write accepts:

        * whole-register write by integer value or reg-type
        * read-modify-write by dict of {reg-field : value}
        """
        ...

    async def when(self, cond : Callable[[T],bool]): 
        """Performs a single-register conditioned wait."""
        ...

class RegFifo[T]():

    async def read(self) -> T:
        pass


class Memory[T](TypeBase):

    # APIs for memory owner to use -- provides direct memory access
    def read(self, addr : int) -> T:
        """Read a value from the memory at the specified address"""
        pass

    def write(self, addr : int, data : T):
        """Write a value to the memory at the specified address"""
        pass

class MemIF(Protocol):

    async def read8(self, addr : u64) -> u8: ...

    async def read16(self, addr : u64) -> u16: ...

    async def read32(self, addr : u64) -> u32: ...

    async def read64(self, addr : u64) -> u64: ...

    async def write8(self, addr : u64, data : u8): ...

    async def write16(self, addr : u64, data : u16): ...

    async def write32(self, addr : u64, data : u32): ...

    async def write64(self, addr : u64, data : u64): ...

@dc.dataclass
class At(object):
    """Locates an element at a specific offset"""
    offset : int = dc.field()
    element : Union[RegFile, Memory,AddressSpace] = dc.field()

# Note: Need some 'swizzle' classes to specify width and alignment
# conversion

class AddrHandle(MemIF):
      pass

@dc.dataclass
class AddressSpace(object):
    """Software-centric view of memory"""

    # mmap specifies the memory maps that compose this
    # address space. mmap is specified using bind.
    # 
    mmap : Tuple[Union[At,RegFile,AddressSpace]] = dc.field()

    # Handle to the base of the address space
    base : AddrHandle = dc.field()


