"""Edge detection awaitables for simulation.

Usage inside a ``@zdc.proc`` body::

    await zdc.negedge(lambda: self.rx)   # wait for rx to fall
    await zdc.posedge(lambda: self.clk)  # wait for clk to rise
    await zdc.edge(lambda: self.flag)    # wait for any transition
"""

import asyncio
from typing import Any, Callable


class _EdgeAwaitable:
    """Awaitable that resolves when a signal undergoes a specified transition.

    The signal is sampled via a callable (typically ``lambda: self.signal``)
    so that the current value can be re-read at each clock edge without
    capturing a stale snapshot at construction time.
    """

    def __init__(self, signal_fn: Callable[[], Any], edge_type: str) -> None:
        self._signal_fn = signal_fn
        self._edge_type = edge_type  # 'neg', 'pos', or 'any'

    def __await__(self):
        task = asyncio.current_task()
        cd = getattr(task, '_zdc_clock_domain', None) if task is not None else None
        if cd is None:
            raise RuntimeError(
                "await zdc.negedge/posedge/edge() called outside a @zdc.proc "
                "with a bound clock domain."
            )
        loop = asyncio.get_running_loop()
        prev = int(self._signal_fn())
        fut = loop.create_future()
        cd._edge_waiters.append((self._signal_fn, prev, self._edge_type, fut))
        yield from fut.__await__()
        return None


def negedge(signal_fn: Callable[[], Any]) -> _EdgeAwaitable:
    """Return an awaitable that resolves on the falling edge of *signal_fn()*.

    Args:
        signal_fn: Zero-argument callable that returns the current signal
                   value, e.g. ``lambda: self.rx``.
    """
    return _EdgeAwaitable(signal_fn, 'neg')


def posedge(signal_fn: Callable[[], Any]) -> _EdgeAwaitable:
    """Return an awaitable that resolves on the rising edge of *signal_fn()*.

    Args:
        signal_fn: Zero-argument callable that returns the current signal value.
    """
    return _EdgeAwaitable(signal_fn, 'pos')


def edge(signal_fn: Callable[[], Any]) -> _EdgeAwaitable:
    """Return an awaitable that resolves on any edge of *signal_fn()*.

    Args:
        signal_fn: Zero-argument callable that returns the current signal value.
    """
    return _EdgeAwaitable(signal_fn, 'any')
