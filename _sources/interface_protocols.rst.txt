.. _interface-protocols:

###################
Interface Protocols
###################

This guide explains **why** ``zdc.IfProtocol`` exists, **what** properties
it captures, and **how** those properties map to the RTL structures emitted
by the synthesizer.

.. contents:: On this page
   :depth: 3
   :local:

Why ``Callable`` Is Insufficient
=================================

Earlier Zuspec versions modelled cross-component method calls as plain
``Callable`` port annotations::

    dat: Callable[[], Awaitable[zdc.u32]] = zdc.port()

This works well for *ad-hoc* simulation but gives the synthesizer no
information beyond the argument and return types.  In hardware, two interfaces
that carry the same payload can require entirely different RTL structures
depending on timing and flow-control constraints:

* A RAM with a fixed 4-cycle read latency needs *no* handshake signals.
* A cache that can backpressure needs a ``req_ready`` signal.
* A DMA engine that issues multiple reads before waiting for any response
  needs an in-flight counter and a response FIFO.

``Callable`` cannot express any of these distinctions, so the synthesizer has
to guess — or refuse to proceed.

``IfProtocol`` solves this by letting the *designer* attach a small set of
named properties to the interface class.  The synthesizer then selects the
correct RTL template automatically.

Defining a Protocol
====================

Subclass ``zdc.IfProtocol`` and add keyword arguments to set properties.
Declare one or more ``async`` methods with type-annotated arguments and
return types; the body is always ``...``::

    import zuspec.dataclasses as zdc

    class RamIface(zdc.IfProtocol,
                   max_outstanding=1,
                   req_always_ready=True,
                   resp_always_valid=True,
                   fixed_latency=4):
        """Fixed-latency ROM read."""
        async def read(self, addr: zdc.u32) -> zdc.u32: ...

Use the class as a port type on a ``Component``::

    @zdc.dataclass
    class Controller(zdc.Component):
        rom: RamIface = zdc.port()

        @zdc.proc
        async def _run(self):
            data = await self.rom.read(0x1000)

Protocol Properties
====================

The table below lists every property, its default value, meaning, and the
RTL signal(s) it affects.

.. list-table::
   :header-rows: 1
   :widths: 22 10 68

   * - Property
     - Default
     - Meaning
   * - ``req_always_ready``
     - ``False``
     - The target *always* accepts a new request.  When ``True`` no
       ``req_ready`` signal is generated; the requester may send every cycle.
   * - ``req_registered``
     - ``False``
     - The request path passes through a register (one-cycle delay).  Emits
       an extra pipeline stage on the request path.
   * - ``resp_always_valid``
     - ``False``
     - The response is always valid on the wire — requires ``fixed_latency``
       to be set.  No ``resp_valid`` signal is generated.
   * - ``fixed_latency``
     - ``None``
     - If set to integer *N*, the response arrives exactly *N* cycles after
       the request without any flow-control signal.  Implies
       ``resp_always_valid=True``.
   * - ``resp_has_backpressure``
     - ``False``
     - The response channel can stall the sender.  Emits a ``resp_ready``
       signal.  Mutually exclusive with ``fixed_latency``.
   * - ``max_outstanding``
     - ``1``
     - Maximum number of simultaneous in-flight requests.  When > 1 the
       synthesizer generates an in-flight counter and possibly a response
       buffer (depending on ``in_order``).
   * - ``in_order``
     - ``True``
     - When ``True`` (with ``max_outstanding > 1``) responses arrive in the
       same order as requests — a depth-``max_outstanding`` FIFO is emitted.
       When ``False`` an out-of-order reorder buffer (ROB) is emitted
       instead.
   * - ``initiation_interval``
     - ``1``
     - Minimum number of cycles between successive requests.  Values > 1
       emit a down-counter gate on the request path.

Property Validation
--------------------

The metaclass checks illegal combinations at class-definition time:

* ``resp_always_valid=True`` requires ``fixed_latency`` to be set.
* ``fixed_latency`` and ``resp_has_backpressure=True`` are mutually
  exclusive.
* ``max_outstanding`` and ``initiation_interval`` must both be ≥ 1.

Per-Method Overrides with ``@zdc.call()``
------------------------------------------

When a single ``IfProtocol`` class declares multiple methods you can override
properties on individual methods using the ``@zdc.call()`` decorator::

    class MixedIface(zdc.IfProtocol, max_outstanding=4):
        async def load(self, addr: zdc.u32) -> zdc.u32: ...

        @zdc.call(max_outstanding=1)
        async def flush(self) -> None: ...

