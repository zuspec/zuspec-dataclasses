"""End-to-end test: PSS LRM Example 45 — DMA transfer scenario.

Translates the canonical PSS DMA compound-action example into
zuspec-dataclasses Python syntax and verifies the full activity IR structure.

PSS DSL equivalent::

    buffer data_buff { rand mem_segment_s seg; };
    resource DMA_channel_s { rand bit[3:0] priority; };

    component dma_c {
        pool[4] DMA_channel_s chan_pool;
        bind chan_pool *;

        action write_data {
            output data_buff data;
            lock DMA_channel_s chan;
            rand bit[7:0] size;
            exec body C = "...";
        };

        action read_data {
            input data_buff data;
            lock DMA_channel_s chan;
        };

        action dma_xfer {
            write_data wr;
            read_data rd;
            activity {
                wr;
                rd with { chan.priority > 5; };
            }
        };
    };
"""
import dataclasses
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.ir.activity import (
    ActivitySequenceBlock,
    ActivityTraversal,
)


# ---------------------------------------------------------------------------
# Model definition
# ---------------------------------------------------------------------------

@zdc.dataclass
class MemSegment(zdc.Struct):
    base: zdc.u32 = zdc.rand()
    size: zdc.u32 = zdc.rand()


@zdc.dataclass
class DataBuff(zdc.Buffer):
    seg: MemSegment = zdc.field(default=None)


@zdc.dataclass
class DmaChannel(zdc.Resource):
    priority: zdc.u4 = zdc.rand()


@zdc.dataclass
class DmaComponent(zdc.Component):
    pass


@zdc.dataclass
class WriteData(zdc.Action[DmaComponent]):
    data: DataBuff = zdc.output()
    chan: DmaChannel = zdc.lock()
    size: zdc.u8 = zdc.rand()

    async def body(self):
        pass


@zdc.dataclass
class ReadData(zdc.Action[DmaComponent]):
    data: DataBuff = zdc.input()
    chan: DmaChannel = zdc.lock()

    async def body(self):
        pass


@zdc.dataclass
class DmaXfer(zdc.Action[DmaComponent]):
    wr: WriteData = zdc.field(default=None)
    rd: ReadData = zdc.field(default=None)

    async def activity(self):
        await self.wr()
        async with self.rd():
            self.rd.chan.priority > 5


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_dma_xfer_has_activity_ir():
    """DmaXfer has __activity__ set by @zdc.dataclass."""
    assert hasattr(DmaXfer, '__activity__')
    ir = DmaXfer.__activity__
    assert isinstance(ir, ActivitySequenceBlock)


def test_dma_xfer_activity_two_stmts():
    """DmaXfer activity has exactly two statements: wr traversal and rd traversal."""
    ir = DmaXfer.__activity__
    assert len(ir.stmts) == 2


def test_dma_xfer_wr_traversal():
    """First statement is ActivityTraversal for 'wr' with no inline constraints."""
    wr_t = DmaXfer.__activity__.stmts[0]
    assert isinstance(wr_t, ActivityTraversal)
    assert wr_t.handle == 'wr'
    assert wr_t.inline_constraints == []


def test_dma_xfer_rd_traversal_with_constraint():
    """Second statement is ActivityTraversal for 'rd' with one inline constraint."""
    import ast
    rd_t = DmaXfer.__activity__.stmts[1]
    assert isinstance(rd_t, ActivityTraversal)
    assert rd_t.handle == 'rd'
    assert len(rd_t.inline_constraints) == 1
    c = rd_t.inline_constraints[0]
    assert isinstance(c, ast.Expr)
    assert isinstance(c.value, ast.Compare)
    assert isinstance(c.value.ops[0], ast.Gt)


def test_write_data_is_atomic():
    """WriteData defines body() and has no __activity__."""
    assert not hasattr(WriteData, '__activity__')


def test_read_data_is_atomic():
    """ReadData defines body() and has no __activity__."""
    assert not hasattr(ReadData, '__activity__')


def test_dma_xfer_is_compound():
    """DmaXfer defines activity() and has __activity__."""
    assert hasattr(DmaXfer, '__activity__')


