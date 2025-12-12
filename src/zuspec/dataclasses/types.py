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
from __future__ import annotations
import abc
import dataclasses as dc
import enum
from typing import Callable, ClassVar, Dict, Generic, List, Optional, TypeVar, Literal, Type, Annotated, Protocol, Any, SupportsInt, Union, Tuple
from .decorators import dataclass, field

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

    def timebase(self) -> Timebase: ... 

    def shutdown(self): ...

    async def wait(self, comp: Component, amt: Time = None): ...

    def time(self) -> Time: ...

class PackedStruct(TypeBase,SupportsInt):

    def __int__(self) -> int:
        return 5

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

    # _impl is always an internal field. User code must never
    # access it
    _impl : Optional[CompImpl] = dc.field(default=None)

    def __post_init__(self):
        # _impl may be None during initial construction; post_init
        # will be called later by __comp_build__
        if self._impl is not None:
            self._impl.post_init(self)

    def shutdown(self):
        assert self._impl is not None
        self._impl.shutdown()

    @property
    def name(self) -> str:
        assert self._impl is not None
        return self._impl.name()

    @property
    def parent(self) -> Optional[Component]:
        assert self._impl is not None
        return self._impl.parent()

    def __bind__(self) -> Optional[Dict]: 
        pass

    async def wait(self, amt : Time = None):
        """
        Uses the default timebase to suspend execution of the
        calling coroutine for the specified time.
        
        When called and simulation is not already running, this also 
        drives the simulation forward.
        """
        assert self._impl is not None
        await self._impl.wait(self, amt)

    def time(self) -> Time: 
        """Returns the current time"""
        assert self._impl is not None
        return self._impl.time()

    def __new__(cls, **kwargs):
        from .config import Config
        if "_impl" not in kwargs.keys():
            ret = Config.inst().factory.mkComponent(cls, **kwargs)
        else:
            ret = object.__new__(cls)
        return ret

class Pool[T,Tc](Protocol):

    @property
    def selector(self) -> Callable[[List[T]], int]:  ...

    @selector.setter
    def selector(self, s : Callable[[List[T]], int]) -> None: ...

    def match(self, c : Tc, m : Callable[[T], bool]) -> int: ...

    def add(self, t : T): ...

    def get(self, i : int) -> T: ...


class ClaimPool[T,Tc](Pool[T,Tc]):

    @abc.abstractmethod
    def lock(self, i : int) -> T: 
        """Acquires the specified object for read-write access"""
        ...

    @abc.abstractmethod
    def share(self, i : int) -> T: 
        """Acquires the specified object for read-only access"""
        ...

    def drop(self, i : int): ...

    pass


class Lock:
    """A mutex lock for coordinating access to shared resources.
    
    This is a zuspec-aware wrapper around asyncio.Lock that can be
    used in component fields and is properly handled by the data model.
    """
    def __init__(self):
        import asyncio
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire the lock. Blocks until the lock is available."""
        await self._lock.acquire()
    
    def release(self):
        """Release the lock."""
        self._lock.release()
    
    def locked(self) -> bool:
        """Return True if the lock is currently held."""
        return self._lock.locked()
    
    async def __aenter__(self):
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False

uint1_t = Annotated[int, U(1)]
uint2_t = Annotated[int, U(2)]
uint3_t = Annotated[int, U(3)]
uint4_t = Annotated[int, U(4)]
uint5_t = Annotated[int, U(5)]
uint6_t = Annotated[int, U(6)]
uint7_t = Annotated[int, U(7)]
uint8_t = Annotated[int, U(8)]
uint16_t = Annotated[int, U(16)]
uint32_t = Annotated[int, U(32)]
uint64_t = Annotated[int, U(64)]

int8_t = Annotated[int, S(8)]
int16_t = Annotated[int, S(16)]
int32_t = Annotated[int, S(32)]
int64_t = Annotated[int, S(64)]

class MyE(enum.IntEnum):
    a = 1
    b = 2

width = Annotated[MyE, U(16)]

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

    async def read(self) -> T: ...

    async def write(self, val : T): ...

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

    async def read8(self, addr : int) -> uint8_t: ...

    async def read16(self, addr : int) -> uint16_t: ...

    async def read32(self, addr : int) -> uint32_t: ...

    async def read64(self, addr : int) -> uint64_t: ...

    async def write8(self, addr : int, data : uint8_t): ...

    async def write16(self, addr : int, data : uint16_t): ...

    async def write32(self, addr : int, data : uint32_t): ...

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


