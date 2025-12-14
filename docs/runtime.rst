####################################
Runtime Implementation (Developer)
####################################

The ``zuspec.dataclasses.rt`` module provides the pure-Python runtime 
implementation of Zuspec semantics. This module is primarily of interest 
to developers extending or integrating Zuspec.

**********
ObjFactory
**********

``ObjFactory`` is responsible for creating runtime instances of Zuspec types.
It handles component construction, field initialization, and binding resolution.

.. code-block:: python3

    from zuspec.dataclasses.rt import ObjFactory

    # Get the singleton factory instance
    factory = ObjFactory.inst()

Key Methods
===========

``mkComponent(cls, **kwargs) -> Component``
    Creates a runtime component instance. Automatically called when
    instantiating a Component subclass.

``mkRegFile(cls, **kwargs) -> RegFile``
    Creates a standalone register file instance.

Component Lifecycle
===================

When a component is instantiated, the factory orchestrates:

1. **Construction** - ``__new__`` intercepts and delegates to factory
2. **__comp_init__** - Wrapper around dataclass ``__init__``
3. **__comp_build__** - Recursive tree initialization:
   
   - Creates ``CompImplRT`` for each component
   - Sets timebase on root component
   - Discovers ``@process`` decorated methods
   - Initializes Memory, RegFile, and AddressSpace fields
   - Applies ``__bind__`` mappings

4. **Validation** - Top-level ports must be bound
5. **Process Start** - Processes start lazily when ``wait()`` is called

Binding System
==============

The factory uses proxy objects to capture binding relationships:

``BindPath``
    Represents a path in the binding system (e.g., ``self.p.prod``)

``BindProxy``
    Proxy object that records attribute access during ``__bind__`` evaluation

``InterfaceImpl``
    Dynamic object that holds bound methods for exports/ports

********
Timebase
********

``Timebase`` implements synthetic simulation time using an event queue.

.. code-block:: python3

    from zuspec.dataclasses.rt import Timebase

    tb = Timebase()
    
    # In async context
    await tb.wait(Time.ns(100))  # Wait 100ns
    tb.after(Time.us(1), callback)  # Schedule callback
    current = tb.time()  # Get current time

Internal Representation
=======================

Time is tracked internally in femtoseconds for maximum precision.
The event queue uses a min-heap for efficient event scheduling.

Key Methods
===========

``wait(amt: Time)``
    Suspend calling coroutine until specified time elapses.
    Creates a future and adds it to the event queue.

``after(amt: Time, call: Callable)``
    Schedule a callback to be invoked at a future time.

``advance() -> bool``
    Advance simulation to next event and wake waiters.
    Returns True if more events remain.

``run_until(amt: Time)``
    Run simulation until specified time, then return.
    Main simulation loop driver.

``stop()``
    Stop the simulation loop.

Properties
==========

``current_time: int``
    Current simulation time in femtoseconds.

``time() -> Time``
    Current time as a Time object (nanoseconds).

***********
CompImplRT
***********

``CompImplRT`` is the runtime implementation backing each Component instance.
It manages processes, timebase inheritance, and simulation control.

.. code-block:: python3

    # Accessed via component._impl (internal use)
    comp._impl.name       # Instance name
    comp._impl.parent     # Parent component
    comp._impl.timebase() # Get timebase (inherits from parent)

Key Methods
===========

``add_process(name, proc)``
    Register a ``@process`` decorated method.

``start_processes(comp)``
    Start all registered processes for a component.

``start_all_processes(comp)``
    Recursively start processes in the component tree.

``set_timebase(tb)``
    Set the timebase for this component (root only).

``timebase() -> Timebase``
    Get timebase, inheriting from parent if not set locally.

``wait(comp, amt)``
    Wait implementation. If simulation not running, starts it.

``shutdown()``
    Cancel all running process tasks.

********
MemoryRT
********

``MemoryRT`` provides the runtime implementation of ``Memory[T]``.
Uses sparse dictionary storage for efficiency.

.. code-block:: python3

    from zuspec.dataclasses.rt import MemoryRT

    mem = MemoryRT(_size=1024, _width=32, _element_type=int)
    mem.write(0, 0xDEADBEEF)
    val = mem.read(0)

Properties
==========

* ``_size`` - Number of elements
* ``_width`` - Bits per element
* ``_element_type`` - Python type of elements
* ``_data`` - Sparse storage dictionary

Methods
=======

``read(addr) -> T``
    Read element at address. Returns 0 for unwritten locations.

``write(addr, data)``
    Write element to address. Value masked to element width.

**********
RegFileRT
**********

``RegFileRT`` provides the runtime implementation of ``RegFile``.
Manages a collection of registers with address-based access.

.. code-block:: python3

    from zuspec.dataclasses.rt import RegFileRT, RegRT

    regfile = RegFileRT()
    reg = RegRT(_value=0, _width=32)
    regfile.add_register("status", reg, offset=0)

Key Methods
===========

``add_register(name, reg, offset)``
    Add a register at the specified byte offset.

``read(addr) -> int``
    Read register at byte offset.

``write(addr, data)``
    Write register at byte offset.

Properties
==========

* ``size`` - Total size in bytes
* ``width`` - Access width (32 bits)

*****
RegRT
*****

``RegRT`` implements individual register behavior with async access.

.. code-block:: python3

    reg = RegRT(_value=0, _width=32, _element_type=MyPackedStruct)
    
    value = await reg.read()   # Returns unpacked struct if applicable
    await reg.write(0x1234)    # Accepts int or PackedStruct

PackedStruct Support
====================

When ``_element_type`` is a ``PackedStruct``:

* ``read()`` unpacks the integer value into struct fields
* ``write()`` accepts either int or struct, packing as needed

**************
AddressSpaceRT
**************

``AddressSpaceRT`` implements address space with memory mapping.

.. code-block:: python3

    from zuspec.dataclasses.rt import AddressSpaceRT, MemoryRT

    aspace = AddressSpaceRT()
    mem = MemoryRT(_size=4096, _width=32, _element_type=int)
    aspace.add_mapping(0x0000, mem)

    val = await aspace.read(0x100, 4)  # Read 4 bytes at 0x100
    await aspace.write(0x100, 0x1234, 4)  # Write 4 bytes

Key Methods
===========

``add_mapping(base_addr, storage)``
    Map storage (MemoryRT or RegFileRT) at base address.

``read(addr, size) -> int``
    Async read from mapped storage.

``write(addr, data, size)``
    Async write to mapped storage.

Storage Resolution
==================

The ``_find_storage()`` method locates the appropriate storage
for an address, returning the storage object and offset within it.
Raises ``RuntimeError`` for unmapped addresses or cross-boundary accesses.

************
AddrHandleRT
************

``AddrHandleRT`` implements the ``MemIF`` protocol for an address space.

.. code-block:: python3

    from zuspec.dataclasses.rt import AddrHandleRT

    handle = aspace.base  # Get handle from AddressSpace
    
    val = await handle.read32(0x1000)
    await handle.write32(0x1000, 0xABCD)

Provides convenience methods for sized accesses:
``read8``, ``read16``, ``read32``, ``read64``,
``write8``, ``write16``, ``write32``, ``write64``

