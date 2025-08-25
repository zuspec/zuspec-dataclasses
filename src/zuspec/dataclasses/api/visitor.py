import dataclasses as dc
from typing import Callable, ClassVar, Dict, Type
from ..annotation import Annotation
from ..component import Component
from ..ports import Input, Output
from ..struct import Struct

@dc.dataclass
class Visitor(object):
    _type_m : Dict[Type,Callable] = dc.field(default_factory=dict)
    _field_factory_m : Dict[Type,Callable] = dc.field(default_factory=dict)

    def __post_init__(self):
        self._type_m = {
            Component : self.visitComponentType
        }
        self._field_factory_m = {
            Input : self.visitInput,
            Output : self.visitOutput
        }

    def visit(self, t):
        found = False
        for base_t,method in self._type_m.items():
            if issubclass(t, base_t):
                method(t)
                found = True
                break
        if not found:
            raise Exception("Unsupported class %s" % str(type(t)))

    def visitComponentType(self, t):
        self.visitStructType(t)
        pass

    def visitStructType(self, t : Struct):
        for f in dc.fields(t):
            self._dispatchField(f)
        
        for f in dir(t):
            o = getattr(t, f)
            if callable(o) and hasattr(o, Annotation.NAME):
                self.visitExec(f, o)
                print("Found")

    def visitExec(self, name, m):
        pass

    def _dispatchField(self, f : dc.Field):
        if f.default_factory in self._field_factory_m.keys():
            self._field_factory_m[f.default_factory](f)
        else:
            self.visitField(f)

    def visitField(self, f : dc.Field):
        pass

    def visitInput(self, f : dc.Field):
        self.visitField(f)
        pass

    def visitOutput(self, f : dc.Field):
        self.visitField(f)
        pass
