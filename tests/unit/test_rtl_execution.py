"""Test Execution Engine (Phase 2B/2C)"""
import asyncio
import pytest
import zuspec.dataclasses as zdc


def test_simple_counter():
    """Test a simple counter with sync process"""
    
    @zdc.dataclass
    class Counter(zdc.Component):
        clock : zdc.bit = zdc.input()
        reset : zdc.bit = zdc.input()
        count : zdc.bit32 = zdc.output()
        
        @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
        def _count_proc(self):
            if self.reset:
                self.count = 0
            else:
                self.count = self.count + 1
    
    counter = Counter()

    async def wait(amt : int):
        nonlocal counter

        for _ in range(amt):
            counter.clock = 1
            await counter.wait(zdc.Time.ns(5))
            counter.clock = 0
            await counter.wait(zdc.Time.ns(5))


    async def run():
        nonlocal counter
        # Initial state
        assert counter.count == 0
    
        # Reset
        counter.reset = 1
        counter.clock = 0
        await counter.wait(zdc.Time.ns(5))
        await wait(1)
        assert counter.count == 0

        await wait(20) 

        assert counter.count == 0
    
        # Release reset and count
        counter.reset = 0
        await wait(10) 
        assert counter.count == 10

        await wait(10) 
        assert counter.count == 20

    asyncio.run(run())    


def test_deferred_assignment_semantics():
    """Verify that sync processes read old values and write new values"""
    
    @zdc.dataclass
    class DeferredTest(zdc.Component):
        clock : zdc.bit = zdc.input()
        value : zdc.bit8 = zdc.field()
        old_value : zdc.bit8 = zdc.field()
        
        @zdc.sync(clock=lambda s: s.clock)
        def _proc(self):
            self.old_value = self.value
            self.value = self.value + 1
    
    comp = DeferredTest()
    
    # Set initial value
    comp.value = 5
    
    async def run():
        nonlocal comp
        
        # After one clock edge, old_value should have captured the old value (5)
        # and value should be incremented (6)
        comp.clock = 1
        await comp.wait(zdc.Time.ns(5))
        comp.clock = 0
        await comp.wait(zdc.Time.ns(5))
        
        assert comp.old_value == 5
        assert comp.value == 6
    
    asyncio.run(run())


def test_simple_comb_process():
    """Test a simple combinational process"""
    
    @zdc.dataclass
    class XorGate(zdc.Component):
        a : zdc.bit8 = zdc.input()
        b : zdc.bit8 = zdc.input()
        out : zdc.bit8 = zdc.output()
        
        @zdc.comb
        def _xor_calc(self):
            self.out = self.a ^ self.b
    
    gate = XorGate()
    
    # Set inputs - comb process evaluates automatically
    gate.a = 5
    gate.b = 3
    
    assert gate.out == (5 ^ 3)


def test_comb_auto_evaluation():
    """Test that comb processes re-evaluate when inputs change"""
    
    @zdc.dataclass
    class AddGate(zdc.Component):
        a : zdc.bit8 = zdc.input()
        b : zdc.bit8 = zdc.input()
        sum : zdc.bit8 = zdc.output()
        
        @zdc.comb
        def _add(self):
            self.sum = self.a + self.b
    
    gate = AddGate()
    
    # Initial state
    assert gate.sum == 0
    
    # Change input a - should trigger re-evaluation
    gate.a = 10
    assert gate.sum == 10
    
    # Change input b - should trigger re-evaluation
    gate.b = 5
    assert gate.sum == 15


def test_sync_and_comb_together():
    """Test component with both sync and comb processes"""
    
    @zdc.dataclass
    class Pipeline(zdc.Component):
        clock : zdc.bit = zdc.input()
        a : zdc.bit8 = zdc.input()
        b : zdc.bit8 = zdc.input()
        result : zdc.bit8 = zdc.output()
        
        _sum : zdc.bit8 = zdc.field()
        
        @zdc.comb
        def _add(self):
            self._sum = self.a + self.b
        
        @zdc.sync(clock=lambda s: s.clock)
        def _register(self):
            self.result = self._sum
    
    pipeline = Pipeline()
    
    async def run():
        nonlocal pipeline
        
        # Set inputs - comb calculates sum immediately
        pipeline.a = 10
        pipeline.b = 20
        
        assert pipeline._sum == 30
        
        # Result is not updated yet (sync process hasn't run)
        assert pipeline.result == 0
        
        # Clock edge captures the sum
        pipeline.clock = 1
        await pipeline.wait(zdc.Time.ns(5))
        pipeline.clock = 0
        await pipeline.wait(zdc.Time.ns(5))
        
        assert pipeline.result == 30
    
    asyncio.run(run())



# ---------------------------------------------------------------------------
# ACTION-4 tests: new IR node handlers
# ---------------------------------------------------------------------------

