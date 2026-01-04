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

