
import dataclasses as dc
import enum
from typing import Callable, Optional

class ExecKind(enum.Enum):
    Sync = enum.auto()
    Proc = enum.auto()

@dc.dataclass
class Exec(object):
    method : Callable = dc.field()
    kind : ExecKind = dc.field()
    bind : Optional[Callable] = dc.field(default=None)
