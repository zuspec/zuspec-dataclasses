
from enum import IntEnum, IntFlag, auto
from tokenize import Intnumber
from typing import List
import vsc_dataclasses as vsc

import vsc_dataclasses.impl.context as vsc_ctxt

class DataTypeArlStruct(vsc_ctxt.DataTypeStruct):

    def addExec(self, exec : 'TypeExec'):
        raise NotImplementedError("addExec")
    
    def getExecs(self):
        raise NotImplementedError("getExecs")
    
    def addFunction(self, f : 'DataTypeFunction'):
        raise NotImplementedError("addFunction")
    
    def getFunctions(self):
        raise NotImplementedError("getFunctions")


class DataTypeAction(DataTypeArlStruct):

    def getComponentType(self) -> 'DataTypeComponent':
        raise NotImplementedError("getComponentType")
    
    def setComponentType(self, t : 'DataTypeComponent'):
        raise NotImplementedError("setComponentType")

    def getCompField(self) -> 'vsc_ctxt.TypeFieldRef':
        raise NotImplementedError("getCompField")

    def addActivity(self, activity : 'TypeFieldActivity'):
        raise NotImplementedError("addActivity")

    def activities(self) -> List['TypeFieldActivity']:
        raise NotImplementedError('activities')

class DataTypeActivity(vsc_ctxt.DataType):

    def mkActivity(self, ctxt : vsc_ctxt.ModelBuildContext, type : 'TypeFieldActivity'):
        raise NotImplementedError("mkActivity")


class DataTypeActivityScope(DataTypeActivity, vsc_ctxt.DataTypeStruct):

    def getActivities(self) -> List['TypeFieldActivity']:
        raise NotImplementedError("getActivities")

    def addActivity(self, a : 'TypeFieldActivity'):
        raise NotImplementedError("addActivity")
    
    def addActivityField(self, a : 'TypeFieldActivity'):
        raise NotImplementedError("addActivityField")

class DataTypeActivityReplicate(DataTypeActivityScope):

    def getCount(self) -> 'TypeExpr':
        pass

class DataTypeActivityTraverse(DataTypeActivity):

    def getTarget(self) -> vsc_ctxt.TypeExprFieldRef:
        raise NotImplementedError("getTarget")

    def getWithC(self) -> 'vsc_ctxt.TypeConstraint':
        raise NotImplementedError("getWithC")

    def setWithC(self, c : 'vsc_ctxt.TypeConstraint'):
        raise NotImplementedError("setWithC")


class DataTypeComponent(vsc_ctxt.DataTypeStruct):

    def getActionTypes(self) -> List[DataTypeAction]:
        raise NotImplementedError("getActionTypes")

    def addActionType(self, t : DataTypeAction):
        raise NotImplementedError("addActionType")

    def addPoolBindDirective(self, bind : 'PoolBindDirective'):
        raise NotImplementedError("addPoolBindDirective")
    
class ParamDir(IntEnum):
    In = auto()
    Out = auto()
    InOut = auto()

class TypeProcStmtScope(object):

    def addStatement(self, s):
        raise NotImplementedError("addStatement")
    
    def addVariable(self, v):
        raise NotImplementedError("addVariable")

    def getStatements(self):
        raise NotImplementedError("getStatements")

    def getVariables(self):
        raise NotImplementedError("getVariables")

class TypeProcStmtVarDecl(object):

    def name(self) -> str:
        raise NotImplementedError("name")
    
    def getDataType(self) -> vsc_ctxt.DataType:
        raise NotImplementedError("getDataType")
    
    def getInit(self):
        raise NotImplementedError("getInit")
    
class DataTypeFunctionParamDecl(TypeProcStmtVarDecl):
    def getDirection(self) -> ParamDir:
        raise NotImplementedError("getDirection")
    
class DataTypeFunctionFlags(IntFlag):
    NoFlags = 0
    Solve   = (1 << 0)
    Target  = (1 << 1)
    Core    = (1 << 2)
    