def test_bitwise_not_unary():
    """ExprUnary Invert (~) produces bitwise complement masked to 64 bits."""
    from zuspec.ir.core.expr import ExprUnary, ExprConstant, UnaryOp
    from zuspec.dataclasses.rt.executor import Executor

    class _FakeBackend:
        def signal_write(self, comp, name, value, width=32):
            pass
        def get_signal(self, comp, name):
            return 0

    exec_ = Executor(state_backend=_FakeBackend(), component=None)

    expr = ExprUnary(op=UnaryOp.Invert, operand=ExprConstant(value=0))
    result = exec_.evaluate_expr(expr)
    # ~0 masked to 64 bits
    assert result == (1 << 64) - 1

    expr2 = ExprUnary(op=UnaryOp.Not, operand=ExprConstant(value=5))
    assert exec_.evaluate_expr(expr2) == 0

    expr3 = ExprUnary(op=UnaryOp.USub, operand=ExprConstant(value=7))
    assert exec_.evaluate_expr(expr3) == -7


def test_bit_slice_extraction():
    """ExprSubscript with ExprSlice extracts correct bit range."""
    from zuspec.ir.core.expr import ExprSubscript, ExprSlice, ExprConstant
    from zuspec.dataclasses.rt.executor import Executor

    class _FakeBackend:
        def signal_write(self, comp, name, value, width=32):
            pass
        def get_signal(self, comp, name):
            return 0

    exec_ = Executor(state_backend=_FakeBackend(), component=None)

    # 0xAB = 0b10101011 — bits [3:0] = 0b1011 = 0xB
    val = 0xAB
    expr = ExprSubscript(
        value=ExprConstant(value=val),
        slice=ExprSlice(upper=ExprConstant(value=3),
                        lower=ExprConstant(value=0))
    )
    assert exec_.evaluate_expr(expr) == 0xB

    # bits [7:4] = 0b1010 = 0xA
    expr2 = ExprSubscript(
        value=ExprConstant(value=val),
        slice=ExprSlice(upper=ExprConstant(value=7),
                        lower=ExprConstant(value=4))
    )
    assert exec_.evaluate_expr(expr2) == 0xA


def test_stmt_repeat_executes_n_times():
    """StmtRepeat executes its body exactly N times."""
    from zuspec.ir.core.stmt import StmtRepeat, StmtAugAssign
    from zuspec.ir.core.expr import ExprConstant, ExprRefLocal, AugOp
    from zuspec.dataclasses.rt.executor import Executor

    class _FakeBackend:
        def signal_write(self, comp, name, value, width=32):
            pass
        def get_signal(self, comp, name):
            return 0

    exec_ = Executor(state_backend=_FakeBackend(), component=None)
    exec_.locals['counter'] = 0

    # Build: repeat (5) { counter += 1 }
    body = [StmtAugAssign(
        target=ExprRefLocal(name='counter'),
        op=AugOp.Add,
        value=ExprConstant(value=1),
    )]
    stmt = StmtRepeat(count=ExprConstant(value=5), body=body)
    exec_.execute_stmt(stmt)
    assert exec_.locals['counter'] == 5


def test_stmt_assert_raises_on_false():
    """StmtAssert raises AssertionError when condition is False."""
    import pytest
    from zuspec.ir.core.stmt import StmtAssert
    from zuspec.ir.core.expr import ExprConstant
    from zuspec.dataclasses.rt.executor import Executor

    class _FakeBackend:
        def signal_write(self, comp, name, value, width=32): pass
        def get_signal(self, comp, name): return 0

    exec_ = Executor(state_backend=_FakeBackend(), component=None)

    # assert True — should not raise
    exec_.execute_stmt(StmtAssert(test=ExprConstant(value=1)))

    # assert False — must raise
    with pytest.raises(AssertionError, match=r"\[zdc sim\]"):
        exec_.execute_stmt(StmtAssert(test=ExprConstant(value=0),
                                      msg=ExprConstant(value="boom")))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ---------------------------------------------------------------------------
# ACTION-2: @zdc.enum decorator tests
# ---------------------------------------------------------------------------

def test_enum_decorator_creates_ir_node():
    """@zdc.enum marks class and creates DataTypeEnum IR node."""
    from zuspec.ir.core.data_type import DataTypeEnum

    @zdc.enum
    class State:
        IDLE  = 0
        FETCH = 1
        EXEC  = 2

    assert hasattr(State, '_zdc_enum') and State._zdc_enum
    assert State._zdc_enum_members == {'IDLE': 0, 'FETCH': 1, 'EXEC': 2}
    assert State._zdc_enum_width == 2
    assert isinstance(State._zdc_data_type, DataTypeEnum)
    assert State._zdc_data_type.name == 'State'
    assert State._zdc_data_type.width == 2
    assert State._zdc_data_type.items == {'IDLE': 0, 'FETCH': 1, 'EXEC': 2}


def test_enum_decorator_explicit_width():
    """@zdc.enum(width=N) stores explicit bit width."""

    @zdc.enum(width=4)
    class Opcode:
        ADD = 0
        SUB = 1

    assert Opcode._zdc_enum_width == 4


def test_enum_values_accessible_as_attributes():
    """Enum member values are plain int attributes on the class."""

    @zdc.enum
    class Color:
        RED   = 0
        GREEN = 1
        BLUE  = 2

    assert Color.RED == 0
    assert Color.GREEN == 1
    assert Color.BLUE == 2
    assert isinstance(Color.RED, int)
