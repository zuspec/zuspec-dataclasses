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

        # For PackedStruct subclasses, compute bit-field layout after
        # dataclass processing so all annotations are resolved.
        from .types import PackedStruct
        if isinstance(cls_t, type) and issubclass(cls_t, PackedStruct):
            cls_t._build_packed_layout()

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


def indexed_regfile(
        read_ports:  int  = 2,
        write_ports: int  = 1,
        shared_port: bool = False,
) -> Any:
    """Declare an :class:`IndexedRegFile` field on a Component.

    Parameters
    ----------
    read_ports:
        Number of independent read port slots.  Controls how many concurrent
        reads are structurally allowed and how many ``rp{N}_addr / rp{N}_data``
        wire groups appear on the synthesised register file module.
    write_ports:
        Number of independent write port slots.  Controls how many concurrent
        writes are structurally allowed and how many ``wp{N}_addr / wp{N}_data
        / wp{N}_we`` wire groups appear on the synthesised module.
    shared_port:
        If ``True``, read and write slot pools are merged into a single pool of
        size 1.  A read and a write cannot occur in the same cycle — this maps
        to a true single-port Block RAM (Xilinx BRAM SP mode, Intel M20K SP).
        Hazard resolution moves to the pipeline controller (stall logic).

        If ``False`` (default), reads and writes use independent slot pools and
        can proceed concurrently on separate physical buses.  RAW hazard
        comparators and forwarding muxes are generated inside the register file
        module by MLS.

    Example::

        # Standard RISC-V: 2 read ports, 1 write port, separate buses
        regfile: IndexedRegFile[zdc.u5, zdc.u32] = zdc.indexed_regfile()

        # FPGA single-port BRAM
        regfile: IndexedRegFile[zdc.u5, zdc.u32] = zdc.indexed_regfile(
            read_ports=1, write_ports=1, shared_port=True
        )
    """
    return dc.field(default=None, metadata={
        'kind':        'indexed_regfile',
        'read_ports':  read_ports,
        'write_ports': write_ports,
        'shared_port': shared_port,
    })


def indexed_pool(
        depth:    int           = 32,
        noop_idx: int | None    = None,
) -> Any:
    """Declare an :class:`IndexedPool` field on a Component.

    Parameters
    ----------
    depth:
        Number of addressable slots — should match the number of registers
        (e.g. 32 for RV32/RV64) or whatever indexed resource the pool tracks.
    noop_idx:
        Optional slot index whose lock / share operations are no-ops.
        Use ``noop_idx=0`` for RISC-V so that writes to ``x0`` and reads of
        ``x0`` never consume a scoreboard slot and never generate hazard
        comparators in the synthesised hardware.

    Example::

        # RISC-V integer scoreboard — x0 is always a no-op
        rd_sched: IndexedPool[zdc.u5] = zdc.indexed_pool(depth=32, noop_idx=0)
    """
    meta: dict = {
        'kind':     'indexed_pool',
        'depth':    depth,
        'noop_idx': noop_idx,
    }
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
        width=None,
        soft=None):
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
    
    if soft is not None:
        metadata["soft_default"] = soft
    
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


def array(depth: int, default=None) -> Any:
    """Marks a fixed-size array field.

    The array has exactly ``depth`` elements, fixed at elaboration time.
    No elements can be added or removed at runtime.

    Use with ``zdc.Array[T]`` as the field type annotation::

        _cpuregs: zdc.Array[zdc.u32] = zdc.array(32)

    Args:
        depth:   Number of elements (must be a positive integer).
        default: Optional per-element reset/default value.
    """
    metadata: dict = {"kind": "array", "depth": depth}
    if default is not None:
        metadata["default"] = default
    return dc.field(default_factory=list, metadata=metadata)


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
    """Declare a *required* API port on a Component — the consumer side.

    A ``port`` field must be bound before the component is used.  Binding
    supplies the concrete implementation of the declared API.

    Two annotation forms are supported:

    **Callable port** — a single async function::

        icache: Callable[[zdc.u32], Awaitable[zdc.u32]] = zdc.port()

        # Bind at construction:
        core = RVCore(icache=my_fetch_fn)

        # Use inside a body:
        insn = await self.comp.icache(self.pc_in)

    **Protocol port** — a duck-typed object with named async methods::

        dcache: DCacheIface = zdc.port()   # DCacheIface is a typing.Protocol

        # Bind at construction (whole object):
        core = RVCore(dcache=MockCache())

        # Use inside a body:
        data = await self.comp.dcache.load(addr, funct3)

    Ports can also be wired inside a containing component via ``__bind__``::

        def __bind__(self):
            return {
                self.core.icache: self.mem.fetch,       # Callable form
                self.core.dcache: self.mem,             # Protocol form (whole object)
                self.core.dcache.load: self._do_load,  # Protocol form (per-method)
            }

    During synthesis the synthesizer maps each port to ready-valid SV channels:
    a Callable port becomes a single req/resp pair; a Protocol port becomes one
    req/resp pair per method.

    See ``zdc.export()`` for the provider side.
    """
    return dc.field(init=False, metadata={"kind": "port"})

