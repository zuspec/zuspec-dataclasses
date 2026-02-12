############
Class Fields
############

Zuspec follows the Python `dataclasses` model for declaring classes and
class fields. The field type annotation specifies the user-visible type
of the field. The initializer (eg field()) captures semantics of the field,
such as the direction of an input/output port or whether the field is
considered to be a post-initialization constant.

.. code-block:: python3

    import zuspec.dataclasses as zdc

    @zdc.dataclass
    class MyComponent(zdc.Component):
        clock : zdc.bit = zdc.input()
        reset : zdc.bit = zdc.input()
        data_out : zdc.u32 = zdc.output()
        mem : zdc.Memory[zdc.u32] = zdc.field(size=1024)

***********
Decorators
***********

@dataclass
==========

The ``@zdc.dataclass`` decorator marks a class as a Zuspec type. It extends
Python's standard ``@dataclass`` with Zuspec-specific processing and profile
validation.

.. code-block:: python3

    @zdc.dataclass
    class MyComponent(zdc.Component):
        pass
    
    # With profile validation
    from zuspec.dataclasses import profiles
    
    @zdc.dataclass(profile=profiles.RetargetableProfile)
    class HardwareModel(zdc.Component):
        data : zdc.u32 = zdc.field()  # Width-annotated required

Profiles control validation rules:

* ``PythonProfile`` - Permissive, allows standard Python types
* ``RetargetableProfile`` - Strict, requires width-annotated types for hardware

@process
========

Marks an async method as an always-running process. The process starts
automatically when the component's simulation begins.

.. code-block:: python3

    @zdc.dataclass
    class Worker(zdc.Component):
        @zdc.process
        async def run(self):
            for i in range(10):
                await self.wait(zdc.Time.ns(10))
                print(f"Iteration {i}")

@sync
=====

Marks a synchronous (clocked) process with deferred assignment semantics.
The process executes on positive edge of clock or reset.

.. code-block:: python3

    @zdc.dataclass
    class Counter(zdc.Component):
        clock : zdc.bit = zdc.input()
        reset : zdc.bit = zdc.input()
        count : zdc.u32 = zdc.output()
        
        @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
        def _counter_proc(self):
            if self.reset:
                self.count = 0
            else:
                self.count = self.count + 1

**Deferred Assignment:** In ``@sync`` processes, assignments don't take effect
immediately. The new value is applied after the method completes but before
the next evaluation.

@comb
=====

Marks a combinational process with immediate assignment semantics.
The process re-evaluates whenever any input changes.

.. code-block:: python3

    @zdc.dataclass
    class Adder(zdc.Component):
        a : zdc.u32 = zdc.input()
        b : zdc.u32 = zdc.input()
        sum : zdc.u32 = zdc.output()
        
        @zdc.comb
        def _add(self):
            self.sum = self.a + self.b

@invariant
==========

Marks a method as a structural invariant that must always hold.

.. code-block:: python3

    @zdc.dataclass
    class Config(zdc.Struct):
        x : zdc.u8 = zdc.field(bounds=(0, 100))
        y : zdc.u8 = zdc.field(bounds=(0, 100))
        
        @zdc.invariant
        def sum_constraint(self) -> bool:
            return self.x + self.y <= 150

@constraint
===========

Marks a method as a constraint for random variables. See :doc:`constraints` for
complete documentation.

.. code-block:: python3

    @zdc.dataclass
    class Packet:
        length: int = zdc.rand(bounds=(64, 1500), default=64)
        
        @zdc.constraint
        def min_size(self):
            self.length >= 64
        
        @zdc.constraint.generic
        def small_packet(self):
            self.length < 256

Constraint methods use statement syntax where statements are implicitly ANDed.
See :doc:`constraints` for details on constraint expressions, helper functions
(``implies()``, ``dist()``, ``unique()``, ``solve_order()``), and random variables.

****************
Field Specifiers
****************

field()
=======

The general-purpose field specifier with the following parameters:

.. code-block:: python3

    zdc.field(
        rand=False,           # Whether field is randomizable
        init=None,            # Dict of init values or callable
        default_factory=None, # Factory for default value
        default=None,         # Default value
        metadata=None,        # Additional metadata dict
        size=None,            # Size (for Memory fields)
        bounds=None,          # Value bounds (min, max)
        width=None            # Width expression for bitv types
    )

