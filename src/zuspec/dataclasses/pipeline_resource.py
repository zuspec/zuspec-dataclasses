"""Pipeline resource and proxy classes.

A :class:`PipelineResource` models an address-tagged hazard-tracked resource
(e.g. a register file or memory bank).  Subscripting it with an address
returns a :class:`_ResourceProxy` that carries both the resource reference
and the specific address, for use with the hazard operations on
:class:`~zuspec.dataclasses.pipeline_ns._PipelineNamespace`.

Example::

    rf = zdc.pipeline.resource(32, lock=zdc.BypassLock())

    # Inside a pipeline stage body:
    zdc.pipeline.reserve(rf[rd_addr])
    val = await zdc.pipeline.block(rf[rs1_addr])
    zdc.pipeline.write(rf[rd_addr], val)
    zdc.pipeline.release(rf[rd_addr])
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pipeline_locks import HazardLock


class PipelineResource:
    """Address-tagged hazard tracker.

    Args:
        size: Address space size (e.g. 32 for a 32-entry register file).
        lock: :class:`~zuspec.dataclasses.pipeline_locks.HazardLock` instance
              controlling the hazard resolution strategy.  Defaults to a
              :class:`~zuspec.dataclasses.pipeline_locks.QueueLock`.
    """

    def __init__(self, size: int, *, lock: "HazardLock | None" = None) -> None:
        from .pipeline_locks import QueueLock
        self._size = size
        self._lock = lock if lock is not None else QueueLock()

    @property
    def size(self) -> int:
        """Number of distinct addresses in this resource."""
        return self._size

    @property
    def lock(self) -> "HazardLock":
        """The hazard lock strategy in use."""
        return self._lock

    def __getitem__(self, addr) -> "_ResourceProxy":
        """Return a bound (resource, address) proxy for hazard operations.

        Args:
            addr: The address within this resource's address space.
        """
        return _ResourceProxy(resource=self, addr=addr)

    def __repr__(self) -> str:  # pragma: no cover
        return f"PipelineResource(size={self._size}, lock={self._lock!r})"


class _ResourceProxy:
    """Bound ``(resource, address)`` pair consumed by hazard operations.

    Obtained by subscripting a :class:`PipelineResource`:
    ``self.rf[addr]`` → ``_ResourceProxy(resource=self.rf, addr=addr)``.
    """

    __slots__ = ("resource", "addr")

    def __init__(self, resource: PipelineResource, addr) -> None:
        self.resource = resource
        self.addr = addr

    def __repr__(self) -> str:  # pragma: no cover
        return f"_ResourceProxy(resource={self.resource!r}, addr={self.addr!r})"
