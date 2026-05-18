.. _counters:

Abstract Counters
=================

``zuspec.dataclasses`` provides a family of *abstract* counter classes that
work at every abstraction level — simulation, RTL synthesis, and formal
verification — without requiring explicit per-cycle callback overhead.

.. contents:: Contents
   :local:
   :depth: 2


Motivation
----------

A naive simulation counter updates a value on every clock edge.  For a 32-bit
counter running at 1 GHz that means one billion Python function calls per
simulated second — far too slow for anything beyond trivial designs.

The abstract counter avoids this by recording only the *start cycle* and
computing the current value on demand:

.. code-block:: python

    value = (current_cycle - start_cycle) % modulus

This "lazy" strategy has zero per-cycle overhead regardless of the counter
width or frequency.


Quick start — free-running counter
------------------------------------

.. code-block:: python

    import zuspec.dataclasses as zdc

    @zdc.dataclass
    class LatencyProbe(zdc.Component):
        cnt: zdc.Counter = zdc.inst(zdc.Counter)

        @zdc.proc
        async def _run(self):
            t0 = self.cnt.snapshot()          # record start time
            # ... do some work ...
            await self.cnt.wait_for(t0 + 256) # stall until 256 cycles later
            latency = self.cnt.value - t0

:attr:`~zdc.Counter.snapshot` is an alias for :attr:`~zdc.Counter.value` that
communicates *timestamping* intent to readers of the code.


Counter types
-------------

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Class
     - Key parameters
     - Description
   * - :class:`~zdc.Counter`
     - ``WIDTH=32``
     - Free-running counter, modulus ``2**WIDTH``.
   * - :class:`~zdc.ModuloCounter`
     - ``PERIOD``
     - Counts 0 … PERIOD-1 then wraps.  PERIOD need not be a power of two.
   * - :class:`~zdc.WatchdogCounter`
     - ``TIMEOUT``
     - Calls :meth:`~zdc.WatchdogCounter.on_timeout` if not kicked in time.
   * - :class:`~zdc.CounterBank`
     - ``COUNT``, ``WIDTH``
     - ``COUNT`` independent counters sharing one clock domain.


Free-running Counter
----------------------

:class:`~zdc.Counter` wraps freely at ``2**WIDTH``.  Use it for timestamps,
latency measurements, and any application where the exact rollover point does
not matter.

Waiting for a specific value
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    await self.cnt.wait_for(target)          # absolute target value
    await self.cnt.wait_ge(threshold)        # first cycle where value >= threshold

``target`` may also be a zero-argument callable so the threshold can be
computed lazily:

.. code-block:: python

    await self.cnt.wait_for(lambda: self.deadline)

Edge case: if ``value == target`` already, :meth:`~zdc.Counter.wait_for`
returns immediately.  If the target was *already passed* (target < current),
the wait runs until the *next* rollover past target.

Scheduling callbacks
~~~~~~~~~~~~~~~~~~~~~

:meth:`~zdc.Counter.schedule` registers a one-shot callback and returns a
:class:`~zdc.ScheduleHandle`:

.. code-block:: python

    handle = self.cnt.schedule(self.cnt.value + 100, callback=self._on_alarm)
    # ... later ...
    handle.cancel()                          # prevent firing
    handle.reschedule(self.cnt.value + 200)  # move the alarm

The handle's :attr:`~zdc.ScheduleHandle.fired` property is ``True`` once the
callback has executed at least once.


ModuloCounter
--------------

:class:`~zdc.ModuloCounter` is the go-to counter for frequency dividers, baud
rate generators, and PWM periods.

.. code-block:: python

    @zdc.dataclass
    class BaudTick(zdc.Component):
        baud: zdc.ModuloCounter = zdc.inst(zdc.ModuloCounter, kwargs={'PERIOD': 868})

        @zdc.proc
        async def _run(self):
            while True:
                await self.baud.wait_next()   # fires every 868 cycles
                self.tx_bit = ~self.tx_bit

:meth:`~zdc.Counter.wait_next` suspends until the counter wraps to 0.  To wait
for a specific phase within the period use :meth:`~zdc.Counter.wait_for`:

.. code-block:: python

    await self.baud.wait_for(434)  # mid-period sample point

Override :meth:`~zdc.ModuloCounter.on_rollover` instead of ``wait_next()`` for
a callback-style interface.


WatchdogCounter
----------------

:class:`~zdc.WatchdogCounter` fires :meth:`~zdc.WatchdogCounter.on_timeout` if
the design does not call :meth:`~zdc.WatchdogCounter.kick` within ``TIMEOUT``
cycles of the last arm/kick.

Arm → kick → disarm lifecycle
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    @zdc.dataclass
    class SafeController(zdc.Component):
        wdog: zdc.WatchdogCounter = zdc.inst(zdc.WatchdogCounter, kwargs={'TIMEOUT': 1000})

        @zdc.proc
        async def _run(self):
            self.wdog.arm()
            while self.active:
                await zdc.tick()
                if self.heartbeat:
                    self.wdog.kick()          # extend the window
            self.wdog.disarm()

        async def on_timeout(self):           # override to handle expiry
            self.fault = 1

