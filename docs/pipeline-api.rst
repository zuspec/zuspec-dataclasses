.. _pipeline-api:

################
Pipeline API
################

The ``zuspec-dataclasses`` pipeline API describes a synchronous, single-issue,
in-order pipeline as a set of Python methods on a :class:`~zuspec.dataclasses.Component`
subclass.  The synthesizer in ``zuspec-synth`` converts these methods into
fully-synthesisable Verilog 2005.

Three decorators work together:

* :ref:`pipeline-decorator` — marks the root data-flow method
* :ref:`stage-decorator` — marks each pipeline stage
* :ref:`sync-decorator` — marks external synchronous FSMs that interact with stages

.. contents:: Contents
   :local:
   :depth: 2

---

.. _pipeline-decorator:

``@zdc.pipeline`` — Pipeline Root
===================================

The pipeline root method describes a single transaction's journey through all
stages.  The synthesizer repeats this path every cycle, inserting pipeline
registers, stall logic, and forwarding muxes as needed.

.. code-block:: python

   @zdc.dataclass
   class TwoStage(zdc.Component):
       clk:   zdc.clock
       rst_n: zdc.reset
       x:     zdc.u32

       @zdc.pipeline(clock="clk", reset="rst_n")
       def execute(self):
           (x,) = self.S1()
           self.S2(x)

       @zdc.stage
       def S1(self) -> (zdc.u32,):
           return (self.x,)

       @zdc.stage
       def S2(self, x: zdc.u32) -> ():
           pass

Each ``self.STAGE(args)`` call is a pipeline-stage invocation.  Arguments are
the **live variables entering that stage**; return values are the **live
variables leaving** it.  Variables that skip intermediate stages are
**auto-threaded** — the synthesizer inserts a pipeline register at every
stage boundary automatically.

``@zdc.pipeline`` arguments
-----------------------------

.. list-table::
   :header-rows: 1
   :widths: 15 10 10 65

   * - Argument
     - Type
     - Default
     - Description
   * - ``clock``
     - ``str``
     - required
     - Clock field name on the component (e.g. ``"clk"``).
   * - ``reset``
     - ``str``
     - required
     - Reset field name on the component (e.g. ``"rst_n"``).
   * - ``forward``
     - ``bool``
     - ``True``
     - Default hazard resolution: ``True`` = forward bypass mux,
       ``False`` = stall the pipeline.
   * - ``no_forward``
     - ``list[str]``
     - ``[]``
     - Per-signal override: signal names that should always use stall
       instead of forwarding, even when ``forward=True``.

---

.. _stage-decorator:

``@zdc.stage`` — Stage Methods
================================

Each stage is a ``def`` method decorated with ``@zdc.stage``.  The method
receives data entering the stage and returns data leaving it.  All register
insertion, stall propagation, and valid-chain management is generated
automatically.

.. code-block:: python

   @zdc.stage
   def IF(self) -> (zdc.u32, zdc.u32):
       zdc.stage.stall(~self.imem_valid)   # hold stage until memory acks
       return (self.pc, self.imem_data)

   @zdc.stage(no_forward=True)
   def MEM(self, addr: zdc.u32, is_load: zdc.u1) -> (zdc.u32,):
       zdc.stage.stall(self.mem_req & ~self.mem_ack)
       return (self.mem_rdata,)

``@zdc.stage`` arguments
--------------------------

.. list-table::
   :header-rows: 1
   :widths: 20 10 10 60

   * - Argument
     - Type
     - Default
     - Description
   * - ``no_forward``
     - ``bool``
     - ``False``
     - When ``True``, exclude all of this stage's outputs as forwarding
       sources.  The synthesizer generates a stall for any hazard path
       that would otherwise produce a bypass mux.  Use for stages whose
       output arrives late (e.g. a load from external memory).

All ``@zdc.stage`` methods must be plain ``def`` (not ``async def``) and all
parameters must carry type annotations so the synthesizer can determine
pipeline register widths.

Stage DSL calls
----------------

These calls are synthesizer annotations — they are **no-ops at Python
runtime**.  The synthesizer recognises them by AST inspection and generates
the corresponding hardware.

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Call
     - Effect
   * - ``zdc.stage.stall(cond)``
     - Freeze this stage and all upstream stages while *cond* is true.
       The current stage stays valid (transaction is paused, not lost).
       The next stage receives a bubble.
   * - ``zdc.stage.cancel(cond=True)``
     - Discard the transaction in this stage (clear valid) without
       freezing upstream.  Upstream stages continue to advance.
   * - ``zdc.stage.flush(self.X, cond=True)``
     - Invalidate the target stage ``X`` next cycle.  Flush priority
       is higher than stall: a stalled stage can still be flushed.

