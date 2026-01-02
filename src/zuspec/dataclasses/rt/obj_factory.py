from __future__ import annotations
import asyncio
import contextvars
import dataclasses as dc
import functools
import inspect
from typing import cast, ClassVar, Dict, List, Type, Optional, Any, Tuple, get_origin, get_args, get_type_hints, TypeAliasType, TYPE_CHECKING
from ..config import ObjFactory as ObjFactoryP
from ..decorators import ExecProc, ExecSync, ExecComb, Input, Output
from ..types import Component, Extern, Lock, Memory, AddressSpace, RegFile, Reg, U, S, At
from ..tlm import Channel, GetIF, PutIF, Transport
from .comp_impl_rt import CompImplRT
from .timebase import Timebase
from .memory_rt import MemoryRT
from .address_space_rt import AddressSpaceRT
from .regfile_rt import RegFileRT, RegRT
from .channel_rt import ChannelRT, GetIFRT, PutIFRT
from .lock_rt import LockRT
from .event_rt import EventRT
from ._bundle_proxy import BundleProxy

if TYPE_CHECKING:
    from .. import Event
    from .tracer import Tracer, Thread

# Context variable to track the current thread
_current_thread: contextvars.ContextVar[Optional['Thread']] = contextvars.ContextVar('_current_thread', default=None)

class SignalDescriptor:
    """Property descriptor that intercepts signal access and routes to eval infrastructure."""
    def __init__(self, name: str, field_type: type, is_input: bool, default_value: int = 0, width: int = 32):
        self.name = name
        self.field_type = field_type
        self.is_input = is_input
        self.default_value = default_value
        self.width = width
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        
        # Use signal_read if eval is initialized
        if hasattr(obj, '_impl') and obj._impl and obj._impl._eval_initialized:
            return obj._impl.signal_read(obj, self.name)
        
        # Fallback during construction
        if hasattr(obj, '_impl') and obj._impl:
            return obj._impl._signal_values.get(self.name, self.default_value)
        
        return self.default_value
    
    def __set__(self, obj, value):
        # Use signal_write if eval is initialized
        if hasattr(obj, '_impl') and obj._impl:
            if obj._impl._eval_initialized:
                obj._impl.signal_write(obj, self.name, value, self.width)
            else:
                # During construction or for simple components, store directly
                old_value = obj._impl._signal_values.get(self.name)
                obj._impl._signal_values[self.name] = value
                
                # Still notify tracer if signal tracing is enabled
                if old_value != value and obj._impl._enable_signal_tracing:
                    obj._impl._notify_signal_tracer(obj, self.name, old_value, value, self.width)

class BindPath:
    """Represents a path in the binding system (e.g., self.cons.call or self.p.prod)"""
    def __init__(self, root, path: Tuple[str, ...]):
        self._root = root
        self._path = path
    
    def __getattr__(self, name):
        return BindPath(self._root, self._path + (name,))
    
    def __repr__(self):
        return f"BindPath({'.'.join(self._path)})"

class InterfaceImpl:
    """Dynamic object to hold bound methods for exports/ports"""
    def __init__(self):
        pass


class TupleRT:
    """Runtime wrapper for fixed-size tuple fields.

    Behaves like a tuple for indexing/iteration, and forwards attribute access
    (eg `.m2m`) to element 0 for convenience.
    """

    def __init__(self, elems):
        self._elems = tuple(elems)

    def __len__(self):
        return len(self._elems)

    def __iter__(self):
        return iter(self._elems)

    def __getitem__(self, idx):
        return self._elems[idx]

    def __getattr__(self, name):
        if len(self._elems) == 0:
            raise AttributeError(name)
        return getattr(self._elems[0], name)

class BindProxy:
    """Proxy object that records attribute access for binding"""
    def __init__(self, comp):
        object.__setattr__(self, '_comp', comp)
        object.__setattr__(self, '_paths', {})
    
    def __getattr__(self, name):
        # Check if this is a field on the component
        comp = object.__getattribute__(self, '_comp')
        if hasattr(comp, name):
            attr = getattr(comp, name)
            # For component fields, methods, etc., return a BindPath
            return BindPath(comp, (name,))
        raise AttributeError(f"'{type(comp).__name__}' has no attribute '{name}'")

@dc.dataclass
class ObjFactory(ObjFactoryP):
    comp_type_m : Dict[Type[Component],Type[Component]] = dc.field(default_factory=dict)
    comp_s : List[Component] = dc.field(default_factory=list)
    tracer : Optional['Tracer'] = dc.field(default=None)
    enable_signal_tracing : bool = dc.field(default=False)
    _inst : ClassVar = None
    _next_tid : int = dc.field(default=0)

    @classmethod
    def inst(cls):
        if cls._inst is None:
            cls._inst = ObjFactory()
        return cls._inst
    
    def _get_tid(self) -> int:
        """Get next task ID for tracing."""
        tid = self._next_tid
        self._next_tid += 1
        return tid

    def mkComponent(self, cls : Type[Component], **kwargs) -> Component:
        if cls in self.comp_type_m.keys():
            cls_rt = self.comp_type_m[cls]
        else:
            fields = []
            namespace = {}
            signal_fields = []  # Track signal fields to create properties

