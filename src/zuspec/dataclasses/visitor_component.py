import dataclasses as dc
from typing import Type
from .component import Component

@dc.dataclass
class VisitorComponent(object):

    def visit(self, c : Type[Component]):

    pass