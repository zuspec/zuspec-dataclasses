"""Activity IR tree interpreter for the PSS pure-Python runtime.

Interprets activity IR trees produced by ``ActivityParser`` and executes
the PSS action lifecycle (pre_solve → randomize → post_solve → body).

Example::

    >>> # ActivityRunner is used via ScenarioRunner or Action.__call__.
"""
from __future__ import annotations

import asyncio
import dataclasses as dc
from typing import TYPE_CHECKING, Any, Optional

from ..ir.activity import (
    ActivityAnonTraversal,
    ActivityAtomic,
    ActivityBind,
    ActivityConstraint,
    ActivityDoWhile,
    ActivityForeach,
    ActivityIfElse,
    ActivityMatch,
    ActivityParallel,
    ActivityReplicate,
    ActivityRepeat,
    ActivitySchedule,
    ActivitySelect,
    ActivitySequenceBlock,
    ActivityStmt,
    ActivitySuper,
    ActivityTraversal,
    ActivityWhileDo,
)
from ..solver.api import randomize
from .action_context import ActionContext
from .debug_rt import _fire_line_event

if TYPE_CHECKING:
    from ..types import Component
    from .pool_resolver import PoolResolver


def _resolve_handle_type(action_cls: type, field_name: str) -> Optional[type]:
    """Walk MRO to find a concrete type annotation for *field_name*, skipping
    generic type variables that cannot be evaluated."""
    for klass in action_cls.__mro__:
        ann = klass.__dict__.get("__annotations__", {})
        if field_name in ann:
            hint = ann[field_name]
            if isinstance(hint, type):
                return hint
            # Could be a string forward-ref or a generic alias — skip it
    return None


