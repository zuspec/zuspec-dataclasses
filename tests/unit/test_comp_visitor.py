
import pytest
from typing import Type
import zuspec.dataclasses as zdc

import dataclasses

class Visitor(object):
    def visit(self, t : Type[zdc.Component]):
        self.visitComponent(t)

    def visitComponent(self, t : Type[zdc.Component]):
        # Visit all fields
        for field in dataclasses.fields(t):
            self.visitField(field.name, field.type, field)
        # Visit all constraint methods
        for name, attr in t.__dict__.items():
            if callable(attr) and getattr(attr, "__constraint__", False):
                self.visitConstraint(name, attr)

    def visitField(self, name, type, field_info):
        print(f"visitField: {name}, {type}, {field_info}")

    def visitConstraint(self, name, method):
        print(f"visitConstraint: {name}, {method}")

def test_elab_1():

    @zdc.dataclass
    class MyComp(zdc.Component):
        f1 : int = zdc.field(default=1)
        f2 : int = zdc.field(default=2)

        @zdc.constraint
        def my_c(self):
            self.f1 == self.f2

    v = Visitor()
    v.visit(MyComp)
