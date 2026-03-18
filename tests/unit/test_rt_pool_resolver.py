"""Tests for rt/pool_resolver.py — PoolResolver (Phase 1: component selection)."""
from __future__ import annotations

import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.rt.pool_resolver import PoolResolver, _action_comp_type


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

@zdc.dataclass
class SimpleCpu(zdc.Component):
    pass


@zdc.dataclass
class AnotherCpu(zdc.Component):
    pass


@zdc.dataclass
class SoC(zdc.Component):
    core0: SimpleCpu = zdc.inst()
    core1: SimpleCpu = zdc.inst()


@zdc.dataclass
class SimpleAction(zdc.Action[SimpleCpu]):
    async def body(self): pass


@zdc.dataclass
class AnotherAction(zdc.Action[AnotherCpu]):
    async def body(self): pass


# ---------------------------------------------------------------------------
# Phase 1 — component selection
# ---------------------------------------------------------------------------

def test_build_single_comp():
    cpu = SimpleCpu()
    pr = PoolResolver.build(cpu)
    assert isinstance(pr, PoolResolver)


def test_build_nested_comp():
    soc = SoC()
    pr = PoolResolver.build(soc)
    candidates = pr._instances_in(soc, SimpleCpu)
    assert len(candidates) == 2
    assert soc.core0 in candidates
    assert soc.core1 in candidates


def test_select_comp_returns_instance():
    cpu = SimpleCpu()
    pr = PoolResolver.build(cpu)
    result = pr.select_comp(SimpleAction, cpu)
    assert isinstance(result, SimpleCpu)
    assert result is cpu


def test_select_comp_random():
    """With 2 SimpleCpu instances, both are selected across many calls."""
    soc = SoC()
    pr = PoolResolver.build(soc)
    seen = set()
    for _ in range(50):
        comp = pr.select_comp(SimpleAction, soc)
        seen.add(id(comp))
    assert len(seen) == 2


def test_select_comp_wrong_type_raises():
    cpu = SimpleCpu()
    pr = PoolResolver.build(cpu)
    with pytest.raises(RuntimeError):
        pr.select_comp(AnotherAction, cpu)


def test_select_comp_error_message_includes_type():
    cpu = SimpleCpu()
    pr = PoolResolver.build(cpu)
    with pytest.raises(RuntimeError, match="AnotherCpu"):
        pr.select_comp(AnotherAction, cpu)


def test_action_comp_type_extracts_T():
    result = _action_comp_type(SimpleAction)
    assert result is SimpleCpu


def test_action_comp_type_indirect_subclass():
    @zdc.dataclass
    class MyAction(SimpleAction):
        async def body(self): pass

    result = _action_comp_type(MyAction)
    assert result is SimpleCpu


def test_action_comp_type_no_annotation_returns_none():
    # Bare Action subclass without type parameter
    class BareAction(zdc.Action):
        pass

    result = _action_comp_type(BareAction)
    assert result is None
