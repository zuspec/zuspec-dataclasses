from .decorators import dataclass
from .struct import Struct

@dataclass
class Component(Struct):

    def init_down(self): pass

    def init_up(self): pass

    pass
