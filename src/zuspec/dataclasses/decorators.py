'''
Created on Mar 19, 2022

@author: mballance
'''
import dataclasses
import dataclasses as dc
from typing import Any, Callable, Dict, Self, TypeVar
# from vsc_dataclasses.decorators import *
# from .impl.action_decorator_impl import ActionDecoratorImpl
# from .impl.exec_decorator_impl import ExecDecoratorImpl
# from .impl.exec_kind_e import ExecKindE
# from .impl.extend_kind_e import ExtendKindE
# from .impl.extend_decorator_impl import ExtendDecoratorImpl
# from .impl.extend_action_decorator_impl import ExtendActionDecoratorImpl
# from .impl.extend_component_decorator_impl import ExtendComponentDecoratorImpl
# from .impl.fn_decorator_impl import FnDecoratorImpl
# from .impl.struct_decorator_impl import StructDecoratorImpl
# from .impl.struct_kind_e import StructKindE
# from .impl.component_decorator_impl import ComponentDecoratorImpl
# from .impl.activity_decorator_impl import ActivityDecoratorImpl
# from .impl.type_kind_e import TypeKindE
from .annotation import Annotation, AnnotationSync
from .ports import Input, Output
from .clock import Clock

def dataclass(cls, **kwargs):
    return dc.dataclass(cls, **kwargs)

def bundle():
    return dc.field()

def mirror():
    return dc.field()

class BitLiteral(int):
    width : int = 1
    def __getitem__(self, v) -> 'BitLiteral':
        return self
        pass
    pass

def bit(t : int) -> BitLiteral:
    return BitLiteral(t)

def val(t : int) -> int:
    return t

def always(instr : BitLiteral):
   match instr[0:1]:
      case bit(0):
        match instr[13:15]:
           case bit(0):
              pass
           case bit(2):
              pass
    # unique case (instr_i[1:0])
    #   // C0
    #   2'b00: begin
    #     unique case (instr_i[15:13])
    #       3'b000: begin
    #         // c.addi4spn -> addi rd', x2, imm
    #         instr_o = {2'b0, instr_i[10:7], instr_i[12:11], instr_i[5],
    #                    instr_i[6], 2'b00, 5'h02, 3'b000, 2'b01, instr_i[4:2], {OPCODE_OP_IMM}};
    #         if (instr_i[12:5] == 8'b0)  illegal_instr_o = 1'b1;
    #       end

    #       3'b010: begin
    #         // c.lw -> lw rd', imm(rs1')
    #         instr_o = {5'b0, instr_i[5], instr_i[12:10], instr_i[6],
    #                    2'b00, 2'b01, instr_i[9:7], 3'b010, 2'b01, instr_i[4:2], {OPCODE_LOAD}};
    #       end

    #       3'b110: begin
    #         // c.sw -> sw rs2', imm(rs1')
    #         instr_o = {5'b0, instr_i[5], instr_i[12], 2'b01, instr_i[4:2],
    #                    2'b01, instr_i[9:7], 3'b010, instr_i[11:10], instr_i[6],
    #                    2'b00, {OPCODE_STORE}};
    #       end

    #       3'b001,
    #       3'b011,
    #       3'b100,
    #       3'b101,
    #       3'b111: begin
    #         illegal_instr_o = 1'b1;
    #       end

    #       default: begin
    #         illegal_instr_o = 1'b1;
    #       end
    #     endcase

a = bit(20)[3:4] 

SelfT = TypeVar('SelfT')

class bind[T](object):
    def __init__(self, c : Callable[[T],Dict[Any,Any]]):
        self._c = c
    def __call__(self, s) -> Dict[Any,Any]:
        return self._c(s)
    
#a = bind2(lambda s:{s.}, selfT=Self)

def field(rand=False, bind : Callable[[object],Dict[Any,Any]] = None):
    pass
    
    # @staticmethod
    # def __call__(rand=False, bind : Callable[[T],Dict[Any,Any]] = None):
    #     pass

    # """
    # Marks a plain data field
    # - rand -- Marks the field as being randomizable
    # - 
    # """
    # # TODO: 
    # return dc.field()

def input(*args, **kwargs):
    return dataclasses.field(default_factory=Input)

def output(*args, **kwargs):
    return dc.field(default_factory=Output)

def lock(*args, **kwargs):
    return dc.field(default_factory=Lock)

def share(*args, **kwargs):
    return dc.field(default_factory=Share)

def port():
    return dc.field()

def export(*args, bind=None, **kwargs):
    return dc.field(*args, **kwargs)

def process(T):
    return T

def reg(offset=0):
    return dc.field()
    pass

def const(**kwargs):
    return dc.field()

def sync(*args, clock=None, reset=None):
    # TODO: handle two forms
    if len(args) == 0:
        def __call__(T):
            Annotation.apply(T, AnnotationSync(clock=clock, reset=reset))
            return T
        return __call__
    else:
        Annotation.apply(args[0], AnnotationSync(clock=clock, reset=reset))
        return args[0]

