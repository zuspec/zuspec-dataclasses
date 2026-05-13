.. _domains:

Clock and Reset Domains
=======================

Domains are the mechanism by which ``zuspec.dataclasses`` propagates clock and
reset information through a component hierarchy **without explicit CLK/RST
wiring**.  Every component that contains ``@zdc.sync`` logic should derive from
:class:`~zuspec.dataclasses.SyncComponent`; the framework then connects the
right clock and reset automatically at elaboration time.

Conceptual overview
-------------------

Every model has an implicit **time domain** (the ``Component`` base).  Digital
logic typically also belongs to a **clock domain** and a **reset domain**.
Designs closer to implementation may additionally declare a **power domain**
(reserved for future elaboration passes).

Domains bind top-down by default: a child component inherits its parent's
clock and reset domain unless explicitly overridden.

Quick start — single-clock design
----------------------------------

The simplest case: one clock, one reset, automatic propagation.

.. code-block:: python

    import zuspec.dataclasses as zdc

    @zdc.dataclass
    class Counter(zdc.SyncComponent):
        """32-bit counter — clock and reset are inherited."""
        count: zdc.bit32 = zdc.output(reset=0)

        @zdc.sync          # fires on the inherited clock_domain
        def tick(self):
            self.count += 1

    @zdc.dataclass
    class Top(zdc.SyncComponent):
        """Board-level top.  Declares the concrete clock and reset."""
        CLK:   zdc.bit = zdc.input()
        RST_N: zdc.bit = zdc.input()

        clock_domain = zdc.clock_domain(
            clock=lambda s: s.CLK,
            reset=lambda s: s.RST_N,
            period=zdc.Time.ns(10),
            name="sys_clk",
        )

        counter: Counter = zdc.inst()   # inherits clock_domain / reset_domain

No ``__bind__`` needed for the counter — domain flows automatically.

For designs without physical clock/reset ports (simulation-only or after
domain resolution) use bare class-level declarations:

.. code-block:: python

    @zdc.dataclass
    class Top(zdc.SyncComponent):
        clock_domain = zdc.ClockDomain(period=zdc.Time.ns(10), name="sys_clk")
        reset_domain = zdc.ResetDomain(style="none")   # reset-free
        counter: Counter = zdc.inst()

Named (multi-clock) domains
----------------------------

Declare extra ``ClockDomain`` class variables for each additional clock.
Bind ``@zdc.sync`` methods to a specific domain using ``domain=``:

.. code-block:: python

    from typing import ClassVar

    @zdc.dataclass
    class DualClock(zdc.SyncComponent):
        fast_clk: ClassVar[zdc.ClockDomain] = zdc.ClockDomain(
            period=zdc.Time.ns(2), name="fast_clk"
        )

        slow_count: zdc.bit32 = 0
        fast_count: zdc.bit32 = 0

        @zdc.sync                               # fires on default clock_domain
        def slow_step(self):
            self.slow_count += 1

        @zdc.sync(domain=lambda s: s.fast_clk)  # fires on fast_clk only
        def fast_step(self):
            self.fast_count += 1

The default (bare ``@zdc.sync``) domain is always ``clock_domain``, inherited
from the parent if not overridden on the component.

Derived domains and ``zdc.super()``
-------------------------------------

Express PLL or clock-divider relationships with
:class:`~zuspec.dataclasses.DerivedClockDomain`:

.. code-block:: python

    @zdc.dataclass
    class ClockGen(zdc.SyncComponent):
        # Divide the parent-inherited clock by 4.
        fast_clk = zdc.DerivedClockDomain(
            source=zdc.super(),   # relative to inherited clock_domain
            div=4,
            name="fast_div4",
        )

:func:`~zuspec.dataclasses.super` is an alias for
:class:`~zuspec.dataclasses.InheritedDomain` — it expresses "derive from
whatever domain my parent provides".  You can also use a lambda to derive
from a named sibling domain:

.. code-block:: python

    fast_clk = zdc.DerivedClockDomain(
        source=lambda s: s.pll_out,  # sibling domain on same component
        mul=3,
    )

Domain binding in ``__bind__``
--------------------------------

Override a child component's domain from the parent's ``__bind__``:

.. code-block:: python

    @zdc.dataclass
    class Top(zdc.SyncComponent):
        fast_clk: ClassVar[zdc.ClockDomain] = zdc.ClockDomain(
            period=zdc.Time.ns(2), name="fast_clk"
        )
        normal: Worker = zdc.inst()   # stays on default clock_domain
        fast:   Worker = zdc.inst()   # will be moved to fast_clk

        def __bind__(self):
            return {
                self.fast.clock_domain: self.fast_clk,
            }

