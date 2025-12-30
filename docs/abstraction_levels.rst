##################
Abstraction Levels
##################

Software Interface: Operation
=============================

* Focuses on key device operations.
* Implements those operations as async methods
* Effectively driver-level
* In cases where the hardware supports independent concurrent operation,
  create 'Protocol'-class groupings.

Software Interface: MMIO
========================

* Focuses on memory and registers
* Ideally, the operation level methods end up being implemented in terms of this interface

* Interface is the register file. Memory-based descriptors are considered implied
  * Actually, may need register file and notification (ie interrupt)
  * Use 'wait-for'?
  * Must effectively capture an interrupt protocol - ISR logic?
  * Only one listener at a time -> runtime error checked

  * Can a coroutine be converted to event-driven?

Event Test: Consider a software interface

The Interface *becomes* the PSS component

Public Interface: Test Scenario

Public Interface: Action

Real-World Interface: How does the outside world interact with us?

Hierarchical Organization of MMIO Interfaces
=============================================

When creating MMIO-level models, organize related registers and events together
using hierarchical Protocol classes. This creates cohesive interfaces where
functionality is grouped logically rather than flattened into a single structure.

Key Principles
--------------

1. **Group related functionality**: Keep registers and events for the same logical
   unit together in a Protocol class

2. **Respect device architecture**: If the hardware has multiple identical channels,
   units, or ports, create a Protocol class representing one instance

3. **Separate global from per-unit**: Global control registers should be separate
   from per-unit (per-channel, per-port) registers

4. **Co-locate registers and events**: Events should be in the same Protocol as the
   registers that configure and report them

Anti-Pattern: Flat Structure
-----------------------------

**❌ WRONG: Flattened registers with separated events**

.. code-block:: python

   @zdc.dataclass
   class DeviceRegs(zdc.RegFile):
       """All registers in one flat structure"""
       global_csr : zdc.Reg[GlobalCSR] = zdc.field()
       ch0_csr : zdc.Reg[ChannelCSR] = zdc.field()
       ch0_addr : zdc.Reg[Address] = zdc.field()
       ch1_csr : zdc.Reg[ChannelCSR] = zdc.field()
       ch1_addr : zdc.Reg[Address] = zdc.field()
       ch2_csr : zdc.Reg[ChannelCSR] = zdc.field()
       ch2_addr : zdc.Reg[Address] = zdc.field()
   
   @zdc.dataclass
   class DeviceEvents(Protocol):
       """Events separated from registers"""
       ch0_done : zdc.Event = zdc.field()
       ch1_done : zdc.Event = zdc.field()
       ch2_done : zdc.Event = zdc.field()
   
   @zdc.dataclass
   class DeviceMMIO(Protocol):
       regs : DeviceRegs = zdc.field()
       events : DeviceEvents = zdc.field()
       irq : zdc.Event = zdc.field()

**Problems with this approach:**

* Channel 0's registers (ch0_csr, ch0_addr) are not grouped together
* Events are disconnected from the registers they relate to
* Hard to reference: ``device.regs.ch0_csr`` and ``device.events.ch0_done`` are in different places
* Doesn't scale well: Adding a 4th channel requires changes in multiple places
* Not discoverable: Can't easily find all parts of "channel 0" interface

Using Tuple for Fixed-Size Arrays
----------------------------------

When a device has multiple identical units (channels, ports, etc.), use Python's
``Tuple`` type with ``zdc.tuple(size=N)`` to create fixed-size arrays:

.. code-block:: python

   from typing import Tuple
   
   @zdc.dataclass
   class DeviceMMIO(Protocol):
       # Fixed-size array of 4 channels
       channels : Tuple[Channel, ...] = zdc.tuple(size=4)

**Why use Tuple?**

* **Type safety**: ``Tuple[Channel, ...]`` indicates a fixed-size collection
* **Clear intent**: Size is explicitly declared in the model
* **Iteration support**: Can iterate over all channels: ``for ch in device.channels``
* **Index access**: Direct access by index: ``device.channels[0]``
* **Structured data**: Better than separate ``ch0``, ``ch1``, ``ch2`` fields

**When to use Tuple vs individual fields:**

* ✓ Use ``Tuple`` when you have 3+ identical units that are accessed programmatically
* ✓ Use ``Tuple`` when the number of units is fixed but might change in variants
* ✗ Avoid individual fields (``ch0``, ``ch1``, etc.) for more than 2-3 identical units

Correct Pattern: Hierarchical Organization
-------------------------------------------

**✓ CORRECT: Hierarchical grouping of related functionality**

.. code-block:: python

   @zdc.dataclass
   class ChannelRegs(zdc.RegFile):
       """Registers for one channel"""
       csr : zdc.Reg[ChannelCSR] = zdc.field()
       addr : zdc.Reg[Address] = zdc.field()
       size : zdc.Reg[Size] = zdc.field()
   
   @zdc.dataclass
   class Channel(Protocol):
       """Complete interface for one channel: registers + events"""
       regs : ChannelRegs = zdc.field()
       done : zdc.Event = zdc.field()
       error : zdc.Event = zdc.field()
   
   @zdc.dataclass
   class GlobalRegs(zdc.RegFile):
       """Global control registers"""
       csr : zdc.Reg[GlobalCSR] = zdc.field()
       int_mask : zdc.Reg[IntMask] = zdc.field()
   
   @zdc.dataclass
   class DeviceMMIO(Protocol):
       global_regs : GlobalRegs = zdc.field()
       channels : Tuple[Channel, ...] = zdc.tuple(size=3)
       irq : zdc.Event = zdc.field()

