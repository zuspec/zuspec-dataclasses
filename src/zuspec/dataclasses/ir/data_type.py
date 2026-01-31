from __future__ import annotations
import dataclasses as dc
import enum
from typing import List, Optional, Protocol, TYPE_CHECKING, Iterator, Any
from .base import Base
from .expr import Expr

if TYPE_CHECKING:
    from .fields import Field
    from .stmt import Stmt, Arguments

class ProcessKind(enum.Enum):
    """Kind of hardware process"""
    COMB = enum.auto()  # Combinational logic
    SYNC = enum.auto()  # Synchronous (clocked) logic

@dc.dataclass(kw_only=True)
class DataType(Base):
    name : Optional[str] = dc.field(default=None)
    py_type : Optional[Any] = dc.field(default=None)  # Reference to original Python type

@dc.dataclass(kw_only=True)
class DataTypePyObj(Base): 
    """Opaque Python object"""
    ...

@dc.dataclass(kw_only=True)
class DataTypeInt(DataType):
    bits : int = dc.field(default=-1)
    signed : bool = dc.field(default=True)

@dc.dataclass(kw_only=True)
class DataTypeStruct(DataType):
    """Structs are pure-data types. 
    - methods and constraints may be applied
    - may inherit from a base

    - use 'Optional' in input to identify ref vs value
    - construct by default (?)
    - have boxed types to permit memory management?
    --> consume semantics
    """
    super : Optional[DataType] = dc.field()
    fields : List[Field] = dc.field(default_factory=list)
    functions : List = dc.field(default_factory=list)
#    constraints

@dc.dataclass(kw_only=True)
class DataTypeClass(DataTypeStruct):
    """Classes are a polymorphic extension of Structs"""
    pass

@dc.dataclass(kw_only=True)
class DataTypeComponent(DataTypeClass):
    """Components are structural building blocks that can have ports, exports, 
    and bindings. The bind_map captures connections between ports/exports."""
    bind_map : List['Bind'] = dc.field(default_factory=list)
    sync_processes : List[Function] = dc.field(default_factory=list)
    comb_processes : List[Function] = dc.field(default_factory=list)


@dc.dataclass(kw_only=True)
class DataTypeExtern(DataTypeComponent):
    """Extern component signature.

    Represents an externally-implemented component/module.
    """

    extern_name: Optional[str] = dc.field(default=None)

if TYPE_CHECKING:
    from .fields import Bind

@dc.dataclass(kw_only=True)
class DataTypeExpr(DataType):
    expr : Expr

@dc.dataclass
class DataTypeEnum(DataType): ...

@dc.dataclass(kw_only=True)
class DataTypeString(DataType): ...

@dc.dataclass(kw_only=True)
class DataTypeLock(DataType):
    """Represents a Lock (mutex) type for synchronization"""
    pass

class DataTypeEvent(DataType):
    """Represents an Event type for interrupt/callback handling"""
    pass

@dc.dataclass(kw_only=True)
class DataTypeMemory(DataType):
    """Represents a Memory type - storage for data elements"""
    element_type : Optional[DataType] = dc.field(default=None)
    size : int = dc.field(default=1024)

@dc.dataclass(kw_only=True)
class DataTypeAddressSpace(DataType):
    """Represents an AddressSpace - software view of memory and registers"""
    pass

@dc.dataclass(kw_only=True)
class DataTypeAddrHandle(DataType):
    """Represents an AddrHandle - pointer abstraction for memory access"""
    pass

@dc.dataclass(kw_only=True)
class DataTypeProtocol(DataType):
    """Represents a Python Protocol (interface definition)"""
    methods : List['Function'] = dc.field(default_factory=list)

@dc.dataclass(kw_only=True)
class Function(Base):
    """Represents a method or function"""
    name : str = dc.field()
    args : 'Arguments' = dc.field(default=None)
    body : List['Stmt'] = dc.field(default_factory=list)
    returns : Optional[DataType] = dc.field(default=None)
    is_async : bool = dc.field(default=False)
    metadata : dict = dc.field(default_factory=dict)
    is_invariant : bool = dc.field(default=False)
    process_kind : Optional[ProcessKind] = dc.field(default=None)
    sensitivity_list : List[Expr] = dc.field(default_factory=list)
    # Import/export information
    is_import : bool = dc.field(default=False)
    is_target : bool = dc.field(default=False)  # import target
    is_solve : bool = dc.field(default=False)   # import solve