class DataTypeFunction(vsc_ctxt.DataType):

    def name(self):
        raise NotImplementedError("DataTypeFunction.name")
    
    def getReturnType(self) -> vsc_ctxt.DataType:
        raise NotImplementedError("DataTypeFunction.getReturnType")
    
    def getParameters(self) -> List[DataTypeFunctionParamDecl]:
        raise NotImplementedError("DataTypeFunction.getParameters")
    
    def addParameter(self, p : DataTypeFunctionParamDecl):
        raise NotImplementedError("DataTypeFunction.addParameter")
    
    def getBody(self):
        raise NotImplementedError("getBody")
    
    def setBody(self, b):
        raise NotImplementedError("setBody")
    
    def addImportSpec(self, spec : 'DataTypeFunctionImport'):
        raise NotImplementedError("addImportSpec")
    
    def getImportSpecs(self) -> List['DataTypeFunctionImport']:
        raise NotImplementedError("getImportSpecs")
    
    def getFlags(self) -> DataTypeFunctionFlags:
        raise NotImplementedError("getFlags")

    def hasFlags(self, f) -> bool:
        raise NotImplementedError("hasFlags")

class DataTypeFunctionImport(object):

    def isTarget(self) -> bool:
        raise NotImplementedError("isTarget")
    
    def isSolve(self) -> bool:
        raise NotImplementedError("isSolve")


class FlowObjKindE(IntEnum):
    Buffer   = 0
    Resource = 1
    State    = 2
    Stream   = 3

class ModelBuildContext(vsc_ctxt.ModelBuildContext):

    def __init__(self, ctxt):
        super().__init__(ctxt)
    pass

class ModelEvalNodeT(IntEnum):
    Action = 0

class ModelFieldComponent(vsc_ctxt.ModelField):

    def initCompTree(self):
        raise NotImplementedError("initCompTree")


class PoolBindKind(IntEnum):
    All = 0

class ExecKindT(IntEnum):
    Body = auto()
    InitDown = auto()
    InitUp = auto()
    PreSolve = auto()
    PostSolve = auto()

class TypeExec(object):

    def getKind(self) -> ExecKindT:
        raise NotImplementedError("getKind")
    
    def getBody(self):
        raise NotImplementedError("getBody")

class TypeExprMethodCallStatic(vsc_ctxt.TypeExpr):

    def getTarget(self) -> DataTypeFunction:
        raise NotImplementedError("getTarget")
    
    def getParameters(self) -> List[vsc_ctxt.TypeExpr]:
        raise NotImplementedError("getParameters")
    
class TypeExprMethodCallContext(TypeExprMethodCallStatic):

    def getContext(self):
        raise NotImplementedError("getContext")

class TypeFieldActivity(vsc_ctxt.TypeField):

    def mkActivity(self, ctxt : ModelBuildContext):
        raise NotImplementedError("mkActivity")
    
class TypeFieldReg(vsc_ctxt.TypeField):

    def getOffset(self):
        raise NotImplementedError("getOffset")
    
    def setOffset(self, off):
        raise NotImplementedError("setOffset")
    
class TypeFieldRegGroup(vsc_ctxt.TypeField):
    def getOffset(self):
        raise NotImplementedError("getOffset")
    
    def setOffset(self, off):
        raise NotImplementedError("setOffset")

class TypeProcStmtAssignOp(IntEnum):
    Eq = auto()
    PlusEq = auto()
    MinusEq = auto()
    ShlEq = auto()
    ShrEq = auto()
    OrEq = auto()
    AndEq = auto()

class TypeProcStmtAssign(object):

    def getLhs(self):
        raise NotImplementedError("getLhs")

    def op(self):
        raise NotImplementedError("op")

    def getRhs(self):
        raise NotImplementedError("getRhs")

class TypeProcStmtExpr(object):

    def getExpr() -> vsc_ctxt.TypeExpr:
        raise NotImplementedError("getExpr")

class TypeProcStmtIfElse(object):

    def getCond(self):
        raise NotImplementedError("getCond")
    
    def setTrue(self, s):
        raise NotImplementedError("setTrue")
    
    def getTrue(self):
        raise NotImplementedError("getTrue")

    def setFalse(self, s):
        raise NotImplementedError("setFalse")

    def getFalse(self):
        raise NotImplementedError("getFalse")

