'''
Created on Mar 19, 2022

@author: mballance
'''
import dataclasses as dc
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

def dataclass(cls, **kwargs):
    return dc.dataclass(cls, **kwargs)

def field(*args, **kwargs):
    return dc.field(*args, **kwargs)

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