@dc.dataclass(kw_only=True)
class Process(Base):
    """Represents a process (@process decorated method)"""
    name : str = dc.field()
    body : List['Stmt'] = dc.field(default_factory=list)

@dc.dataclass(kw_only=True)
class DataTypeRef(DataType):
    """Reference to another type by name (for forward references)"""
    ref_name : str = dc.field()


@dc.dataclass(kw_only=True)
class DataTypeGetIF(DataType):
    """Represents a GetIF interface - consumer side of a channel"""
    element_type : Optional[DataType] = dc.field(default=None)


@dc.dataclass(kw_only=True)
class DataTypePutIF(DataType):
    """Represents a PutIF interface - producer side of a channel"""
    element_type : Optional[DataType] = dc.field(default=None)


@dc.dataclass(kw_only=True)
class DataTypeTuple(DataType):
    """Represents a fixed-size Tuple field."""
    element_type : Optional[DataType] = dc.field(default=None)
    size : int = dc.field(default=0)
    # Optional implementation/factory type to construct elements
    elem_factory : Optional['DataType'] = dc.field(default=None)


@dc.dataclass(kw_only=True)
class DataTypeChannel(DataType):
    """Represents a TLM Channel - bidirectional communication channel"""
    element_type : Optional[DataType] = dc.field(default=None)


# =============================================================================
# Template Parameter Support (for parameterized types like reg_c<R, ACC, SZ>)
# =============================================================================

class TemplateParamKind(enum.Enum):
    """Kind of template parameter"""
    TYPE = enum.auto()    # type parameter (e.g., type R)
    VALUE = enum.auto()   # int/bit parameter (e.g., int SZ)
    ENUM = enum.auto()    # enum parameter (e.g., reg_access ACC)


@dc.dataclass(kw_only=True)
class TemplateParam(Base):
    """Template parameter declaration"""
    name : str = dc.field()
    kind : TemplateParamKind = dc.field()


@dc.dataclass(kw_only=True)
class TemplateParamType(TemplateParam):
    """Type template parameter (e.g., 'type R')"""
    constraint_type : Optional[DataType] = dc.field(default=None)  # Base constraint
    default_value : Optional[DataType] = dc.field(default=None)


@dc.dataclass(kw_only=True)
class TemplateParamValue(TemplateParam):
    """Value template parameter (e.g., 'int SZ')"""
    value_type : DataType = dc.field()  # int, bit, etc.
    default_value : Optional[Expr] = dc.field(default=None)


@dc.dataclass(kw_only=True)
class TemplateParamEnum(TemplateParam):
    """Enum template parameter (e.g., 'reg_access ACC')"""
    enum_type : DataTypeEnum = dc.field()
    default_value : Optional[str] = dc.field(default=None)


# =============================================================================
# Template Argument Support (actual parameters in instantiation)
# =============================================================================

@dc.dataclass(kw_only=True)
class TemplateArg(Base):
    """Template argument (actual parameter in instantiation)"""
    param_name : str = dc.field()


@dc.dataclass(kw_only=True)
class TemplateArgType(TemplateArg):
    """Type argument"""
    type_value : DataType = dc.field()


@dc.dataclass(kw_only=True)
class TemplateArgValue(TemplateArg):
    """Value argument"""
    value_expr : Expr = dc.field()


@dc.dataclass(kw_only=True)
class TemplateArgEnum(TemplateArg):
    """Enum argument"""
    enum_value : str = dc.field()


# =============================================================================
# Parameterized Types
# =============================================================================

@dc.dataclass(kw_only=True)
class DataTypeParameterized(DataType):
    """Base type that can be parameterized with template arguments
    
    Represents the uninstantiated template (e.g., reg_c itself)
    """
    template_params : List[TemplateParam] = dc.field(default_factory=list)


