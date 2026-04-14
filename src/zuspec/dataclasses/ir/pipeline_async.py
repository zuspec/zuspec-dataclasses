"""IR nodes for async pipeline methods.

These nodes are produced by :class:`AsyncPipelineFrontendPass` and consumed
by downstream synthesis passes.  They do not affect ``rt`` execution.
"""

from __future__ import annotations

import dataclasses as dc
from typing import Any, List, Optional


@dc.dataclass
class IrPipeline:
    """Root IR node for one ``@zdc.pipeline`` async method."""
    method_name: str
    clock_lambda: Any            # AST node of the clock lambda, or None
    reset_lambda: Any            # AST node of the reset lambda, or None
    stages: List["IrStage"] = dc.field(default_factory=list)


@dc.dataclass
class IrStage:
    """One ``async with zdc.pipeline.stage() as NAME:`` block."""
    name: str                    # identifier from the ``as NAME`` clause
    cycles: int = 1              # from ``stage(cycles=N)``, default 1
    body: List[Any] = dc.field(default_factory=list)         # IR nodes for body stmts
    hazard_ops: List["IrHazardOp"] = dc.field(default_factory=list)


@dc.dataclass
class IrHazardOp:
    """Any hazard operation: reserve, block, write, release, or acquire."""
    op: str                      # "reserve" | "block" | "write" | "release" | "acquire"
    resource_expr: Any           # AST expression for ``resource[addr]``
    mode: str = "write"          # "read" or "write"
    value_expr: Any = None       # only for ``op == "write"``


@dc.dataclass
class IrStall:
    """``await NAME.stall(n)``"""
    stage_var: str
    cycles_expr: Any             # AST expression for *n*


@dc.dataclass
class IrBubble:
    """``await NAME.bubble()``"""
    stage_var: str


@dc.dataclass
class IrInFlightSearch:
    """``zdc.pipeline.find(predicate)``"""
    predicate_expr: Any          # AST expression for the predicate callable
