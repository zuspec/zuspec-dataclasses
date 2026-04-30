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

from zuspec.ir.core.activity import (
    ActivityAnonTraversal,
    ActivityAtomic,
    ActivityBind,
    ActivityChain,
    ActivityConstraint,
    ActivityConstraintForall,
    ActivityDoWhile,
    ActivityFill,
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


def _split_hier_expr(expr) -> tuple:
    """Extract (label, field_name) from a two-level ExprAttribute chain.

    ``ExprAttribute(ExprAttribute(TypeExprRefSelf, label), field)``
    -> ``(label, field)``

    Returns ``(None, None)`` if the expression does not match this pattern.
    """
    from zuspec.ir.core.expr import ExprAttribute, TypeExprRefSelf
    if not isinstance(expr, ExprAttribute):
        return (None, None)
    outer_attr = expr.attr
    inner = expr.value
    if not isinstance(inner, ExprAttribute):
        return (None, None)
    label = inner.attr
    return (label, outer_attr)


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


import functools as _functools


@_functools.lru_cache(maxsize=None)
def _action_has_rand_fields(action_type: type) -> bool:
    """Cached check: does *action_type* have any rand/randc fields?"""
    try:
        import dataclasses as _dc
        struct = getattr(action_type, '_zdc_struct', None)
        if struct is not None:
            from ..ir.core.data_type import FieldKind
            return any(getattr(f, 'rand_kind', None) is not None for f in struct.fields)
        # Fallback: inspect the dataclass fields directly
        for f in _dc.fields(action_type):
            if f.metadata and f.metadata.get('rand'):
                return True
        return False
    except Exception:
        return True  # conservative: assume yes


def _eval_comp_path(expr, root_comp: Any) -> Any:
    """Evaluate a PSS component-path expression rooted at *root_comp*.

    In PSS, component paths like pss_top.spi_initiators[0] are encoded in IR
    as ExprSubscript(ExprAttribute(ExprAttribute(TypeExprRefSelf, 'pss_top'),
    'spi_initiators'), ExprConstant(0)).  TypeExprRefSelf resolves to root_comp,
    and the first attribute (the component type name) is the PSS absolute-path
    anchor -- it refers to the root comp itself rather than a named field on it.

    The anchor is detected by comparing the attribute string against the runtime
    type name of root_comp (i.e. type(root_comp).__name__).  This is a language-
    level semantic check (PSS LRM requires comp paths to start with the comp type
    name), not a user-imposed naming convention.
    """
    from zuspec.ir.core.expr import (
        ExprAttribute, TypeExprRefSelf, ExprSubscript, ExprConstant,
        ExprRefUnresolved,
    )

    def _walk(node: Any) -> Any:
        if isinstance(node, TypeExprRefSelf):
            return root_comp
        if isinstance(node, ExprAttribute):
            base = _walk(node.value)
            if base is None:
                return None
            # PSS absolute-path anchor: the first attribute after TypeExprRefSelf
            # is the component type name (e.g. 'pss_top').  Skip it and return
            # the root comp directly -- the base IS root_comp here.
            if isinstance(node.value, TypeExprRefSelf) and node.attr == type(root_comp).__name__:
                return root_comp
            return getattr(base, node.attr, None)
        if isinstance(node, ExprSubscript):
            base = _walk(node.value)
            idx = _walk(node.slice)
            if base is None or idx is None:
                return None
            try:
                return base[int(idx)]
            except (TypeError, IndexError):
                return None
        if isinstance(node, ExprConstant):
            return node.value
        if isinstance(node, ExprRefUnresolved):
            # Single unresolved name -- try as a field on root_comp
            return getattr(root_comp, node.name, None)
        return None

    return _walk(expr)


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
        elif t is ActivityFill:
            await self._fill(stmt, ctx)
        elif t is ActivityChain:
            await self._chain(stmt, ctx)
        elif t is ActivityConstraintForall:
            pass  # forall constraints are advisory in Phase 3; bounded enumeration deferred
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

        # Pre-scan for ActivityBind: build explicit routing table (2-B).
        # Maps (dst_label, dst_field) -> (src_label, src_field).
        explicit_binds: dict[tuple, tuple] = {}
        for stmt in node.stmts:
            if type(stmt) is ActivityBind:
                src_label, src_field = _split_hier_expr(stmt.src)
                dst_label, dst_field = _split_hier_expr(stmt.dst)
                if src_label and dst_label:
                    explicit_binds[(dst_label, dst_field)] = (src_label, src_field)

        # Forward constraint propagation: create a fresh propagator for this
        # sequence block.  It records completed actions' field values so that
        # subsequent inline constraints can reference them as label.field.
        from .forward_constraint_propagator import ForwardConstraintPropagator
        propagator = ForwardConstraintPropagator()

        # Running store of resolved flow objects produced by labeled traversals.
        # Maps label -> action_instance (populated after each traversal).
        label_actions: dict[str, object] = {}

        # Build per-traversal flow_bindings from explicit binds resolved so far.
        def _resolved_bindings_for(label: str) -> dict:
            """Build flow_bindings injecting any explicit-bind inputs for `label`."""
            from .flow_obj_rt import BufferInstance
            result = dict(ctx.flow_bindings)
            for (dst_lbl, dst_field), (src_lbl, src_field) in explicit_binds.items():
                if dst_lbl != label:
                    continue
                src_action = label_actions.get(src_lbl)
                if src_action is None:
                    continue
                val = getattr(src_action, src_field, None)
                if val is None:
                    continue
                # Wrap in a ready BufferInstance so _traverse injects it as input
                bi = BufferInstance(obj=val)
                bi.set_ready()
                result[dst_field] = (bi, "input")
            return result

        for stmt in node.stmts:
            if type(stmt) is ActivityConstraint:
                continue  # already processed above
            if type(stmt) is ActivityBind:
                continue  # structural -- handled via explicit_binds above

            # Determine label for this traversal (if any) to look up resolved bindings
            stmt_label = None
            if type(stmt) is ActivityTraversal:
                stmt_label = stmt.handle
            elif type(stmt) is ActivityAnonTraversal:
                stmt_label = stmt.label

            resolved_binds = (
                _resolved_bindings_for(stmt_label)
                if stmt_label is not None
                else dict(ctx.flow_bindings)
            )

            seq_ctx = ActionContext(
                action=ctx.action,
                comp=ctx.comp,
                pool_resolver=ctx.pool_resolver,
                parent=ctx,
                seed=ctx.seed,
                inline_constraints=ctx.inline_constraints,
                flow_bindings=resolved_binds,
                head_resource_hints=ctx.head_resource_hints,
                structural_solver=ctx.structural_solver,
                forward_propagator=propagator,
                tracer=ctx.tracer,
                check_contracts=ctx.check_contracts,
                coverage_model=ctx.coverage_model,
            )

            # Attach any matching inline constraints to traversal nodes
            t = type(stmt)
            if t is ActivityTraversal and stmt.handle in constraint_map:
                stmt = _stmt_with_constraints(stmt, constraint_map[stmt.handle])
            elif t is ActivityAnonTraversal and stmt.label and stmt.label in constraint_map:
                stmt = _stmt_with_constraints(stmt, constraint_map[stmt.label])

            await self._exec(stmt, seq_ctx)

            # Record completed action instance so downstream binds can reference it
            if stmt_label is not None and ctx.action is not None:
                act_inst = getattr(ctx.action, stmt_label, None)
                if act_inst is not None:
                    label_actions[stmt_label] = act_inst

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
        comp_override: Optional[Any] = None,   # WI-6: explicit component instance
    ) -> Any:
        """Full PSS action traversal lifecycle:
          1. Instantiate
          2. Assign comp
          2b. Inject flow-object bindings (before pre_solve so hooks see the flow obj)
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

        # 2. Assign comp — use explicit override when provided (WI-6 comp== routing)
        if comp_override is not None:
            action.comp = comp_override
        else:
            action.comp = ctx.pool_resolver.select_comp(action_type, ctx.comp)

        # 2b. Inject flow-object bindings BEFORE pre_solve so that pre_solve(),
        #     randomize(), and post_solve() all see the concrete flow object.
        #     For output (producer): the flow object was already randomized in
        #     create_flow_instances(); set it directly.
        #     For input (consumer): await the buffer being ready — safe here
        #     because ScheduleGraph guarantees the producer stage has completed
        #     before the consumer stage starts.
        output_flow_insts = []
        from .flow_obj_rt import BufferInstance, StreamInstance, StatePool
        for field_name, binding in ctx.flow_bindings.items():
            flow_inst, direction = binding
            if isinstance(flow_inst, BufferInstance):
                if direction == "output":
                    setattr(action, field_name, flow_inst.obj)
                    output_flow_insts.append(flow_inst)
                else:
                    setattr(action, field_name, await flow_inst.wait_ready())
            elif isinstance(flow_inst, StreamInstance):
                setattr(action, field_name, flow_inst)
            elif isinstance(flow_inst, StatePool):
                # State flow binding: inject concrete state object, not pool.
                # direction "state" is used for both input and output in flow_bindings;
                # check annotation metadata to distinguish producer vs consumer.
                _dir = direction  # "output", "input", or "state"
                ann: dict = {}
                for _kls in action_type.__mro__:
                    ann.update(_kls.__dict__.get("__annotations__", {}))
                import dataclasses as _dcf
                try:
                    _fields_meta = {
                        f.name: (f.metadata or {})
                        for f in _dcf.fields(action_type)
                    }
                except TypeError:
                    _fields_meta = {}
                _meta = _fields_meta.get(field_name, {})
                _field_dir = _meta.get("direction", _dir)  # "input" or "output"

                if _field_dir == "output":
                    # Producer: create a fresh state instance; set initial=False
                    # (the pool manages the initial flag; output always updates state)
                    _state_type = ann.get(field_name)
                    if isinstance(_state_type, type):
                        _new_state = object.__new__(_state_type)
                        try:
                            for _f in _dcf.fields(_state_type):
                                if _f.default is not _dcf.MISSING:
                                    object.__setattr__(_new_state, _f.name, _f.default)
                                elif _f.default_factory is not _dcf.MISSING:
                                    object.__setattr__(_new_state, _f.name, _f.default_factory())
                                else:
                                    object.__setattr__(_new_state, _f.name, None)
                        except TypeError:
                            pass
                        # initial=False: this is an output transition, not the first state
                        if hasattr(_new_state, 'initial'):
                            object.__setattr__(_new_state, 'initial', False)
                        setattr(action, field_name, _new_state)
                    else:
                        setattr(action, field_name, flow_inst)  # fallback
                else:
                    # Consumer: inject pool.current or create initial state
                    if flow_inst.initial or flow_inst.current is None:
                        # First ever state: create initial instance
                        _state_type = ann.get(field_name)
                        if isinstance(_state_type, type):
                            _init_state = object.__new__(_state_type)
                            try:
                                for _f in _dcf.fields(_state_type):
                                    if _f.default is not _dcf.MISSING:
                                        object.__setattr__(_init_state, _f.name, _f.default)
                                    elif _f.default_factory is not _dcf.MISSING:
                                        object.__setattr__(_init_state, _f.name, _f.default_factory())
                                    else:
                                        object.__setattr__(_init_state, _f.name, None)
                            except TypeError:
                                pass
                            if hasattr(_init_state, 'initial'):
                                object.__setattr__(_init_state, 'initial', True)
                            setattr(action, field_name, _init_state)
                        else:
                            setattr(action, field_name, flow_inst)
                    else:
                        # Subsequent state: use current and mark initial=False
                        _cur = flow_inst.current
                        if hasattr(_cur, 'initial'):
                            object.__setattr__(_cur, 'initial', False)
                        setattr(action, field_name, _cur)
                # Store the pool reference for post-body state write-back
                output_flow_insts.append(('state_pool', field_name, flow_inst,
                                          _field_dir == "output"))

        # For any unbound flow-output fields (no explicit consumer provided),
        # create an orphan buffer so that body() can write to the field.
        _create_orphan_output_buffers(action_type, action, ctx.flow_bindings)
        # Notify tracer
        if ctx.tracer is not None:
            ctx.tracer.action_start(action_type, action.comp, ctx.seed)

        # 3. pre_solve
        action.pre_solve()

        # 4. Randomize — apply inline constraints when present.
        # If a forward propagator is active, substitute cross-action label.field
        # references in the constraint AST before solving.
        child_seed = ctx.seed ^ id(action_type)
        import ast as _ast_mod
        # Partition constraints: Python-AST (for legacy solver) vs IR-expression.
        py_ast_inline = [c for c in inline_constraints if isinstance(c, _ast_mod.stmt)]
        ir_expr_inline = [c for c in inline_constraints if not isinstance(c, _ast_mod.stmt)]

        effective_py_constraints = py_ast_inline
        if ctx.forward_propagator is not None and py_ast_inline:
            effective_py_constraints = ctx.forward_propagator.substitute(py_ast_inline)
        try:
            from ..solver.api import RandomizationError, randomize_with_ast_constraints
            # Fast-path: skip solver entirely for actions with no rand fields.
            _has_rand = _action_has_rand_fields(action_type)
            if _has_rand or effective_py_constraints:
                if effective_py_constraints:
                    randomize_with_ast_constraints(
                        action,
                        effective_py_constraints,
                        handle=label,
                        seed=child_seed,
                    )
                else:
                    randomize(action, seed=child_seed)
                # Apply IR-expression constraints as post-solve field fixups.
                if ir_expr_inline:
                    _apply_ir_constraints(action, ir_expr_inline, ctx)
            elif ir_expr_inline:
                _apply_ir_constraints(action, ir_expr_inline, ctx)
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
            structural_solver=ctx.structural_solver,
            forward_propagator=ctx.forward_propagator,
            tracer=ctx.tracer,
            check_contracts=ctx.check_contracts,
            coverage_model=ctx.coverage_model,
        )

        # 5b. Check @constraint.requires before body (debug mode)
        if ctx.check_contracts:
            self._check_role_constraints(action, action_type, child_ctx, 'requires')

        # 6. Execute body
        if ctx.tracer is not None:
            ctx.tracer.action_exec_begin(action)
        from .resource_rt import acquire_resources, release_resources
        solved_resource_hints = getattr(action, '_zdc_resource_hints', None)
        claims = await acquire_resources(action, child_ctx, extra_hints=solved_resource_hints)
        try:
            await self._exec_action_body(action_type, action, child_ctx)
            for buf_inst in output_flow_insts:
                if isinstance(buf_inst, tuple) and buf_inst[0] == 'state_pool':
                    # State write-back: commit output state to pool after body completes
                    _, _fname, _pool, _is_output = buf_inst
                    if _is_output:
                        _state_obj = getattr(action, _fname, None)
                        if _state_obj is not None:
                            _pool.write_release(_state_obj)
                else:
                    buf_inst.set_ready()
        finally:
            release_resources(claims)
        if ctx.tracer is not None:
            ctx.tracer.action_exec_end(action)

        # 6b. Check @constraint.ensures after body (debug mode)
        if ctx.check_contracts:
            self._check_role_constraints(action, action_type, child_ctx, 'ensures')

        # Record this action's concrete field values for forward propagation
        # in subsequent sequential actions (P3).
        if ctx.forward_propagator is not None:
            ctx.forward_propagator.record_completed(action, label=label)

        # 7. Sample covergroups after body/activity — all field values are now final.
        if ctx.coverage_model is not None:
            _sample_covergroups(action_type, action, ctx.coverage_model)

        return action

    def _check_role_constraints(
        self,
        action: Any,
        action_type: type,
        ctx: ActionContext,
        role: str,
    ) -> None:
        """Evaluate all constraints with *role* against *action*.

        Raises ContractViolation on the first failing expression.
        """
        from ..constraint_parser import ConstraintParser
        from ..decorators import ContractViolation
        from .expr_eval import ExprEval

        evaluator = ExprEval(ctx)
        for name, method in action_type.__dict__.items():
            if (hasattr(method, '_is_constraint') and method._is_constraint
                    and getattr(method, '_constraint_role', None) == role):
                parser = ConstraintParser()
                info = parser.parse_constraint(method)
                for expr in info['exprs']:
                    result = evaluator.eval(expr)
                    if not result:
                        raise ContractViolation(
                            role=role,
                            method_name=f"{action_type.__name__}.{name}",
                            expr_repr=str(expr),
                        )

    async def _exec_action_body(
        self,
        action_type: type,
        action: Any,
        ctx: ActionContext,
    ) -> None:
        """Execute body() for atomic actions, or walk __activity__ for compound.

        If the action type has ``@extend`` subclasses, all activities are merged
        into an implied schedule block (PSS implied-schedule semantics).
        When ``ctx.check_contracts`` is ``True``, ``with zdc.requires:`` /
        ``with zdc.ensures:`` blocks inside ``body()`` are checked before/after
        body execution.
        """
        extensions = _collect_extensions(action_type)
        if len(extensions) > 1:
            # Multiple extensions: implied schedule — run all activities as stages
            from zuspec.ir.core.activity import ActivitySchedule
            activities = [
                e.__dict__["__activity__"]
                for e in extensions
                if "__activity__" in e.__dict__ and e.__dict__["__activity__"] is not None
            ]
            if activities:
                from zuspec.ir.core.base import Base
                implied = ActivitySchedule(stmts=activities)
                await self._schedule(implied, ctx)
            else:
                await self._call_body_with_contracts(action_type, action, ctx)
            return

        activity_ir = getattr(action_type, "__activity__", None)
        if activity_ir is not None:
            await ActivityRunner().run(activity_ir, ctx)
        else:
            await self._call_body_with_contracts(action_type, action, ctx)

    async def _call_body_with_contracts(
        self,
        action_type: type,
        action: Any,
        ctx: ActionContext,
    ) -> None:
        """Call ``action.body()``, checking ``with zdc.requires/ensures:`` contracts.

        When ``ctx.check_contracts`` is ``False``, this is equivalent to
        ``await action.body()``.
        """
        if ctx.check_contracts:
            from .contract_checker import check_body_contracts
            check_body_contracts(action_type, action, ctx, 'requires')
        await action.body()
        if ctx.check_contracts:
            from .contract_checker import check_body_contracts
            check_body_contracts(action_type, action, ctx, 'ensures')

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
            label=node.handle,
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

        # Abstract action guard (1-L): abstract actions cannot be traversed directly.
        # The PSS LRM requires that only concrete sub-types are instantiated.
        ir_struct = getattr(action_type, '_zdc_struct', None)
        if ir_struct is not None and getattr(ir_struct, 'is_abstract', False):
            raise RuntimeError(
                f"Cannot traverse abstract action '{action_type.__name__}' directly. "
                f"Use a concrete sub-action that extends it."
            )

        # Structural inference: if the consumer has unbound flow-input slots,
        # use the structural solver to select and traverse producer actions first.
        # Exclude fields already covered by explicit init_bindings (e.g. Decode(fetch=fetch.out))
        # so that the structural solver does not infer duplicate predecessor actions.
        effective_ctx = ctx
        if ctx.structural_solver is not None:
            explicitly_bound = {field_name for field_name, _, _ in (node.init_bindings or [])}
            unbound = _collect_unbound_flow_inputs(action_type, ctx.flow_bindings, explicitly_bound)
            if unbound:
                effective_ctx = await self._apply_inferred_actions(
                    ctx.structural_solver.solve(
                        action_type, unbound, ctx,
                        inline_constraints=node.inline_constraints,
                    ),
                    ctx,
                )

        # Resolve explicit init_bindings: inject flow bindings from labeled predecessors.
        if node.init_bindings and effective_ctx.forward_propagator is not None:
            from .flow_obj_rt import BufferInstance
            extra_bindings: dict = {}
            for (field_name, src_label, src_attr) in node.init_bindings:
                src_action = effective_ctx.forward_propagator.get_action(src_label)
                if src_action is not None:
                    val = getattr(src_action, src_attr, None)
                    if val is not None:
                        buf = BufferInstance(obj=val)
                        buf.set_ready()
                        extra_bindings[field_name] = (buf, "input")
            if extra_bindings:
                effective_ctx = dc.replace(
                    effective_ctx,
                    flow_bindings={**effective_ctx.flow_bindings, **extra_bindings},
                )

        # Evaluate comp_expr to get an explicit component instance override.
        # PSS comp paths (e.g. pss_top.spi_initiators[0]) are walked directly
        # from ctx.comp using _eval_comp_path, which handles the absolute-path
        # anchor (component type name as first element) without naming convention.
        comp_override = None
        comp_expr = getattr(node, 'comp_expr', None)
        if comp_expr is not None:
            try:
                comp_override = _eval_comp_path(comp_expr, ctx.comp)
            except Exception:
                comp_override = None

        action = await self._traverse(
            action_type,
            node.inline_constraints,
            effective_ctx,
            label=node.label,
            head_resource_hints=ctx.head_resource_hints or {},
            comp_override=comp_override,
        )
        if node.label and ctx.action is not None and hasattr(ctx.action, node.label):
            setattr(ctx.action, node.label, action)

    async def _apply_inferred_actions(
        self,
        inferred: list,
        ctx: ActionContext,
    ) -> ActionContext:
        """Traverse all inferred actions and return a new context with their
        outputs added to flow_bindings so the consumer can pick them up.

        Sequential (Buffer/State) inferred actions are traversed first.
        Concurrent (Stream) inferred actions are not yet supported and raise
        NotImplementedError.
        """
        from .flow_obj_rt import BufferInstance
        from .structural_solver import InferredAction

        augmented_bindings: dict = dict(ctx.flow_bindings)

        for ia in inferred:
            if ia.ordering == "concurrent":
                raise NotImplementedError(
                    "Structural inference of concurrent Stream actions is not yet "
                    "supported; use an explicit activity with parallel scheduling."
                )

            # Create the buffer object for this inferred producer->consumer pair
            from .resource_rt import make_resource
            buf_obj = make_resource(ia.flow_obj_type)

            # State-chain: if src_state/dst_state are known from BFS, create
            # concrete state objects for the flow-input and flow-output fields
            # so the transition action's cross-flow constraints reduce to
            # single-variable problems.
            if ia.src_state is not None and ia.dst_state is not None:
                from .state_graph_factory import _fields_from_state_type
                field_descs = _fields_from_state_type(ia.flow_obj_type)

                prev_obj = make_resource(ia.flow_obj_type)
                next_obj = make_resource(ia.flow_obj_type)
                for fd, sv in zip(field_descs, ia.src_state):
                    object.__setattr__(prev_obj, fd.name, sv)
                for fd, dv in zip(field_descs, ia.dst_state):
                    object.__setattr__(next_obj, fd.name, dv)

                prev_inst = BufferInstance(obj=prev_obj)
                next_inst = BufferInstance(obj=next_obj)

                # Find flow-input and flow-output field names on the action
                from .structural_solver import _find_flow_field
                in_field = _find_flow_field(ia.action_type, ia.flow_obj_type, "input")
                out_field = _find_flow_field(ia.action_type, ia.flow_obj_type, "output")

                prod_bindings = dict(augmented_bindings)
                prod_bindings[in_field] = (prev_inst, "output")
                prod_bindings[out_field] = (next_inst, "output")
                # Mark both as ready immediately since values are pre-set
                prev_inst.set_ready()
                next_inst.set_ready()

                inferred_ctx = ActionContext(
                    action=ctx.action,
                    comp=ctx.comp,
                    pool_resolver=ctx.pool_resolver,
                    parent=ctx,
                    seed=ctx.seed ^ id(ia.action_type),
                    inline_constraints=[],
                    flow_bindings=prod_bindings,
                    structural_solver=ctx.structural_solver,
                    forward_propagator=ctx.forward_propagator,
                    tracer=ctx.tracer,
                )
                await self._traverse(ia.action_type, [], inferred_ctx)

                # Wire the destination state as input for the consumer
                augmented_bindings[ia.input_field] = (next_inst, "input")
            else:
                try:
                    from ..solver.api import randomize as _rand
                    _rand(buf_obj)
                except Exception:
                    pass
                buf_inst = BufferInstance(obj=buf_obj)

                # Build a context for the inferred producer
                prod_bindings = dict(augmented_bindings)
                prod_bindings[ia.output_field] = (buf_inst, "output")
                inferred_ctx = ActionContext(
                    action=ctx.action,
                    comp=ctx.comp,
                    pool_resolver=ctx.pool_resolver,
                    parent=ctx,
                    seed=ctx.seed ^ id(ia.action_type),
                    inline_constraints=[],
                    flow_bindings=prod_bindings,
                    structural_solver=ctx.structural_solver,
                    forward_propagator=ctx.forward_propagator,
                    tracer=ctx.tracer,
                )
                await self._traverse(ia.action_type, [], inferred_ctx)

                # Wire the produced buffer as input for the consumer
                augmented_bindings[ia.input_field] = (buf_inst, "input")

        return ActionContext(
            action=ctx.action,
            comp=ctx.comp,
            pool_resolver=ctx.pool_resolver,
            parent=ctx,
            seed=ctx.seed,
            inline_constraints=ctx.inline_constraints,
            flow_bindings=augmented_bindings,
            structural_solver=ctx.structural_solver,
            forward_propagator=ctx.forward_propagator,
            tracer=ctx.tracer,
        )

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
                structural_solver=ctx.structural_solver,
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
                    structural_solver=ctx.structural_solver,
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
        if not eligible and not getattr(node, 'allow_none', False):
            raise RuntimeError("select: no eligible branch (all guards false)")
        weights = [
            int(ev.eval(b.weight)) if b.weight is not None else 1
            for b in eligible
        ]
        # allow_none: add a null sentinel branch with weight 1 (3-N)
        if getattr(node, 'allow_none', False):
            eligible = list(eligible) + [None]
            weights = list(weights) + [1]
        if not eligible:
            return
        chosen = random.choices(eligible, weights=weights, k=1)[0]
        if chosen is None:
            return  # null branch: no action taken
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
        from zuspec.ir.core.expr import ExprRange, ExprRangeList
        ev = ExprEval(ctx)
        subject = ev.eval(node.subject)

        default_case = None
        for case in node.cases:
            if case.pattern is None:
                # Default case - execute if no other case matches
                default_case = case
                continue
            if _match_pattern(subject, case.pattern, ev):
                for stmt in case.body:
                    await self._exec(stmt, ctx)
                return

        if default_case is not None:
            for stmt in default_case.body:
                await self._exec(stmt, ctx)
    async def _fill(self, node: ActivityFill, ctx: ActionContext) -> None:
        """Coverage fill loop (PSS 12.9) -- runs body until coverage goal met
        or max_iters exhausted (3-K).

        Coverage tracking is not yet wired (Phase 3); this acts as a bounded
        repeat with early-exit when a ``__coverage_model__`` is attached to ctx.
        """
        for _ in range(node.max_iters):
            for stmt in node.body:
                await self._exec(stmt, ctx)
            # Check coverage model if available
            cov_model = ctx.coverage_model
            if cov_model is not None and cov_model.all_covered():
                break

    async def _chain(self, node: ActivityChain, ctx: ActionContext) -> None:
        """Chain statement -- automatic flow-object forwarding between sequential
        actions (PSS 12.2.2).  Executes stmts in order; output flow objects of
        each action are passed as inputs to the next (3-M).

        Full flow-object forwarding requires runtime action introspection; for
        now, stmts execute sequentially in a sequence block, matching Phase 3
        partial support.
        """
        for stmt in node.stmts:
            await self._exec(stmt, ctx)

    async def _bind(self, node, ctx) -> None:
        """ActivityBind is structural in sequence blocks -- handled by _seq pre-pass.

        In schedule blocks, explicit binds are handled by the ScheduleGraph.
        This method is a no-op because the work was done before traversal starts.
        """
        pass


def _sample_covergroups(action_type: type, action: Any, coverage_model) -> None:
    """Sample all PssCoverGroups attached to *action_type* into *coverage_model*.

    Called from ``_traverse`` after body/activity execution so that all field
    values (including those written by body()) are committed before sampling.
    Each coverpoint's ``target_expr`` is evaluated via ``eval_cover_expr``;
    crosses are sampled from the last-recorded coverpoint values.
    """
    from .coverage_model import eval_cover_expr
    pss_cgs = getattr(action_type, '__pss_covergroups__', None)
    if not pss_cgs:
        return
    for cg in pss_cgs:
        for cp in cg.coverpoints:
            value = eval_cover_expr(cp.target_expr, action)
            if value is not None:
                coverage_model.sample(cg.instance_name, cp.name, value)
        for cx in cg.crosses:
            vals = tuple(
                coverage_model.last_value(cg.instance_name, cp_name)
                for cp_name in cx.coverpoint_names
            )
            if all(v is not None for v in vals):
                coverage_model.sample_cross(cg.instance_name, cx.name, vals)


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _apply_ir_constraints(action: Any, constraints: list, ctx) -> None:
    """Apply IR-expression inline constraints as post-solve fixups.

    For simple equality constraints like ``tx_byte == i``, directly sets the
    field on *action* to the evaluated RHS.  Non-equality constraints are
    evaluated and ignored if they fail (logged only).
    """
    from zuspec.ir.core.expr import ExprBin, ExprAttribute, TypeExprRefSelf, ExprRefUnresolved
    from .expr_eval import ExprEval
    ev = ExprEval(ctx)
    for expr in constraints:
        if not isinstance(expr, ExprBin):
            continue
        op = expr.op
        if op not in ('==', 'eq'):
            continue
        # Try to resolve the LHS as a field name on the action
        lhs = expr.lhs
        field_name = None
        if isinstance(lhs, ExprAttribute) and isinstance(lhs.value, TypeExprRefSelf):
            field_name = lhs.attr
        elif isinstance(lhs, ExprRefUnresolved):
            field_name = lhs.name
        if field_name is None or not hasattr(action, field_name):
            continue
        try:
            rhs_val = ev.eval(expr.rhs)
            if rhs_val is not None:
                setattr(action, field_name, rhs_val)
        except Exception:
            pass  # Non-critical; solver already ran


def _match_pattern(subject, pattern, ev):
    """Return True if `subject` matches a PSS match pattern.

    Handles:
    - ExprRangeList: checks if subject falls in any range or equals any single value.
    - ExprRange: checks if subject equals a single value or is within [lower, upper].
    - Fallback: evaluates the pattern and compares with ==.
    """
    from zuspec.ir.core.expr import ExprRange, ExprRangeList
    if isinstance(pattern, ExprRangeList):
        return any(_match_pattern(subject, r, ev) for r in pattern.ranges)
    if isinstance(pattern, ExprRange):
        lower = ev.eval(pattern.lower)
        if pattern.upper is None:
            return subject == lower
        upper = ev.eval(pattern.upper)
        return lower <= subject <= upper
    # Fallback: evaluate and compare
    val = ev.eval(pattern)
    if isinstance(val, (list, tuple, set)):
        return subject in val
    return subject == val


def _collect_unbound_flow_inputs(
    action_type: type,
    flow_bindings: dict,
    explicitly_bound: set = None,
) -> list:
    """Return ``(field_name, flow_obj_type)`` tuples for flow-input fields on
    *action_type* that are not already present in *flow_bindings*.

    *explicitly_bound* is an optional set of field names covered by explicit
    init_bindings (e.g. ``Decode(fetch=fetch.out)``); those fields are excluded
    so the structural solver does not infer duplicate predecessor actions.

    These represent slots that the structural solver needs to fill.
    """
    try:
        fields = dc.fields(action_type)
    except TypeError:
        return []

    ann: dict = {}
    for klass in action_type.__mro__:
        ann.update(klass.__dict__.get("__annotations__", {}))

    result = []
    for f in fields:
        meta = f.metadata or {}
        if meta.get("kind") != "flow_ref":
            continue
        if meta.get("direction") != "input":
            continue
        if f.name in flow_bindings:
            continue
        if explicitly_bound and f.name in explicitly_bound:
            continue
        flow_obj_type = ann.get(f.name)
        if isinstance(flow_obj_type, type):
            result.append((f.name, flow_obj_type))
    return result


def _create_orphan_output_buffers(
    action_type: type,
    action: Any,
    flow_bindings: dict,
) -> None:
    """For each flow-output field on *action* that is still ``None`` (not yet
    bound via *flow_bindings*), create a minimal buffer instance so that
    ``body()`` can write to the field without crashing.

    This covers actions traversed in isolation (no explicit consumer registered
    for their output) — orphaned outputs are valid in PSS when the producer is
    inferred or the user doesn't need the value.
    """
    try:
        fields = dc.fields(action_type)
    except TypeError:
        return

    ann: dict = {}
    for klass in action_type.__mro__:
        ann.update(klass.__dict__.get("__annotations__", {}))

    from .resource_rt import make_resource
    for f in fields:
        meta = f.metadata or {}
        if meta.get("kind") != "flow_ref":
            continue
        if meta.get("direction") != "output":
            continue
        if f.name in flow_bindings:
            continue
        # Field is unbound — create an orphan buffer
        flow_obj_type = ann.get(f.name)
        if isinstance(flow_obj_type, type):
            try:
                buf_obj = make_resource(flow_obj_type)
                object.__setattr__(action, f.name, buf_obj)
            except Exception:
                pass


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
    """Return handle names referenced via self.<handle>.<field> in a constraint.

    Supports both Python-AST constraints (from Python-native code) and IR
    expression constraints (from PSS-translated activities).  In PSS-translated
    constraints, handle references appear as ExprAttribute chains:
    ``ExprAttribute(ExprAttribute(TypeExprRefSelf(), handle), field)``.
    """
    import ast as _ast
    names = []

    # Python-AST path (legacy python-native constraints)
    if isinstance(stmt, _ast.stmt):
        for node in _ast.walk(stmt):
            if (isinstance(node, _ast.Attribute) and
                    isinstance(node.value, _ast.Attribute) and
                    isinstance(node.value.value, _ast.Name) and
                    node.value.value.id == "self"):
                names.append(node.value.attr)
        return list(dict.fromkeys(names))

    # IR-expression path (PSS-translated constraints via ExprAttribute chains)
    try:
        from zuspec.ir.core.expr import ExprAttribute, TypeExprRefSelf

        def _walk_ir(node):
            if node is None:
                return
            # pattern: ExprAttribute(ExprAttribute(TypeExprRefSelf, handle), field)
            if (isinstance(node, ExprAttribute) and
                    isinstance(node.value, ExprAttribute) and
                    isinstance(node.value.value, TypeExprRefSelf)):
                names.append(node.value.attr)
            # Recurse into child attributes
            for attr in ('value', 'lhs', 'rhs', 'func', 'cond',
                         'test', 'body', 'orelse', 'operand', 'val'):
                child = getattr(node, attr, None)
                if child is not None and not isinstance(child, (str, int, float, bool)):
                    _walk_ir(child)
            for attr in ('args', 'elts', 'ranges'):
                lst = getattr(node, attr, None)
                if isinstance(lst, list):
                    for item in lst:
                        _walk_ir(item)

        _walk_ir(stmt)
    except ImportError:
        pass

    return list(dict.fromkeys(names))


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
                # Randomize the flow object's own rand fields before binding
                try:
                    from ..solver.api import randomize, RandomizationError
                    randomize(obj)
                except Exception:
                    pass  # No rand fields or unsolvable — use defaults
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