class ActivityRunner:
    """Interprets activity IR trees produced by ActivityParser."""

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        block: ActivitySequenceBlock,
        ctx: ActionContext,
    ) -> None:
        """Execute *block* in the given context."""
        await self._seq(block, ctx)

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------

    async def _exec(self, stmt: ActivityStmt, ctx: ActionContext) -> None:
        if stmt.loc:
            _fire_line_event(
                stmt.loc.file or "",
                stmt.loc.line,
                vars(ctx.action) if ctx.action is not None else {},
            )

        t = type(stmt)
        if t is ActivitySequenceBlock:
            await self._seq(stmt, ctx)
        elif t is ActivityTraversal:
            await self._traverse_handle(stmt, ctx)
        elif t is ActivityAnonTraversal:
            await self._traverse_anon(stmt, ctx)
        elif t is ActivitySuper:
            await self._super(stmt, ctx)
        elif t is ActivityParallel:
            await self._parallel(stmt, ctx)
        elif t is ActivitySchedule:
            await self._schedule(stmt, ctx)
        elif t is ActivityAtomic:
            await self._atomic(stmt, ctx)
        elif t is ActivityRepeat:
            await self._repeat(stmt, ctx)
        elif t is ActivityDoWhile:
            await self._do_while(stmt, ctx)
        elif t is ActivityWhileDo:
            await self._while_do(stmt, ctx)
        elif t is ActivityForeach:
            await self._foreach(stmt, ctx)
        elif t is ActivityReplicate:
            await self._replicate(stmt, ctx)
        elif t is ActivitySelect:
            await self._select(stmt, ctx)
        elif t is ActivityIfElse:
            await self._if_else(stmt, ctx)
        elif t is ActivityMatch:
            await self._match(stmt, ctx)
        elif t is ActivityConstraint:
            pass  # scheduling constraint — no runtime action in Phase 1
        elif t is ActivityBind:
            await self._bind(stmt, ctx)
        else:
            raise RuntimeError(f"Unhandled activity node: {type(stmt).__name__}")

    # ------------------------------------------------------------------
    # Sequential block
    # ------------------------------------------------------------------

    async def _seq(self, node: ActivitySequenceBlock, ctx: ActionContext) -> None:
        # Pre-scan for ActivityConstraint nodes and build a constraint map.
        # Keys are handle/label names referenced in the constraint expressions.
        constraint_map: dict[str, list] = {}
        for stmt in node.stmts:
            if type(stmt) is ActivityConstraint:
                for expr in stmt.constraints:
                    for name in _extract_handle_names(expr):
                        constraint_map.setdefault(name, []).append(expr)

        for stmt in node.stmts:
            if type(stmt) is ActivityConstraint:
                continue  # already processed above
            # Attach any matching inline constraints to traversal nodes
            t = type(stmt)
            if t is ActivityTraversal and stmt.handle in constraint_map:
                stmt = _stmt_with_constraints(stmt, constraint_map[stmt.handle])
            elif t is ActivityAnonTraversal and stmt.label and stmt.label in constraint_map:
                stmt = _stmt_with_constraints(stmt, constraint_map[stmt.label])
            await self._exec(stmt, ctx)

    # ------------------------------------------------------------------
    # Action traversal — core lifecycle
    # ------------------------------------------------------------------

    async def _traverse(
        self,
        action_type: type,
        inline_constraints: list,
        ctx: ActionContext,
        label: Optional[str] = None,
        head_resource_hints: Optional[dict] = None,
    ) -> Any:
        """Full PSS action traversal lifecycle:
          1. Instantiate
          2. Assign comp
          3. pre_solve()
          4. randomize()
          5. post_solve()
          6. body() or recurse into sub-activity
        """
        # 1. Instantiate using object.__new__ and set dataclass field defaults
        action = object.__new__(action_type)
        try:
            fields = dc.fields(action_type)
        except TypeError:
            fields = ()
        for f in fields:
            if f.default is not dc.MISSING:
                object.__setattr__(action, f.name, f.default)
            elif f.default_factory is not dc.MISSING:
                object.__setattr__(action, f.name, f.default_factory())
            else:
                object.__setattr__(action, f.name, None)

        # 2. Assign comp
        action.comp = ctx.pool_resolver.select_comp(action_type, ctx.comp)

        # Notify tracer
        if ctx.tracer is not None:
            ctx.tracer.action_start(action_type, action.comp, ctx.seed)

        # 3. pre_solve
        action.pre_solve()

        # 4. Randomize — apply inline constraints when present
        child_seed = ctx.seed ^ id(action_type)
        try:
            from ..solver.api import RandomizationError, randomize_with_ast_constraints
            if inline_constraints:
                randomize_with_ast_constraints(
                    action,
                    inline_constraints,
                    handle=label,
                    seed=child_seed,
                )
            else:
                randomize(action, seed=child_seed)
        except RandomizationError as e:
            if "No random variables" not in str(e):
                raise

        # Notify tracer
        if ctx.tracer is not None:
            ctx.tracer.action_solved(action)

        # 5. post_solve
        action.post_solve()

        # Build child context — inherit flow_bindings from parent context
        child_ctx = ActionContext(
            action=action,
            comp=action.comp,
            pool_resolver=ctx.pool_resolver,
            parent=ctx,
            seed=child_seed,
            inline_constraints=[],
            flow_bindings=ctx.flow_bindings,
            head_resource_hints=head_resource_hints or {},
            tracer=ctx.tracer,
        )

        # Inject flow-object bindings onto the action
        output_flow_insts = []
        for field_name, binding in child_ctx.flow_bindings.items():
            flow_inst, direction = binding
            from .flow_obj_rt import BufferInstance, StreamInstance, StatePool
            if isinstance(flow_inst, BufferInstance):
                if direction == "output":
                    setattr(action, field_name, flow_inst.obj)
                    output_flow_insts.append(flow_inst)
                else:
                    setattr(action, field_name, await flow_inst.wait_ready())
            elif isinstance(flow_inst, StreamInstance):
                setattr(action, field_name, flow_inst)
            elif isinstance(flow_inst, StatePool):
                setattr(action, field_name, flow_inst)

        # 6. Execute body
        if ctx.tracer is not None:
            ctx.tracer.action_exec_begin(action)
        from .resource_rt import acquire_resources, release_resources
        claims = await acquire_resources(action, child_ctx)
        try:
            await self._exec_action_body(action_type, action, child_ctx)
            for buf_inst in output_flow_insts:
                buf_inst.set_ready()
        finally:
            release_resources(claims)
        if ctx.tracer is not None:
            ctx.tracer.action_exec_end(action)

        return action

    async def _exec_action_body(
        self,
        action_type: type,
        action: Any,
        ctx: ActionContext,
    ) -> None:
        """Execute body() for atomic actions, or walk __activity__ for compound.

        If the action type has ``@extend`` subclasses, all activities are merged
        into an implied schedule block (PSS implied-schedule semantics).
        """
        extensions = _collect_extensions(action_type)
        if len(extensions) > 1:
            # Multiple extensions: implied schedule — run all activities as stages
            from ..ir.activity import ActivitySchedule
            activities = [
                e.__dict__["__activity__"]
                for e in extensions
                if "__activity__" in e.__dict__ and e.__dict__["__activity__"] is not None
            ]
            if activities:
                from ..ir.base import Base
                implied = ActivitySchedule(stmts=activities)
                await self._schedule(implied, ctx)
            else:
                await action.body()
            return

        activity_ir = getattr(action_type, "__activity__", None)
        if activity_ir is not None:
            await ActivityRunner().run(activity_ir, ctx)
        else:
            await action.body()

    # ------------------------------------------------------------------
    # Handle traversal:  self.handle()
    # ------------------------------------------------------------------

    async def _traverse_handle(
        self, node: ActivityTraversal, ctx: ActionContext
    ) -> None:
        handle_val = getattr(ctx.action, node.handle, None)
        if handle_val is not None:
            action_type = type(handle_val)
        else:
            # Field is None — resolve type from annotations
            action_type = _resolve_handle_type(type(ctx.action), node.handle)
            if action_type is None:
                raise RuntimeError(
                    f"Action {type(ctx.action).__name__} has no handle '{node.handle}'"
                )
        traversed = await self._traverse(
            action_type,
            node.inline_constraints,
            ctx,
            head_resource_hints=ctx.head_resource_hints or {},
        )
        # Write traversed instance back onto the handle field
        if ctx.action is not None and hasattr(ctx.action, node.handle):
            setattr(ctx.action, node.handle, traversed)

    # ------------------------------------------------------------------
    # Anonymous traversal:  do(Type)
    # ------------------------------------------------------------------

    async def _traverse_anon(
        self, node: ActivityAnonTraversal, ctx: ActionContext
    ) -> None:
        action_type = _resolve_action_type(node, ctx)
        action = await self._traverse(
            action_type,
            node.inline_constraints,
            ctx,
            label=node.label,
            head_resource_hints=ctx.head_resource_hints or {},
        )
        if node.label and ctx.action is not None and hasattr(ctx.action, node.label):
            setattr(ctx.action, node.label, action)

    # ------------------------------------------------------------------
    # Super traversal:  super().activity()
    # ------------------------------------------------------------------

    async def _super(self, node: ActivitySuper, ctx: ActionContext) -> None:
        parent_activity = _find_super_activity(type(ctx.action))
        if parent_activity is None:
            return
        await ActivityRunner().run(parent_activity, ctx)

    # ------------------------------------------------------------------
    # Phase 2 — parallel, schedule, atomic
    # ------------------------------------------------------------------

    async def _parallel(self, node: ActivityParallel, ctx: ActionContext) -> None:
        from .binding_solver import BindingSolver

        head_types = [_first_action_type(stmt, ctx) for stmt in node.stmts]

        solver = BindingSolver()
        try:
            head_assigns = solver.solve_heads(
                [t for t in head_types if t is not None], ctx
            )
        except RuntimeError:
            head_assigns = []

        coros = []
        for i, stmt in enumerate(node.stmts):
            hints = head_assigns[i].resource_hints if i < len(head_assigns) else {}
            branch_ctx = ActionContext(
                action=ctx.action,
                comp=ctx.comp,
                pool_resolver=ctx.pool_resolver,
                parent=ctx,
                seed=ctx.seed ^ i,
                head_resource_hints=hints,
                tracer=ctx.tracer,
            )
            coros.append(self._exec(stmt, branch_ctx))

        await _gather_with_join(coros, node.join_spec)

    async def _schedule(self, node: ActivitySchedule, ctx: ActionContext) -> None:
        graph = ScheduleGraph.build(node.stmts, ctx)
        graph.create_flow_instances()
        for stage_stmts in graph.stages():
            coros = []
            for stmt in stage_stmts:
                orig_idx = node.stmts.index(stmt)
                raw_bindings = graph.flow_bindings_for_stmt(orig_idx)
                stage_ctx = ActionContext(
                    action=ctx.action,
                    comp=ctx.comp,
                    pool_resolver=ctx.pool_resolver,
                    parent=ctx,
                    seed=ctx.seed ^ orig_idx,
                    flow_bindings={k: v for k, v in raw_bindings.items()},
                    tracer=ctx.tracer,
                )
                coros.append(self._exec(stmt, stage_ctx))
            await asyncio.gather(*coros)

    async def _atomic(self, node: ActivityAtomic, ctx: ActionContext) -> None:
        async with _get_atomic_lock(ctx):
            for stmt in node.stmts:
                await self._exec(stmt, ctx)

    async def _repeat(self, node, ctx):
        from .expr_eval import ExprEval
        count = int(ExprEval(ctx).eval(node.count))
        for i in range(count):
            if node.index_var and ctx.action is not None:
                setattr(ctx.action, node.index_var, i)
            for stmt in node.body:
                await self._exec(stmt, ctx)

    async def _do_while(self, node, ctx):
        from .expr_eval import ExprEval
        while True:
            for stmt in node.body:
                await self._exec(stmt, ctx)
            if not ExprEval(ctx).eval(node.condition):
                break

    async def _while_do(self, node, ctx):
        from .expr_eval import ExprEval
        while ExprEval(ctx).eval(node.condition):
            for stmt in node.body:
                await self._exec(stmt, ctx)

    async def _foreach(self, node, ctx):
        from .expr_eval import ExprEval
        collection = ExprEval(ctx).eval(node.collection)
        for i, item in enumerate(collection):
            if node.index_var and ctx.action is not None:
                setattr(ctx.action, node.index_var, i)
            if ctx.action is not None:
                setattr(ctx.action, node.iterator, item)
            for stmt in node.body:
                await self._exec(stmt, ctx)

    async def _replicate(self, node, ctx):
        from .expr_eval import ExprEval
        count = int(ExprEval(ctx).eval(node.count))
        for i in range(count):
            if node.index_var and ctx.action is not None:
                setattr(ctx.action, node.index_var, i)
            for stmt in node.body:
                await self._exec(stmt, ctx)

    async def _select(self, node, ctx):
        import random
        from .expr_eval import ExprEval
        ev = ExprEval(ctx)
        eligible = [
            b for b in node.branches
            if b.guard is None or ev.eval(b.guard)
        ]
        if not eligible:
            raise RuntimeError("select: no eligible branch (all guards false)")
        weights = [
            int(ev.eval(b.weight)) if b.weight is not None else 1
            for b in eligible
        ]
        chosen = random.choices(eligible, weights=weights, k=1)[0]
        for stmt in chosen.body:
            await self._exec(stmt, ctx)

    async def _if_else(self, node, ctx):
        from .expr_eval import ExprEval
        cond = ExprEval(ctx).eval(node.condition)
        body = node.if_body if cond else node.else_body
        for stmt in body:
            await self._exec(stmt, ctx)

    async def _match(self, node, ctx):
        from .expr_eval import ExprEval
        ev = ExprEval(ctx)
        subject = ev.eval(node.subject)
        for case in node.cases:
            pattern = ev.eval(case.pattern)
            if subject == pattern:
                for stmt in case.body:
                    await self._exec(stmt, ctx)
                return
    async def _bind(self, node, ctx):     pass  # Phase 5


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _resolve_action_type(node: ActivityAnonTraversal, ctx: ActionContext) -> type:
    """Return the Python class for an ActivityAnonTraversal node."""
    if node.action_type_cls is not None:
        return node.action_type_cls
    import sys
    module = sys.modules.get(type(ctx.action).__module__) if ctx.action is not None else None
    if module:
        cls = getattr(module, node.action_type, None)
        if cls is not None:
            return cls
    raise RuntimeError(
        f"Cannot resolve action type '{node.action_type}' "
        f"in module '{type(ctx.action).__module__ if ctx.action is not None else '<unknown>'}'"
    )


