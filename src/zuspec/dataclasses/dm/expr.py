#****************************************************************************
# Copyright 2019-2025 Matthew Ballance and contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#****************************************************************************
from __future__ import annotations
import dataclasses as dc
import enum
from typing import Optional
from .base import Base


@dc.dataclass(kw_only=True)
class Expr(Base):
    pass

class BinOp(enum.Enum):
    Add = enum.auto(); Sub = enum.auto(); Mult = enum.auto(); Div = enum.auto(); Mod = enum.auto()
    BitAnd = enum.auto(); BitOr = enum.auto(); BitXor = enum.auto(); LShift = enum.auto(); RShift = enum.auto()
    Eq = enum.auto(); NotEq = enum.auto(); Lt = enum.auto(); LtE = enum.auto(); Gt = enum.auto(); GtE = enum.auto()
    And = enum.auto(); Or = enum.auto()

class UnaryOp(enum.Enum):
    Invert = enum.auto(); Not = enum.auto(); UAdd = enum.auto(); USub = enum.auto()

class BoolOp(enum.Enum):
    And = enum.auto(); Or = enum.auto()

class CmpOp(enum.Enum):
    Eq = enum.auto(); NotEq = enum.auto(); Lt = enum.auto(); LtE = enum.auto(); Gt = enum.auto(); GtE = enum.auto(); Is = enum.auto(); IsNot = enum.auto(); In = enum.auto(); NotIn = enum.auto()

class AugOp(enum.Enum):
    Add = enum.auto(); Sub = enum.auto(); Mult = enum.auto(); Div = enum.auto(); Mod = enum.auto(); Pow = enum.auto()
    LShift = enum.auto(); RShift = enum.auto(); BitAnd = enum.auto(); BitOr = enum.auto(); BitXor = enum.auto(); FloorDiv = enum.auto()

@dc.dataclass(kw_only=True)
class Keyword(Base):
    arg: Optional[str] = dc.field(default=None)
    value: Expr = dc.field()

@dc.dataclass(kw_only=True)
class ExprBin(Expr):
    lhs : Expr = dc.field()
    op : BinOp = dc.field()
    rhs : Expr = dc.field()

@dc.dataclass(kw_only=True)
class ExprRef(Expr):
    pass

@dc.dataclass(kw_only=True)
class ExprConstant(Expr):
    value: object = dc.field()
    kind: Optional[str] = dc.field(default=None)

@dc.dataclass
class TypeExprRefSelf(ExprRef): 
    """Reference to 'self'"""
    ...

@dc.dataclass(kw_only=True)
class ExprRefField(ExprRef):
    """Reference to a field relative to the base expression"""
    base : Expr = dc.field()
    index : int = dc.field()


@dc.dataclass(kw_only=True)
class ExprRefPy(ExprRef):
    """Reference relative to a Python object (base)"""
    base : Expr = dc.field()
    ref : str = dc.field()

class ExprRefBottomUp(ExprRef):
    """Reference to a field relative to the active procedural scope"""
    uplevel : int = dc.field(default=0)
    index : int = dc.field()

# class TypeExprRefTopDown(ABC):
#     @property
#     @abstractmethod
#     def ref(self) -> str:
#         ...

@dc.dataclass(kw_only=True)
class ExprUnary(Expr):
    op: UnaryOp = dc.field()
    operand: Expr = dc.field()

@dc.dataclass(kw_only=True)
class ExprBool(Expr):
    op: BoolOp = dc.field()
    values: list[Expr] = dc.field(default_factory=list)

@dc.dataclass(kw_only=True)
class ExprCompare(Expr):
    left: Expr = dc.field()
    ops: list[CmpOp] = dc.field(default_factory=list)
    comparators: list[Expr] = dc.field(default_factory=list)

@dc.dataclass(kw_only=True)
class ExprAttribute(Expr):
    value: Expr = dc.field()
    attr: str = dc.field()

@dc.dataclass(kw_only=True)
class ExprSlice(Expr):
    lower: Optional[Expr] = dc.field(default=None)
    upper: Optional[Expr] = dc.field(default=None)
    step: Optional[Expr] = dc.field(default=None)

@dc.dataclass(kw_only=True)
class ExprSubscript(Expr):
    value: Expr = dc.field()
    slice: ExprSlice = dc.field()

@dc.dataclass(kw_only=True)
class ExprCall(Expr):
    func: Expr = dc.field()
    args: list[Expr] = dc.field(default_factory=list)
    keywords: list[Keyword] = dc.field(default_factory=list)


