"""Tests for rt/action_context.py — ActionContext dataclass."""
from __future__ import annotations

import dataclasses as dc
import pytest

import zuspec.dataclasses as zdc
from zuspec.dataclasses.rt.action_context import ActionContext
from zuspec.dataclasses.rt.pool_resolver import PoolResolver


@zdc.dataclass
class _Cpu(zdc.Component):
    pass


def _make_resolver():
    return PoolResolver.build(_Cpu())


def test_construct_minimal():
    """Required fields action, comp, pool_resolver are accepted."""
    cpu = _Cpu()
    ctx = ActionContext(action=None, comp=cpu, pool_resolver=_make_resolver())
    assert ctx.comp is cpu
    assert ctx.action is None


def test_defaults():
    cpu = _Cpu()
    ctx = ActionContext(action=None, comp=cpu, pool_resolver=_make_resolver())
    assert ctx.parent is None
    assert ctx.seed == 0
    assert ctx.inline_constraints == []
    assert ctx.flow_bindings == {}
    assert ctx.head_resource_hints == {}
    assert ctx.tracer is None


def test_parent_chain():
    cpu = _Cpu()
    pr = _make_resolver()
    root = ActionContext(action=None, comp=cpu, pool_resolver=pr)
    child = ActionContext(action=None, comp=cpu, pool_resolver=pr, parent=root)
    assert child.parent is root
    assert root.parent is None


def test_seed_type():
    cpu = _Cpu()
    ctx = ActionContext(action=None, comp=cpu, pool_resolver=_make_resolver(), seed=42)
    assert isinstance(ctx.seed, int)
    assert ctx.seed == 42


def test_flow_bindings_mutable_per_instance():
    cpu = _Cpu()
    pr = _make_resolver()
    a = ActionContext(action=None, comp=cpu, pool_resolver=pr)
    b = ActionContext(action=None, comp=cpu, pool_resolver=pr)
    a.flow_bindings["x"] = 1
    assert "x" not in b.flow_bindings


def test_inline_constraints_mutable_per_instance():
    cpu = _Cpu()
    pr = _make_resolver()
    a = ActionContext(action=None, comp=cpu, pool_resolver=pr)
    b = ActionContext(action=None, comp=cpu, pool_resolver=pr)
    a.inline_constraints.append(42)
    assert 42 not in b.inline_constraints
