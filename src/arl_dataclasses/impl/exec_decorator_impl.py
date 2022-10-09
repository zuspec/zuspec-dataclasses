'''
Created on Mar 19, 2022

@author: mballance
'''
import typeworks
from .exec_type import ExecType
from .exec_kind_e import ExecKindE
from .ctor import Ctor

class ExecDecoratorImpl(typeworks.RegistrationDecoratorBase):
    
    def __init__(self, kind, args, kwargs):
        super().__init__(ExecType, args, kwargs)
        self._kind = kind

    def register_decl(self, T):
        print("Register exec: %s %s" % (T.__name__, hasattr(T, "__annotations__")))
        print("  %s" % str(T.__annotations__))
        # lines = inspect.getsource(T)
        # print(lines)

        # file = inspect.getfile(T)

        # module = T.__module__
        # print("module: %s %s" % (str(module), file))

        # with open(file, "r") as fp:
        #     tree = ast.parse(fp.read())
        # print("tree: %s" % str(tree))

        for key,value in getattr(T, "__annotations__", {}).items():
            print("Key: %s ; %s" % (key, str(value)))
        typeworks.DeclRgy.push_decl(
            ExecType, 
            ExecType(self._kind, T), 
            typeworks.enclosing_scopename(T))
