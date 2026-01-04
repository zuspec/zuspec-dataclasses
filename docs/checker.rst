Zuspec IR Checker
=================

Overview
--------

The Zuspec IR Checker is an extensible validation framework that checks your Zuspec code by analyzing the Intermediate Representation (IR). Unlike traditional type checkers that work at the AST level, the IR checker validates the *semantic* model of your code, ensuring it conforms to profile-specific rules.

**Key Features:**

* **IR-based validation** - Checks compiled IR, not raw Python AST
* **Profile-aware** - Different rules for different abstraction levels
* **Extensible** - Plugins can register custom checkers via entrypoints
* **Flake8 integration** - Works seamlessly with existing tools
* **VSCode support** - Real-time error highlighting in the editor

Architecture
------------

The checker uses a three-layer architecture:

1. **Flake8 Plugin** (``zuspec_flake8``) - Entry point that hooks into flake8
2. **Core Checker** (``IRChecker``) - Builds IR and dispatches to profile checkers  
3. **Profile Checkers** - Validate IR nodes according to profile rules

.. code-block:: text

    Flake8 → ZuspecFlake8Plugin → IRChecker → Profile Checker
                                     ↓
                                   IR Model
                                     ↓
                            Source Locations

Installation and Setup
----------------------

Basic Installation
~~~~~~~~~~~~~~~~~~

The checker is included with ``zuspec-dataclasses``:

.. code-block:: bash

    pip install zuspec-dataclasses
    # or
    uv pip install zuspec-dataclasses

The flake8 plugin is automatically registered via entrypoints.

Configuration
~~~~~~~~~~~~~

Configure in your ``pyproject.toml``:

.. code-block:: toml

    [tool.flake8]
    max-line-length = 100
    extend-ignore = ["E203", "W503"]
    
    [tool.zuspec]
    # Package roots for IR compilation
    package_roots = [
        "src",
        "tests"
    ]

**Configuration Options:**

* ``package_roots`` - List of directories containing your Zuspec packages. The checker needs to know where to find modules for import resolution during IR compilation.

VSCode Integration
~~~~~~~~~~~~~~~~~~

1. **Install the Python extension** (if not already installed)

2. **Install flake8** in your project environment:

   .. code-block:: bash

       uv pip install flake8

3. **Configure VSCode settings** in ``.vscode/settings.json``:

   .. code-block:: json

       {
           "python.linting.enabled": true,
           "python.linting.flake8Enabled": true,
           "python.linting.flake8Path": "packages/python/bin/flake8",
           "python.linting.lintOnSave": true
       }

4. **Reload VSCode window**: Press ``Ctrl+Shift+P`` and select "Developer: Reload Window"

After setup, Zuspec errors will appear with red squiggles in the editor:

.. image:: screenshots/vscode_zuspec_error.png
   :alt: VSCode showing Zuspec error on line 32

Error Codes
-----------

The checker produces errors with codes ``ZDC001`` through ``ZDC006``:

ZDC001: Width Annotation Required
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integer fields must have explicit width annotations in retargetable code.

**Bad:**

.. code-block:: python

    @zdc.dataclass
    class Counter(zdc.Component):
        count: int = zdc.field()  # Error: infinite-width int

**Good:**

.. code-block:: python

    @zdc.dataclass
    class Counter(zdc.Component):
        count: zdc.uint32_t = zdc.field()  # OK: explicit width

ZDC002: Non-Zuspec Type
~~~~~~~~~~~~~~~~~~~~~~~

Fields must use Zuspec types (Component, Struct, width-annotated integers).

**Bad:**

.. code-block:: python

    @zdc.dataclass
    class MyComponent(zdc.Component):
        data: object = zdc.field()  # Error: not a Zuspec type

**Good:**

.. code-block:: python

    @zdc.dataclass
    class MyComponent(zdc.Component):
        data: zdc.uint8_t = zdc.field()  # OK: Zuspec type

ZDC003: Unannotated Variable
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Variables in process/sync/comb methods must have type annotations.

**Bad:**

