###########
Constraints
###########

Zuspec provides a comprehensive SystemVerilog/PSS-style constraint framework for
declarative specification of constraints on random variables. Constraints are
declared using decorated methods and parsed from Python AST without runtime execution.

**Key Features:**

* Pythonic syntax with statement-based constraints
* Full AST parsing (no runtime execution)
* Support for SystemVerilog and PSS constraint patterns
* Fixed-size arrays with indexing and iterative constraints
* Constraint helper functions (sum, unique, ascending, descending)
* Inline constraints with ``randomize_with``
* Distribution, implication, uniqueness, and solve ordering
* Type-safe with IDE support

***************
Quick Example
***************

.. code-block:: python3

    import zuspec.dataclasses as zdc
    from typing import List

    @zdc.dataclass
    class Packet:
        # Scalar random fields
        length: int = zdc.rand(domain=(64, 1500))
        header_len: int = zdc.rand(domain=(20, 60))
        pkt_type: int = zdc.rand(domain=(0, 3))
        
        # Array random field
        payload: List[int] = zdc.rand(size=8, domain=(0, 255))
        
        # Constraint using helper functions
        @zdc.constraint
        def valid_payload(self):
            assert zdc.unique(self.payload)  # All bytes unique
            assert zdc.sum(self.payload) < 1000  # Checksum limit
        
        # Iterative constraint with for loop
        @zdc.constraint
        def byte_ordering(self):
            for i in range(7):
                assert self.payload[i] < self.payload[i+1]
        
        # Traditional constraints
        @zdc.constraint
        def valid_length(self):
            assert self.length >= self.header_len
    
    # Randomize and use
    pkt = Packet()
    zdc.randomize(pkt, seed=42)
    print(f"Payload: {pkt.payload}, sum={sum(pkt.payload)}")

********************
Random Variables
********************

rand()
======

Declares a random variable that will be assigned a value by the constraint solver.
Supports both scalar fields and fixed-size arrays.

**Scalar Fields:**

.. code-block:: python3

    @zdc.dataclass
    class Transaction:
        # Basic random variable
        addr: int = zdc.rand()
        
        # With domain bounds
        data: int = zdc.rand(domain=(0, 255))
        
        # With explicit bit width
        flags: int = zdc.rand(domain=(0, 15))

**Array Fields:**

.. code-block:: python3

    from typing import List
    
    @zdc.dataclass
    class BufferTransaction:
        # Fixed-size array of 16 random integers
        buffer: List[int] = zdc.rand(size=16, domain=(0, 255))
        
        # Array with wider domain
        values: List[int] = zdc.rand(size=8, domain=(0, 1023))

**Parameters:**

* ``domain`` (tuple, optional) - ``(min, max)`` value bounds (inclusive)
* ``size`` (int, optional) - Array size for List[T] fields
* ``width`` (int or callable, optional) - Bit width for ``bitv`` types

.. note::
   The parameter name changed from ``bounds`` to ``domain`` in recent versions.
   ``domain`` better reflects support for both ranges and discrete value sets.

randc()
=======

Declares a random-cyclic variable that cycles through all values in its domain
before repeating. The solver ensures a permutation is exhausted before generating
a new one.

.. code-block:: python3

    @zdc.dataclass
    class TestSequence:
        # Random-cyclic: cycles through 0-15
        test_id: int = zdc.randc(domain=(0, 15))
        
        @zdc.constraint
        def valid_tests(self):
            # Only IDs 0-11 are valid
            assert self.test_id < 12

**Parameters:**

* Same as ``rand()``
* Currently only supports scalar fields (not arrays)

**********************
Constraint Decorators
**********************

@constraint
===========

Marks a method as a fixed constraint that is always applied during randomization.
Constraints use ``assert`` statement syntax.

.. code-block:: python3

    @zdc.dataclass
    class BusTransaction:
        addr: int = zdc.rand(domain=(0, 255))
        data: int = zdc.rand(domain=(0, 255))
        
        @zdc.constraint
        def addr_aligned(self):
            """Address must be word-aligned"""
            assert self.addr % 4 == 0
        
        @zdc.constraint
        def data_bounds(self):
            """Multiple constraints in one method"""
            assert self.data > 0
            assert self.data < 200

**Statement Syntax:**

Constraints use ``assert`` statement syntax. Multiple assertions are implicitly ANDed:

.. code-block:: python3

    @zdc.constraint
    def bounds_check(self):
        assert self.x >= 0      # Statement 1
        assert self.x < 100     # Statement 2
        assert self.y > self.x  # Statement 3
        # All three must be true

