import dataclasses as dc
from typing import Dict

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


class Bit(metaclass=BitMeta):
    T : int = 1
    pass