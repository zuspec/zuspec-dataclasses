import abc
import dataclasses as dc
from typing import Callable, Dict, Awaitable, Type, dataclass_transform

@dc.dataclass
class IPut[T]():
    put : Callable[[Type[T]], Awaitable] = dc.field()

@dc.dataclass
class IGet[T]():
    get : Callable[[], Awaitable[T]] = dc.field()

