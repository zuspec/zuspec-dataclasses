
from __future__ import annotations
import dataclasses as dc
import enum
from typing import List
from .base import Base
from .data_type import DataType
from .expr import Expr

class FieldKind(enum.Enum):
    """Kind of field in a component/class"""
    Field = enum.auto()    # Regular field
    Port = enum.auto()     # Port (API consumer)
    Export = enum.auto()   # Export (API provider)

@dc.dataclass
class Bind(Base):
    lhs : Expr = dc.field()
    rhs : Expr = dc.field()

@dc.dataclass
class BindSet(Base):
    binds : List[Bind] = dc.field(default_factory=list)

@dc.dataclass(kw_only=True)
class Field(Base):
    name : str = dc.field()
    datatype : DataType = dc.field()
    kind : FieldKind = dc.field(default=FieldKind.Field)
    bindset : BindSet = dc.field(default_factory=BindSet)

@dc.dataclass(kw_only=True)
class FieldInOut(Field):
    is_out : bool = dc.field()


