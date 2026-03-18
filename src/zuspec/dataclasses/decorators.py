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
import inspect
import sys
from typing import Any, Callable, Dict, Optional, Self, TypeVar, TYPE_CHECKING, Union, TypeVarTuple, Generic, Literal
from typing import dataclass_transform

if TYPE_CHECKING:
    from .profiles import Profile


def _resolve_annotations(cls) -> None:
    """Resolve any string annotations caused by 'from __future__ import annotations'.

    When classes are defined inside functions the module globals alone are not
    sufficient to evaluate deferred annotations.  We walk up the call stack
    collecting locals from every frame so that locally-defined types (like a
    component class defined inside a test function) can be resolved.
    """
    if not cls.__annotations__:
        return

    # Build a combined namespace: module globals + all enclosing frame locals
    try:
        mod_globals = vars(sys.modules.get(cls.__module__, None) or {})
    except Exception:
        mod_globals = {}

    localns: Dict[str, Any] = {}
    frame = inspect.currentframe()
    while frame is not None:
        localns.update(frame.f_locals)
        frame = frame.f_back

    resolved: Dict[str, Any] = {}
    for name, ann in cls.__annotations__.items():
        if isinstance(ann, str):
            try:
                resolved[name] = eval(ann, mod_globals, localns)
            except Exception:
                resolved[name] = ann  # leave unresolved strings as-is
        else:
            resolved[name] = ann
    cls.__annotations__ = resolved


@dataclass_transform()
def dataclass(cls=None, *, profile: Optional[type['Profile']] = None, **kwargs):
    """Decorator for defining zuspec dataclasses with optional profile enforcement.
    
    Args:
        cls: Class being decorated (when used without parameters)
        profile: Profile class defining validation rules (defaults to RetargetableProfile)
        **kwargs: Additional arguments passed to dataclasses.dataclass
    
    Example:
        from zuspec.dataclasses import dataclass, profiles
        
        @dataclass(profile=profiles.PythonProfile)
        class MyClass:
            x: int  # Allowed with Python profile
        
        @dataclass(profile=profiles.RetargetableProfile)
        class MyRetargetableClass:
            x: uint32_t  # Width-annotated type required
    """
    def decorator(cls):
        # Store profile information in class metadata for mypy plugin
        # The profile attribute is used by the MyPy plugin to determine
        # which validation rules to apply
        if profile is not None:
            cls.__profile__ = profile
        # If no profile specified, MyPy plugin will use DEFAULT_PROFILE

        # Resolve deferred string annotations (from __future__ import annotations)
        # before dc.dataclass processes them, so runtime code sees real type objects.
        _resolve_annotations(cls)

        # TODO: Add type annotations to decorated methods
        cls_annotations = cls.__annotations__

        for name, value in cls.__dict__.items():
    #        print("Name: %s ; Value: %s" % (name, value))
            if isinstance(value, dc.Field) and not name in cls_annotations:
                print("TODO: annotate field")
                cls_annotations[name] = int

        cls_t = dc.dataclass(cls, kw_only=True, **kwargs)

        # Detect activity/body mutual exclusion and parse the activity method
        has_activity = 'activity' in cls.__dict__
        has_body = 'body' in cls.__dict__
        if has_activity and has_body:
            raise TypeError(
                f"@zdc.dataclass class '{cls.__name__}' defines both activity() and body(). "
                "A compound action must define activity(); an atomic action must define body()."
            )
        if has_activity:
            from .activity_parser import ActivityParser
            cls_t.__activity__ = ActivityParser().parse(cls.__dict__['activity'])

        return cls_t
    
    # Handle both @dataclass and @dataclass(...) syntax
    if cls is None:
        return decorator
    else:
        return decorator(cls)

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
        domain : Optional[tuple]=None,
        width=None):
    """Field declaration for structs and bundles.
    
    Args:
        rand: Mark field as random variable (deprecated - use rand() function)
        domain: Domain constraint for random variable (tuple of (min, max) or list of values)
        width: For width-unspecified types (eg bitv), specifies the concrete width.
               May be an int or a lambda that reads consts (eg width=lambda s: s.DATA_WIDTH).
    """
    args = {}

    if default_factory is not None:
        args["default_factory"] = default_factory

    # *Always* specify a default to avoid becoming a required field
    if "default_factory" not in args.keys():
        args["default"] = default
    
    if size is not None:
        metadata = {} if metadata is None else metadata
        metadata["size"] = size
    
    if domain is not None:
        metadata = {} if metadata is None else metadata
        metadata["domain"] = domain
    
    if width is not None:
        metadata = {} if metadata is None else metadata
        metadata["width"] = width
    
    if rand:
        metadata = {} if metadata is None else metadata
        metadata["rand"] = True

    if metadata is not None:
        args["metadata"] = metadata

    return dc.field(**args)