def export():
    """Declare an *offered* API export on a Component — the provider side.

    An ``export`` field advertises that this component implements the declared
    API and can be bound to a matching ``port`` on another component.

    The annotation follows the same two forms as ``zdc.port()``:

    **Callable export**::

        fetch: Callable[[zdc.u32], Awaitable[zdc.u32]] = zdc.export()

    **Protocol export**::

        mem_iface: MemIface = zdc.export()   # MemIface is a typing.Protocol

    Binding is set up by the containing component's ``__bind__`` method, or
    at construction time by the consumer that holds both the port and the
    export::

        def __bind__(self):
            return {self.requester.api: self.provider}

    See ``zdc.port()`` for the consumer side.
    """
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
    clock : Optional[str] = dc.field(default=None)
    reset : Optional[str] = dc.field(default=None)
    reset_async : bool = dc.field(default=False)
    reset_active_low : bool = dc.field(default=True)

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

def sync(clock: str = None, reset: str = None,
         reset_async: bool = False, reset_active_low: bool = True):
    """
    Decorator for synchronous processes.
    
    The process is evaluated on positive edge of clock or reset.
    Assignments in sync processes are deferred - they take effect
    after the method completes but before next evaluation.
    
    Args:
        clock: Clock field name or lambda (e.g. ``"clk"`` or ``lambda s: s.clk``).
        reset: Reset field name or lambda (e.g. ``"rst_n"``).
        reset_async: If ``True``, generate ``always_ff @(posedge clk or [neg/pos]edge rst)``
            sensitivity list (asynchronous reset). Default: ``False`` (synchronous reset).
        reset_active_low: If ``True`` (default), reset asserts low (active-low, e.g. ``rst_n``).
            Controls the edge polarity in the async sensitivity list: ``negedge rst_n``.
            If ``False``, reset asserts high: ``posedge rst``.
        
    Example:
        @zdc.sync(clock="clk", reset="rst_n")
        def _count(self):
            if self.reset:
                self.count = 0
            else:
                self.count += 1

        # Asynchronous active-low reset:
        @zdc.sync(clock="clk", reset="rst_n", reset_async=True, reset_active_low=True)
        def _ff(self):
            if self.rst_n == 0:
                self.q = 0
            else:
                self.q = self.d
    """
    def decorator(method):
        return ExecSync(method=method, clock=clock, reset=reset,
                        reset_async=reset_async, reset_active_low=reset_active_low)
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


def enum(cls=None, *, width: int = None):
    """Declare a synthesizable enum type.

    Marks a plain Python class as a synthesizable HDL enum. The class body
    must contain integer-valued class attributes (members). The decorated class
    gains ``_zdc_enum = True``, ``_zdc_enum_members``, ``_zdc_enum_width``, and
    a ``_zdc_data_type`` attribute pointing at the corresponding
    :class:`~zuspec.dataclasses.ir.data_type.DataTypeEnum` IR node.

    Usage::

        @zdc.enum
        class State:
            IDLE  = 0
            FETCH = 1
            EXEC  = 2

        @zdc.enum(width=4)    # explicit bit width
        class Opcode:
            ADD = 0
            SUB = 1

    The bit width is inferred from the number of members if not specified:
    ``ceil(log2(len(members) + 1))`` bits, with a minimum of 1.

    Args:
        cls: The class to decorate (when used as ``@zdc.enum`` without arguments).
        width: Optional explicit bit width for the enum type.

    Returns:
        The decorated class (with ``_zdc_enum`` markers and IR node attached).
    """
    import math
    from .ir.data_type import DataTypeEnum

    def _apply(cls):
        members = {
            k: v for k, v in cls.__dict__.items()
            if not k.startswith('_') and isinstance(v, int)
        }
        inferred_width = width if width is not None else max(
            1, math.ceil(math.log2(max(len(members), 1) + 1))
        )
        cls._zdc_enum = True
        cls._zdc_enum_members = members
        cls._zdc_enum_width = inferred_width
        cls._zdc_data_type = DataTypeEnum(
            name=cls.__name__,
            items=dict(members),
            width=inferred_width,
            py_type=cls,
        )
        return cls

    return _apply(cls) if cls is not None else _apply


# ---------------------------------------------------------------------------
# Pipeline process support
# ---------------------------------------------------------------------------