- :meth:`~zdc.WatchdogCounter.arm` — start or restart the timeout window.
  Pass ``cycles`` to override ``TIMEOUT`` for this activation only.
- :meth:`~zdc.WatchdogCounter.kick` — reset the window; keeps the watchdog
  armed.
- :meth:`~zdc.WatchdogCounter.disarm` — stop the watchdog without firing.


CounterBank
------------

:class:`~zdc.CounterBank` provides ``COUNT`` independent counters that share a
single clock domain, avoiding the overhead of instantiating ``COUNT`` separate
:class:`~zdc.Component` objects.

.. code-block:: python

    @zdc.dataclass
    class MultiChannel(zdc.Component):
        timers: zdc.CounterBank = zdc.inst(zdc.CounterBank,
                                           kwargs={'COUNT': 4, 'WIDTH': 16})

        @zdc.proc
        async def _run(self):
            snap = self.timers.snapshot_all()   # atomic snapshot of all 4
            await self.timers[0].wait_for(snap[0] + 100)

Individual counters are accessed by index (``self.timers[i]``) and expose the
same :meth:`~zdc.Counter.wait_for` / :meth:`~zdc.Counter.wait_ge` /
:meth:`~zdc.Counter.schedule` interface as a standalone :class:`~zdc.Counter`.


RTL synthesis
-------------

:class:`~zdc.ModuloCounter` and :class:`~zdc.WatchdogCounter` fields inside a
:func:`~zdc.proc`-based component are synthesised automatically by the
``zuspec-synth`` pass.  The synthesiser replaces ``await cnt.wait_next()``
with an equivalent ``await zdc.cycles(PERIOD)`` pattern, which the RTL backend
maps to a hardware cycle-count register.

The counter field itself is *neutralised* (removed from the synthesised port
list) so the generated SystemVerilog contains only the internal state register.

.. code-block:: systemverilog

    // Generated for Blinker(ModuloCounter(PERIOD=8))
    always_ff @(posedge clk) begin
        if (!rst_n) state <= S_IDLE;
        else case (state)
            S_IDLE: begin state <= S_1; S_1_cnt <= 8-1; end
            S_1:    begin
                if (S_1_cnt == 0) begin led <= ~led; state <= S_IDLE; end
                else S_1_cnt <= S_1_cnt - 1;
            end
        endcase
    end

.. note::
   :meth:`~zdc.Counter.wait_for` with a runtime-computed target is **not
   synthesisable**.  Use :meth:`~zdc.Counter.wait_next` or pass a compile-time
   constant.


Formal verification
-------------------

``zuspec-be-fv`` automatically derives SystemVerilog Assertions from counter
fields via :class:`~zuspec.be.fv.passes.AbstractionFormalPass`:

.. code-block:: python

    from zuspec.be.fv.passes import AbstractionFormalPass

    fpass = AbstractionFormalPass(Blinker)

    for sva in fpass.all_properties():
        print(sva)

    # Recommended BMC depth for full coverage:
    print(fpass.min_required_depth())

Two assertions are generated per counter:

range_invariant
    ``0 <= cnt && cnt < PERIOD`` — the counter stays in bounds.
monotone_progress
    Each cycle the counter increments by 1, or rolls over from ``PERIOD-1``
    to 0 — no arbitrary jumps.

:meth:`~zuspec.be.fv.passes.AbstractionFormalPass.min_required_depth` returns the
minimum BMC depth needed to observe all :meth:`~zdc.Counter.wait_for` targets,
making it easy to set the solver bound correctly.


Edge cases
----------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Situation
     - Behaviour
   * - ``wait_for(target)`` when ``value == target``
     - Returns immediately (no suspension).
   * - ``wait_for(target)`` when target already passed
     - Waits until the *next* rollover then continues to target.
   * - ``wait_for(0)`` on a ``ModuloCounter``
     - Equivalent to ``wait_next()`` — suspends until the next wrap.
   * - ``WatchdogCounter.kick()`` before ``arm()``
     - Silently ignored.
   * - ``WatchdogCounter.arm()`` while already armed
     - Restarts the timeout window from now.
   * - ``CounterBank[i]`` out of range
     - Raises ``IndexError``.


FAQ
---

**Can I use a counter across clock-domain boundaries (CDC)?**
  Counters are tied to a single :class:`~zdc.ClockDomain`.  To sample a
  counter value in a different domain, use
  :meth:`~zdc.Counter.snapshot` in the source domain and transfer the
  captured integer via a synchroniser or FIFO.

**What is the difference between** ``wait_ge`` **and** ``wait_for``?
  ``wait_for(t)`` waits until ``value == t`` (mod modulus).  ``wait_ge(t)``
  waits until ``value >= t``, which is useful when the exact rollover boundary
  doesn't matter and over-shooting is acceptable.

**How do I implement a step ≠ 1 counter?**
  Instantiate a ``ModuloCounter`` with ``PERIOD = target_step`` and call
  ``wait_next()`` in a loop.  Each ``wait_next()`` advances the logical time
  by exactly ``PERIOD`` cycles.  Alternatively, use ``Counter`` directly and
  call ``wait_for(snapshot() + step)`` for a one-shot advance.