# def action(*args, **kwargs): 
#     if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
#         # No-argument form
#         return ActionDecoratorImpl([], {})(args[0])
#     else:
#         # Argument form
#         return ActionDecoratorImpl(args, kwargs)
    
# def activity(*args, **kwargs):
#     if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
#         # No-argument form
#         return ActivityDecoratorImpl([], {})(args[0])
#     else:
#         return ActivityDecoratorImpl(args, kwargs)

# def component(*args, **kwargs):
#     if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
#         # No-argument form
#         return ComponentDecoratorImpl([], {})(args[0])
#     else:
#         return ComponentDecoratorImpl(args, kwargs)

def constraint(T):
    setattr(T, "__constraint__", True)
    return T
    
 # def constraint(*args, **kwargs):
# #     if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
# #         # No-argument form
# #         return ConstraintDecoratorImpl({})(args[0])
# #     else:
# #         return ConstraintDecoratorImpl(kwargs)

# def buffer(*args, **kwargs): 
#     if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
#         # No-argument form
#         return StructDecoratorImpl(StructKindE.Buffer, [], {})(args[0])
#     else:
#         return ActionDecoratorImpl(StructKindE.Buffer, args, kwargs)
    
# def resource(*args, **kwargs): 
#     if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
#         # No-argument form
#         return StructDecoratorImpl(StructKindE.Resource, [], {})(args[0])
#     else:
#         return StructDecoratorImpl(StructKindE.Resource, [], kwargs)
    
# def state(*args, **kwargs): 
#     if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
#         # No-argument form
#         return StructDecoratorImpl(StructKindE.State, {})(args[0])
#     else:
#         return ActionDecoratorImpl(StructKindE.State, kwargs)
    
# def stream(*args, **kwargs): 
#     if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
#         # No-argument form
#         return StructDecoratorImpl(StructKindE.Stream, {})(args[0])
#     else:
#         return ActionDecoratorImpl(StructKindE.Stream, kwargs)
    
# def struct(*args, **kwargs): 
#     if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
#         # No-argument form
#         return StructDecoratorImpl(StructKindE.Struct, [], {})(args[0])
#     else:
#         return ActionDecoratorImpl(StructKindE.Struct, args, kwargs)

# class exec(object):
#     @staticmethod
#     def body(*args, **kwargs):
#         if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
#             # No-argument form
#             return ExecDecoratorImpl(ExecKindE.Body, [], {})(args[0])
#         else:
#             return ExecDecoratorImpl(ExecKindE.Body, args, kwargs)
        
#     @staticmethod
#     def init_down(*args, **kwargs):
#         if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
#             # No-argument form
#             return ExecDecoratorImpl(ExecKindE.InitDown, [], {})(args[0])
#         else:
#             return ExecDecoratorImpl(ExecKindE.InitDown, args, kwargs)
        
#     @staticmethod
#     def init_up(*args, **kwargs):
#         if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
#             # No-argument form
#             return ExecDecoratorImpl(ExecKindE.InitUp, [], {})(args[0])
#         else:
#             return ExecDecoratorImpl(ExecKindE.InitUp, args, kwargs)
        
#     @staticmethod
#     def pre_solve(*args, **kwargs):
#         if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
#             # No-argument form
#             return ExecDecoratorImpl(ExecKindE.PreSolve, [], {})(args[0])
#         else:
#             return ExecDecoratorImpl(ExecKindE.PreSolve, args, kwargs)
        
#     @staticmethod
#     def post_solve(*args, **kwargs):
#         if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
#             # No-argument form
#             return ExecDecoratorImpl(ExecKindE.PostSolve, [], {})(args[0])
#         else:
#             return ExecDecoratorImpl(ExecKindE.PostSolve, args, kwargs)

# class extend(object):
#     @staticmethod
#     def action(target, *args, **kwargs):
#         return ExtendActionDecoratorImpl(target, args, kwargs)

#     @staticmethod
#     def component(target, *args, **kwargs):
#         return ExtendComponentDecoratorImpl(target, args, kwargs)

# class extern(object):

#     # TODO:    
#     @staticmethod
#     def action(*args, **kwargs):
#         raise NotImplementedError("extern.action not implemented")
#         if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
#             # No-argument form
#             return ExecDecoratorImpl(ExecKindE.PreSolve, {})(args[0])
#         else:
#             return ExecDecoratorImpl(ExecKindE.PreSolve, kwargs)

# def fn(*args, **kwargs): 
#     if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
#         # No-argument form
#         return FnDecoratorImpl(False, {})(args[0])
#     else:
#         return FnDecoratorImpl(False, kwargs)

# def import_fn(*args, **kwargs): 
#     if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
#         # No-argument form
#         return FnDecoratorImpl(True, {})(args[0])
#     else:
#         return FnDecoratorImpl(True, kwargs)