def pool(size: Optional[int] = None, default_factory=None) -> Any:
    """Declare a resource/flow-object pool on a Component field.

    Example::

        channels: ClaimPool[DmaChannel] = zdc.pool(
            default_factory=lambda: ClaimPool.fromList([DmaChannel(), DmaChannel()])
        )
    """
    meta: Dict[str, object] = {"kind": "pool"}
    if size is not None:
        meta["size"] = size
    if default_factory is not None:
        return dc.field(default_factory=default_factory, metadata=meta)
    return dc.field(default=None, metadata=meta)


def flow_output(default=dc.MISSING, **kwargs) -> Any:
    """Declare an action field as a flow-object output (producer side).

    Use on action fields of type ``Buffer``, ``Stream``, or ``State``.
    The runtime injects a ``BufferInstance``/``StreamInstance``/``StatePool``
    whose output face the action exposes.

    Example::

        @zdc.dataclass
        class Producer(zdc.Action[MyComp]):
            buf: MyBuf = flow_output()
    """
    kw: dict = {"metadata": {"kind": "flow_ref", "direction": "output"}}
    if default is not dc.MISSING:
        kw["default"] = default
    return dc.field(**kw)


def flow_input(default=dc.MISSING, **kwargs) -> Any:
    """Declare an action field as a flow-object input (consumer side).

    Example::

        @zdc.dataclass
        class Consumer(zdc.Action[MyComp]):
            buf: MyBuf = flow_input()
    """
    kw: dict = {"metadata": {"kind": "flow_ref", "direction": "input"}}
    if default is not dc.MISSING:
        kw["default"] = default
    return dc.field(**kw)


def extend(cls=None):
    """Decorator marking a class as a PSS type extension of its base class.

    The decorated class must inherit from exactly one ``@zdc.dataclass``-decorated
    class (action, component, buffer, etc.).  Multiple extensions of the same
    base type imply a PSS ``schedule`` block when composed.

    Sets two class attributes:
    - ``__extends__``: the base class being extended
    - ``__is_extension__``: ``True``

    Raises:
        TypeError: If the class has no valid zuspec base class to extend.

    Example::

        @zdc.dataclass
        class WriteData(zdc.Action[MyComp]):
            size: zdc.u8 = zdc.rand()
            async def body(self): ...

        @zdc.extend
        class WriteDataExt(WriteData):
            tag: zdc.u4 = zdc.rand()
    """
    def _decorate(cls):
        bases = [
            b for b in cls.__bases__
            if hasattr(b, '__dataclass_fields__') or hasattr(b, '__activity__')
        ]
        if not bases:
            raise TypeError(
                f"@zdc.extend: '{cls.__name__}' must inherit from a zuspec dataclass "
                "(action, component, struct, buffer, stream, state, or resource)."
            )
        cls.__extends__ = bases[0]
        cls.__is_extension__ = True
        # Parse the extension's own activity() method if it defines one
        if 'activity' in cls.__dict__:
            from .activity_parser import ActivityParser
            cls.__activity__ = ActivityParser().parse(cls.__dict__['activity'])
        return cls

    if cls is None:
        return _decorate
    return _decorate(cls)


def lock(size: Optional[int] = None) -> Any:
    """Declare an exclusive resource-lock claim on an action field.

    The annotated field type must be a subclass of ``zdc.Resource``.

    Args:
        size: If provided, declares a fixed-size array of lock claims.

    Example::

        chan: DmaChannel = zdc.lock()
        chans: List[DmaChannel] = zdc.lock(size=4)
    """
    meta: Dict[str, object] = {"kind": "resource_ref", "claim": "lock"}
    if size is not None:
        meta["size"] = size
    return dc.field(default=None, metadata=meta)


def share(size: Optional[int] = None) -> Any:
    """Declare a shared resource claim on an action field.

    The annotated field type must be a subclass of ``zdc.Resource``.

    Args:
        size: If provided, declares a fixed-size array of share claims.

    Example::

        cpu: CpuCore = zdc.share()
    """
    meta: Dict[str, object] = {"kind": "resource_ref", "claim": "share"}
    if size is not None:
        meta["size"] = size
    return dc.field(default=None, metadata=meta)

