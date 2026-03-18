"""Tests for ActivityParser — Phase 2 (scheduling blocks)."""
import textwrap
import unittest.mock as mock
import pytest
from zuspec.dataclasses.activity_parser import ActivityParser, ActivityParseError
from zuspec.dataclasses.ir.activity import (
    ActivityAnonTraversal,
    ActivityAtomic,
    ActivityParallel,
    ActivitySchedule,
    ActivitySequenceBlock,
    ActivityTraversal,
    JoinSpec,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _parse(src: str) -> ActivitySequenceBlock:
    src = textwrap.dedent(src)
    with mock.patch("inspect.getsource", return_value=src):
        return ActivityParser().parse(mock.MagicMock())


# ---------------------------------------------------------------------------
# parallel()
# ---------------------------------------------------------------------------

def test_parallel_basic():
    """with parallel(): → ActivityParallel with no join_spec."""
    ir = _parse("""
        async def activity(self):
            with parallel():
                await self.a1()
                await self.a2()
    """)
    assert len(ir.stmts) == 1
    par = ir.stmts[0]
    assert isinstance(par, ActivityParallel)
    assert par.join_spec is None
    assert len(par.stmts) == 2
    assert isinstance(par.stmts[0], ActivityTraversal)
    assert par.stmts[0].handle == 'a1'
    assert par.stmts[1].handle == 'a2'


def test_parallel_join_all_is_default():
    """parallel() with no kwargs → join_spec is None (join_all by default)."""
    ir = _parse("""
        async def activity(self):
            with parallel():
                await self.a1()
    """)
    assert ir.stmts[0].join_spec is None


def test_parallel_join_branch():
    """parallel(join_branch='L2') → JoinSpec(kind='branch', branch_label='L2')."""
    ir = _parse("""
        async def activity(self):
            with parallel(join_branch='L2'):
                L2 = do(ActionA)
                L3 = do(ActionB)
            do(ActionC)
    """)
    par = ir.stmts[0]
    assert isinstance(par, ActivityParallel)
    assert par.join_spec is not None
    assert par.join_spec.kind == 'branch'
    assert par.join_spec.branch_label == 'L2'
    # After the parallel block, ActionC
    assert isinstance(ir.stmts[1], ActivityAnonTraversal)
    assert ir.stmts[1].action_type == 'ActionC'


def test_parallel_join_none():
    """parallel(join_none=True) → JoinSpec(kind='none')."""
    ir = _parse("""
        async def activity(self):
            with parallel(join_none=True):
                await self.a1()
                await self.a2()
    """)
    js = ir.stmts[0].join_spec
    assert js is not None
    assert js.kind == 'none'
    assert js.count is None
    assert js.branch_label is None


def test_parallel_join_select():
    """parallel(join_select=1) → JoinSpec(kind='select', count=Const(1))."""
    ir = _parse("""
        async def activity(self):
            with parallel(join_select=1):
                await self.a1()
                await self.a2()
    """)
    js = ir.stmts[0].join_spec
    assert js.kind == 'select'
    assert js.count is not None
    assert js.count['type'] == 'constant'
    assert js.count['value'] == 1


def test_parallel_join_first():
    """parallel(join_first=1) → JoinSpec(kind='first', count=Const(1))."""
    ir = _parse("""
        async def activity(self):
            with parallel(join_first=1):
                await self.a1()
                await self.a2()
            await self.a3()
    """)
    js = ir.stmts[0].join_spec
    assert js.kind == 'first'
    assert js.count['value'] == 1
    # Sequential action after the parallel block
    assert isinstance(ir.stmts[1], ActivityTraversal)
    assert ir.stmts[1].handle == 'a3'


def test_parallel_with_do_stmts():
    """parallel() body can contain do() anonymous traversals."""
    ir = _parse("""
        async def activity(self):
            with parallel():
                do(WriteData)
                do(ReadData)
    """)
    par = ir.stmts[0]
    assert len(par.stmts) == 2
    assert all(isinstance(s, ActivityAnonTraversal) for s in par.stmts)
    assert par.stmts[0].action_type == 'WriteData'
    assert par.stmts[1].action_type == 'ReadData'


# ---------------------------------------------------------------------------
# schedule()
# ---------------------------------------------------------------------------

def test_schedule_basic():
    """with schedule(): → ActivitySchedule with no join_spec."""
    ir = _parse("""
        async def activity(self):
            with schedule():
                await self.a1()
                await self.a2()
                await self.a3()
    """)
    assert len(ir.stmts) == 1
    sched = ir.stmts[0]
    assert isinstance(sched, ActivitySchedule)
    assert sched.join_spec is None
    assert len(sched.stmts) == 3


def test_schedule_join_branch():
    """schedule(join_branch='L1') → JoinSpec(kind='branch', branch_label='L1')."""
    ir = _parse("""
        async def activity(self):
            with schedule(join_branch='L1'):
                L1 = do(ActionA)
                L2 = do(ActionB)
            do(ActionC)
    """)
    sched = ir.stmts[0]
    assert isinstance(sched, ActivitySchedule)
    js = sched.join_spec
    assert js.kind == 'branch'
    assert js.branch_label == 'L1'


def test_schedule_join_none():
    """schedule(join_none=True) → JoinSpec(kind='none')."""
    ir = _parse("""
        async def activity(self):
            with schedule(join_none=True):
                do(ActionA)
    """)
    js = ir.stmts[0].join_spec
    assert js.kind == 'none'


def test_schedule_join_first():
    """schedule(join_first=2) → JoinSpec(kind='first', count=Const(2))."""
    ir = _parse("""
        async def activity(self):
            with schedule(join_first=2):
                do(ActionA)
                do(ActionB)
                do(ActionC)
    """)
    js = ir.stmts[0].join_spec
    assert js.kind == 'first'
    assert js.count['value'] == 2


# ---------------------------------------------------------------------------
# sequence() — explicit
# ---------------------------------------------------------------------------

def test_sequence_explicit():
    """with sequence(): → ActivitySequenceBlock (explicit, same as default)."""
    ir = _parse("""
        async def activity(self):
            with sequence():
                await self.a1()
                await self.a2()
    """)
    assert len(ir.stmts) == 1
    seq = ir.stmts[0]
    assert isinstance(seq, ActivitySequenceBlock)
    assert len(seq.stmts) == 2
    assert seq.stmts[0].handle == 'a1'


def test_sequence_nested_in_parallel():
    """Explicit sequence inside parallel."""
    ir = _parse("""
        async def activity(self):
            with parallel():
                with sequence():
                    await self.a1()
                    await self.a2()
                await self.a3()
    """)
    par = ir.stmts[0]
    assert isinstance(par, ActivityParallel)
    assert len(par.stmts) == 2
    seq = par.stmts[0]
    assert isinstance(seq, ActivitySequenceBlock)
    assert len(seq.stmts) == 2


# ---------------------------------------------------------------------------
# atomic()
# ---------------------------------------------------------------------------

def test_atomic_basic():
    """with atomic(): → ActivityAtomic."""
    ir = _parse("""
        async def activity(self):
            with atomic():
                await self.a1()
                await self.a2()
    """)
    assert len(ir.stmts) == 1
    atom = ir.stmts[0]
    assert isinstance(atom, ActivityAtomic)
    assert len(atom.stmts) == 2
    assert atom.stmts[0].handle == 'a1'
    assert atom.stmts[1].handle == 'a2'


def test_atomic_single_stmt():
    """atomic() with a single statement."""
    ir = _parse("""
        async def activity(self):
            with atomic():
                do(WriteAction)
    """)
    atom = ir.stmts[0]
    assert isinstance(atom, ActivityAtomic)
    assert len(atom.stmts) == 1
    assert isinstance(atom.stmts[0], ActivityAnonTraversal)


# ---------------------------------------------------------------------------
# Nesting
# ---------------------------------------------------------------------------

def test_parallel_nested_inside_sequence():
    """Parallel block inside the default (implicit) sequence."""
    ir = _parse("""
        async def activity(self):
            await self.pre()
            with parallel():
                await self.a1()
                await self.a2()
            await self.post()
    """)
    assert len(ir.stmts) == 3
    assert isinstance(ir.stmts[0], ActivityTraversal)
    assert isinstance(ir.stmts[1], ActivityParallel)
    assert isinstance(ir.stmts[2], ActivityTraversal)


def test_schedule_nested_inside_parallel():
    """schedule() nested inside parallel()."""
    ir = _parse("""
        async def activity(self):
            with parallel():
                with schedule():
                    await self.a1()
                    await self.a2()
                await self.a3()
    """)
    par = ir.stmts[0]
    assert isinstance(par, ActivityParallel)
    sched = par.stmts[0]
    assert isinstance(sched, ActivitySchedule)
    assert len(sched.stmts) == 2


def test_deeply_nested_blocks():
    """Three levels of nesting: parallel > sequence > atomic."""
    ir = _parse("""
        async def activity(self):
            with parallel():
                with sequence():
                    with atomic():
                        await self.a1()
    """)
    par = ir.stmts[0]
    seq = par.stmts[0]
    atom = seq.stmts[0]
    assert isinstance(atom, ActivityAtomic)
    assert atom.stmts[0].handle == 'a1'
