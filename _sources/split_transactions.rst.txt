.. _split-transactions:

####################
Split Transactions
####################

A *split transaction* separates the moment a request is sent from the moment
its response is consumed.  This guide explains how ``zdc.Completion[T]``,
``zdc.Queue[T]``, ``zdc.spawn()``, and ``zdc.select()`` work together to
model — and synthesize — split-transaction hardware.

.. contents:: On this page
   :depth: 3
   :local:

The Blocking vs Split-Transaction Mismatch
==========================================

A simple ``await self.port.read(addr)`` call is *blocking*: the coroutine
suspends until the response arrives.  This is fine for Scenario A/B ports
(single outstanding request), but it becomes a performance bottleneck for
Scenario C/D ports where the hardware can hold multiple requests in flight
simultaneously.

Consider a prefetch buffer that should keep 4 reads outstanding::

    # Naive — only 1 read in flight at a time
    for addr in addresses:
        data = await self.mem.read(addr)   # stalls here waiting for response
        process(data)

The fix is to *decouple* the request from the response using
``zdc.Completion[T]`` and ``zdc.spawn()``.

``zdc.Completion[T]`` — One-Shot Result Token
==============================================

A ``Completion[T]`` is a typed, one-shot future.  It has three operations:

* **Create:** ``done = zdc.Completion[T]()`` — allocates the token.
* **Set:**    ``done.set(value)`` — delivers the result; non-blocking.
* **Await:**  ``result = await done`` — suspends the caller until the result
  is available.

``set()`` is always non-blocking to avoid deadlock: the coroutine that calls
``set()`` (the *producer*) must never block on the *consumer's* readiness.

API summary::

    done: zdc.Completion[zdc.u32] = zdc.Completion[zdc.u32]()

    # Producer side (runs in a spawned coroutine):
    done.set(42)           # delivers value — never blocks

    # Consumer side:
    result = await done    # suspends until set() is called
    assert done.is_set     # True after set() returns

At simulation time a ``Completion`` is backed by an ``asyncio.Future``.
At synthesis the IR extractor maps it to a response register / signal bundle
in the generated RTL.

``zdc.Queue[T]`` — Bounded FIFO
================================

``zdc.Queue[T]`` is an ``asyncio.Queue``-backed bounded FIFO used to carry
data *between* processes inside a component.  Its depth is set at declaration
time::

    @zdc.dataclass
    class MyComp(zdc.Component):
        _req_q: zdc.Queue[LoadReq] = zdc.queue(depth=4)

Operations::

    await self._req_q.put(item)   # blocks when full
    item = await self._req_q.get()  # blocks when empty
    self._req_q.qsize()           # current occupancy
    self._req_q.full()            # True if occupancy == depth
    self._req_q.empty()           # True if occupancy == 0

At synthesis the FIFO is lowered to a synchronous RTL FIFO with the given
depth parameter.

``zdc.spawn()`` — Fire-and-Forget
===================================

``zdc.spawn(coro)`` starts ``coro`` concurrently *without suspending the
caller*.  It returns a ``SpawnHandle``::

    handle = zdc.spawn(self._do_read(addr, done))
    # caller continues immediately

``SpawnHandle`` methods::

    await handle.join()    # wait until the coroutine finishes
    await handle.cancel()  # request cancellation and wait

At simulation time ``spawn()`` wraps ``asyncio.create_task()``.  At synthesis
the synthesizer bounds concurrent spawns to the ``max_outstanding`` value of
the ``IfProtocol`` port called inside the spawned coroutine and emits a
slot-array FSM.

``zdc.select()`` — First Non-Empty Queue
=========================================

``zdc.select()`` waits until any of a set of queues has an item ready and
returns both the item and the tag that was paired with the queue::

    item, tag = await zdc.select(
        (self._load_q,  "load"),
        (self._store_q, "store"),
    )
    if tag == "load":
        ...handle load result...
    else:
        ...handle store acknowledgement...

