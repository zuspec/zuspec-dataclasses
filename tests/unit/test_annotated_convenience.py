import dataclasses as dc
from typing import Annotated

class bit:
    """Creates Annotated[int, U(width)] for unsigned bit fields"""
    def __class_getitem__(cls, width: int):
        return Annotated[int, width]

class sint:
    """Creates Annotated[int, S(width)] for signed bit fields"""
    def __class_getitem__(cls, width: int):
        return Annotated[int, width]

@dc.dataclass
class MyC(object):
    a : bit[32] = dc.field()


