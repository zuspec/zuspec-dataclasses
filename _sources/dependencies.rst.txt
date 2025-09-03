############
Dependencies
############

`Dependencies` provide a way for modeling elements to specify the 
services that they are dependent on (require), and have those 
dependencies provided by the containing environment.
Many models will simply build on top of service kinds that are 
defined by the Zuspec library, but models are allowed to define 
their own as well.
Zuspec `Services` implement a form of the 
`dependency-injection pattern <https://en.wikipedia.org/wiki/Dependency_injection>`_ .

Dependency is an association, not an implementation. No specific implementation is inferred. 

Let's look an example. Clock and reset could be modeled as a dependency:

* Most RTL modules require access to clock and reset
* The vast majority only have a single clock and reset
* Most RTL modules receive the same clock and reset as their siblings

Instead of routing clock and reset to each module, we can simply
inherit the `Timebase` that our parent component provides. Let's look
at an example:

.. code-block:: python3

    class SubC1(zdc.Componet):
        count : zdc.Bit[32] = zdc.output()

        @zdc.sync
        def _inc(self):
          self.count += 1

    class Upper(zdc.Component):
        clock : zdc.Bit = zdc.input()
        reset : zdc.Bit = zdc.input()

        _timebase : zdc.TimebaseClockReset = zdc.field(
            init=dict(clock=lamba s:s.clock, reset=lambda s:s.reset))

        _c1_1 : SubC1 = zdc.field()
        _c1_2 : SubC1 = zdc.field()

In the example above, component SubC1 declares a synchronous method. Synchronous
methods are evaluated relative to a Timebase, which means that SubC1 has a 
Timebase dependency.

Fortunately, an instance exists in the containing component. A Zuspec processing
tool will automatically bind the dependency in `_c1_1` and `_c1_2` to the 
`TimebaseClockReset` instance in the containing component. 