@constraint.generic
===================

Marks a method as a generic constraint that is only applied when explicitly
activated. Used for conditional constraint sets.

.. code-block:: python3

    @zdc.dataclass
    class Packet:
        length: int = zdc.rand(domain=(64, 1500))
        
        @zdc.constraint.generic
        def small_packet(self):
            assert self.length < 256
        
        @zdc.constraint.generic
        def large_packet(self):
            assert self.length >= 1024

Generic constraints can be selectively enabled based on test scenarios.

***********************
Array Constraints
***********************

Arrays are declared using Python's ``List`` type annotation with a fixed size.
Individual array elements can be constrained using indexing.

Array Declaration
=================

.. code-block:: python3

    from typing import List
    
    @zdc.dataclass
    class ArrayExample:
        # Fixed-size array of 8 elements
        buffer: List[int] = zdc.rand(size=8, domain=(0, 255))
        
        # Multiple arrays
        data: List[int] = zdc.rand(size=16, domain=(0, 1023))
        mask: List[int] = zdc.rand(size=16, domain=(0, 1))

Array Indexing
==============

Access individual array elements using subscript notation:

.. code-block:: python3

    @zdc.constraint
    def element_constraints(self):
        # First element must be even
        assert self.buffer[0] % 2 == 0
        
        # Last element larger than first
        assert self.buffer[7] > self.buffer[0]
        
        # Element relationships
        assert self.data[3] == self.data[2] + 1

Computed Indices
================

Use arithmetic expressions in array indices:

.. code-block:: python3

    @zdc.constraint
    def computed_indices(self):
        # Adjacent elements
        for i in range(7):
            assert self.buffer[i] <= self.buffer[i + 1]
        
        # Stride access
        for i in range(4):
            assert self.matrix[i * 3] != 0

Iterative Constraints
=====================

Use Python ``for`` loops to express constraints over array elements:

**Simple Loops:**

.. code-block:: python3

    @zdc.constraint
    def all_positive(self):
        for i in range(8):
            assert self.buffer[i] > 0

**Nested Loops:**

.. code-block:: python3

    @zdc.constraint
    def all_unique(self):
        # Ensure all elements are unique
        for i in range(8):
            for j in range(i + 1, 8):
                assert self.buffer[i] != self.buffer[j]

**Variable-Bounded Loops:**

.. code-block:: python3

    @zdc.dataclass
    class VariableBuffer:
        count: int = zdc.rand(domain=(1, 8))
        buffer: List[int] = zdc.rand(size=8, domain=(0, 100))
        
        @zdc.constraint
        def active_elements(self):
            # Only first 'count' elements constrained
            for i in range(self.count):
                assert self.buffer[i] < 50

**Using len():**

.. code-block:: python3

    @zdc.constraint
    def full_array(self):
        for i in range(len(self.buffer)):
            assert self.buffer[i] != 0

.. note::
   Loops are expanded at parse time, not executed at runtime.
   Variable-bounded loops use implication constraints.

***********************
Constraint Expressions
***********************

Comparison Operators
====================

Standard comparison operators are supported:

.. code-block:: python3

    @zdc.constraint
    def comparisons(self):
        assert self.a < 100          # Less than
        assert self.b <= 100         # Less than or equal
        assert self.c > 0            # Greater than
        assert self.d >= 10          # Greater than or equal
        assert self.e == 50          # Equal
        assert self.f != 0           # Not equal
        assert 0 <= self.g < 100     # Chained comparison

Boolean Operators
=================

Logical operators combine constraint expressions:

.. code-block:: python3

    @zdc.constraint
    def logic(self):
        assert (self.a > 0) and (self.b > 0)     # AND
        assert (self.x < 10) or (self.y < 10)    # OR
        assert not self.flag                      # NOT
        assert not (self.read and self.write)    # NOT of expression

Arithmetic Operators
====================

Arithmetic expressions can be used in constraints:

.. code-block:: python3

    @zdc.constraint
    def arithmetic(self):
        assert self.sum == self.a + self.b
        assert self.diff == self.a - self.b
        assert self.product == self.a * self.b
        assert self.quotient == self.a / self.b
        assert self.remainder == self.a % self.b
        assert self.aligned == (self.addr % 4 == 0)

Set Membership
==============

Use Python's ``in`` operator for set membership:

.. code-block:: python3

    @zdc.constraint
    def membership(self):
        # Value in range [0, 16)
        assert self.x in range(0, 16)
        
        # Value in discrete set
        assert self.type in [0, 1, 2, 5, 7]

