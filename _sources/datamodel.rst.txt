################################
Data Model (Developer)
################################

The ``zuspec.dataclasses.dm`` module defines a type model for representing
Zuspec descriptions. This data model is used by tools that analyze, transform,
or generate code from Zuspec models.

*******
Context
*******

``Context`` is the container for all type definitions in a data model.

.. code-block:: python3

    from zuspec.dataclasses.dm import Context

    ctx = Context()
    # type_m maps qualified type names to DataType instances
    ctx.type_m["MyModule.MyComponent"] = data_type

**********
Data Types
**********

The data type hierarchy represents different kinds of types in Zuspec.

DataType (Base)
===============

Base class for all data types.

.. code-block:: python3

    @dataclass
    class DataType(Base):
        name: Optional[str]      # Qualified type name
        py_type: Optional[Any]   # Reference to original Python type

DataTypeInt
===========

Integer types with width and signedness.

.. code-block:: python3

    @dataclass
    class DataTypeInt(DataType):
        bits: int = -1      # Bit width (-1 for default)
        signed: bool = True

DataTypeStruct
==============

Pure-data types with fields and optional methods.

.. code-block:: python3

    @dataclass
    class DataTypeStruct(DataType):
        super: Optional[DataType]  # Base type
        fields: List[Field]        # Field definitions
        functions: List[Function]  # Methods

DataTypeClass
=============

Polymorphic extension of struct (supports inheritance).

DataTypeComponent
=================

Structural building blocks with ports, exports, and bindings.

.. code-block:: python3

    @dataclass
    class DataTypeComponent(DataTypeClass):
        bind_map: List[Bind]  # Port/export connections

DataTypeProtocol
================

Interface definitions (Python Protocol types).

.. code-block:: python3

    @dataclass
    class DataTypeProtocol(DataType):
        methods: List[Function]  # Interface methods

Other Data Types
================

* ``DataTypeString`` - String type
* ``DataTypeEnum`` - Enumeration type
* ``DataTypeLock`` - Mutex lock type
* ``DataTypeMemory`` - Memory storage type (with element_type, size)
* ``DataTypeAddressSpace`` - Address space type
* ``DataTypeAddrHandle`` - Memory access handle
* ``DataTypeRef`` - Forward reference to type by name
* ``DataTypeExpr`` - Type defined by expression

******
Fields
******

Field
=====

Represents a field in a struct/class/component.

.. code-block:: python3

    @dataclass
    class Field(Base):
        name: str
        datatype: DataType
        kind: FieldKind = FieldKind.Field
        bindset: BindSet

FieldKind
=========

Enumeration of field kinds:

* ``FieldKind.Field`` - Regular data field
* ``FieldKind.Port`` - API consumer (requires binding)
* ``FieldKind.Export`` - API provider

FieldInOut
==========

Input/output field with direction.

.. code-block:: python3

    @dataclass
    class FieldInOut(Field):
        is_out: bool  # True for output, False for input

********
Bindings
********

Bind
====

Single binding between two expressions.

.. code-block:: python3

    @dataclass
    class Bind(Base):
        lhs: Expr  # Target (port, export method)
        rhs: Expr  # Source (export, method)

BindSet
=======

Collection of bindings for a field.

.. code-block:: python3

    @dataclass
    class BindSet(Base):
        binds: List[Bind]

***********
Expressions
***********

Expression types represent values and references in the data model.

Core Expression Types
=====================

``Expr``
    Base class for all expressions.

``ExprConstant``
    Literal value.

    .. code-block:: python3

        @dataclass
        class ExprConstant(Expr):
            value: object
            kind: Optional[str]  # Type hint

``ExprBin``
    Binary operation.

    .. code-block:: python3

        @dataclass
        class ExprBin(Expr):
            lhs: Expr
            op: BinOp
            rhs: Expr

``ExprUnary``
    Unary operation.

``ExprBool``
    Boolean operation (and/or) with multiple values.

``ExprCompare``
    Comparison with chained operators.

Reference Expressions
=====================

``ExprRef``
    Base for reference expressions.

``TypeExprRefSelf``
    Reference to ``self``.

``ExprRefField``
    Reference to a field relative to base expression.

    .. code-block:: python3

        @dataclass
        class ExprRefField(ExprRef):
            base: Expr   # Base expression (e.g., TypeExprRefSelf)
            index: int   # Field index

``ExprRefPy``
    Reference to a Python attribute.

    .. code-block:: python3

        @dataclass
        class ExprRefPy(ExprRef):
            base: Expr
            ref: str  # Attribute name

``ExprRefBottomUp``
    Reference relative to procedural scope.

Access Expressions
==================

``ExprAttribute``
    Attribute access (``obj.attr``).

``ExprSubscript``
    Subscript access (``obj[key]``).

``ExprSlice``
    Slice specification (``lower:upper:step``).

``ExprCall``
    Function/method call.

    .. code-block:: python3

        @dataclass
        class ExprCall(Expr):
            func: Expr
            args: List[Expr]
            keywords: List[Keyword]

Operators
=========

``BinOp``
    Binary operators: Add, Sub, Mult, Div, Mod, BitAnd, BitOr, BitXor, 
    LShift, RShift, Eq, NotEq, Lt, LtE, Gt, GtE, And, Or

``UnaryOp``
    Unary operators: Invert, Not, UAdd, USub

