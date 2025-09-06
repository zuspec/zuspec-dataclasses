import dataclasses as dc
from typing import Callable, ClassVar, Dict, Type
from ..annotation import Annotation
from ..bit import Bit
from ..component import Component
from ..struct import Struct

@dc.dataclass
class Visitor(object):
    _type_m : Dict[Type,Callable] = dc.field(default_factory=dict)

    def __post_init__(self):
        self._type_m = {
            Component : self.visitComponentType
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

    def _visitFields(self, t : Struct):
        print("--> visitFields")
        for f in dc.fields(t):
            print("Field: %s" % f.name)
            self._dispatchField(f)
        print("<-- visitFields")

    def _dispatchField(self, f : dc.Field):
        if f.default_factory is not None:
            if issubclass(f.default_factory, input):
                self.visitInputField(f)
            elif issubclass(f.default_factory, Output):
                self.visitOutputField(f)
        else:
            if f.type == int:
                self.visitIntField(f)
            elif f.type == str:
                self.visitStrField(f)
            elif callable(f.type):
                if issubclass(f.type, Bit):
                    visitBitField(f)
                print("class")
            else:
                print("Error: unhandled: %s" % str(f.type))

    def visitStructType(self, t : Struct):
        self._visitFields(t)
        
        for f in dir(t):
            o = getattr(t, f)
            if callable(o) and hasattr(o, Annotation.NAME):
                print("Found")

    def visitField(self, f : dc.Field): pass

    def visitInputField(self, f : dc.Field):
        self.visitField(f)

    def visitOutputField(self, f : dc.Field):
        self.visitField(f)

    def visitIntField(self, f : dc.Field):
        self.visitField(f)

    def visitStrField(self, f : dc.Field):
        self.visitField(f)

    def visitInput(self, f : dc.Field):
        pass