The ``priority`` keyword controls which queue wins when multiple are
non-empty:

* ``'left_to_right'`` (default) — leftmost argument wins.
* ``'round_robin'`` — priority rotates after each selection to prevent
  starvation.

::

    item, tag = await zdc.select(
        (self._q0, 0), (self._q1, 1),
        priority='round_robin',
    )

At synthesis ``select()`` lowers to a priority arbiter or a round-robin
arbiter, respectively.

The LSU Pattern — Step by Step
================================

The Load-Store Unit (``examples/06_lsu/lsu.py``) is the canonical example.
Here is the key design decomposed into steps.

Step 1 — Declare typed ports
-----------------------------

::

    class AxiReadIface(zdc.IfProtocol,
                       max_outstanding=4,
                       in_order=True):
        async def read(self, addr: zdc.u64, len_: zdc.u8) -> zdc.u64: ...

    class LoadCmdIface(zdc.IfProtocol, max_outstanding=1):
        async def load(self, addr: zdc.u64, size: zdc.u8) -> zdc.u64: ...

Step 2 — Add an internal queue
--------------------------------

The queue carries in-progress results from the spawned reader back to the
main process::

    _load_q: zdc.Queue[zdc.u64] = zdc.queue(depth=4)

Step 3 — Accept commands and spawn readers
-------------------------------------------

The handler process accepts each load command and spawns a sub-coroutine to
issue the AXI read::

    @zdc.proc
    async def _load_handler(self):
        while True:
            addr = ...           # receive load command
            zdc.spawn(self._do_axi_read(addr))

Step 4 — Spawned coroutine sends result to queue
-------------------------------------------------

::

    async def _do_axi_read(self, addr: zdc.u64):
        data = await self.axi_r.read(addr, 8)
        await self._load_q.put(data)   # non-blocking relative to response

Step 5 — Drain results with select
------------------------------------

A separate drain process pulls items from whichever queue is ready::

    @zdc.proc
    async def _drain(self):
        while True:
            data, tag = await zdc.select(
                (self._load_q,  "load"),
                (self._store_q, "store"),
            )
            ...forward data to caller...

Deadlock Avoidance
===================

The rule is:

    **``Completion.set()`` and ``Queue.put()`` must never block on the
    result consumer.**

If the spawned coroutine tries to call ``await done`` itself *and* the main
process never reads from the queue that delivers ``done``, you have a
deadlock.  The design pattern that avoids this is:

1. The spawned coroutine calls ``done.set(value)`` (non-blocking).
2. The main process calls ``result = await done`` (blocking only on the token,
   not on the spawned coroutine's progress).

Or using a queue:

1. The spawned coroutine calls ``await q.put(item)`` — which *can* block if
   the queue is full.
2. Keep the queue depth ≥ ``max_outstanding`` to ensure the producer never
   stalls waiting for the consumer.

``spawn()`` Semantics Across Abstraction Levels
================================================

.. list-table::
   :header-rows: 1
   :widths: 15 42 43

   * - Level
     - Behavior
     - Notes
   * - L0 Python
     - ``asyncio.create_task()``
     - Standard cooperative multitasking; tasks run on the asyncio event loop.
   * - L1 C runtime
     - Cooperative thread in the C coroutine scheduler
     - Uses ``zdc_spawn()`` from the C runtime; no preemption.
   * - RTL (synthesis)
     - Slot-array FSM with ``max_outstanding`` slots
     - Each slot holds state for one in-flight transaction; the FSM allocates
       a free slot on each ``spawn()`` and frees it on completion.

.. seealso::

   :doc:`interface_protocols` — Protocol properties and synthesis scenarios.

   :doc:`migration_callable_to_protocol` — Upgrading existing ``Callable``
   ports to ``IfProtocol``.

   :doc:`types` — API reference for all new primitives.
