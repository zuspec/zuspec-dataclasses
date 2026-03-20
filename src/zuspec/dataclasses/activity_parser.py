"""AST parser for PSS activity methods.

Parses ``async def activity(self)`` methods from Python AST and produces
activity IR nodes (``zuspec.dataclasses.ir.activity``).

The parser is intentionally stateless between calls.  Each call to
``ActivityParser.parse()`` returns a fresh ``ActivitySequenceBlock`` rooted
at the top-level body of the parsed method.

Usage::

    from zuspec.dataclasses.activity_parser import ActivityParser

    ir = ActivityParser().parse(MyAction.activity)
    # ir is an ActivitySequenceBlock
"""
from __future__ import annotations

import ast
import inspect
import textwrap
from typing import Any, Callable, Dict, List, Optional, Tuple

from .ir.activity import (
    ActivityAnonTraversal,
    ActivityAtomic,
    ActivityBind,
    ActivityConstraint,
    ActivityDoWhile,
    ActivityForeach,
    ActivityIfElse,
    ActivityMatch,
    ActivityParallel,
    ActivityRepeat,
    ActivityReplicate,
    ActivitySchedule,
    ActivitySelect,
    ActivitySequenceBlock,
    ActivityStmt,
    ActivitySuper,
    ActivityTraversal,
    ActivityWhileDo,
    JoinSpec,
    MatchCase,
    SelectBranch,
)


class ActivityParseError(ValueError):
    """Raised when an unsupported AST pattern is encountered."""


_parse_cache: Dict[Tuple, ActivitySequenceBlock] = {}


