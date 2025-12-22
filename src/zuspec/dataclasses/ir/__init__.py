"""
The zuspec.ir module defines a set of classes that provide a type model
to represent time-consuming behaviors. The data model targets behavioral
models of hardware-centric systems.

Several conventions are used by this data model, and extensions, to 
textually represent content within the datamodel and constraints on
that content.

"""
import dataclasses as dc
from typing import dataclass_transform

def profile(modname, super=None):
    """Register a profile"""
    from .profile_rgy import ProfileRgy
    ProfileRgy.register_profile(modname, super)


from .base import Base, BaseP
from .context import Context
from .visitor import Visitor
from .json_converter import JsonConverter

@dataclass_transform()
def visitor_dataclass(pmod, *args, **kwargs):
    """Decorator for datamodel Visitor class"""
    def closure(T):
        c = dc.dataclass(T, *args, **kwargs)
        setattr(c, "__new__", lambda cls,pmod=pmod: Visitor.__new__(cls,pmod))
        return c
    return closure

def visitor(pmod, *args, **kwargs):
    """Decorator for non-datamodel Visitor class"""
    def closure(T):
        setattr(T, "__new__", lambda cls,pmod=pmod: Visitor.__new__(cls,pmod))
        return T
    return closure

def json_converter(pmod, *args, **kwargs):
    """Decorator for JsonConverter class"""
    def closure(T):
        setattr(T, "__new__", lambda cls,pmod=pmod: JsonConverter.__new__(cls,pmod))
        return T
    return closure


# Re-export data model types
from .fields import Bind, BindSet, Field, FieldInOut, FieldKind, SignalDirection
from .data_type import (
    DataType, DataTypeInt, DataTypeStruct, DataTypeClass, DataTypeComponent, DataTypeExtern,
    DataTypeExpr, DataTypeEnum, DataTypeString, DataTypeLock, DataTypeMemory,
    DataTypeAddressSpace, DataTypeAddrHandle, DataTypeProtocol, DataTypeRef,
    DataTypeGetIF, DataTypePutIF, DataTypeChannel,
    Function, Process, ProcessKind
)
from .expr import (
    Expr, BinOp, UnaryOp, BoolOp, CmpOp, AugOp,
    ExprBin, ExprRef, ExprConstant, TypeExprRefSelf, ExprRefField,
    ExprRefParam, ExprRefLocal, ExprRefUnresolved, ExprRefPy,
    ExprRefBottomUp, ExprUnary, ExprBool, ExprCompare,
    ExprAttribute, ExprSlice, ExprSubscript, ExprCall, Keyword, ExprAwait
)
from .expr_phase2 import (
    ExprList, ExprTuple, ExprDict, ExprSet, Comprehension, ExprListComp,
    ExprDictComp, ExprSetComp, ExprGeneratorExp, ExprIfExp, ExprLambda, ExprNamedExpr,
    ExprJoinedStr, ExprFormattedValue
)
from .stmt import (
    Stmt, StmtExpr, StmtAssign, StmtAugAssign, StmtReturn, StmtIf, StmtFor,
    StmtWhile, StmtBreak, StmtContinue, StmtPass, StmtRaise, StmtAssert, Alias, Arg, Arguments,
    StmtAssume, StmtCover,
    WithItem, StmtWith, StmtExceptHandler, StmtTry, TypeIgnore, Module,
    StmtMatch, StmtMatchCase, Pattern, PatternValue, PatternAs, PatternOr, PatternSequence
)

__all__ = [
    "profile","Base","BaseP","Visitor","JsonConverter","json_converter",
    "Bind","BindSet","Field","FieldInOut","FieldKind","SignalDirection",
    "DataType","DataTypeInt","DataTypeStruct","DataTypeClass","DataTypeComponent","DataTypeExtern",
    "DataTypeExpr","DataTypeEnum","DataTypeString","DataTypeLock","DataTypeMemory",
    "DataTypeAddressSpace","DataTypeAddrHandle","DataTypeProtocol","DataTypeRef",
    "DataTypeGetIF","DataTypePutIF","DataTypeChannel",
    "Function","Process","ProcessKind",
    "Expr","BinOp","UnaryOp","BoolOp","CmpOp","AugOp","ExprBin","ExprRef","ExprConstant",
    "TypeExprRefSelf","ExprRefField","ExprRefParam","ExprRefLocal","ExprRefUnresolved",
    "ExprRefPy","ExprRefBottomUp","ExprUnary",
    "ExprBool","ExprCompare","ExprAttribute","ExprSlice","ExprSubscript","ExprCall","Keyword","ExprAwait",
    "Stmt","StmtExpr","StmtAssign","StmtAugAssign","StmtReturn","StmtIf","StmtFor","StmtWhile",
    "StmtBreak","StmtContinue","StmtPass","StmtRaise","StmtAssert","StmtAssume","StmtCover","Alias","Arg","Arguments",
"ExprList","ExprTuple","ExprDict","ExprSet","Comprehension","ExprListComp","ExprDictComp",
"ExprSetComp","ExprGeneratorExp","ExprIfExp","ExprLambda","ExprNamedExpr",
"WithItem","StmtWith","StmtExceptHandler","StmtTry","TypeIgnore","Module",
"ExprJoinedStr","ExprFormattedValue","StmtMatch","StmtMatchCase","Pattern","PatternValue","PatternAs","PatternOr","PatternSequence",
"Context"
]

# Important to place after all data-model classes have been imported
profile(__name__)

# Note: 'fe' module is only available in the base zuspec.ir package, not zuspec.dataclasses.ir
# from . import fe
