###########
Constraints
###########

Zuspec provides a SystemVerilog/PSS-style constraint framework for declarative
specification of constraints on random variables. Constraints are declared using
decorated methods and parsed from Python AST without runtime execution.

**Key Features:**

* Pythonic syntax with statement-based constraints
* Full AST parsing (no runtime execution)
* Support for SystemVerilog and PSS constraint patterns
* Fixed and generic constraints
* Distribution, implication, uniqueness, and solve ordering
* Type-safe with IDE support

***************
Quick Example
***************

.. code-block:: python3

    import zuspec.dataclasses as zdc

    @zdc.dataclass
    class Packet:
        # Random fields
        length: int = zdc.rand(bounds=(64, 1500), default=64)
        header_len: int = zdc.rand(bounds=(20, 60), default=20)
        pkt_type: int = zdc.rand(bounds=(0, 3), default=0)
        
        # Fixed constraint (always applied)
        @zdc.constraint
        def valid_length(self):
            self.length >= self.header_len
        
        # Distribution constraint
        @zdc.constraint
        def type_distribution(self):
            zdc.dist(self.pkt_type, {
                0: 40,  # 40% weight
                1: 30,  # 30% weight
                2: 20,  # 20% weight
                3: 10   # 10% weight
            })
        
        # Generic constraint (conditionally applied)
        @zdc.constraint.generic
        def small_packet(self):
            self.length < 256

********************
Random Variables
********************

rand()
======

Declares a random variable that will be assigned a value by the constraint solver.

.. code-block:: python3

    @zdc.dataclass
    class Transaction:
        # Basic random variable
        addr: int = zdc.rand(default=0)
        
        # With bounds
        data: int = zdc.rand(bounds=(0, 255), default=0)
        
        # Random array
        buffer: int = zdc.rand(size=16, default=0)

**Parameters:**

* ``bounds`` (tuple, optional) - ``(min, max)`` value bounds
* ``default`` (any) - Default value when not randomized
* ``size`` (int, optional) - Array size for vector fields
* ``width`` (int or callable, optional) - Bit width for ``bitv`` types

randc()
=======

Declares a random-cyclic variable that cycles through all values in its domain
before repeating. The solver ensures a permutation is exhausted before generating
a new one.

.. code-block:: python3

    @zdc.dataclass
    class TestSequence:
        # Random-cyclic: cycles through 0-15
        test_id: int = zdc.randc(bounds=(0, 15), default=0)
        
        @zdc.constraint
        def valid_tests(self):
            # Only IDs 0-11 are valid
            self.test_id < 12

**Parameters:**

* Same as ``rand()``

**********************
Constraint Decorators
**********************

@constraint
===========

Marks a method as a fixed constraint that is always applied during randomization.

.. code-block:: python3

    @zdc.dataclass
    class BusTransaction:
        addr: int = zdc.rand(bounds=(0, 255), default=0)
        data: int = zdc.rand(default=0)
        
        @zdc.constraint
        def addr_aligned(self):
            """Address must be word-aligned"""
            self.addr % 4 == 0

**Statement Syntax:**

Constraints use statement syntax (not returns). Multiple statements are implicitly ANDed:

.. code-block:: python3

    @zdc.constraint
    def bounds_check(self):
        self.x >= 0      # Statement 1
        self.x < 100     # Statement 2
        self.y > self.x  # Statement 3
        # All three must be true

@constraint.generic
===================

Marks a method as a generic constraint that is only applied when explicitly
activated. Used for conditional constraint sets.

.. code-block:: python3

    @zdc.dataclass
    class Packet:
        length: int = zdc.rand(bounds=(64, 1500), default=64)
        
        @zdc.constraint.generic
        def small_packet(self):
            self.length < 256
        
        @zdc.constraint.generic
        def large_packet(self):
            self.length >= 1024

Generic constraints can be selectively enabled based on test scenarios.

***********************
Constraint Expressions
***********************

Comparison Operators
====================

Standard comparison operators are supported:

.. code-block:: python3

    @zdc.constraint
    def comparisons(self):
        self.a < 100          # Less than
        self.b <= 100         # Less than or equal
        self.c > 0            # Greater than
        self.d >= 10          # Greater than or equal
        self.e == 50          # Equal
        self.f != 0           # Not equal
        0 <= self.g < 100     # Chained comparison

Boolean Operators
=================

Logical operators combine constraint expressions:

.. code-block:: python3

    @zdc.constraint
    def logic(self):
        (self.a > 0) and (self.b > 0)     # AND
        (self.x < 10) or (self.y < 10)    # OR
        not self.flag                      # NOT
        not (self.read and self.write)    # NOT of expression

Arithmetic Operators
====================

Arithmetic expressions can be used in constraints:

.. code-block:: python3

    @zdc.constraint
    def arithmetic(self):
        self.sum == self.a + self.b
        self.diff == self.a - self.b
        self.product == self.a * self.b
        self.quotient == self.a / self.b
        self.remainder == self.a % self.b
        self.aligned == (self.addr % 4 == 0)

