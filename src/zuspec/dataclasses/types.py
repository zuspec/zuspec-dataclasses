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
from typing import Callable, ClassVar, Dict, Generic, List, Optional, TypeVar, Literal, Type, Annotated, Protocol, Any, SupportsInt, Union, Tuple, Self
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

@dc.dataclass
class AnnotationFileSet(object):
    filetype : str = dc.field()
    basedir : str = dc.field()
    incdirs : Set[str] = dc.field(default_factory=set)
    defines : Set[str] = dc.field(default_factory=set)
    files : List[str] = dc.field(default_factory=list)


class PackedStruct(TypeBase,SupportsInt):

    def __int__(self) -> int:
        return 5

    pass

class Struct(TypeBase):
    pass

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
        return self._impl.name()

    @property
    def parent(self) -> Optional[Component]:
        assert self._impl is not None
        return self._impl.parent()

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

@dc.dataclass
class XtorComponent[T](Component):
    """A Transactor component has a single-level interface and an 
    operation-level interface"""
    xtor_if : T = export()

class Pool[T](Protocol):
    pass

@dc.dataclass
class ListPool[T](Pool[T]):
    # Bind target to specify pool elements
    elems : List[T] = dc.field()

    @abc.abstractmethod
    def __getitem__(self, idx : int) -> T:
        ...

    @abc.abstractmethod
    def get(self, idx : int) -> T:
        ...

    @property
    @abc.abstractmethod
    def size(self) -> int:
        ...


class ClaimPool[T,Tc](Pool[T]):

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


