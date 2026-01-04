
from typing import Union, Iterator, Type, get_type_hints, Any, Optional, Protocol, get_origin, get_args, Annotated
import dataclasses as dc
import inspect
import ast
from .ir.context import Context
from .ir.data_type import (
    DataType, DataTypeInt, DataTypeStruct, DataTypeClass,
    DataTypeComponent, DataTypeExtern, DataTypeProtocol, DataTypeRef, DataTypeString,
    DataTypeLock, DataTypeEvent, DataTypeMemory, DataTypeChannel, DataTypeGetIF, DataTypePutIF,
    DataTypeTuple,
    Function, Process
)
from .ir.fields import Field, FieldKind, Bind, FieldInOut
from .ir.stmt import (
    Stmt, Arguments, Arg,
    StmtFor, StmtWhile, StmtExpr, StmtAssign, StmtAugAssign, StmtPass, StmtReturn, StmtIf,
    StmtAssert, StmtAssume, StmtCover, StmtMatch, StmtMatchCase,
)
from .ir.expr import ExprCall, ExprAttribute, ExprConstant, ExprRef, ExprBin, BinOp, AugOp, ExprRefField, TypeExprRefSelf, ExprRefPy, ExprAwait, ExprRefParam, ExprRefLocal, ExprRefUnresolved, ExprCompare, ExprSubscript, ExprBool
from .types import TypeBase, Component, Extern, Lock, Memory

# Import Event at runtime to avoid circular dependency
def _get_event_type():
    from . import Event
    return Event
from .tlm import Channel, GetIF, PutIF
from .decorators import ExecProc, ExecSync, ExecComb, Input, Output


@dc.dataclass
class ConversionScope:
    """Scope context for AST to datamodel conversion"""
    component: DataTypeComponent = None  # Current component being processed
    field_indices: dict = dc.field(default_factory=dict)    # field_name -> index
    method_params: set = dc.field(default_factory=set)      # Parameter names in current method
    local_vars: set = dc.field(default_factory=set)         # Local variables in current scope


def _create_bind_proxy_class(target_cls: type, field_indices: dict, field_types: dict):
    """Create a dynamic proxy class that can be used to evaluate __bind__ with super() support.
    
    The proxy class inherits from the target class's base to support super() calls.
    """
    
    class _BindProxyBase:
        """Mixin that provides the proxy behavior for capturing field references."""
        
        def __new__(cls, *args, **kwargs):
            # Bypass any custom __new__ from parent classes
            return object.__new__(cls)
        
        def __init__(self, field_indices: dict, field_types: dict, expr: ExprRef = None):
            object.__setattr__(self, '_field_indices', field_indices)
            object.__setattr__(self, '_field_types', field_types)
            object.__setattr__(self, '_expr', expr if expr is not None else TypeExprRefSelf())
        
        def __getattribute__(self, name: str):
            # Always allow access to proxy-internal attributes
            if name in ('_field_indices', '_field_types', '_expr') or name.startswith('__'):
                return object.__getattribute__(self, name)

            field_indices = object.__getattribute__(self, '_field_indices')
            field_types = object.__getattribute__(self, '_field_types')
            expr = object.__getattribute__(self, '_expr')

            # Allow binding to dataclass fields that start with '_' (eg internal sub-instances)
            if name.startswith('_') and name not in field_indices:
                return object.__getattribute__(self, name)

            if name in field_indices:
                index = field_indices[name]
                new_expr = ExprRefField(base=expr, index=index)
                
                if name in field_types:
                    hints, field_type = field_types[name]
                    if field_type is not None and hasattr(field_type, '__dataclass_fields__'):
                        nested_indices = {}
                        nested_types = {}
                        idx = 0
                        for fname, fval in field_type.__dataclass_fields__.items():
                            if not fname.startswith('_'):
                                nested_indices[fname] = idx
                                try:
                                    nested_hints = get_type_hints(field_type)
                                    nested_type = nested_hints.get(fname)
                                    nested_types[fname] = (nested_hints, nested_type)
                                except Exception:
                                    nested_types[fname] = ({}, None)
                                idx += 1
                        return _BindProxy(nested_indices, nested_types, new_expr)
                    elif field_type is not None:
                        return _BindProxyMethod(new_expr, field_type)
                
                return _ExprRefWrapper(new_expr)
            else:
                return _ExprRefWrapper(ExprRefPy(base=expr, ref=name))
        
        def __hash__(self):
            expr = object.__getattribute__(self, '_expr')
            return hash(id(expr))
        
        def __eq__(self, other):
            return self is other
    
    # Create a proxy class that inherits from _BindProxyBase and target_cls
    # This allows super() to work correctly
    proxy_cls = type(
        f'_BindProxy_{target_cls.__name__}',
        (_BindProxyBase, target_cls),
        {
            '__new__': _BindProxyBase.__new__,
            '__init__': _BindProxyBase.__init__,
            '__getattribute__': _BindProxyBase.__getattribute__,
        }
    )
    
    return proxy_cls(field_indices, field_types)


class _BindProxy:
    """Proxy object used to capture field references during __bind__ evaluation.
    
    When accessing attributes on this proxy, it builds up ExprRefField expressions
    that capture the path to the referenced field. For example:
    - self.p becomes ExprRefField(base=TypeExprRefSelf(), index=0) for field p at index 0
    - self.p.prod becomes ExprRefField(base=ExprRefField(base=TypeExprRefSelf(), index=0), index=0)
      for field prod at index 0 of type p
    """
    def __init__(self, field_indices: dict, field_types: dict, expr: ExprRef = None):
        # field_indices maps field name -> index
        # field_types maps field name -> (type hints dict, field type class)
        object.__setattr__(self, '_field_indices', field_indices)
        object.__setattr__(self, '_field_types', field_types)
        object.__setattr__(self, '_expr', expr if expr is not None else TypeExprRefSelf())
    
    def __getattr__(self, name: str):
        field_indices = object.__getattribute__(self, '_field_indices')
        field_types = object.__getattribute__(self, '_field_types')
        expr = object.__getattribute__(self, '_expr')
        
        if name in field_indices:
            # Create ExprRefField for this field access
            index = field_indices[name]
            new_expr = ExprRefField(base=expr, index=index)
            
            # Get the type of this field to enable chained access
            if name in field_types:
                hints, field_type = field_types[name]
                if field_type is not None and hasattr(field_type, '__dataclass_fields__'):
                    # Build field indices for the nested type, excluding internal fields
                    nested_indices = {}
                    nested_types = {}
                    idx = 0
                    for fname, fval in field_type.__dataclass_fields__.items():
                        if not fname.startswith('_'):
                            nested_indices[fname] = idx
                            try:
                                nested_hints = get_type_hints(field_type)
                                nested_type = nested_hints.get(fname)
                                nested_types[fname] = (nested_hints, nested_type)
                            except Exception:
                                nested_types[fname] = ({}, None)
                            idx += 1
                    return _BindProxy(nested_indices, nested_types, new_expr)
                elif field_type is not None:
                    # Protocol or other type - allow method references via ExprRefPy
                    return _BindProxyMethod(new_expr, field_type)
            
            return _ExprRefWrapper(new_expr)
        else:
            # For method references on self (or unknown attributes), return ExprRefPy wrapped
            return _ExprRefWrapper(ExprRefPy(base=expr, ref=name))
    
    def __hash__(self):
        # Make proxy hashable so it can be used as dict key
        expr = object.__getattribute__(self, '_expr')
        return hash(id(expr))
    
    def __eq__(self, other):
        return self is other


