"""AST visitor skeleton that extracts :class:`IrPipeline` from an
``@zdc.pipeline`` async method.

This module is a skeleton — it can parse the basic pipeline structure but
does not yet handle all body-statement patterns.  Extend as synthesis needs
grow.
"""

from __future__ import annotations

import ast
from typing import List, Optional

from .pipeline_async import (
    IrBubble,
    IrHazardOp,
    IrInFlightSearch,
    IrPipeline,
    IrStage,
    IrStall,
)

_PIPELINE_DECORATOR_NAMES = {"pipeline"}
_STAGE_CALL = "stage"                  # zdc.pipeline.stage()
_HAZARD_OPS = {"reserve", "block", "write", "release", "acquire"}


class AsyncPipelineFrontendPass(ast.NodeVisitor):
    """Extract :class:`IrPipeline` from an async pipeline method's AST.

    Usage::

        import ast, inspect, textwrap
        src = textwrap.dedent(inspect.getsource(MyComp.run))
        tree = ast.parse(src)
        pass_ = AsyncPipelineFrontendPass()
        pass_.visit(tree)
        ir = pass_.result   # IrPipeline or None
    """

    def __init__(self) -> None:
        self.result: Optional[IrPipeline] = None

    # ------------------------------------------------------------------
    # Public entry
    # ------------------------------------------------------------------

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if self._has_pipeline_decorator(node):
            self.result = self._extract_pipeline(node)
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Pipeline extraction
    # ------------------------------------------------------------------

    def _has_pipeline_decorator(self, node: ast.AsyncFunctionDef) -> bool:
        for dec in node.decorator_list:
            name = self._decorator_name(dec)
            if name in _PIPELINE_DECORATOR_NAMES:
                return True
        return False

    def _decorator_name(self, node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return ""

    def _extract_pipeline(self, node: ast.AsyncFunctionDef) -> IrPipeline:
        stages: List[IrStage] = []
        for stmt in node.body:
            stage = self._try_extract_stage(stmt)
            if stage is not None:
                stages.append(stage)
        return IrPipeline(
            method_name=node.name,
            clock_lambda=None,
            reset_lambda=None,
            stages=stages,
        )

    # ------------------------------------------------------------------
    # Stage extraction
    # ------------------------------------------------------------------

    def _try_extract_stage(self, node: ast.stmt) -> Optional[IrStage]:
        """Return an :class:`IrStage` if *node* is an ``async with stage()``."""
        if not isinstance(node, ast.AsyncWith):
            return None
        if not node.items:
            return None
        item = node.items[0]
        if not self._is_stage_call(item.context_expr):
            return None
        name = self._extract_stage_name(item)
        cycles = self._extract_cycles_kwarg(item.context_expr)
        hazard_ops: List[IrHazardOp] = []
        body_nodes: List[object] = []
        for stmt in node.body:
            op = self._try_extract_hazard_op(stmt)
            if op is not None:
                hazard_ops.append(op)
                body_nodes.append(op)
            else:
                body_nodes.append(stmt)
        return IrStage(name=name, cycles=cycles, body=body_nodes, hazard_ops=hazard_ops)

    def _is_stage_call(self, node: ast.expr) -> bool:
        """True if *node* looks like ``zdc.pipeline.stage(...)`` or ``pipeline.stage(...)``."""
        if not isinstance(node, ast.Call):
            return False
        fn = node.func
        if isinstance(fn, ast.Attribute):
            return fn.attr == _STAGE_CALL
        return False

    def _extract_stage_name(self, item: ast.withitem) -> str:
        """Return the ``as NAME`` identifier, or ``""`` if absent."""
        if item.optional_vars is not None and isinstance(item.optional_vars, ast.Name):
            return item.optional_vars.id
        return ""

    def _extract_cycles_kwarg(self, call: ast.Call) -> int:
        """Return the ``cycles=N`` keyword argument value, defaulting to 1."""
        for kw in call.keywords:
            if kw.arg == "cycles" and isinstance(kw.value, ast.Constant):
                return int(kw.value.value)
        return 1

    # ------------------------------------------------------------------
    # Hazard operation extraction
    # ------------------------------------------------------------------

    def _try_extract_hazard_op(self, node: ast.stmt) -> Optional[IrHazardOp]:
        """Return :class:`IrHazardOp` if *node* is an ``await pipeline.<op>()`` call."""
        call = self._unwrap_await_expr(node)
        if call is None:
            return None
        fn = call.func
        if not isinstance(fn, ast.Attribute):
            return None
        op_name = fn.attr
        if op_name not in _HAZARD_OPS:
            return None
        resource_expr = call.args[0] if call.args else None
        mode = "write"
        for kw in call.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                mode = str(kw.value.value)
        value_expr = call.args[1] if op_name == "write" and len(call.args) > 1 else None
        return IrHazardOp(op=op_name, resource_expr=resource_expr, mode=mode, value_expr=value_expr)

    def _unwrap_await_expr(self, node: ast.stmt) -> Optional[ast.Call]:
        """Return the inner Call if *node* is ``await <call>`` or ``_ = await <call>``."""
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Await):
            inner = node.value.value
            if isinstance(inner, ast.Call):
                return inner
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Await):
            inner = node.value.value
            if isinstance(inner, ast.Call):
                return inner
        return None
