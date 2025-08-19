import dataclasses as dc
from typing import Callable, ClassVar

@dc.dataclass
class Annotation(object):
    NAME : ClassVar[str] = "__zsp_annotation__"

    @classmethod
    def apply(cls, o, v):
        setattr(o, cls.NAME, v)
    pass

@dc.dataclass
class AnnotationSync(Annotation):
    clock : Callable
    reset : Callable
