from .decorators import dataclass
from .struct import Struct

@dataclass
class Component(Struct):
    """
    Component classes are structural in nature. 
    The lifecycle of a component tree is as follows:
    - The root component and fields of component type are constructed
    - The 'init_down' method is invoked in a depth-first manner
    - The 'init_up' method is invoked
    """

    def build(self): pass