Example:

.. code-block:: python3

    @zdc.dataclass
    class MyStruct(zdc.Struct):
        a : int = zdc.field(default=10)
        b : zdc.u8 = zdc.field(bounds=(0, 255))
        mem : zdc.Memory[zdc.u32] = zdc.field(size=4096)

const()
=======

Marks a field as a post-construction constant (structural type parameter).
Used for configuration and parameterization.

.. code-block:: python3

    @zdc.dataclass
    class WishboneInitiator(zdc.Bundle):
        DATA_WIDTH : zdc.u32 = zdc.const(default=32)
        ADDR_WIDTH : zdc.u32 = zdc.const(default=32)
        
        # Other fields can reference const values
        dat_w : zdc.bitv = zdc.output(width=lambda s: s.DATA_WIDTH)

rand()
======

Marks a field as a random variable for constraint-based randomization.
See :doc:`constraints` for complete documentation.

.. code-block:: python3

    @zdc.dataclass
    class Transaction:
        # Basic random variable
        addr: int = zdc.rand(default=0)
        
        # With value bounds
        data: int = zdc.rand(bounds=(0, 255), default=0)
        
        # Random array
        buffer: int = zdc.rand(size=16, default=0)

**Parameters:**

* ``bounds`` (tuple) - ``(min, max)`` value bounds
* ``default`` (any) - Default value when not randomized
* ``size`` (int) - Array size for vector fields
* ``width`` (int or callable) - Bit width for ``bitv`` types

Random variables are constrained using ``@constraint`` decorated methods.

randc()
=======

Marks a field as a random-cyclic variable that cycles through all values
before repeating.

.. code-block:: python3

    @zdc.dataclass
    class TestSequence:
        # Cycles through 0-15
        test_id: int = zdc.randc(bounds=(0, 15), default=0)
        
        @zdc.constraint
        def valid_tests(self):
            self.test_id < 12  # Only 0-11 are valid

Random-cyclic variables ensure all valid values are generated before repeating.
Parameters are the same as ``rand()``. See :doc:`constraints` for details.

input()
=======

Marks a field as an input port. Input fields see the value of their
bound output with no delay. Supports optional ``width`` parameter for
``bitv`` types.

.. code-block:: python3

    @zdc.dataclass
    class Consumer(zdc.Component):
        clock : zdc.bit = zdc.input()
        data : zdc.u32 = zdc.input()
        
        # Variable-width input with lambda expression
        param_data : zdc.bitv = zdc.input(width=lambda s: s.DATA_WIDTH)

* Top-level inputs are bound to implicit outputs
* Non-top-level inputs must be explicitly bound to outputs

output()
========

Marks a field as an output port. Bound inputs see the current value
with no delay. Supports optional ``width`` parameter for ``bitv`` types.

.. code-block:: python3

    @zdc.dataclass
    class Producer(zdc.Component):
        clock : zdc.bit = zdc.input()
        data : zdc.u32 = zdc.output()
        
        # Variable-width output
        result : zdc.bitv = zdc.output(width=lambda s: s.RESULT_WIDTH)

bundle()
========

Instantiates a bundle (interface) with declared directionality.
Supports ``kwargs`` parameter for passing configuration to the bundle.

.. code-block:: python3

    @zdc.dataclass
    class MyComponent(zdc.Component):
        DATA_WIDTH : zdc.u32 = zdc.const(default=32)
        
        bus : WishboneBus = zdc.bundle(
            kwargs=lambda s: dict(
                DATA_WIDTH=s.DATA_WIDTH,
                ADDR_WIDTH=s.DATA_WIDTH))

mirror()
========

Instantiates a bundle with flipped directionality (inputs become outputs
and vice versa).

.. code-block:: python3

    @zdc.dataclass
    class Responder(zdc.Component):
        bus_mirror : WishboneBus = zdc.mirror()

monitor()
=========

Instantiates a bundle for passive monitoring (all signals are inputs).

.. code-block:: python3

    @zdc.dataclass
    class Monitor(zdc.Component):
        bus_mon : WishboneBus = zdc.monitor()

port()
======