#            if "__post_init__" in cls.__dict__.keys():
#                namespace["__post_init__"] = cls.__dict__["__post_init__"]

            # Resolve annotations to handle postponed evaluation (from __future__ import annotations)
            try:
                type_hints = get_type_hints(cls, include_extras=True)
            except Exception:
                type_hints = {}

            field_names = set()

            const_defaults = {}
            for cf in dc.fields(cls):
                if cf.metadata and cf.metadata.get('kind') == 'const':
                    const_defaults[cf.name] = cf.default if cf.default is not dc.MISSING else 0

            for f in dc.fields(cls):
                field_type = type_hints.get(f.name, f.type)
                origin = get_origin(field_type)

                if inspect.isclass(field_type) and Extern in getattr(field_type, '__mro__', ()):
                    raise RuntimeError(
                        f"Extern type '{field_type.__qualname__}' is not supported in rt"
                    )
                
                # Check if this is an Input or Output field (marker via default_factory)
                is_signal = False
                is_input = False
                is_field_signal = False
                
                if f.default_factory is not dc.MISSING:
                    if f.default_factory is Input:
                        is_signal = True
                        is_input = True
                    elif f.default_factory is Output:
                        is_signal = True
                        is_input = False
                
                # Also check if this is a regular field with a bit type (should participate in eval)
                # Bit types can be Annotated[int, U(...)] or direct type references
                if not is_signal and f.init:
                    # Check for Annotated types (e.g., bit8 = Annotated[int, U(width=8)])
                    from typing import Annotated
                    if origin is not None and origin is Annotated:
                        # It's an Annotated type, likely a bit type
                        is_signal = True
                        is_field_signal = True
                    elif hasattr(field_type, '__name__'):
                        type_name = getattr(field_type, '__name__', '')
                        # Check for bit types (bit, bit8, bit16, etc.) or uint types
                        if (type_name.startswith('bit') or type_name.startswith('uint') or 
                            type_name.startswith('int') and type_name.endswith('_t')):
                            is_signal = True
                            is_field_signal = True
                
                if is_signal:
                    # Store signal field metadata including default value - don't add to dataclass fields
                    default_value = f.default if f.default is not dc.MISSING else 0
                    
                    # Extract width from metadata/type annotation
                    width = 32  # default

                    if f.metadata and 'width' in f.metadata:
                        spec = f.metadata.get('width')
                        if callable(spec):
                            tmp = type('Tmp', (), const_defaults)()
                            width = int(spec(tmp))
                        else:
                            width = int(spec)

                    from typing import Annotated
                    if origin is not None and origin is Annotated:
                        args = get_args(field_type)
                        if args and len(args) > 1:
                            for meta in args[1:]:
                                if isinstance(meta, (U, S)):
                                    width = meta.width
                                    break
                    elif hasattr(field_type, '__metadata__'):
                        for meta in field_type.__metadata__:
                            if isinstance(meta, (U, S)):
                                width = meta.width
                                break
                    elif hasattr(field_type, '__name__'):
                        # Try to parse width from type name (e.g., bit8, uint16_t)
                        type_name = field_type.__name__
                        if type_name.startswith('bit') and type_name[3:].isdigit():
                            width = int(type_name[3:])
                        elif type_name.startswith('uint') and type_name.endswith('_t'):
                            mid = type_name[4:-2]
                            if mid.isdigit():
                                width = int(mid)
                        elif type_name == 'bit':
                            width = 1
                    
                    signal_fields.append((f.name, field_type, is_input, default_value, width))
                    continue
                
                field_kind = f.metadata.get('kind') if f.metadata else None

                # Handle instance fields (auto-constructed)
                if field_kind == 'instance':
                    metadata = dict(f.metadata) if f.metadata else {}
                    ctor_kwargs = metadata.get('kwargs')

                    if field_type is Lock:
                        fields.append((f.name, object, dc.field(default_factory=LockRT, metadata=metadata)))
                    elif inspect.isclass(field_type):
                        if callable(ctor_kwargs):
                            # Needs parent instance to evaluate
                            fields.append((f.name, field_type, dc.field(default=None, metadata=metadata)))
                        elif isinstance(ctor_kwargs, dict):
                            def _mk_inst(_t=field_type, _kw=dict(ctor_kwargs)):
                                return _t(**_kw)
                            fields.append((f.name, field_type, dc.field(default_factory=_mk_inst, metadata=metadata)))
                        else:
                            fields.append((f.name, field_type, dc.field(default_factory=field_type, metadata=metadata)))
                    elif getattr(field_type, '_is_protocol', False):
                        raise RuntimeError(
                            f"Cannot auto-construct Protocol type '{getattr(field_type, '__qualname__', str(field_type))}' for field '{f.name}'"
                        )
                    else:
                        fields.append((f.name, object, dc.field(default=None, metadata=metadata)))

                # Handle fixed-size tuple fields
                elif field_kind == 'tuple':
                    size = 0
                    if f.metadata and 'size' in f.metadata:
                        size = f.metadata['size']
                    elem_factory = f.metadata.get('elem_factory') if f.metadata else None

                    # Derive element type from annotation Tuple[T]
                    elem_t = None
                    if origin is tuple:
                        args = get_args(field_type)
                        if args:
                            elem_t = args[0]

                    if elem_factory is None:
                        elem_factory = elem_t

                    if size == 0:
                        raise RuntimeError(f"Tuple field '{f.name}' must specify a non-zero size")
                    if elem_factory is None:
                        raise RuntimeError(f"Tuple field '{f.name}' missing element type")
                    if getattr(elem_factory, '_is_protocol', False):
                        raise RuntimeError(
                            f"Tuple field '{f.name}' element type is a Protocol; specify elem_factory"
                        )

                    def _mk_tuple(_t=elem_factory, _sz=size):
                        def _mk_elem():
                            if _t is Lock:
                                return LockRT()
                            if inspect.isclass(_t):
                                return _t()
                            raise RuntimeError(f"Cannot construct tuple element type '{_t}'")
                        return TupleRT(_mk_elem() for _ in range(_sz))

                    fields.append((f.name, object, dc.field(default_factory=_mk_tuple, metadata=f.metadata)))

                # Check if this is a Memory field
                elif origin is not None and origin is Memory:
                    # Memory fields will be initialized in __comp_build__
                    # Store the original type in metadata for later use
                    metadata = dict(f.metadata) if f.metadata else {}
                    metadata['__memory_type__'] = field_type
                    fields.append((f.name, object, dc.field(
                        default=None,
                        metadata=metadata)))
                # Check if this is a Channel field
                elif origin is not None and origin is Channel:
                    # Channel fields will be initialized in __comp_build__
                    metadata = dict(f.metadata) if f.metadata else {}
                    metadata['__channel_type__'] = field_type
                    fields.append((f.name, object, dc.field(
                        default=None,
                        metadata=metadata)))
                # Check if this is a GetIF or PutIF port field
                elif origin is not None and (origin is GetIF or origin is PutIF):
                    # These are port types - they stay as None until bound
                    metadata = dict(f.metadata) if f.metadata else {}
                    if origin is GetIF:
                        metadata['__getif_type__'] = field_type
                    else:
                        metadata['__putif_type__'] = field_type
                    fields.append((f.name, object, dc.field(
                        default=None,
                        metadata=metadata)))
                # Check if this is a Transport type (TypeAliasType)
                elif origin is not None and isinstance(origin, TypeAliasType) and origin.__name__ == 'Transport':
                    # Transport is a Callable type alias for port/export bindings
                    metadata = dict(f.metadata) if f.metadata else {}
                    metadata['__transport_type__'] = field_type
                    fields.append((f.name, object, dc.field(
                        default=None,
                        metadata=metadata)))
                # Check for Lock type directly (before isclass check since Lock is a Protocol)
                elif field_type is Lock:
                    # Lock fields get auto-constructed with runtime implementation
                    fields.append((f.name, object, dc.field(default_factory=LockRT)))
                elif inspect.isclass(field_type):
                    if issubclass(field_type, Component):
                        if f.default_factory is dc.MISSING:
                            fields.append((f.name, field_type, dc.field(default_factory=field_type)))
                        # Re-author to ensure construction is proper
                    elif issubclass(field_type, AddressSpace):
                        # AddressSpace fields will be initialized in __comp_build__
                        # Store the original type in metadata for later use
                        metadata = dict(f.metadata) if f.metadata else {}
                        metadata['__aspace_type__'] = field_type
                        fields.append((f.name, object, dc.field(
                            default=None,
                            metadata=metadata)))
                    elif issubclass(field_type, RegFile):
                        # RegFile fields will be initialized in __comp_build__
                        metadata = dict(f.metadata) if f.metadata else {}
                        metadata['__regfile_type__'] = field_type
                        fields.append((f.name, object, dc.field(
                            default=None,
                            metadata=metadata)))
                    elif not f.init:
                        fields.append((f.name, field_type, dc.field(
                            default=None,
                            metadata=f.metadata)))
            # TODO: Copy over 

            # for f in dir(cls):
            #     if not f.startswith("_") and f not in field_names:
            #         print("Field: %s" % f)
            #         fo = getattr(cls, f)
            #         if isinstance(fo, )

            cls_rt = dc.make_dataclass(
                cls.__name__,
                fields,
                namespace=namespace,
                kw_only=True,
                bases=(cls,))
            self.comp_type_m[cls] = cls_rt
            
            # Add signal properties after class creation
            for sig_name, sig_type, is_input, default_value, width in signal_fields:
                descriptor = SignalDescriptor(sig_name, sig_type, is_input, default_value, width)
                setattr(cls_rt, sig_name, descriptor)

            # Wrap async methods for tracing if tracer is enabled
            if self.tracer is not None:
                self._wrap_async_methods(cls_rt)

            # Only set up __init__ wrapper once when creating the class
            setattr(cls_rt, "__dc_init__", getattr(cls_rt, "__init__"))
            setattr(cls_rt, "__init__", self.__comp_init__)

        # Just a placeholder at this point
        kwargs["_impl"] = None

        comp = Component.__new__(cls_rt, **kwargs)
        
        return cast(Component, comp)
    
    def _wrap_async_methods(self, cls_rt: Type[Component]):
        """Wrap async methods for tracing.
        
        Only wraps user-defined async methods (not inherited from Component base class).
        """
        # Get methods from the original class (before runtime wrapping)
        for name in dir(cls_rt):
            if name.startswith('_'):
                continue
            
            attr = getattr(cls_rt, name)
            if not inspect.iscoroutinefunction(attr):
                continue
            
            # Skip methods inherited from Component base class
            if hasattr(Component, name):
                continue
            
            # Create wrapped version
            original_method = attr
            
            @functools.wraps(original_method)
            async def wrapped_method(self, *args, _original=original_method, _method_name=name, **kwargs):
                tracer = self._impl._tracer if self._impl else None
                
                # If no tracer, just call original method
                if tracer is None:
                    return await _original(self, *args, **kwargs)
                
                from .tracer import Thread
                
                timebase = self._impl.timebase() if self._impl else None
                
                # Get parameter names for building args dict
                sig = inspect.signature(_original)
                bound_args = sig.bind(self, *args, **kwargs)
                bound_args.apply_defaults()
                
                # Build args dict excluding 'self'
                args_dict = {k: v for k, v in bound_args.arguments.items() if k != 'self'}
                
                # Get or create thread context
                current_thread = _current_thread.get()
                if current_thread is None:
                    # This is a top-level call - create a new thread
                    tid = ObjFactory.inst()._get_tid()
                    thread = Thread(tid=tid, parent=None, component=None)
                else:
                    # This is a nested call - reuse the current thread
                    thread = current_thread
                
                # Get current time for enter event
                if timebase:
                    enter_time_ns = timebase.time().as_ns()
                else:
                    enter_time_ns = 0
                
                tracer.enter(_method_name, thread, enter_time_ns, args_dict)
                
                # Set this thread as the current context for nested calls
                token = _current_thread.set(thread)
                
                exc = None
                ret = None
                try:
                    ret = await _original(self, *args, **kwargs)
                    return ret
                except Exception as e:
                    exc = e
                    raise
                finally:
                    # Restore previous context
                    _current_thread.reset(token)
                    
                    # Get current time for leave event
                    if timebase:
                        leave_time_ns = timebase.time().as_ns()
                    else:
                        leave_time_ns = enter_time_ns
                    
                    tracer.leave(_method_name, thread, leave_time_ns, ret, exc)
            
            setattr(cls_rt, name, wrapped_method)
    
    def mkEvent(self, cls : Type['Event'], **kwargs) -> 'Event':
        """Create an Event instance with runtime implementation."""
        event_rt = EventRT()
        return cast('Event', event_rt)

    def mkRegFile(self, cls : Type[RegFile], **kwargs) -> RegFile:
        """Create a standalone RegFile instance."""
        # Create the runtime regfile instance
        regfile_rt = RegFileRT()
        
        # Iterate through the RegFile's fields to create individual registers
        offset = 0
        for reg_field in dc.fields(cls):
            reg_field_type = reg_field.type
            reg_origin = get_origin(reg_field_type)
            
            # Check if this is a Reg field
            if reg_origin is not None and reg_origin is Reg:
                # Get the element type from the generic parameter
                args = get_args(reg_field_type)
                element_type = args[0] if args else int
                
                # Extract width from the element type
                width = 32  # default
                if hasattr(element_type, '__metadata__'):
                    metadata = element_type.__metadata__
                    if metadata:
                        for item in metadata:
                            if isinstance(item, (U, S)):
                                width = item.width
                                break
                
                # Create the runtime register instance
                reg_rt = RegRT(_value=0, _width=width, _element_type=element_type)
                
                # Add register to regfile
                regfile_rt.add_register(reg_field.name, reg_rt, offset)
                
                # Create a property-like object that allows access to the register
                setattr(regfile_rt, reg_field.name, reg_rt)
                
                # Advance offset (assuming 32-bit registers aligned on 4-byte boundaries)
                offset += 4
        
        return cast(RegFile, regfile_rt)

    @staticmethod 
    def __comp_init__(comp, *args, **kwargs):
        """Wrapper around component __init__. Allows the 
        factory to elaborate the component tree
        """
        self = ObjFactory.inst()
        
        # Extract port bindings from kwargs (fields with "port" metadata)
        port_bindings = {}
        for f in dc.fields(type(comp)):
            if f.metadata and f.metadata.get("kind") == "port":
                if f.name in kwargs:
                    port_bindings[f.name] = kwargs.pop(f.name)
            
        self.comp_s.append(comp)
        # __dc_init__ is already bound to comp, so don't pass comp again
        getattr(comp, "__dc_init__")(*args, **kwargs)
        self.comp_s.pop()

        if len(self.comp_s) == 0:
            # Initialize the component tree after initialization
            # of the root component
            timebase = Timebase()
            ObjFactory.__comp_build__(comp, None, "", timebase, port_bindings)
            # Validate that all top-level ports are bound
            ObjFactory.__validate_top_level_ports__(comp)
            # Note: Processes are started lazily when the simulation runs,
            # not during construction (no event loop available yet)

    @staticmethod
    def __comp_build__(comp, parent, name, timebase: Timebase, port_bindings: Dict[str, Any] = None):
        factory = ObjFactory.inst()
        tracer = factory.tracer
        enable_signal_tracing = factory.enable_signal_tracing
        comp._impl = CompImplRT(
            _factory=None, 
            _name=name, 
            _parent=parent, 
            _tracer=tracer,
            _enable_signal_tracing=enable_signal_tracing
        )
        
        # Register signals with tracer if signal tracing is enabled
        if enable_signal_tracing and tracer is not None:
            ObjFactory.__register_signals_with_tracer__(comp, tracer, parent)
        
        # Set timebase on root component
        if parent is None:
            comp._impl.set_timebase(timebase)

        # Discover @process decorated methods
        # Note: @sync and @comb methods are discovered through datamodel, not here
        has_eval = False
        for attr_name in dir(type(comp)):
            attr = getattr(type(comp), attr_name, None)
            if isinstance(attr, ExecProc):
                comp._impl.add_process(attr_name, attr)
            elif isinstance(attr, (ExecSync, ExecComb)):
                has_eval = True
        
        # Initialize evaluation infrastructure if component has sync/comb processes
        if has_eval:
            comp._impl._init_eval(comp)

        # Initialize instance fields that require parent context before discovering children
        ObjFactory.__init_instance_fields__(comp)

        # Build child components first (bottom-up)
        for f in dc.fields(comp):
            fo = getattr(comp, f.name)
            if isinstance(fo, Component):
                ObjFactory.__comp_build__(fo, comp, f.name, timebase)
            elif isinstance(fo, TupleRT):
                for i, e in enumerate(fo):
                    if isinstance(e, Component):
                        ObjFactory.__comp_build__(e, comp, f"{f.name}[{i}]", timebase)
            elif isinstance(fo, tuple) or isinstance(fo, list):
                for i, e in enumerate(fo):
                    if isinstance(e, Component):
                        ObjFactory.__comp_build__(e, comp, f"{f.name}[{i}]", timebase)
        
        # Initialize Memory fields
        ObjFactory.__init_memory_fields__(comp)
        
        # Initialize RegFile fields
        ObjFactory.__init_regfile_fields__(comp)
        
        # Initialize AddressSpace fields
        ObjFactory.__init_address_space_fields__(comp)
        
        # Initialize Channel fields
        ObjFactory.__init_channel_fields__(comp)

        # Initialize Bundle fields
        ObjFactory.__init_bundle_fields__(comp)
        
        # Apply port bindings provided at construction (for top-level ports)
        if port_bindings:
            for port_name, impl in port_bindings.items():
                setattr(comp, port_name, impl)

        # Apply bindmap after children are built
        if hasattr(comp, "__bind__"):
            # Create a proxy for binding that captures paths
            proxy = BindProxy(comp)

            # Call __bind__ with the proxy as self to capture paths
            bind_method = comp.__bind__
            if bind_method.__code__.co_argcount > 0:
                # Method takes self, call with proxy
                import types
                bound_method = types.MethodType(bind_method.__func__, proxy)
                bindmap = bound_method()
            else:
                bindmap = bind_method()

            if bindmap is not None:
                # Allow returning either a dict or an iterable of (lhs,rhs) pairs
                if not isinstance(bindmap, dict):
                    if isinstance(bindmap, (tuple, list)) and len(bindmap) == 2 and not (
                        isinstance(bindmap[0], (tuple, list)) and len(bindmap[0]) == 2
                    ):
                        bindmap = (bindmap,)
                    bindmap = dict(bindmap)
                ObjFactory.__apply_bindmap__(comp, bindmap)

    @staticmethod
    def __register_signals_with_tracer__(comp, tracer, parent):
        """Register all signals on a component with the tracer.
        
        This allows the tracer to know about all signals before value changes occur,
        which is needed for VCD header generation.
        """
        from .tracer import SignalTracer
        if not isinstance(tracer, SignalTracer):
            return
        
        # Build component path
        parts = []
        c = comp
        while c is not None:
            impl = c._impl if hasattr(c, '_impl') and c._impl else None
            if impl is not None:
                if impl._name:
                    parts.append(impl._name)
                else:
                    parts.append(type(c).__name__)
                c = impl._parent
            else:
                parts.append(type(c).__name__)
                break
        parts.reverse()
        comp_path = ".".join(parts) if parts else type(comp).__name__
        
        # Register signals from SignalDescriptor properties
        for attr_name in dir(type(comp)):
            if attr_name.startswith('_'):
                continue
            attr = getattr(type(comp), attr_name, None)
            if isinstance(attr, SignalDescriptor):
                tracer.register_signal(comp_path, attr.name, attr.width, attr.is_input)

    @staticmethod
    def __init_memory_fields__(comp):
        """Initialize Memory fields with their runtime implementations."""
        for f in dc.fields(comp):
            # Check if this field has Memory type info stored in metadata
            if f.metadata and '__memory_type__' in f.metadata:
                field_type = f.metadata['__memory_type__']
                
                # Get the element type from the generic parameter
                args = get_args(field_type)
                element_type = args[0] if args else int
                
                # Extract width from the element type
                width = 32  # default
                if hasattr(element_type, '__metadata__'):
                    metadata = element_type.__metadata__
                    if metadata:
                        for item in metadata:
                            if isinstance(item, (U, S)):
                                width = item.width
                                break
                
                # Get size from field metadata
                size = 1024  # default
                if f.metadata and 'size' in f.metadata:
                    size = f.metadata['size']
                
                # Create the runtime memory instance
                mem_rt = MemoryRT(
                    _size=size,
                    _element_type=element_type,
                    _width=width
                )
                
                # Set the field value to the runtime instance
                setattr(comp, f.name, mem_rt)

    @staticmethod
    def __init_address_space_fields__(comp):
        """Initialize AddressSpace fields with their runtime implementations."""
        for f in dc.fields(comp):
            # Check if this field has AddressSpace type info stored in metadata
            if f.metadata and '__aspace_type__' in f.metadata:
                # Create the runtime address space instance
                aspace_rt = AddressSpaceRT()
                # Set the field value to the runtime instance
                setattr(comp, f.name, aspace_rt)

    @staticmethod
    def __init_regfile_fields__(comp):
        """Initialize RegFile fields with their runtime implementations."""
        for f in dc.fields(comp):
            # Check if this field has RegFile type info stored in metadata
            if f.metadata and '__regfile_type__' in f.metadata:
                field_type = f.metadata['__regfile_type__']
                
                # Create the runtime regfile instance
                regfile_rt = RegFileRT()
                
                # Iterate through the RegFile's fields to create individual registers
                offset = 0
                for reg_field in dc.fields(field_type):
                    reg_field_type = reg_field.type
                    reg_origin = get_origin(reg_field_type)
                    
                    # Check if this is a Reg field
                    if reg_origin is not None and reg_origin is Reg:
                        # Get the element type from the generic parameter
                        args = get_args(reg_field_type)
                        element_type = args[0] if args else int
                        
                        # Extract width from the element type
                        width = 32  # default
                        if hasattr(element_type, '__metadata__'):
                            metadata = element_type.__metadata__
                            if metadata:
                                for item in metadata:
                                    if isinstance(item, (U, S)):
                                        width = item.width
                                        break
                        
                        # Create the runtime register instance
                        reg_rt = RegRT(_value=0, _width=width, _element_type=element_type)
                        
                        # Add register to regfile
                        regfile_rt.add_register(reg_field.name, reg_rt, offset)
                        
                        # Create a property-like object that allows access to the register
                        setattr(regfile_rt, reg_field.name, reg_rt)
                        
                        # Advance offset (assuming 32-bit registers aligned on 4-byte boundaries)
                        offset += 4
                
                # Set the field value to the runtime instance
                setattr(comp, f.name, regfile_rt)

    @staticmethod
    def __init_channel_fields__(comp):
        """Initialize Channel fields with their runtime implementations."""
        for f in dc.fields(comp):
            # Check if this field has Channel type info stored in metadata
            if f.metadata and '__channel_type__' in f.metadata:
                field_type = f.metadata['__channel_type__']
                
                # Get the element type from the generic parameter
                args = get_args(field_type)
                element_type = args[0] if args else None
                
                # Create the runtime channel instance
                channel_rt = ChannelRT(_element_type=element_type)
                
                # Set the field value to the runtime instance
                setattr(comp, f.name, channel_rt)

    @staticmethod
    def __init_instance_fields__(comp):
        """Initialize instance fields that require evaluating kwargs against the parent instance."""
        factory = ObjFactory.inst()
        factory.comp_s.append(comp)
        try:
            for f in dc.fields(comp):
                kind = f.metadata.get('kind') if f.metadata else None
                if kind != 'instance':
                    continue
                ctor_kwargs = f.metadata.get('kwargs') if f.metadata else None
                if not callable(ctor_kwargs):
                    continue
                if getattr(comp, f.name) is not None:
                    continue

                field_type = f.type
                kw = ctor_kwargs(comp)
                if kw is not None and not isinstance(kw, dict):
                    raise RuntimeError(f"Field '{f.name}' kwargs must be dict or callable returning dict")

                if field_type is Lock:
                    setattr(comp, f.name, LockRT())
                elif inspect.isclass(field_type):
                    setattr(comp, f.name, field_type(**(kw or {})))
        finally:
            factory.comp_s.pop()

    @staticmethod
    def __init_bundle_fields__(comp):
        """Initialize bundle/mirror/monitor fields by creating BundleProxy objects."""
        for f in dc.fields(comp):
            kind = f.metadata.get('kind') if f.metadata else None
            if kind not in ('bundle', 'mirror', 'monitor'):
                continue

            bundle_t = f.type
            is_mirror = (kind == 'mirror')

            const_fields = {}
            signal_dirs = {}
            signal_widths = {}

            # Helper for evaluating lambda widths against const fields
            def _eval_width(spec):
                if spec is None:
                    return 32
                if callable(spec):
                    tmp = type('Tmp', (), const_fields)()
                    return int(spec(tmp))
                return int(spec)

            if hasattr(bundle_t, '__dataclass_fields__'):
                # Pass 1: collect const defaults
                for bf in dc.fields(bundle_t):
                    bf_kind = bf.metadata.get('kind') if bf.metadata else None
                    if bf_kind == 'const':
                        const_fields[bf.name] = bf.default if bf.default is not dc.MISSING else 0

                # Apply field-level ctor kwargs overrides
                ctor_kwargs = f.metadata.get('kwargs') if f.metadata else None
                ctor_kwargs = ctor_kwargs(comp) if callable(ctor_kwargs) else ctor_kwargs
                if ctor_kwargs:
                    if not isinstance(ctor_kwargs, dict):
                        raise RuntimeError(f"Field '{f.name}' kwargs must be dict or callable returning dict")
                    const_fields.update(ctor_kwargs)

                # Pass 2: build signal directions and widths
                for bf in dc.fields(bundle_t):
                    bf_kind = bf.metadata.get('kind') if bf.metadata else None
                    if bf_kind == 'const':
                        continue

                    # Determine signal direction from input()/output()
                    is_in = (bf.default_factory is Input) if bf.default_factory is not dc.MISSING else False
                    is_out = (bf.default_factory is Output) if bf.default_factory is not dc.MISSING else False

                    if is_mirror:
                        is_in, is_out = is_out, is_in

                    if is_in or is_out:
                        signal_dirs[bf.name] = 'in' if is_in else 'out'
                        width = _eval_width(bf.metadata.get('width') if bf.metadata else None)
                        signal_widths[bf.name] = width

                        sig_full = f"{f.name}.{bf.name}"
                        if sig_full not in comp._impl._signal_values:
                            default_v = bf.default if bf.default is not dc.MISSING else 0
                            comp._impl._signal_values[sig_full] = default_v
                        comp._impl._signal_widths[sig_full] = width

            setattr(comp, f.name, BundleProxy(comp, f.name, const_fields, signal_dirs, signal_widths))

    @staticmethod
    def __apply_bindmap__(comp, bindmap):
        """Apply bindmap entries by setting target values to source values.
        
        Bindmap is a dictionary where keys are targets and values are sources.
        Both should be BindPath objects that represent attribute paths.
        - Targets: Port, ExportMethod (fields or methods that need assignment)
        - Sources: Export, Method (fields or methods to be assigned from)
        - Special case: AddressSpace.mmap targets get At() objects for memory mapping
        - Special case: Event.at targets get callbacks bound
        """
        # Process AddressSpace.mmap and Event.at bindings first
        aspace_bindings = []
        event_bindings = []
        other_bindings = {}
        
        for target, source in bindmap.items():
            # Check if target is a path to .mmap attribute
            if isinstance(target, BindPath) and len(target._path) >= 2 and target._path[-1] == 'mmap':
                aspace_bindings.append((target, source))
            # Check if target is a path to .at attribute (Event callback)
            elif isinstance(target, BindPath) and len(target._path) >= 2 and target._path[-1] == 'at':
                event_bindings.append((target, source))
            else:
                other_bindings[target] = source
        
        # Handle AddressSpace.mmap bindings
        for target, source in aspace_bindings:
            # Get the AddressSpace object
            aspace_path = target._path[:-1]  # Remove 'mmap' from path
            aspace = ObjFactory.__resolve_bind_path__(comp, BindPath(comp, aspace_path))
            
            if isinstance(aspace, AddressSpaceRT):
                # source can be a single At object or a tuple of At objects
                at_list = [source] if isinstance(source, At) else (source if isinstance(source, tuple) else [source])
                
                for at_obj in at_list:
                    if isinstance(at_obj, At):
                        # Resolve the storage element (could be a BindPath to Memory)
                        storage = at_obj.element
                        if isinstance(storage, BindPath):
                            storage = ObjFactory.__resolve_bind_path__(comp, storage)
                        
                        # Add the mapping to the address space
                        aspace.add_mapping(at_obj.offset, storage)
        
        # Handle Event.at bindings (callback binding)
        for target, source in event_bindings:
            # Get the Event object
            event_path = target._path[:-1]  # Remove 'at' from path
            event = ObjFactory.__resolve_bind_path__(comp, BindPath(comp, event_path))
            
            if isinstance(event, EventRT):
                # Get the callback (source should be a method reference)
                callback = ObjFactory.__resolve_bind_path__(comp, source)
                # Bind the callback to the event
                event.bind_callback(callback)
        
        # Sort bindmap entries: prioritize entries where source is available
        # Process in order: Export->Port, Method->ExportMethod, Port->ExportMethod
        ordered_entries = ObjFactory.__order_bindmap__(comp, other_bindings)
        
        for target, source in ordered_entries:
            # Get source value by traversing from comp
            source_value = ObjFactory.__resolve_bind_path__(comp, source)

            # Bundle-to-bundle binding: connect signals based on direction
            if isinstance(target, BindPath) and isinstance(source, BindPath):
                try:
                    target_value = ObjFactory.__resolve_bind_path__(comp, target)
                except AttributeError:
                    target_value = None
                if isinstance(target_value, BundleProxy) and isinstance(source_value, BundleProxy):
                    # Resolve owning components
                    def _owner_and_field(p: BindPath):
                        o = comp
                        for part in p._path[:-1]:
                            o = getattr(o, part)
                        return o, p._path[-1]

                    a_comp, a_field = _owner_and_field(target)
                    b_comp, b_field = _owner_and_field(source)

                    a_dirs = object.__getattribute__(target_value, '_signal_dirs')
                    b_dirs = object.__getattribute__(source_value, '_signal_dirs')

                    for sig in set(a_dirs.keys()) & set(b_dirs.keys()):
                        a_dir = a_dirs[sig]
                        b_dir = b_dirs[sig]

                        if a_dir == 'out' and b_dir == 'in':
                            a_comp._impl.add_signal_binding(f"{a_field}.{sig}", b_comp, f"{b_field}.{sig}")
                        elif b_dir == 'out' and a_dir == 'in':
                            b_comp._impl.add_signal_binding(f"{b_field}.{sig}", a_comp, f"{a_field}.{sig}")

                    # Do not overwrite bundle proxies with setattr
                    continue
            
            # Bundle-signal / signal binding: bind at the signal layer (no setattr on BundleProxy)
            if isinstance(target, BindPath) and isinstance(source, BindPath):
                def _signal_endpoint(p: BindPath):
                    # Bundle signal reference: <bundle>.<sig>
                    if len(p._path) >= 2:
                        owner = comp
                        for part in p._path[:-2]:
                            owner = getattr(owner, part)
                        bundle_field = p._path[-2]
                        sig = p._path[-1]
                        try:
                            bundle = getattr(owner, bundle_field)
                        except Exception:
                            bundle = None
                        if isinstance(bundle, BundleProxy):
                            dirs = object.__getattribute__(bundle, '_signal_dirs')
                            if sig in dirs:
                                widths = object.__getattribute__(bundle, '_signal_widths')
                                return (owner, f"{bundle_field}.{sig}", dirs.get(sig), len(p._path), True, widths.get(sig, 32))

                    # Scalar signal reference: <sig>
                    owner = comp
                    if len(p._path) > 1:
                        for part in p._path[:-1]:
                            owner = getattr(owner, part)
                    if len(p._path) == 0:
                        return None
                    sig = p._path[-1]
                    desc = getattr(type(owner), sig, None)
                    if isinstance(desc, SignalDescriptor):
                        return (owner, sig, ('in' if desc.is_input else 'out'), len(p._path), False, getattr(desc, 'width', 32))
                    return None

                t_ep = _signal_endpoint(target)
                s_ep = _signal_endpoint(source)
                if t_ep is not None and s_ep is not None:
                    # Default: explicit (target <- source)
                    src_ep = s_ep
                    dst_ep = t_ep

                    s_dir = s_ep[2]
                    t_dir = t_ep[2]
                    s_depth = s_ep[3]
                    t_depth = t_ep[3]
                    s_is_bundle = s_ep[4]
                    t_is_bundle = t_ep[4]

                    # Prefer out->in based on direction
                    if t_dir == 'out' and s_dir == 'in':
                        src_ep, dst_ep = t_ep, s_ep
                    # For input-input, prefer parent/bundle driving child
                    elif s_dir == t_dir == 'in':
                        if s_is_bundle != t_is_bundle:
                            src_ep = s_ep if s_is_bundle else t_ep
                            dst_ep = t_ep if s_is_bundle else s_ep
                        elif s_depth != t_depth:
                            src_ep = s_ep if s_depth < t_depth else t_ep
                            dst_ep = t_ep if s_depth < t_depth else s_ep
                    # For output-output, prefer child driving parent/bundle
                    elif s_dir == t_dir == 'out':
                        if s_is_bundle != t_is_bundle:
                            src_ep = s_ep if not s_is_bundle else t_ep
                            dst_ep = t_ep if not s_is_bundle else s_ep
                        elif s_depth != t_depth:
                            src_ep = s_ep if s_depth > t_depth else t_ep
                            dst_ep = t_ep if s_depth > t_depth else s_ep

                    src_comp, src_sig, _src_dir, _src_depth, _src_is_bundle, src_w = src_ep
                    dst_comp, dst_sig, _dst_dir, _dst_depth, _dst_is_bundle, _dst_w = dst_ep

                    if hasattr(src_comp, '_impl') and src_comp._impl and hasattr(dst_comp, '_impl') and dst_comp._impl:
                        src_comp._impl.add_signal_binding(src_sig, dst_comp, dst_sig)
                        # Ensure no extra latency: initialize target to current source value
                        dst_comp._impl._signal_values[dst_sig] = src_comp._impl._signal_values.get(src_sig, 0)
                        dst_comp._impl._signal_widths[dst_sig] = src_comp._impl._signal_widths.get(src_sig, src_w)
                        continue

            # Set target to source value by traversing from comp
            ObjFactory.__set_bind_path_value__(comp, target, source_value)
            
            # Register runtime binding for signal propagation
            # This allows clock edges to propagate from parent to child components
            if isinstance(target, BindPath) and isinstance(source, BindPath):
                # Get source component and signal name
                if len(source._path) > 0:
                    source_comp = comp
                    if len(source._path) > 1:
                        # Navigate to the component that owns this signal
                        for part in source._path[:-1]:
                            source_comp = getattr(source_comp, part)
                    source_signal = source._path[-1]
                    
                    # Get target component and signal name
                    target_comp = comp
                    if len(target._path) > 1:
                        for part in target._path[:-1]:
                            target_comp = getattr(target_comp, part)
                    target_signal = target._path[-1]
                    
                    # Register binding: when source_signal changes, update target_signal
                    if hasattr(source_comp, '_impl') and source_comp._impl:
                        source_comp._impl.add_signal_binding(source_signal, target_comp, target_signal)

    @staticmethod
    def __order_bindmap__(comp, bindmap):
        """Order bindmap entries.
        
        Priority order:
        1. Sources that are simple methods (Method)
        2. Sources that are exports (Export)
        3. Port-to-ExportMethod connections (processed after sources)
        """
        entries = list(bindmap.items())
        
        # Categorize entries based on metadata
        method_bindings = []  # Method -> ExportMethod
        export_bindings = []  # Export -> Port
        other_bindings = []   # Other connections
        
        for target, source in entries:
            if isinstance(target, BindPath) and isinstance(source, BindPath):
                # Check the source path to categorize
                source_obj = ObjFactory.__get_obj_at_path__(comp, source._path[:-1]) if len(source._path) > 1 else comp
                source_attr = source._path[-1] if source._path else None
                
                if source_attr and hasattr(source_obj, source_attr):
                    attr_val = getattr(source_obj, source_attr)
                    if callable(attr_val):
                        # It's a method
                        method_bindings.append((target, source))
                    else:
                        # Check metadata for export/port
                        metadata = ObjFactory.__get_field_metadata__(source_obj, source_attr)
                        if metadata and metadata.get("kind") == "export":
                            export_bindings.append((target, source))
                        else:
                            other_bindings.append((target, source))
                else:
                    other_bindings.append((target, source))
            elif isinstance(source, BindPath):
                # Source is a path, determine what it points to
                source_obj = ObjFactory.__resolve_bind_path__(comp, source)
                if callable(source_obj):
                    method_bindings.append((target, source))
                else:
                    other_bindings.append((target, source))
            else:
                other_bindings.append((target, source))
        
        # Return ordered list: methods first, then exports, then others
        return method_bindings + export_bindings + other_bindings

    @staticmethod
    def __get_field_metadata__(obj, field_name):
        """Get metadata for a field by name."""
        if hasattr(obj, '__dataclass_fields__'):
            fields_dict = obj.__dataclass_fields__
            if field_name in fields_dict:
                return fields_dict[field_name].metadata
        return None

    @staticmethod
    def __get_obj_at_path__(comp, path: Tuple[str, ...]):
        """Get the object at a given path from comp."""
        obj = comp
        for attr_name in path:
            obj = getattr(obj, attr_name)
        return obj

    @staticmethod
    def __resolve_bind_path__(comp, path_obj):
        """Resolve a BindPath to its actual value by traversing from comp.
        
        If path_obj is already a value (not a BindPath), return it.
        Otherwise, traverse the path from comp to find the value.
        """
        if isinstance(path_obj, BindPath):
            obj = comp
            for attr_name in path_obj._path:
                obj = getattr(obj, attr_name)
            return obj
        
        # If it's a bound method or other callable, return it directly
        return path_obj

    @staticmethod
    def __set_bind_path_value__(comp, target, value):
        """Set a target field/method to a value by traversing from comp.
        
        The target represents a BindPath like self.cons.call or self.p.prod.
        We need to traverse to the parent object and set the final attribute.
        
        For paths like self.cons.call where cons is None, we need to:
        1. Create an InterfaceImpl object for cons
        2. Set the call attribute on that object
        """
        if isinstance(target, BindPath):
            # Traverse to the parent object
            obj = comp
            for i, attr_name in enumerate(target._path[:-1]):
                next_obj = getattr(obj, attr_name)
                
                # If we encounter None and this is an export/port field, create InterfaceImpl
                if next_obj is None:
                    # Check if this is an export or port field
                    metadata = ObjFactory.__get_field_metadata__(obj, attr_name)
                    if metadata and metadata.get("kind") in ["export", "port"]:
                        # Create an InterfaceImpl object
                        next_obj = InterfaceImpl()
                        setattr(obj, attr_name, next_obj)
                
                obj = next_obj
            
            # Set the final attribute
            final_attr = target._path[-1]
            setattr(obj, final_attr, value)
        else:
            # Fallback for non-BindPath targets
            if hasattr(target, "__self__"):
                parent_obj = target.__self__
                if hasattr(target, "__name__"):
                    setattr(parent_obj, target.__name__, value)

    @staticmethod
    def __start_processes__(comp):
        """Recursively start all processes in the component tree."""
        # Start processes for child components first
        for f in dc.fields(comp):
            fo = getattr(comp, f.name)
            if isinstance(fo, Component):
                ObjFactory.__start_processes__(fo)
        
        # Start processes for this component
        comp._impl.start_processes(comp)

    @staticmethod
    def __validate_top_level_ports__(comp):
        """Validate that all ports on the root component are bound.
        
        Top-level ports must be bound during construction since there is
        no parent component to provide bindings.
        """
        unbound_ports = []
        for f in dc.fields(comp):
            if f.metadata and f.metadata.get("kind") == "port":
                port_value = getattr(comp, f.name, None)
                if port_value is None:
                    unbound_ports.append(f.name)
        
        if unbound_ports:
            raise RuntimeError(
                f"Top-level component '{type(comp).__name__}' has unbound ports: {', '.join(unbound_ports)}. "
                f"Top-level ports must be bound by passing an implementation during construction, "
                f"e.g., MyComponent({unbound_ports[0]}=my_impl)"
            )

    pass

