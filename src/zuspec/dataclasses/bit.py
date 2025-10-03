import dataclasses as dc
from typing import Dict

class BitMeta(type):
    """
    The BitMeta class is a constructor for Bit types.
    Bit[12], for example, produces a Bit type where
    W=12.
    """

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
                "W" : W
            })
            self.type_m[W] = t
            return t

class Bit(metaclass=BitMeta):
    """
    Variables of 'Bit' type represent unsigned W-bit values.
    The value of the variables is automatically masked. For 
    example, assigning 20 (b10100) to a 4-bit variable will 
    result in 4 (b0100) being stored in the variable.
    """
    W : int = 1

class Bits(metaclass=BitMeta):
    W : int = -1