class _ExprRefWrapper:
    """Hashable wrapper for ExprRef that can be used as dict keys."""
    def __init__(self, expr: ExprRef):
        object.__setattr__(self, '_expr', expr)
    
    def __hash__(self):
        return hash(id(self))
    
    def __eq__(self, other):
        return self is other


class _BindProxyMethod:
    """Proxy for method references on protocol types."""
    def __init__(self, base_expr: ExprRef, protocol_type: type):
        object.__setattr__(self, '_base_expr', base_expr)
        object.__setattr__(self, '_protocol_type', protocol_type)
    
    def __getattr__(self, name: str):
        base_expr = object.__getattribute__(self, '_base_expr')
        return _ExprRefWrapper(ExprRefPy(base=base_expr, ref=name))
    
    def __hash__(self):
        base_expr = object.__getattribute__(self, '_base_expr')
        return hash(id(base_expr))
    
    def __eq__(self, other):
        return self is other


class DataModelFactory(object):
    """Converts Zuspec class types to a data model context containing type-definition data models."""

    def __init__(self):
        self._context : Context = None
        self._pending : list = []  # Types pending processing
        self._processed : set = set()  # Already processed types

    def build(self, 
              types : Union[Iterator[Type[TypeBase]], Type[TypeBase]]) -> Context:
        """Build a Context containing data models for the given types."""
        self._context = Context()
        self._pending = []
        self._processed = set()
        
        # Handle single type or iterator
        if isinstance(types, type):
            types = [types]
        
        # Add all input types to pending
        for t in types:
            self._add_pending(t)
        
        # Process all pending types
        while self._pending:
            t = self._pending.pop(0)
            if t not in self._processed:
                self._process_type(t)
                self._processed.add(t)
        
        return self._context

    def _add_pending(self, t : Type):
        """Add a type to the pending list if not already processed."""
        if t is not None and t not in self._processed and t not in self._pending:
            self._pending.append(t)

    def _get_type_name(self, t : Type) -> str:
        """Get the fully qualified name for a type."""
        if hasattr(t, '__qualname__'):
            return t.__qualname__
        return t.__name__

    def _process_type(self, t : Type):
        """Process a single type and add its data model to the context."""
        type_name = self._get_type_name(t)
        
        # Skip if already in context
        if type_name in self._context.type_m:
            return
        
        # Determine type kind and process accordingly
        if self._is_extern(t):
            dm = self._process_extern(t)
        elif self._is_protocol(t):
            dm = self._process_protocol(t)
        elif self._is_component(t):
            dm = self._process_component(t)
        elif dc.is_dataclass(t):
            dm = self._process_dataclass(t)
        else:
            # Generic class
            dm = self._process_class(t)
        
        if dm is not None:
            dm.name = type_name
            dm.py_type = t
            self._context.type_m[type_name] = dm

    def _is_protocol(self, t : Type) -> bool:
        """Check if a type is a Protocol."""
        return bool(getattr(t, '_is_protocol', False))

    def _is_extern(self, t: Type) -> bool:
        """Check if a type inherits from Extern."""
        return (hasattr(t, '__mro__') and Extern in t.__mro__ and t is not Extern)

    def _is_component(self, t : Type) -> bool:
        """Check if a type inherits from Component."""
        return (hasattr(t, '__mro__') and 
                Component in t.__mro__ and 
                t is not Component)

    def _process_protocol(self, t : Type) -> DataTypeProtocol:
        """Process a Protocol type into DataTypeProtocol."""
        methods = []
        
        # Get method signatures from the protocol
        for name, member in inspect.getmembers(t):
            if name.startswith('_'):
                continue
            if callable(member) or isinstance(member, property):
                func = self._extract_function(t, name, member)
                if func is not None:
                    methods.append(func)
        
        return DataTypeProtocol(methods=methods)

    def _extract_function(self, cls : Type, name : str, member, field_indices: dict = None) -> Optional[Function]:
        """Extract a Function data model from a method."""
        # Get the function object
        if isinstance(member, property):
            return None
        
        # Try to get signature
        try:
            sig = inspect.signature(member)
        except (ValueError, TypeError):
            # For abstract methods in protocols, try to get from annotations
            if hasattr(cls, '__annotations__') and name in cls.__annotations__:
                return None
            return None
        
        # Get type hints
        try:
            hints = get_type_hints(member)
        except Exception as e:
            # get_type_hints can fail due to forward references or missing imports
            # This is acceptable - we'll just work without type hints
            hints = {}
        
        # Build arguments and collect param names for scope
        args_list = []
        param_names = set()
        for idx, (param_name, param) in enumerate(sig.parameters.items()):
            if param_name == 'self':
                continue
            annotation = hints.get(param_name)
            arg = Arg(arg=param_name, annotation=self._type_to_expr(annotation))
            args_list.append(arg)
            param_names.add(param_name)
        
        arguments = Arguments(args=args_list)
        
        # Get return type
        return_type = hints.get('return')
        returns = self._annotation_to_datatype(return_type) if return_type else None
        
        # Check if async
        is_async = inspect.iscoroutinefunction(member)
        
        # Check for @invariant decorator
        is_invariant = hasattr(member, '_is_invariant') and member._is_invariant
        
        # Create conversion scope
        scope = ConversionScope(
            field_indices=field_indices if field_indices else {},
            method_params=param_names
        )
        
        # Get method body (for actual implementations) with scope
        body = self._extract_method_body(cls, name, scope)
        
        return Function(
            name=name,
            args=arguments,
            body=body,
            returns=returns,
            is_async=is_async,
            is_invariant=is_invariant
        )

    def _type_to_expr(self, annotation) -> Optional[Any]:
        """Convert a type annotation to an expression (for now, just store as constant)."""
        if annotation is None:
            return None
        return ExprConstant(value=annotation)

    def _annotation_to_datatype(self, annotation) -> Optional[DataType]:
        """Convert a type annotation to a DataType."""
        if annotation is None:
            return None
        if annotation is int:
            return DataTypeInt()
        if annotation is str:
            return DataTypeString()
        # For other types, create a reference
        if hasattr(annotation, '__name__'):
            return DataTypeRef(ref_name=self._get_type_name(annotation))
        return None

    def _process_extern(self, t: Type) -> DataTypeExtern:
        """Process an Extern signature type into DataTypeExtern."""
        fields = self._extract_fields(t)

        extern_name = t.__name__
        attrs = getattr(t, 'attributes', None)
        if not isinstance(attrs, dict):
            attrs = getattr(t, 'annotations', None)
        if isinstance(attrs, dict) and attrs.get('name'):
            extern_name = attrs.get('name')

        return DataTypeExtern(
            super=None,
            fields=fields,
            functions=[],
            bind_map=[],
            sync_processes=[],
            comb_processes=[],
            extern_name=extern_name
        )

    def _process_component(self, t : Type) -> DataTypeComponent:
        """Process a Component type into DataTypeComponent."""
        # Get superclass data type
        super_dt = None
        for base in t.__mro__[1:]:
            if base is Component:
                break
            if self._is_component(base):
                self._add_pending(base)
                super_dt = DataTypeRef(ref_name=self._get_type_name(base))
                break
        
        # Process fields and build field indices for scope
        fields = self._extract_fields(t)
        field_indices = {f.name: idx for idx, f in enumerate(fields)}
        
        # Build field types for proxy class creation
        try:
            hints = get_type_hints(t)
        except Exception:
            hints = {}
        
        field_types = {}
        for fname in field_indices.keys():
            field_type = hints.get(fname)
            field_types[fname] = (hints, field_type)
        
        # Process functions (methods and processes)
        functions = []
        processes = []
        sync_processes = []
        comb_processes = []
        
        # First, find @process, @sync, @comb decorated methods from class __dict__
        for name, member in t.__dict__.items():
            if isinstance(member, ExecProc):
                proc = self._extract_process(t, name, member, field_indices)
                if proc is not None:
                    processes.append(proc)
            elif isinstance(member, ExecSync):
                func = self._process_sync_method(t, name, member, field_indices, field_types)
                if func is not None:
                    sync_processes.append(func)
            elif isinstance(member, ExecComb):
                func = self._process_comb_method(t, name, member, field_indices, field_types)
                if func is not None:
                    comb_processes.append(func)
        
        # Then, find regular methods (excluding those starting with _ except __bind__)
        for name, member in inspect.getmembers(t):
            if name.startswith('_') and name != '__bind__':
                continue
            
            # Skip if already processed as a process, sync, or comb
            member_in_dict = t.__dict__.get(name)
            if isinstance(member_in_dict, (ExecProc, ExecSync, ExecComb)):
                continue
            
            if callable(member) and not isinstance(member, type):
                func = self._extract_function(t, name, member, field_indices)
                if func is not None:
                    functions.append(func)
        
        # Extract bind map from __bind__ method
        bind_map = self._extract_bind_map(t)
        
        dm = DataTypeComponent(
            super=super_dt,
            fields=fields,
            functions=functions + processes,
            bind_map=bind_map,
            sync_processes=sync_processes,
            comb_processes=comb_processes
        )
        return dm

    def _extract_fields(self, t : Type) -> list:
        """Extract fields from a dataclass type."""
        fields = []
        
        if not dc.is_dataclass(t):
            return fields
        
        # Get type hints
        try:
            hints = get_type_hints(t, include_extras=True)
        except Exception as e:
            # get_type_hints can fail due to forward references or missing imports
            # This is acceptable for field extraction - we'll just work without type hints
            hints = {}
        
        for f in dc.fields(t):
            # Skip internal implementation fields
            if f.name == '_impl':
                continue
            
            # Skip internal fields (except Lock fields and explicitly typed internal fields)
            field_type = hints.get(f.name)
            # Fallback to field.type if get_type_hints failed (e.g., for generic types like XtorComponent[T])
            if field_type is None and hasattr(f, 'type'):
                field_type = f.type
                # If field_type is a string (forward reference), try to resolve it
                if isinstance(field_type, str):
                    # Try to resolve in the class's module namespace
                    if hasattr(t, '__module__'):
                        import sys
                        module = sys.modules.get(t.__module__)
                        if module and hasattr(module, field_type):
                            field_type = getattr(module, field_type)
            if f.name.startswith('_'):
                # Include Lock fields even if they start with _
                # Also include fields explicitly marked with zdc.field() by checking if they have a datatype annotation
                if not (field_type is Lock or field_type is not None):
                    continue
            
            # Check if this is an input or output port
            is_input_port = False
            is_output_port = False
            if f.default_factory is not dc.MISSING:
                if f.default_factory is Input:
                    is_input_port = True
                elif f.default_factory is Output:
                    is_output_port = True
            
            # Determine field kind from metadata
            kind = FieldKind.Field
            if f.metadata:
                field_kind = f.metadata.get('kind')
                if field_kind == 'port':
                    kind = FieldKind.Port
                elif field_kind == 'export':
                    kind = FieldKind.Export
            
            # Get field type
            origin = get_origin(field_type)
            if origin is tuple:
                args = get_args(field_type)
                elem_py_t = args[0] if args else None
                elem_dt = self._resolve_field_type(elem_py_t)

                size = 0
                if f.metadata and 'size' in f.metadata:
                    size = f.metadata['size']
                else:
                    # Support explicit fixed-length Tuple[T0,T1,...]
                    if args and len(args) > 1 and args[-1] is not Ellipsis:
                        size = len(args)

                elem_factory_dt = None
                if f.metadata and 'elem_factory' in f.metadata:
                    ef_t = f.metadata['elem_factory']
                    elem_factory_dt = DataTypeRef(ref_name=self._get_type_name(ef_t))
                    # Ensure factory type is processed
                    if hasattr(ef_t, '__mro__') and (self._is_protocol(ef_t) or self._is_extern(ef_t) or self._is_component(ef_t)):
                        self._add_pending(ef_t)

                datatype = DataTypeTuple(element_type=elem_dt, size=size, elem_factory=elem_factory_dt)

                # Add referenced element type to pending
                if elem_py_t is not None and hasattr(elem_py_t, '__mro__'):
                    if self._is_protocol(elem_py_t) or self._is_extern(elem_py_t) or self._is_component(elem_py_t):
                        self._add_pending(elem_py_t)
            else:
                datatype = self._resolve_field_type(field_type)

                # For Memory fields, extract size from metadata
                if isinstance(datatype, DataTypeMemory) and f.metadata and 'size' in f.metadata:
                    datatype.size = f.metadata['size']

                # Add referenced types to pending
                if field_type is not None and hasattr(field_type, '__mro__'):
                    if self._is_protocol(field_type) or self._is_extern(field_type) or self._is_component(field_type):
                        self._add_pending(field_type)
            
            # Check if this is a const field
            is_const = False
            if f.metadata and f.metadata.get('kind') == 'const':
                is_const = True
            
            # Extract width expression if present
            width_expr = None
            if f.metadata and 'width' in f.metadata:
                width_val = f.metadata['width']
                if callable(width_val):
                    from .ir.expr import ExprLambda
                    width_expr = ExprLambda(callable=width_val)
            
            # Extract kwargs expression if present
            kwargs_expr = None
            if f.metadata and 'kwargs' in f.metadata:
                kwargs_val = f.metadata['kwargs']
                if callable(kwargs_val):
                    from .ir.expr import ExprLambda
                    kwargs_expr = ExprLambda(callable=kwargs_val)
            
            # Try to get source location for this field
            field_loc = self._get_field_location(t, f.name)
            
            # Create FieldInOut for input/output ports, otherwise regular Field
            if is_input_port or is_output_port:
                field_dm = FieldInOut(
                    name=f.name,
                    datatype=datatype,
                    kind=kind,
                    is_out=is_output_port,  # True for output, False for input
                    width_expr=width_expr,
                    kwargs_expr=kwargs_expr,
                    is_const=is_const,
                    loc=field_loc
                )
            else:
                field_dm = Field(
                    name=f.name,
                    datatype=datatype,
                    kind=kind,
                    width_expr=width_expr,
                    kwargs_expr=kwargs_expr,
                    is_const=is_const,
                    loc=field_loc
                )
            fields.append(field_dm)
        
        return fields

    def _get_field_location(self, cls: Type, field_name: str) -> Optional['Loc']:
        """
        Get source location for a field in a class.
        
        Uses AST parsing to find the field definition and extract line/column info.
        """
        try:
            import inspect
            import ast
            from .ir.base import Loc
            
            # Get source file and lines
            source_lines, start_lineno = inspect.getsourcelines(cls)
            source_file = inspect.getsourcefile(cls)
            source = ''.join(source_lines)
            
            # Parse the source
            tree = ast.parse(source)
            
            # Find the class definition
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == cls.__name__:
                    # Find the field annotation
                    for stmt in node.body:
                        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                            if stmt.target.id == field_name:
                                # Found it! Calculate actual line number
                                actual_lineno = start_lineno + stmt.lineno - 1
                                return Loc(
                                    file=source_file,
                                    line=actual_lineno,
                                    pos=stmt.col_offset
                                )
            
            # If not found in annotations, might be a method or property
            # Return class location as fallback
            return Loc(
                file=source_file,
                line=start_lineno,
                pos=0
            )
        except Exception as e:
            # If we can't get location, return None (will default to line 1)
            return None

    def _resolve_field_type(self, field_type) -> DataType:
        """Resolve a field type annotation to a DataType."""
        if field_type is None:
            return DataType()
        
        # Handle string annotations (forward references)
        if isinstance(field_type, str):
            # String annotations will be resolved when the referenced type is processed
            # For now, return bare DataType
            return DataType()
        
        if field_type is int:
            return DataTypeInt()
        if field_type is str:
            return DataTypeString()
        if field_type is Lock:
            return DataTypeLock()
        
        # Check for Event type
        Event = _get_event_type()
        if field_type is Event or (inspect.isclass(field_type) and issubclass(field_type, Event)):
            return DataTypeEvent()
        
        # Check for Annotated types (e.g., Annotated[int, U(32)])
        origin = get_origin(field_type)
        if origin is Annotated:
            # Extract the base type and metadata
            args = get_args(field_type)
            base_type = args[0] if args else None
            metadata = args[1:] if len(args) > 1 else ()
            
            # Check if this is an annotated int with width information
            if base_type is int and metadata:
                from .types import U, S
                for m in metadata:
                    if isinstance(m, (U, S)):
                        return DataTypeInt(bits=m.width, signed=isinstance(m, S))
            
            # Fall back to resolving the base type
            return self._resolve_field_type(base_type)
        
        # Check for generic types (Memory[T], Channel[T], GetIF[T], PutIF[T], Tuple[T])
        if origin is not None:
            args = get_args(field_type)
            element_type = self._resolve_field_type(args[0]) if args else None

            if origin is tuple:
                return DataTypeTuple(element_type=element_type, size=0)
            if origin is Memory:
                # Extract size from field metadata if available
                # Size will be handled during field extraction where we have access to metadata
                return DataTypeMemory(element_type=element_type, size=1024)
            if origin is Channel:
                return DataTypeChannel(element_type=element_type)
            if origin is GetIF:
                return DataTypeGetIF(element_type=element_type)
            if origin is PutIF:
                return DataTypePutIF(element_type=element_type)
        
        if hasattr(field_type, '__name__'):
            return DataTypeRef(ref_name=self._get_type_name(field_type))
        return DataType()

    def _extract_bind_map(self, t: Type) -> list:
        """Extract bind map from __bind__ method by evaluating it with a proxy self.
        
        The bind map captures connections between ports/exports as ExprRefField expressions.
        For example, `self.p.prod : self.c.cons` becomes:
        - lhs: ExprRefField(base=ExprRefField(base=TypeExprRefSelf(), index=0), index=0)
        - rhs: ExprRefField(base=ExprRefField(base=TypeExprRefSelf(), index=1), index=0)
        """
        bind_map = []
        
        # Check if __bind__ is defined on this class (not inherited)
        if '__bind__' not in t.__dict__:
            return bind_map
        
        bind_method = t.__dict__['__bind__']
        if not callable(bind_method):
            return bind_map
        
        # Build field indices and types for the proxy
        field_indices = {}
        field_types = {}
        
        if dc.is_dataclass(t):
            try:
                hints = get_type_hints(t)
            except Exception as e:
                # get_type_hints can fail due to forward references or missing imports
                # This is acceptable for bind proxy - we'll work without type hints
                hints = {}
            
            idx = 0
            for f in dc.fields(t):
                if f.name == '_impl':
                    continue
                # Allow underscore-prefixed fields if they are explicitly typed
                if f.name.startswith('_') and hints.get(f.name) is None:
                    continue
                field_indices[f.name] = idx
                # Try to get type from hints first, fall back to field.type
                field_type = hints.get(f.name)
                if field_type is None and hasattr(f, 'type'):
                    # Use field.type as fallback when get_type_hints fails
                    # This handles generic types like XtorComponent[T] where T isn't in scope
                    field_type = f.type
                field_types[f.name] = (hints, field_type)
                idx += 1
        
        # Create proxy that supports super() calls by inheriting from target class
        proxy = _create_bind_proxy_class(t, field_indices, field_types)
        
        try:
            result = bind_method(proxy)

            if result is None:
                return bind_map

            items = None
            if isinstance(result, dict):
                items = result.items()
            elif isinstance(result, (tuple, list)):
                # Allow returning a single pair: (lhs, rhs)
                if len(result) == 2 and not (
                    isinstance(result[0], (tuple, list)) and len(result[0]) == 2
                ):
                    items = (result,)
                else:
                    items = result
            else:
                raise RuntimeError(
                    f"__bind__ must return a dict or an iterable of (lhs,rhs) pairs; got {type(result).__name__}")

            for e in items:
                try:
                    lhs, rhs = e
                except Exception:
                    raise RuntimeError(
                        f"__bind__ iterable entries must be (lhs,rhs) pairs; got {e!r}")

                # Convert proxy results to Bind entries
                lhs_expr = self._normalize_bind_expr(lhs)
                rhs_expr = self._normalize_bind_expr(rhs)
                if lhs_expr is not None and rhs_expr is not None:
                    bind = Bind(lhs=lhs_expr, rhs=rhs_expr)
                    # Validate binding rules (if this component has sync/comb processes)
                    self._validate_bind(t, bind, field_indices, field_types)
                    bind_map.append(bind)
        except Exception as e:
            # __bind__ method execution failed - this indicates a user error in the bind method
            raise RuntimeError(
                f"Failed to evaluate __bind__ method for class '{t.__name__}': {e}\n"
                f"The __bind__ method should return either a dict mapping (lhs->rhs), or an iterable of (lhs,rhs) pairs. "
                f"Example: return {{self.producer.output: self.consumer.input}} or return ((self.producer.output, self.consumer.input),)"
            ) from e
        
        return bind_map
    
    def _normalize_bind_expr(self, expr) -> Optional[ExprRef]:
        """Normalize a bind expression result to an ExprRef."""
        if isinstance(expr, ExprRef):
            return expr
        if isinstance(expr, _BindProxy):
            return object.__getattribute__(expr, '_expr')
        if isinstance(expr, _BindProxyMethod):
            return object.__getattribute__(expr, '_base_expr')
        if isinstance(expr, _ExprRefWrapper):
            return object.__getattribute__(expr, '_expr')
        return None
    
    def _validate_bind(self, component_class: Type, bind: Bind, field_indices: dict, field_types: dict):
        """Validate binding rules for port connections.
        
        Binding Rules:
        - ✅ Legal: output → input (normal signal flow)
        - ✅ Legal: input → input (wire-through/fanout)
        - ❌ Illegal: output → output (multiple drivers)
        - ✅ Legal: constant → input (tie-off)
        
        Args:
            component_class: The component class being processed
            bind: The Bind to validate
            field_indices: Field name to index mapping
            field_types: Field name to type information mapping
        """
        # Only validate if we have sync or comb processes (indicates component with evaluation)
        if not any(isinstance(member, (ExecSync, ExecComb)) for member in component_class.__dict__.values()):
            return  # Not a component with sync/comb processes, skip validation
        
        # Check if LHS is a constant (not allowed)
        if isinstance(bind.lhs, ExprConstant):
            raise ValueError(
                f"Bind error in {component_class.__name__}: "
                f"Cannot bind to a constant value on the left-hand side. "
                f"Binds must be of the form: target_port: source_signal"
            )
        
        # If RHS is a constant, this is a tie-off (always legal for inputs)
        if isinstance(bind.rhs, ExprConstant):
            # Constant bindings are always legal (tie-off to 0, 1, etc.)
            return
        
        # TODO: Full port direction validation
        # For now, we've validated the basic cases:
        # - No constants on LHS
        # - Constants on RHS are allowed (tie-offs)
        # 
        # Full validation of output→output would require walking the component
        # hierarchy and checking FieldInOut.is_out flags, which is complex during
        # construction. This could be added as a post-construction validation pass.
    
    def _resolve_bind_field(self, expr, field_indices: dict, field_types: dict) -> Optional[tuple]:
        """Resolve a bind expression to (is_input, field_name).
        
        Returns:
            Tuple of (is_input: bool, field_name: str) or None if cannot resolve
        """
        # For now, we'll just return None to skip detailed validation
        # The proper implementation would need to walk the component hierarchy
        # and check FieldInOut.is_out flags in the datamodel
        # This is complex because we're validating during datamodel construction
        # A better approach would be to validate after the full datamodel is built
        return None

    def _extract_process(self, cls : Type, name : str, exec_proc : ExecProc, field_indices: dict = None) -> Optional[Process]:
        """Extract a Process from an @process decorated method."""
        method = exec_proc.method
        
        # Create conversion scope for process
        scope = ConversionScope(
            field_indices=field_indices if field_indices else {}
        )
        
        body = self._extract_method_body(cls, method.__name__, scope)
        
        return Process(
            name=method.__name__,
            body=body
        )

    def _process_sync_method(self, cls: Type, name: str, 
                            exec_sync: ExecSync, 
                            field_indices: dict,
                            field_types: dict) -> Optional[Function]:
        """Convert a @sync decorated method to a datamodel Function."""
        
        # Create proxy instance to evaluate clock/reset lambdas
        proxy_inst = _create_bind_proxy_class(cls, field_indices, field_types)
        
        # Evaluate lambdas to get ExprRefField for clock and reset
        clock_expr = None
        reset_expr = None
        
        try:
            if exec_sync.clock is not None:
                clock_result = exec_sync.clock(proxy_inst)
                clock_expr = self._normalize_bind_expr(clock_result)
                if clock_expr is None:
                    raise ValueError(f"Clock lambda in @sync for '{name}' did not return a valid field reference")
            
            if exec_sync.reset is not None:
                reset_result = exec_sync.reset(proxy_inst)
                reset_expr = self._normalize_bind_expr(reset_result)
                if reset_expr is None:
                    raise ValueError(f"Reset lambda in @sync for '{name}' did not return a valid field reference")
        except Exception as e:
            raise RuntimeError(
                f"Failed to evaluate clock/reset lambdas for @sync method '{name}' in class '{cls.__name__}': {e}"
            ) from e
        
        # Extract method body as AST
        scope = ConversionScope(
            component=None,
            field_indices=field_indices,
            method_params=set(),
            local_vars=set()
        )
        
        try:
            body = self._extract_method_body(cls, exec_sync.method.__name__, scope)
        except Exception as e:
            raise RuntimeError(
                f"Failed to extract method body for @sync method '{name}' in class '{cls.__name__}': {e}"
            ) from e
        
        # Create Function with metadata
        func = Function(
            name=name,
            body=body,
            metadata={
                "kind": "sync",
                "clock": clock_expr,
                "reset": reset_expr,
                "method": exec_sync.method
            }
        )
        
        return func

    def _process_comb_method(self, cls: Type, name: str,
                            exec_comb: ExecComb,
                            field_indices: dict,
                            field_types: dict) -> Optional[Function]:
        """Convert a @comb decorated method to a datamodel Function."""
        
        # Extract method body
        scope = ConversionScope(
            component=None,
            field_indices=field_indices,
            method_params=set(),
            local_vars=set()
        )
        
        try:
            body = self._extract_method_body(cls, exec_comb.method.__name__, scope)
        except Exception as e:
            raise RuntimeError(
                f"Failed to extract method body for @comb method '{name}' in class '{cls.__name__}': {e}"
            ) from e
        
        # Analyze AST to extract sensitivity list
        sensitivity_list = self._extract_sensitivity_list(body)
        
        # Create Function with metadata
        func = Function(
            name=name,
            body=body,
            metadata={
                "kind": "comb",
                "sensitivity": sensitivity_list,
                "method": exec_comb.method
            }
        )
        
        return func

    def _extract_sensitivity_list(self, body: list) -> list:
        """Walk AST and collect all field references that are read."""
        
        class SensitivityVisitor:
            def __init__(self):
                self.reads = []
                self.writes = set()
            
            def visit_stmt(self, stmt):
                if isinstance(stmt, StmtAssign):
                    self.visit_stmt_assign(stmt)
                elif isinstance(stmt, StmtExpr):
                    self.visit_expr(stmt.expr)
                elif isinstance(stmt, StmtIf):
                    self.visit_expr(stmt.test)
                    for s in stmt.body:
                        self.visit_stmt(s)
                    for s in stmt.orelse:
                        self.visit_stmt(s)
                elif isinstance(stmt, StmtFor):
                    self.visit_expr(stmt.iter)
                    for s in stmt.body:
                        self.visit_stmt(s)
                    for s in stmt.orelse:
                        self.visit_stmt(s)
                elif isinstance(stmt, StmtReturn):
                    if stmt.value:
                        self.visit_expr(stmt.value)
            
            def visit_stmt_assign(self, stmt):
                # Track write targets
                for target in stmt.targets:
                    if isinstance(target, (ExprRefField, ExprAttribute)):
                        field_key = self._field_key(target)
                        if field_key is not None:
                            self.writes.add(field_key)
                # Visit RHS for reads
                self.visit_expr(stmt.value)
            
            def visit_expr(self, expr):
                if expr is None:
                    return
                
                if isinstance(expr, (ExprRefField, ExprAttribute)):
                    # Track reads (but we'll filter out writes later)
                    self.reads.append(expr)
                elif isinstance(expr, ExprCall):
                    self.visit_expr(expr.func)
                    for arg in expr.args:
                        self.visit_expr(arg)
                elif isinstance(expr, ExprBin):
                    self.visit_expr(expr.lhs)
                    self.visit_expr(expr.rhs)
                elif isinstance(expr, ExprCompare):
                    self.visit_expr(expr.left)
                    for c in expr.comparators:
                        self.visit_expr(c)
                elif isinstance(expr, ExprBool):
                    for v in expr.values:
                        self.visit_expr(v)
                # Add more expression types as needed
            
            def _field_key(self, expr) -> Optional[str]:
                """Generate a unique key for a field/path reference."""
                if isinstance(expr, ExprRefField):
                    base_k = self._field_key(expr.base)
                    return f"{base_k}[{expr.index}]" if base_k is not None else str(expr.index)
                if isinstance(expr, ExprAttribute):
                    base_k = self._field_key(expr.value)
                    return f"{base_k}.{expr.attr}" if base_k is not None else expr.attr
                if isinstance(expr, TypeExprRefSelf):
                    return "self"
                return None
        
        visitor = SensitivityVisitor()
        for stmt in body:
            visitor.visit_stmt(stmt)
        
        # Filter out writes from sensitivity list
        sensitivity = []
        for read_expr in visitor.reads:
            field_key = visitor._field_key(read_expr)
            if field_key not in visitor.writes:
                # Avoid duplicates
                if not any(visitor._field_key(s) == field_key for s in sensitivity):
                    sensitivity.append(read_expr)
        
        return sensitivity

    def _extract_method_body(self, cls : Type, method_name : str, scope: ConversionScope = None) -> list:
        """Extract the AST body of a method and convert to data model statements."""
        import textwrap
        
        try:
            source = inspect.getsource(cls)
            # Dedent to handle classes defined in indented contexts (e.g., inside functions)
            source = textwrap.dedent(source)
        except OSError as e:
            # inspect.getsource fails when source is not available (e.g., classes defined
            # in string literals passed to exec(), interactive sessions, or __main__ scripts)
            raise RuntimeError(
                f"Cannot retrieve source code for class '{cls.__name__}' method '{method_name}'. "
                f"This typically happens when classes are defined in string literals passed to exec() "
                f"or in interactive sessions. Define your classes in a proper .py module file instead. "
                f"Original error: {e}"
            ) from e
        
        try:
            source = textwrap.dedent(source)
            tree = ast.parse(source)
            
            # Find the class definition - need to handle nested classes in functions
            # Use ast.walk() but filter to the right class name
            class_node = None
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == cls.__name__:
                    class_node = node
                    break
            
            if class_node is not None:
                # Find the method in this class
                for item in class_node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name == method_name:
                            return self._convert_ast_body(item.body, scope)
        except SyntaxError as e:
            raise RuntimeError(
                f"Failed to parse source code for class '{cls.__name__}' method '{method_name}': {e}"
            ) from e
        
        return []

    def _convert_ast_body(self, body : list, scope: ConversionScope = None) -> list:
        """Convert AST statement list to data model statements."""
        stmts = []
        for node in body:
            stmt = self._convert_ast_stmt(node, scope)
            if stmt is not None:
                stmts.append(stmt)
        return stmts

    def _convert_ast_stmt(self, node : ast.AST, scope: ConversionScope = None) -> Optional[Stmt]:
        """Convert an AST statement to a data model statement."""

        def is_call_named(call: ast.Call, name: str) -> bool:
            # zdc.cover(...)
            if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name):
                return call.func.value.id == "zdc" and call.func.attr == name
            # cover(...)
            if isinstance(call.func, ast.Name):
                return call.func.id == name
            return False

        if isinstance(node, ast.Assert):
            return StmtAssert(
                test=self._convert_ast_expr(node.test, scope),
                msg=self._convert_ast_expr(node.msg, scope) if node.msg else None,
            )

        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if is_call_named(call, "assume") and len(call.args) >= 1:
                return StmtAssume(
                    test=self._convert_ast_expr(call.args[0], scope),
                    msg=self._convert_ast_expr(call.args[1], scope) if len(call.args) > 1 else None,
                )
            if is_call_named(call, "cover") and len(call.args) >= 1:
                return StmtCover(
                    test=self._convert_ast_expr(call.args[0], scope),
                    msg=self._convert_ast_expr(call.args[1], scope) if len(call.args) > 1 else None,
                )

        if isinstance(node, ast.Expr):
            expr = self._convert_ast_expr(node.value, scope)
            if expr is not None:
                return StmtExpr(expr=expr)
        elif isinstance(node, ast.For):
            # Track loop variable as local
            if scope is not None and isinstance(node.target, ast.Name):
                scope.local_vars.add(node.target.id)
            return StmtFor(
                target=self._convert_ast_expr(node.target, scope),
                iter=self._convert_ast_expr(node.iter, scope),
                body=self._convert_ast_body(node.body, scope),
                orelse=self._convert_ast_body(node.orelse, scope)
            )
        elif isinstance(node, ast.While):
            return StmtWhile(
                test=self._convert_ast_expr(node.test, scope),
                body=self._convert_ast_body(node.body, scope),
                orelse=self._convert_ast_body(node.orelse, scope) if node.orelse else []
            )
        elif isinstance(node, ast.If):
            return StmtIf(
                test=self._convert_ast_expr(node.test, scope),
                body=self._convert_ast_body(node.body, scope),
                orelse=self._convert_ast_body(node.orelse, scope)
            )
        elif isinstance(node, ast.Assign):
            # Track assigned variables as locals
            if scope is not None:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        scope.local_vars.add(target.id)
            return StmtAssign(
                targets=[self._convert_ast_expr(t, scope) for t in node.targets],
                value=self._convert_ast_expr(node.value, scope)
            )
        elif isinstance(node, ast.AugAssign):
            # Convert augmented assignment (e.g., x += 1)
            op_map = {
                ast.Add: AugOp.Add,
                ast.Sub: AugOp.Sub,
                ast.Mult: AugOp.Mult,
                ast.Div: AugOp.Div,
                ast.Mod: AugOp.Mod,
                ast.Pow: AugOp.Pow,
                ast.LShift: AugOp.LShift,
                ast.RShift: AugOp.RShift,
                ast.BitAnd: AugOp.BitAnd,
                ast.BitOr: AugOp.BitOr,
                ast.BitXor: AugOp.BitXor,
                ast.FloorDiv: AugOp.FloorDiv
            }
            op = op_map.get(type(node.op), AugOp.Add)
            return StmtAugAssign(
                target=self._convert_ast_expr(node.target, scope),
                op=op,
                value=self._convert_ast_expr(node.value, scope)
            )
        elif isinstance(node, ast.Pass):
            return StmtPass()
        elif isinstance(node, ast.Return):
            return StmtReturn(
                value=self._convert_ast_expr(node.value, scope) if node.value else None
            )
        elif isinstance(node, ast.Match):
            # Handle match/case statement (Python 3.10+)
            cases = []
            for case in node.cases:
                pattern = self._convert_ast_pattern(case.pattern, scope)
                guard = self._convert_ast_expr(case.guard, scope) if case.guard else None
                body = self._convert_ast_body(case.body, scope)
                cases.append(StmtMatchCase(
                    pattern=pattern,
                    guard=guard,
                    body=body
                ))
            return StmtMatch(
                subject=self._convert_ast_expr(node.subject, scope),
                cases=cases
            )
        return None

    def _convert_ast_expr(self, node : ast.AST, scope: ConversionScope = None) -> Optional[Any]:
        """Convert an AST expression to a data model expression."""
        if node is None:
            return None
        
        if isinstance(node, ast.Call):
            return ExprCall(
                func=self._convert_ast_expr(node.func, scope),
                args=[self._convert_ast_expr(a, scope) for a in node.args]
            )
        elif isinstance(node, ast.Attribute):
            value_expr = self._convert_ast_expr(node.value, scope)
            attr_name = node.attr
            
            # Handle self.field -> ExprRefField
            if isinstance(value_expr, TypeExprRefSelf) and scope and attr_name in scope.field_indices:
                return ExprRefField(
                    base=value_expr,
                    index=scope.field_indices[attr_name]
                )
            
            # For other cases, use ExprAttribute
            return ExprAttribute(
                value=value_expr,
                attr=attr_name
            )
        elif isinstance(node, ast.Name):
            name = node.id
            
            # Handle 'self'
            if name == "self":
                return TypeExprRefSelf()
            
            # Handle field reference
            if scope and name in scope.field_indices:
                return ExprRefField(
                    base=TypeExprRefSelf(),
                    index=scope.field_indices[name]
                )
            
            # Handle method parameter reference
            if scope and name in scope.method_params:
                return ExprRefParam(name=name)
            
            # Handle local variable reference
            if scope and name in scope.local_vars:
                return ExprRefLocal(name=name)
            
            # Unresolved - could be a builtin or external reference
            return ExprRefUnresolved(name=name)
        elif isinstance(node, ast.Constant):
            return ExprConstant(value=node.value)
        elif isinstance(node, ast.BinOp):
            return ExprBin(
                lhs=self._convert_ast_expr(node.left, scope),
                op=self._convert_binop(node.op),
                rhs=self._convert_ast_expr(node.right, scope)
            )
        elif isinstance(node, ast.Compare):
            from .ir.expr import ExprCompare
            return ExprCompare(
                left=self._convert_ast_expr(node.left, scope),
                ops=[self._convert_cmpop(op) for op in node.ops],
                comparators=[self._convert_ast_expr(comp, scope) for comp in node.comparators]
            )
        elif isinstance(node, ast.BoolOp):
            from .ir.expr import ExprBool
            return ExprBool(
                op=self._convert_boolop(node.op),
                values=[self._convert_ast_expr(v, scope) for v in node.values]
            )
        elif isinstance(node, ast.UnaryOp):
            from .ir.expr import ExprUnary
            return ExprUnary(
                op=self._convert_unaryop(node.op),
                operand=self._convert_ast_expr(node.operand, scope)
            )
        elif isinstance(node, ast.Await):
            # Preserve await expression in datamodel
            return ExprAwait(
                value=self._convert_ast_expr(node.value, scope)
            )
        elif isinstance(node, ast.IfExp):
            # Handle ternary conditional expression (a if test else b)
            from .ir.expr_phase2 import ExprIfExp
            return ExprIfExp(
                test=self._convert_ast_expr(node.test, scope),
                body=self._convert_ast_expr(node.body, scope),
                orelse=self._convert_ast_expr(node.orelse, scope)
            )
        elif isinstance(node, ast.Compare):
            # Handle comparison expressions (a == b, a < b, etc.)
            return ExprCompare(
                left=self._convert_ast_expr(node.left, scope),
                ops=[self._convert_cmpop(op) for op in node.ops],
                comparators=[self._convert_ast_expr(comp, scope) for comp in node.comparators]
            )
        elif isinstance(node, ast.List):
            # Handle list literals [a, b, c] as a constant containing the list
            # Convert to a tuple of the evaluated constant values for simpler runtime handling
            elts = [self._convert_ast_expr(elt, scope) for elt in node.elts]
            # If all elements are constants, create a constant list
            if all(isinstance(e, ExprConstant) for e in elts):
                return ExprConstant(value=[e.value for e in elts])
            # Otherwise use ExprList from phase2
            from .ir.expr_phase2 import ExprList
            return ExprList(elts=elts)
        elif isinstance(node, ast.Subscript):
            # Handle subscript operations (e.g., array[index])
            return ExprSubscript(
                value=self._convert_ast_expr(node.value, scope),
                slice=self._convert_ast_expr(node.slice, scope)
            )
        elif isinstance(node, ast.Tuple):
            # Handle tuple literals (a, b, c) or return (x, y)
            from .ir.expr_phase2 import ExprTuple
            return ExprTuple(
                elts=[self._convert_ast_expr(elt, scope) for elt in node.elts]
            )
        
        # Fallback: store as constant with the AST node type
        return ExprConstant(value=f"<{type(node).__name__}>")

    def _convert_ast_pattern(self, node: ast.pattern, scope: ConversionScope = None):
        """Convert AST match pattern to data model Pattern."""
        from .ir.stmt import PatternValue, PatternAs, PatternOr, PatternSequence
        
        if isinstance(node, ast.MatchValue):
            # Literal value pattern: case 0:, case "hello":
            return PatternValue(
                value=self._convert_ast_expr(node.value, scope)
            )
        elif isinstance(node, ast.MatchAs):
            # Wildcard pattern: case _:
            # Or capture pattern: case x:
            return PatternAs(
                pattern=self._convert_ast_pattern(node.pattern, scope) if node.pattern else None,
                name=node.name
            )
        elif isinstance(node, ast.MatchOr):
            # Or pattern: case 1 | 2:
            return PatternOr(
                patterns=[self._convert_ast_pattern(p, scope) for p in node.patterns]
            )
        elif isinstance(node, ast.MatchSequence):
            # Sequence pattern: case [x, y]:
            return PatternSequence(
                patterns=[self._convert_ast_pattern(p, scope) for p in node.patterns]
            )
        else:
            # Fallback for unsupported patterns - treat as wildcard
            return PatternAs(pattern=None, name=None)

    def _convert_binop(self, op : ast.operator) -> BinOp:
        """Convert AST binary operator to data model BinOp."""
        op_map = {
            ast.Add: BinOp.Add,
            ast.Sub: BinOp.Sub,
            ast.Mult: BinOp.Mult,
            ast.Div: BinOp.Div,
            ast.Mod: BinOp.Mod,
            ast.BitAnd: BinOp.BitAnd,
            ast.BitOr: BinOp.BitOr,
            ast.BitXor: BinOp.BitXor,
            ast.LShift: BinOp.LShift,
            ast.RShift: BinOp.RShift,
        }
        return op_map.get(type(op), BinOp.Add)
    
    def _convert_cmpop(self, op : ast.cmpop):
        """Convert AST comparison operator to data model CmpOp."""
        from .ir.expr import CmpOp
        op_map = {
            ast.Eq: CmpOp.Eq,
            ast.NotEq: CmpOp.NotEq,
            ast.Lt: CmpOp.Lt,
            ast.LtE: CmpOp.LtE,
            ast.Gt: CmpOp.Gt,
            ast.GtE: CmpOp.GtE,
            ast.Is: CmpOp.Is,
            ast.IsNot: CmpOp.IsNot,
            ast.In: CmpOp.In,
            ast.NotIn: CmpOp.NotIn,
        }
        return op_map.get(type(op), CmpOp.Eq)
    
    def _convert_boolop(self, op : ast.boolop):
        """Convert AST boolean operator to data model BoolOp."""
        from .ir.expr import BoolOp as DmBoolOp
        op_map = {
            ast.And: DmBoolOp.And,
            ast.Or: DmBoolOp.Or,
        }
        return op_map.get(type(op), DmBoolOp.And)
    
    def _convert_unaryop(self, op : ast.unaryop):
        """Convert AST unary operator to data model UnaryOp."""
        from .ir.expr import UnaryOp
        op_map = {
            ast.Invert: UnaryOp.Invert,
            ast.Not: UnaryOp.Not,
            ast.UAdd: UnaryOp.UAdd,
            ast.USub: UnaryOp.USub,
        }
        return op_map.get(type(op), UnaryOp.UAdd)

    def _convert_cmpop(self, op : ast.cmpop) -> 'CmpOp':
        """Convert AST comparison operator to data model CmpOp."""
        from .ir.expr import CmpOp
        op_map = {
            ast.Eq: CmpOp.Eq,
            ast.NotEq: CmpOp.NotEq,
            ast.Lt: CmpOp.Lt,
            ast.LtE: CmpOp.LtE,
            ast.Gt: CmpOp.Gt,
            ast.GtE: CmpOp.GtE,
            ast.Is: CmpOp.Is,
            ast.IsNot: CmpOp.IsNot,
            ast.In: CmpOp.In,
            ast.NotIn: CmpOp.NotIn,
        }
        return op_map.get(type(op), CmpOp.Eq)

    def _process_dataclass(self, t : Type) -> DataTypeStruct:
        """Process a dataclass into DataTypeStruct."""
        # Process fields and build field indices for scope
        fields = self._extract_fields(t)
        field_indices = {f.name: idx for idx, f in enumerate(fields)}
        
        # Extract methods (including @invariant decorated ones)
        functions = []
        for name, member in inspect.getmembers(t):
            if name.startswith('_'):
                continue
            if callable(member) and not isinstance(member, type):
                func = self._extract_function(t, name, member, field_indices)
                if func is not None:
                    functions.append(func)
        
        return DataTypeStruct(super=None, fields=fields, functions=functions)

    def _process_class(self, t : Type) -> DataTypeClass:
        """Process a generic class into DataTypeClass."""
        return DataTypeClass(super=None, fields=[], functions=[])
