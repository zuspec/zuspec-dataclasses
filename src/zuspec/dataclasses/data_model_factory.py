
from typing import Union, Iterator, Type, get_type_hints, Any, Optional, Protocol, get_origin, get_args, Annotated
import dataclasses as dc
import inspect
import ast
from .ir.context import Context
import enum as _enum_mod
from .ir.data_type import (
    DataType, DataTypeInt, DataTypeUptr, DataTypeStruct, DataTypeClass,
    DataTypeAction, DataTypeComponent, DataTypeExtern, DataTypeProtocol, DataTypeRef, DataTypeString,
    DataTypeLock, DataTypeEvent, DataTypeMemory, DataTypeArray, DataTypeChannel, DataTypeGetIF, DataTypePutIF,
    DataTypeTuple, DataTypeTupleReturn, DataTypeEnum, DataTypeClaimPool,
    Function, Process, ProcessKind
)
from .ir.fields import Field, FieldKind, Bind, FieldInOut
from .ir.stmt import (
    Stmt, Arguments, Arg,
    StmtFor, StmtWhile, StmtExpr, StmtAssign, StmtAnnAssign, StmtAugAssign, StmtPass, StmtReturn, StmtIf,
    StmtAssert, StmtAssume, StmtCover, StmtMatch, StmtMatchCase,
)
from .ir.expr import ExprCall, ExprAttribute, ExprConstant, ExprRef, ExprBin, BinOp, AugOp, ExprRefField, TypeExprRefSelf, ExprRefPy, ExprAwait, ExprRefParam, ExprRefLocal, ExprRefUnresolved, ExprCompare, ExprSubscript, ExprBool
from .types import TypeBase, Component, Extern, Lock, Memory, Struct

# Import Event at runtime to avoid circular dependency
def _get_event_type():
    from . import Event
    return Event
from .tlm import Channel, GetIF, PutIF
from .decorators import ExecProc, ExecSync, ExecComb, Input, Output


# ---------------------------------------------------------------------------
# Private sentinels used only during action-body conversion.
# These are returned by _convert_ast_expr in action-body mode and are ALWAYS
# consumed by the surrounding Attribute handler — they never appear in the
# final IR.
# ---------------------------------------------------------------------------
class _ExprActionSelf:
    """Sentinel: represents ``self`` inside an action body being inlined."""
    __slots__ = ()

class _ExprActionComp:
    """Sentinel: represents ``self.comp`` inside an action body being inlined."""
    __slots__ = ()


@dc.dataclass
class ConversionScope:
    """Scope context for AST to datamodel conversion"""
    component: DataTypeComponent = None  # Current component being processed
    field_indices: dict = dc.field(default_factory=dict)    # field_name -> index
    method_params: set = dc.field(default_factory=set)      # Parameter names in current method
    local_vars: set = dc.field(default_factory=set)         # Local variables in current scope
    # var_name -> (field_idx, idx_expr, mode) for `async with self.field.read/write(idx) as var:`
    regfile_bindings: dict = dc.field(default_factory=dict)

    # --- Action body inlining context ---
    # Set when converting an action body that is being inlined into a parent process.
    is_action_body: bool = False
    # Name of the result variable in the parent scope (e.g. "fn").
    action_result_var: str = ""
    # Non-comp field names of the action (e.g. {"pc_in", "pc_out", "insn32"}).
    action_field_names: set = dc.field(default_factory=set)
    # Prefix for action-body local variables to avoid naming conflicts (e.g. "fn_").
    action_local_prefix: str = ""
    # Component's field indices (for resolving self.comp.X in the action body).
    comp_field_indices: dict = dc.field(default_factory=dict)
    # var_name -> comp_field_idx mapping for ``async with self.comp.pool.lock() as var:``
    pool_claims: dict = dc.field(default_factory=dict)

    # Action class being inlined (for instance method lookup during constraint compilation)
    action_cls: type = None
    # True when converting @zdc.constraint methods as imperative stmts (treats == as =)
    is_constraint_mode: bool = False
    # Pragma map from scan_pragmas(): line_number -> {key: value}
    pragma_map: Optional[dict] = None
    # Comment map from scan_line_comments(): line_number -> comment_text
    comment_map: Optional[dict] = None
    # Leading comment for the current method (set by _extract_method_body)
    method_comment: Optional[str] = None


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
                    
                    # Check if field_type is a Tuple
                    origin = get_origin(field_type)
                    if origin is tuple:
                        # Return a tuple proxy that supports subscript access
                        args = get_args(field_type)
                        elem_type = args[0] if args else None
                        return _BindProxyTuple(new_expr, elem_type)
                    elif field_type is not None and hasattr(field_type, '__dataclass_fields__'):
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
                
                # Check if field_type is a Tuple
                origin = get_origin(field_type)
                if origin is tuple:
                    # Return a tuple proxy that supports subscript access
                    args = get_args(field_type)
                    elem_type = args[0] if args else None
                    return _BindProxyTuple(new_expr, elem_type)
                elif field_type is not None and hasattr(field_type, '__dataclass_fields__'):
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


