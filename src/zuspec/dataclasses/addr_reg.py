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

class AddrTrait(zdc.Struct): pass


class AddrSpaceBase:
    pass

uint64_t = Annotated[int, "abc"]

AddrTraitT = TypeVar('AddrTraitT', bound=AddrTrait)

class AddrRegion[AddrTraitT]():
    trait : Type[AddrTraitT] = zdc.trait()
    pass

class MyTrait(AddrTrait):
    a : int = 5

class TransparentAddrSpace[AddrTraitT](AddrSpaceBase):

    def add_region(self, region : AddrRegion[AddrTraitT]): pass

    pass

class MyAddrTrait(AddrTrait):
    pass

class Other(object):
    pass

t : TransparentAddrSpace = TransparentAddrSpace()
o = Other()

r = AddrRegion[MyTrait]()
r2 = AddrRegion[Other]()

t.add_region(r2)

r.trait.a

RegT = TypeVar("RegT", bound=Union[int,StructPacked])

class Reg[RegT](object):

    @abc.abstractmethod
    def read(self) -> Type[RegT]: pass

    @abc.abstractmethod
    def write(self, data : Type[RegT]): pass

    def write_fields(self, fields : Dict[object,int]): pass

class RegGroup(object):
    @abc.abstractmethod
    def get_handle(self): pass

    @abc.abstractmethod
    def set_handle(self, h): pass

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