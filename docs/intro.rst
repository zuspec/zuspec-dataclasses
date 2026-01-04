##########################
Zuspec Language Overview
##########################

Zuspec is a Python-embedded modeling language focused on modeling 
the behavior of digital hardware designs at multiple levels of abstraction 
-- from an abstract behavioral model down to register transfer level (RTL).
Multiple distinct implementations can be derived from a Zuspec
model to address various points on the performance / fidelity curve.

Zuspec is a Python-based language, which means that it is embedded in
Python and adopts Python syntax, but applies special semantic rules 
to specified portions of the description. 

Zuspec is composed of four elements:

* Language facade -- the base classes and decorators used to identify key elements of the description
* Pure-Python runtime -- A pure Python implementation of the Zuspec semantics that leverages the Python 
  implementation of the source description
* Data Model -- An AST-like data model that captures the key type and behavioral descriptions involved 
  in a model
* Datamodel Processing Tools -- Tools that operate on the data model to analyze aspects
  of the model or produce additional outputs (eg C implementation)

It is critical to keep all of these aspects independent and modular. For example, the language
facade (zuspec.dataclasses namespace classes) must not be aware of the pure-python runtime.

Zuspec types inherit from a Zuspec base class, and are decorated with @zdc.dataclass.
Zuspec classes are dataclasses. 

Fields of Zuspec classes have the basic form of Python dataclass fields.

Zuspec input is valid Python syntax, but is not executable on its own because the input
specifies intent, not implementation. For example:

.. code-block:: python3

    class MyIF(Protocol):
      async def api(self): ...

    class MyTargT(zdc.Component):
      p : MyIF = zdc.export()

      def __bind__(self): return {
        p.api : self.target
      }

      async def target(self, val : int):
        print("target: %d" % val)
        await self.wait(zdc.Time.ns(10))

    class MyInitC(zdc.Component):
      p : MyIF = zdc.port()

      @zdc.process
      async def run(self):
        for i in range(16):
          await self.p.call(i)

    class TopC(zdc.Component):
      i : MyInitC = zdc.field()
      c : MyConsC = zdc.field()

      def __bind__(self): return {
        i.t : c.t
      }


In the example above, the *modeling* aspect of Zuspec is shown in several
places:

* Ports and exports are marked as having a Python type of MyIF, but are not
  explicitly initialized. A Python type checker can validate that method calls
  are valid
* The methods of an *export* are specified via the mapping returned from __bind__.
  Here, again, the relationship is modeled and not the implementation
* In the initiator, the *process* decoration marks the run method as one that is
  automatically started when an instance of the class is created
* In the top-level component, the __bind__ method specifies that the initiator and
  consumer port/export is connected

All the code is valid Python that supports static analysis tools such as type checkers.



Processing
==========

Many Zuspec implementations provide something that appears to be a Python object.
In these cases, the Zuspec-defined class that is the base of the user-defined class
provides a __new__ implementation that constructs an appropriate implementation object.
These providers are known as Object Factories, and implement the ObjFactory protocol.
The base classes obtain the proper ObjFactory implementation via the Config class.

This scheme allows Zuspec classes to be created as any other Python class. 

Runtime 
=======

An implementation of the 'Timebase' class allows methods to synchronize with respect 
to a simulation time. The time used in 'Timebase' is not a wallclock time, so 
asyncio.sleep() is never used in a Zuspec description


Datamodel
=========

Zuspec uses a data model that is a superset, or specialization, of Python. In other
words, the Zuspec data model can represent the Python language, but also has special
types that are significant in Zuspec. For example, the data model has a `Component` 
class that represents a class that inherits from the language-facade `Component` type.

The Zuspec dataclasses package provides a processor that accepts a set of types and
produces data models that correspond to them.

Fundamentally, the Zuspec datamodel is a type data model.

All type definitions in a datamodel Context have a name corresponding to the qualname 
of the source type.

The datamodel bind map captures relationships between:

* port and export
* input and output
* input and input
* export API type method and method

port, export, input, and output references are captured as indexed expressions.

.. code-block:: python3

      def __bind__(self): return {
        i.t : c.t
      }

For example, the bind from the example above results in a bind map with a single 
entry has the following type expressions:

* RefFieldIndex(RefFieldIndex(0, RefContext()), 0)
* RefFieldIndex(RefFieldIndex(1, RefContext()), 0)


The datamodel bind map is created by evaluating the __bind__ method and passing
an object for 'self' that converts references to fields to reference expression 
data model elements. 