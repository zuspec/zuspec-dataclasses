############
Core Types
############

The ``zuspec.dataclasses`` module provides core types for modeling 
hardware-centric systems. These types form the user-facing API for 
defining components, memory, registers, and time-based behaviors.

*********
Component
*********

The ``Component`` class is the primary structural building block in Zuspec.
Components form hierarchical trees and can contain fields, ports, exports,
processes, and bindings.

.. code-block:: python3

    import zuspec.dataclasses as zdc

    @zdc.dataclass
    class MyComponent(zdc.Component):
        clock : zdc.uint1_t = zdc.input()
        reset : zdc.uint1_t = zdc.input()
        
        @zdc.process
        async def run(self):
            while True:
                await self.wait(zdc.Time.ns(10))
                print(f"Time: {self.time()}")

Properties
==========

* ``name`` - The instance name of the component
* ``parent`` - Reference to the parent component (None for root)

Methods
=======

* ``wait(amt: Time)`` - Suspend execution for the specified time
* ``time() -> Time`` - Return the current simulation time
* ``shutdown()`` - Cancel all running process tasks
* ``__bind__() -> Dict`` - Override to specify port/field bindings

Lifecycle
=========

1. Component and child fields are constructed
2. ``__comp_build__`` initializes the component tree (depth-first)
3. ``__bind__`` mappings are applied
4. Processes start when simulation begins (via ``wait()``)

*************
Time & Timing
*************

Time
====

The ``Time`` class represents simulation time with various unit granularities.

.. code-block:: python3

    import zuspec.dataclasses as zdc

    # Create time values using factory methods
    t1 = zdc.Time.ns(100)    # 100 nanoseconds
    t2 = zdc.Time.us(5)      # 5 microseconds  
    t3 = zdc.Time.ms(1)      # 1 millisecond
    t4 = zdc.Time.s(0.5)     # 0.5 seconds
    t5 = zdc.Time.ps(250)    # 250 picoseconds
    t6 = zdc.Time.fs(1000)   # 1000 femtoseconds
    t7 = zdc.Time.delta()    # Zero-time delta

TimeUnit
========

Enumeration of supported time units:

* ``TimeUnit.S`` - Seconds
* ``TimeUnit.MS`` - Milliseconds  
* ``TimeUnit.US`` - Microseconds
* ``TimeUnit.NS`` - Nanoseconds
* ``TimeUnit.PS`` - Picoseconds
* ``TimeUnit.FS`` - Femtoseconds

Timebase Protocol
=================

The ``Timebase`` protocol defines the interface for simulation time control:

* ``wait(amt: Time)`` - Suspend until time elapses
* ``after(amt: Time, call: Callable)`` - Schedule callback
* ``time() -> Time`` - Get current simulation time

*************
Integer Types
*************

Zuspec provides width-specified integer types using Python's ``Annotated`` type.

Predefined Types
================

Unsigned integers:

* ``uint1_t`` through ``uint8_t`` - 1 to 8 bit unsigned
* ``uint16_t``, ``uint32_t``, ``uint64_t`` - 16, 32, 64 bit unsigned

Signed integers:

* ``int8_t``, ``int16_t``, ``int32_t``, ``int64_t``

Width Specifiers
================

For custom widths, use ``U(width)`` for unsigned or ``S(width)`` for signed:

.. code-block:: python3

    from typing import Annotated
    import zuspec.dataclasses as zdc

    # Custom 24-bit unsigned integer
    uint24_t = Annotated[int, zdc.U(24)]
    
    # Custom 12-bit signed integer
    int12_t = Annotated[int, zdc.S(12)]

    @zdc.dataclass
    class MyStruct(zdc.PackedStruct):
        field_a : uint24_t = zdc.field()
        field_b : int12_t = zdc.field()

************
PackedStruct
************

``PackedStruct`` represents bit-packed data structures where fields are 
packed contiguously in memory.

.. code-block:: python3

    import zuspec.dataclasses as zdc

    @zdc.dataclass
    class StatusReg(zdc.PackedStruct):
        valid : zdc.uint1_t = zdc.field()
        ready : zdc.uint1_t = zdc.field()
        count : zdc.uint8_t = zdc.field()
        data  : zdc.uint16_t = zdc.field()

PackedStruct instances support conversion to/from integers, enabling
direct register read/write operations.

************
Memory Types
************

Memory[T]
=========

``Memory[T]`` provides direct memory access with element-typed storage.

.. code-block:: python3

    import zuspec.dataclasses as zdc

    @zdc.dataclass
    class MemoryController(zdc.Component):
        # 1024-element memory of 32-bit values
        mem : zdc.Memory[zdc.uint32_t] = zdc.field(size=1024)

Methods:

* ``read(addr: int) -> T`` - Read element at address
* ``write(addr: int, data: T)`` - Write element to address

RegFile
=======

``RegFile`` is the base class for register file definitions.