def rand(
        domain: Optional[tuple] = None,
        default: Any = 0,
        size: Optional[int] = None,
        max_size: Optional[int] = None,
        width=None):
    """Mark a field as a random variable.
    
    Random variables are solved by the constraint solver during randomization.
    
    Example:
        @dataclass
        class Packet:
            length: rand(domain=(64, 1500), default=64)
            # Fixed-size array of 16 elements
            buffer: List[int] = rand(size=16, domain=(0, 255))
            # Variable-size array (max 32 elements, determined by constraints)
            payload: List[int] = rand(max_size=32, domain=(0, 255))
    
    Args:
        domain: Domain constraint - tuple of (min, max) or list of allowed values
        default: Default value when not randomized
        size: For array fields, fixed size of the array (must be positive integer)
        max_size: For variable-size arrays, maximum array size (defaults to 32)
        width: For width-unspecified types, concrete width
        
    Returns:
        Field metadata for a random variable
    
    Note:
        - If size is specified: Creates fixed-size array
        - If max_size is specified: Creates variable-size array (length determined by constraints)
        - Cannot specify both size and max_size
    """
    # Validate size parameters
    if size is not None and max_size is not None:
        raise ValueError("Cannot specify both 'size' and 'max_size' - use one or the other")
    
    if size is not None:
        if not isinstance(size, int):
            raise TypeError(f"size must be an integer, got {type(size).__name__}")
        if size <= 0:
            raise ValueError(f"size must be positive, got {size}")
    
    if max_size is not None:
        if not isinstance(max_size, int):
            raise TypeError(f"max_size must be an integer, got {type(max_size).__name__}")
        if max_size <= 0:
            raise ValueError(f"max_size must be positive, got {max_size}")
    
    metadata = {"rand": True, "rand_kind": "rand"}
    
    if domain is not None:
        metadata["domain"] = domain
    
    if size is not None:
        metadata["size"] = size
    
    if max_size is not None:
        metadata["max_size"] = max_size
    
    if width is not None:
        metadata["width"] = width
    
    return dc.field(default=default, metadata=metadata)


def randc(
        domain: Optional[tuple] = None,
        default: Any = 0,
        size: Optional[int] = None,
        width=None):
    """Mark a field as a random-cyclic variable.
    
    Random-cyclic variables iterate through all values in their domain
    before repeating. The solver ensures a permutation of all valid values
    is exhausted before regenerating a new permutation.
    
    Example:
        @dataclass
        class TestSequence:
            test_id: randc(domain=(0, 15))  # Cycles through 0-15
            
            @constraint
            def valid_test(self):
                self.test_id < 12  # Only IDs 0-11 valid
    
    Args:
        domain: Domain constraint - tuple of (min, max) or list of allowed values
        default: Default value when not randomized
        size: For array fields, size of the array (must be positive integer)
        width: For width-unspecified types, concrete width
        
    Returns:
        Field metadata for a random-cyclic variable
    """
    # Validate size parameter
    if size is not None:
        if not isinstance(size, int):
            raise TypeError(f"size must be an integer, got {type(size).__name__}")
        if size <= 0:
            raise ValueError(f"size must be positive, got {size}")
    
    metadata = {"rand": True, "rand_kind": "randc"}
    
    if domain is not None:
        metadata["domain"] = domain
    
    if size is not None:
        metadata["size"] = size
    
    if width is not None:
        metadata["width"] = width
    
    return dc.field(default=default, metadata=metadata)
    
class Input(object): 
    """Marker type for 'input' dataclass fields"""
    ...

class Output(object):
    """Marker type for 'output' dataclass fields"""
    ...

def input(*args, width=None, **kwargs) -> Any:
    """Marks an input field.

    Args:
        width: For width-unspecified types (eg bitv), specifies the concrete width.
               May be an int or a lambda that reads consts (eg width=lambda s: s.DATA_WIDTH).
    """
    metadata = {}
    if width is not None:
        metadata["width"] = width
    return dataclasses.field(default_factory=Input, metadata=metadata if metadata else None)

def output(*args, width=None, reset=None, **kwargs) -> Any:
    """Marks an output field.

    Args:
        width: For width-unspecified types (eg bitv), specifies the concrete width.
               May be an int or a lambda that reads consts (eg width=lambda s: s.DATA_WIDTH).
        reset: Reset value for the output. Used to generate reset logic in synchronous processes.
               For scalar types, use a literal (e.g., reset=0).
               For struct types, use a dict (e.g., reset={'data': 0, 'valid': 0}).
    """
    metadata = {}
    if width is not None:
        metadata["width"] = width
    if reset is not None:
        metadata["reset"] = reset
    return dc.field(default_factory=Output, metadata=metadata if metadata else None)