class _BindProxyTuple:
    """Proxy for tuple field types that supports subscript access."""
    def __init__(self, base_expr: ExprRef, elem_type: type):
        object.__setattr__(self, '_base_expr', base_expr)
        object.__setattr__(self, '_elem_type', elem_type)
    
    def __getitem__(self, index):
        """Handle self.req[i] - return an ExprSubscript expression."""
        base_expr = object.__getattribute__(self, '_base_expr')
        elem_type = object.__getattribute__(self, '_elem_type')
        
        # Create subscript expression
        subscript_expr = ExprSubscript(
            value=base_expr,
            slice=ExprConstant(value=index)
        )
        
        # Return appropriate proxy based on element type
        if elem_type is not None:
            if hasattr(elem_type, '__dataclass_fields__'):
                # Element is a dataclass - return _BindProxy for nested access
                nested_indices = {}
                nested_types = {}
                idx = 0
                for fname, fval in elem_type.__dataclass_fields__.items():
                    if not fname.startswith('_'):
                        nested_indices[fname] = idx
                        try:
                            nested_hints = get_type_hints(elem_type)
                            nested_type = nested_hints.get(fname)
                            nested_types[fname] = (nested_hints, nested_type)
                        except Exception:
                            nested_types[fname] = ({}, None)
                        idx += 1
                return _BindProxy(nested_indices, nested_types, subscript_expr)
            else:
                # Protocol or other type - allow method references
                return _BindProxyMethod(subscript_expr, elem_type)
        
        return _ExprRefWrapper(subscript_expr)
    
    def __hash__(self):
        base_expr = object.__getattribute__(self, '_base_expr')
        return hash(id(base_expr))
    
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
        elif self._is_action(t):
            dm = self._process_action(t)
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
    
    def _is_struct(self, t : Type) -> bool:
        """Check if a type inherits from Struct (bundle)."""
        return (hasattr(t, '__mro__') and 
                Struct in t.__mro__ and 
                t is not Struct)

    def _get_scope_globals(self, scope: Optional['ConversionScope']) -> dict:
        """Return the module-level globals for the component class in *scope*.

        These are used to resolve action class names encountered in method bodies.
        """
        if scope is not None and scope.component is not None:
            # scope.component may be a DataTypeComponent (with .py_type)
            # or the raw Python class itself (during early processing)
            comp_ref = scope.component
            if isinstance(comp_ref, type):
                comp_py_type = comp_ref
            else:
                comp_py_type = getattr(comp_ref, 'py_type', None)
            if comp_py_type is not None:
                mod = inspect.getmodule(comp_py_type)
                if mod is not None:
                    return vars(mod)
        return {}

    def _is_action(self, t: Type) -> bool:
        """Return True if *t* is a zdc.Action[T] subclass."""
        from .types import Action
        for base in getattr(t, '__orig_bases__', ()):
            if getattr(base, '__origin__', None) is Action:
                return True
        return False

    def _get_action_comp_type(self, t: Type):
        """Return the component type T from ``Action[T]``, or None."""
        from .types import Action
        import typing
        for base in getattr(t, '__orig_bases__', ()):
            if getattr(base, '__origin__', None) is Action:
                args = getattr(base, '__args__', ())
                if not args:
                    return None
                arg = args[0]
                # Resolve ForwardRef (from ``Action['ClassName']`` string annotation)
                if isinstance(arg, typing.ForwardRef):
                    # Try to resolve against the module where the action class is defined
                    mod = inspect.getmodule(t)
                    if mod is not None:
                        resolved = getattr(mod, arg.__forward_arg__, None)
                        if resolved is not None:
                            return resolved
                    return None  # Can't resolve
                return arg
        return None

    def _process_action(self, t: Type) -> DataTypeAction:
        """Process a zdc.Action subclass into DataTypeAction.

        Collects the action's data fields and stores the body() stmts for
        later inlining by :meth:`_inline_action_call`.
        """
        comp_type = self._get_action_comp_type(t)
        comp_type_name = self._get_type_name(comp_type) if comp_type else None

        # Ensure the component type is also processed.
        if comp_type is not None:
            self._add_pending(comp_type)

        # Collect action fields via dataclass introspection.
        # Action[T] defines `comp: T` as field 0; we include it so field indices
        # match the Python class layout, but mark its C-struct presence separately.
        fields = self._extract_fields(t)

        # Collect @staticmethod members and convert them to Function IR.
        static_methods = self._collect_static_methods(t)

        # The body() stmts will be filled in lazily when the action is first
        # inlined (comp's field_indices are needed at that point).
        return DataTypeAction(
            super=None,
            fields=fields,
            comp_type_name=comp_type_name,
            body_stmts=[],   # populated on first inline
            static_methods=static_methods,
        )

    def _collect_static_methods(self, t: Type) -> list:
        """Return a list of ``Function`` IR objects for each ``@staticmethod`` on *t*.

        Only converts methods whose source can be retrieved and parsed.  Skips
        dunder names and any method that fails to parse.
        """
        funcs = []
        for name, member in t.__dict__.items():
            if name.startswith('__'):  # skip dunder only; single-underscore helpers like _sext are valid
                continue
            if not isinstance(member, staticmethod):
                continue
            fn = member.__func__
            func_ir = self._convert_static_method(name, fn)
            if func_ir is not None:
                funcs.append(func_ir)
        return funcs

    def _convert_static_method(self, name: str, fn) -> Optional[Function]:
        """Convert a single static method function to a ``Function`` IR node."""
        import textwrap
        try:
            src = inspect.getsource(fn)
            src = textwrap.dedent(src)
            tree = ast.parse(src)
        except Exception:
            return None

        func_nodes = [n for n in ast.walk(tree)
                      if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        if not func_nodes:
            return None
        func_def = func_nodes[0]

        # Build a "plain function" scope: parameters are method_params, no component.
        param_names = {arg.arg for arg in func_def.args.args
                       if arg.arg not in ('self', 'cls')}
        scope = ConversionScope(
            component=None,
            field_indices={},
            method_params=param_names,
            local_vars=set(),
        )

        body_stmts = self._convert_ast_body(func_def.body, scope)

        args = Arguments(
            args=[Arg(arg=p.arg) for p in func_def.args.args
                  if p.arg not in ('self', 'cls')]
        )
        return Function(name=name, args=args, body=body_stmts)


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
        
        # Build metadata dict for function markers
        func_metadata = {}
        if hasattr(member, '_is_constraint') and member._is_constraint:
            func_metadata['_is_constraint'] = True
            if hasattr(member, '_constraint_kind'):
                func_metadata['_constraint_kind'] = member._constraint_kind
        
        # Create conversion scope; component=cls so action class names can be
        # resolved from the module globals via _get_scope_globals.
        scope = ConversionScope(
            component=cls,
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
            is_invariant=is_invariant,
            metadata=func_metadata
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

        # Scan for @property getters — each becomes a wire (continuous assignment).
        wire_processes = []
        for name, member in t.__dict__.items():
            if isinstance(member, property) and member.fget is not None:
                func = self._extract_wire(t, name, member.fget, field_indices)
                if func is not None:
                    wire_processes.append(func)

        # Extract bind map from __bind__ method
        bind_map = self._extract_bind_map(t)
        
        dm = DataTypeComponent(
            super=super_dt,
            fields=fields,
            functions=functions + processes,
            bind_map=bind_map,
            sync_processes=sync_processes,
            comb_processes=comb_processes,
            wire_processes=wire_processes,
        )
        return dm

    def _extract_fields(self, t : Type) -> list:
        """Extract fields from a dataclass type."""
        from .pragma import scan_pragmas as _scan_pragmas
        fields = []
        
        if not dc.is_dataclass(t):
            return fields

        # Build a map from field name → pragma dict by scanning source once
        field_pragmas: dict = {}
        try:
            import textwrap
            source_lines, start_lineno = inspect.getsourcelines(t)
            source = textwrap.dedent(''.join(source_lines))
            pragmas_by_line = _scan_pragmas(source)
            if pragmas_by_line:
                # Walk AST to correlate AnnAssign field names with their line's pragmas
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and node.name == t.__name__:
                        for stmt in node.body:
                            if (isinstance(stmt, ast.AnnAssign)
                                    and isinstance(stmt.target, ast.Name)
                                    and stmt.lineno in pragmas_by_line):
                                field_pragmas[stmt.target.id] = pragmas_by_line[stmt.lineno]
        except (OSError, TypeError):
            pass
        
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
            
            # Check if field_type is actually a dc.Field (from rand() or randc() decorator)
            # If so, extract metadata from it
            field_metadata = {}
            if isinstance(field_type, dc.Field):
                # rand() or randc() returns a Field with metadata
                if field_type.metadata:
                    field_metadata = dict(field_type.metadata)
                # Get the actual type from the field's default value or annotation
                # Check if width is specified in metadata
                if 'width' in field_metadata:
                    # Create an int type with the specified width
                    from .types import U
                    from typing import Annotated
                    width = field_metadata['width']
                    field_type = Annotated[int, U(width)]
                else:
                    # Default to int32 for random variables without explicit width
                    from .types import U
                    from typing import Annotated
                    field_type = Annotated[int, U(32)]
            elif f.metadata:
                field_metadata = dict(f.metadata)
                
                # If this is a rand/randc field with int type and no width, default to int32
                if field_type == int and field_metadata.get('rand', False):
                    if 'width' not in field_metadata:
                        from .types import U
                        from typing import Annotated
                        field_type = Annotated[int, U(32)]
            
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
                import collections.abc
                field_kind = f.metadata.get('kind')
                if field_kind in ('port', 'export'):
                    is_export = field_kind == 'export'
                    ann_origin = get_origin(field_type)
                    if ann_origin is collections.abc.Callable:
                        kind = FieldKind.CallableExport if is_export else FieldKind.CallablePort
                    elif getattr(field_type, '_is_protocol', False):
                        kind = FieldKind.ProtocolExport if is_export else FieldKind.ProtocolPort
                    elif isinstance(field_type, type):
                        # Bundle subclass (existing behaviour)
                        kind = FieldKind.Export if is_export else FieldKind.Port
                    else:
                        kind = FieldKind.Export if is_export else FieldKind.Port
            
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
                    if hasattr(ef_t, '__mro__') and (self._is_protocol(ef_t) or self._is_extern(ef_t) or self._is_component(ef_t) or self._is_struct(ef_t)):
                        self._add_pending(ef_t)

                datatype = DataTypeTuple(element_type=elem_dt, size=size, elem_factory=elem_factory_dt)

                # Add referenced element type to pending
                if elem_py_t is not None and hasattr(elem_py_t, '__mro__'):
                    if self._is_protocol(elem_py_t) or self._is_extern(elem_py_t) or self._is_component(elem_py_t) or self._is_struct(elem_py_t):
                        self._add_pending(elem_py_t)
            elif origin is list:
                # Handle List[T] for array fields
                args = get_args(field_type)
                elem_py_t = args[0] if args else None
                
                # For array rand fields without explicit width, default element type to int32
                if elem_py_t == int and field_metadata and field_metadata.get('rand', False):
                    if 'width' not in field_metadata:
                        # Default to int32 for random array elements
                        from .types import U
                        from typing import Annotated
                        elem_py_t = Annotated[int, U(32)]
                
                elem_dt = self._resolve_field_type(elem_py_t)
                
                # For now, just resolve as the element type
                # Array handling is done at the solver level via size metadata
                datatype = elem_dt
                
                # Handle variable-size arrays (Phase 3)
                # If max_size is specified, this is a variable-size array
                if field_metadata and field_metadata.get('rand', False):
                    has_size = 'size' in field_metadata and field_metadata['size'] is not None
                    has_max_size = 'max_size' in field_metadata and field_metadata['max_size'] is not None
                    
                    if not has_size and not has_max_size:
                        # No size or max_size - default to variable-size with default max
                        # This allows: buffer: List[int] = rand(domain=(0, 255))
                        field_metadata['max_size'] = 32  # Default maximum size
                        field_metadata['is_variable_size'] = True
                    elif has_max_size:
                        # Explicit max_size - variable-size array
                        field_metadata['is_variable_size'] = True
                    # If has_size, it's a fixed-size array (existing behavior)
                
                # Add referenced element type to pending
                if elem_py_t is not None and hasattr(elem_py_t, '__mro__'):
                    if self._is_protocol(elem_py_t) or self._is_extern(elem_py_t) or self._is_component(elem_py_t) or self._is_struct(elem_py_t):
                        self._add_pending(elem_py_t)
            else:
                datatype = self._resolve_field_type(field_type)

                # For Memory fields, extract size from metadata
                if isinstance(datatype, DataTypeMemory) and f.metadata and 'size' in f.metadata:
                    datatype.size = f.metadata['size']

                # For Array fields, extract depth from metadata
                if isinstance(datatype, DataTypeArray) and f.metadata and 'depth' in f.metadata:
                    datatype.size = f.metadata['depth']

                # Add referenced types to pending
                if field_type is not None and hasattr(field_type, '__mro__'):
                    if self._is_protocol(field_type) or self._is_extern(field_type) or self._is_component(field_type) or self._is_struct(field_type):
                        self._add_pending(field_type)
            
            # Check if this is a const field
            is_const = False
            if field_metadata and field_metadata.get('kind') == 'const':
                is_const = True
            
            # Extract rand/randc metadata for constraint solver
            rand_kind = None
            domain = None
            array_size = None  # Extract array size for solver
            max_array_size = None  # Extract max size for variable-size arrays
            is_variable_size = False  # Flag for variable-size arrays
            
            if field_metadata:
                # Check for rand/randc markers
                if field_metadata.get('rand', False):
                    rand_kind = field_metadata.get('rand_kind', 'rand')
                
                # Extract domain for random variables
                if 'domain' in field_metadata:
                    domain = field_metadata['domain']
                
                # Extract array size (fixed-size)
                if 'size' in field_metadata:
                    array_size = field_metadata['size']
                
                # Extract max_size (variable-size)
                if 'max_size' in field_metadata:
                    max_array_size = field_metadata['max_size']
                
                # Extract variable-size flag
                if 'is_variable_size' in field_metadata:
                    is_variable_size = field_metadata['is_variable_size']
            
            # Extract width expression if present
            width_expr = None
            if field_metadata and 'width' in field_metadata:
                width_val = field_metadata['width']
                if callable(width_val):
                    from .ir.expr import ExprLambda
                    width_expr = ExprLambda(callable=width_val)
            
            # Extract kwargs expression if present
            kwargs_expr = None
            if field_metadata and 'kwargs' in field_metadata:
                kwargs_val = field_metadata['kwargs']
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
                    rand_kind=rand_kind,
                    domain=domain,
                    size=array_size,
                    max_size=max_array_size,
                    is_variable_size=is_variable_size,
                    loc=field_loc,
                    pragmas=field_pragmas.get(f.name, {}),
                )
            else:
                field_dm = Field(
                    name=f.name,
                    datatype=datatype,
                    kind=kind,
                    width_expr=width_expr,
                    kwargs_expr=kwargs_expr,
                    is_const=is_const,
                    rand_kind=rand_kind,
                    domain=domain,
                    size=array_size,
                    max_size=max_array_size,
                    is_variable_size=is_variable_size,
                    loc=field_loc,
                    pragmas=field_pragmas.get(f.name, {}),
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
            
            # Check if this is an annotated int (or bv subclass) with width information
            if (base_type is int or (inspect.isclass(base_type) and issubclass(base_type, int))) and metadata:
                from .types import U, S, Uptr
                for m in metadata:
                    if isinstance(m, Uptr):
                        # Platform-sized pointer type
                        return DataTypeUptr()
                    if isinstance(m, (U, S)):
                        return DataTypeInt(bits=m.width, signed=isinstance(m, S))
            
            # Fall back to resolving the base type
            return self._resolve_field_type(base_type)

        # bv[N] subclasses: proper subclasses of bv with class-level _width
        from .types import bv as _bv
        if inspect.isclass(field_type) and issubclass(field_type, _bv):
            width = getattr(field_type, '_width', 0)
            if width > 0:
                return DataTypeInt(bits=width, signed=False)
        
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
            from .types import Array as _Array
            if origin is _Array:
                # Size comes from field metadata (array(depth=N)); default -1 if unknown here
                return DataTypeArray(element_type=element_type, size=-1)
            if origin is Channel:
                return DataTypeChannel(element_type=element_type)
            if origin is GetIF:
                return DataTypeGetIF(element_type=element_type)
            if origin is PutIF:
                return DataTypePutIF(element_type=element_type)
            # ClaimPool[ElemType] → DataTypeClaimPool carrying the element type name
            origin_name = getattr(origin, '__name__', '') or getattr(origin, '_name', '')
            if origin_name in ('ClaimPool',):
                elem_py = args[0] if args else None
                elem_name = self._get_type_name(elem_py) if (elem_py and hasattr(elem_py, '__name__')) else ''
                if elem_py and hasattr(elem_py, '__mro__') and self._is_component(elem_py):
                    self._add_pending(elem_py)
                return DataTypeClaimPool(elem_type_name=elem_name)
        
        # Handle Python IntEnum subclasses → DataTypeEnum
        if inspect.isclass(field_type) and issubclass(field_type, _enum_mod.IntEnum):
            items = {member.name: member.value for member in field_type}
            return DataTypeEnum(items=items, py_type=field_type)

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
        """Extract a Process from an @process decorated method.

        If the method has parameters beyond ``self``, it is promoted to a
        ``Function`` with ``is_async=True`` so that the SW backend can emit a
        callable entry point with the correct C signature.  Pure processes
        with no parameters are still emitted as ``Process`` nodes.
        """
        method = exec_proc.method

        # Collect parameters (skip 'self')
        try:
            hints = get_type_hints(method)
        except Exception:
            hints = {}
        sig = inspect.signature(method)
        param_names: set = set()
        args_list = []
        for pname, _p in sig.parameters.items():
            if pname == 'self':
                continue
            annotation = hints.get(pname)
            args_list.append(Arg(arg=pname, annotation=self._type_to_expr(annotation)))
            param_names.add(pname)

        return_type = hints.get('return')
        returns = self._annotation_to_datatype(return_type) if return_type else None

        scope = ConversionScope(
            component=cls,
            field_indices=field_indices if field_indices else {},
            method_params=param_names,
        )

        body = self._extract_method_body(cls, method.__name__, scope)

        if args_list:
            # Promote to Function so the SW backend can emit a callable C entry.
            return Function(
                name=method.__name__,
                args=Arguments(args=args_list),
                body=body,
                returns=returns,
                is_async=True,
                metadata={"is_process": True},
            )
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
            comment=scope.method_comment,
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
            comment=scope.method_comment,
            metadata={
                "kind": "comb",
                "sensitivity": sensitivity_list,
                "method": exec_comb.method
            }
        )
        
        return func

    def _extract_wire(self, cls: Type, name: str, fget, field_indices: dict) -> Optional[Function]:
        """Convert a @property getter to a wire (continuous-assignment) Function.

        The getter body is parsed exactly like a @comb method.  A missing or
        unresolvable return-type annotation generates a warning but does not
        prevent extraction — the emitter can infer width from the expression.
        """
        scope = ConversionScope(
            component=None,
            field_indices=field_indices,
            method_params=set(),
            local_vars=set()
        )

        try:
            body = self._extract_method_body(cls, name, scope)
        except Exception as e:
            import warnings
            warnings.warn(
                f"@property '{cls.__name__}.{name}' body could not be extracted "
                f"and will not appear as a wire in the IR: {e}"
            )
            return None

        # Return type determines wire width — warn if absent.
        return_type = None
        try:
            hints = get_type_hints(fget, include_extras=True)
            return_type = self._resolve_field_type(hints.get('return')) if 'return' in hints else None
        except Exception:
            pass

        if return_type is None:
            import warnings
            warnings.warn(
                f"@property '{cls.__name__}.{name}' has no return type annotation; "
                "wire width will be inferred by the emitter."
            )

        sensitivity_list = self._extract_sensitivity_list(body)

        return Function(
            name=name,
            body=body,
            returns=return_type,
            process_kind=ProcessKind.WIRE,
            sensitivity_list=sensitivity_list,
            metadata={
                "kind": "wire",
                "sensitivity": sensitivity_list,
            }
        )

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

            # Build pragma map once for this class source and attach to scope.
            if scope is not None and scope.pragma_map is None:
                from .pragma import scan_pragmas as _scan_pragmas, scan_line_comments as _scan_line_comments
                scope.pragma_map = _scan_pragmas(source)
                scope.comment_map = _scan_line_comments(source)
            
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
                            # Collect leading comment for this method
                            if scope is not None:
                                scope.method_comment = self._collect_method_comment(item, scope.comment_map)
                            return self._convert_ast_body(item.body, scope)
        except SyntaxError as e:
            raise RuntimeError(
                f"Failed to parse source code for class '{cls.__name__}' method '{method_name}': {e}"
            ) from e
        
        return []

    def _collect_method_comment(self, func_node, comment_map: Optional[dict]) -> Optional[str]:
        """Return the comment text associated with a method definition.

        Combines two sources in order (earlier first):
          1. Leading ``#`` block — consecutive comment lines sitting immediately
             above the first decorator (or the ``def`` line if undecorated),
             collected from *comment_map*.
          2. Docstring — the ``\"\"\"...\"\"\"`` string literal that is the first
             statement in the function body, if present.

        Returns ``None`` when neither source yields any text.
        """
        parts = []

        # 1. Leading # block (above the decorator or def)
        if comment_map:
            if func_node.decorator_list:
                start = min(d.lineno for d in func_node.decorator_list)
            else:
                start = func_node.lineno
            comment_lines = []
            lineno = start - 1
            while lineno > 0 and lineno in comment_map:
                comment_lines.append(comment_map[lineno])
                lineno -= 1
            if comment_lines:
                parts.append('\n'.join(reversed(comment_lines)))

        # 2. Docstring
        docstring = ast.get_docstring(func_node)
        if docstring:
            parts.append(docstring)

        return '\n'.join(parts) if parts else None

    def _convert_ast_body(self, body : list, scope: ConversionScope = None) -> list:
        """Convert AST statement list to data model statements."""
        stmts = []
        for node in body:
            stmt = self._convert_ast_stmt(node, scope)
            if stmt is None:
                continue
            if isinstance(stmt, list):
                stmts.extend(stmt)
            else:
                stmts.append(stmt)
        return stmts

    def _convert_async_with(self, node, scope: ConversionScope = None):
        """Lower `async with self.field.read/write(idx) as var:` to flat IR assignments.

        Recognises the IndexedRegFile accessor pattern and inlines the body
        by substituting `var.set(value)` → StmtAssign and `var.get()` → ExprSubscript.
        Also recognises ``async with self.comp.pool.lock() as claim:`` and tracks
        `claim` as a pool-claim variable so that ``claim.t.method(args)`` is lowered
        to ``self->pool.method(self->pool.method_ud, args)`` via ExprRefField.
        Returns a single Stmt, a list of Stmts, or None.
        """
        # Build a child scope carrying the new bindings; preserve action-body context
        child_scope = ConversionScope(
            component=scope.component if scope else None,
            field_indices=scope.field_indices.copy() if scope else {},
            method_params=scope.method_params.copy() if scope else set(),
            local_vars=scope.local_vars.copy() if scope else set(),
            regfile_bindings=scope.regfile_bindings.copy() if scope else {},
            is_action_body=scope.is_action_body if scope else False,
            action_result_var=scope.action_result_var if scope else "",
            action_field_names=scope.action_field_names if scope else set(),
            action_local_prefix=scope.action_local_prefix if scope else "",
            comp_field_indices=scope.comp_field_indices if scope else {},
            pool_claims=scope.pool_claims.copy() if scope else {},
            action_cls=scope.action_cls if scope else None,
            is_constraint_mode=scope.is_constraint_mode if scope else False,
        )

        for item in node.items:
            binding = self._parse_regfile_with_item(item, scope)
            if binding is not None:
                var_name, field_idx, idx_expr, _mode = binding
                child_scope.regfile_bindings[var_name] = (field_idx, idx_expr, _mode)
                continue

            # Direct write: ``async with self.comp.field.write(idx, val): pass``
            # (no `as var` binding — val is passed inline as second arg)
            direct_write = self._parse_direct_regfile_write_item(item, scope)
            if direct_write is not None:
                # Emit the write immediately before the body statements
                return direct_write

            # ClaimPool.lock() as claim → pool_claims[claim_var] = comp_field_idx
            pool_binding = self._parse_claim_pool_item(item, scope)
            if pool_binding is not None:
                claim_var, pool_field_idx = pool_binding
                child_scope.pool_claims[claim_var] = pool_field_idx
                child_scope.local_vars.add(claim_var)

        body_stmts = self._convert_ast_body(node.body, child_scope)

        # Python has function scope, not block scope: variables assigned inside
        # an `async with` body are visible in the enclosing scope after the block.
        if scope is not None:
            scope.local_vars.update(child_scope.local_vars)

        if len(body_stmts) == 1:
            return body_stmts[0]
        elif len(body_stmts) > 1:
            return body_stmts
        return None

    def _parse_claim_pool_item(self, item, scope: ConversionScope):
        """Detect ``self.comp.pool_field.lock() as var`` items.

        Returns ``(var_name, pool_field_idx)`` or ``None``.
        The pool_field_idx is an index into ``scope.comp_field_indices``.
        """
        ctx = item.context_expr
        var = item.optional_vars

        if not (isinstance(ctx, ast.Call) and isinstance(var, ast.Name)):
            return None
        func = ctx.func
        if not (isinstance(func, ast.Attribute) and func.attr == 'lock'):
            return None

        # Callee must be self.comp.pool_field
        callee = func.value
        if not (isinstance(callee, ast.Attribute)
                and isinstance(callee.value, ast.Attribute)
                and isinstance(callee.value.value, ast.Name)
                and callee.value.value.id == 'self'
                and callee.value.attr == 'comp'):
            return None

        pool_field_name = callee.attr
        if scope is None or pool_field_name not in scope.comp_field_indices:
            return None

        pool_field_idx = scope.comp_field_indices[pool_field_name]
        return (var.id, pool_field_idx)

    def _parse_regfile_with_item(self, item, scope: ConversionScope = None):
        """Parse one `async with` item for the IndexedRegFile pattern.

        Matches: ``self.field.read(idx) as var`` or ``self.field.write(idx) as var``
        Returns ``(var_name, field_idx, idx_expr, mode)`` or ``None``.
        """
        ctx = item.context_expr
        var = item.optional_vars

        if not (isinstance(ctx, ast.Call) and isinstance(var, ast.Name)):
            return None

        func = ctx.func
        if not isinstance(func, ast.Attribute):
            return None

        mode = func.attr
        if mode not in ('read', 'write'):
            return None

        field_expr = func.value
        if not (isinstance(field_expr, ast.Attribute) and
                isinstance(field_expr.value, ast.Name) and
                field_expr.value.id == 'self'):
            return None

        field_name = field_expr.attr
        if scope is None or field_name not in scope.field_indices:
            return None

        field_idx = scope.field_indices[field_name]

        if len(ctx.args) != 1:
            return None

        idx_expr = self._convert_ast_expr(ctx.args[0], scope)
        return (var.id, field_idx, idx_expr, mode)

    def _parse_direct_regfile_write_item(self, item, scope: ConversionScope):
        """Detect ``async with self.comp.field.write(idx, val): pass`` (no as-binding).

        This is the action-body writeback pattern where both the index and value are
        passed directly to write().  Returns a StmtAssign or None.
        Handles both ``self.field.write(idx, val)`` (component context) and
        ``self.comp.field.write(idx, val)`` (action-body context).
        """
        ctx = item.context_expr
        var = item.optional_vars
        # Must be a plain Call with no as-binding
        if not isinstance(ctx, ast.Call):
            return None
        if var is not None:
            return None  # has a binding → handled by _parse_regfile_with_item

        func = ctx.func
        if not (isinstance(func, ast.Attribute) and func.attr == 'write'):
            return None

        # Must have exactly 2 args: index and value
        if len(ctx.args) != 2:
            return None

        # Resolve the field.  Accept both:
        #   self.field.write(idx, val)          (component method scope)
        #   self.comp.field.write(idx, val)     (action body scope)
        field_expr = func.value
        field_idx = None
        if (isinstance(field_expr, ast.Attribute) and
                isinstance(field_expr.value, ast.Name) and
                field_expr.value.id == 'self' and
                scope is not None and
                field_expr.attr in scope.field_indices):
            # self.field.write(...)
            field_idx = scope.field_indices[field_expr.attr]
            comp_ref = TypeExprRefSelf()
        elif (isinstance(field_expr, ast.Attribute) and
                isinstance(field_expr.value, ast.Attribute) and
                isinstance(field_expr.value.value, ast.Name) and
                field_expr.value.value.id == 'self' and
                field_expr.value.attr == 'comp' and
                scope is not None and
                field_expr.attr in scope.comp_field_indices):
            # self.comp.field.write(...)  (action body)
            field_idx = scope.comp_field_indices[field_expr.attr]
            comp_ref = TypeExprRefSelf()
        else:
            return None

        idx_ir = self._convert_ast_expr(ctx.args[0], scope)
        val_ir = self._convert_ast_expr(ctx.args[1], scope)

        return StmtAssign(
            targets=[ExprSubscript(
                value=ExprRefField(base=comp_ref, index=field_idx),
                slice=idx_ir,
            )],
            value=val_ir,
        )

    # ------------------------------------------------------------------
    # Action call inlining
    # ------------------------------------------------------------------

    def _try_lower_regfile_read_all(self, tuple_target: ast.Tuple, rhs_node, scope: ConversionScope):
        """Try to lower ``a, b = await self.comp.regfile.read_all(i1, i2)``
        to individual get-calls ``a = {Comp}_{field}_get(comp, i1)`` etc.

        Returns a list of IR stmts on success, or None if the pattern doesn't match.
        """
        # Strip await if present
        call_node = rhs_node
        if isinstance(rhs_node, ast.Await):
            call_node = rhs_node.value

        if not isinstance(call_node, ast.Call):
            return None
        func_node = call_node.func
        if not (isinstance(func_node, ast.Attribute) and func_node.attr == 'read_all'):
            return None

        # The callee must be self.comp.<field>
        callee_obj = func_node.value
        if not (isinstance(callee_obj, ast.Attribute)
                and isinstance(callee_obj.value, ast.Attribute)
                and isinstance(callee_obj.value.value, ast.Name)
                and callee_obj.value.value.id == 'self'
                and callee_obj.value.attr == 'comp'):
            return None

        field_name = callee_obj.attr
        comp_name = self._get_type_name(scope.component) if (scope and scope.component) else None
        if comp_name is None:
            return None

        # Arity must match number of targets
        arity = len(tuple_target.elts)
        if len(call_node.args) != arity:
            return None

        stmts = []
        getter_name = f"{comp_name}_{field_name}_get"
        for i, (elt, arg_node) in enumerate(zip(tuple_target.elts, call_node.args)):
            if not isinstance(elt, ast.Name):
                return None
            var_name = elt.id
            if scope and scope.is_action_body and scope.action_local_prefix:
                var_name = scope.action_local_prefix + var_name
            if scope is not None:
                scope.local_vars.add(var_name)
            idx_expr = self._convert_ast_expr(arg_node, scope)
            stmts.append(StmtAssign(
                targets=[ExprRefLocal(name=var_name)],
                value=ExprCall(
                    func=ExprRefUnresolved(name=getter_name),
                    args=[TypeExprRefSelf(), idx_expr],
                ),
            ))
        return stmts

    def _parse_action_call(self, node: ast.AST):
        """Detect ``await ActionCls(kwargs)(comp=self)`` and return ``(action_ast_name, inner_call, outer_call)`` or None.

        The pattern in the AST is:
          ast.Await(
            ast.Call(                          # outer: invocation  (comp=self)
              func=ast.Call(                   # inner: constructor (pc_in=self.pc, ...)
                func=ast.Name("ActionCls"),
                keywords=[...]
              ),
              keywords=[ast.keyword(arg="comp", ...)]
            )
          )
        """
        # Unwrap a bare Await at the top level
        if isinstance(node, ast.Await):
            inner = node.value
        else:
            inner = node

        if not isinstance(inner, ast.Call):
            return None

        outer_call = inner
        inner_call = outer_call.func

        if not isinstance(inner_call, ast.Call):
            return None

        func_node = inner_call.func
        if isinstance(func_node, ast.Name):
            action_name = func_node.id
        else:
            return None  # must be a bare name

        return (action_name, inner_call, outer_call)

    def _inline_action_call(
        self,
        result_var: Optional[str],
        action_name: str,
        inner_call: ast.Call,
        outer_call: ast.Call,
        scope: ConversionScope,
        py_globals: dict,
    ) -> Optional[list]:
        """Inline an action call, returning a list of IR stmts.

        Returns a list of IR stmts that replace the original ``await`` stmt:
          1. A typed declaration for *result_var* (if given) so liveness
             analysis places it in the coroutine frame.
          2. Keyword-argument initialisation stmts (``result_var.kwarg = expr``).
          3. The action body stmts (converted with an action-body scope).

        Returns ``None`` if the action class cannot be resolved.
        """
        # Resolve the action Python class
        action_cls = py_globals.get(action_name)
        if action_cls is None:
            return None
        if not self._is_action(action_cls):
            return None

        action_type_name = self._get_type_name(action_cls)

        # Ensure the action type is processed and in type_m
        if action_type_name not in self._context.type_m:
            self._process_type(action_cls)

        action_dt = self._context.type_m.get(action_type_name)
        if not isinstance(action_dt, DataTypeAction):
            return None

        # Field indices of the action (includes 'comp' at index 0)
        action_field_indices = {f.name: idx for idx, f in enumerate(action_dt.fields)}
        # Data field names (everything except 'comp')
        action_data_field_names = {f.name for f in action_dt.fields if f.name != 'comp'}

        # The variable name used in the parent scope (may be None for void calls)
        rv = result_var or "_action_result"
        prefix = rv + "_"  # prefix for action-body locals to avoid naming conflicts

        result_stmts = []

        # 1. Always declare the action var so liveness analysis puts it in locals_struct.
        scope.local_vars.add(rv)
        result_stmts.append(StmtAnnAssign(
            target=ExprRefLocal(name=rv),
            annotation=ExprRefUnresolved(name=action_type_name),
            value=None,
            ir_type=action_dt,
        ))

        # 2. Init stmts from inner_call keywords (e.g. pc_in=self.pc).
        for kw in inner_call.keywords:
            if kw.arg is None or kw.arg == 'comp':
                continue
            if kw.arg not in action_data_field_names:
                continue
            val_expr = self._convert_ast_expr(kw.value, scope)
            target = ExprAttribute(value=ExprRefLocal(name=rv), attr=kw.arg)
            result_stmts.append(StmtAssign(
                targets=[target],
                value=val_expr,
            ))

        # 3. Convert action body() with action-body scope.
        body_stmts = self._convert_action_body(
            action_cls=action_cls,
            result_var=rv,
            action_field_names=action_data_field_names,
            local_prefix=prefix,
            comp_field_indices=scope.field_indices,
            outer_scope=scope,
        )
        result_stmts.extend(body_stmts)

        return result_stmts

    def _convert_action_body(
        self,
        action_cls: Type,
        result_var: str,
        action_field_names: set,
        local_prefix: str,
        comp_field_indices: dict,
        outer_scope: ConversionScope,
    ) -> list:
        """Convert action_cls.body() to IR stmts for inlining into the parent coroutine.

        ``self`` in the action body is translated:
        - ``self.X`` where X is an action field  → ``ExprAttribute(ExprRefLocal(result_var), X)``
        - ``self.comp``                           → component self (TypeExprRefSelf / sentinel)
        - ``self.comp.X``                         → ``ExprRefField(TypeExprRefSelf(), idx_of_X)``
        """
        # Only use a body if the class itself defines one (not just inherits the Action stub).
        body_method = action_cls.__dict__.get('body', None)
        if body_method is None:
            # No explicit body: try compiling @zdc.constraint methods as imperative logic
            return self._compile_constraint_methods_as_body(
                action_cls, result_var, action_field_names, local_prefix,
                comp_field_indices, outer_scope
            )

        try:
            import textwrap
            src = inspect.getsource(body_method)
            src = textwrap.dedent(src)
            tree = ast.parse(src)
        except Exception:
            return []

        # Build action-body scope
        action_scope = ConversionScope(
            component=outer_scope.component,
            field_indices={},            # action fields accessed via sentinels, not field_indices
            method_params=set(),
            local_vars=set(),
            regfile_bindings={},
            is_action_body=True,
            action_result_var=result_var,
            action_field_names=action_field_names,
            action_local_prefix=local_prefix,
            comp_field_indices=comp_field_indices,
            action_cls=action_cls,
        )

        # Walk the function def body
        func_nodes = [n for n in ast.walk(tree) if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef))]
        if not func_nodes:
            return []

        func_def = func_nodes[0]
        return self._convert_ast_body(func_def.body, action_scope)

    def _compile_constraint_methods_as_body(
        self,
        action_cls: type,
        result_var: str,
        action_field_names: set,
        local_prefix: str,
        comp_field_indices: dict,
        outer_scope: 'ConversionScope',
    ) -> list:
        """Compile @zdc.constraint methods as an imperative body for SW execution.

        Each ``self.field == value`` in a constraint method is lowered to an
        assignment ``self.field = value``.  The constraint guard (``if cond:``)
        becomes a C ``if`` statement.
        """
        import textwrap

        action_scope = ConversionScope(
            component=outer_scope.component,
            field_indices={},
            method_params=set(),
            local_vars=set(),
            regfile_bindings={},
            is_action_body=True,
            action_result_var=result_var,
            action_field_names=action_field_names,
            action_local_prefix=local_prefix,
            comp_field_indices=comp_field_indices,
            action_cls=action_cls,
            is_constraint_mode=True,
        )

        stmts = []
        for name, member in inspect.getmembers(action_cls):
            if name.startswith('__'):
                continue
            if not (hasattr(member, '_is_constraint') and member._is_constraint):
                continue
            try:
                src = textwrap.dedent(inspect.getsource(member))
                tree = ast.parse(src)
            except Exception:
                continue
            func_nodes = [n for n in ast.walk(tree)
                          if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            if not func_nodes:
                continue
            func_def = func_nodes[0]
            stmts.extend(self._convert_ast_body(func_def.body, action_scope))
        return stmts

    def _try_inline_instance_method_as_expr(self, method, parent_scope: 'ConversionScope'):
        """Inline a simple single-return instance method as an IR expression.

        Returns the converted IR expression, or None if the method is too complex
        (e.g. multiple return statements or no return statement).
        """
        import textwrap
        try:
            src = textwrap.dedent(inspect.getsource(method))
            tree = ast.parse(src)
        except Exception:
            return None
        func_nodes = [n for n in ast.walk(tree)
                      if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        if not func_nodes:
            return None
        func_def = func_nodes[0]
        body = func_def.body
        if len(body) == 1 and isinstance(body[0], ast.Return) and body[0].value is not None:
            return self._convert_ast_expr(body[0].value, parent_scope)
        return None

    def _inline_method_with_return_assign(
        self,
        method,
        target_expr,
        parent_scope: 'ConversionScope',
    ) -> Optional[list]:
        """Inline a method body replacing every ``return X`` with ``target = X``.

        Used to compile ``self.field == self._complex_method()`` constraint
        expressions where the method has a match/if-else body.  Returns a list
        of IR stmts, or None on failure.
        """
        import textwrap
        try:
            src = textwrap.dedent(inspect.getsource(method))
            tree = ast.parse(src)
        except Exception:
            return None
        func_nodes = [n for n in ast.walk(tree)
                      if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        if not func_nodes:
            return None
        func_def = func_nodes[0]
        return self._convert_body_return_to_assign(func_def.body, target_expr, parent_scope)

    def _convert_body_return_to_assign(
        self,
        body_nodes: list,
        target_expr,
        scope: 'ConversionScope',
    ) -> list:
        """Convert a list of AST nodes, replacing ``return X`` with ``target = X``."""
        stmts = []
        for node in body_nodes:
            if isinstance(node, ast.Return):
                if node.value is not None:
                    val_expr = self._convert_ast_expr(node.value, scope)
                    stmts.append(StmtAssign(targets=[target_expr], value=val_expr))
            elif isinstance(node, ast.If):
                test_expr = self._convert_ast_expr(node.test, scope)
                then_stmts = self._convert_body_return_to_assign(node.body, target_expr, scope)
                else_stmts = self._convert_body_return_to_assign(node.orelse, target_expr, scope)
                stmts.append(StmtIf(test=test_expr, body=then_stmts, orelse=else_stmts))
            elif isinstance(node, ast.Match):
                subject_expr = self._convert_ast_expr(node.subject, scope)
                cases = []
                for case in node.cases:
                    pattern_expr = self._convert_ast_pattern(case.pattern, scope)
                    guard = self._convert_ast_expr(case.guard, scope) if case.guard else None
                    case_body = self._convert_body_return_to_assign(case.body, target_expr, scope)
                    cases.append(StmtMatchCase(pattern=pattern_expr, guard=guard, body=case_body))
                stmts.append(StmtMatch(subject=subject_expr, cases=cases))
            else:
                stmt = self._convert_ast_stmt(node, scope)
                if stmt is not None:
                    if isinstance(stmt, list):
                        stmts.extend(stmt)
                    else:
                        stmts.append(stmt)
        return stmts


    def _convert_ast_stmt(self, node : ast.AST, scope: ConversionScope = None) -> Optional[Stmt]:
        """Convert an AST statement to a data model statement."""

        def _leading_comment(n) -> Optional[str]:
            """Collect the block of plain comment lines immediately above n.lineno."""
            if not (scope and scope.comment_map):
                return None
            lines = []
            lineno = getattr(n, 'lineno', None)
            if lineno is None:
                return None
            lineno -= 1
            while lineno > 0 and lineno in scope.comment_map:
                lines.append(scope.comment_map[lineno])
                lineno -= 1
            return '\n'.join(reversed(lines)) if lines else None

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

        # In constraint mode: treat ``self.field == value`` as an assignment.
        # This compiles @zdc.constraint methods (which use == for field binding)
        # to imperative C assignments for SW execution.
        if (scope is not None and scope.is_constraint_mode and
                isinstance(node, ast.Expr) and isinstance(node.value, ast.Compare)):
            compare = node.value
            if (len(compare.ops) == 1 and isinstance(compare.ops[0], ast.Eq) and
                    isinstance(compare.left, ast.Attribute) and
                    isinstance(compare.left.value, ast.Name) and
                    compare.left.value.id == 'self' and
                    compare.left.attr in scope.action_field_names):
                field_name = compare.left.attr
                target = ExprAttribute(
                    value=ExprRefLocal(name=scope.action_result_var),
                    attr=field_name,
                )
                comparator = compare.comparators[0]
                # For complex RHS method calls: inline the method body with return→assign
                if (isinstance(comparator, ast.Call) and
                        isinstance(comparator.func, ast.Attribute) and
                        isinstance(comparator.func.value, ast.Name) and
                        comparator.func.value.id == 'self' and
                        scope.action_cls is not None):
                    method_name = comparator.func.attr
                    raw_member = scope.action_cls.__dict__.get(method_name)
                    if not isinstance(raw_member, staticmethod):
                        method = getattr(scope.action_cls, method_name, None)
                        if method is not None and callable(method):
                            block = self._inline_method_with_return_assign(method, target, scope)
                            if block is not None:
                                return block
                value_expr = self._convert_ast_expr(comparator, scope)
                return StmtAssign(targets=[target], value=value_expr)

        # Handle var.set(value) where var is an IndexedRegFile write binding
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and
                isinstance(node.value.func, ast.Attribute) and node.value.func.attr == 'set' and
                isinstance(node.value.func.value, ast.Name) and scope is not None and
                node.value.func.value.id in scope.regfile_bindings):
            var_name = node.value.func.value.id
            field_idx, idx_expr, _mode = scope.regfile_bindings[var_name]
            if len(node.value.args) >= 1:
                rhs = self._convert_ast_expr(node.value.args[0], scope)
                return StmtAssign(
                    targets=[ExprSubscript(
                        value=ExprRefField(base=TypeExprRefSelf(), index=field_idx),
                        slice=idx_expr,
                    )],
                    value=rhs,
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
            # Check for void action call: ``await ActionCls(kwargs)(comp=self)``
            if isinstance(node.value, ast.Await):
                parsed = self._parse_action_call(node.value)
                if parsed is not None:
                    action_name, inner_call, outer_call = parsed
                    py_globals = self._get_scope_globals(scope)
                    inlined = self._inline_action_call(
                        result_var=None,
                        action_name=action_name,
                        inner_call=inner_call,
                        outer_call=outer_call,
                        scope=scope,
                        py_globals=py_globals,
                    )
                    if inlined is not None:
                        return inlined
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
                orelse=self._convert_ast_body(node.orelse, scope),
                comment=_leading_comment(node),
            )
        elif isinstance(node, ast.While):
            return StmtWhile(
                test=self._convert_ast_expr(node.test, scope),
                body=self._convert_ast_body(node.body, scope),
                orelse=self._convert_ast_body(node.orelse, scope) if node.orelse else [],
                comment=_leading_comment(node),
            )
        elif isinstance(node, ast.If):
            pragmas = scope.pragma_map.get(node.lineno, {}) if (scope and scope.pragma_map) else {}
            return StmtIf(
                test=self._convert_ast_expr(node.test, scope),
                body=self._convert_ast_body(node.body, scope),
                orelse=self._convert_ast_body(node.orelse, scope),
                pragmas=pragmas,
                comment=_leading_comment(node),
            )
        elif isinstance(node, ast.Assign):
            # Check for unannotated action call: ``var = await ActionCls(kwargs)(comp=self)``
            # This is the same as ast.AnnAssign but without a type annotation.
            if (node.value is not None and isinstance(node.value, ast.Await)
                    and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)):
                parsed = self._parse_action_call(node.value)
                if parsed is not None:
                    action_name, inner_call, outer_call = parsed
                    result_var = node.targets[0].id
                    # Apply action-body prefix when inlining nested actions
                    if scope and scope.is_action_body and scope.action_local_prefix:
                        result_var = scope.action_local_prefix + result_var
                    py_globals = self._get_scope_globals(scope)
                    inlined = self._inline_action_call(
                        result_var=result_var,
                        action_name=action_name,
                        inner_call=inner_call,
                        outer_call=outer_call,
                        scope=scope,
                        py_globals=py_globals,
                    )
                    if inlined is not None:
                        return inlined
            # Lower tuple-unpack: ``a, b, ... = f(...)`` → temp struct + field extracts.
            # Special case: ``a, b = await self.comp.regfile.read_all(i1, i2)``
            # → ``a = CompName_regfile_get(comp, i1); b = CompName_regfile_get(comp, i2)``
            if (len(node.targets) == 1 and isinstance(node.targets[0], ast.Tuple)):
                regfile_lowered = self._try_lower_regfile_read_all(
                    node.targets[0], node.value, scope)
                if regfile_lowered is not None:
                    return regfile_lowered
                tuple_target = node.targets[0]
                arity = len(tuple_target.elts)
                # Generate a unique temp name using a counter stored on self.
                tmp_idx = getattr(self, '_tuple_unpack_ctr', 0)
                self._tuple_unpack_ctr = tmp_idx + 1
                tmp_name = f"_tu_{tmp_idx}"
                if scope is not None:
                    scope.local_vars.add(tmp_name)
                rhs_expr = self._convert_ast_expr(node.value, scope)
                stmts = [
                    StmtAnnAssign(
                        target=ExprRefLocal(name=tmp_name),
                        annotation=ExprRefUnresolved(name="_zsp_tuple"),
                        value=rhs_expr,
                        ir_type=DataTypeTupleReturn(arity=arity),
                    )
                ]
                for i, elt in enumerate(tuple_target.elts):
                    if isinstance(elt, ast.Name):
                        var_name = elt.id
                        if scope and scope.is_action_body and scope.action_local_prefix:
                            var_name = scope.action_local_prefix + var_name
                        if scope is not None:
                            scope.local_vars.add(var_name)
                        stmts.append(StmtAssign(
                            targets=[ExprRefLocal(name=var_name)],
                            value=ExprAttribute(
                                value=ExprRefLocal(name=tmp_name),
                                attr=f"v{i}",
                            ),
                        ))
                return stmts
            # Track assigned variables as locals; apply action-body prefix if needed
            if scope is not None:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        var_name = target.id
                        if scope.is_action_body and scope.action_local_prefix:
                            var_name = scope.action_local_prefix + var_name
                        scope.local_vars.add(var_name)
            _assign_pragmas = scope.pragma_map.get(node.lineno, {}) if (scope and scope.pragma_map) else {}
            return StmtAssign(
                targets=[self._convert_ast_expr(t, scope) for t in node.targets],
                value=self._convert_ast_expr(node.value, scope),
                pragmas=_assign_pragmas,
                comment=_leading_comment(node),
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
                value=self._convert_ast_expr(node.value, scope),
                comment=_leading_comment(node),
            )
        elif isinstance(node, ast.AnnAssign):
            # Annotated assignment: ``name: Type = value``
            # Check for action call pattern: ``var: T = await ActionCls(kwargs)(comp=self)``
            if node.value is not None and isinstance(node.value, ast.Await):
                parsed = self._parse_action_call(node.value)
                if parsed is not None:
                    action_name, inner_call, outer_call = parsed
                    result_var = node.target.id if isinstance(node.target, ast.Name) else None
                    # Apply action-body prefix when inlining nested actions
                    if result_var and scope and scope.is_action_body and scope.action_local_prefix:
                        result_var = scope.action_local_prefix + result_var
                    py_globals = self._get_scope_globals(scope)
                    inlined = self._inline_action_call(
                        result_var=result_var,
                        action_name=action_name,
                        inner_call=inner_call,
                        outer_call=outer_call,
                        scope=scope,
                        py_globals=py_globals,
                    )
                    if inlined is not None:
                        return inlined
            # Track the target as a local variable.
            if scope is not None and isinstance(node.target, ast.Name):
                scope.local_vars.add(node.target.id)
            target = self._convert_ast_expr(node.target, scope)
            annotation = self._convert_ast_expr(node.annotation, scope)
            value = self._convert_ast_expr(node.value, scope) if node.value else None
            return StmtAnnAssign(
                target=target,
                annotation=annotation,
                value=value,
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
            pragmas = scope.pragma_map.get(node.lineno, {}) if (scope and scope.pragma_map) else {}
            return StmtMatch(
                subject=self._convert_ast_expr(node.subject, scope),
                cases=cases,
                pragmas=pragmas,
                comment=_leading_comment(node),
            )
        elif isinstance(node, (ast.AsyncWith, ast.With)):
            return self._convert_async_with(node, scope)
        return None

    def _convert_ast_expr(self, node : ast.AST, scope: ConversionScope = None) -> Optional[Any]:
        """Convert an AST expression to a data model expression."""
        if node is None:
            return None
        
        if isinstance(node, ast.Call):
            # Handle var.get() where var is an IndexedRegFile read binding
            if (isinstance(node.func, ast.Attribute) and node.func.attr == 'get' and
                    isinstance(node.func.value, ast.Name) and scope is not None and
                    node.func.value.id in scope.regfile_bindings):
                var_name = node.func.value.id
                field_idx, idx_expr, _mode = scope.regfile_bindings[var_name]
                return ExprSubscript(
                    value=ExprRefField(base=TypeExprRefSelf(), index=field_idx),
                    slice=idx_expr,
                )

            # In action-body scope: inline self._method() calls.
            # - @staticmethod → direct call (no self argument)
            # - simple instance method (single return) → inline the return expr
            if (isinstance(node.func, ast.Attribute) and
                    isinstance(node.func.value, ast.Name) and
                    node.func.value.id == 'self' and
                    scope is not None and scope.is_action_body and
                    scope.action_cls is not None):
                method_name = node.func.attr
                raw_member = scope.action_cls.__dict__.get(method_name)
                if isinstance(raw_member, staticmethod):
                    # Emit as a direct C function call (static inline, no self)
                    return ExprCall(
                        func=ExprRefUnresolved(name=method_name),
                        args=[self._convert_ast_expr(a, scope) for a in node.args],
                    )
                method = getattr(scope.action_cls, method_name, None)
                if (method is not None and callable(method) and
                        not (hasattr(method, '_is_constraint') and method._is_constraint) and
                        method_name not in ('body',)):
                    inlined = self._try_inline_instance_method_as_expr(method, scope)
                    if inlined is not None:
                        return inlined

            return ExprCall(
                func=self._convert_ast_expr(node.func, scope),
                args=[self._convert_ast_expr(a, scope) for a in node.args]
            )
        elif isinstance(node, ast.Attribute):
            attr_name = node.attr

            # --- Pool claim: claim.t → ExprRefField for the pool field ---
            # Detect BEFORE full value conversion to avoid recursion issues.
            if (attr_name == 't'
                    and isinstance(node.value, ast.Name)
                    and scope is not None
                    and node.value.id in scope.pool_claims):
                pool_field_idx = scope.pool_claims[node.value.id]
                return ExprRefField(base=TypeExprRefSelf(), index=pool_field_idx)

            value_expr = self._convert_ast_expr(node.value, scope)

            # --- Action-body scope translation ---
            if scope and scope.is_action_body:
                # self.comp.X  (value_expr is a _ExprActionComp sentinel)
                if isinstance(value_expr, _ExprActionComp):
                    if attr_name in scope.comp_field_indices:
                        return ExprRefField(
                            base=TypeExprRefSelf(),
                            index=scope.comp_field_indices[attr_name],
                        )
                    # Fall through to ExprAttribute so unknown accesses aren't lost
                    return ExprAttribute(value=TypeExprRefSelf(), attr=attr_name)

                # self.X  (value_expr is _ExprActionSelf sentinel)
                if isinstance(value_expr, _ExprActionSelf):
                    if attr_name == 'comp':
                        return _ExprActionComp()
                    # Action data field access → locals->result_var.field
                    if attr_name in scope.action_field_names:
                        return ExprAttribute(
                            value=ExprRefLocal(name=scope.action_result_var),
                            attr=attr_name,
                        )
                    # Unknown action attribute — emit unresolved
                    return ExprRefUnresolved(name=attr_name)

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
            
            # Handle 'self' — return sentinel when inside an action body
            if name == "self":
                if scope and scope.is_action_body:
                    return _ExprActionSelf()
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

            # Inside action body, unresolved names get the local prefix
            if scope and scope.is_action_body and name not in ('True', 'False', 'None'):
                prefixed = scope.action_local_prefix + name
                if prefixed in scope.local_vars:
                    return ExprRefLocal(name=prefixed)
            
            # Try resolving as a module-level integer constant (e.g. _OP_OP = 0x33)
            py_globals = self._get_scope_globals(scope)
            if py_globals:
                val = py_globals.get(name)
                if isinstance(val, int) and not isinstance(val, bool):
                    return ExprConstant(value=val)

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
        elif isinstance(node, ast.Slice):
            # Handle bit-slice expressions, e.g. x[4:0] → ExprSlice(lower=4, upper=0)
            from .ir.expr import ExprSlice
            return ExprSlice(
                lower=self._convert_ast_expr(node.lower, scope) if node.lower is not None else None,
                upper=self._convert_ast_expr(node.upper, scope) if node.upper is not None else None,
                is_bit_slice=True,
            )
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
            ast.FloorDiv: BinOp.FloorDiv,
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