class PipelineError(Exception):
    """Raised when a ``@zdc.pipeline`` body violates the pipeline contract.

    Common causes:

    - A ``@zdc.stage`` method is declared ``async def`` (not allowed).
    - A ``@zdc.stage`` method is missing parameter type annotations.
    - The pipeline root body contains non-stage calls.
    - A RAW hazard cannot be resolved given the ``forward=`` setting.
    """


class _LegacyForwardingDecl:
    """Returned by the deprecated :func:`forward` helper for backward compat."""
    __slots__ = ("signal", "from_stage", "to_stage")

    def __init__(self, signal: str, from_stage: str = "", to_stage: str = "") -> None:
        self.signal = signal
        self.from_stage = from_stage
        self.to_stage = to_stage


def forward(signal: str = "", from_stage: str = "", to_stage: str = "") -> "_LegacyForwardingDecl":
    """Deprecated — use ``@zdc.stage`` ``no_forward`` annotation instead.

    Previously used as ``forward=[zdc.forward(signal="x", ...)]`` in the
    ``@zdc.pipeline`` decorator; the old sentinel-based pipeline API no longer
    requires this helper.  It is kept only for backward compatibility and will
    be removed in a future release.
    """
    import warnings
    warnings.warn(
        "zdc.forward() is deprecated. "
        "Use @zdc.stage(no_forward=True) in the new method-per-stage API instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _LegacyForwardingDecl(signal=signal, from_stage=from_stage, to_stage=to_stage)


class _StageDSL:
    """Singleton DSL object for pipeline stage decoration and meta-methods.

    **As a decorator** — decorate stage methods on a pipeline component:

    .. code-block:: python

        @zdc.stage
        def IF(self) -> tuple[zdc.u32, zdc.u32]:
            ...

        @zdc.stage(no_forward=True)
        def MEM(self, alu_result: zdc.u32, ...) -> ...:
            ...

    **As meta-methods** inside stage and sync bodies (synthesizer annotations;
    all are no-ops at Python runtime):

    .. code-block:: python

        zdc.stage.stall(~self.imem_valid)
        zdc.stage.cancel(cond=is_nop)
        zdc.stage.flush(self.IF, cond=mispredicted)
        ok = zdc.stage.valid(self.ID)
        rdy = zdc.stage.ready(self.IF)
        stld = zdc.stage.stalled(self.MEM)

    **Multi-cycle stages**

    By default each stage occupies one pipeline register (one clock-cycle
    latency).  Use ``cycles=N`` to insert additional pipeline registers::

        # Form A — at definition site (applies everywhere this stage is used)
        @zdc.stage(cycles=2)
        def EX(self, insn: zdc.u32) -> (zdc.u32,):
            ...

        # Form B — at call site (overrides Form A for this pipeline body only)
        @zdc.pipeline(clock='clk', reset='rst_n')
        def execute(self):
            (insn,) = self.IF()
            with zdc.stage.cycles(3):      # EX expanded to 3 substages here
                (result,) = self.EX(insn)
            self.WB(result)

    Form B overrides Form A when both are present.
    Substages are named ``EX_c1``, ``EX_c2``, …, ``EX_cN`` in generated Verilog.
    """

    def __call__(self, func=None, *, no_forward: bool = False, cycles: int = 1):
        """Handle both ``@zdc.stage`` (bare) and ``@zdc.stage(...)`` forms.

        Args:
            func:        The stage method, when used as a bare decorator.
            no_forward:  When True, exclude all outputs of this stage from
                         forwarding; generate stall logic instead.
            cycles:      Number of pipeline registers for this stage (≥ 1).
                         Defaults to 1.  Can be overridden per call-site with
                         ``with zdc.stage.cycles(N):`` in the pipeline body.

        Raises:
            ValueError: If *cycles* is less than 1.
        """
        if cycles < 1:
            raise ValueError(f"@zdc.stage cycles must be >= 1, got {cycles!r}")
        if func is not None:
            # Bare @zdc.stage form
            func._zdc_stage = True
            func._zdc_stage_no_forward = False
            func._zdc_stage_cycles = 1
            return func
        # Parametric @zdc.stage(no_forward=..., cycles=...) form
        def decorator(method):
            method._zdc_stage = True
            method._zdc_stage_no_forward = no_forward
            method._zdc_stage_cycles = cycles
            return method
        return decorator

    @staticmethod
    def stall(cond=None):
        """Suppress valid propagation to the next stage while *cond* is true.

        This is a synthesizer annotation; it is a no-op at Python runtime.

        The current stage remains valid (transaction is paused, not discarded).
        All upstream stages are frozen as well.  The next stage receives a bubble.

        Args:
            cond: Combinational Boolean condition; may be keyword ``cond=``.
        """

    @staticmethod
    def cancel(cond: bool = True):
        """Clear this stage's valid without freezing upstream.

        This is a synthesizer annotation; it is a no-op at Python runtime.

        The transaction in this stage is discarded (as if it never happened).
        Upstream stages continue to advance normally.

        Args:
            cond: Combinational Boolean enable; defaults to ``True``.
        """

    @staticmethod
    def flush(target, cond: bool = True):
        """Flush (invalidate) a target stage.

        This is a synthesizer annotation; it is a no-op at Python runtime.

        Priority: flush > cancel > stall > normal propagation.

        Args:
            target: The stage method reference (e.g. ``self.IF``).
            cond:   Combinational Boolean enable; defaults to ``True``.
        """

    @staticmethod
    def valid(stage_method) -> bool:
        """Return True if *stage_method*'s stage holds a live transaction.

        Synthesizer query — substituted with ``{STAGE}_valid`` in RTL;
        always returns False at Python runtime.

        Args:
            stage_method: Stage method reference (e.g. ``self.ID``).
        """
        return False

    @staticmethod
    def ready(stage_method) -> bool:
        """Return True if *stage_method*'s stage can accept a new transaction.

        Synthesizer query — substituted with ``(~{STAGE}_valid | ~{STAGE}_stalled)``;
        always returns True at Python runtime.

        Args:
            stage_method: Stage method reference (e.g. ``self.IF``).
        """
        return True

    @staticmethod
    def stalled(stage_method) -> bool:
        """Return True if *stage_method*'s stage is currently stalled.

        Synthesizer query — substituted with ``{STAGE}_stalled`` in RTL;
        always returns False at Python runtime.

        Args:
            stage_method: Stage method reference (e.g. ``self.MEM``).
        """
        return False

    @staticmethod
    def cycles(n: int):
        """Override the number of pipeline registers for the enclosed stage call(s).

        This is a synthesizer annotation; it is a no-op at Python runtime.
        The enclosed ``self.STAGE(...)`` calls are each expanded into *n* pipeline
        registers (substages) during synthesis.

        Args:
            n: Number of pipeline registers (≥ 1).  ``n=1`` is the default and
               has no effect.

        Raises:
            ValueError: If *n* is less than 1.

        Example::

            @zdc.pipeline(clock='clk', reset='rst_n')
            def execute(self):
                (insn,) = self.IF()
                with zdc.stage.cycles(3):
                    (result,) = self.EX(insn)   # EX split into 3 pipeline stages
                self.WB(result)
        """
        import contextlib

        if n < 1:
            raise ValueError(f"zdc.stage.cycles n must be >= 1, got {n!r}")

        @contextlib.contextmanager
        def _cm():
            yield

        return _cm()


#: Singleton DSL object.  Use ``@zdc.stage`` to decorate stage methods and
#: ``zdc.stage.stall/cancel/flush/valid/ready/stalled(...)`` inside bodies.
stage = _StageDSL()


def pipeline(
    clock: str = None,
    reset: str = None,
    forward=True,
    no_forward: list = None,
    stages=None,  # Deprecated: kept for backward compat with old sentinel-based API
):
    """Decorator for pipeline processes.

    Unlike ``@zdc.sync`` (which describes single-cycle sequential logic), a
    pipeline process describes a single *transaction* flowing through multiple
    clock-edge boundaries.  Multiple transactions are in-flight simultaneously;
    the hardware repeats the body continuously, accepting a new transaction each
    cycle.

    The body must be a plain ``def`` (not ``async def``) and its body is a
    sequence of ``self.STAGE(args)`` calls, one per ``@zdc.stage`` method,
    in pipeline order.

    Args:
        clock:      Clock field name (e.g. ``"clk"``).
        reset:      Reset field name (e.g. ``"rst_n"``).
        forward:    Process-level default for unresolved RAW hazards:
                    ``True`` (default) — forward via bypass mux;
                    ``False`` — stall.
        no_forward: Optional list of signal names to exclude from forwarding
                    at the process level (per-signal escape hatch).
        stages:     Deprecated.  Accepted for backward compatibility with the
                    old sentinel-based API; ignored by the new
                    ``PipelineFrontendPass``.

    Example::

        @zdc.pipeline(clock="clk", reset="rst_n", forward=True)
        def execute(self):
            pc, insn = self.IF()
            rs1, rs2, rd = self.ID(insn)
            result = self.EX(rs1, rs2)
            self.WB(rd, result)
    """
    def decorator(method):
        method._zdc_pipeline        = True
        method._zdc_pipeline_clock  = clock
        method._zdc_pipeline_reset  = reset
        method._zdc_pipeline_forward = forward
        method._zdc_pipeline_no_forward = no_forward or []
        # Store for backward compat with PipelineAnnotationPass
        method._zdc_pipeline_stages = stages
        return method
    return decorator

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
