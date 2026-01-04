import dataclasses as dc
from typing import Callable, Protocol, Tuple


class GetIF[T](Protocol):

    async def get(self) -> T: ...

    def try_get(self) -> Tuple[bool, T]: ...

class PutIF[T](Protocol):

    async def put(self, T): ...

    def try_put(self, T) -> bool: ...

class ReqRspIF[Treq,Trsp](PutIF[Treq],GetIF[Trsp]):
    pass

type Transport[Treq,Trsp] = Callable[[Treq],Trsp]


@dc.dataclass
class Channel[T](Protocol):
    put : PutIF = dc.field()
    get : GetIF = dc.field()

@dc.dataclass
class ReqRspChannel[Treq,Trsp](Protocol):
    init : ReqRspIF[Treq,Trsp] = dc.field()
    targ : ReqRspIF[Trsp,Treq] = dc.field()