After elaboration ``fast`` ticks only when ``fast_clk`` is driven; ``normal``
ticks only when the default ``clock_domain`` is driven.  The same syntax works
for ``reset_domain`` overrides.

SDC output
----------

Generate `Synopsys Design Constraints
<https://en.wikipedia.org/wiki/Synopsys_Design_Constraints>`_ (Tcl/SDC) from
an elaborated design:

.. code-block:: python

    from zuspec.dataclasses.sdc_emit import emit_sdc

    async with zdc.simulate(Top) as top:
        print(emit_sdc(top))

Example output::

    # ---- Clock definitions ----
    create_clock -name {sys_clk} -period 10.000

    # ---- Derived / generated clocks ----
    create_generated_clock -name {fast_div4} -source [get_clocks {sys_clk}] -divide_by 4

    # ---- False paths (CDC crossings & reset sequencing) ----
    # CDC crossing: slow_clk → fast_clk
    set_false_path -from [get_clocks {slow_clk}] -to   [get_clocks {fast_clk}]

:func:`~zuspec.dataclasses.emit_sdc` is a convenience wrapper.
:class:`~zuspec.dataclasses.SDCEmitPass` provides finer control:

.. code-block:: python

    p = zdc.SDCEmitPass()
    p.visit(top)
    text = p.sdc_text()

CDC primitives
--------------

Use these classes for known-safe clock-domain crossings.  They suppress the
corresponding ``set_false_path`` in SDC output automatically.

``zdc.TwoFFSync``
    Synthesizable two-flip-flop synchronizer for single-bit CDC crossings.

``zdc.AsyncFIFO``
    Structural placeholder for multi-bit asynchronous FIFOs.

``@zdc.cdc_unchecked(reason)``
    Marks a class or field as a known-safe crossing that should be excluded
    from CDC analysis.

.. code-block:: python

    @zdc.cdc_unchecked("Gray-coded counter — safe by construction")
    @zdc.dataclass
    class GraySyncBus(zdc.Component): ...

Migration guide — from explicit CLK/RST to domains
----------------------------------------------------

**Before** (explicit wiring):

.. code-block:: python

    @zdc.dataclass
    class Counter(zdc.Component):
        CLK: zdc.bit = zdc.input()
        RST: zdc.bit = zdc.input()
        count: zdc.bit32 = zdc.output()

        @zdc.sync(clock=lambda s: s.CLK, reset=lambda s: s.RST)
        def tick(self):
            if self.RST:
                self.count = 0
            else:
                self.count += 1

    @zdc.dataclass
    class Top(zdc.Component):
        CLK: zdc.bit = zdc.input()
        RST: zdc.bit = zdc.input()
        counter: Counter = zdc.inst()

        def __bind__(self):
            return (
                (self.counter.CLK, self.CLK),
                (self.counter.RST, self.RST),
            )

**After** (domain-based):

.. code-block:: python

    @zdc.dataclass
    class Counter(zdc.SyncComponent):
        reset_domain = zdc.ResetDomain(style="sync")
        count: zdc.bit32 = zdc.output(reset=0)

        @zdc.sync            # auto clock + reset via inherited domain
        def tick(self):
            self.count += 1  # reset handled by SyncComponent infrastructure

    @zdc.dataclass
    class Top(zdc.SyncComponent):
        CLK: zdc.bit = zdc.input()
        RST: zdc.bit = zdc.input()
        clock_domain = zdc.clock_domain(
            clock=lambda s: s.CLK,
            reset=lambda s: s.RST,
            period=zdc.Time.ns(10),
        )
        counter: Counter = zdc.inst()   # no __bind__ needed

Key changes:

1. ``Counter`` inherits from ``SyncComponent`` instead of ``Component``.
2. The ``CLK`` / ``RST`` ports are removed from ``Counter``.
3. ``@zdc.sync`` becomes bare (no ``clock=`` / ``reset=`` lambdas).
4. ``reset=0`` on output fields provides the reset value; the framework
   injects ``if self.rst: self.count = 0`` at synthesis time.
5. ``Top.__bind__`` no longer needs to wire CLK/RST.

Power domains (future)
-----------------------

``zdc.PowerDomain`` is a stub annotation for upcoming UPF/CPF power-aware
elaboration passes.  Declare at class level to name the power domain:

.. code-block:: python

    @zdc.dataclass
    class AlwaysOn(zdc.SyncComponent):
        pwr_domain = zdc.PowerDomain(name="always_on", always_on=True)

Power-domain analysis is not yet implemented.