``stall`` always takes a positional condition.  ``cancel`` and ``flush``
accept either a positional or ``cond=`` keyword:

.. code-block:: python

   # Inside a stage body
   zdc.stage.stall(~self.imem_valid)          # positional
   zdc.stage.stall(cond=~self.imem_valid)     # keyword — identical

   if mispredicted:
       zdc.stage.flush(self.IF)               # cond=True implied by if-body
   zdc.stage.flush(self.IF, cond=mispredicted)  # explicit — identical hardware

---

.. _sync-decorator:

``@zdc.sync`` — Synchronous FSMs
==================================

External FSMs that manage pipeline interactions (e.g. instruction-fetch,
load-store units, interrupt controllers) are marked with ``@zdc.sync``.
They run every clock cycle and can observe stage-validity signals via
DSL query functions.

.. code-block:: python

   @zdc.sync(clock="clk", reset="rst_n")
   def fetch_ctrl(self):
       if zdc.stage.ready(self.IF):   # IF can accept a new instruction
           self.imem_req  = 1
           self.imem_addr = self.pc

``@zdc.sync`` arguments
-------------------------

.. list-table::
   :header-rows: 1
   :widths: 15 10 10 65

   * - Argument
     - Type
     - Default
     - Description
   * - ``clock``
     - ``str``
     - required
     - Clock field name.
   * - ``reset``
     - ``str``
     - required
     - Reset field name.

Stage query functions (usable inside ``@zdc.sync`` and ``@zdc.stage`` bodies)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Query
     - Meaning / generated hardware
   * - ``zdc.stage.valid(self.X)``
     - Stage X holds a live transaction → ``X_valid`` flip-flop
   * - ``zdc.stage.ready(self.X)``
     - Stage X can accept a new transaction →
       ``(~X_valid | ~X_stalled)`` combinational wire
   * - ``zdc.stage.stalled(self.X)``
     - Stage X is currently stalled → ``X_stalled`` combinational wire

Flush from ``@zdc.sync``
~~~~~~~~~~~~~~~~~~~~~~~~~

``zdc.stage.flush(target, cond)`` may also be called from a ``@zdc.sync``
body.  This lets interrupt controllers or exception handlers discard all
in-flight pipeline transactions:

.. code-block:: python

   @zdc.sync(clock="clk", reset="rst_n")
   def irq_ctrl(self):
       take_irq = self.irq & ~self.irq_masked
       if take_irq:
           zdc.stage.flush(self.S1)   # cond=True implied by if-body
           zdc.stage.flush(self.S2)
           zdc.stage.flush(self.S3)

---

Migration Guide — Old Sentinel API → New Method API
=====================================================

The original pipeline API used ``zdc.stage()`` sentinel objects inside the
pipeline body:

.. code-block:: python

   # OLD API (deprecated) — sentinel-based
   @zdc.pipeline(clock=lambda s: s.clk, reset=lambda s: s.rst_n,
                 stages=["IF", "EX"])
   def execute(self):
       IF = zdc.stage()
       pc = self.pc
       EX = zdc.stage()
       result = pc + 1

Replace it with the new method-per-stage API:

.. code-block:: python

   # NEW API — method-per-stage
   @zdc.pipeline(clock="clk", reset="rst_n")
   def execute(self):
       (pc,) = self.IF()
       self.EX(pc)

   @zdc.stage
   def IF(self) -> (zdc.u32,):
       return (self.pc,)

   @zdc.stage
   def EX(self, pc: zdc.u32) -> ():
       pass

Key changes:

* ``clock``/``reset`` change from ``lambda s: s.clk`` → ``"clk"`` (string field name).
* Remove ``stages=`` parameter; stage order is expressed by the call sequence.
* Each ``IF = zdc.stage()`` sentinel becomes a ``@zdc.stage`` method.
* Variables passed between stages become method parameters and return values.
* ``zdc.forward(...)`` / ``zdc.no_forward(...)`` helpers are replaced by the
  ``no_forward`` argument on ``@zdc.stage`` and ``@zdc.pipeline``.

The old ``PipelineAnnotationPass`` in ``zuspec-synth`` is deprecated.  The new
``PipelineFrontendPass`` handles components using the method-per-stage API.