class ActivityParser:
    """Parser for ``async def activity(self)`` method bodies.

    Produces a tree of activity IR nodes from the Python AST.  Inline
    constraint expressions inside ``with`` blocks are represented as raw
    ``Dict[str, Any]`` objects (same format as ``ConstraintParser.parse_expr``).

    Results are cached by source-text hash so repeated calls for the same
    unchanged method body are O(1).
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, method: Callable) -> ActivitySequenceBlock:
        """Parse an activity method and return the top-level IR node.

        Results are cached by (source hash, file, start_lineno); identical
        source in different files produces distinct IR trees with correct loc.

        Args:
            method: The ``async def activity(self)`` method to parse.

        Returns:
            ``ActivitySequenceBlock`` containing the parsed statements.

        Raises:
            ActivityParseError: If an unsupported AST pattern is encountered.
        """
        source = textwrap.dedent(inspect.getsource(method))
        try:
            src_file: str = inspect.getsourcefile(method) or ""
            _, start_lineno = inspect.getsourcelines(method)
        except (TypeError, OSError):
            src_file = ""
            start_lineno = 1
        key = (hash(source), src_file, start_lineno)
        if key in _parse_cache:
            return _parse_cache[key]

        # Store per-parse state used by _loc() and _resolve_type_cls()
        self._src_file = src_file
        self._start_lineno = start_lineno
        self._method_globals: Dict[str, Any] = getattr(method, "__globals__", {})

        tree = ast.parse(source)

        func_def = tree.body[0]
        if not isinstance(func_def, (ast.AsyncFunctionDef, ast.FunctionDef)):
            raise ActivityParseError(
                f"Expected AsyncFunctionDef or FunctionDef, got {type(func_def).__name__}"
            )

        result = ActivitySequenceBlock(
            stmts=self._parse_body(func_def.body),
            loc=self._loc(func_def),
        )
        _parse_cache[key] = result
        return result

    # ------------------------------------------------------------------
    # Body / statement parsing
    # ------------------------------------------------------------------

    def _parse_body(self, stmts: List[ast.stmt]) -> List[ActivityStmt]:
        result: List[ActivityStmt] = []
        for stmt in stmts:
            parsed = self._parse_stmt(stmt)
            if parsed is not None:
                result.append(parsed)
        return result

    def _parse_stmt(self, node: ast.stmt) -> Optional[ActivityStmt]:
        # Skip docstrings
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                return None

        if isinstance(node, ast.Expr):
            return self._parse_expr_stmt(node.value)

        if isinstance(node, ast.Assign):
            return self._parse_assign(node)

        if isinstance(node, ast.With):
            return self._parse_with(node)

        if isinstance(node, ast.AsyncWith):
            return self._parse_async_with(node)

        if isinstance(node, ast.For):
            return self._parse_for(node)

        if isinstance(node, ast.If):
            return self._parse_if(node)

        if isinstance(node, ast.Match):
            return self._parse_match(node)

        raise ActivityParseError(
            f"Unsupported activity statement type: {type(node).__name__} "
            f"at line {getattr(node, 'lineno', '?')}"
        )

    # ------------------------------------------------------------------
    # Expression-statement parsing
    # ------------------------------------------------------------------

    def _parse_expr_stmt(self, node: ast.expr) -> ActivityStmt:
        """Handle bare expression statements (traversals, bind, super).

        Handle traversals must use ``await``: ``await self.handle()``.
        Non-awaited ``self.handle()`` raises ``ActivityParseError``.
        """
        awaited = isinstance(node, ast.Await)
        inner = node.value if awaited else node

        # super().activity() → ActivitySuper (no await needed)
        if self._is_super_activity(inner):
            return ActivitySuper(loc=self._loc(inner))

        # bind(src, dst) → ActivityBind (no await needed)
        if self._is_call_name(inner, "bind"):
            call = inner  # type: ast.Call
            src = self._parse_expr(call.args[0])
            dst = self._parse_expr(call.args[1])
            return ActivityBind(src=src, dst=dst, loc=self._loc(inner))

        # await do(Type) → ActivityAnonTraversal
        # Bare do(Type) without await is now an error.
        if self._is_call_name(inner, "do"):
            if not awaited:
                type_name = self._type_name(inner.args[0])  # type: ignore[attr-defined]
                raise ActivityParseError(
                    f"Anonymous traversal must be awaited: "
                    f"use 'await do({type_name})' "
                    f"at line {getattr(node, 'lineno', '?')}"
                )
            type_name = self._type_name(inner.args[0])  # type: ignore[attr-defined]
            return ActivityAnonTraversal(
                action_type=type_name,
                action_type_cls=self._resolve_type_cls(type_name),
                loc=self._loc(inner),
            )

        # await self.handle() → ActivityTraversal
        if isinstance(inner, ast.Call) and self._is_self_attr_call(inner):
            if not awaited:
                raise ActivityParseError(
                    f"Handle traversal must be awaited: "
                    f"use 'await {ast.unparse(inner)}' "
                    f"at line {getattr(node, 'lineno', '?')}"
                )
            return self._traversal_from_call(inner)

        raise ActivityParseError(
            f"Unsupported expression statement: {ast.dump(node)}"
        )

    # ------------------------------------------------------------------
    # Assignment parsing
    # ------------------------------------------------------------------

    def _parse_assign(self, node: ast.Assign) -> ActivityStmt:
        """Handle ``x = await do(Type)`` — labeled anonymous traversal.

        Bare ``x = do(Type)`` without ``await`` is rejected.
        """
        rhs = node.value
        awaited = isinstance(rhs, ast.Await)
        if awaited:
            rhs = rhs.value
        if (
            len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and self._is_call_name(rhs, "do")
        ):
            label = node.targets[0].id
            call: ast.Call = rhs  # type: ignore[assignment]
            type_name = self._type_name(call.args[0])
            if not awaited:
                raise ActivityParseError(
                    f"Labeled anonymous traversal must be awaited: "
                    f"use '{label} = await do({type_name})' "
                    f"at line {getattr(node, 'lineno', '?')}"
                )
            return ActivityAnonTraversal(
                action_type=type_name,
                label=label,
                action_type_cls=self._resolve_type_cls(type_name),
                loc=self._loc(node),
            )

        raise ActivityParseError(
            f"Unsupported assignment in activity body: {ast.dump(node)}"
        )

    # ------------------------------------------------------------------
    # With-statement parsing
    # ------------------------------------------------------------------

    def _parse_with(self, node: ast.With) -> ActivityStmt:
        if len(node.items) != 1:
            raise ActivityParseError(
                "Activity 'with' blocks must have exactly one context expression"
            )

        item = node.items[0]
        ctx = item.context_expr
        asname = item.optional_vars

        # with do(Type) as x: → ActivityAnonTraversal (labeled + constraints)
        if self._is_call_name(ctx, "do"):
            call: ast.Call = ctx  # type: ignore[assignment]
            label = asname.id if isinstance(asname, ast.Name) else None
            constraints = self._parse_inline_constraints(node.body)
            type_name = self._type_name(call.args[0])
            return ActivityAnonTraversal(
                action_type=type_name,
                label=label,
                inline_constraints=constraints,
                action_type_cls=self._resolve_type_cls(type_name),
                loc=self._loc(node),
            )

        # with self.handle(): → error; must be async with
        if isinstance(ctx, ast.Call) and self._is_self_attr_call(ctx):
            raise ActivityParseError(
                f"Handle traversal with constraints must use 'async with': "
                f"use 'async with {ast.unparse(ctx)}:' "
                f"at line {getattr(node, 'lineno', '?')}"
            )

        # with parallel(...): → ActivityParallel
        if self._is_call_name(ctx, "parallel"):
            return ActivityParallel(
                stmts=self._parse_body(node.body),
                join_spec=self._parse_join_spec(ctx),  # type: ignore[arg-type]
                loc=self._loc(node),
            )

        # with schedule(...): → ActivitySchedule
        if self._is_call_name(ctx, "schedule"):
            return ActivitySchedule(
                stmts=self._parse_body(node.body),
                join_spec=self._parse_join_spec(ctx),  # type: ignore[arg-type]
                loc=self._loc(node),
            )

        # with sequence(): → ActivitySequenceBlock (explicit)
        if self._is_call_name(ctx, "sequence"):
            return ActivitySequenceBlock(stmts=self._parse_body(node.body), loc=self._loc(node))

        # with atomic(): → ActivityAtomic
        if self._is_call_name(ctx, "atomic"):
            return ActivityAtomic(stmts=self._parse_body(node.body), loc=self._loc(node))

        # with select(): → ActivitySelect
        if self._is_call_name(ctx, "select"):
            return self._parse_select(node.body, node)

        # with branch(...): → SelectBranch (handled by _parse_select)
        if self._is_call_name(ctx, "branch"):
            raise ActivityParseError(
                "'with branch():' must appear directly inside 'with select():'"
            )

        # with do_while(cond): → ActivityDoWhile
        if self._is_call_name(ctx, "do_while"):
            call = ctx  # type: ignore[assignment]
            cond = self._parse_expr(call.args[0])
            return ActivityDoWhile(
                condition=cond,
                body=self._parse_body(node.body),
                loc=self._loc(node),
            )

        # with while_do(cond): → ActivityWhileDo
        if self._is_call_name(ctx, "while_do"):
            call = ctx  # type: ignore[assignment]
            cond = self._parse_expr(call.args[0])
            return ActivityWhileDo(
                condition=cond,
                body=self._parse_body(node.body),
                loc=self._loc(node),
            )

        # with constraint(): → ActivityConstraint
        if self._is_call_name(ctx, "constraint"):
            return ActivityConstraint(
                constraints=self._parse_inline_constraints(node.body),
                loc=self._loc(node),
            )

        raise ActivityParseError(
            f"Unsupported 'with' context in activity: {ast.dump(ctx)}"
        )

    def _parse_async_with(self, node: ast.AsyncWith) -> ActivityStmt:
        """Handle ``async with self.handle(): ...`` — traversal with inline constraints."""
        if len(node.items) != 1:
            raise ActivityParseError(
                "Activity 'async with' blocks must have exactly one context expression"
            )
        item = node.items[0]
        ctx = item.context_expr

        # async with self.handle(): → ActivityTraversal (with constraints)
        if isinstance(ctx, ast.Call) and self._is_self_attr_call(ctx):
            traversal = self._traversal_from_call(ctx)
            traversal.inline_constraints = self._parse_inline_constraints(node.body)
            return traversal

        raise ActivityParseError(
            f"'async with' in activity only valid for handle traversals (self.handle()): "
            f"{ast.dump(ctx)}"
        )

    # ------------------------------------------------------------------
    # For-loop parsing
    # ------------------------------------------------------------------

    def _parse_for(self, node: ast.For) -> ActivityStmt:
        iter_node = node.iter

        # for i in range(N) → ActivityRepeat
        if self._is_call_name(iter_node, "range"):
            call: ast.Call = iter_node  # type: ignore[assignment]
            if len(call.args) != 1:
                raise ActivityParseError(
                    "Activity repeat 'range()' must have exactly one argument"
                )
            count = self._parse_expr(call.args[0])
            index_var = node.target.id if isinstance(node.target, ast.Name) else None
            return ActivityRepeat(
                count=count,
                index_var=index_var,
                body=self._parse_body(node.body),
                loc=self._loc(node),
            )

        # for i in replicate(N) → ActivityReplicate
        if self._is_call_name(iter_node, "replicate"):
            call = iter_node  # type: ignore[assignment]
            count = self._parse_expr(call.args[0])
            index_var = node.target.id if isinstance(node.target, ast.Name) else None
            label = self._kwarg_str(call, "label")
            return ActivityReplicate(
                count=count,
                index_var=index_var,
                label=label,
                body=self._parse_body(node.body),
                loc=self._loc(node),
            )

        # for i, item in enumerate(self.collection) → ActivityForeach (indexed)
        if self._is_call_name(iter_node, "enumerate"):
            call = iter_node  # type: ignore[assignment]
            inner = call.args[0]
            collection = self._parse_expr(inner)
            if isinstance(node.target, ast.Tuple) and len(node.target.elts) == 2:
                index_var = node.target.elts[0].id if isinstance(node.target.elts[0], ast.Name) else None
                iterator = node.target.elts[1].id if isinstance(node.target.elts[1], ast.Name) else "_item"
            else:
                index_var = None
                iterator = node.target.id if isinstance(node.target, ast.Name) else "_item"
            return ActivityForeach(
                iterator=iterator,
                collection=collection,
                index_var=index_var,
                body=self._parse_body(node.body),
                loc=self._loc(node),
            )

        # for item in self.collection → ActivityForeach
        if isinstance(iter_node, ast.Attribute):
            collection = self._parse_expr(iter_node)
            iterator = node.target.id if isinstance(node.target, ast.Name) else "_item"
            return ActivityForeach(
                iterator=iterator,
                collection=collection,
                body=self._parse_body(node.body),
                loc=self._loc(node),
            )

        raise ActivityParseError(
            f"Unsupported 'for' iterator in activity: {ast.dump(iter_node)}"
        )

    # ------------------------------------------------------------------
    # If / Match parsing
    # ------------------------------------------------------------------

    def _parse_if(self, node: ast.If) -> ActivityIfElse:
        condition = self._parse_expr(node.test)
        if_body = self._parse_body(node.body)
        else_body: List[ActivityStmt] = []

        if node.orelse:
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                else_body = [self._parse_if(node.orelse[0])]
            else:
                else_body = self._parse_body(node.orelse)

        return ActivityIfElse(condition=condition, if_body=if_body, else_body=else_body, loc=self._loc(node))

    def _parse_match(self, node: ast.Match) -> ActivityMatch:
        subject = self._parse_expr(node.subject)
        cases: List[MatchCase] = []
        for case in node.cases:
            pattern = self._parse_match_pattern(case.pattern)
            body = self._parse_body(case.body)
            cases.append(MatchCase(pattern=pattern, body=body))
        return ActivityMatch(subject=subject, cases=cases, loc=self._loc(node))

    def _parse_match_pattern(self, pattern: ast.pattern) -> Dict[str, Any]:
        """Convert a match pattern to a dict representation."""
        if isinstance(pattern, ast.MatchAs):
            if pattern.pattern is None:
                return {"type": "wildcard"}
            return {"type": "as", "pattern": self._parse_match_pattern(pattern.pattern), "name": pattern.name}
        if isinstance(pattern, ast.MatchValue):
            return self._parse_expr(pattern.value)
        if isinstance(pattern, ast.MatchOr):
            return {"type": "or", "patterns": [self._parse_match_pattern(p) for p in pattern.patterns]}
        return {"type": "unknown", "dump": ast.dump(pattern)}

    # ------------------------------------------------------------------
    # Select / branch parsing
    # ------------------------------------------------------------------

    def _parse_select(self, body: List[ast.stmt], parent_node: Optional[ast.AST] = None) -> ActivitySelect:
        branches: List[SelectBranch] = []
        for stmt in body:
            if isinstance(stmt, ast.With) and len(stmt.items) == 1:
                ctx = stmt.items[0].context_expr
                if self._is_call_name(ctx, "branch"):
                    call: ast.Call = ctx  # type: ignore[assignment]
                    guard = self._kwarg_expr(call, "guard")
                    weight = self._kwarg_expr(call, "weight")
                    branch_body = self._parse_body(stmt.body)
                    branches.append(SelectBranch(guard=guard, weight=weight, body=branch_body))
                    continue
            raise ActivityParseError(
                f"'with select():' body must contain only 'with branch():' blocks; "
                f"found {ast.dump(stmt)}"
            )
        loc = self._loc(parent_node) if parent_node is not None else None
        return ActivitySelect(branches=branches, loc=loc)

    # ------------------------------------------------------------------
    # Join-spec parsing
    # ------------------------------------------------------------------

    def _parse_join_spec(self, call: ast.Call) -> Optional[JoinSpec]:
        """Parse join_* keyword args from a parallel/schedule call."""
        if not call.keywords:
            return None

        for kw in call.keywords:
            if kw.arg == "join_branch":
                label = kw.value.value if isinstance(kw.value, ast.Constant) else None
                return JoinSpec(kind="branch", branch_label=label)
            if kw.arg == "join_none" and isinstance(kw.value, ast.Constant) and kw.value.value:
                return JoinSpec(kind="none")
            if kw.arg == "join_select":
                count = self._parse_expr(kw.value)
                return JoinSpec(kind="select", count=count)
            if kw.arg == "join_first":
                count = self._parse_expr(kw.value)
                return JoinSpec(kind="first", count=count)
        return None

    # ------------------------------------------------------------------
    # Inline constraint parsing
    # ------------------------------------------------------------------

    def _parse_inline_constraints(self, body: List[ast.stmt]) -> List[ast.stmt]:
        """Return constraint AST statements verbatim for solver integration."""
        result = []
        for stmt in body:
            if isinstance(stmt, ast.Pass):
                continue
            result.append(stmt)
        return result

    # ------------------------------------------------------------------
    # Expression parsing (thin wrapper — produces dict, like ConstraintParser)
    # ------------------------------------------------------------------

    def _parse_expr(self, node: ast.expr) -> Dict[str, Any]:
        from .constraint_parser import ConstraintParser
        return ConstraintParser().parse_expr(node)

    # ------------------------------------------------------------------
    # Traversal helpers
    # ------------------------------------------------------------------

    def _traversal_from_call(self, call: ast.Call) -> ActivityTraversal:
        """Build an ActivityTraversal from ``self.handle()`` or ``self.handle[i]()``."""
        func = call.func  # type: ignore[attr-defined]
        # self.handle[i]() — subscript
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Subscript):
            subscript = func.value
            handle = subscript.value.attr if isinstance(subscript.value, ast.Attribute) else None
            if handle is None:
                raise ActivityParseError(f"Unsupported subscript traversal: {ast.dump(call)}")
            index = self._parse_expr(subscript.slice)
            return ActivityTraversal(handle=handle, index=index, loc=self._loc(call))
        # self.handle()
        if isinstance(func, ast.Attribute):
            return ActivityTraversal(handle=func.attr, loc=self._loc(call))
        raise ActivityParseError(f"Unsupported traversal call: {ast.dump(call)}")

    # ------------------------------------------------------------------
    # Predicate / utility helpers
    # ------------------------------------------------------------------

    def _loc(self, ast_node: ast.AST) -> "Loc":
        """Convert an AST node's lineno to an IR Loc instance."""
        from .ir.base import Loc
        line = getattr(ast_node, "lineno", 1)
        pos = getattr(ast_node, "col_offset", 0)
        return Loc(
            file=getattr(self, "_src_file", ""),
            line=getattr(self, "_start_lineno", 1) + line - 1,
            pos=pos,
        )

    def _resolve_type_cls(self, type_name: str) -> Optional[type]:
        """Resolve *type_name* to a class via method globals (best-effort)."""
        globals_ = getattr(self, "_method_globals", {})
        # Simple name
        cls = globals_.get(type_name)
        if cls is not None:
            return cls
        # Qualified name like "pkg.MyAction" — skip; runtime falls back to string
        return None

    @staticmethod
    def _is_self_attr_call(node: ast.expr) -> bool:
        """True if node is ``self.something(...)``."""
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)  # type: ignore[attr-defined]
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
        )

    @staticmethod
    def _is_call_name(node: ast.expr, name: str) -> bool:
        """True if node is a call to ``name(...)`` or ``<pkg>.name(...)``."""
        if not isinstance(node, ast.Call):
            return False
        func = node.func  # type: ignore[attr-defined]
        # bare call: name(...)
        if isinstance(func, ast.Name) and func.id == name:
            return True
        # qualified call: zdc.name(...) or any_module.name(...)
        if isinstance(func, ast.Attribute) and func.attr == name:
            return True
        return False

    @staticmethod
    def _is_super_activity(node: ast.expr) -> bool:
        """True if node is ``super().activity()``."""
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)  # type: ignore[attr-defined]
            and node.func.attr == "activity"
            and isinstance(node.func.value, ast.Call)
            and isinstance(node.func.value.func, ast.Name)
            and node.func.value.func.id == "super"
        )

    @staticmethod
    def _type_name(node: ast.expr) -> str:
        """Extract a dotted type name from a Name or Attribute node."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{ActivityParser._type_name(node.value)}.{node.attr}"
        raise ActivityParseError(f"Cannot extract type name from: {ast.dump(node)}")

    @staticmethod
    def _kwarg_str(call: ast.Call, name: str) -> Optional[str]:
        """Return a string keyword argument value, or None if absent."""
        for kw in call.keywords:
            if kw.arg == name and isinstance(kw.value, ast.Constant):
                return str(kw.value.value)
        return None

    def _kwarg_expr(self, call: ast.Call, name: str) -> Optional[Dict[str, Any]]:
        """Return a parsed keyword argument expression, or None if absent."""
        for kw in call.keywords:
            if kw.arg == name:
                return self._parse_expr(kw.value)
        return None