def _find_super_activity(action_type: type):
    """Find the __activity__ IR from the first base class that defines it."""
    for base in action_type.__mro__[1:]:
        if "__activity__" in base.__dict__:
            return base.__dict__["__activity__"]
    return None


def _collect_extensions(action_type: type) -> list:
    """Return *action_type* plus any ``@extend`` subclasses registered for it."""
    result = [action_type]
    for sub in action_type.__subclasses__():
        if getattr(sub, "__is_extension__", False) and getattr(sub, "__extends__", None) is action_type:
            result.append(sub)
    return result


def _extract_handle_names(stmt) -> list:
    """Return handle names referenced via self.<handle>.<field> in an AST stmt."""
    import ast as _ast
    names = []
    for node in _ast.walk(stmt):
        if (isinstance(node, _ast.Attribute) and
                isinstance(node.value, _ast.Attribute) and
                isinstance(node.value.value, _ast.Name) and
                node.value.value.id == "self"):
            names.append(node.value.attr)
    return list(dict.fromkeys(names))  # deduplicated, order-preserving


def _stmt_with_constraints(stmt, extra_constraints: list):
    """Return a copy of *stmt* with additional inline_constraints attached."""
    import dataclasses as _dc
    # Merge existing + new constraints without mutating the original
    existing = list(getattr(stmt, "inline_constraints", []))
    new_stmt = _dc.replace(stmt, inline_constraints=existing + extra_constraints)
    return new_stmt