**Benefits of this approach:**

* All channel 0 functionality: ``device.channels[0].regs.csr``, ``device.channels[0].done``
* Clear grouping: Everything for channel 0 is under ``device.channels[0]``
* Easy to add channels: Just change the ``size`` parameter in ``zdc.tuple()``
* Reusable: ``Channel`` Protocol can be used for all channels
* Self-documenting: Structure mirrors hardware architecture
* Discoverable: IDE autocomplete shows all parts of a channel together
* Tuple typing: Using ``Tuple[Channel, ...]`` captures fixed-size lists of channels

Usage Comparison
----------------

**Flat structure (anti-pattern):**

.. code-block:: python

   # Configure channel 0 - scattered references
   await device.regs.ch0_csr.write(...)
   await device.regs.ch0_addr.write(...)
   await device.events.ch0_done.wait()  # Wait in different namespace
   
   # Hard to work with programmatically
   for i in range(3):
       await getattr(device.regs, f'ch{i}_csr').write(...)  # Awkward
       await getattr(device.events, f'ch{i}_done').wait()

**Hierarchical structure (correct):**

.. code-block:: python

   # Configure channel 0 - cohesive interface
   await device.channels[0].regs.csr.write(...)
   await device.channels[0].regs.addr.write(...)
   await device.channels[0].done.wait()  # Wait in same namespace
   
   # Easy to work with programmatically
   for ch in device.channels:
       await ch.regs.csr.write(...)
       await ch.done.wait()

Example: DMA Controller
------------------------

The WISHBONE DMA/Bridge demonstrates hierarchical organization:

.. code-block:: python

   @zdc.dataclass
   class DmaChannelRegs(zdc.RegFile):
       """8 registers per channel"""
       csr : zdc.Reg[DmaChannelCSR] = zdc.field()
       sz : zdc.Reg[DmaChannelSZ] = zdc.field()
       a0 : zdc.Reg[DmaChannelAddr] = zdc.field()
       am0 : zdc.Reg[DmaChannelAddrMask] = zdc.field()
       a1 : zdc.Reg[DmaChannelAddr] = zdc.field()
       am1 : zdc.Reg[DmaChannelAddrMask] = zdc.field()
       desc : zdc.Reg[DmaChannelDesc] = zdc.field()
       swptr : zdc.Reg[DmaChannelSWPtr] = zdc.field()
   
   @zdc.dataclass
   class DmaChannel(Protocol):
       """Complete channel interface: registers + 3 events"""
       regs : DmaChannelRegs = zdc.field()
       error : zdc.Event = zdc.field()
       done : zdc.Event = zdc.field()
       chunk_done : zdc.Event = zdc.field()
   
   @zdc.dataclass
   class DmaGlobalRegs(zdc.RegFile):
       """Global DMA control"""
       csr : zdc.Reg[DmaMainCSR] = zdc.field()
       int_msk_a : zdc.Reg[u32] = zdc.field()
       int_msk_b : zdc.Reg[u32] = zdc.field()
       int_src_a : zdc.Reg[u32] = zdc.field()
       int_src_b : zdc.Reg[u32] = zdc.field()
   
   @zdc.dataclass
   class DmaMMIO(Protocol):
       global_regs : DmaGlobalRegs = zdc.field()
       channels : Tuple[DmaChannel, ...] = zdc.tuple(size=4)
       irq_a : zdc.Event = zdc.field()
       irq_b : zdc.Event = zdc.field()

**Usage:**

.. code-block:: python

   # Start DMA transfer on channel 0
   await dma.channels[0].regs.a0.write(src_addr)
   await dma.channels[0].regs.a1.write(dst_addr)
   await dma.channels[0].regs.sz.write(DmaChannelSZ(tot_sz=256))
   await dma.channels[0].regs.csr.write(DmaChannelCSR(ch_en=1, inc_src=1, inc_dst=1))
   
   # Wait for completion
   await dma.channels[0].done.wait()
   
   # Check for errors
   csr = await dma.channels[0].regs.csr.read()
   if csr.err:
       print("Transfer error")

**Why this structure:**

* All channel 0 operations use ``dma.channels[0].*`` prefix
* Registers (``dma.channels[0].regs.*``) and events (``dma.channels[0].done``) are co-located
* Global interrupt routing is separate (``dma.global_regs.int_msk_a``)
* Physical interrupts are at top level (``dma.irq_a``, ``dma.irq_b``)
* Each channel is self-contained and reusable
* Fixed-size tuple captures all 4 channels: ``channels : Tuple[DmaChannel, ...] = zdc.tuple(size=4)``

Design Guidelines
-----------------