Marks a field as an API consumer. Ports must be bound to a matching
export that provides the interface implementation.

.. code-block:: python3

    class MemIF(Protocol):
        async def read(self, addr: int) -> int: ...
        async def write(self, addr: int, data: int): ...

    @zdc.dataclass
    class Consumer(zdc.Component):
        mem : MemIF = zdc.port()

export()
========

Marks a field as an API provider. Exports must be bound to implementations
of the interface methods via ``__bind__``.

.. code-block:: python3

    @zdc.dataclass
    class Provider(zdc.Component):
        mem : MemIF = zdc.export()
        
        def __bind__(self): return {
            self.mem.read : self.do_read,
            self.mem.write : self.do_write,
        }
        
        async def do_read(self, addr: int) -> int:
            return self._data[addr]
        
        async def do_write(self, addr: int, data: int):
            self._data[addr] = data

inst()
======

Marks a field for automatic instance construction based on annotated type.
Supports ``kwargs`` for constructor arguments and ``size`` for containers.

.. code-block:: python3

    @zdc.dataclass
    class Top(zdc.Component):
        # Single instance with kwargs
        counter : Counter = zdc.inst(
            kwargs=lambda s: dict(WIDTH=s.COUNTER_WIDTH))
        
        # Array of instances
        workers : List[Worker] = zdc.inst(
            elem_factory=Worker, 
            size=4)

tuple()
=======

Creates a fixed-size tuple field with automatic element construction.

.. code-block:: python3

    from typing import Tuple
    
    @zdc.dataclass
    class RegBank(zdc.Component):
        regs : Tuple[zdc.Reg[zdc.u32], ...] = zdc.tuple(
            size=8, 
            elem_factory=lambda: zdc.Reg[zdc.u32]())

**************
Binding Helper
**************

bind[Ts,Ti]
===========

The ``bind`` helper class provides type-safe binding specifications for
inline field bindings.

.. code-block:: python3

    from typing import Self

    @zdc.dataclass
    class Parent(zdc.Component):
        clock : zdc.bit = zdc.input()
        child : ChildComponent = zdc.field(bind=zdc.bind[Self, ChildComponent](
            lambda s, f: {
                f.clock : s.clock,
            }
        ))

The lambda receives:

* ``s`` - Handle to parent class (Self)
* ``f`` - Handle to field being bound (ChildComponent)

Returns a dict mapping target fields to source fields.

***************
Execution Types
***************

ExecKind
========

Enumeration of execution method kinds:

* ``ExecKind.Comb`` - Combinational (RTL)
* ``ExecKind.Sync`` - Synchronous (RTL)
* ``ExecKind.Proc`` - Process (behavioral)

Exec / ExecProc / ExecSync / ExecComb
======================================

Internal marker types for decorated methods:

* ``Exec`` - Base execution marker
* ``ExecProc`` - Process execution marker (from ``@process``)
* ``ExecSync`` - Synchronous execution marker (from ``@sync``)
* ``ExecComb`` - Combinational execution marker (from ``@comb``)

*************************
Parameterization Features
*************************

Zuspec supports powerful parameterization through const fields and lambda
expressions. See `PARAMETERIZATION_SUMMARY.md <../PARAMETERIZATION_SUMMARY.md>`_
for complete details.

Width Expressions
=================

Fields can reference const parameters to determine their width dynamically:

.. code-block:: python3

    @zdc.dataclass
    class ParameterizedBus(zdc.Bundle):
        DATA_WIDTH : zdc.u32 = zdc.const(default=32)
        
        # Width derived from parameter
        data : zdc.bitv = zdc.output(width=lambda s: s.DATA_WIDTH)
        
        # Computed width
        byte_en : zdc.bitv = zdc.input(width=lambda s: s.DATA_WIDTH // 8)

Kwargs for Bundle Instantiation
================================

Components can pass parameters to nested bundles:

.. code-block:: python3

    @zdc.dataclass
    class SystemComponent(zdc.Component):
        BUS_WIDTH : zdc.u32 = zdc.const(default=64)
        
        bus : SystemBus = zdc.bundle(
            kwargs=lambda s: dict(
                WIDTH=s.BUS_WIDTH,
                ADDR_WIDTH=32))

This enables flexible, reusable component designs with compile-time
configuration.
