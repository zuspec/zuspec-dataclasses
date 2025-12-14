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
        clock : zdc.uint1_t = zdc.input()
        reset : zdc.uint1_t = zdc.input()
        data_out : zdc.uint32_t = zdc.output()
        mem : zdc.Memory[zdc.uint32_t] = zdc.field(size=1024)

***********
Decorators
***********

@dataclass
==========

The ``@zdc.dataclass`` decorator marks a class as a Zuspec type. It extends
Python's standard ``@dataclass`` with Zuspec-specific processing.

.. code-block:: python3

    @zdc.dataclass
    class MyComponent(zdc.Component):
        pass

@process
========

Marks an async method as an always-running process. The process starts
when the component's simulation begins.

.. code-block:: python3

    @zdc.dataclass
    class Worker(zdc.Component):
        @zdc.process
        async def run(self):
            while True:
                await self.wait(zdc.Time.ns(10))
                # Do work

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
        size=None             # Size (for Memory fields)
    )

Example:

.. code-block:: python3

    @zdc.dataclass
    class MyStruct(zdc.Struct):
        a : int = zdc.field(default=10)
        mem : zdc.Memory[zdc.uint32_t] = zdc.field(size=4096)

input()
=======

Marks a field as an input port. Input fields see the value of their
bound output with no delay.

.. code-block:: python3

    @zdc.dataclass
    class Consumer(zdc.Component):
        clock : zdc.uint1_t = zdc.input()
        data : zdc.uint32_t = zdc.input()

* Top-level inputs are bound to implicit outputs
* Non-top-level inputs must be explicitly bound to outputs

output()
========

Marks a field as an output port. Bound inputs see the current value
with no delay.

.. code-block:: python3

    @zdc.dataclass
    class Producer(zdc.Component):
        clock : zdc.uint1_t = zdc.input()
        data : zdc.uint32_t = zdc.output()

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
of the interface methods.

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

*************
Binding Helper
*************

bind[Ts,Ti]
===========

The ``bind`` helper class provides type-safe binding specifications for
inline field bindings.

.. code-block:: python3

    from typing import Self

    @zdc.dataclass
    class Parent(zdc.Component):
        clock : zdc.uint1_t = zdc.input()
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

Exec / ExecProc
===============

Internal marker types for decorated methods:

* ``Exec`` - Base execution marker
* ``ExecProc`` - Process execution marker (from ``@process``)
