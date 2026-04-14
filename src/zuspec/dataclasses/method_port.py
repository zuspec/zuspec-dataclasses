"""Method ports for the async pipeline DSL.

Method ports provide explicit, synthesis-visible ingress and egress channels
for pipeline components, replacing the implicit pattern of reading/writing
component fields directly inside stage bodies.

Canonical pipeline shape::

    @zdc.pipeline(clock_domain=lambda s: s.cd)
    async def _execute(self):
        async with zdc.pipeline.stage() as IF:
            a = await self.a_in.get()       # explicit GET
            b = await self.b_in.get()

        async with zdc.pipeline.stage() as COMPUTE:
            result = a + b

        async with zdc.pipeline.stage() as WB:
            await self.result_out.put(result)  # explicit PUT

Level semantics
---------------
* **Level 0 (functional):** :meth:`InPort.get` pops from an internal asyncio
  queue fed by the testbench via :meth:`InPort.drive`.  :meth:`OutPort.put`
  appends to an internal list readable by :meth:`OutPort.collect`.  Neither
  call ever blocks due to backpressure.
* **Level 1 (behavioral timing):** The runtime may replace the backing queue
  with a timed channel that models valid/ready handshaking.
* **RTL synthesis:** ``SVEmitPass`` maps each :class:`InPort` to a
  ``valid_i`` / ``ready_o`` / ``data_i`` bundle and each :class:`OutPort` to
  ``valid_o`` / ``ready_i`` / ``data_o``.

Testbench API example::

    pipe = MyPipeline()

    # Feed inputs
    for a, b in operand_pairs:
        pipe.a_in.drive(a)
        pipe.b_in.drive(b)

    asyncio.run(pipe.wait(Time(TimeUnit.NS, 50)))

    results = pipe.result_out.collect()
    assert results == expected
"""

from __future__ import annotations

import asyncio
from typing import Any, Generic, List, Optional, TypeVar

T = TypeVar("T")


# ---------------------------------------------------------------------------
# InPort
# ---------------------------------------------------------------------------

class InPort(Generic[T]):
    """Pipeline ingress method port.

    Attach to a component field using :func:`in_port`::

        @zdc.dataclass
        class Adder(zdc.Component):
            a_in: zdc.InPort[zdc.u32] = zdc.in_port()
            b_in: zdc.InPort[zdc.u32] = zdc.in_port()

    Within a pipeline stage body, call ``await self.a_in.get()`` to consume
    one token.  In a testbench, call ``self.a_in.drive(val)`` to enqueue a
    token.

    Attributes:
        _queue:    Internal asyncio.Queue backing get()/drive().
        _width:    Bit-width hint for synthesis (None = infer from type param).
        port_name: Field name on the parent component (set by descriptor).
    """

    def __init__(self, width: Optional[int] = None) -> None:
        self._queue: asyncio.Queue = asyncio.Queue()
        self._width = width
        self.port_name: str = ""
        # Marker for IR extraction
        self._zdc_in_port: bool = True

    async def get(self) -> T:
        """Consume one token from the ingress channel.

        Suspends until a token is available (i.e., until :meth:`drive` has
        been called).  In the pipeline runtime the suspension is automatically
        charged as stall cycles to the current stage.

        Returns:
            The next token value.
        """
        return await self._queue.get()

    def drive(self, value: T) -> None:
        """Enqueue *value* as the next ingress token.

        Call this from the testbench (before or during simulation) to supply
        data to the pipeline.

        Args:
            value: The token to enqueue.
        """
        self._queue.put_nowait(value)

    def qsize(self) -> int:
        """Return the number of tokens currently queued."""
        return self._queue.qsize()

    def __repr__(self) -> str:
        return f"InPort(name={self.port_name!r}, queued={self.qsize()})"


# ---------------------------------------------------------------------------
# OutPort
# ---------------------------------------------------------------------------