.. code-block:: python3

    import zuspec.dataclasses as zdc

    @zdc.dataclass
    class ControlRegs(zdc.RegFile):
        status : zdc.Reg[zdc.uint32_t] = zdc.field()
        control : zdc.Reg[zdc.uint32_t] = zdc.field()
        data : zdc.Reg[zdc.uint32_t] = zdc.field()

Reg[T]
======

``Reg[T]`` represents an individual register with async access methods.

.. code-block:: python3

    # Read and write registers
    value = await regs.status.read()
    await regs.control.write(0x01)

    # Conditional wait
    await regs.status.when(lambda v: v & 0x01)

Methods:

* ``read() -> T`` - Async read of register value
* ``write(val: T)`` - Async write to register
* ``when(cond: Callable[[T], bool])`` - Wait for condition

AddressSpace
============

``AddressSpace`` provides a software-centric view of memory, mapping
multiple storage regions into a unified address space.

.. code-block:: python3

    import zuspec.dataclasses as zdc

    @zdc.dataclass
    class SoC(zdc.Component):
        mem : zdc.Memory[zdc.uint32_t] = zdc.field(size=0x10000)
        regs : ControlRegs = zdc.field()
        aspace : zdc.AddressSpace = zdc.field()

        def __bind__(self): return {
            self.aspace.mmap : (
                zdc.At(0x0000_0000, self.mem),
                zdc.At(0x1000_0000, self.regs),
            )
        }

At
==

The ``At`` helper specifies an element's location in an address space:

.. code-block:: python3

    zdc.At(offset=0x1000_0000, element=self.regs)

MemIF Protocol
==============

``MemIF`` defines the byte-level memory access interface:

* ``read8/16/32/64(addr)`` - Read sized values
* ``write8/16/32/64(addr, data)`` - Write sized values

AddrHandle
==========

``AddrHandle`` implements ``MemIF`` and provides a pointer-like abstraction
for accessing an address space.

***************
Synchronization
***************

Lock
====

``Lock`` provides a mutex for coordinating access to shared resources.

.. code-block:: python3

    import zuspec.dataclasses as zdc

    @zdc.dataclass  
    class SharedResource(zdc.Component):
        mutex : zdc.Lock = zdc.field()
        
        @zdc.process
        async def worker(self):
            async with self.mutex:
                # Critical section
                pass

Methods:

* ``acquire()`` - Async acquire lock
* ``release()`` - Release lock
* ``locked() -> bool`` - Check if locked

Supports async context manager (``async with``).

**********
Pool Types
**********

Pool[T,Tc]
==========

``Pool[T,Tc]`` manages a collection of resources with matching and selection.

.. code-block:: python3

    pool.add(item)           # Add item to pool
    pool.get(index)          # Get item by index
    pool.match(ctx, cond)    # Find matching item
    pool.selector = fn       # Set selection function

ClaimPool[T,Tc]
===============

``ClaimPool`` extends Pool with exclusive/shared locking:

* ``lock(i)`` - Acquire item for read-write access
* ``share(i)`` - Acquire item for read-only access
* ``drop(i)`` - Release item

********************
Interface Protocols
********************

The following types implement the interface-protocol system introduced in
version 2026.1.  See :doc:`interface_protocols` and :doc:`split_transactions`
for conceptual background.

IfProtocol
==========

``zdc.IfProtocol`` is the base class for typed interface definitions.

.. code-block:: python3

    class MyIface(zdc.IfProtocol,
                  max_outstanding=4,
                  in_order=True,
                  req_always_ready=False,
                  resp_has_backpressure=False):
        async def read(self, addr: zdc.u32) -> zdc.u32: ...
        async def write(self, addr: zdc.u32, data: zdc.u32) -> None: ...

Class keyword arguments (protocol properties):

* ``req_always_ready`` *(bool, default False)* — target always accepts
  requests; suppresses ``req_ready`` signal.
* ``req_registered`` *(bool, default False)* — request path passes through a
  register (one-cycle delay).
* ``resp_always_valid`` *(bool, default False)* — response always valid;
  requires ``fixed_latency`` to be set.
* ``fixed_latency`` *(int or None, default None)* — response arrives exactly
  *N* cycles after request; suppresses all handshake signals.
* ``resp_has_backpressure`` *(bool, default False)* — emits ``resp_ready``
  signal; mutually exclusive with ``fixed_latency``.
* ``max_outstanding`` *(int, default 1)* — maximum simultaneous in-flight
  requests.
* ``in_order`` *(bool, default True)* — responses arrive in request order;
  emits a response FIFO when ``max_outstanding > 1``.
* ``initiation_interval`` *(int, default 1)* — minimum cycles between
  requests.

Class methods:

* ``_get_properties() -> dict`` — returns the resolved properties dict.
* ``_get_ir_properties() -> IfProtocolProperties`` — returns the IR dataclass
  instance used by the synthesizer.

