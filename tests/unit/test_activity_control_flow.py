"""Tests for ActivityParser — Phase 3 (control flow)."""
import textwrap
import unittest.mock as mock
import pytest
from zuspec.dataclasses.activity_parser import ActivityParser, ActivityParseError
from zuspec.dataclasses.ir.activity import (
    ActivityAnonTraversal,
    ActivityBind,
    ActivityConstraint,
    ActivityDoWhile,
    ActivityForeach,
    ActivityIfElse,
    ActivityMatch,
    ActivityParallel,
    ActivityReplicate,
    ActivityRepeat,
    ActivitySelect,
    ActivitySequenceBlock,
    ActivityTraversal,
    ActivityWhileDo,
    MatchCase,
    SelectBranch,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _parse(src: str) -> ActivitySequenceBlock:
    src = textwrap.dedent(src)
    with mock.patch("inspect.getsource", return_value=src):
        return ActivityParser().parse(mock.MagicMock())


# ---------------------------------------------------------------------------
# repeat — for i in range(N)
# ---------------------------------------------------------------------------

def test_repeat_literal_count():
    """for i in range(3): → ActivityRepeat(count=Const(3), index_var='i')."""
    ir = _parse("""
        async def activity(self):
            for i in range(3):
                await self.a1()
    """)
    assert len(ir.stmts) == 1
    rep = ir.stmts[0]
    assert isinstance(rep, ActivityRepeat)
    assert rep.count == {'type': 'constant', 'value': 3}
    assert rep.index_var == 'i'
    assert len(rep.body) == 1
    assert isinstance(rep.body[0], ActivityTraversal)
    assert rep.body[0].handle == 'a1'


def test_repeat_field_count():
    """for i in range(self.count): → ActivityRepeat with attribute expr."""
    ir = _parse("""
        async def activity(self):
            for i in range(self.count):
                await self.a1()
    """)
    rep = ir.stmts[0]
    assert isinstance(rep, ActivityRepeat)
    assert rep.count['type'] == 'attribute'
    assert rep.count['attr'] == 'count'
    assert rep.index_var == 'i'


def test_repeat_no_index_var():
    """for _ in range(5): → index_var='_'."""
    ir = _parse("""
        async def activity(self):
            for _ in range(5):
                do(WriteAction)
    """)
    rep = ir.stmts[0]
    assert isinstance(rep, ActivityRepeat)
    assert rep.index_var == '_'
    assert rep.count['value'] == 5


def test_repeat_multi_body():
    """repeat body can contain multiple statements."""
    ir = _parse("""
        async def activity(self):
            for i in range(self.n):
                await self.wr()
                await self.rd()
    """)
    rep = ir.stmts[0]
    assert len(rep.body) == 2
    assert rep.body[0].handle == 'wr'
    assert rep.body[1].handle == 'rd'


def test_repeat_in_parallel():
    """repeat nested inside parallel."""
    ir = _parse("""
        async def activity(self):
            with parallel():
                for i in range(4):
                    do(WriteAction)
    """)
    par = ir.stmts[0]
    assert isinstance(par, ActivityParallel)
    rep = par.stmts[0]
    assert isinstance(rep, ActivityRepeat)
    assert rep.count['value'] == 4


# ---------------------------------------------------------------------------
# foreach — for item in self.collection
# ---------------------------------------------------------------------------

def test_foreach_basic():
    """for item in self.data_array: → ActivityForeach."""
    ir = _parse("""
        async def activity(self):
            for item in self.data_array:
                do(ProcessAction)
    """)
    assert len(ir.stmts) == 1
    fe = ir.stmts[0]
    assert isinstance(fe, ActivityForeach)
    assert fe.iterator == 'item'
    assert fe.collection['attr'] == 'data_array'
    assert fe.index_var is None
    assert len(fe.body) == 1


def test_foreach_with_enumerate():
    """for i, item in enumerate(self.array): → ActivityForeach with index_var."""
    ir = _parse("""
        async def activity(self):
            for i, item in enumerate(self.items):
                await self.a1()
    """)
    fe = ir.stmts[0]
    assert isinstance(fe, ActivityForeach)
    assert fe.iterator == 'item'
    assert fe.index_var == 'i'
    assert fe.collection['attr'] == 'items'


# ---------------------------------------------------------------------------
# do_while / while_do
# ---------------------------------------------------------------------------

def test_do_while():
    """with do_while(self.s1.last_one != 0): → ActivityDoWhile."""
    ir = _parse("""
        async def activity(self):
            with do_while(self.s1.last_one != 0):
                await self.s1()
    """)
    dw = ir.stmts[0]
    assert isinstance(dw, ActivityDoWhile)
    assert dw.condition['type'] == 'compare'
    assert dw.condition['ops'] == ['!=']
    assert len(dw.body) == 1
    assert dw.body[0].handle == 's1'


def test_do_while_multi_body():
    """do_while body can contain multiple statements."""
    ir = _parse("""
        async def activity(self):
            with do_while(self.flag > 0):
                await self.a1()
                await self.a2()
    """)
    dw = ir.stmts[0]
    assert len(dw.body) == 2


def test_while_do():
    """with while_do(self.remaining > 0): → ActivityWhileDo."""
    ir = _parse("""
        async def activity(self):
            with while_do(self.remaining > 0):
                do(ProcessAction)
    """)
    wd = ir.stmts[0]
    assert isinstance(wd, ActivityWhileDo)
    assert wd.condition['type'] == 'compare'
    assert wd.condition['ops'] == ['>']
    assert len(wd.body) == 1
    assert isinstance(wd.body[0], ActivityAnonTraversal)


# ---------------------------------------------------------------------------
# replicate
# ---------------------------------------------------------------------------

def test_replicate_basic():
    """for i in replicate(self.count): → ActivityReplicate."""
    ir = _parse("""
        async def activity(self):
            with parallel():
                for i in replicate(self.count):
                    do(ActionA)
    """)
    par = ir.stmts[0]
    rep = par.stmts[0]
    assert isinstance(rep, ActivityReplicate)
    assert rep.count['attr'] == 'count'
    assert rep.index_var == 'i'
    assert rep.label is None
    assert len(rep.body) == 1


def test_replicate_with_label():
    """replicate(N, label='RL') → ActivityReplicate(label='RL')."""
    ir = _parse("""
        async def activity(self):
            with parallel():
                for i in replicate(self.count, label='RL'):
                    do(ActionA)
                    do(ActionB)
    """)
    rep = ir.stmts[0].stmts[0]
    assert isinstance(rep, ActivityReplicate)
    assert rep.label == 'RL'
    assert len(rep.body) == 2


def test_replicate_literal_count():
    """replicate(4) with literal count."""
    ir = _parse("""
        async def activity(self):
            with parallel():
                for i in replicate(4):
                    do(ActionA)
    """)
    rep = ir.stmts[0].stmts[0]
    assert rep.count['value'] == 4


# ---------------------------------------------------------------------------
# select / branch
# ---------------------------------------------------------------------------

def test_select_two_branches():
    """select with two branches → ActivitySelect with 2 SelectBranch nodes."""
    ir = _parse("""
        async def activity(self):
            with select():
                with branch():
                    await self.action1()
                with branch():
                    await self.action2()
    """)
    sel = ir.stmts[0]
    assert isinstance(sel, ActivitySelect)
    assert len(sel.branches) == 2
    assert all(isinstance(b, SelectBranch) for b in sel.branches)
    assert sel.branches[0].guard is None
    assert sel.branches[0].weight is None


def test_select_branch_with_guard():
    """branch(guard=self.a == 0) → SelectBranch with guard expr."""
    ir = _parse("""
        async def activity(self):
            with select():
                with branch(guard=self.a == 0):
                    await self.action1()
    """)
    branch = ir.stmts[0].branches[0]
    assert branch.guard is not None
    assert branch.guard['type'] == 'compare'
    assert branch.guard['ops'] == ['==']


def test_select_branch_with_weight():
    """branch(weight=70) → SelectBranch with weight expr."""
    ir = _parse("""
        async def activity(self):
            with select():
                with branch(weight=70):
                    await self.action1()
                with branch(weight=30):
                    await self.action2()
    """)
    b0, b1 = ir.stmts[0].branches
    assert b0.weight['value'] == 70
    assert b1.weight['value'] == 30


def test_select_branch_guard_and_weight():
    """branch(guard=..., weight=...) → both set."""
    ir = _parse("""
        async def activity(self):
            with select():
                with branch(guard=self.x > 0, weight=20):
                    await self.action1()
    """)
    b = ir.stmts[0].branches[0]
    assert b.guard is not None
    assert b.weight['value'] == 20


def test_select_branch_body_has_do():
    """Branch body can contain do() anonymous traversals."""
    ir = _parse("""
        async def activity(self):
            with select():
                with branch(weight=50):
                    do(WriteData)
                with branch(weight=50):
                    do(ReadData)
    """)
    sel = ir.stmts[0]
    assert isinstance(sel.branches[0].body[0], ActivityAnonTraversal)
    assert sel.branches[1].body[0].action_type == 'ReadData'


def test_select_three_branches():
    """select with three branches."""
    ir = _parse("""
        async def activity(self):
            with select():
                with branch(weight=70):
                    do(DmaXfer)
                with branch(weight=20):
                    do(ReadData)
                with branch(weight=10):
                    do(WriteData)
    """)
    assert len(ir.stmts[0].branches) == 3


# ---------------------------------------------------------------------------
# if / else
# ---------------------------------------------------------------------------

def test_if_no_else():
    """if cond: body (no else) → ActivityIfElse with empty else_body."""
    ir = _parse("""
        async def activity(self):
            if self.x > 5:
                await self.a1()
    """)
    ife = ir.stmts[0]
    assert isinstance(ife, ActivityIfElse)
    assert ife.condition['ops'] == ['>']
    assert len(ife.if_body) == 1
    assert ife.if_body[0].handle == 'a1'
    assert ife.else_body == []


def test_if_else():
    """if/else → ActivityIfElse with both bodies populated."""
    ir = _parse("""
        async def activity(self):
            if self.x > 5:
                await self.a1()
            else:
                await self.a2()
    """)
    ife = ir.stmts[0]
    assert len(ife.if_body) == 1
    assert len(ife.else_body) == 1
    assert ife.if_body[0].handle == 'a1'
    assert ife.else_body[0].handle == 'a2'


def test_if_elif_else():
    """if/elif/else → nested ActivityIfElse in else_body."""
    ir = _parse("""
        async def activity(self):
            if self.x > 10:
                await self.a1()
            elif self.x > 5:
                await self.a2()
            else:
                await self.a3()
    """)
    ife = ir.stmts[0]
    assert len(ife.if_body) == 1
    assert len(ife.else_body) == 1
    # elif becomes a nested ActivityIfElse in else_body
    inner = ife.else_body[0]
    assert isinstance(inner, ActivityIfElse)
    assert inner.if_body[0].handle == 'a2'
    assert inner.else_body[0].handle == 'a3'


def test_if_with_parallel_body():
    """if body can contain a parallel block."""
    ir = _parse("""
        async def activity(self):
            if self.mode == 0:
                with parallel():
                    await self.a1()
                    await self.a2()
    """)
    ife = ir.stmts[0]
    assert isinstance(ife.if_body[0], ActivityParallel)


# ---------------------------------------------------------------------------
# match / case
# ---------------------------------------------------------------------------

def test_match_basic():
    """match self.level: case 0: ... case 1: ... → ActivityMatch."""
    ir = _parse("""
        async def activity(self):
            match self.level:
                case 0:
                    await self.action1()
                case 1:
                    await self.action2()
    """)
    m = ir.stmts[0]
    assert isinstance(m, ActivityMatch)
    assert m.subject['attr'] == 'level'
    assert len(m.cases) == 2
    assert m.cases[0].pattern == {'type': 'constant', 'value': 0}
    assert isinstance(m.cases[0].body[0], ActivityTraversal)
    assert m.cases[0].body[0].handle == 'action1'


def test_match_wildcard():
    """case _: maps to wildcard pattern."""
    ir = _parse("""
        async def activity(self):
            match self.level:
                case 0:
                    await self.a1()
                case _:
                    await self.a2()
    """)
    m = ir.stmts[0]
    assert m.cases[1].pattern == {'type': 'wildcard'}


def test_match_three_cases():
    """match with three cases."""
    ir = _parse("""
        async def activity(self):
            match self.security_level:
                case 0:
                    await self.action1()
                case 1:
                    await self.action2()
                case _:
                    await self.action3()
    """)
    assert len(ir.stmts[0].cases) == 3


# ---------------------------------------------------------------------------
# constraint block
# ---------------------------------------------------------------------------

def test_constraint_block():
    """with constraint(): → ActivityConstraint with ast.stmt nodes."""
    ir = _parse("""
        async def activity(self):
            await self.a1()
            await self.a2()
            with constraint():
                self.a1.size < 100
                self.a1.addr != self.a2.addr
    """)
    import ast
    assert len(ir.stmts) == 3
    con = ir.stmts[2]
    assert isinstance(con, ActivityConstraint)
    assert len(con.constraints) == 2
    c0, c1 = con.constraints
    assert isinstance(c0, ast.Expr) and isinstance(c0.value.ops[0], ast.Lt)
    assert isinstance(c1, ast.Expr) and isinstance(c1.value.ops[0], ast.NotEq)


def test_constraint_block_empty():
    """with constraint(): pass → ActivityConstraint with no constraints."""
    ir = _parse("""
        async def activity(self):
            with constraint():
                pass
    """)
    con = ir.stmts[0]
    assert isinstance(con, ActivityConstraint)
    assert con.constraints == []


# ---------------------------------------------------------------------------
# bind
# ---------------------------------------------------------------------------

def test_bind():
    """bind(self.producer.data_out, self.consumer.data_in) → ActivityBind."""
    ir = _parse("""
        async def activity(self):
            await self.producer()
            await self.consumer()
            bind(self.producer.data_out, self.consumer.data_in)
    """)
    b = ir.stmts[2]
    assert isinstance(b, ActivityBind)
    # src is self.producer.data_out
    assert b.src['attr'] == 'data_out'
    # dst is self.consumer.data_in
    assert b.dst['attr'] == 'data_in'


# ---------------------------------------------------------------------------
# Complex / combined scenarios
# ---------------------------------------------------------------------------

def test_repeat_with_select_inside():
    """for/range containing a select block."""
    ir = _parse("""
        async def activity(self):
            for i in range(self.count):
                with select():
                    with branch(weight=70):
                        do(DmaXfer)
                    with branch(weight=30):
                        do(ReadData)
    """)
    rep = ir.stmts[0]
    assert isinstance(rep, ActivityRepeat)
    sel = rep.body[0]
    assert isinstance(sel, ActivitySelect)
    assert len(sel.branches) == 2


def test_parallel_with_repeat_and_select():
    """Parallel block containing both repeat and select."""
    ir = _parse("""
        async def activity(self):
            with parallel(join_first=1):
                do(WriteData)
                do(WriteData)
            do(ReadData)
    """)
    par = ir.stmts[0]
    assert isinstance(par, ActivityParallel)
    assert par.join_spec.kind == 'first'
    assert len(par.stmts) == 2
    last = ir.stmts[1]
    assert isinstance(last, ActivityAnonTraversal)
    assert last.action_type == 'ReadData'