Bit Operations
==============

Subscript notation accesses bits and slices:

.. code-block:: python3

    @zdc.constraint
    def bit_ops(self):
        # Bit slice (SystemVerilog style)
        assert self.addr[1:0] == 0
        
        # Single bit
        assert self.flags[0] == 1

*****************
Helper Functions
*****************

Zuspec provides helper functions that expand common constraint patterns into
equivalent loop-based constraints. All helpers expand at parse time with zero
runtime overhead.

sum()
=====

Returns the sum of all elements in an array. Use in expressions and comparisons.

.. code-block:: python3

    from typing import List
    
    @zdc.dataclass
    class Packet:
        payload: List[int] = zdc.rand(size=8, domain=(0, 31))
        checksum: int = zdc.rand(domain=(100, 150))
        
        @zdc.constraint
        def checksum_constraint(self):
            # Sum of payload must equal checksum
            assert zdc.sum(self.payload) == self.checksum
        
        @zdc.constraint
        def bounded_sum(self):
            # Sum must be in range
            assert zdc.sum(self.payload) >= 50
            assert zdc.sum(self.payload) <= 200

**Expansion:**

``sum(arr)`` expands to ``arr[0] + arr[1] + ... + arr[N-1]``

**Works with:**
* Equality: ``sum(arr) == 100``
* Comparisons: ``sum(arr) < 200``, ``sum(arr) >= 50``
* Arithmetic: ``sum(arr) * 2 == target``

unique()
========

Ensures all elements in an array are distinct (no duplicates).

.. code-block:: python3

    @zdc.dataclass
    class IDGenerator:
        ids: List[int] = zdc.rand(size=8, domain=(0, 15))
        
        @zdc.constraint
        def all_unique(self):
            # All IDs must be different
            assert zdc.unique(self.ids)

**Expansion:**

.. code-block:: python3

    # Expands to:
    for i in range(N):
        for j in range(i+1, N):
            assert arr[i] != arr[j]

**Use Cases:**
* Unique identifiers
* Distinct test values
* Permutation generation

ascending()
===========

Constrains array elements to strictly ascending order (each element < next element).

.. code-block:: python3

    @zdc.dataclass
    class SortedSequence:
        sequence: List[int] = zdc.rand(size=6, domain=(0, 100))
        
        @zdc.constraint
        def ordered(self):
            # Elements must be strictly increasing
            assert zdc.ascending(self.sequence)
            
            # Can combine with other constraints
            assert self.sequence[0] >= 10

**Expansion:**

.. code-block:: python3

    # Expands to:
    for i in range(N-1):
        assert arr[i] < arr[i+1]

**Use Cases:**
* Sorted data generation
* Timestamp sequences
* Priority ordering

descending()
============

Constrains array elements to strictly descending order (each element > next element).

.. code-block:: python3

    @zdc.dataclass
    class PriorityQueue:
        priorities: List[int] = zdc.rand(size=5, domain=(0, 50))
        
        @zdc.constraint
        def priority_order(self):
            # Priorities decrease from first to last
            assert zdc.descending(self.priorities)

**Expansion:**

.. code-block:: python3

    # Expands to:
    for i in range(N-1):
        assert arr[i] > arr[i+1]

**Use Cases:**
* Priority queues
* Reverse-sorted data
* Deadline scheduling

Combining Helpers
=================

Multiple helpers can be combined in the same constraint:

.. code-block:: python3

    @zdc.dataclass
    class CombinedExample:
        values: List[int] = zdc.rand(size=5, domain=(1, 30))
        
        @zdc.constraint
        def all_constraints(self):
            assert zdc.unique(self.values)      # All different
            assert zdc.ascending(self.values)   # Sorted order
            assert zdc.sum(self.values) >= 60   # Minimum total

    # Result: 5 unique, ascending values with sum ≥ 60
    # Example: [11, 12, 13, 14, 15] (sum = 65)

implies()
=========

Expresses implication constraints: "if condition, then consequence must hold."

.. code-block:: python3

    @zdc.constraint
    def implications(self):
        # If type is 0, addr must be less than 16
        assert zdc.implies(self.addr_type == 0, self.addr < 16)
        
        # If type is 1, addr must be in range [16, 128)
        assert zdc.implies(self.addr_type == 1, 
                          self.addr in range(16, 128))

**Logical equivalent:** ``implies(a, b)`` is ``(not a) or b``

dist()
======

Specifies weighted distribution for random variables.

**Discrete Values:**