.. code-block:: python3

    @zdc.dataclass
    class Core(zdc.Component):
        imem: MyIface = zdc.port()

        @zdc.proc
        async def _run(self):
            data = await self.imem.read(0x1000)

``@zdc.call()`` Decorator
--------------------------

Overrides protocol properties on an individual method::

    class Iface(zdc.IfProtocol, max_outstanding=4):
        async def load(self, addr: zdc.u32) -> zdc.u32: ...

        @zdc.call(max_outstanding=1)
        async def flush(self) -> None: ...

SimpleCall
==========

``zdc.SimpleCall[ArgType, RetType]`` is a convenience alias that creates a
single-method ``IfProtocol`` subclass with a ``__call__`` method.

.. code-block:: python3

    # Single argument
    dat: zdc.SimpleCall[zdc.u32, zdc.u32] = zdc.port()
    result = await self.dat(value)   # invokes __call__

    # Multiple arguments: SimpleCall[Arg0, Arg1, ..., Ret]
    op:  zdc.SimpleCall[zdc.u32, zdc.u32, zdc.u64] = zdc.port()
    out = await self.op(a, b)

``SimpleCall`` supports the same class-keyword protocol properties as
``IfProtocol`` via subclassing::

    class FastDat(zdc.SimpleCall[zdc.u32, zdc.u32],
                  fixed_latency=2,
                  req_always_ready=True):
        pass

Completion[T]
=============

``zdc.Completion[T]`` is a one-shot result synchronization token.  Create one
per in-flight transaction; the producer calls ``set()``; the consumer
``await``s it.

.. code-block:: python3

    done: zdc.Completion[zdc.u32] = zdc.Completion[zdc.u32]()

    # Producer (may run in a spawned coroutine):
    done.set(42)           # non-blocking; must be called exactly once

    # Consumer:
    result = await done    # suspends until set() is called
    assert done.is_set     # True after set() returns

Methods and properties:

* ``set(value: T) -> None`` — delivers the result; non-blocking; call exactly
  once.
* ``__await__()`` — suspend until ``set()`` has been called; returns the
  value.
* ``is_set: bool`` — ``True`` after ``set()`` has been called.

At simulation time backed by ``asyncio.Future``.
At synthesis mapped to a response register / signal bundle.

Queue[T]
========

``zdc.Queue[T]`` is a bounded FIFO for intra-component inter-process
communication.  Declare with ``zdc.queue(depth=N)`` as the initializer.

.. code-block:: python3

    @zdc.dataclass
    class MyComp(zdc.Component):
        _req_q: zdc.Queue[LoadReq] = zdc.queue(depth=4)

``zdc.queue(depth=N)`` factory parameters:

* ``depth`` *(int, required)* — maximum number of items; must be ≥ 1.
* ``element_type`` *(type, optional)* — element type hint for the synthesizer.

``Queue`` methods (all on the instance):

* ``await put(item: T) -> None`` — block until space is available, then
  enqueue ``item``.
* ``await get() -> T`` — block until an item is available, then dequeue and
  return it.
* ``qsize() -> int`` — current number of items in the queue.
* ``full() -> bool`` — ``True`` when occupancy equals depth.
* ``empty() -> bool`` — ``True`` when the queue contains no items.

At simulation time backed by ``asyncio.Queue(maxsize=depth)``.
At synthesis lowered to a synchronous RTL FIFO with depth parameter.

zdc.spawn()
===========

``zdc.spawn(coro)`` starts a coroutine concurrently without suspending the
caller.

.. code-block:: python3

    handle = zdc.spawn(self._do_read(addr, done))
    # caller continues immediately
    await handle.join()   # wait for completion (optional)

Parameters:

* ``coro`` *(Coroutine)* — the coroutine to run concurrently.

Returns a ``SpawnHandle``.

At simulation time wraps ``asyncio.create_task()``.
At synthesis lowers to a slot-array FSM bounded by the ``max_outstanding``
of the ``IfProtocol`` port called inside the coroutine.

SpawnHandle
-----------

* ``await join() -> None`` — suspend the caller until the spawned coroutine
  completes.
* ``await cancel() -> None`` — request cancellation and wait for the
  coroutine to stop.  RTL cancellation is not yet supported.

zdc.select()
============

``zdc.select(*queues_with_tags)`` blocks until any of the supplied queues has
an item ready.

.. code-block:: python3

    item, tag = await zdc.select(
        (self._load_q,  "load"),
        (self._store_q, "store"),
    )

Parameters:

* ``*queues_with_tags`` — one or more ``(queue, tag)`` pairs.
* ``priority`` *(str, keyword, default ``'left_to_right'``)* — arbitration
  policy:

  * ``'left_to_right'`` — leftmost non-empty queue wins.
  * ``'round_robin'`` — priority rotates after each selection.

Returns ``(item, tag)`` where ``tag`` identifies which queue yielded.

At simulation time uses ``asyncio.wait(..., return_when=FIRST_COMPLETED)``.
At synthesis lowers to a priority arbiter or round-robin arbiter.

