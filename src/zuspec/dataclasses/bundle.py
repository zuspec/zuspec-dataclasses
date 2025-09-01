from typing import Annotated, Type, TypeVar
from .decorators import dataclass

@dataclass
class Bundle(object):
    """
    A bundle type collects one or more ports, exports,
    inputs, outputs, or bundles. 

    Bundle fields are created with field(). Bundle-mirror
    fields are created with mirror() or field(mirror=True)

    A bundle field can be connected to a mirror field. 
    - Bundle
    - Bundle Mirror
    - Bundle Monitor (all are inputs / exports)
    """
    pass

#BundleT=TypeVar('BundleT', bound=Bundle)

#class Mirror[BundleT](Annotated[Type[BundleT], "is mirror"]): pass

# class MirrorMeta[BundleT](type):

#     def __getitem__(self, t : BundleT) -> BundleT:
#         pass

# @dataclass
# class Mirror[BundleT](metaclass=MirrorMeta[BundleT]):
#     pass

