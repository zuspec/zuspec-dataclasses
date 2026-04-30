"""Compiled scenario fast path for static sequential PSS activities.

This module implements "compile once, execute many times" at the scenario
level — mirroring what the deterministic constraint analyser does for
individual action solves.  For a static sequential activity (a plain sequence
of ``ActivityAnonTraversal`` nodes with explicit flow wiring and no
parallelism), ``ScenarioCompiler.compile()`` builds a ``CompiledScenario`` in
one pass.  Subsequent calls to ``CompiledScenario.run()`` execute a tight
loop that skips all per-iteration framework overhead:

- No ``dataclasses.fields()`` introspection (pre-computed once).
- No pool / component resolution (pre-resolved once).
- No output-buffer allocation per cycle (fresh objects from pre-computed
  defaults).
- No ``ActionContext`` construction or forward-propagator bookkeeping.
- No activity-runner dispatch tree (direct loop over pre-compiled steps).

Usage::

    compiler = ScenarioCompiler()
    scenario = compiler.compile(EntryAction, comp, pool_resolver)
    if scenario is not None:
        actions = await scenario.run()  # fast path
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import textwrap
from typing import Any, Optional, TYPE_CHECKING

from ..activity_parser import ActivityParser
from ..activity_parser import ActivityAnonTraversal, ActivitySequenceBlock
from .resource_rt import get_resource_fields, release_resources

if TYPE_CHECKING:
    from .pool_resolver import PoolResolver


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class FlowOutputSpec:
    """Pre-computed spec for creating a fresh flow-output object each cycle."""

    field_name: str
    obj_type: type
    # Pre-computed (name, value) pairs for cheap object initialisation
    field_defaults: list


@dataclasses.dataclass
class CompiledStep:
    """Pre-compiled descriptor for a single action in a flat sequence."""

    action_cls: type
    comp: Any                   # pre-resolved component instance
    label: str                  # label in the activity (e.g. "dec")

    # Pre-computed (name, value) list for object.__new__ instantiation
    field_defaults: list

    # Flow inputs: list of (my_field_name, src_step_index, src_attr_name)
    flow_inputs: list

    # Flow output specs: one entry per output flow-ref field
    flow_output_specs: list     # list[FlowOutputSpec]

    # Compiled deterministic solve function, or None → generic randomize()
    solve_fn: Optional[Any]

    # True if body() contains at least one real `await` expression
    has_async_body: bool

    # Pre-computed resource fields (empty list for most stages)
    resource_fields: list


@dataclasses.dataclass
class CompiledScenario:
    """Pre-compiled execution plan for a static sequential PSS scenario.

    Built once by ``ScenarioCompiler.compile()``.  Call ``run()`` on every
    scenario iteration.
    """

    steps: list             # list[CompiledStep]
    pool_resolver: Any      # PoolResolver
    entry_cls: Any = None   # type of the enclosing orchestrator action
    entry_comp: Any = None  # pre-resolved component for the entry action
    entry_field_defaults: list = dataclasses.field(default_factory=list)

    async def run(self, tracer=None) -> Any:
        """Execute one scenario iteration using the compiled fast path.

        Returns the entry action instance (the orchestrator whose activity
        was compiled into these steps), with labeled sub-action results
        written back onto its fields.
        """
        from ..solver.api import randomize

        # Create the entry (orchestrator) action and fire its tracer event
        entry = None
        if self.entry_cls is not None:
            entry = object.__new__(self.entry_cls)
            for name, val in self.entry_field_defaults:
                object.__setattr__(entry, name, val)
            if self.entry_comp is not None:
                object.__setattr__(entry, "comp", self.entry_comp)
            if tracer is not None:
                tracer.action_start(self.entry_cls, entry, 0)

        actions: list = [None] * len(self.steps)

        for i, step in enumerate(self.steps):
            # 1. Instantiate action with pre-computed field defaults
            action = object.__new__(step.action_cls)
            for name, val in step.field_defaults:
                object.__setattr__(action, name, val)
            object.__setattr__(action, "comp", step.comp)

            # 2. Create fresh flow-output objects from pre-computed defaults
            #    (fresh each cycle to avoid stale values across iterations)
            for spec in step.flow_output_specs:
                obj = object.__new__(spec.obj_type)
                for name, val in spec.field_defaults:
                    object.__setattr__(obj, name, val)
                object.__setattr__(action, spec.field_name, obj)

            # 3. Wire flow inputs from completed earlier steps
            for my_field, src_idx, src_attr in step.flow_inputs:
                object.__setattr__(
                    action, my_field, getattr(actions[src_idx], src_attr)
                )

            # 4. pre_solve hook (usually a no-op)
            action.pre_solve()

            # Notify tracer before solving
            if tracer is not None:
                tracer.action_start(step.action_cls, action, 0)

            # 5. Solve — compiled deterministic function when available.
            #    solve_fn is captured at compile time but _zdc_compiled_solve is
            #    set lazily on first randomize() call, so check at runtime and
            #    cache in the step on first hit (avoids repeated getattr).
            solve_fn = step.solve_fn
            if solve_fn is None:
                solve_fn = getattr(step.action_cls, "_zdc_compiled_solve", None)
                if solve_fn is not None:
                    step.solve_fn = solve_fn  # cache for next iteration
            if solve_fn is not None:
                solve_fn(action)
            else:
                randomize(action)
                # randomize() may have triggered deterministic compilation — cache it
                fn = getattr(step.action_cls, "_zdc_compiled_solve", None)
                if fn is not None:
                    step.solve_fn = fn

            # 6. post_solve hook (usually a no-op)
            action.post_solve()

            # Notify tracer after solving
            if tracer is not None:
                tracer.action_solved(action)

            # 7. Acquire resources (empty list for most stages — skip branch)
            claims: list = []
            if step.resource_fields:
                claims = await _fast_acquire(action, step, self.pool_resolver)

            # 8. Execute body
            if step.has_async_body:
                await action.body()
            else:
                _run_sync_coro(action.body())

            # 9. Release resources
            if claims:
                release_resources(claims)

            actions[i] = action

        # Write labeled sub-actions back onto the entry action's fields
        if entry is not None:
            for i, step in enumerate(self.steps):
                if step.label and hasattr(entry, step.label):
                    object.__setattr__(entry, step.label, actions[i])
            if tracer is not None:
                tracer.action_solved(entry)
            return entry

        # No entry action — return last step result (legacy pipeline behaviour)
        return actions[-1] if actions else None


# ---------------------------------------------------------------------------
# Compiler
# ---------------------------------------------------------------------------


class ScenarioCompiler:
    """Analyses a static sequential activity and produces a CompiledScenario.

    Returns ``None`` if the activity is not compilable (parallel, conditional,
    structural-inference nodes, etc.).
    """

    def compile(
        self,
        action_type: type,
        comp: Any,
        pool_resolver: "PoolResolver",
    ) -> Optional[CompiledScenario]:
        """Build a :class:`CompiledScenario`, or return ``None`` if not compilable."""
        activity_fn = getattr(action_type, "activity", None)
        if activity_fn is None:
            return None

        try:
            ir = ActivityParser().parse(activity_fn)
        except Exception:
            return None

        if not isinstance(ir, ActivitySequenceBlock):
            return None
        if not _is_flat_sequence(ir):
            return None

        # Resolve entry action component
        try:
            entry_comp = pool_resolver.select_comp(action_type, comp)
        except Exception:
            entry_comp = comp
        entry_field_defaults = _compute_field_defaults(action_type)

        steps: list = []
        label_to_idx: dict = {}

        for node in ir.stmts:
            action_cls = node.action_type_cls
            if action_cls is None:
                return None

            # Fall back to slow path if any child is a compound action (has its own
            # activity IR) — the fast path only handles leaf-body execution.
            if "__activity__" in action_cls.__dict__:
                return None

            # Fall back if any step has inline constraints — those need
            # randomize_with_ast_constraints, not plain randomize().
            if node.inline_constraints:
                return None

            # Resolve component once (static topology)
            try:
                resolved_comp = pool_resolver.select_comp(action_cls, comp)
            except Exception:
                return None

            # Pre-compute field defaults for cheap instantiation
            field_defaults = _compute_field_defaults(action_cls)

            # Translate init_bindings → (my_field, src_step_index, src_attr)
            flow_inputs: list = []
            for my_field, src_label, src_attr in (node.init_bindings or []):
                if src_label not in label_to_idx:
                    return None  # unresolvable binding — fall back
                flow_inputs.append((my_field, label_to_idx[src_label], src_attr))

            # Build flow output specs
            flow_output_specs = _build_flow_output_specs(action_cls)

            # Compiled deterministic solve function (set by analyser, or None)
            solve_fn = getattr(action_cls, "_zdc_compiled_solve", None)

            # AST inspection for real await in body()
            has_async_body = _body_has_real_await(action_cls)

            # Resource fields (pre-computed; empty for most stages)
            resource_fields = get_resource_fields(action_cls)

            step = CompiledStep(
                action_cls=action_cls,
                comp=resolved_comp,
                label=node.label or "",
                field_defaults=field_defaults,
                flow_inputs=flow_inputs,
                flow_output_specs=flow_output_specs,
                solve_fn=solve_fn,
                has_async_body=has_async_body,
                resource_fields=resource_fields,
            )
            steps.append(step)
            if node.label:
                label_to_idx[node.label] = len(steps) - 1

        return CompiledScenario(
            steps=steps,
            pool_resolver=pool_resolver,
            entry_cls=action_type,
            entry_comp=entry_comp,
            entry_field_defaults=entry_field_defaults,
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _is_flat_sequence(ir: ActivitySequenceBlock) -> bool:
    """True iff *ir* contains only ``ActivityAnonTraversal`` nodes."""
    for stmt in ir.stmts:
        if not isinstance(stmt, ActivityAnonTraversal):
            return False
    return True


def _compute_field_defaults(action_type: type) -> list:
    """Pre-compute ``(field_name, default_value)`` pairs for *action_type*.

    Called once per class during compilation.  The result is stored on the
    ``CompiledStep`` and applied via ``object.__setattr__`` in a tight loop
    at runtime — replacing the per-iteration ``dataclasses.fields()`` call.
    """
    result: list = []
    try:
        fields = dataclasses.fields(action_type)
    except TypeError:
        return result
    for f in fields:
        if f.default is not dataclasses.MISSING:
            result.append((f.name, f.default))
        elif f.default_factory is not dataclasses.MISSING:
            result.append((f.name, f.default_factory()))
        else:
            result.append((f.name, None))
    return result


def _build_flow_output_specs(action_type: type) -> list:
    """Build a :class:`FlowOutputSpec` for each flow-output field.

    Called once per class during compilation.
    """
    # Collect all annotations from MRO (most-derived wins)
    ann_map: dict = {}
    for klass in reversed(action_type.__mro__):
        ann_map.update(klass.__dict__.get("__annotations__", {}))

    result: list = []
    try:
        fields = dataclasses.fields(action_type)
    except TypeError:
        return result

    for f in fields:
        meta = f.metadata or {}
        if meta.get("kind") != "flow_ref" or meta.get("direction") != "output":
            continue
        output_type = ann_map.get(f.name)
        if isinstance(output_type, type):
            result.append(
                FlowOutputSpec(
                    field_name=f.name,
                    obj_type=output_type,
                    field_defaults=_compute_field_defaults(output_type),
                )
            )
    return result


def _body_has_real_await(action_type: type) -> bool:
    """Return ``True`` if ``body()`` contains at least one ``await`` node.

    Uses AST inspection on the first ``body`` definition found in the MRO.
    Falls back to ``True`` (conservative — uses the event loop) on any error.
    """
    body_fn = None
    for klass in action_type.__mro__:
        if "body" in klass.__dict__:
            body_fn = klass.__dict__["body"]
            break
    if body_fn is None:
        return False

    try:
        src = inspect.getsource(body_fn)
        tree = ast.parse(textwrap.dedent(src))
        for node in ast.walk(tree):
            if isinstance(node, ast.Await):
                return True
        return False
    except Exception:
        return True  # conservative fallback


def _run_sync_coro(coro: Any) -> None:
    """Drive a no-await coroutine to completion without touching the event loop.

    Used for ``async def body()`` methods that contain no real ``await``
    (e.g. Decode, Execute, Writeback stages).  The coroutine executes
    synchronously and raises ``StopIteration`` immediately.
    """
    try:
        coro.send(None)
    except StopIteration:
        pass
    finally:
        coro.close()


async def _fast_acquire(action: Any, step: CompiledStep, pool_resolver: Any) -> list:
    """Simplified resource acquisition using the pre-computed resource_fields list.

    Mirrors ``acquire_resources()`` from ``resource_rt.py`` but takes the
    pre-computed ``resource_fields`` list directly instead of calling
    ``get_resource_fields()`` each time.  Reads ``action._zdc_resource_hints``
    (set by the constraint solver) to pin each share/lock to a specific slot.
    """
    hints: dict = getattr(action, '_zdc_resource_hints', {}) or {}

    entries: list = []
    for fi in step.resource_fields:
        pool = pool_resolver.resolve_pool(action, fi.name)
        if pool is None:
            continue
        instance_id = hints.get(fi.name)
        entries.append((pool, fi, instance_id))

    # Sort by (pool identity, instance_id) for deadlock-free ordering
    entries.sort(key=lambda e: (id(e[0]), e[2] if e[2] is not None else -1))

    claims: list = []
    for pool, fi, instance_id in entries:
        filter_fn = None
        if instance_id is not None:
            filter_fn = lambda _r, i, _iid=instance_id: i == _iid
        if fi.claim == "lock":
            claim = await pool.lock(filter=filter_fn)
            # Apply solver write-back (e.g. assert self.rd_reg.t == alu_out)
            write_val = hints.get(f"{fi.name}.t")
            if write_val is not None:
                claim.t = write_val
        else:
            claim = await pool.share(filter=filter_fn)
        object.__setattr__(action, fi.name, claim.t)
        claims.append((pool, claim))

    return claims
