from typing import Self, Type, TypeVar
from .decorators import dataclass, field
from .component import Component
from .struct import Struct

CompT = TypeVar('CompT', bound=Component)

@dataclass
class Action[CompT](Struct):
    """
    Action-derived types 

    Valid fields
    - All Struct fields
    - Input / Output fields of Buffer, Stream, and State types
    - Lock / Share fields of Resource types
    Valid sub-regions
    - All Struct sub-regions
    - activity
    """
    comp : Type[CompT] = field()

@dataclass
class MyAction(Action[Component]):
    pass
