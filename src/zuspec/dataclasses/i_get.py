from typing import Generic
from abc import abstractmethod, ABC

class IGet[T](ABC):

    @abstractmethod
    def Get(self) -> T: pass
