import abc
import zuspec.dataclasses as zdc
from typing import Annotated, TypeVar, Type, Union
from .bit import BitVal
from .decorators import dataclass, constraint
from .struct import StructPacked

class AddrHandle(): pass

class AddrTrait(zdc.Struct): pass


class AddrSpaceBase:
    pass

# uint64_t = Annotated[int, "abc"]

AddrTraitT = TypeVar('AddrTraitT', bound=AddrTrait)

@dataclass
class AddrRegion[AddrTraitT]():
    trait : Type[AddrTraitT] = zdc.field()

@dataclass
class TransparentAddrSpace[AddrTraitT](AddrSpaceBase):

    @abc.abstractmethod
    def add_region(self, region : AddrRegion[AddrTraitT]) -> AddrHandle: 
        """Adds a region to the address space, returning a handle to that region"""
        pass

@dataclass
class AddrClaim[AddrTraitT]():
    trait : AddrTraitT = zdc.field(rand=True)
    size : int = zdc.field(rand=True)

    @constraint
    def size_align_c(self):
        self.size > 0


    @abc.abstractmethod
    def handle(self, offset : int = 0) -> AddrHandle:
        """Returns a handle corresponding to the claim"""
        pass

RegT = TypeVar("RegT", bound=Union[BitVal,StructPacked])

class Reg[RegT](object):

    @abc.abstractmethod
    async def read(self) -> Type[RegT]:
        """Reads the value of the register"""
        pass

    @abc.abstractmethod
    async def write(self, data : Type[RegT]): 
        """Writes the value of the register"""
        pass

class RegGroup(object):
    @abc.abstractmethod
    def get_handle(self) -> AddrHandle: 
        """Gets the address handle that corresponds to this group"""
        pass

    @abc.abstractmethod
    def set_handle(self, h): 
        """Sets the address handle corresponding to this root group"""
        pass


