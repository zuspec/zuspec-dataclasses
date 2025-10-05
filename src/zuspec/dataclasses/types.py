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
from typing import Dict, Generic, TypeVar, Literal, Type
from .decorators import dataclass, field

@dataclass
class TypeBase(object):
    """Marker for all Zuspec types"""
    pass

class BitMeta(type):
    """
    The BitMeta class is a constructor for Bit types.
    Bit[12], for example, produces a Bit type where
    W=12.
    """

    def __new__(cls, name, bases, attrs):
        return super().__new__(cls, name, bases, attrs)
    
    def __init__(self, name, bases, attrs):
        super().__init__(name, bases, attrs)
        self.type_m : Dict = {}
    
    def __getitem__(self, W : int):
        if W in self.type_m.keys():
            return self.type_m[W]
        else:
            t = type("bit[%d]" % W, (Bit,), {
                "W" : W
            })
            self.type_m[W] = t
            return t

# class BitLiteral(int):
#     W : int = 1

#     def __new__(cls, )

#     def __getitem__(self, v) -> 'BitLiteral':
#         return self
#         pass
#     pass

class Bit(int, metaclass=BitMeta):
    """
    Variables of 'Bit' type represent unsigned W-bit values.
    The value of the variables is automatically masked. For 
    example, assigning 20 (b10100) to a 4-bit variable will 
    result in 4 (b0100) being stored in the variable.
    """
    W : int = 1

    def __new__(cls, val : int=0):
        return super(Bit, cls).__new__(cls, val)

class Bits(int, metaclass=BitMeta):
    W : int = -1

    def __new__(cls, val : int=0):
        return super(Bits, cls).__new__(cls, val)

class IntMeta(type):
    """
    The IntMeta class is a constructor for Int types.
    Int[12], for example, produces a Int type where
    W=12.
    """

    def __new__(cls, name, bases, attrs):
        return super().__new__(cls, name, bases, attrs)
    
    def __init__(self, name, bases, attrs):
        super().__init__(name, bases, attrs)
        self.type_m : Dict = {}
    
    def __getitem__(self, W : int):
        if W in self.type_m.keys():
            return self.type_m[W]
        else:
            t = type("bit[%d]" % W, (Bit,), {
                "W" : W
            })
            self.type_m[W] = t
            return t

class Int(TypeBase, metaclass=IntMeta):
    """
    Variables of 'Int' type represent signed W-bit values.
    The value of the variables is automatically masked. For 
    example, assigning 20 (b10100) to a 4-bit variable will 
    result in 4 (b0100) being stored in the variable. Note
    that this may change the size of the variable.
    """
    W : int = -1

@dataclass
class Bundle(TypeBase):
    """
    A bundle type collects one or more ports, exports,
    inputs, outputs, or bundles. 

    Bundle fields are created with field(). Bundle-mirror
    fields are created with mirror() or field(mirror=True)
    Bundle-monitor fields are created with monitor() or
    field(monitor=True)

    A bundle field can be connected to a mirror field. 
    A bundle monitor field can be connected to both a 
    bundle and a bundle mirror.
    - Bundle
    - Bundle Mirror
    - Bundle Monitor (all are inputs / exports)
    """
    pass

@dataclass
class StructPacked(TypeBase):
    """
    StructPacked types are fixed-size data structures. 
    Fields may only be of a fixed size. 

    Valid sub-regions
    - constraint
    - pre_solve / post_solve
    """
    pass

@dataclass
class Struct(TypeBase):
    """
    Struct types are data structures that may contain
    variable-size fields. 

    Valid sub-regions
    - constraint
    - pre_solve / post_solve
    - method
    """

@dataclass
class Component(Struct):
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

    @abc.abstractmethod
    async def wait(self, amt : float, units : int = 0):
        """
        Uses the default timebase to suspend execution of the
        calling coroutine for the specified time.
        """
        pass

CompT = TypeVar('CompT', bound=Component)

@dataclass
class ComponentExtern(Component):
    """
    Extern components are used to interface with existing descriptions,
    such as existing Verilog RTL.
    """

@dataclass
class Action[CompT](Struct):
    """
    Action-derived types 

    Valid fields
    - All Struct fields
    - Input / Output fields of Buffer, Stream, and State types
    - Lock / Share fields of Resource types
    Valid sub-regions
    - All Struct sub-regions
    - activity
    """
    comp : Type[CompT] = field()