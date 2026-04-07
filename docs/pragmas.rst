###############
Pragma Comments
###############

Zuspec supports *pragma comments* — inline ``# zdc:`` comments that attach
structured metadata to Python language elements.  Pragmas are designed to
be as non-invasive as possible: they follow the same tradition as Python's
own tool-comment conventions (``# type: ignore``, ``# noqa``, etc.) and
require no structural changes to the code.

The pragma system has two primary uses:

1. **Synthesis attributes** on statements in ``@comb`` / ``@sync`` method
   bodies — directs backend code generators to emit attributes such as
   ``(* parallel_case *)`` or ``(* full_case *)`` in the generated
   SystemVerilog.
2. **Field metadata** on component field declarations — attaches
   attributes such as ``(* keep *)`` to the generated signal.

****************************************
Syntax
****************************************

A pragma comment starts with the literal prefix ``# zdc:`` (case-insensitive,
leading/trailing whitespace ignored) and contains a comma-separated list of
*items*:

.. code-block:: text

    # zdc: flag, key=value, key="string value"

Each item is one of:

* **bare flag** — ``flag`` becomes ``{flag: True}``
* **integer value** — ``key=42`` becomes ``{key: 42}``
* **boolean value** — ``key=True`` / ``key=False`` become ``{key: True/False}``
* **quoted string** — ``key="hello"`` becomes ``{key: "hello"}``
* **unquoted string fallback** — ``key=word`` (not a number/bool literal)
  becomes ``{key: "word"}``

Keys are lowercased; flag names are lowercased.  Multiple ``# zdc:`` items
on the same logical comment are merged.

*************************************************************************************************************************
Statement Pragmas in @comb / @sync
*************************************************************************************************************************

Place a ``# zdc:`` comment at the end of an ``if`` (or ``match``) line to
annotate that statement.  The pragma is attached to the top ``if`` of an
if/elif/else chain and covers the entire chain.

.. code-block:: python3

    import zuspec.dataclasses as zdc

    @zdc.dataclass
    class Alu(zdc.Component):
        a:   zdc.u32 = zdc.input()
        b:   zdc.u32 = zdc.input()
        sel: zdc.u8  = zdc.input()
        out: zdc.u32 = zdc.output(reset=0)

        @zdc.comb
        def _result(self):
            if self.sel == 0:  # zdc: parallel_case, full_case
                self.out = self.a + self.b
            elif self.sel == 1:
                self.out = self.a - self.b
            elif self.sel == 2:
                self.out = self.a & self.b
            else:
                self.out = self.a | self.b

When ``zuspec-be-sv`` generates SystemVerilog from the above, it emits:

.. code-block:: systemverilog

    (* parallel_case, full_case *)
    if (sel == 0) begin
        out = a + b;
    end else if ...

**Supported synthesis flags:**

``parallel_case``
    Informs the synthesis tool that the ``if``/``elif`` branches are mutually
    exclusive (one-hot conditions).  Equivalent to Verilog
    ``(* parallel_case *)`` on a ``case(1'b1)`` statement.

``full_case``
    Informs the synthesis tool that all possible input combinations are
    covered by the branches; unspecified combinations need not generate
    latches.  Equivalent to Verilog ``(* full_case *)``.

Both flags are often combined: ``# zdc: parallel_case, full_case``.

*************************************************************************************************************************
Field Pragmas
*************************************************************************************************************************

Place a ``# zdc:`` comment at the end of a field declaration line to
annotate that field.

.. code-block:: python3

    @zdc.dataclass
    class DebugView(zdc.Component):
        clk:           zdc.bit = zdc.input()
        dbg_ascii_instr: zdc.u64 = zdc.output(reset=0)  # zdc: keep
        dbg_insn_imm:  zdc.u32  = zdc.output(reset=0)   # zdc: keep

The ``keep`` pragma prevents synthesis tools from optimising away signals
that are only used for debug or formal verification:

.. code-block:: systemverilog

    (* keep *) logic [63:0] dbg_ascii_instr;
    (* keep *) logic [31:0] dbg_insn_imm;

**Supported field flag:**

``keep``
    Prevents the synthesis tool from removing the signal during
    optimisation.  Equivalent to Verilog ``(* keep *)``.

*************************************************************************************************************************
Labels
*************************************************************************************************************************

The pragma system also supports arbitrary key/value metadata via the
``label`` key, which can be used to tag specific statements or fields
for external tools:

.. code-block:: python3

    @zdc.sync(clock=lambda s: s.clk, reset=lambda s: s.rst)
    def _cpu_fsm(self):
        if self._cpu_state == CpuState.FETCH:  # zdc: parallel_case, full_case, label=cpu_fsm_top
            ...

The label is stored in ``stmt.pragmas["label"]`` and can be queried by
analysis passes or synthesis backends to locate specific IR nodes without
traversing the full AST.

*************************************************************************************************************************
Programmatic Access
*************************************************************************************************************************

Pragma maps can be scanned from any source string using the public API:

.. code-block:: python3

    from zuspec.dataclasses import scan_pragmas, parse_pragma_str

    # Scan an entire source file/method body
    source = """
    if self.sel == 0:  # zdc: parallel_case, full_case
        pass
    x: int = 0  # zdc: keep
    """
    pragmas = scan_pragmas(source)
    # {2: {'parallel_case': True, 'full_case': True}, 4: {'keep': True}}

    # Parse a single pragma string
    attrs = parse_pragma_str("parallel_case, full_case, label=my_fsm")
    # {'parallel_case': True, 'full_case': True, 'label': 'my_fsm'}

``scan_pragmas(source)``
    Returns a ``Dict[int, Dict[str, Any]]`` mapping 1-based line numbers
    to pragma dictionaries.  Lines without a ``# zdc:`` comment are absent
    from the result.

``parse_pragma_str(text)``
    Parses a single comma-separated pragma item string (the text after
    ``# zdc:``) and returns a ``Dict[str, Any]``.

*************************************************************************************************************************
IR Storage
*************************************************************************************************************************

After parsing, pragmas are stored in two IR locations:

* **Statement nodes** — ``StmtIf.pragmas`` and ``StmtMatch.pragmas`` (both
  ``Dict[str, Any]``), populated by ``DataModelFactory`` when it converts
  the method body AST.
* **Field nodes** — ``Field.pragmas`` (``Dict[str, Any]``), populated when
  ``DataModelFactory`` scans the class body.

Backend generators (e.g. ``zuspec-be-sv``) query ``stmt.pragmas`` /
``field.pragmas`` to decide whether to emit ``(* … *)`` attributes in the
generated SystemVerilog output.

*************************************************************************************************************************
Combining with Other Comments
*************************************************************************************************************************

A pragma comment may appear alongside other ``#`` comments on the same
physical line as long as the ``# zdc:`` token comes after any other
comment text:

.. code-block:: python3

    if self._mem_wordsize == 0:  # word (0=32-bit)  # zdc: full_case
        ...

Only the last ``# zdc:`` token on a line is used; earlier ones on the
same line are ignored.
