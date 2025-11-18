from ..types import Class

class Object(Class):
    pass

class Phase(Object):
    pass

class Component(Object):

    def build_phase(self, phase : Phase): ...

    def connect_phase(self, phase : Phase): ...

    pass
