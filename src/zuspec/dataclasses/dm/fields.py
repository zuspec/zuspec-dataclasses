
from __future__ import annotations
import dataclasses as dc
from typing import List
from .base import Base
from .data_type import DataType
from .expr import Expr

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
    bindset : BindSet = dc.field(default_factory=BindSet)

@dc.dataclass(kw_only=True)
class FieldInOut(Field):
    is_out : bool = dc.field()

