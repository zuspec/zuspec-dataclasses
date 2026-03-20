"""Tests for ActivityParser — Phase 1 (sequential traversal)."""
import ast
import textwrap
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.activity_parser import ActivityParser, ActivityParseError
from zuspec.dataclasses.ir.activity import (
    ActivityAnonTraversal,
    ActivityBind,
    ActivitySequenceBlock,
    ActivitySuper,
    ActivityTraversal,
)


# ---------------------------------------------------------------------------
# Helper: parse activity source directly
# ---------------------------------------------------------------------------

def _parse_src(src: str) -> ActivitySequenceBlock:
    """Parse activity method source text directly (avoids closure issues)."""
    src = textwrap.dedent(src)
    tree = ast.parse(src)
    func = tree.body[0]

    # Build a callable mock whose getsource returns the src
    import types, inspect, unittest.mock as mock

    method = mock.MagicMock()
    method.__code__ = compile(src, "<test>", "exec").co_consts[0]  # unused

    # Patch inspect.getsource to return our src
    with mock.patch("inspect.getsource", return_value=src):
        return ActivityParser().parse(method)


# ---------------------------------------------------------------------------
# Single-handle traversal
# ---------------------------------------------------------------------------

def test_single_handle_traversal():
    """self.a1() → ActivityTraversal(handle='a1')."""
    ir = _parse_src("""
        async def activity(self):
            await self.a1()
    """)
    assert isinstance(ir, ActivitySequenceBlock)
    assert len(ir.stmts) == 1
    t = ir.stmts[0]
    assert isinstance(t, ActivityTraversal)
    assert t.handle == 'a1'
    assert t.index is None
    assert t.inline_constraints == []


def test_multiple_sequential_traversals():
    """Multiple handle traversals → ActivitySequenceBlock with N nodes."""
    ir = _parse_src("""
        async def activity(self):
            await self.a1()
            await self.a2()
            await self.a3()
    """)
    assert len(ir.stmts) == 3
    handles = [s.handle for s in ir.stmts]
    assert handles == ['a1', 'a2', 'a3']


# ---------------------------------------------------------------------------
# Handle traversal with inline constraints
# ---------------------------------------------------------------------------

def test_traversal_with_inline_constraints():
    """async with self.h(): constraint → ActivityTraversal with inline_constraints as ast.stmt."""
    ir = _parse_src("""
        async def activity(self):
            async with self.rd():
                self.rd.chan_priority > 5
    """)
    assert len(ir.stmts) == 1
    t = ir.stmts[0]
    assert isinstance(t, ActivityTraversal)
    assert t.handle == 'rd'
    assert len(t.inline_constraints) == 1
    import ast
    c = t.inline_constraints[0]
    assert isinstance(c, ast.Expr)
    assert isinstance(c.value, ast.Compare)
    assert len(c.value.ops) == 1
    assert isinstance(c.value.ops[0], ast.Gt)


def test_traversal_with_empty_with_block():
    """with self.h(): pass → ActivityTraversal, no constraints."""
    ir = _parse_src("""
        async def activity(self):
            async with self.h():
                pass
    """)
    t = ir.stmts[0]
    assert isinstance(t, ActivityTraversal)
    assert t.inline_constraints == []


# ---------------------------------------------------------------------------
# Anonymous traversal (do)
# ---------------------------------------------------------------------------

def test_anon_traversal_bare():
    """await do(WriteAction) → ActivityAnonTraversal(action_type='WriteAction')."""
    ir = _parse_src("""
        async def activity(self):
            await do(WriteAction)
    """)
    assert len(ir.stmts) == 1
    t = ir.stmts[0]
    assert isinstance(t, ActivityAnonTraversal)
    assert t.action_type == 'WriteAction'
    assert t.label is None
    assert t.inline_constraints == []


def test_anon_traversal_bare_requires_await():
    """Bare do(WriteAction) without await raises ActivityParseError."""
    with pytest.raises(ActivityParseError, match="must be awaited"):
        _parse_src("""
            async def activity(self):
                do(WriteAction)
        """)


def test_anon_traversal_with_label_assign():
    """xfer = await do(WriteAction) → ActivityAnonTraversal(label='xfer')."""
    ir = _parse_src("""
        async def activity(self):
            xfer = await do(WriteAction)
    """)
    t = ir.stmts[0]
    assert isinstance(t, ActivityAnonTraversal)
    assert t.label == 'xfer'
    assert t.action_type == 'WriteAction'