class Context(vsc.impl.Context):

    def findDataTypeAction(self, name) -> 'DataTypeAction':
        raise NotImplementedError("findDataTypeAction")
    
    def mkDataTypeAction(self, name) -> DataTypeAction:
        raise NotImplementedError("mkDataTypeAction")

    def addDataTypeAction(self, t : DataTypeAction) -> bool:
        raise NotImplementedError("addDataTypeAction")

    def mkDataTypeActivityParallel(self) -> 'DataTypeActivityParallel':
        raise NotImplementedError("mkDataTypeActivityParallel")

    def mkDataTypeActivityReplicate(self, count) -> 'DataTypeActivityReplicate':
        raise NotImplementedError("mkDataTypeActivityReplicate")

    def mkDataTypeActivitySchedule(self) -> 'DataTypeActivitySchedule':
        raise NotImplementedError("mkDataTypeActivitySchedule")

    def mkDataTypeActivitySequence(self) -> 'DataTypeActivitySequence':
        raise NotImplementedError("mkDataTypeActivitySequence")

    def mkDataTypeActivityTraverse(self, target : 'vsc_ctxt.TypeExprFieldRef', with_c : 'vsc_ctxt.TypeConstraint'):
        raise NotImplementedError("mkDataTypeActivityTraverse")

    def findDataTypeComponent(self, name) -> 'DataTypeComponent':
        raise NotImplementedError("findDataTypeComponent")

    def mkDataTypeComponent(self, name) -> 'DataTypeComponent':
        raise NotImplementedError("mkDataTypeComponent")

    def addDataTypeComponent(self, t : 'DataTypeComponent') -> bool:
        raise NotImplementedError("addDataTypeComponent")
    
    def mkDataTypeFunction(self,
                           name : str,
                           rtype : vsc_ctxt.DataType,
                           own_rtype : bool,
                           flags : DataTypeFunctionFlags):
        raise NotImplementedError("mkDataTypeFunction")
    
    def addDataTypeFunction(self, f):
        raise NotImplementedError("addDataTypeFunction")
    
    def getDataTypeFunctions(self):
        raise NotImplementedError("getDataTypeFunctions")
    
    def findDataTypeFunction(self, name):
        raise NotImplementedError("findDataTypeFunction")
    
    def mkDataTypeFunctionImport(self,
                                lang,
                                is_target,
                                is_solve):
        raise NotImplementedError("mkDataTypeFunctionImport")

    def mkDataTypeFunctionParamDecl(self,
                                name,
                                dir : ParamDir,
                                type : vsc_ctxt.DataType,
                                own : bool,
                                init : vsc_ctxt.TypeExpr) -> DataTypeFunctionParamDecl:
        raise NotImplementedError("mkDataTypeFunctionParamDecl")

    def mkTypeExec(self,
                   kind,
                   body):
        raise NotImplementedError("mkTypeExec")
    
    def mkTypeExprMethodCallContext(self,
                                target : DataTypeFunction,
                                context,
                                params : List[vsc_ctxt.TypeExpr]):
        raise NotImplementedError("mkTypeExprMethodCallContext")

    def mkTypeExprMethodCallStatic(self,
                                target : DataTypeFunction,
                                params : List[vsc_ctxt.TypeExpr]):
        raise NotImplementedError("mkTypeExprMethodCallStatic")

    def mkTypeFieldActivity(self, name, type : 'DataTypeActivity', owned):
        raise NotImplementedError("mkTypeFieldActivity")
    
    def mkTypeFieldReg(self,
                    name,
                    type,
                    owned):
        raise NotImplementedError("mkTypeFieldReg")

    def mkTypeFieldRegGroup(self,
                    name,
                    type,
                    owned):
        raise NotImplementedError("mkTypeFieldRegGroup")
    
    def mkTypeProcStmtAssign(self,
                             lhs,
                             op,
                             rhs):
        raise NotImplementedError("mkTypeProcStmtAssign")
    
    def mkTypeProcStmtScope(self):
        raise NotImplementedError("mkTypeProcStmtScope")
    
    def mkTypeProcStmtExpr(self, expr):
        raise NotImplementedError("mkTypeProcStmtExpr")
    
    def mkTypeProcStmtIfElse(self,
                            cond,
                            true_s,
                            false_s):
        raise NotImplementedError("mkTypeProcStmtIfElse")
    

    pass