@dc.dataclass(kw_only=True)
class DataTypeSpecialized(DataType):
    """Instantiated template with concrete arguments
    
    Example: reg_c<bit[32], READWRITE, 32>
    
    Template parameter values are retrievable from specialized types
    for downstream tooling to reason about register widths, access modes, etc.
    """
    base_template : DataTypeParameterized = dc.field()
    template_args : List[TemplateArg] = dc.field(default_factory=list)
    specialized_name : Optional[str] = dc.field(default=None)  # e.g., "reg_c_bit32_READWRITE_32"
    
    def get_template_arg(self, param_name: str) -> Optional[TemplateArg]:
        """Retrieve template argument by parameter name"""
        for arg in self.template_args:
            if arg.param_name == param_name:
                return arg
        return None
    
    def get_template_arg_value(self, param_name: str) -> Any:
        """Retrieve the actual value of a template argument
        
        Returns:
            - DataType for type parameters
            - Expr for value parameters  
            - str for enum parameters
            - None if parameter not found
        """
        arg = self.get_template_arg(param_name)
        if arg is None:
            return None
        if isinstance(arg, TemplateArgType):
            return arg.type_value
        elif isinstance(arg, TemplateArgValue):
            return arg.value_expr
        elif isinstance(arg, TemplateArgEnum):
            return arg.enum_value
        return None


# =============================================================================
# Register-Specific Types
# =============================================================================

@dc.dataclass(kw_only=True)
class DataTypeRegister(DataTypeComponent):
    """Register component type (specialization of reg_c)
    
    Represents an instantiated register component with resolved template parameters.
    For eager specialization, all template parameters are resolved and stored directly
    as fields for easy access by downstream tools.
    """
    # Core register parameters (extracted from template args for direct access)
    register_value_type : DataType = dc.field()  # Type R parameter
    access_mode : str = dc.field(default="READWRITE")  # ACC parameter (READWRITE, READONLY, WRITEONLY)
    size_bits : int = dc.field()  # SZ2 parameter
    
    # Template information (for tools that need full template context)
    base_template : Optional[DataTypeParameterized] = dc.field(default=None)  # Reference to reg_c template
    template_args : List[TemplateArg] = dc.field(default_factory=list)  # Actual arguments used
    
    # Register-specific metadata
    is_pure : bool = dc.field(default=True)  # Registers should be pure components
    
    # SystemRDL compatibility fields
    systemrdl_regwidth : Optional[int] = dc.field(default=None)  # Power-of-2 width for SystemRDL
    systemrdl_accesswidth : Optional[int] = dc.field(default=None)
    
    # Inherited from DataTypeComponent:
    # - fields: register fields (from struct R if applicable)
    # - functions: read(), write(), read_val(), write_val(), etc.
    
    def get_register_param(self, param_name: str) -> Any:
        """Convenience method to retrieve template parameter values
        
        Args:
            param_name: 'R', 'ACC', or 'SZ2'/'SZ'
            
        Returns:
            - register_value_type for 'R'
            - access_mode string for 'ACC'
            - size_bits int for 'SZ2' or 'SZ'
        """
        if param_name == 'R':
            return self.register_value_type
        elif param_name == 'ACC':
            return self.access_mode
        elif param_name == 'SZ2' or param_name == 'SZ':
            return self.size_bits
        return None
    
    def compute_systemrdl_width(self) -> int:
        """Compute SystemRDL-compatible width (next power of 2)"""
        import math
        if self.size_bits < 8:
            return 8
        return 1 << (self.size_bits - 1).bit_length()


@dc.dataclass(kw_only=True)
class DataTypeRegisterGroup(DataTypeComponent):
    """Register group component type (specialization of reg_group_c)
    
    Aggregates registers and sub-groups with offset management.
    """
    # Inherited fields list contains register instances
    
    # Offset tracking
    offset_map : dict = dc.field(default_factory=dict)  # field_name -> offset
    
    # Register group is always pure
    is_pure : bool = dc.field(default=True)
    
    # Address handle association
    has_address_handle : bool = dc.field(default=False)