``flush`` is constrained to at most 1 outstanding call even though the
interface as a whole supports 4.

The Five Synthesis Scenarios
=============================

The synthesizer selects one of five RTL templates (Scenarios A–E) based on
the resolved property set.

Scenario A — Fixed Latency (no handshake)
------------------------------------------

**Trigger:** ``fixed_latency=N`` (implicitly ``resp_always_valid=True``).

Generated signals::

    req_addr  [W-1:0]   // request payload
    resp_data [W-1:0]   // response payload (valid N cycles later)

No ``req_ready``, ``req_valid``, ``resp_valid``, or ``resp_ready`` signals.
The synthesizer inserts an *N*-stage shift-register delay line on the data
path.

*Example:* a synchronous ROM or a pipelined multiplier with a known latency.

Scenario B — Basic Handshake (max_outstanding=1)
--------------------------------------------------

**Trigger:** ``max_outstanding=1``, ``fixed_latency=None``.

Generated signals::

    req_valid              // requester asserts while sending
    req_ready              // target asserts when it can accept
    req_payload [W-1:0]
    resp_valid             // target asserts with response
    resp_ready             // (only if resp_has_backpressure=True)
    resp_data   [W-1:0]

This is the simplest two-phase handshake, equivalent to a classic
valid/ready interface.

*Example:* a single-entry scratchpad or a register-mapped peripheral.

Scenario C — In-Order Multi-Outstanding
-----------------------------------------

**Trigger:** ``max_outstanding=N > 1``, ``in_order=True``.

Adds to Scenario B:

* An **in-flight counter** (``inflight_cnt``, *⌈log₂N⌉+1* bits) that gates
  ``req_valid`` when it reaches ``max_outstanding``.
* A **response FIFO** of depth ``max_outstanding`` to absorb responses that
  arrive before the consumer is ready.

*Example:* a DDR controller or AXI read channel where the slave returns
responses in address order.

Scenario D — Out-of-Order Multi-Outstanding
--------------------------------------------

**Trigger:** ``max_outstanding=N > 1``, ``in_order=False``.

Adds to Scenario C:

* A transaction **ID field** on the request (``req_id``, *⌈log₂N⌉* bits).
* A **reorder buffer** (ROB) indexed by ``req_id`` so responses can be
  matched to their callers regardless of arrival order.
* ``resp_id`` on the response path.

*Example:* an AXI4 master with multiple outstanding reads using ``ARID``/
``RID`` tagging.

Scenario E — Pipelined (initiation_interval > 1)
--------------------------------------------------

**Trigger:** ``initiation_interval=II > 1``.

Wraps any scenario above with a down-counter that blocks ``req_valid`` for
*II − 1* cycles after each accepted request.

*Example:* a floating-point unit that accepts a new operand every 3 cycles.

Choosing the Right Scenario
----------------------------

Use this decision tree:

1. Does the target always respond after a known fixed number of cycles?
   → Scenario A (``fixed_latency=N``).
2. Is only one request ever in flight at a time?
   → Scenario B (``max_outstanding=1``).
3. Multiple in flight, responses in order?
   → Scenario C (``max_outstanding=N``, ``in_order=True``).
4. Multiple in flight, responses may arrive out of order?
   → Scenario D (``in_order=False``).
5. Target needs a minimum gap between requests?
   → Add ``initiation_interval=II`` to any of the above.

Form A vs Form B
=================

The synthesizer recognizes two forms of protocol usage.

**Form B** (recommended) uses a dedicated ``IfProtocol`` class as the port
type.  All protocol metadata is in one place and reusable across components::

    class MemIface(zdc.IfProtocol, max_outstanding=4, in_order=True):
        async def read(self, addr: zdc.u32) -> zdc.u32: ...

    @zdc.dataclass
    class Core(zdc.Component):
        imem: MemIface = zdc.port()

**Form A** (legacy) inlines protocol information as a ``Callable`` without
properties, relying on defaults.  It is still supported for backward
compatibility but produces only Scenario B (or an error if the synthesizer
needs more information)::

    # Form A — no protocol properties, synthesizes as Scenario B only
    dat: Callable[[], Awaitable[zdc.u32]] = zdc.port()

See :doc:`migration_callable_to_protocol` for step-by-step instructions to
upgrade Form A ports to Form B.

.. seealso::

   :doc:`split_transactions` — ``zdc.Completion[T]``, ``zdc.spawn()``,
   and ``zdc.select()`` for multi-outstanding split-transaction patterns.

   :doc:`types` — Full API reference for all new protocol primitives.