def test_anon_traversal_label_assign_requires_await():
    """xfer = do(WriteAction) without await raises ActivityParseError."""
    with pytest.raises(ActivityParseError, match="must be awaited"):
        _parse_src("""
            async def activity(self):
                xfer = do(WriteAction)
        """)


def test_anon_traversal_with_context_manager_label():
    """with do(WriteAction) as wr: → ActivityAnonTraversal(label='wr')."""
    ir = _parse_src("""
        async def activity(self):
            with do(WriteAction) as wr:
                wr.size > 10
    """)
    t = ir.stmts[0]
    assert isinstance(t, ActivityAnonTraversal)
    assert t.label == 'wr'
    assert t.action_type == 'WriteAction'
    assert len(t.inline_constraints) == 1
    import ast
    c = t.inline_constraints[0]
    assert isinstance(c, ast.Expr)
    assert isinstance(c.value, ast.Compare)
    assert len(c.value.ops) == 1
    assert isinstance(c.value.ops[0], ast.Gt)


def test_anon_traversal_no_constraints_with_block():
    """with do(WriteAction) as wr: pass → label set, no constraints."""
    ir = _parse_src("""
        async def activity(self):
            with do(WriteAction) as wr:
                pass
    """)
    t = ir.stmts[0]
    assert isinstance(t, ActivityAnonTraversal)
    assert t.label == 'wr'
    assert t.inline_constraints == []


def test_anon_traversal_dotted_type():
    """await do(pkg.WriteAction) → action_type='pkg.WriteAction'."""
    ir = _parse_src("""
        async def activity(self):
            await do(pkg.WriteAction)
    """)
    t = ir.stmts[0]
    assert isinstance(t, ActivityAnonTraversal)
    assert t.action_type == 'pkg.WriteAction'


# ---------------------------------------------------------------------------
# super().activity()
# ---------------------------------------------------------------------------

def test_super_activity():
    """super().activity() → ActivitySuper."""
    ir = _parse_src("""
        async def activity(self):
            super().activity()
    """)
    assert len(ir.stmts) == 1
    assert isinstance(ir.stmts[0], ActivitySuper)


def test_super_with_other_stmts():
    """super().activity() followed by other stmts."""
    ir = _parse_src("""
        async def activity(self):
            super().activity()
            await self.a1()
    """)
    assert len(ir.stmts) == 2
    assert isinstance(ir.stmts[0], ActivitySuper)
    assert isinstance(ir.stmts[1], ActivityTraversal)


# ---------------------------------------------------------------------------
# @zdc.dataclass integration — activity detection
# ---------------------------------------------------------------------------

def test_dataclass_detects_activity():
    """@zdc.dataclass stores __activity__ when activity() is defined."""

    @zdc.dataclass
    class MyComp(zdc.Component):
        pass

    @zdc.dataclass
    class SubAction(zdc.Action[MyComp]):
        pass

    @zdc.dataclass
    class CompoundAction(zdc.Action[MyComp]):
        sub: SubAction = zdc.field(default=None)

        async def activity(self):
            await self.sub()

    assert hasattr(CompoundAction, '__activity__')
    ir = CompoundAction.__activity__
    assert isinstance(ir, ActivitySequenceBlock)
    assert len(ir.stmts) == 1
    assert isinstance(ir.stmts[0], ActivityTraversal)
    assert ir.stmts[0].handle == 'sub'


def test_dataclass_no_activity_no_attribute():
    """@zdc.dataclass does NOT set __activity__ for atomic actions."""

    @zdc.dataclass
    class MyComp(zdc.Component):
        pass

    @zdc.dataclass
    class AtomicAction(zdc.Action[MyComp]):
        async def body(self):
            pass

    assert not hasattr(AtomicAction, '__activity__')


def test_dataclass_body_and_activity_raises():
    """Defining both body() and activity() raises TypeError."""

    @zdc.dataclass
    class MyComp(zdc.Component):
        pass

    with pytest.raises(TypeError, match="both activity\\(\\) and body\\(\\)"):
        @zdc.dataclass
        class BadAction(zdc.Action[MyComp]):
            async def activity(self):
                pass

            async def body(self):
                pass


# ---------------------------------------------------------------------------
# Docstring skipping
# ---------------------------------------------------------------------------

def test_docstring_skipped():
    """Docstrings at the start of the activity are silently skipped."""
    ir = _parse_src("""
        async def activity(self):
            \"\"\"This docstring should be ignored.\"\"\"
            await self.a1()
    """)
    assert len(ir.stmts) == 1
    assert isinstance(ir.stmts[0], ActivityTraversal)
