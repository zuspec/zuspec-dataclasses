import dataclasses as dc
from typing import Dict, Generic, TypeVar, Literal, Type

class BitMeta(type):

    def __new__(cls, name, bases, attrs):
        return super().__new__(cls, name, bases, attrs)
    
    def __init__(self, name, bases, attrs):
        super().__init__(name, bases, attrs)
        self.type_m : Dict = {}
    
    def __getitem__(self, W : int):
        if W in self.type_m.keys():
            return self.type_m[W]
        else:
            t = type("bit[%d]" % W, (Bit,), {
                "T" : W
            })
            self.type_m[W] = t
            return t

T = TypeVar('T')

class Bit[T]: pass

class Int[T]: pass

#    T : int = 1

#    def __class_getitem__(cls, W : int) -> 'Bit[T]':
#        return "abc"
#        return cls
#        pass
#    pass


#W = TypeVar('W')

#def bit_t(W : int) -> _GenericA[Bit[T]]:
#    return Bit[Literal[W]]

#def int_t(W : int) -> Int:
#    return Int[Literal[W]]

class Bits():
    pass

class IntVal():
    pass

class BitVal(int):
    def __new__(cls, v : int, w : int):
        ret = super().__new__(cls, v)
        setattr(ret, "W", w)
        return ret
    def __getitem__(self, v):
        return 5
    
    def __add__(self, rhs):
        pass
    
v = BitVal(5, 16)
v += 5

def bv(v : int, w : int=1) -> BitVal:
    return BitVal(v, w)

a = bv(5,32)

def iv(): pass

uint64_t = Bit[Literal[64]]
#int64_t = Int[Literal[64]]
