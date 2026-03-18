"""Tests for Phase 4 — flow-object and resource fields in actions."""
import dataclasses
import textwrap
import unittest.mock as mock
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.activity_parser import ActivityParser
from zuspec.dataclasses.ir.activity import (
    ActivityBind,
    ActivitySequenceBlock,
    ActivityTraversal,
)


def _parse(src: str) -> ActivitySequenceBlock:
    src = textwrap.dedent(src)
    with mock.patch("inspect.getsource", return_value=src):
        return ActivityParser().parse(mock.MagicMock())


# ---------------------------------------------------------------------------
# Buffer fields with input / output
# ---------------------------------------------------------------------------

def test_buffer_output_field():
    """Action with a Buffer output() field has correct metadata."""
    @zdc.dataclass
    class DataBuff(zdc.Buffer):
        base: zdc.u32 = zdc.rand()

    @zdc.dataclass
    class WriteAction(zdc.Action[zdc.Component]):
        data: DataBuff = zdc.output()

    fields = {f.name: f for f in dataclasses.fields(WriteAction)}
    # output() metadata (existing decorator behavior)
    assert 'data' in fields


def test_buffer_input_field():
    """Action with a Buffer input() field."""
    @zdc.dataclass
    class DataBuff(zdc.Buffer):
        base: zdc.u32 = zdc.rand()

    @zdc.dataclass
    class ReadAction(zdc.Action[zdc.Component]):
        data: DataBuff = zdc.input()

    fields = {f.name: f for f in dataclasses.fields(ReadAction)}
    assert 'data' in fields


# ---------------------------------------------------------------------------
# Stream and State fields
# ---------------------------------------------------------------------------

def test_stream_field():
    """Action with a Stream output field."""
    @zdc.dataclass
    class DataStream(zdc.Stream):
        width: zdc.u8 = zdc.rand()

    @zdc.dataclass
    class ProduceAction(zdc.Action[zdc.Component]):
        stream_out: DataStream = zdc.output()

    fields = {f.name: f for f in dataclasses.fields(ProduceAction)}
    assert 'stream_out' in fields


def test_state_field():
    """Action with a State input field."""
    @zdc.dataclass
    class ConfigState(zdc.State):
        mode: zdc.u4 = zdc.rand()

    @zdc.dataclass
    class ConfigAction(zdc.Action[zdc.Component]):
        cfg: ConfigState = zdc.input()

    fields = {f.name: f for f in dataclasses.fields(ConfigAction)}
    assert 'cfg' in fields


# ---------------------------------------------------------------------------
# Resource fields with lock / share
# ---------------------------------------------------------------------------

def test_resource_lock_field():
    """Action with a Resource lock() field has resource_ref/lock metadata."""
    @zdc.dataclass
    class DmaChannel(zdc.Resource):
        priority: zdc.u4 = zdc.rand()

    @zdc.dataclass
    class WriteAction(zdc.Action[zdc.Component]):
        chan: DmaChannel = zdc.lock()

    fields = {f.name: f for f in dataclasses.fields(WriteAction)}
    meta = fields['chan'].metadata
    assert meta['kind'] == 'resource_ref'
    assert meta['claim'] == 'lock'


def test_resource_share_field():
    """Action with a Resource share() field has resource_ref/share metadata."""
    @zdc.dataclass
    class CpuCore(zdc.Resource):
        pass

    @zdc.dataclass
    class SharedAction(zdc.Action[zdc.Component]):
        cpu: CpuCore = zdc.share()

    fields = {f.name: f for f in dataclasses.fields(SharedAction)}
    meta = fields['cpu'].metadata
    assert meta['kind'] == 'resource_ref'
    assert meta['claim'] == 'share'


# ---------------------------------------------------------------------------
# Mixed action fields (buffer + resource + rand)
# ---------------------------------------------------------------------------

