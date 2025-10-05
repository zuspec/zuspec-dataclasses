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
from typing import Any, Callable, Dict, Optional, Self, TypeVar, TYPE_CHECKING, Union
from .annotation import Annotation, AnnotationSync


if TYPE_CHECKING:
    from .api.type_processor import TypeProcessor

def dataclass(cls, **kwargs):
    # TODO: Add type annotations to decorated methods
    cls_annotations = cls.__annotations__

    for name, value in cls.__dict__.items():
#        print("Name: %s ; Value: %s" % (name, value))
        if isinstance(value, dc.Field) and not name in cls_annotations:
            print("TODO: annotate field")
            cls_annotations[name] = int

    cls_t = dc.dataclass(cls, **kwargs)

    setattr(cls_t, "__base_init__", getattr(cls_t, "__init__"))
    def local_init(self, tp : 'TypeProcessor', *args, **kwargs):
        """Only called during type processing"""
        return tp.init(self, *args, **kwargs)
    setattr(cls_t, "__init__", local_init)

    if not hasattr(cls_t, "__base_new__"):
        setattr(cls_t, "__base_new__", getattr(cls_t, "__new__"))
        def local_new(c, tp : 'TypeProcessor', *args, **kwargs):
            """Always called during user-object construction"""
            return tp.new(c, *args, **kwargs)
        setattr(cls_t, "__new__", local_new)

    return cls_t

def bundle():
    return dc.field()

def mirror():
    return dc.field()

def monitor():
    return dc.field()

class bind[T]:
    """Helper class for specifying binds. Ensures that the parameter
     passed to the lambda is identified as the class type
    """
    def __init__(self, c : Callable[[T],Dict[Any,Any]]):
        self._c = c
    
def field(
        rand=False, 
        bind : Optional[Callable[[object],Dict[Any,Any]]] = None,
        init : Optional[Union[Dict[str,Any], Callable[[object],Dict[Any,Any]]]] = None,
        default_factory : Optional[Any] = None,
        default : Optional[Any] = None):
    args = {}
    metadata = None

#     # Obtain the location of this call
#     import inspect
#     frame = inspect.currentframe()
#     print("--> ")
#     while frame is not None:
#         modname = frame.f_globals["__name__"]

#         print("modname: %s" % modname)
#         if not modname.startswith("zuspec.dataclasses") and not modname.startswith("importlib"):
#             break
# #            pass
# #            frame = frame.f_back
#         else:
#             frame = frame.f_back
#     print("<-- ")

#     if frame is not None:
#         print("Location: %s:%d" % (frame.f_code.co_filename, frame.f_lineno))

    if default_factory is not None:
        args["default_factory"] = default_factory

    if bind is not None:
        metadata = {} if metadata is None else metadata
        metadata["bind"] = bind

    # *Always* specify a default to avoid becoming a required field
    if "default_factory" not in args.keys():
        args["default"] = default

    if metadata is not None:
        print("metadata: %s" % metadata)
        args["metadata"] = metadata
    return dc.field(**args)
    
    # @staticmethod
    # def __call__(rand=False, bind : Callable[[T],Dict[Any,Any]] = None):
    #     pass

    # """
    # Marks a plain data field
    # - rand -- Marks the field as being randomizable
    # - 
    # """
    # # TODO: 
    # return dc.field()

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

def lock(*args, **kwargs):
    return dc.field(default_factory=Lock)

def share(*args, **kwargs):
    return dc.field(default_factory=Share)

def port():
    return dc.field()

def export(*args, bind=None, **kwargs):
    return dc.field(*args, **kwargs)

class ExecKind(enum.Enum):
    Comb = enum.auto()
    Sync = enum.auto()
    Proc = enum.auto()

@dc.dataclass
class Exec(object):
    method : Callable = dc.field()
    kind : ExecKind = dc.field()
    timebase : Optional[Callable] = field(default=None)
    t : Optional[Callable] = field(default=None)

def extern(
    typename,
    bind,
    files=None,
    params=None):
    """
    Denotes an instance of an external module
    """
    from .struct import Extern
    return dc.field(default_factory=Extern,
                    metadata=dict(
                        typename=typename,
                        bind=bind,
                        files=files,
                        params=params))

def process(T):
    """
    Marks an always-running process. The specified
    method must be `async` and take no arguments
    """
    return Exec(T, ExecKind.Proc)

def reg(offset=0):
    return dc.field()
    pass

def const(default=None):
    return dc.field()

@dc.dataclass
class ExecSync(Exec):
    clock : Optional[Callable] = field(default=None)
    reset : Optional[Callable] = field(default=None)

def sync(clock : Callable, reset : Callable):
    """
    Marks a synchronous-evaluation region, which is evaluated on 
    the active edge of either the clock or reset.

    The semantics of a `sync` method differ from native Python.
    Assignments are delayed/nonblocking: they only take effect after
    evaluation of the method completes. If a variable is assigned multiple times
    within a sync method, only the last assignment to that variable in the method
    is applied for that cycle. Earlier assignments are ignored. Augmented
    assignments (eg +=) are treated the same as regular assignments.

    @zdc.sync
    def _update(self):
      self.val1 = self.val1 + 1
      self.val1 = self.val1 + 1
      self.val2 += 1
      self.val2 += 1

    In the example above, both val1 and val2 will only be increased by one
    each time _update is evaluated.
    """
    def __call__(T):
        return ExecSync(method=T, kind=ExecKind.Sync, clock=clock, reset=reset)
    return __call__

def comb(latch : bool=False):
    """
    Marks a combinational evaluation region that is evaluated 
    whenever one of the variables read by the method changes.
    """
    def __call__(T):
        return Exec(method=T, kind=ExecKind.Comb, )
    return __call__

def constraint(T):
    setattr(T, "__constraint__", True)
    return T
