from __future__ import annotations
import dataclasses as dc
from typing import List, Optional, Protocol, TYPE_CHECKING, Iterator, Any
from .base import Base
from .expr import Expr

if TYPE_CHECKING:
    from .fields import Field
    from .stmt import Stmt, Arguments

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
    is_invariant : bool = dc.field(default=False)

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
class DataTypeChannel(DataType):
    """Represents a TLM Channel - bidirectional communication channel"""
    element_type : Optional[DataType] = dc.field(default=None)