.. code-block:: python

    @zdc.sync(clock=lambda s: s.clock)
    def process(self):
        x = 5  # Error: no type annotation

**Good:**

.. code-block:: python

    @zdc.sync(clock=lambda s: s.clock)
    def process(self):
        x: zdc.uint8_t = 5  # OK: annotated

ZDC004: Type Annotation Error
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Type annotations must be valid and resolvable.

**Bad:**

.. code-block:: python

    @zdc.dataclass
    class MyComponent(zdc.Component):
        data: NonexistentType = zdc.field()  # Error: undefined type

**Good:**

.. code-block:: python

    @zdc.dataclass
    class MyComponent(zdc.Component):
        data: zdc.uint16_t = zdc.field()  # OK: valid type

ZDC005: Non-Zuspec Constructor Call
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Constructors in retargetable code must be for Zuspec types.

**Bad:**

.. code-block:: python

    def build(self):
        obj = object()  # Error: Python object() not allowed

**Good:**

.. code-block:: python

    def build(self):
        obj = MyComponent()  # OK: Zuspec Component

ZDC006: Forbidden Function Call
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Some Python functions are not allowed in retargetable code.

**Bad:**

.. code-block:: python

    def process(self):
        if hasattr(self, 'optional'):  # Error: dynamic introspection
            pass

**Good:**

.. code-block:: python

    def process(self):
        if self.enabled:  # OK: static attribute access
            pass

Built-in Profiles
-----------------

PythonProfile
~~~~~~~~~~~~~

The most permissive profile, allows all Python constructs.

**Use when:**

* Writing pure Python implementations
* Prototyping before targeting hardware
* Testing with maximum flexibility

**Allows:**

* Infinite-width integers (``int``)
* Dynamic operations (``hasattr``, ``getattr``, ``setattr``)
* Unannotated variables
* ``Any`` and ``object`` types

**Example:**

.. code-block:: python

    @zdc.dataclass(profile=profiles.PythonProfile)
    class FlexibleModel:
        count: int = zdc.field(default=0)  # OK in Python profile
        
        def process(self):
            x = 5  # Unannotated OK
            if hasattr(self, 'optional'):  # Dynamic access OK
                return getattr(self, 'optional')

RetargetableProfile
~~~~~~~~~~~~~~~~~~~

The default profile for hardware-targetable code.

**Use when:**

* Writing code for synthesis or compilation
* Targeting multiple backends (Verilog, C++, etc.)
* Need strong type safety

**Requires:**

* Width-annotated integer types
* Concrete types (no ``Any`` or ``object``)
* Type annotations on all variables
* Static attribute access

**Example:**

.. code-block:: python

    @zdc.dataclass  # Uses RetargetableProfile by default
    class Counter(zdc.Component):
        count: zdc.uint32_t = zdc.output()
        
        @zdc.sync(clock=lambda s: s.clock)
        def increment(self):
            next_val: zdc.uint32_t = self.count + 1  # Annotation required
            self.count = next_val

Profile Auto-Detection
----------------------

The checker automatically detects which profile applies to each class by examining its type hierarchy:

.. code-block:: python

    @zdc.dataclass
    class MyComponent(zdc.Component):  # Auto-detected as Retargetable
        data: zdc.uint8_t = zdc.field()
    
    @zdc.dataclass(profile=profiles.PythonProfile)
    class MyPythonClass:  # Explicitly Python profile
        data: int = zdc.field()

Creating Custom Checkers
-------------------------

You can extend the checker system with custom profile checkers.

Step 1: Create Profile and Checker Classes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    # my_checker_plugin/profiles.py
    from zuspec.dataclasses.profiles import Profile
    from zuspec.dataclasses.ir_checker import ProfileChecker
    from zuspec.dataclasses.ir.base import Field, DataTypeInt
    
    class MyCustomProfile(Profile):
        """Custom profile with specific rules."""
        pass
    
    class MyCustomChecker(ProfileChecker):
        """Checker that validates MyCustomProfile rules."""
        
        def check_field(self, field: Field, context) -> list:
            """Validate field types."""
            errors = []
            
            # Example: Only allow 32-bit integers
            if isinstance(field.datatype, DataTypeInt):
                if field.datatype.bits != 32:
                    errors.append({
                        'line': field.loc.line if field.loc else 1,
                        'col': field.loc.pos if field.loc else 0,
                        'code': 'ZDC101',
                        'message': f"Field '{field.name}' must be 32-bit"
                    })
            
            return errors

