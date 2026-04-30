"""High-level entry point for running PSS scenarios on a component tree.

Example::

    >>> # ScenarioRunner is the preferred entry point for running actions.
"""
from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING, Any, Optional, Type

from .action_context import ActionContext
from .coverage_model import PssCoverageModel
from .activity_runner import ActivityRunner
from .pool_resolver import PoolResolver
from .action_registry import ActionRegistry
from .icl_table import ICLTable
from .structural_solver import StructuralSolver
import functools as _functools

# Cache ActionRegistry+ICLTable by root component *type* — these are
# purely class-based and do not change between iterations with the same
# component topology.  Keyed by the runtime class so different top-level
# component types remain independent.
@_functools.lru_cache(maxsize=None)
def _cached_registry_and_icl(root_cls: type):
    """Build and cache ActionRegistry + ICLTable for a given root class."""
    # We need a real instance to walk subcomponent types.
    # Build a sentinel instance just for class-discovery purposes.
    # Because this runs during ScenarioRunner.__init__ we always have an
    # instance available; the lambda below captures it from the call site.
    return None  # populated at call site; placeholder to satisfy lru_cache signature


_registry_cache: dict = {}  # type(root) -> (registry, icl_table)

if TYPE_CHECKING:
    from ..types import Component


class DeadlockError(RuntimeError):
    """Raised when a scenario does not complete within the watchdog timeout."""


class ScenarioRunner:
    """Stateful entry point for running PSS scenarios on a component tree.

    Usage::

        top = Top()
        runner = ScenarioRunner(top, seed=42)
        await runner.run(EntryAction)
    """

    def __init__(
        self,
        comp: "Component",
        seed: Optional[int] = None,
        tracer=None,
        check_contracts: bool = False,
        coverage_model: Optional[PssCoverageModel] = None,
    ) -> None:
        self._comp = comp
        self._resolver = PoolResolver.build(comp)
        self._seed = seed if seed is not None else random.randrange(2**32)
        self._tracer = tracer
        self._check_contracts = check_contracts
        self._coverage_model = coverage_model
        # ActionRegistry and ICLTable depend only on component/action CLASS
        # topology, not on the specific instance, so they are cached per root type.
        root_cls = type(comp)
        cached = _registry_cache.get(root_cls)
        if cached is None:
            registry = ActionRegistry.build(comp)
            icl_table = ICLTable.build(registry)
            cached = (registry, icl_table)
            _registry_cache[root_cls] = cached
        self._registry, self._icl_table = cached
        self._structural_solver = StructuralSolver(self._icl_table, seed=self._seed, registry=self._registry)

    async def run(
        self, action_type: Type, timeout_s: float = 30.0, **kwargs
    ) -> Any:
        """Traverse *action_type* once against the component tree."""
        ctx = ActionContext(
            action=None,
            comp=self._comp,
            pool_resolver=self._resolver,
            seed=self._seed,
            structural_solver=self._structural_solver,
            tracer=self._tracer,
            check_contracts=self._check_contracts,
            coverage_model=self._coverage_model,
        )
        runner = ActivityRunner()
        try:
            async with asyncio.timeout(timeout_s):
                action = await runner._traverse(action_type, [], ctx)
        except asyncio.TimeoutError:
            raise DeadlockError(
                f"Scenario did not complete within {timeout_s}s — "
                f"possible deadlock in resource acquisition"
            )
        self._seed = (
            self._seed * 6364136223846793005 + 1442695040888963407
        ) & 0xFFFF_FFFF_FFFF_FFFF
        return action

    async def run_n(self, action_type: Type, n: int) -> None:
        """Traverse *action_type* *n* times sequentially."""
        for _ in range(n):
            await self.run(action_type)


async def run_action(
    comp: "Component",
    action_type: Type,
    seed: Optional[int] = None,
    coverage_model: Optional[PssCoverageModel] = None,
) -> Any:
    """Single-shot convenience: traverse *action_type* on *comp*.

    Equivalent to ``await ScenarioRunner(comp, seed).run(action_type)``.
    """
    runner = ScenarioRunner(comp, seed=seed, coverage_model=coverage_model)
    return await runner.run(action_type)


def run_action_sync(
    comp: "Component",
    action_type: Type,
    seed: Optional[int] = None,
    coverage_model: Optional[PssCoverageModel] = None,
) -> Any:
    """Synchronous wrapper around :func:`run_action` for non-async callers."""
    return asyncio.run(run_action(comp, action_type, seed=seed, coverage_model=coverage_model))
