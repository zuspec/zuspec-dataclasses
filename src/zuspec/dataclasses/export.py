import dataclasses as dc
from abc import abstractmethod, ABC

@dc.dataclass
class Export[T](ABC):

    @abstractmethod
    def __call__(self) -> T: pass
