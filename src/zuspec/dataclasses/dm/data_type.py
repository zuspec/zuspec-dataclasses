from __future__ import annotations
import dataclasses as dc
from typing import List, Optional, Protocol, TYPE_CHECKING, Iterator
from .base import Base
from .expr import Expr

if TYPE_CHECKING:
    from .fields import Field

@dc.dataclass(kw_only=True)
class DataType(Base): ...

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

class DataTypeComponent(DataTypeClass):
    """Components are """
    ...

@dc.dataclass(kw_only=True)
class DataTypeExpr(DataType):
    expr : Expr

@dc.dataclass
class DataTypeEnum(DataType): ...

@dc.dataclass(kw_only=True)
class DataTypeString(DataType): ...