``BoolOp``
    Boolean operators: And, Or

``CmpOp``
    Comparison operators: Eq, NotEq, Lt, LtE, Gt, GtE, Is, IsNot, In, NotIn

``AugOp``
    Augmented assignment operators: Add, Sub, Mult, Div, Mod, Pow, 
    LShift, RShift, BitAnd, BitOr, BitXor, FloorDiv

Extended Expressions
====================

From ``expr_phase2.py``:

* ``ExprList``, ``ExprTuple``, ``ExprDict``, ``ExprSet`` - Collection literals
* ``ExprListComp``, ``ExprDictComp``, ``ExprSetComp`` - Comprehensions
* ``ExprGeneratorExp`` - Generator expression
* ``ExprIfExp`` - Conditional expression (ternary)
* ``ExprLambda`` - Lambda expression
* ``ExprNamedExpr`` - Walrus operator (``:=``)
* ``ExprJoinedStr``, ``ExprFormattedValue`` - F-string support

**********
Statements
**********

Statement types represent executable code in the data model.

Core Statements
===============

``Stmt``
    Base class for statements.

``StmtExpr``
    Expression statement.

``StmtAssign``
    Assignment (``targets = value``).

``StmtAugAssign``
    Augmented assignment (``target += value``).

``StmtReturn``
    Return statement.

``StmtPass``
    Pass statement.

Control Flow
============

``StmtIf``
    Conditional with test, body, and orelse.

``StmtFor``
    For loop with target, iter, body, and orelse.

``StmtWhile``
    While loop.

``StmtBreak``, ``StmtContinue``
    Loop control.

``StmtMatch``, ``StmtMatchCase``
    Pattern matching (Python 3.10+).

Exception Handling
==================

``StmtRaise``
    Raise exception.

``StmtAssert``
    Assertion.

``StmtTry``, ``StmtExceptHandler``
    Try/except blocks.

``StmtWith``, ``WithItem``
    Context manager.

*******************
Functions & Methods
*******************

Function
========

Represents a method or standalone function.

.. code-block:: python3

    @dataclass
    class Function(Base):
        name: str
        args: Arguments
        body: List[Stmt]
        returns: Optional[DataType]
        is_async: bool

Process
=======

Represents a ``@process`` decorated method.

.. code-block:: python3

    @dataclass
    class Process(Base):
        name: str
        body: List[Stmt]

Arguments
=========

Function argument specification.

.. code-block:: python3

    @dataclass
    class Arguments(Base):
        args: List[Arg]
        # Plus: posonlyargs, kwonlyargs, vararg, kwarg, defaults, kw_defaults

Arg
===

Single argument.

.. code-block:: python3

    @dataclass
    class Arg(Base):
        arg: str                    # Argument name
        annotation: Optional[Expr]  # Type annotation

*******
Visitor
*******

The ``Visitor`` class provides the visitor pattern for traversing data models.

.. code-block:: python3

    from zuspec.dataclasses import dm

    @dm.visitor(__name__)
    class MyVisitor(dm.Visitor):
        def visitDataTypeComponent(self, obj: dm.DataTypeComponent):
            # Process component type
            for field in obj.fields:
                field.accept(self)
        
        def visitField(self, obj: dm.Field):
            # Process field
            pass

The ``@dm.visitor(pmod)`` decorator builds visitor method dispatch based
on the profile registry. Unimplemented visit methods default to ``visitBase``.

*************
JsonConverter
*************

``JsonConverter`` provides serialization support for data models.

.. code-block:: python3

    from zuspec.dataclasses import dm

    @dm.json_converter(__name__)
    class MyConverter(dm.JsonConverter):
        pass

****************
DataModelFactory
****************

``DataModelFactory`` converts Python Zuspec types into data model representations.

.. code-block:: python3

    from zuspec.dataclasses import DataModelFactory

    factory = DataModelFactory()
    context = factory.build([MyComponent, MyProtocol])
    
    # Access type definitions
    comp_type = context.type_m["MyComponent"]

Key Methods
===========

``build(types) -> Context``
    Build a Context containing data models for the given types.
    Handles single types or iterables.

Internal Processing
===================

* ``_process_type(t)`` - Dispatch to appropriate type processor
* ``_process_component(t)`` - Create DataTypeComponent
* ``_process_protocol(t)`` - Create DataTypeProtocol
* ``_process_dataclass(t)`` - Create DataTypeStruct
* ``_extract_fields(t)`` - Extract Field list from dataclass
* ``_extract_bind_map(t)`` - Evaluate ``__bind__`` to capture bindings
* ``_extract_method_body(cls, name)`` - Parse method AST to statements

Bind Map Extraction
===================

The factory uses proxy objects to evaluate ``__bind__`` methods:

1. Create ``_BindProxy`` with field indices and types
2. Call ``__bind__(proxy)`` to get binding dict
3. Convert proxy paths to ``ExprRefField`` expressions
4. Build ``Bind`` entries for each mapping

***************
Profile System
***************

The ``dm`` module uses a profile system for extensibility.

.. code-block:: python3

    from zuspec.dataclasses import dm

    # Register a profile (extends base dm)
    dm.profile(__name__, super="zuspec.dataclasses.dm")

Profiles track which data model classes exist, enabling the Visitor
to generate appropriate dispatch methods.

