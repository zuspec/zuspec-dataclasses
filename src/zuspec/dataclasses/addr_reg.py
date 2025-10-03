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
import zuspec.dataclasses as zdc
from typing import Annotated, Dict, TypeVar, Type, Union
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

    def write_fields(self, fields : Dict[object,int]): pass

class RegGroup(object):
    @abc.abstractmethod
    def get_handle(self) -> AddrHandle: 
        """Gets the address handle that corresponds to this group"""
        pass

    @abc.abstractmethod
    def set_handle(self, h): 
        """Sets the address handle corresponding to this root group"""
        pass


class At(object):
    a : zdc.Bit[15] = zdc.field()
    b : zdc.Bit[15] = zdc.field()

#    def __int__(self) -> int:
#        pass

# r : Reg[At] = 5
# r.read() == 20
# r.write()
# r.write_fields({At.a : 5})
# def reg(offset=)

# def reg_array(offset=0, offset_of=lambda i: )