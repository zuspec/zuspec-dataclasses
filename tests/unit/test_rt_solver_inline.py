"""Runtime tests: inline constraints on handle and anon traversals are satisfied.

These tests prove that:
  - `async with self.handle(): constraint` actually constrains the rand field
  - `with do(T) as lbl: constraint` actually constrains the rand field
  - same seed + same constraint → same solution (determinism)
  - constraint is satisfied across a range of seeds
"""
from __future__ import annotations

import asyncio
import dataclasses as dc

import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.rt.scenario_runner import ScenarioRunner


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Domain model (module-level so the activity parser can resolve types)
# ---------------------------------------------------------------------------

@zdc.dataclass
class Cpu(zdc.Component):
    pass


@zdc.dataclass
class Leaf(zdc.Action[Cpu]):
    """Atomic action with two independent rand fields."""
    addr: zdc.u32 = zdc.rand()
    size: zdc.u8 = zdc.rand()
    async def body(self): pass


# --- Handle inline constraints ---

@zdc.dataclass
class SingleConstraintOuter(zdc.Action[Cpu]):
    """async with self.sub(): self.sub.addr > 0x1000"""
    sub: Leaf = None

    async def activity(self):
        async with self.sub():
            self.sub.addr > 0x1000


@zdc.dataclass
class RangeConstraintOuter(zdc.Action[Cpu]):
    """async with self.sub(): 0x100 < addr < 0x200"""
    sub: Leaf = None

    async def activity(self):
        async with self.sub():
            self.sub.addr > 0x100
            self.sub.addr < 0x200


# --- Anonymous traversal inline constraints ---

@zdc.dataclass
class AnonConstraintOuter(zdc.Action[Cpu]):
    """with do(Leaf) as s: s.size < 50  →  label writeback to self.s"""
    s: Leaf = None

    async def activity(self):
        with do(Leaf) as s:
            s.size < 50


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _run_n(action_type, comp_factory=Cpu, n=20):
    return [_run(ScenarioRunner(comp_factory(), seed=i).run(action_type)) for i in range(n)]


# ---------------------------------------------------------------------------
# T1 — Single handle inline constraint satisfied
# ---------------------------------------------------------------------------

def test_handle_inline_gt_satisfied():
    """addr > 0x1000 is satisfied after traversal."""
    cpu = Cpu()
    result = _run(ScenarioRunner(cpu, seed=42).run(SingleConstraintOuter))
    assert result.sub is not None
    assert result.sub.addr > 0x1000


def test_handle_inline_gt_satisfied_many_seeds():
    """addr > 0x1000 is satisfied for every seed in 0..19."""
    for r in _run_n(SingleConstraintOuter):
        assert r.sub.addr > 0x1000, f"constraint violated: addr={r.sub.addr:#x}"


# ---------------------------------------------------------------------------
# T2 — Range constraint (two expressions in one block)
# ---------------------------------------------------------------------------

def test_handle_inline_range_satisfied():
    """0x100 < addr < 0x200 is satisfied after traversal."""
    cpu = Cpu()
    result = _run(ScenarioRunner(cpu, seed=42).run(RangeConstraintOuter))
    assert result.sub is not None
    assert 0x100 < result.sub.addr < 0x200


def test_handle_inline_range_satisfied_many_seeds():
    """0x100 < addr < 0x200 is satisfied for every seed in 0..19."""
    for r in _run_n(RangeConstraintOuter):
        addr = r.sub.addr
        assert 0x100 < addr < 0x200, f"constraint violated: addr={addr:#x}"


# ---------------------------------------------------------------------------
# T3 — Seed determinism with inline constraints
# ---------------------------------------------------------------------------

def test_handle_inline_seed_reproducible():
    """Same seed → same constrained solution."""
    cpu1, cpu2 = Cpu(), Cpu()
    r1 = _run(ScenarioRunner(cpu1, seed=999).run(RangeConstraintOuter))
    r2 = _run(ScenarioRunner(cpu2, seed=999).run(RangeConstraintOuter))
    assert r1.sub.addr == r2.sub.addr
    assert r1.sub.size == r2.sub.size


def test_handle_inline_different_seeds_vary():
    """Different seeds should produce different constrained values (not all same)."""
    addrs = {_run(ScenarioRunner(Cpu(), seed=i).run(RangeConstraintOuter)).sub.addr
             for i in range(20)}
    assert len(addrs) > 1, "All seeds produced the same value — suspicious"


# ---------------------------------------------------------------------------
# T4 — Anonymous traversal inline constraint
# ---------------------------------------------------------------------------

def test_anon_inline_constraint_satisfied():
    """Anon traversal: s.size < 50 is satisfied after traversal (label writeback)."""
    cpu = Cpu()
    result = _run(ScenarioRunner(cpu, seed=42).run(AnonConstraintOuter))
    assert result.s is not None
    assert result.s.size < 50


def test_anon_inline_constraint_satisfied_many_seeds():
    """Anon traversal: s.size < 50 holds for every seed in 0..19."""
    for r in _run_n(AnonConstraintOuter):
        assert r.s.size < 50, f"constraint violated: size={r.s.size}"