.. code-block:: python3

    @zdc.constraint
    def type_distribution(self):
        zdc.dist(self.pkt_type, {
            0: 40,  # Type 0: 40% weight
            1: 30,  # Type 1: 30% weight
            2: 20,  # Type 2: 20% weight
            3: 10   # Type 3: 10% weight
        })

**Ranges:**

.. code-block:: python3

    @zdc.constraint
    def addr_distribution(self):
        zdc.dist(self.addr, {
            # Weight per value in range
            range(0, 64): (64, 'per_value'),
            
            # Total weight for entire range
            range(64, 192): (128, 'total'),
            
            # Another per-value range
            range(192, 256): (64, 'per_value')
        })

**Weight Types:**

* Integer: Absolute weight for discrete values
* ``(weight, 'per_value')``: Weight per value in range
* ``(weight, 'total')``: Total weight for entire range

solve_order()
=============

Provides a hint to the solver about variable ordering for better constraint
propagation. Variables are solved in the specified order.

.. code-block:: python3

    @zdc.constraint
    def order_hint(self):
        # Solve addr before data
        zdc.solve_order(self.addr, self.data)
        assert self.data == self.addr * 2

Multiple variables can be specified:

.. code-block:: python3

    @zdc.constraint
    def pipeline_order(self):
        # stage1 solved first, then stage2, then stage3
        zdc.solve_order(self.stage1, self.stage2, self.stage3)

***********************
Inline Constraints
***********************

randomize_with
==============

The ``randomize_with`` context manager allows adding constraints inline without
modifying the dataclass definition. Useful for scenario-specific constraints.

**Basic Usage:**

.. code-block:: python3

    @zdc.dataclass
    class Packet:
        length: int = zdc.rand(domain=(64, 1500))
        data: List[int] = zdc.rand(size=8, domain=(0, 255))
    
    pkt = Packet()
    
    # Add inline constraints
    with zdc.randomize_with(pkt):
        assert pkt.length < 256
        assert zdc.sum(pkt.data) == 100

**With Loops:**

.. code-block:: python3

    with zdc.randomize_with(obj):
        # Iterative constraint
        for i in range(8):
            assert obj.buffer[i] > 0
        
        # Nested loops
        for i in range(8):
            for j in range(i+1, 8):
                assert obj.buffer[i] != obj.buffer[j]

**With Helper Functions:**

.. code-block:: python3

    with zdc.randomize_with(obj):
        assert zdc.unique(obj.ids)
        assert zdc.ascending(obj.sequence)
        assert zdc.sum(obj.values) >= 50

**With Seed:**

.. code-block:: python3

    with zdc.randomize_with(obj, seed=42):
        assert obj.x > 10
        assert obj.y < 100

**Combining with Class Constraints:**

Inline constraints are ANDed with any existing ``@constraint`` methods:

.. code-block:: python3

    @zdc.dataclass
    class Transaction:
        addr: int = zdc.rand(domain=(0, 255))
        
        @zdc.constraint
        def aligned(self):
            assert self.addr % 4 == 0
    
    txn = Transaction()
    
    # Both constraints apply
    with zdc.randomize_with(txn):
        assert txn.addr < 128  # Additional constraint
    
    # Result: addr is word-aligned AND < 128

*********************
Parsing Constraints
*********************

ConstraintParser
================

Extracts and parses constraint methods from dataclasses. Converts constraint
expressions to IR-compatible dictionary representation.

.. code-block:: python3

    from zuspec.dataclasses import ConstraintParser
    
    @zdc.dataclass
    class Transaction:
        addr: int = zdc.rand(bounds=(0, 255), default=0)
        
        @zdc.constraint
        def aligned(self):
            self.addr % 4 == 0
    
    # Parse constraints
    parser = ConstraintParser()
    constraints = parser.extract_constraints(Transaction)
    
    for c in constraints:
        print(f"Constraint: {c['name']}")
        print(f"  Kind: {c['kind']}")  # 'fixed' or 'generic'
        print(f"  Expressions: {len(c['exprs'])}")

extract_rand_fields()
=====================

Extracts all random and random-cyclic fields from a dataclass with their metadata.

.. code-block:: python3

    from zuspec.dataclasses import extract_rand_fields
    
    @zdc.dataclass
    class Packet:
        length: int = zdc.rand(bounds=(64, 1500), default=64)
        test_id: int = zdc.randc(bounds=(0, 15), default=0)
    
    # Extract random fields
    rand_fields = extract_rand_fields(Packet)
    
    for f in rand_fields:
        print(f"Field: {f['name']}")
        print(f"  Kind: {f['kind']}")  # 'rand' or 'randc'
        if 'bounds' in f:
            print(f"  Bounds: {f['bounds']}")

