import dataclasses as dc
from typing import ClassVar, Dict, Generic, Type
from abc import abstractmethod


class PortMeta(type):

    def __new__(cls, name, bases, attrs):
        return super().__new__(cls, name, bases, attrs)
    
    def __init__(self, name, bases, attrs):
        super().__init__(name, bases, attrs)
        self.type_m : Dict = {}
    
    def __getitem__(self, T):
        print("__getitem__: %s" % T)
        if T in self.type_m.keys():
            return self.type_m[T]
        else:
            def new(cls):
                print("Port.__new__: %s %s" % (cls, cls.Tp))
                return super().__new__(cls)
            def init(self):
                print("Port.__init__: %s %s" % (self, self.Tp))
                self.imp = None
            def call(self):
                print("__call__")

            t = type(T.__name__, (Port,), {
#                "__new__": new,
                "__init__": init,
                "__call__": call
            })
            setattr(t, "Tp", T)
            self.type_m[T] = t
            return t

class Port[T](metaclass=PortMeta):

    @abstractmethod
    def __call__(self) -> T:
        pass

# # Bundle is a collection of ports/exports
# class WishboneI():
#     valid : Output[bool]
#     ready : Input[bool]
#     pass

# class ReverseT(type):
#     def __new__(cls, name, bases, attrs):
#         return super().__new__(cls, name, bases, attrs)

#     def __getitem__(self, T : type):
#         pass


# class Reverse[T](metaclass=ReverseT):

#     def __class_getitem__(cls):
#         pass

#     pass

# WishboneIM=Reverse[WishboneI]

# class Api[T](ABC):

#     @abstractmethod
#     def put(self, val : T):
#         pass

#     @abstractmethod
#     def get(self) -> T:
#         pass

# class MyModule:
#     init_o : Port[WishboneI]
#     dat_o : Port[Api[int]]

#     def doit(self):
#         self.init_o().ready = 1
#         if self.init_o().valid:
#             pass

#         a = self.dat_o().get()
#         self.dat_o().put(5)

class Input(object):
    pass

class Output(object):
    pass