When designing MMIO interfaces:

1. **Identify repetition**: Look for multiple identical units (channels, ports, banks)

   * Create a Protocol class for one unit
   * Use ``Tuple`` and ``zdc.tuple(size=N)`` to instantiate multiple instances

2. **Group registers**: Keep related registers together in RegFile classes

   * Per-channel registers → ChannelRegs
   * Global registers → GlobalRegs
   * Configuration vs status → separate if they serve different purposes

3. **Co-locate events**: Put events in the same Protocol as their related registers

   * Channel done event → in Channel Protocol
   * Global interrupt → in top-level Protocol

4. **Separate concerns**: Keep global and per-unit functionality distinct

   * Global control → separate from per-channel control
   * Interrupt routing (global) vs interrupt source (per-channel)

5. **Think about usage**: Design for how the interface will be used

   * ``device.channels[0].done`` is clearer than ``device.events.ch0_done``
   * Enables list comprehensions: ``[ch.done for ch in device.channels]``
   * Fixed-size tuples provide type safety and structured access

Identifying Logical Events in MMIO Abstraction
===============================================

When creating an MMIO-level model, you must identify and expose all **logical events**
that the device generates, not just the physical interrupt signals.

Physical vs Logical Events
--------------------------

* **Physical Events**: Actual interrupt pins (irq, inta_o, intb_o, intr, etc.)

  * These are what connect to interrupt controllers
  * Often aggregated/ORed combinations of multiple sources
  * May be routed through mask/enable registers

* **Logical Events**: Individual event sources within the device

  * Specific conditions like error, done, timeout, overflow, etc.
  * Each has its own enable bit and status/source bit
  * Multiple logical events combine to create physical interrupts

Logical Event Identification Checklist
---------------------------------------

When analyzing a hardware specification, look for:

1. **Interrupt enable bits** (INE_*, IE, *_IE, etc.)

   * Each enable bit typically corresponds to a logical event
   * Example: ``INE_ERR``, ``INE_DONE``, ``INE_CHK_DONE``
   * Multiple enable bits → multiple logical events

2. **Interrupt source/status bits** (INT_*, IS_*, *_IS, etc.)

   * These indicate which logical event occurred
   * Often Read-On-Clear (ROC) or Write-1-to-Clear (W1C)
   * Example: ``INT_ERR``, ``INT_DONE``, ``INT_CHK_DONE``

3. **Condition status bits** (DONE, ERR, BUSY, READY, etc.)

   * Status bits that indicate event conditions
   * May or may not have associated interrupt enables
   * Still useful for polling-based access patterns

4. **Interrupt routing/masking architecture**

   * Global mask registers (``INT_MSK_*``, ``INT_EN_*``)
   * Per-channel or per-source routing configuration
   * Multiple physical interrupt outputs
   * Look for MUX/OR trees in block diagrams

5. **Per-channel or per-unit replication**

   * Devices with multiple channels often replicate events
   * Example: 4 DMA channels × 3 events = 12 logical events
   * All may feed into 1 or 2 physical interrupt outputs

Event Placement in Hierarchy
-----------------------------

Place logical events in the same Protocol as their related registers:

.. code-block:: python

   # ✓ CORRECT: Events with their registers
   @zdc.dataclass
   class Channel(Protocol):
       regs : ChannelRegs = zdc.field()
       done : zdc.Event = zdc.field()    # Channel-specific event
       error : zdc.Event = zdc.field()   # Channel-specific event
   
   # ❌ WRONG: Events separated from registers
   @zdc.dataclass
   class ChannelEvents(Protocol):
       done : zdc.Event = zdc.field()
       error : zdc.Event = zdc.field()
   
   @zdc.dataclass
   class Channel(Protocol):
       regs : ChannelRegs = zdc.field()
       events : ChannelEvents = zdc.field()  # Unnecessary nesting

Rationale for Logical Events
-----------------------------

Exposing logical events provides critical benefits:

* **Driver Development**: Software needs to know which specific event occurred

  * Error vs done vs timeout require different handling
  * Cannot distinguish from physical interrupt alone

* **Test Scenarios**: Tests need to wait for specific conditions

  * ``await device.ch0.done.wait()`` is clearer than register polling
  * Enables event-driven test patterns
  * Supports concurrent waiting on multiple event types

* **Verification**: Proper event sequencing can be checked

  * Verify error events occur before done events
  * Check that chunk_done precedes final done
  * Validate interrupt masking behavior

* **Abstraction**: Higher-level operations compose from logical events

  * Operation-level methods can wait for specific device states
  * Test scenarios don't need to know register bit positions
  * Device behavior is more explicit and documentable

Implementation: Transfer Function
=================================

* Algorithmic with timing implementation

Implementation: Cycle Accurate
==============================

- What are we 

* Is this about operation granularity?
* Is this assumption about how frequently the block is evaluated?

  * At operational boundaries
  * At implementation boundaries

    * Several levels of detail here

* What does it say 

Hardware Interface Level
========================
- Per-interface, though likely to share an abstraction level

* Transfer-function
* Transaction level
* Wire / Detailed protocol
