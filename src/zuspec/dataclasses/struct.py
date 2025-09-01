import abc
from typing import Dict, Optional, Type
from .decorators import dataclass

@dataclass
class StructPacked(object):
    """
    StructPacked types are fixed-size data structures. 
    Fields may only be of a fixed size. 

    Valid sub-regions
    - constraint
    - pre_solve / post_solve
    """
    pass

@dataclass
class Struct(object):
    """
    Struct types are data structures that may contain
    variable-size fields. 

    Valid sub-regions
    - constraint
    - pre_solve / post_solve
    - method
    """

    # @abc.abstractmethod
    # def bind[T](self, t : T):
    #             t : Type[T], 
    #             init : Optional[Dict]=None,
    #             bind : Optional[Dict]=None) -> T:
    #     """
    #     Public API
    #     Applies service Creates a new instance of the specified class.
    #     - Resolves service claims relative to the context
    #       object and any bind specifications.
    #     """
    #     pass

    pass
