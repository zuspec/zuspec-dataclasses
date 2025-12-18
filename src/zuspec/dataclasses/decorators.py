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
#
# Created on Mar 19, 2022
# @author: mballance
#****************************************************************************
import dataclasses
import dataclasses as dc
import enum
from typing import Any, Callable, Dict, Optional, Self, TypeVar, TYPE_CHECKING, Union, TypeVarTuple, Generic
from typing import dataclass_transform


@dataclass_transform()
def dataclass(cls, **kwargs):
    # TODO: Add type annotations to decorated methods
    cls_annotations = cls.__annotations__

    for name, value in cls.__dict__.items():
#        print("Name: %s ; Value: %s" % (name, value))
        if isinstance(value, dc.Field) and not name in cls_annotations:
            print("TODO: annotate field")
            cls_annotations[name] = int

    cls_t = dc.dataclass(cls, kw_only=True, **kwargs)

    return cls_t

class bind[Ts,Ti]:
    """Helper class for specifying binds. Ensures that the parameter
     passed to the lambda is identified as the class type.
    """
    def __init__(self, c : Callable[[Ts,Ti],Dict[Any,Any]]):
        self._c = c

def field(
        rand=False, 
        init : Optional[Union[Dict[str,Any], Callable[[object],Dict[Any,Any]]]] = None,
        default_factory : Optional[Any] = None,
        default : Optional[Any] = None,
        metadata : Optional[Dict[str,object]]=None,
        size : Optional[int]=None,
        bounds : Optional[tuple]=None):
    args = {}

    if default_factory is not None:
        args["default_factory"] = default_factory

    # *Always* specify a default to avoid becoming a required field
    if "default_factory" not in args.keys():
        args["default"] = default
    
    if size is not None:
        metadata = {} if metadata is None else metadata
        metadata["size"] = size
    
    if bounds is not None:
        metadata = {} if metadata is None else metadata
        metadata["bounds"] = bounds

    if metadata is not None:
        args["metadata"] = metadata

    return dc.field(**args)
    
class Input(object): 
    """Marker type for 'input' dataclass fields"""
    ...

class Output(object):
    """Marker type for 'output' dataclass fields"""
    ...

def input(*args, **kwargs):
    """
    Marks an input field. Input fields declared on a 
    top-level component are `bound` to an implicit output. Those
    on non-top-level components must explicitly be `bound` to an 
    output. An input field sees the value of the output field 
    to which it is bound with no delay
    """
    return dataclasses.field(default_factory=Input)

def output(*args, **kwargs):
    """
    Marks an output field. Input fields that are bound to
    an output field always see its current output value 
    with no delay.
    """
    return dc.field(default_factory=Output)

def port():
    """A 'port' field is an API consumer. It must be bound
    to a matching 'export' field that provides an implementation
    of the API"""
    return dc.field(init=False, metadata={"kind": "port"})

def export():
    """An 'export' field is an API provider. It must be bound
    to implementations of the API class -- either per method 
    or on a whole-class basis."""
    return dc.field(init=False, metadata={"kind": "export"})

class ExecKind(enum.Enum):
    Comb = enum.auto()
    Sync = enum.auto()
    Proc = enum.auto()

@dc.dataclass
class Exec(object):
    method : Callable = dc.field()
#    kind : ExecKind = dc.field()
#    timebase : Optional[Callable] = field(default=None)
#    t : Optional[Callable] = field(default=None)

class ExecProc(Exec): pass

@dc.dataclass
class ExecSync(Exec):
    """Synchronous process"""
    clock : Optional[Callable] = dc.field(default=None)
    reset : Optional[Callable] = dc.field(default=None)

@dc.dataclass
class ExecComb(Exec):
    """Combinational process"""
    pass

def process(T):
    """
    Marks an always-running process. The specified
    method must be `async` and take no arguments. The
    process is started when the component containing 
    it begins to run.
    """
    # Datamodel Mapping
    return ExecProc(T)

def sync(clock: Callable = None, reset: Callable = None):
    """
    Decorator for synchronous processes.
    
    The process is evaluated on positive edge of clock or reset.
    Assignments in sync processes are deferred - they take effect
    after the method completes but before next evaluation.
    
    Args:
        clock: Lambda expression that returns clock signal reference
        reset: Lambda expression that returns reset signal reference
        
    Example:
        @zdc.sync(clock=lambda s:s.clock, reset=lambda s:s.reset)
        def _count(self):
            if self.reset:
                self.count = 0
            else:
                self.count += 1
    """
    def decorator(method):
        return ExecSync(method=method, clock=clock, reset=reset)
    return decorator

def comb(method):
    """
    Decorator for combinational processes.
    
    The process is re-evaluated whenever any of the signals it reads change.
    Assignments in comb processes take effect immediately.
    
    Example:
        @zdc.comb
        def _calc(self):
            self.out = self.a ^ self.b
    """
    return ExecComb(method=method)

def invariant(func):
    """Decorator to mark a method as a structural invariant.
    
    The decorated method should return a boolean expression that must 
    always hold for valid instances of the dataclass.
    
    Example:
        @zdc.dataclass
        class Config(zdc.Struct):
            x: zdc.uint8_t = zdc.field(bounds=(0, 100))
            y: zdc.uint8_t = zdc.field(bounds=(0, 100))
            
            @zdc.invariant
            def sum_constraint(self) -> bool:
                return self.x + self.y <= 150
    
    Args:
        func: Method that returns bool
        
    Returns:
        Decorated function with _is_invariant flag set
    """
    func._is_invariant = True
    return func