class OutPort(Generic[T]):
    """Pipeline egress method port.

    Attach to a component field using :func:`out_port`::

        @zdc.dataclass
        class Adder(zdc.Component):
            result: zdc.OutPort[zdc.u32] = zdc.out_port()

    Within a pipeline stage body (the last stage), call
    ``await self.result.put(val)`` to emit a token.  In a testbench, call
    ``self.result.collect()`` to retrieve all emitted tokens.

    Attributes:
        _results:  List of emitted tokens.
        _event:    asyncio.Event signalled on each put() for waiters.
        _width:    Bit-width hint for synthesis.
        port_name: Field name on the parent component (set by descriptor).
    """

    def __init__(self, width: Optional[int] = None) -> None:
        self._results: List[T] = []
        self._event: asyncio.Event = asyncio.Event()
        self._width = width
        self.port_name: str = ""
        # Marker for IR extraction
        self._zdc_out_port: bool = True

    async def put(self, value: T) -> None:
        """Emit *value* to the egress channel.

        At Level 0 this always succeeds immediately (no backpressure).
        The value is appended to the internal result list and the event is
        signalled so any :meth:`wait_for_output` coroutine can wake up.

        Args:
            value: The token to emit.
        """
        self._results.append(value)
        self._event.set()
        self._event.clear()
        await asyncio.sleep(0)  # yield so waiters can observe the event

    def collect(self, *, clear: bool = True) -> List[T]:
        """Return all tokens emitted so far.

        Args:
            clear: If ``True`` (default), clear the internal list after
                   returning.  Set to ``False`` to peek without consuming.

        Returns:
            List of emitted token values in emission order.
        """
        results = list(self._results)
        if clear:
            self._results.clear()
        return results

    def count(self) -> int:
        """Return the number of tokens emitted so far."""
        return len(self._results)

    async def wait_for_output(self, n: int = 1, *, timeout: float = 1.0) -> List[T]:
        """Wait until at least *n* tokens have been emitted, then return them.

        Primarily a testbench helper for sequencing assertions.

        Args:
            n:       Minimum number of output tokens to wait for.
            timeout: Maximum real-time seconds to wait (raises
                     :class:`asyncio.TimeoutError` on expiry).

        Returns:
            All tokens emitted so far (may be more than *n*).
        """
        deadline = asyncio.get_event_loop().time() + timeout
        while len(self._results) < n:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise asyncio.TimeoutError(
                    f"OutPort: timed out waiting for {n} outputs"
                    f" (got {len(self._results)})"
                )
            try:
                await asyncio.wait_for(
                    self._wait_event(), timeout=remaining
                )
            except asyncio.TimeoutError:
                break
        return self.collect(clear=False)

    async def _wait_event(self) -> None:
        self._event.set()
        self._event.clear()
        await asyncio.sleep(0)

    def __repr__(self) -> str:
        return f"OutPort(name={self.port_name!r}, emitted={self.count()})"


# ---------------------------------------------------------------------------
# Descriptors — used by factory functions
# ---------------------------------------------------------------------------

class _InPortDescriptor:
    """Descriptor that lazily creates one :class:`InPort` per instance."""

    _zdc_in_port_field: bool = True

    def __init__(self, width: Optional[int] = None) -> None:
        self._width = width
        self._attr_name: str = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr_name = name

    def __get__(self, obj, objtype=None) -> "InPort | _InPortDescriptor":
        if obj is None:
            return self
        inst_key = f"_inp_inst_{self._attr_name}"
        port = obj.__dict__.get(inst_key)
        if port is None or not isinstance(port, InPort):
            port = InPort(width=self._width)
            port.port_name = self._attr_name
            # Re-create event in the current event loop if needed
            try:
                port._queue = asyncio.Queue()
            except RuntimeError:
                pass
            obj.__dict__[inst_key] = port
        return port

    def __set__(self, obj, value) -> None:
        # When @zdc.dataclass calls __init__, it may call __set__ with the
        # descriptor instance as the "default" value.  Ignore that; __get__
        # will create the real InPort lazily.
        if isinstance(value, _InPortDescriptor):
            return
        inst_key = f"_inp_inst_{self._attr_name}"
        if isinstance(value, InPort):
            value.port_name = self._attr_name
        obj.__dict__[inst_key] = value


class _OutPortDescriptor:
    """Descriptor that lazily creates one :class:`OutPort` per instance."""

    _zdc_out_port_field: bool = True

    def __init__(self, width: Optional[int] = None) -> None:
        self._width = width
        self._attr_name: str = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr_name = name

    def __get__(self, obj, objtype=None) -> "OutPort | _OutPortDescriptor":
        if obj is None:
            return self
        inst_key = f"_outp_inst_{self._attr_name}"
        port = obj.__dict__.get(inst_key)
        if port is None or not isinstance(port, OutPort):
            port = OutPort(width=self._width)
            port.port_name = self._attr_name
            obj.__dict__[inst_key] = port
        return port

    def __set__(self, obj, value) -> None:
        # When @zdc.dataclass calls __init__, it may call __set__ with the
        # descriptor instance as the "default" value.  Ignore that.
        if isinstance(value, _OutPortDescriptor):
            return
        inst_key = f"_outp_inst_{self._attr_name}"
        if isinstance(value, OutPort):
            value.port_name = self._attr_name
        obj.__dict__[inst_key] = value


# ---------------------------------------------------------------------------
# Public factory functions
# ---------------------------------------------------------------------------

def in_port(width: Optional[int] = None) -> "_InPortDescriptor":
    """Declare an :class:`InPort` field on a component.

    Analogous to ``zdc.input()`` but for method-port ingress.

    Args:
        width: Optional explicit bit-width for synthesis.  If omitted, width
               is inferred from the type annotation by the synthesis pass.

    Example::

        @zdc.dataclass
        class Adder(zdc.Component):
            a_in: zdc.InPort[zdc.u32] = zdc.in_port()
    """
    return _InPortDescriptor(width=width)


def out_port(width: Optional[int] = None) -> "_OutPortDescriptor":
    """Declare an :class:`OutPort` field on a component.

    Analogous to ``zdc.output()`` but for method-port egress.

    Args:
        width: Optional explicit bit-width for synthesis.

    Example::

        @zdc.dataclass
        class Adder(zdc.Component):
            result: zdc.OutPort[zdc.u32] = zdc.out_port()
    """
    return _OutPortDescriptor(width=width)
