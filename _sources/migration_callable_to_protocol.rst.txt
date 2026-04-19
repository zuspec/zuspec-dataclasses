.. _migration-callable-to-protocol:

######################################
Migration: Callable → IfProtocol
######################################

This guide helps you upgrade existing ``Callable``-typed ports to the new
``zdc.IfProtocol`` style that enables richer synthesis.

.. contents:: On this page
   :depth: 3
   :local:

Overview
=========

Prior to ``zdc.IfProtocol``, inter-component calls were declared as plain
``Callable`` ports::

    # Old style (Form A)
    dat: Callable[[], Awaitable[zdc.u32]] = zdc.port()

The new style (Form B) declares a named interface class::

    # New style (Form B)
    class DatIface(zdc.IfProtocol):
        async def get(self) -> zdc.u32: ...

    dat: DatIface = zdc.port()

Form B is required for Scenario C/D synthesis (multi-outstanding) and is
preferred for all new code.  Form A continues to work for Scenario B
(single-outstanding, basic handshake) and will not be removed.

Step-by-Step Migration
========================

Step 1 — Identify the Callable port
-------------------------------------

Look for port declarations that use ``Callable`` or ``Awaitable``::

    # Old
    from typing import Callable, Awaitable

    @zdc.dataclass
    class Cache(zdc.Component):
        mem_read: Callable[[zdc.u32], Awaitable[zdc.u32]] = zdc.port()

Step 2 — Create an ``IfProtocol`` class
-----------------------------------------

Create a class that inherits from ``zdc.IfProtocol``.  Set class keyword
arguments to describe the hardware timing contract.  Declare the method(s)
with the same signature::

    # New
    class MemReadIface(zdc.IfProtocol,
                       max_outstanding=1,      # add more if needed
                       req_always_ready=False,
                       resp_has_backpressure=False):
        async def read(self, addr: zdc.u32) -> zdc.u32: ...

Choose properties based on your hardware target (see
:doc:`interface_protocols` for the full property table and scenario guide).

Step 3 — Update the port declaration
--------------------------------------

Replace the ``Callable`` annotation with the new interface type::

    @zdc.dataclass
    class Cache(zdc.Component):
        mem_read: MemReadIface = zdc.port()   # was Callable[...]

Step 4 — Update call sites
----------------------------

``Callable`` ports were invoked with a direct call::

    # Old call site
    data = await self.mem_read(addr)

``IfProtocol`` ports are invoked by naming the method::

    # New call site
    data = await self.mem_read.read(addr)

For ``SimpleCall`` (single-method shorthand) the old ``__call__`` style is
preserved::

    dat: zdc.SimpleCall[zdc.u32, zdc.u32] = zdc.port()
    result = await self.dat(value)   # unchanged

Step 5 — Update bindings
--------------------------

Port bindings in ``__bind__`` reference the field name, so no change is
needed if the field name stayed the same.

Step 6 — Add protocol properties
----------------------------------

This is the most important step.  Match the properties to the actual hardware
you are targeting:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Hardware characteristic
     - Property to set
   * - Target always accepts requests
     - ``req_always_ready=True``
   * - Response arrives after fixed N cycles
     - ``fixed_latency=N``
   * - Multiple reads can be in flight
     - ``max_outstanding=N``
   * - Responses arrive in request order
     - ``in_order=True`` (default)
   * - Responses may arrive out of order
     - ``in_order=False``
   * - Minimum gap between requests
     - ``initiation_interval=II``

Side-by-Side Reference
=======================

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - Old (Form A)
     - New (Form B)
   * - ``Callable[[zdc.u32], Awaitable[zdc.u32]]``
     - ``class Iface(zdc.IfProtocol): async def read(self, addr: zdc.u32) -> zdc.u32: ...``
   * - ``dat: Callable[...] = zdc.port()``
     - ``dat: Iface = zdc.port()``
   * - ``await self.dat(addr)``
     - ``await self.dat.read(addr)``
   * - No synthesis metadata
     - Full property-driven RTL template selection
   * - Synthesizes as Scenario B only
     - Synthesizes as Scenario A–E based on properties

``SimpleCall`` Shorthand
=========================

If your port has exactly one argument and one return type and you do not need
to attach non-default properties, ``zdc.SimpleCall`` provides a compact
migration path::

    # Old
    dat: Callable[[zdc.u32], Awaitable[zdc.u32]] = zdc.port()
    result = await self.dat(value)

    # New (SimpleCall)
    dat: zdc.SimpleCall[zdc.u32, zdc.u32] = zdc.port()
    result = await self.dat(value)   # __call__ is preserved

``SimpleCall`` is an ``IfProtocol`` subclass and participates fully in
synthesis.  To add non-default properties, subclass it::

    class FastDatIface(zdc.SimpleCall[zdc.u32, zdc.u32],
                       fixed_latency=2,
                       req_always_ready=True):
        pass

Backward Compatibility Notes
==============================

* Existing tests that instantiate components with ``Callable`` ports will
  continue to pass; the Python runtime is unchanged.
* Synthesis of ``Callable`` ports falls back to Scenario B with default
  properties.  If your synthesis tests relied on those generated signals,
  they will continue to pass after migration with ``max_outstanding=1``
  (the default).
* The ``@zdc.call()`` decorator is only available on methods of an
  ``IfProtocol`` subclass; it has no effect on ``Callable`` ports.
* The IR checker (``flake8-zdc``) will emit a warning for ``Callable``-typed
  ports in a future release.  Migrating now avoids the warning.

.. seealso::

   :doc:`interface_protocols` — Full explanation of the property model and
   synthesis scenarios.

   :doc:`types` — API reference for ``IfProtocol``, ``SimpleCall``, and all
   new primitives.
