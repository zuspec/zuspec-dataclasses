###########
Constraints
###########

Constraints may be used in many places within a `Zuspec` description
to relate the values of random variables. Constraint methods are 
regular Python methods where all statements are treated as boolean
statements an applied concurrently. In other words, there is no 
procedural order in which the statements are evaluated. All must 
hold 'True'.

*****************
Constraint Blocks
*****************

Constraint blocks are methods decorated with the `constraint` 
decorator. They are legal in randomizable `Zuspec` contexts, 
such as Struct, Action, and Component.

.. code-block:: python3

    import zuspec.dataclasses as zdc

    @zdc.dataclass
    class MyS(zdc.Struct):
      a : int = zdc.field(rand=True)
      b : int = zdc.field(rand=True)

      @zdc.constraint
      def ab_c(self):
        self.a > 0 and self.a < 10
        self.b in range(0,9)
        self.a < self.b

Constraint blocks always apply when the containing scope is randomized.

********************
Constraint Functions
********************

Constraint methods are reusable constraints that only apply once they
have been referenced.

.. code-block:: python3

    import zuspec.dataclasses as zdc

    @zdc.constraint
    def max(rv, v1, v2):
        rv == v1 if v1 > v2 else v2

    @zdc.dataclass
    class MyS(zdc.Struct):
      a : int = zdc.field(rand=True)
      b : int = zdc.field(rand=True)
      c : int = zdc.field(rand=True)

      @zdc.constraint
      def ab_c(self):
        self.a > 0
        self.b in range(0,9)
        self.a < self.b

        if self.b == 5:
          self.a_range_small()

        max(self.c, self.a, self.b)

      @zdc.constraint(fn=True)
      def a_range_small(self):
        self.a i range(0,9)

In the example above, `max` is defined as a standalone constraint function.
The `constraint` decorator determines this based on the presence of 
parameters to the function. A constraint function is considered to have
a boolean result which is the logical `and` of all statements within.

The `max` constraint above equates the three variables to ensure that
the result variable takes the maximum value of the two inputs. Activating
the constraint is done by referencing it within a constraint. It is 
illegal to call a constraint function in procedural code.

The `a_range_small` method is also a constraint function. Because this
function acts on class variables and has no additional parameters, we 
explicitly mark the constraint as being a function (fn=True).

*********************
Constraint Statements
*********************

All constraint statements follow Python syntax, but are interpreted
as boolean statements instead of procedural statements.

Boolean Expressions
*******************

**in** Operator
===============

The `in` operator may be used in constraint expressions. The rhs
expression must be an iterable, and may include:

* **range** function
* a generator function
* a list or tuple

The iterable must be "pure", in the sense that it always returns
the same set given the same inputs.

.. code-block:: python3

    import zuspec.dataclasses as zdc

    class MyS(zdc.Struct):
        a : int = zdc.field(rand=True)

        @zdc.constraint
        def _a_c(self):
            self.a in range(10) # a in 0..9

For
***

* enumerate() support

If/Else
*******

Match
*****




 
        
        
        

