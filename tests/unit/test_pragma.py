"""Tests for the ``# zdc:`` pragma comment system.

Covers:
- ``parse_pragma_str`` — tokeniser for pragma body text
- ``scan_pragmas`` — source-level comment scanner
- ActivityParser — pragmas attached to activity IR nodes (match, if, traversal)
- DataModelFactory / Field IR — pragmas attached to field declarations
"""
from __future__ import annotations

import ast
import textwrap
import unittest.mock as mock

import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.pragma import parse_pragma_str, scan_pragmas
from zuspec.dataclasses.activity_parser import ActivityParser
from zuspec.dataclasses.ir.activity import (
    ActivityIfElse,
    ActivityMatch,
    ActivitySequenceBlock,
    ActivityTraversal,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_src(src: str) -> ActivitySequenceBlock:
    """Parse activity source text directly, bypassing inspect."""
    src = textwrap.dedent(src)
    with mock.patch("inspect.getsource", return_value=src):
        return ActivityParser().parse(mock.MagicMock())


# ===========================================================================
# parse_pragma_str
# ===========================================================================

class TestParsePragmaStr:
    def test_single_flag(self):
        assert parse_pragma_str("parallel_case") == {"parallel_case": True}

    def test_multiple_flags(self):
        r = parse_pragma_str("parallel_case, full_case")
        assert r == {"parallel_case": True, "full_case": True}

    def test_key_int_value(self):
        assert parse_pragma_str("weight=10") == {"weight": 10}

    def test_key_string_value(self):
        assert parse_pragma_str('label="fetch_stage"') == {"label": "fetch_stage"}

    def test_key_bare_string_value(self):
        assert parse_pragma_str("label=fetch_stage") == {"label": "fetch_stage"}

    def test_mixed(self):
        r = parse_pragma_str('parallel_case, full_case, label="decode_fsm"')
        assert r["parallel_case"] is True
        assert r["full_case"] is True
        assert r["label"] == "decode_fsm"

    def test_whitespace_tolerant(self):
        assert parse_pragma_str("  parallel_case , full_case  ") == {
            "parallel_case": True,
            "full_case": True,
        }

    def test_key_bool_literal(self):
        assert parse_pragma_str("keep=True") == {"keep": True}
        assert parse_pragma_str("keep=False") == {"keep": False}

    def test_empty(self):
        assert parse_pragma_str("") == {}
        assert parse_pragma_str("   ") == {}


# ===========================================================================
# scan_pragmas
# ===========================================================================

class TestScanPragmas:
    def test_single_line(self):
        src = "x = 1  # zdc: keep\ny = 2\n"
        r = scan_pragmas(src)
        assert r == {1: {"keep": True}}

    def test_multiple_lines(self):
        src = textwrap.dedent("""\
            a = 1  # zdc: parallel_case, full_case
            b = 2
            c = 3  # zdc: label=my_node
        """)
        r = scan_pragmas(src)
        assert r[1] == {"parallel_case": True, "full_case": True}
        assert r[3] == {"label": "my_node"}
        assert 2 not in r

    def test_case_insensitive_prefix(self):
        src = "x = 1  # ZDC: keep\n"
        r = scan_pragmas(src)
        assert r == {1: {"keep": True}}

    def test_no_pragmas(self):
        src = "x = 1  # regular comment\ny = 2\n"
        assert scan_pragmas(src) == {}

    def test_inline_on_match(self):
        src = textwrap.dedent("""\
            async def body(self):
                match self.op:  # zdc: parallel_case
                    case 0: pass
        """)
        r = scan_pragmas(src)
        assert 2 in r
        assert r[2] == {"parallel_case": True}


# ===========================================================================
# ActivityParser — pragma attachment
# ===========================================================================

class TestActivityParserPragmas:
    def test_match_pragma(self):
        ir = _parse_src("""
            async def activity(self):
                match self.op:  # zdc: parallel_case, full_case
                    case 0:
                        await self.a()
        """)
        assert len(ir.stmts) == 1
        stmt = ir.stmts[0]
        assert isinstance(stmt, ActivityMatch)
        assert stmt.pragmas.get("parallel_case") is True
        assert stmt.pragmas.get("full_case") is True

    def test_if_pragma(self):
        ir = _parse_src("""
            async def activity(self):
                if self.x > 0:  # zdc: label=branch_positive
                    await self.a()
        """)
        stmt = ir.stmts[0]
        assert isinstance(stmt, ActivityIfElse)
        assert stmt.pragmas.get("label") == "branch_positive"

    def test_traversal_pragma(self):
        ir = _parse_src("""
            async def activity(self):
                await self.fetch()  # zdc: label=fetch_stage
        """)
        stmt = ir.stmts[0]
        assert isinstance(stmt, ActivityTraversal)
        assert stmt.pragmas.get("label") == "fetch_stage"

    def test_no_pragma_is_empty_dict(self):
        ir = _parse_src("""
            async def activity(self):
                await self.a()
        """)
        assert ir.stmts[0].pragmas == {}

    def test_pragma_with_label_and_flag(self):
        ir = _parse_src("""
            async def activity(self):
                match self.cpu_state:  # zdc: parallel_case, full_case, label=cpu_fsm
                    case 0: await self.fetch()
                    case 1: await self.exec()
        """)
        stmt = ir.stmts[0]
        assert isinstance(stmt, ActivityMatch)
        assert stmt.pragmas == {
            "parallel_case": True,
            "full_case": True,
            "label": "cpu_fsm",
        }

    def test_multiple_statements_independent_pragmas(self):
        ir = _parse_src("""
            async def activity(self):
                match self.op:  # zdc: parallel_case
                    case 0: await self.a()
                if self.x:  # zdc: label=guard
                    await self.b()
        """)
        assert ir.stmts[0].pragmas == {"parallel_case": True}
        assert ir.stmts[1].pragmas == {"label": "guard"}


# ===========================================================================
# Field IR — pragma attachment via DataModelFactory
# ===========================================================================

class TestFieldPragmas:
    def test_keep_pragma_on_field(self):
        @zdc.dataclass
        class MyComp(zdc.Component):
            dbg_pc: zdc.bit32 = zdc.field()  # zdc: keep

        from zuspec.dataclasses.data_model_factory import DataModelFactory
        dmf = DataModelFactory()
        fields = dmf._extract_fields(MyComp)
        f = next(x for x in fields if x.name == "dbg_pc")
        assert f.pragmas.get("keep") is True

    def test_label_pragma_on_field(self):
        @zdc.dataclass
        class MyComp2(zdc.Component):
            counter: zdc.bit32 = zdc.field()  # zdc: keep, label=perf_counter

        from zuspec.dataclasses.data_model_factory import DataModelFactory
        dmf = DataModelFactory()
        fields = dmf._extract_fields(MyComp2)
        f = next(x for x in fields if x.name == "counter")
        assert f.pragmas.get("keep") is True
        assert f.pragmas.get("label") == "perf_counter"

    def test_no_pragma_field_empty(self):
        @zdc.dataclass
        class MyComp3(zdc.Component):
            val: zdc.bit32 = zdc.field()

        from zuspec.dataclasses.data_model_factory import DataModelFactory
        dmf = DataModelFactory()
        fields = dmf._extract_fields(MyComp3)
        f = next(x for x in fields if x.name == "val")
        assert f.pragmas == {}
