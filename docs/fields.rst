############
Class Fields
############

Zuspec follows the Python `dataclasses` model for declaring classes and
class fields. 

.. code-block:: python3

    import zuspec.dataclasses as zdc

    @zdc.dataclass
    class MyS(zdc.Struct):
        W : int = zdc.const(default=10)
        a : int = zdc.field(rand=True, domain=range(10))
        b : int = zdc.rand()

The example above shows several aspects of declaring fields within a
Zuspec datatype. 

* **W** - Constant that will be configured during initialization
* **a** - Random field with a built-in constraint limiting it to 0..9
* **b** - Random field specified with the `rand` convenience field specifier

* default is reset value
* rand  - Marks whether this field is randomizable
* const - Marks whether this field is const
* domain - Iterable, or Callable that produces an iterable, of the field domain
* bind
* init - dict of initialization values to apply. Elements may be lambda expressions
* claims
* provides
* export - makes the container a dependency provider of this field
* depends - Type to use in dependency binding
* mirror - Marks a bundle field as being a mirror of the specified type

ClassVar

***********
Convenience
***********
- rand
- const
- output - claim==True if a Service provides==True if 
  - Pool[T] if in an action context ; implicit bind via comp dependency
  - T otherwise ; explicit bind
- input
- port
  - Is a dependency on T ; explicit bind 
- export
  - Is a T provider ; explicit bind
- 
