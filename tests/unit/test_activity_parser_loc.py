"""Tests for source location population in ActivityParser (T1.1).

Verifies that every IR node produced by ActivityParser carries a `loc`
with the correct source file and line number.
"""
from __future__ import annotations

import inspect
import textwrap
from unittest import mock

import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.activity_parser import ActivityParser, _parse_cache
from zuspec.dataclasses.ir.activity import (
    ActivityAnonTraversal,
    ActivityParallel,
    ActivityRepeat,
    ActivitySequenceBlock,
    ActivityTraversal,
)


# ---------------------------------------------------------------------------
# Helper — parse a real method (not a mock) so loc is populated from this file
# ---------------------------------------------------------------------------

@zdc.dataclass
class _LocCpu(zdc.Component):
    pass


@zdc.dataclass
class _SubA(zdc.Action[_LocCpu]):
    async def body(self): pass


@zdc.dataclass
class _SubB(zdc.Action[_LocCpu]):
    async def body(self): pass


@zdc.dataclass
class _CompoundA(zdc.Action[_LocCpu]):
    async def activity(self):
        do(_SubA)
        do(_SubB)


@zdc.dataclass
class _CompoundParallel(zdc.Action[_LocCpu]):
    async def activity(self):
        with zdc.parallel():
            do(_SubA)
            do(_SubB)


@zdc.dataclass
class _CompoundRepeat(zdc.Action[_LocCpu]):
    async def activity(self):
        for _i in range(3):
            do(_SubA)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_loc_populated_on_anon_traversal():
    ir = ActivityParser().parse(_CompoundA.activity)
    stmt = ir.stmts[0]
    assert isinstance(stmt, ActivityAnonTraversal)
    assert stmt.loc is not None
    assert stmt.loc.line > 0


def test_loc_populated_on_parallel():
    ir = ActivityParser().parse(_CompoundParallel.activity)
    stmt = ir.stmts[0]
    assert isinstance(stmt, ActivityParallel)
    assert stmt.loc is not None
    assert stmt.loc.line > 0


def test_loc_populated_on_repeat():
    ir = ActivityParser().parse(_CompoundRepeat.activity)
    stmt = ir.stmts[0]
    assert isinstance(stmt, ActivityRepeat)
    assert stmt.loc is not None
    assert stmt.loc.line > 0


def test_loc_file_matches_source_file():
    ir = ActivityParser().parse(_CompoundA.activity)
    stmt = ir.stmts[0]
    assert stmt.loc is not None
    expected_file = inspect.getsourcefile(_CompoundA.activity)
    assert stmt.loc.file == expected_file


def test_loc_line_increases_downward():
    ir = ActivityParser().parse(_CompoundA.activity)
    stmts = ir.stmts
    assert len(stmts) >= 2
    assert stmts[0].loc.line < stmts[1].loc.line


def test_action_type_cls_resolved():
    """ActivityAnonTraversal.action_type_cls should be the resolved class."""
    ir = ActivityParser().parse(_CompoundA.activity)
    stmt = ir.stmts[0]
    assert isinstance(stmt, ActivityAnonTraversal)
    # action_type_cls is resolved from method.__globals__
    assert stmt.action_type_cls is _SubA


def test_cache_key_includes_file():
    """Two identical method bodies in different files should cache separately."""
    src = textwrap.dedent("""
        async def activity(self):
            await self.a1()
    """)
    key_a = (hash(src), "/file_a.py", 10)
    key_b = (hash(src), "/file_b.py", 20)
    _parse_cache.pop(key_a, None)
    _parse_cache.pop(key_b, None)

    parser = ActivityParser()
    with mock.patch("inspect.getsource", return_value=src), \
         mock.patch("inspect.getsourcefile", return_value="/file_a.py"), \
         mock.patch("inspect.getsourcelines", return_value=(None, 10)):
        ir_a = parser.parse(mock.MagicMock())

    with mock.patch("inspect.getsource", return_value=src), \
         mock.patch("inspect.getsourcefile", return_value="/file_b.py"), \
         mock.patch("inspect.getsourcelines", return_value=(None, 20)):
        ir_b = parser.parse(mock.MagicMock())

    assert ir_a is not ir_b


def test_loc_on_nested_block():
    """Statements inside a parallel branch carry correct loc."""
    ir = ActivityParser().parse(_CompoundParallel.activity)
    parallel = ir.stmts[0]
    assert isinstance(parallel, ActivityParallel)
    inner = parallel.stmts[0]
    assert isinstance(inner, ActivityAnonTraversal)
    assert inner.loc is not None
    assert inner.loc.line > 0


def test_top_level_sequence_block_has_loc():
    ir = ActivityParser().parse(_CompoundA.activity)
    assert isinstance(ir, ActivitySequenceBlock)
    assert ir.loc is not None