def test_action_with_mixed_fields():
    """Action can have buffer, resource, and rand fields together."""
    @zdc.dataclass
    class DataBuff(zdc.Buffer):
        seg: zdc.u32 = zdc.rand()

    @zdc.dataclass
    class DmaChannel(zdc.Resource):
        priority: zdc.u4 = zdc.rand()

    @zdc.dataclass
    class WriteAction(zdc.Action[zdc.Component]):
        data: DataBuff = zdc.output()
        chan: DmaChannel = zdc.lock()
        size: zdc.u8 = zdc.rand()

    field_names = {f.name for f in dataclasses.fields(WriteAction)}
    assert {'data', 'chan', 'size'}.issubset(field_names)

    all_fields = {f.name: f for f in dataclasses.fields(WriteAction)}
    assert all_fields['chan'].metadata['claim'] == 'lock'


# ---------------------------------------------------------------------------
# bind() in activity body
# ---------------------------------------------------------------------------

def test_bind_in_activity():
    """bind(self.producer.data_out, self.consumer.data_in) → ActivityBind IR."""
    ir = _parse("""
        async def activity(self):
            await self.producer()
            await self.consumer()
            bind(self.producer.data_out, self.consumer.data_in)
    """)
    assert len(ir.stmts) == 3
    b = ir.stmts[2]
    assert isinstance(b, ActivityBind)
    assert b.src['attr'] == 'data_out'
    assert b.dst['attr'] == 'data_in'


def test_bind_multiple():
    """Multiple bind() calls in one activity."""
    ir = _parse("""
        async def activity(self):
            await self.wr()
            await self.rd()
            bind(self.wr.out_buf, self.rd.in_buf)
            bind(self.wr.out_state, self.rd.in_state)
    """)
    binds = [s for s in ir.stmts if isinstance(s, ActivityBind)]
    assert len(binds) == 2
    assert binds[0].src['attr'] == 'out_buf'
    assert binds[1].src['attr'] == 'out_state'


# ---------------------------------------------------------------------------
# Activity parsing with resource / buffer action fields present
# ---------------------------------------------------------------------------

def test_activity_with_resource_action():
    """Compound action with resource-using sub-actions parses correctly."""
    @zdc.dataclass
    class DmaChannel(zdc.Resource):
        priority: zdc.u4 = zdc.rand()

    @zdc.dataclass
    class DataBuff(zdc.Buffer):
        seg: zdc.u32 = zdc.rand()

    @zdc.dataclass
    class MyComp(zdc.Component):
        pass

    @zdc.dataclass
    class WriteData(zdc.Action[MyComp]):
        data: DataBuff = zdc.output()
        chan: DmaChannel = zdc.lock()
        size: zdc.u8 = zdc.rand()

        async def body(self):
            pass

    @zdc.dataclass
    class ReadData(zdc.Action[MyComp]):
        data: DataBuff = zdc.input()
        chan: DmaChannel = zdc.lock()

        async def body(self):
            pass

    @zdc.dataclass
    class DmaXfer(zdc.Action[MyComp]):
        wr: WriteData = zdc.field(default=None)
        rd: ReadData = zdc.field(default=None)

        async def activity(self):
            await self.wr()
            async with self.rd():
                self.rd.chan.priority > 5

    # Assert IR structure
    assert hasattr(DmaXfer, '__activity__')
    ir = DmaXfer.__activity__
    assert isinstance(ir, ActivitySequenceBlock)
    assert len(ir.stmts) == 2

    wr_t = ir.stmts[0]
    assert isinstance(wr_t, ActivityTraversal)
    assert wr_t.handle == 'wr'
    assert wr_t.inline_constraints == []

    rd_t = ir.stmts[1]
    assert isinstance(rd_t, ActivityTraversal)
    assert rd_t.handle == 'rd'
    assert len(rd_t.inline_constraints) == 1
    import ast
    assert isinstance(rd_t.inline_constraints[0], ast.Expr)
    assert isinstance(rd_t.inline_constraints[0].value.ops[0], ast.Gt)
