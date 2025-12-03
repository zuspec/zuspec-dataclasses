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
from typing import Dict, Generic, Optional, TypeVar, Literal, Type, Annotated, Protocol, Any
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

@dc.dataclass
class S(SignWidth): pass

@dc.dataclass
class U(SignWidth):
    def __post_init__(self):
        # signed for U types is always False
        self.signed = False

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
    Struct types 
    variable-size fields. 

    Valid sub-regions
    - constraint
    - pre_solve / post_solve
    - method
    """

class CompImpl(Protocol):

    def name(self) -> str: ...

    def parent(self) -> Component: ...

    def post_init(self, comp): ...


@dc.dataclass
class Component(object):
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
        print("--> __post_init__ %s" % str(type(self)))
        print("  impl: %s" % str(self._impl))
#        self._impl.post_init(self)
        print("<-- __post_init__")
#        assert self._impl is not None
#        self._impl.post_init(self)

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

    async def wait(self, amt : float, units : int = 0):
        """
        Uses the default timebase to suspend execution of the
        calling coroutine for the specified time.
        """
        pass

    def __new__(cls, **kwargs):
        from .config import Config
        print("--> __new__ %s" % cls.__qualname__)
        if "_impl" not in kwargs.keys():
            ret = Config.inst().factory.mkComponent(cls, **kwargs)
            print("impl: %s" % ret._impl)
        else:
            print("have _impl")
            ret = super().__new__(cls)
#        ret.__init__(**kwargs)
        print("<-- __new__ %s" % cls.__qualname__)
        return ret
        
    def __init__(self, *args, **kwargs):
        print("--> __init__")
        super().__init__(*args, **kwargs)
        print("<-- __init__")

        
    # def __init__(self, **kwargs):
    #     if "parent" not in kwargs.keys():
    #         kwargs["parent"] = None
    #     if "name" not in kwargs.keys():
    #         kwargs["name"] = "root"
        