# ------------------------------------------------------------------
# Parallel/atomic helpers
# ------------------------------------------------------------------

async def _gather_with_join(coros: list, join_spec) -> None:
    """Run coroutines according to the join policy in *join_spec*."""
    import asyncio

    if join_spec is None or join_spec.kind == "all":
        await asyncio.gather(*coros)

    elif join_spec.kind == "none":
        for c in coros:
            asyncio.create_task(c)

    elif join_spec.kind == "first":
        n = 1
        if join_spec.count is not None:
            try:
                n = int(join_spec.count)
            except (TypeError, ValueError):
                n = 1
        tasks = [asyncio.create_task(c) for c in coros]
        done_count = 0
        pending = set(tasks)
        while done_count < n and pending:
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )
            done_count += len(done)
        # Cancel remaining tasks
        for t in pending:
            t.cancel()

    elif join_spec.kind == "select":
        import random as _random
        n = 1
        if join_spec.count is not None:
            try:
                n = int(join_spec.count)
            except (TypeError, ValueError):
                n = 1
        tasks = [asyncio.create_task(c) for c in coros]
        chosen = _random.sample(tasks, k=min(n, len(tasks)))
        unchosen = [t for t in tasks if t not in chosen]
        for t in unchosen:
            t.cancel()
        await asyncio.gather(*chosen, return_exceptions=True)

    else:
        # Fallback: join all
        await asyncio.gather(*coros)


