"""End-to-end tests: control flow statements in compound actions."""
import asyncio
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.activity_dsl import do, select, branch
from zuspec.dataclasses.rt.scenario_runner import ScenarioRunner


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Simple component (no resources needed)
# ---------------------------------------------------------------------------

@zdc.dataclass
class SysComp(zdc.Component):
    pass


# ---------------------------------------------------------------------------
# Counter leaf action
# ---------------------------------------------------------------------------

_exec_log: list = []


@zdc.dataclass
class Tick(zdc.Action[SysComp]):
    async def body(self):
        _exec_log.append("tick")


@zdc.dataclass
class Tock(zdc.Action[SysComp]):
    async def body(self):
        _exec_log.append("tock")


# ---------------------------------------------------------------------------
# Compound with repeat (Python for-range syntax)
# ---------------------------------------------------------------------------

@zdc.dataclass
class RepeatThree(zdc.Action[SysComp]):
    async def activity(self):
        for i in range(3):
            do(Tick)


# ---------------------------------------------------------------------------
# Compound with foreach (Python for-enumerate syntax)
# ---------------------------------------------------------------------------

@zdc.dataclass
class ForeachFive(zdc.Action[SysComp]):
    items: list = zdc.field(default_factory=lambda: [0, 1, 2, 3, 4])

    async def activity(self):
        for idx, item in enumerate(self.items):
            do(Tick)


# ---------------------------------------------------------------------------
# Compound with if/else (Python if syntax)
# ---------------------------------------------------------------------------

@zdc.dataclass
class IfElse(zdc.Action[SysComp]):
    flag: bool = True

    async def activity(self):
        if self.flag:
            do(Tick)
        else:
            do(Tock)


# ---------------------------------------------------------------------------
# Compound with select (two equal-weight alternatives)
# ---------------------------------------------------------------------------

@zdc.dataclass
class SelectEither(zdc.Action[SysComp]):
    async def activity(self):
        with select():
            with branch(weight=1):
                do(Tick)
            with branch(weight=1):
                do(Tock)


# ---------------------------------------------------------------------------
# Compound with sequential sub-actions
# ---------------------------------------------------------------------------

@zdc.dataclass
class TickTock(zdc.Action[SysComp]):
    t1: Tick = None
    t2: Tock = None

    async def activity(self):
        await self.t1()
        await self.t2()


# ---------------------------------------------------------------------------
# Nested control flow: repeat inside if
# ---------------------------------------------------------------------------

@zdc.dataclass
class NestedControl(zdc.Action[SysComp]):
    flag: bool = True

    async def activity(self):
        if self.flag:
            for i in range(2):
                do(Tick)
        else:
            do(Tock)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_repeat_runs_n_times():
    """for i in range(3) executes leaf action exactly 3 times."""
    _exec_log.clear()
    comp = SysComp()
    _run(ScenarioRunner(comp, seed=1).run(RepeatThree))
    assert _exec_log.count("tick") == 3


def test_foreach_runs_n_iterations():
    """for idx, item in enumerate(items) executes leaf exactly len(items) times."""
    _exec_log.clear()
    comp = SysComp()
    _run(ScenarioRunner(comp, seed=2).run(ForeachFive))
    assert _exec_log.count("tick") == 5


def test_if_else_true_branch():
    """if True: executes the if branch (Tick), not else (Tock)."""
    _exec_log.clear()
    comp = SysComp()
    _run(ScenarioRunner(comp, seed=3).run(IfElse))
    assert "tick" in _exec_log
    assert "tock" not in _exec_log


def test_if_else_false_branch():
    """if False: executes the else branch (Tock), not if (Tick)."""
    _exec_log.clear()

    @zdc.dataclass
    class IfElseFalse(zdc.Action[SysComp]):
        flag: bool = False

        async def activity(self):
            if self.flag:
                do(Tick)
            else:
                do(Tock)

    comp = SysComp()
    _run(ScenarioRunner(comp, seed=3).run(IfElseFalse))
    assert "tock" in _exec_log
    assert "tick" not in _exec_log


def test_select_executes_one_branch():
    """select() executes exactly one of the weighted alternatives."""
    _exec_log.clear()
    comp = SysComp()
    _run(ScenarioRunner(comp, seed=4).run(SelectEither))
    total = _exec_log.count("tick") + _exec_log.count("tock")
    assert total == 1


def test_sequential_handles_both_run():
    """Sequential compound: both Tick and Tock body() called in order."""
    _exec_log.clear()
    comp = SysComp()
    result = _run(ScenarioRunner(comp, seed=5).run(TickTock))
    assert "tick" in _exec_log
    assert "tock" in _exec_log
    assert _exec_log.index("tick") < _exec_log.index("tock")
    assert result.t1 is not None
    assert result.t2 is not None


def test_nested_control_true_executes_repeat():
    """if True → repeat(2): Tick called twice."""
    _exec_log.clear()
    comp = SysComp()
    _run(ScenarioRunner(comp, seed=6).run(NestedControl))
    assert _exec_log.count("tick") == 2
    assert "tock" not in _exec_log