def test_data_buff_is_buffer():
    """DataBuff inherits from Buffer."""
    assert issubclass(DataBuff, zdc.Buffer)
    assert issubclass(DataBuff, zdc.Struct)


def test_dma_channel_is_resource():
    """DmaChannel inherits from Resource."""
    assert issubclass(DmaChannel, zdc.Resource)


def test_write_data_lock_field():
    """WriteData.chan has resource_ref/lock metadata."""
    fields = {f.name: f for f in dataclasses.fields(WriteData)}
    meta = fields['chan'].metadata
    assert meta['kind'] == 'resource_ref'
    assert meta['claim'] == 'lock'


def test_read_data_lock_field():
    """ReadData.chan has resource_ref/lock metadata."""
    fields = {f.name: f for f in dataclasses.fields(ReadData)}
    meta = fields['chan'].metadata
    assert meta['kind'] == 'resource_ref'
    assert meta['claim'] == 'lock'


def test_write_data_output_field_present():
    """WriteData has a 'data' field (Buffer output)."""
    field_names = {f.name for f in dataclasses.fields(WriteData)}
    assert 'data' in field_names


def test_read_data_input_field_present():
    """ReadData has a 'data' field (Buffer input)."""
    field_names = {f.name for f in dataclasses.fields(ReadData)}
    assert 'data' in field_names


# ---------------------------------------------------------------------------
# Stress test / advanced scenario
# ---------------------------------------------------------------------------

@zdc.dataclass
class TopComponent(zdc.Component):
    dma: DmaComponent = zdc.field(default=None)


@zdc.dataclass
class StressTest(zdc.Action[TopComponent]):
    count: zdc.u8 = zdc.rand()

    async def activity(self):
        for i in range(self.count):
            with zdc.parallel():
                with zdc.do(WriteData) as wr:
                    wr.size > 16
                zdc.do(ReadData)
            with zdc.select():
                with zdc.branch(weight=70):
                    zdc.do(DmaXfer)
                with zdc.branch(weight=30):
                    zdc.do(ReadData)


from zuspec.dataclasses.ir.activity import (
    ActivityAnonTraversal,
    ActivityParallel,
    ActivityRepeat,
    ActivitySelect,
)


def test_stress_test_has_activity():
    """StressTest has __activity__ parsed correctly."""
    assert hasattr(StressTest, '__activity__')
    ir = StressTest.__activity__
    assert isinstance(ir, ActivitySequenceBlock)
    assert len(ir.stmts) == 1  # single for loop


def test_stress_test_repeat():
    """StressTest top-level is ActivityRepeat."""
    rep = StressTest.__activity__.stmts[0]
    assert isinstance(rep, ActivityRepeat)
    assert rep.count['attr'] == 'count'
    assert rep.index_var == 'i'


def test_stress_test_repeat_body_parallel_then_select():
    """Repeat body has parallel block then select block."""
    rep = StressTest.__activity__.stmts[0]
    assert len(rep.body) == 2
    assert isinstance(rep.body[0], ActivityParallel)
    assert isinstance(rep.body[1], ActivitySelect)


def test_stress_test_parallel_contents():
    """Parallel block has two anonymous traversals."""
    rep = StressTest.__activity__.stmts[0]
    par = rep.body[0]
    assert len(par.stmts) == 2
    # First: with do(WriteData) as wr: wr.size > 16
    wr_t = par.stmts[0]
    assert isinstance(wr_t, ActivityAnonTraversal)
    assert wr_t.action_type == 'WriteData'
    assert wr_t.label == 'wr'
    assert len(wr_t.inline_constraints) == 1
    # Second: do(ReadData)
    rd_t = par.stmts[1]
    assert isinstance(rd_t, ActivityAnonTraversal)
    assert rd_t.action_type == 'ReadData'


def test_stress_test_select_branches():
    """Select block has two weighted branches."""
    rep = StressTest.__activity__.stmts[0]
    sel = rep.body[1]
    assert len(sel.branches) == 2
    assert sel.branches[0].weight['value'] == 70
    assert sel.branches[1].weight['value'] == 30
    assert sel.branches[0].body[0].action_type == 'DmaXfer'
    assert sel.branches[1].body[0].action_type == 'ReadData'
