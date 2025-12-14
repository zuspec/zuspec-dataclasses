##################
Abstraction Levels
##################

Software Interface: Operation
=============================

* Focuses on key device operations.
* Implements those operations as async methods
* Effectively driver-level

Software Interface: Programmer's View
=====================================

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


