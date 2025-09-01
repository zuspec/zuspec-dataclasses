import abc
import dataclasses as dc
from typing import List

class DependencyProvider(abc.ABC): pass

class Pool[T](DependencyProvider): pass

class TrackingDependencyProvider[T](DependencyProvider):
    """
    Dependency provider that tracks its dependencies. 
    This is typically used by a component that must use
    dependency information to properly build itself.
    """

    @abc.abstractmethod
    def dependents(self) -> List[T]:
        """
        List of dependencies bound to this provider
        """
        pass

