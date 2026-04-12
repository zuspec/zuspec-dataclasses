"""Pipeline IR nodes produced during elaboration of ``@zdc.pipeline`` components.

These dataclasses are built by :mod:`zuspec.dataclasses.data_model_factory`
when it encounters a component with ``@zdc.pipeline``, ``@zdc.stage``, and
``@zdc.sync`` methods.  The synthesis passes in ``zuspec-synth`` consume them
to build the full ``PipelineIR``.

Node hierarchy
--------------
- :class:`PipelineRootIR`   — the root method's call sequence
  - :class:`StageCallNode`  — one ``self.STAGE(args)`` invocation
- :class:`StageMethodIR`    — one ``@zdc.stage``-decorated method
  - :class:`StallDeclNode`  — ``zdc.stage.stall(cond)``
  - :class:`CancelDeclNode` — ``zdc.stage.cancel(cond)``
  - :class:`FlushDeclNode`  — ``zdc.stage.flush(target, cond)``
  - :class:`StageQueryNode` — ``zdc.stage.valid/ready/stalled(self.X)``
- :class:`SyncMethodIR`     — one ``@zdc.sync``-decorated method
  - :class:`FlushDeclNode`  — ``zdc.stage.flush(...)`` inside sync body
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any, List, Optional


# ---------------------------------------------------------------------------
# Stage-call node (one invocation in the pipeline root body)
# ---------------------------------------------------------------------------

@dataclass
class StageCallNode:
    """One ``self.STAGE(args)`` call in the pipeline root body.

    :attr:`stage_name` is the method name (e.g. ``"IF"``).
    :attr:`arg_names`  is the list of variable names passed *into* the stage
        (i.e., the call arguments — these become stage-register inputs).
    :attr:`return_names` is the list of variable names that receive the
        stage's return values (i.e., the LHS of the assignment, if any).
    :attr:`cycles` is the number of pipeline registers for this call site,
        set by ``with zdc.stage.cycles(N):`` in the pipeline body (Form B).
        Defaults to 1.  The synthesis pass also checks the decorator-level
        default (Form A) via ``StageMethodIR.cycles`` and uses whichever is
        larger (Form B wins when explicitly set).
    """
    stage_name:    str
    arg_names:     List[str] = field(default_factory=list)
    return_names:  List[str] = field(default_factory=list)
    cycles:        int = 1


# ---------------------------------------------------------------------------
# Stall / Cancel / Flush / Query nodes
# ---------------------------------------------------------------------------

@dataclass
class StallDeclNode:
    """A ``zdc.stage.stall(cond)`` call found in a stage body.

    :attr:`cond_ast` is the raw Python AST expression node for the condition.
    The synthesis pass lowers this into a combinational stall-predicate wire.
    """
    cond_ast: Any  # ast.expr node


@dataclass
class CancelDeclNode:
    """A ``zdc.stage.cancel(cond=True)`` call found in a stage body.

    :attr:`cond_ast` is the raw Python AST expression node for the condition.
    The synthesis pass lowers this into a cancel wire.
    """
    cond_ast: Any  # ast.expr node


@dataclass
class FlushDeclNode:
    """A ``zdc.stage.flush(target, cond=True)`` call found in a stage or sync body.

    :attr:`target_stage` is the resolved target stage name (e.g. ``"IF"``).
    :attr:`cond_ast`     is the raw Python AST expression node for the enable.
    The synthesis pass generates a ``{SOURCE}_flush_{TARGET}`` wire.
    """
    target_stage: str
    cond_ast:     Any  # ast.expr node


@dataclass
class StageQueryNode:
    """A ``zdc.stage.valid/ready/stalled(self.X)`` call.

    :attr:`kind`       is one of ``"valid"``, ``"ready"``, ``"stalled"``.
    :attr:`stage_name` is the resolved stage name (e.g. ``"ID"``).
    The synthesis pass substitutes this with the appropriate Verilog signal.
    """
    kind:       str  # "valid" | "ready" | "stalled"
    stage_name: str


# ---------------------------------------------------------------------------
# Pipeline root IR
# ---------------------------------------------------------------------------

@dataclass
class PipelineRootIR:
    """IR for the ``@zdc.pipeline``-decorated root method.

    :attr:`clock`       — clock field name (string).
    :attr:`reset`       — reset field name (string).
    :attr:`forward`     — process-level forward default (bool, default True).
    :attr:`no_forward`  — process-level per-signal no-forward list.
    :attr:`stage_calls` — ordered list of :class:`StageCallNode`, one per
        ``self.STAGE(...)`` invocation in the root body.
    """
    clock:       Optional[str]
    reset:       Optional[str]
    forward:     bool              = True
    no_forward:  List[str]         = field(default_factory=list)
    stage_calls: List[StageCallNode] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage method IR
# ---------------------------------------------------------------------------

@dataclass
class PortSpec:
    """A typed port (input or output) of a stage method.

    :attr:`name`  — parameter/return-variable name.
    :attr:`annotation_ast` — raw AST annotation node (e.g. ``zdc.u32``).
    """
    name:            str
    annotation_ast:  Any = None  # ast.expr or None if unannotated


@dataclass
class StageMethodIR:
    """IR for one ``@zdc.stage``-decorated method.

    :attr:`name`         — method name (e.g. ``"IF"``).
    :attr:`no_forward`   — per-stage no-forward flag (from decorator arg).
    :attr:`cycles`       — decorator-level pipeline-register count (Form A).
                           Set from ``@zdc.stage(cycles=N)``; defaults to 1.
                           Can be overridden per call-site via
                           ``with zdc.stage.cycles(N):`` (Form B).
    :attr:`inputs`       — ordered input port specs (from method parameters).
    :attr:`outputs`      — ordered output port specs (from return annotation).
    :attr:`stall_decls`  — ``zdc.stage.stall(...)`` calls found in the body.
    :attr:`cancel_decls` — ``zdc.stage.cancel(...)`` calls found in the body.
    :attr:`flush_decls`  — ``zdc.stage.flush(...)`` calls found in the body.
    :attr:`query_nodes`  — ``zdc.stage.valid/ready/stalled(...)`` calls.
    :attr:`body_ast`     — raw AST ``FunctionDef`` node for expression lowering.
    """
    name:         str
    no_forward:   bool                  = False
    cycles:       int                   = 1
    inputs:       List[PortSpec]        = field(default_factory=list)
    outputs:      List[PortSpec]        = field(default_factory=list)
    stall_decls:  List[StallDeclNode]   = field(default_factory=list)
    cancel_decls: List[CancelDeclNode]  = field(default_factory=list)
    flush_decls:  List[FlushDeclNode]   = field(default_factory=list)
    query_nodes:  List[StageQueryNode]  = field(default_factory=list)
    body_ast:     Any = None  # ast.FunctionDef


# ---------------------------------------------------------------------------
# Sync method IR
# ---------------------------------------------------------------------------

@dataclass
class SyncMethodIR:
    """IR for one ``@zdc.sync``-decorated method.

    :attr:`name`        — method name.
    :attr:`clock`       — clock field name (string).
    :attr:`reset`       — reset field name (string).
    :attr:`flush_decls` — ``zdc.stage.flush(...)`` calls in the body.
    :attr:`query_nodes` — ``zdc.stage.valid/ready/stalled(...)`` calls.
    :attr:`body_ast`    — raw AST ``FunctionDef`` node.
    """
    name:         str
    clock:        Optional[str]         = None
    reset:        Optional[str]         = None
    flush_decls:  List[FlushDeclNode]   = field(default_factory=list)
    query_nodes:  List[StageQueryNode]  = field(default_factory=list)
    body_ast:     Any = None  # ast.FunctionDef