Set Membership
==============

Use Python's ``in`` operator for set membership:

.. code-block:: python3

    @zdc.constraint
    def membership(self):
        # Value in range [0, 16)
        self.x in range(0, 16)
        
        # Value in discrete set
        self.type in [0, 1, 2, 5, 7]

Bit Operations
==============

Subscript notation accesses bits and slices:

.. code-block:: python3

    @zdc.constraint
    def bit_ops(self):
        # Bit slice (SystemVerilog style)
        self.addr[1:0] == 0
        
        # Single bit
        self.flags[0] == 1

*****************
Helper Functions
*****************

implies()
=========

Expresses implication constraints: "if condition, then consequence must hold."

.. code-block:: python3

    @zdc.constraint
    def implications(self):
        # If type is 0, addr must be less than 16
        zdc.implies(self.addr_type == 0, self.addr < 16)
        
        # If type is 1, addr must be in range [16, 128)
        zdc.implies(self.addr_type == 1, 
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

unique()
========

Constrains a set of variables to have unique values.

.. code-block:: python3

    @zdc.dataclass
    class IDGenerator:
        id1: int = zdc.rand(bounds=(0, 15), default=0)
        id2: int = zdc.rand(bounds=(0, 15), default=0)
        id3: int = zdc.rand(bounds=(0, 15), default=0)
        
        @zdc.constraint
        def all_unique(self):
            zdc.unique([self.id1, self.id2, self.id3])

**Alternative:** Explicit pairwise constraints:

.. code-block:: python3

    @zdc.constraint
    def all_unique_explicit(self):
        self.id1 != self.id2
        self.id1 != self.id3
        self.id2 != self.id3

solve_order()
=============

Provides a hint to the solver about variable ordering for better constraint
propagation. Variables are solved in the specified order.

.. code-block:: python3

    @zdc.constraint
    def order_hint(self):
        # Solve addr before data
        zdc.solve_order(self.addr, self.data)
        self.data == self.addr * 2

Multiple variables can be specified:

.. code-block:: python3

    @zdc.constraint
    def pipeline_order(self):
        # stage1 solved first, then stage2, then stage3
        zdc.solve_order(self.stage1, self.stage2, self.stage3)

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

    @zdc.dataclass
    class BusTransaction:
        """Bus transaction with comprehensive constraints"""
        
        # Random fields
        addr: int = zdc.rand(bounds=(0, 255), default=0)
        data: int = zdc.rand(bounds=(0, 255), default=0)
        read_enable: int = zdc.rand(default=0)
        write_enable: int = zdc.rand(default=0)
        addr_type: int = zdc.rand(bounds=(0, 2), default=0)
        
        # Fixed constraints
        @zdc.constraint
        def not_both_rw(self):
            """Cannot read and write simultaneously"""
            not (self.read_enable and self.write_enable)
        
        @zdc.constraint
        def at_least_one(self):
            """Must have read or write enabled"""
            self.read_enable or self.write_enable
        
        @zdc.constraint
        def addr_aligned(self):
            """Address must be word-aligned"""
            self.addr % 4 == 0
        
        @zdc.constraint
        def addr_type_ranges(self):
            """Address type determines address range"""
            zdc.implies(self.addr_type == 0, 
                       self.addr in range(0, 64))
            zdc.implies(self.addr_type == 1, 
                       self.addr in range(64, 192))
            zdc.implies(self.addr_type == 2, 
                       self.addr in range(192, 256))
        
        @zdc.constraint
        def solve_order_hint(self):
            """Solve address before data"""
            zdc.solve_order(self.addr, self.data)
        
        # Generic constraints
        @zdc.constraint.generic
        def low_addr(self):
            """Generic: restrict to low addresses"""
            self.addr < 128
    
    # Parse the constraints
    parser = zdc.ConstraintParser()
    constraints = parser.extract_constraints(BusTransaction)
    rand_fields = zdc.extract_rand_fields(BusTransaction)
    
    print(f"Found {len(constraints)} constraints")
    print(f"Found {len(rand_fields)} random fields")

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
* ⏳ Array constraints (``for`` loops - future)

**PSS (Portable Stimulus Standard):**

* ✅ Fixed constraints (``@constraint``)
* ✅ Generic constraints (``@constraint.generic``)
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
where each statement is implicitly ANDed:

.. code-block:: python3

    @zdc.constraint
    def bounds(self):
        self.x >= 0       # Statement 1
        self.x < 100      # Statement 2
        # Equivalent to: (self.x >= 0) and (self.x < 100)

This matches SystemVerilog and PSS syntax patterns.

Future Extensions
=================

Planned enhancements include:

* **Soft constraints** - Preferences that guide but don't restrict solutions
* **Array constraints** - ``for`` loop support for constraining arrays
* **Parameterized generics** - Generic constraints with parameters
* **Activity constraints** - PSS-specific activity and action constraints
* **Optimization** - Constraint propagation and caching