class RegField(object):
    """Marker type for 'reg' (internal register) dataclass fields.
    
    Note: This is distinct from zdc.Reg which is for register-file style
    registers with read/write methods. RegField is for internal FSM state.
    """
    ...

def reg(reset=None, width=None) -> Any:
    """Marks an internal register field.

    Internal registers are state elements that persist across clock cycles.
    They are not exposed as ports but are used for internal FSM state.

    Args:
        reset: Reset value for the register. Used to generate reset logic.
               For scalar types, use a literal (e.g., reset=0).
               For struct types, use a dict (e.g., reset={'field': 0}).
        width: For width-unspecified types (eg bitv), specifies the concrete width.
               May be an int or a lambda that reads consts.
    """
    metadata = {"kind": "reg"}
    if reset is not None:
        metadata["reset"] = reset
    if width is not None:
        metadata["width"] = width
    return dc.field(default_factory=RegField, metadata=metadata)


def const(default=None) -> Any:
    """Marks a post-construction constant.

    Used primarily for configuration and bundle/interface parameters.
    """
    return dc.field(default=default, metadata={"kind": "const"})


def bundle(
        default_factory=dc.MISSING,
        kwargs: Optional[Union[Dict[str, Any], Callable[[object], Dict[str, Any]]]] = None
    ) -> Any:
    """Marks a field as a bundle/interface with declared directionality."""
    metadata = {"kind": "bundle"}
    if kwargs is not None:
        metadata["kwargs"] = kwargs
    return dc.field(init=False, default_factory=default_factory, metadata=metadata)


def mirror(
        default_factory=dc.MISSING,
        kwargs: Optional[Union[Dict[str, Any], Callable[[object], Dict[str, Any]]]] = None
    ) -> Any:
    """Marks a field as a bundle/interface with flipped directionality."""
    metadata = {"kind": "mirror"}
    if kwargs is not None:
        metadata["kwargs"] = kwargs
    return dc.field(init=False, default_factory=default_factory, metadata=metadata)


def monitor(
        default_factory=dc.MISSING,
        kwargs: Optional[Union[Dict[str, Any], Callable[[object], Dict[str, Any]]]] = None
    ) -> Any:
    """Marks a field as a bundle/interface for passive monitoring."""
    metadata = {"kind": "monitor"}
    if kwargs is not None:
        metadata["kwargs"] = kwargs
    return dc.field(init=False, default_factory=default_factory, metadata=metadata)

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

def inst(
        default_factory=dc.MISSING,
        kwargs: Optional[Union[Dict[str, Any], Callable[[object], Dict[str, Any]]]] = None,
        elem_factory: Optional[Union[type, Callable[[object], Any]]] = None,
        size: Optional[int] = None
    ):
    """Instance attributes are automatically constructed based on the annotated type.
    
    Args:
        default_factory: Factory function to create the instance
        kwargs: Dict or lambda returning dict with constructor arguments
        elem_factory: For container types, factory for creating elements
        size: For container types, size of the container
    """
    metadata = {"kind": "instance"}
    if kwargs is not None:
        metadata["kwargs"] = kwargs
    if elem_factory is not None:
        metadata["elem_factory"] = elem_factory
    if size is not None:
        metadata["size"] = size
    return dc.field(
        init=False,
        default_factory=default_factory,
        metadata=metadata)

def tuple(size=0, elem_factory=None):
    """Fixed-size tuple field.

    Note: element construction is handled by the runtime.
    """
    metadata = {"kind": "tuple"}
    if size is not None and size != 0:
        metadata["size"] = size
    if elem_factory is not None:
        metadata["elem_factory"] = elem_factory
    return dc.field(init=False, metadata=metadata)


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


class _ConstraintDecorator:
    """Decorator for constraint methods with support for variants."""
    
    def __call__(self, func):
        """Mark a method as a fixed constraint (always applies).
        
        Example:
            @constraint
            def valid_addr(self):
                self.addr < 256
        """
        func._is_constraint = True
        func._constraint_kind = 'fixed'
        return func
    
    def generic(self, func):
        """Mark a method as a generic constraint (only applies when referenced).
        
        Example:
            @constraint.generic
            def addr_low(self):
                self.addr < 0x1000
        """
        func._is_constraint = True
        func._constraint_kind = 'generic'
        return func

# Create singleton instance
constraint = _ConstraintDecorator()


def view(m):
    """Marks a method that returns a component view"""
    return m
