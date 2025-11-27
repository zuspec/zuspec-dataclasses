#####################
Zuspec Developer Info
#####################

Zuspec dataclasses provides five distinct areas of functionality:

* User-input types and decorators in the root package (zuspec.dataclasses)
* Datamodel classes in the *dm* sub-package
* Runtime classes in the *rt* sub-package
* Classes that transform user input (dataclasses) to datamodel in dc2dm
* Classes that transform datamodel (dm) to a Python implementation in dm2py

Workflows
=========

The Zuspec core package, potentially with other packages, supporst multiple 
workflows. Consequently, it's critical to maintain separation between the
five areas of functionality above.

Zuspec as a Class Library
-------------------------

In this workflow, the user views Zuspec as a class library with executable 
semantics. Specifically, something like the following works:

.. code-block:: python3

    # Counter example
    import zuspec.dataclasses as zdc

    @zdc.dataclass
    class Counter(zdc.Component):
        clock : zdc.bit = zdc.input()
        reset : zdc.bit = zdc.input()
        count : zdc.uint32 = zdc.output()

        @zdc.sync(clock=lambda s:s.clock, reset=lambda s:s.reset)
        def _inc(self):
            if self.reset:
                self.count = 0
            else:
                self.count += 1

    async def run():
        c = Counter()
        c.reset = 1
        c.clock = 0

        for _ in range(10):
            await c.wait(zdc.Time.ns(10))
            c.clock = 1
            await c.wait(zdc.Time.ns(10))
            c.clock = 0

        c.reset = 0a

        for _ in range(10):
            await c.wait(zdc.Time.ns(10))
            c.clock = 1
            await c.wait(zdc.Time.ns(10))
            c.clock = 0
        
        # Expect c.count to be 10

In this workflow, what actually happens is the following:

* The Zuspec library intercepts __new__ for Counter
* The Counter class is transformed to a datamodel representation using classes in *dm*
  by the classes in *dc2dm*. 
* The *dm* representation of the class is transformed to a Python implementation Python-based
  on the classes in *rt*. The implementation of this transform is in *dm2py*.
* An instance of the implementation class is returned from __new__
* The calling code interacts with this implementation

The object returned by the Counter() call appears to be an instance of the original 
class. However, its implementation differs in key ways:

* User-declared fields (eg clock, reset) are accessed via properties, allowing 
  value changes to trigger evaluation updates as required
* The *_inc* method is called by the Zuspec runtime framework when a change in 
  *clock* or *reset* fields is detected


