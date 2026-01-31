##################
Abstraction Levels
##################

========
Overview
========

ZuSpec-dataclasses models organize device interfaces across three key abstraction areas,
each serving different modeling and verification needs.

.. image:: design_abstraction.png

1. **Logical Interface** - How software sees and interacts with the device

   * Operation level: High-level operations (e.g., "start DMA transfer")
   * MMIO level: Register-based control and status visibility

2. **Physical Interface** - How the rest of the design interacts with the device

   * Operation level: High-level operations (e.g., "start DMA transfer")
   * MMIO: Memory-mapped register transactions
   * TLM: Transaction-level modeling (bus protocols)
   * Protocol: Pin-level signaling and timing

3. **Internal Implementation** - How the device implements its core algorithm

   * Algorithmic: Functional behavior with or without timing
   * Cycle-accurate: Detailed microarchitectural implementation
   * Register-Transfer Level (RTL): Synthesizable implementation

These definitions extend to the system level as well:

.. image:: system_abstraction.png


A primary difference between device and system view is more diversity in the
abstraction levels employed. For example, an RTL level of abstraction might be
employed for a key device within the system, while the rest is implemented 
at the algorithmic level. This enables the full system to be simulated more
quickly, while preserving accuracy within the target device.


==================
Logical Interface
==================

The logical interface captures how the environment (typically software) interacts 
with a device. There are two key abstraction levels in play here:

Operation Level
===============

The operation level focuses on key device operations exposed as async methods,
representing the driver-level view of the device.

**Key characteristics:**

* Implements device operations as async methods
* Effectively driver-level abstraction
* Hides register-level details behind operation semantics
* For devices supporting independent concurrent operations, group related
  operations into Protocol classes

**Example: Operation interface (generic device)**

.. code-block:: python

   from typing import Protocol
   
   class DeviceOperations(Protocol):
       async def configure(self, addr: int, size: int) -> bool:
           """Configure device parameters"""
           ...
           
       async def start(self) -> bool:
           """Start device operation"""
           ...
           
       async def wait_complete(self) -> bool:
           """Wait for operation completion"""
           ...

Operations-Level Implementation Pattern
========================================

For behavioral models implementing an operations-level interface, follow
this pattern:

**Key Principles:**

1. **Synchronous Operations:** Operations complete immediately (no background processes)
2. **Protocol Interfaces:** Define operations as Protocol classes for type safety
3. **Separation:** Keep interface definitions separate from implementation
4. **Direct References:** Use direct interface references for external connections

**Implementation Pattern:**

.. code-block:: python

    from typing import Protocol
    
    # 1. Define operations interface (in separate file/module)
    class DeviceOperationsIF(Protocol):
        async def configure(self, addr: int, size: int) -> bool:
            """Configure device for operation"""
            ...
            
        async def start(self) -> bool:
            """Start the operation"""
            ...
    
    # 2. Define external interfaces needed
    class MemoryIF(Protocol):
        async def read(self, addr: int) -> int: ...
        async def write(self, addr: int, data: int) -> None: ...
    
    # 3. Implement component
    @zdc.dataclass
    class Device(zdc.Component):
        regs: DeviceRegs = zdc.field()
        _mem_if: MemoryIF = None  # Set via setup()
        ops: DeviceOperationsIF = zdc.export()
        
        async def configure(self, addr: int, size: int) -> bool:
            """Implementation of configure operation"""
            # Validate parameters
            if addr & 0x3 != 0:  # Check alignment
                return False
            
            # Configure via registers
            await self.regs.addr.write(addr)
            await self.regs.size.write(size)
            return True
            
        async def start(self) -> bool:
            """Implementation of start operation"""
            # Set status to active
            await self.regs.status.write(ACTIVE)
            
            # Perform operation immediately (behavioral model)
            addr = await self.regs.addr.read()
            data = await self._mem_if.read(addr)
            # ... complete operation ...
            
            # Set completion status
            await self.regs.status.write(COMPLETE)
            return True
    
    # 4. Parent component provides memory interface
    @zdc.dataclass
    class System(zdc.Component):
        device: Device = zdc.field()
        memory: Memory = zdc.field()
        
        def __bind__(self):
            return {
                # Bind parent ports to external interfaces
                # Child interfaces set up via setup()
            }
        
        def setup(self):
            """Call after binding to initialize child interfaces"""
            self.device._mem_if = self.memory.mem_if