_atomic_locks: dict[int, asyncio.Lock] = {}


def _get_atomic_lock(ctx: ActionContext) -> asyncio.Lock:
    """Return (or create) an asyncio.Lock scoped to the pool_resolver tree."""
    key = id(ctx.pool_resolver)
    if key not in _atomic_locks:
        _atomic_locks[key] = asyncio.Lock()
    return _atomic_locks[key]


def _first_action_type(stmt: ActivityStmt, ctx: ActionContext) -> Optional[type]:
    """Return the action type of the first traversal in a statement subtree."""
    if isinstance(stmt, ActivityTraversal):
        return _resolve_handle_type(type(ctx.action), stmt.handle) if ctx.action else None
    if isinstance(stmt, ActivityAnonTraversal):
        return stmt.action_type_cls or None
    if isinstance(stmt, ActivitySequenceBlock) and stmt.stmts:
        return _first_action_type(stmt.stmts[0], ctx)
    return None


# ---------------------------------------------------------------------------
# Flow-object helpers for ScheduleGraph
# ---------------------------------------------------------------------------

def _get_action_type_from_stmt(stmt, ctx: "ActionContext") -> Optional[type]:
    """Return the primary action type for a stmt (traversal nodes only)."""
    if isinstance(stmt, ActivityAnonTraversal):
        return _resolve_action_type(stmt, ctx)
    if isinstance(stmt, ActivityTraversal):
        return _resolve_handle_type(type(ctx.action), stmt.handle) if ctx.action else None
    return None


def _flow_field_types(action_type: type, direction: str) -> set:
    """Return set of (field_name, flow_type) tuples for fields with the given direction."""
    if action_type is None:
        return set()
    try:
        fields = dc.fields(action_type)
    except TypeError:
        return set()
    result = set()
    for f in fields:
        meta = f.metadata or {}
        if meta.get("kind") == "flow_ref" and meta.get("direction") == direction:
            ann = {}
            for klass in action_type.__mro__:
                ann.update(klass.__dict__.get("__annotations__", {}))
            ftype = ann.get(f.name)
            if ftype is not None and isinstance(ftype, type):
                result.add((f.name, ftype))
    return result