*******************
Complete Example
*******************

.. code-block:: python3

    import zuspec.dataclasses as zdc
    from typing import List

    @zdc.dataclass
    class NetworkPacket:
        """Network packet with comprehensive constraints"""
        
        # Scalar random fields
        packet_type: int = zdc.rand(domain=(0, 3))
        priority: int = zdc.rand(domain=(0, 7))
        length: int = zdc.rand(domain=(64, 1500))
        
        # Array random fields
        header: List[int] = zdc.rand(size=4, domain=(0, 255))
        payload: List[int] = zdc.rand(size=16, domain=(0, 255))
        
        # Basic constraints
        @zdc.constraint
        def valid_length(self):
            """Length must accommodate header + payload"""
            assert self.length >= 64
        
        @zdc.constraint
        def priority_rules(self):
            """High-priority packets use specific types"""
            assert zdc.implies(self.priority >= 6, 
                              self.packet_type in [0, 1])
        
        # Array constraints with helpers
        @zdc.constraint
        def payload_constraints(self):
            """Payload must be unique and checksum bounded"""
            assert zdc.unique(self.payload)
            assert zdc.sum(self.payload) < 2000
        
        # Iterative constraint
        @zdc.constraint
        def header_ordering(self):
            """Header bytes must be ascending"""
            for i in range(3):
                assert self.header[i] < self.header[i+1]
        
        # Generic constraint
        @zdc.constraint.generic
        def small_packet(self):
            """Generic: restrict to small packets"""
            assert self.length < 256
    
    # Create and randomize
    pkt = NetworkPacket()
    zdc.randomize(pkt, seed=42)
    
    print(f"Type: {pkt.packet_type}, Priority: {pkt.priority}")
    print(f"Header: {pkt.header}")
    print(f"Payload sum: {sum(pkt.payload)}")
    
    # Randomize with inline constraints
    pkt2 = NetworkPacket()
    with zdc.randomize_with(pkt2, seed=123):
        assert pkt2.priority == 7  # Force high priority
        assert zdc.ascending(pkt2.payload)  # Sorted payload
    
    print(f"High-priority packet: {pkt2.priority}")
    print(f"Sorted payload: {pkt2.payload}")

*********************
Supported Patterns
*********************

Constraint Language Coverage
=============================

**SystemVerilog:**

* ✅ Basic constraints (comparisons, arithmetic)
* ✅ Logical operators (``and``, ``or``, ``not``)
* ✅ Set membership (``in range()``)
* ✅ Implication (``implies()``)
* ✅ Distribution (``dist()``)
* ✅ Uniqueness (``unique()``)
* ✅ Solve ordering (``solve_order()``)
* ✅ Random-cyclic variables (``randc()``)
* ✅ Array constraints (fixed-size with indexing)
* ✅ Iterative constraints (``for`` loops with ranges)
* ✅ Helper functions (``sum``, ``unique``, ``ascending``, ``descending``)
* ⏳ Variable-size arrays (future)
* ⏳ Jagged arrays (future)

**PSS (Portable Stimulus Standard):**

* ✅ Fixed constraints (``@constraint``)
* ✅ Generic constraints (``@constraint.generic``)
* ✅ Inline constraints (``randomize_with``)
* ⏳ Parameterized generics (future)
* ⏳ Activity constraints (future)
* ⏳ Action fields (future)

*****************
Design Notes
*****************

AST-Based Parsing
=================

Constraints are **never executed at runtime**. They are parsed from Python AST,
enabling:

* Static analysis and validation
* Code generation to other languages
* Type checking without execution
* IDE support and autocomplete

Statement-Based Syntax
======================

Unlike functions that return boolean expressions, constraints use statement syntax
with explicit ``assert`` where each statement is implicitly ANDed:

.. code-block:: python3

    @zdc.constraint
    def bounds(self):
        assert self.x >= 0       # Statement 1
        assert self.x < 100      # Statement 2
        # Equivalent to: (self.x >= 0) and (self.x < 100)

This matches SystemVerilog and PSS syntax patterns.

Future Extensions
=================

Planned enhancements include:

* **Variable-size arrays** - Arrays with runtime-determined length
* **Soft constraints** - Preferences that guide but don't restrict solutions
* **Parameterized generics** - Generic constraints with parameters
* **Activity constraints** - PSS-specific activity and action constraints
* **Additional helpers** - sorted(), product(), count(), min(), max()
* **Optimization** - Constraint propagation and caching
