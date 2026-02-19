from __future__ import annotations
import asyncio
import dataclasses as dc
from typing import List, cast
from ..types import ClaimPool, Claim

@dc.dataclass
class ListClaimPool[T](ClaimPool[T]):
    """Claim pool operating on a list of resources"""
    resources: List[T] = dc.field()
    # TODO: Must have access to a timing domain to support proper round-robin
    # TODO: Specify allocation scheme -- make pluggable?
    _ev: asyncio.Event = dc.field(default_factory=asyncio.Event)
    _waiters: int = dc.field(default=0)
    _state: List[int] = dc.field(default_factory=list)
    _count: List[int] = dc.field(default_factory=list)

    def __post_init__(self):
        for _ in range(len(self.resources)):
            self._state.append(0)
            self._count.append(0)
        pass

    @dc.dataclass
    class ListClaim(Claim[T]):
        _p: ListClaimPool[T] = dc.field()
        _id: int = dc.field()

        @property
        def id(self) -> int:
            return self._id

        @property
        def t(self) -> T:
            return self._p.resources[self._id]

        @t.setter
        def t(self, v: T):
            self._p.resources[self._id] = v

    async def lock(
            self,
            claim_id: Optional[Any] = None,
            filter: Optional[Callable[[T, int], bool]] = None) -> Claim[T]:
        while True:
            # Select a matching resource that is available
            for i,r in enumerate(self.resources):
                if self._state[i] == 0 and (filter is None or filter(r, i)):
                    self._state[i] = 1
                    return ListClaimPool[T].ListClaim(self, i)
            # Otherwise, wait for a change in state
            self._waiters += 1
            await self._ev.wait()
            self._waiters -= 1
            if self._waiters == 0:
                self._ev.clear()

    async def share(
            self,
            claim_id: Optional[Any] = None,
            filter: Optional[Callable[[T, int], bool]] = None) -> Claim[T]:
        while True:
            # Select a matching resource that is available
            for i,r in enumerate(self.resources):
                if self._state[i] in (0,2) and (filter is None or filter(r, i)):
                    self._state[i] = 2
                    self._count[i] += 1
                    return ListClaimPool[T].ListClaim(self, i)
            # Otherwise, wait for a change in state
            self._waiters += 1
            await self._ev.wait()
            self._waiters -= 1
            if self._waiters == 0:
                self._ev.clear()
    
    def drop(
            self,
            claim: Claim[T]):
        lc: ListClaimPool[T].ListClaim = cast(ListClaimPool[T].ListClaim, claim)
        if self._state[lc.id] == 1:
            # Lock
            self._state[lc.id] = 0
            self._ev.set()
        elif self._state[lc.id] == 2:
            self._count[lc.id] -= 1
            if self._count[lc.id] <= 0:
                self._count[lc.id] = 0
                self._state[lc.id] = 0
                self._ev.set()
        else:
            raise Exception("Resource %d state mismatch" % lc.id)