**Usage Pattern:**

.. code-block:: python

    @zdc.dataclass
    class Top(zdc.Component):
        system: System = zdc.field()
        
        async def run(self):
            # Initialize interfaces after binding
            self.system.setup()
            
            # Use operations interface
            result = await self.system.device.configure(0x1000, 64)
            assert result == True
            
            result = await self.system.device.start()
            assert result == True

**Note:** This pattern is appropriate when you need high-level driver-like
operations without cycle-accurate timing. For models requiring concurrent
background activity, use ``@zdc.process`` methods instead.

MMIO Level
==========

The MMIO level focuses on memory-mapped registers and events, providing
register-based control and visibility into device state.

**Key characteristics:**

* Interface is the register file and associated events
* Operation-level methods are typically implemented in terms of this interface
* Captures interrupt protocols through event abstractions
* Memory-based descriptors are implied but not explicitly modeled

**Core components:**

* **Register files** (``zdc.RegFile``): Collections of memory-mapped registers
* **Events** (``zdc.Event``): Logical events like interrupts, completions, errors
* **Protocol** (``Protocol``): Grouping of related registers and events

**Example: Device MMIO interface**

.. code-block:: python

   @zdc.dataclass
   class DeviceRegs(zdc.RegFile):
       addr: zdc.Reg[zdc.u32]       # Address register
       size: zdc.Reg[zdc.u32]       # Size register  
       control: zdc.Reg[zdc.u8]     # Control register (start, stop, etc.)
       status: zdc.Reg[zdc.u8]      # Status register (busy, error, done)
   
   @zdc.dataclass
   class DeviceMmio(Protocol):
       regs: DeviceRegs             # Register file
       complete: zdc.Event          # Completion event
       error: zdc.Event             # Error event


====================
Physical Interface
====================

The physical interface describes how the rest of the design interacts with the device
at various levels of implementation detail.

Operation Level
===============

Early in the design cycle, it is common make the device's physical interface the same
as the logical interface. This is because the internals of the device are often 
implemented in terms of operations.

MMIO Level
==========

Device views intended for use by software often directly expose a MMIO physical
interface. This allows software emulation frameworks (e.g. QEMU) to directly
interact with the device.

TLM Level
=========

Transaction-level modeling provides a higher-level abstraction of bus interactions,
focusing on the transfer of data rather than signal-level details.

**Key characteristics:**

* Abstract transaction passing instead of cycle-by-cycle bus activity
* Faster simulation performance
* Suitable for system-level verification and performance analysis
* Common for virtual prototyping and software development

Protocol Level
==============

Protocol-level modeling captures pin-accurate signaling and timing relationships
between the device and other hardware components.

**Key characteristics:**

* Models actual hardware signals and their timing
* Captures protocol-specific handshaking (e.g., AXI, AHB, APB)
* Used for detailed hardware verification
* Includes clock-accurate behavior

==========================
Internal Implementation
==========================

The internal implementation models describe how the device realizes its functionality,
from algorithmic behavior to cycle-accurate microarchitecture.

Algorithmic Level
=================

Algorithmic modeling captures the functional behavior of the device with timing
characteristics but without detailed cycle-by-cycle implementation.

**Key characteristics:**

* Functional correctness with approximate timing
* Models what the device does, not how it's implemented
* Suitable for performance modeling and early software development
* Can be refined to more detailed implementations

**Example use cases:**

* Golden reference models for verification
* Performance estimation
* Algorithm validation
* Early software/firmware development

Cycle-Accurate Level
====================

Cycle-accurate modeling provides detailed microarchitectural implementation,
capturing behavior at individual clock cycle boundaries.

**Key characteristics:**

* Clock-cycle accurate state transitions
* Models pipeline stages, arbitration, and resource conflicts
* Captures detailed timing and performance characteristics
* Used for RTL correlation and detailed performance analysis

**Design considerations:**

* Operation granularity: How frequently is the block evaluated?
  
  * At operational boundaries (coarse-grained)
  * At implementation boundaries (fine-grained)
  * Multiple levels of detail may coexist

* Timing assumptions: What timing guarantees are provided?
  
  * Cycle boundaries
  * Pipeline depth
  * Resource availability

Register-Transfer Level (RTL)
=============================

RTL modeling provides a synthesizable description of design behavior that
can be taken directly to synthesis.

