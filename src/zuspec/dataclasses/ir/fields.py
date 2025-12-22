
from __future__ import annotations
import dataclasses as dc
import enum
from typing import List, Optional
from .base import Base
from .data_type import DataType
from .expr import Expr

class FieldKind(enum.Enum):
    """Kind of field in a component/class"""
    Field = enum.auto()    # Regular field
    Port = enum.auto()     # Port (API consumer)
    Export = enum.auto()   # Export (API provider)

class SignalDirection(enum.Enum):
    """Direction of hardware signals"""
    INPUT = enum.auto()
    OUTPUT = enum.auto()
    INOUT = enum.auto()

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
    direction : Optional[SignalDirection] = dc.field(default=None)
    clock : Optional[Expr] = dc.field(default=None)
    initial_value : Optional[Expr] = dc.field(default=None)

@dc.dataclass(kw_only=True)
class FieldInOut(Field):
    is_out : bool = dc.field()


