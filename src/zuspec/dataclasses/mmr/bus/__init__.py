"""Bus protocol adapters for abstract register files."""
from .base import BusPort
from .passthrough import PassthroughPort

__all__ = ['BusPort', 'PassthroughPort']
