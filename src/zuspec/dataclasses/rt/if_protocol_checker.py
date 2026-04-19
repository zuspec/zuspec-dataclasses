"""``ProtocolChecker`` — Level 1 behavioral protocol enforcement wrapper.

Wraps an ``IfProtocol`` port to enforce protocol properties during Level 1
simulation.  At Level 0 the raw port is used directly (no wrapper).
"""
from __future__ import annotations

import asyncio
from typing import Any, List, Optional


class ProtocolChecker:
    """Wraps an IfProtocol port to enforce protocol properties at Level 1.

    Enforces:
    * ``max_outstanding`` — semaphore limits concurrent in-flight requests.
    * ``in_order``        — tracks completion order and emits a warning if
                            responses arrive out-of-order.

    Example::

        checker = ProtocolChecker(raw_port, props)
        result = await checker.call("read", addr=0x100)
    """

    def __init__(self, port: Any, properties: Any):
        """
        Args:
            port:       The raw IfProtocol port object.
            properties: An ``IfProtocolProperties`` IR dataclass (or duck-typed
                        object with the same attributes).
        """
        self._port = port
        self._props = properties
        self._semaphore = asyncio.Semaphore(properties.max_outstanding)
        self._in_flight: List[asyncio.Future] = []

    async def call(self, method_name: str, *args, **kwargs) -> Any:
        """Invoke ``method_name`` on the wrapped port with protocol enforcement."""
        await self._semaphore.acquire()

        order_token: Optional[asyncio.Future] = None
        if self._props.in_order:
            order_token = asyncio.get_event_loop().create_future()
            self._in_flight.append(order_token)

        try:
            method = getattr(self._port, method_name)
            result = await method(*args, **kwargs)
        finally:
            self._semaphore.release()

        if self._props.in_order and order_token is not None:
            self._check_order(order_token)

        return result

    def _check_order(self, token: asyncio.Future) -> None:
        """Warn if this call completed before an earlier outstanding call."""
        if token in self._in_flight:
            idx = self._in_flight.index(token)
            # All entries before idx should already be done if in-order holds
            for earlier in self._in_flight[:idx]:
                if not earlier.done():
                    import warnings
                    warnings.warn(
                        "ProtocolChecker: in_order=True violation — "
                        "a later request completed before an earlier one",
                        stacklevel=3,
                    )
                    break
            if not token.done():
                token.set_result(None)
            self._in_flight.remove(token)

    def __repr__(self):
        return (
            f"ProtocolChecker(port={self._port!r}, "
            f"max_outstanding={self._props.max_outstanding}, "
            f"in_order={self._props.in_order})"
        )