Step 2: Register via Entrypoint
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In your plugin's ``pyproject.toml``:

.. code-block:: toml

    [project.entry-points."zuspec.checkers"]
    my_custom = "my_checker_plugin:MyCustomProfile:MyCustomChecker"

The format is: ``name = "module:ProfileClass:CheckerClass"``

Step 3: Install and Use
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    pip install my-checker-plugin

The checker is now automatically available:

.. code-block:: python

    from my_checker_plugin.profiles import MyCustomProfile
    
    @zdc.dataclass(profile=MyCustomProfile)
    class MyComponent(zdc.Component):
        value: zdc.uint32_t = zdc.field()  # OK
        # bad: zdc.uint16_t = zdc.field()  # Would fail with ZDC101

Checker Extension API
---------------------

ProfileChecker Base Class
~~~~~~~~~~~~~~~~~~~~~~~~~

All custom checkers should inherit from ``ProfileChecker``:

.. code-block:: python

    from zuspec.dataclasses.ir_checker import ProfileChecker
    from zuspec.dataclasses.ir.base import (
        Component, Field, Function, Statement
    )
    
    class MyChecker(ProfileChecker):
        
        def check_component(self, component: Component) -> list:
            """Check a component definition."""
            return []  # Return list of error dicts
        
        def check_field(self, field: Field, context) -> list:
            """Check a field definition."""
            return []
        
        def check_function(self, function: Function, context) -> list:
            """Check a function/method definition."""
            return []
        
        def check_statement(self, stmt: Statement, context) -> list:
            """Check a statement in a function body."""
            return []

Error Format
~~~~~~~~~~~~

Errors should be dictionaries with these keys:

.. code-block:: python

    {
        'line': int,        # Source line number (1-indexed)
        'col': int,         # Column offset (0-indexed)
        'code': str,        # Error code (e.g., 'ZDC001')
        'message': str      # Human-readable description
    }

Reusing Core Infrastructure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Custom checkers can leverage core utilities:

.. code-block:: python

    from zuspec.dataclasses.ir_checker import (
        is_zuspec_type,      # Check if type is Zuspec-compatible
        get_type_width,      # Extract width from annotated int
        resolve_type,        # Resolve type references
    )
    
    class MyChecker(ProfileChecker):
        def check_field(self, field: Field, context) -> list:
            if not is_zuspec_type(field.datatype):
                return [{
                    'line': field.loc.line if field.loc else 1,
                    'col': field.loc.pos if field.loc else 0,
                    'code': 'ZDC102',
                    'message': f"Field '{field.name}' uses non-Zuspec type"
                }]
            return []

Command-Line Usage
------------------

Run the checker from the command line:

.. code-block:: bash

    # Check a single file
    flake8 src/my_module.py
    
    # Check entire project
    flake8 src/
    
    # Show only Zuspec errors
    flake8 src/ | grep ZDC
    
    # Verbose output with line numbers
    flake8 --format='%(path)s:%(row)d:%(col)d: %(code)s %(text)s' src/

Integration with CI/CD
~~~~~~~~~~~~~~~~~~~~~~

Add to your CI pipeline:

.. code-block:: yaml

    # .github/workflows/lint.yml
    - name: Check Zuspec code
      run: |
        pip install flake8 zuspec-dataclasses
        flake8 src/ --select=ZDC

Troubleshooting
---------------

Errors Not Showing in VSCode
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. **Check flake8 is enabled:**

   .. code-block:: json
   
       {
           "python.linting.flake8Enabled": true
       }

2. **Verify flake8 path** points to environment with zuspec-dataclasses:

   .. code-block:: bash
   
       which flake8
       flake8 --version

