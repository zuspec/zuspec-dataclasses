from __future__ import annotations
import dataclasses as dc
import inspect
from typing import cast, ClassVar, Dict, List, Type, Optional, Any, Tuple, get_origin, get_args
from ..config import ObjFactory as ObjFactoryP
from ..decorators import ExecProc
from ..types import Component, Lock, Memory, AddressSpace, RegFile, Reg, U, S, At
from .comp_impl_rt import CompImplRT
from .timebase import Timebase
from .memory_rt import MemoryRT
from .address_space_rt import AddressSpaceRT
from .regfile_rt import RegFileRT, RegRT

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
    _inst : ClassVar = None

    @classmethod
    def inst(cls):
        if cls._inst is None:
            cls._inst = ObjFactory()
        return cls._inst

    def mkComponent(self, cls : Type[Component], **kwargs) -> Component:
        if cls in self.comp_type_m.keys():
            cls_rt = self.comp_type_m[cls]
        else:
            fields = []
            namespace = {}

#            if "__post_init__" in cls.__dict__.keys():
#                namespace["__post_init__"] = cls.__dict__["__post_init__"]

            field_names = set()
            for f in dc.fields(cls):
                field_type = f.type
                origin = get_origin(field_type)
                
                # Check if this is a Memory field
                if origin is not None and origin is Memory:
                    # Memory fields will be initialized in __comp_build__
                    # Store the original type in metadata for later use
                    metadata = dict(f.metadata) if f.metadata else {}
                    metadata['__memory_type__'] = field_type
                    fields.append((f.name, object, dc.field(
                        default=None,
                        metadata=metadata)))
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
                    elif issubclass(field_type, Lock):
                        # Lock fields get auto-constructed
                        fields.append((f.name, field_type, dc.field(default_factory=Lock)))
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

            # Only set up __init__ wrapper once when creating the class
            setattr(cls_rt, "__dc_init__", getattr(cls_rt, "__init__"))
            setattr(cls_rt, "__init__", self.__comp_init__)

        # Just a placeholder at this point
        kwargs["_impl"] = None

        comp = Component.__new__(cls_rt, **kwargs)
        
        return cast(Component, comp)

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
                reg_rt = RegRT(_value=0, _width=width)
                
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
        comp._impl = CompImplRT(_factory=None, _name=name, _parent=parent)
        
        # Set timebase on root component
        if parent is None:
            comp._impl.set_timebase(timebase)

        # Discover @process decorated methods
        for attr_name in dir(type(comp)):
            attr = getattr(type(comp), attr_name, None)
            if isinstance(attr, ExecProc):
                comp._impl.add_process(attr_name, attr)

        # Build child components first (bottom-up)
        for f in dc.fields(comp):
            fo = getattr(comp, f.name)
            if isinstance(fo, Component):
                ObjFactory.__comp_build__(fo, comp, f.name, timebase)
        
        # Initialize Memory fields
        ObjFactory.__init_memory_fields__(comp)
        
        # Initialize RegFile fields
        ObjFactory.__init_regfile_fields__(comp)
        
        # Initialize AddressSpace fields
        ObjFactory.__init_address_space_fields__(comp)
        
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
                ObjFactory.__apply_bindmap__(comp, bindmap)

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
                        reg_rt = RegRT(_value=0, _width=width)
                        
                        # Add register to regfile
                        regfile_rt.add_register(reg_field.name, reg_rt, offset)
                        
                        # Create a property-like object that allows access to the register
                        setattr(regfile_rt, reg_field.name, reg_rt)
                        
                        # Advance offset (assuming 32-bit registers aligned on 4-byte boundaries)
                        offset += 4
                
                # Set the field value to the runtime instance
                setattr(comp, f.name, regfile_rt)

    @staticmethod
    def __apply_bindmap__(comp, bindmap):
        """Apply bindmap entries by setting target values to source values.
        
        Bindmap is a dictionary where keys are targets and values are sources.
        Both should be BindPath objects that represent attribute paths.
        - Targets: Port, ExportMethod (fields or methods that need assignment)
        - Sources: Export, Method (fields or methods to be assigned from)
        - Special case: AddressSpace.mmap targets get At() objects for memory mapping
        """
        # Process AddressSpace.mmap bindings first
        aspace_bindings = []
        other_bindings = {}
        
        for target, source in bindmap.items():
            # Check if target is a path to .mmap attribute
            if isinstance(target, BindPath) and len(target._path) >= 2 and target._path[-1] == 'mmap':
                aspace_bindings.append((target, source))
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
        
        # Sort bindmap entries: prioritize entries where source is available
        # Process in order: Export->Port, Method->ExportMethod, Port->ExportMethod
        ordered_entries = ObjFactory.__order_bindmap__(comp, other_bindings)
        
        for target, source in ordered_entries:
            # Get source value by traversing from comp
            source_value = ObjFactory.__resolve_bind_path__(comp, source)
            
            # Set target to source value by traversing from comp
            ObjFactory.__set_bind_path_value__(comp, target, source_value)

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

