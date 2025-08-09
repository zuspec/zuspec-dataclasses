from typing import Generic
from abc import abstractmethod, ABC

class IPut[T](ABC):

    @abstractmethod
    def put(self, val : T): pass