3. **Reload VSCode window:** Ctrl+Shift+P → "Developer: Reload Window"

4. **Check Problems panel** (Ctrl+Shift+M) for errors

5. **Test from command line:**

   .. code-block:: bash
   
       flake8 path/to/file.py

Errors at Line 1:1
~~~~~~~~~~~~~~~~~~

If all errors show at line 1, column 1, the IR is missing source locations. This was fixed in version 2026.1+. Upgrade:

.. code-block:: bash

    pip install --upgrade zuspec-dataclasses

"Module not found" Errors
~~~~~~~~~~~~~~~~~~~~~~~~~~

The checker needs to import your code to build IR. Ensure:

1. **Configure package_roots** in ``pyproject.toml``:

   .. code-block:: toml
   
       [tool.zuspec]
       package_roots = ["src"]

2. **Install package in development mode:**

   .. code-block:: bash
   
       pip install -e .

3. **Check Python path** includes your source directories

Slow Performance
~~~~~~~~~~~~~~~~

IR compilation can be slow for large projects. To optimize:

1. **Use .flake8cache** to cache results
2. **Run on changed files only** in CI
3. **Exclude unnecessary directories:**

   .. code-block:: toml
   
       [tool.flake8]
       exclude = [".git", "__pycache__", "build", "dist"]

Comparison with Other Tools
---------------------------

vs MyPy
~~~~~~~

========================  ==================  ===================
Feature                   MyPy Plugin         IR Checker
========================  ==================  ===================
Analysis Level            Python AST          Zuspec IR
Type Checking             Yes (static)        Yes (semantic)
Profile Awareness         Yes                 Yes
Flake8 Integration        No                  Yes
VSCode Integration        Via MyPy extension  Via Flake8
Extensibility             MyPy plugin API     Entrypoints
Error Location            Excellent           Excellent (2026.1+)
========================  ==================  ===================

**Note:** The mypy plugin is deprecated in favor of the IR checker.

vs Flake8 Style Checkers
~~~~~~~~~~~~~~~~~~~~~~~~~

Traditional flake8 plugins check code style (formatting, naming, imports). The Zuspec IR checker validates **semantic correctness** - whether your code can be compiled to the target platform.

vs PyLint
~~~~~~~~~

PyLint focuses on Python best practices and bug detection. The Zuspec IR checker enforces **hardware synthesis constraints** - ensuring code is retargetable to Verilog, VHDL, C++, etc.

Frequently Asked Questions
--------------------------

**Q: Do I need to configure anything special for the checker to work?**

A: Only if you have complex import structures. Add ``package_roots`` to your ``pyproject.toml`` pointing to your source directories.

**Q: Can I disable specific error codes?**

A: Yes, use flake8's standard ignore mechanism:

.. code-block:: bash

    flake8 --extend-ignore=ZDC001,ZDC003 src/

Or in ``pyproject.toml``:

.. code-block:: toml

    [tool.flake8]
    extend-ignore = ["ZDC001", "ZDC003"]

**Q: How do I create a checker for my own profile?**

A: Create a ``ProfileChecker`` subclass and register it via entrypoints. See `Creating Custom Checkers`_.

**Q: Can I use this with pre-commit hooks?**

A: Yes! Add to ``.pre-commit-config.yaml``:

.. code-block:: yaml

    repos:
      - repo: https://github.com/pycqa/flake8
        rev: 6.0.0
        hooks:
          - id: flake8
            additional_dependencies: [zuspec-dataclasses]

**Q: Does the checker work with Python 3.8?**

A: The checker requires Python 3.9+ for full AST support.

**Q: Can I use the checker in Jupyter notebooks?**

A: Not directly. Extract your Zuspec code to ``.py`` files for checking.

See Also
--------

* :doc:`profiles` - Profile system overview
* :doc:`types` - Zuspec type system
* :doc:`components` - Component and structure definitions
* `Profile Checker Design <profile_checker_design.html>`_ - Implementation details (historical, mypy-based)

.. note::

   The mypy plugin is deprecated as of version 2026.1. Use the flake8-based IR checker instead.