def _flow_outputs(stmt, ctx: "ActionContext") -> set:
    """Return set of (field_name, flow_type) tuples that this stmt produces."""
    at = _get_action_type_from_stmt(stmt, ctx)
    return _flow_field_types(at, "output")


def _flow_inputs(stmt, ctx: "ActionContext") -> set:
    """Return set of (field_name, flow_type) tuples that this stmt consumes."""
    at = _get_action_type_from_stmt(stmt, ctx)
    return _flow_field_types(at, "input")


class ScheduleGraph:
    """Builds a partial order from flow-object producer/consumer relationships
    among the statements in a schedule block."""

    def __init__(self):
        self._stmts: list = []
        self._edges: list = []          # (producer_idx, consumer_idx)
        self._flow_connections: list = []  # (prod_idx, prod_field, cons_idx, cons_field, flow_type)

    @staticmethod
    def build(stmts: list, ctx: "ActionContext") -> "ScheduleGraph":
        graph = ScheduleGraph()
        graph._stmts = stmts
        for i, s_a in enumerate(stmts):
            outputs = _flow_outputs(s_a, ctx)
            for j, s_b in enumerate(stmts):
                if i == j:
                    continue
                inputs = _flow_inputs(s_b, ctx)
                for (out_field, out_type) in outputs:
                    for (in_field, in_type) in inputs:
                        try:
                            if out_type is in_type or (
                                isinstance(out_type, type) and isinstance(in_type, type)
                                and issubclass(out_type, in_type)
                            ):
                                if (i, j) not in [(e[0], e[1]) for e in graph._edges]:
                                    graph._edges.append((i, j))
                                graph._flow_connections.append(
                                    (i, out_field, j, in_field, out_type)
                                )
                        except TypeError:
                            pass
        return graph

    def stages(self) -> list:
        """Return statements grouped into parallel stages via topological sort (Kahn's)."""
        from collections import deque
        n = len(self._stmts)
        if n == 0:
            return []
        in_degree = [0] * n
        adj: dict = {i: [] for i in range(n)}
        for src, dst in self._edges:
            adj[src].append(dst)
            in_degree[dst] += 1
        queue = deque(i for i in range(n) if in_degree[i] == 0)
        stages = []
        visited = 0
        while queue:
            stage_indices = list(queue)
            queue.clear()
            stages.append([self._stmts[i] for i in stage_indices])
            visited += len(stage_indices)
            for i in stage_indices:
                for j in adj[i]:
                    in_degree[j] -= 1
                    if in_degree[j] == 0:
                        queue.append(j)
        if visited < n:
            raise RuntimeError(
                "ScheduleGraph: cyclic dependency detected among schedule statements"
            )
        return stages

    def flow_bindings_for_stmt(self, stmt_idx: int) -> dict:
        """Return a mapping field_name → (flow_instance, direction) for stmt_idx."""
        return self._bindings_by_stmt.get(stmt_idx, {})

    def create_flow_instances(self) -> None:
        """Create all BufferInstance/StreamInstance/StatePool objects."""
        from .flow_obj_rt import BufferInstance, StreamInstance, StatePool
        from ..types import Buffer, Stream, State
        from .resource_rt import make_resource

        self._bindings_by_stmt: dict = {}

        for prod_idx, prod_field, cons_idx, cons_field, flow_type in self._flow_connections:
            try:
                is_buffer = isinstance(flow_type, type) and issubclass(flow_type, Buffer)
                is_stream = isinstance(flow_type, type) and issubclass(flow_type, Stream)
                is_state = isinstance(flow_type, type) and issubclass(flow_type, State)
            except TypeError:
                is_buffer = is_stream = is_state = False

            if is_buffer:
                obj = make_resource(flow_type)
                flow_inst = BufferInstance(obj=obj)
            elif is_stream:
                flow_inst = StreamInstance()
                is_buffer = False
            elif is_state:
                flow_inst = StatePool()
                is_buffer = False
            else:
                continue

            # Producer gets output side
            self._bindings_by_stmt.setdefault(prod_idx, {})[prod_field] = (
                flow_inst, "output" if is_buffer else ("stream" if is_stream else "state")
            )
            # Consumer gets input side
            self._bindings_by_stmt.setdefault(cons_idx, {})[cons_field] = (
                flow_inst, "input" if is_buffer else ("stream" if is_stream else "state")
            )
