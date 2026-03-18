"""Tests for Phase 5 — @zdc.extend decorator and ActivityParser caching."""
import textwrap
import unittest.mock as mock
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.activity_parser import ActivityParser, _parse_cache


# ---------------------------------------------------------------------------
# @zdc.extend — basic usage
# ---------------------------------------------------------------------------

def test_extend_marks_class():
    """@zdc.extend sets __is_extension__ and __extends__ on the class."""
    @zdc.dataclass
    class MyComp(zdc.Component):
        pass

    @zdc.dataclass
    class WriteData(zdc.Action[MyComp]):
        size: zdc.u8 = zdc.rand()

        async def body(self):
            pass

    @zdc.extend
    class WriteDataExt(WriteData):
        tag: zdc.u4 = zdc.rand()

    assert WriteDataExt.__is_extension__ is True
    assert WriteDataExt.__extends__ is WriteData


def test_extend_no_valid_base_raises():
    """@zdc.extend raises TypeError when the class has no zuspec base."""
    with pytest.raises(TypeError, match="must inherit from a zuspec dataclass"):
        @zdc.extend
        class Orphan:
            pass


def test_extend_with_call_syntax():
    """@zdc.extend() (called with parens) also works."""
    @zdc.dataclass
    class MyComp(zdc.Component):
        pass

    @zdc.dataclass
    class ReadData(zdc.Action[MyComp]):
        async def body(self):
            pass

    @zdc.extend()
    class ReadDataExt(ReadData):
        priority: zdc.u4 = zdc.rand()

    assert ReadDataExt.__is_extension__ is True
    assert ReadDataExt.__extends__ is ReadData


def test_extend_action_with_activity():
    """@zdc.extend on a compound (activity) action works."""
    @zdc.dataclass
    class MyComp(zdc.Component):
        pass

    @zdc.dataclass
    class WriteData(zdc.Action[MyComp]):
        async def body(self):
            pass

    @zdc.dataclass
    class ReadData(zdc.Action[MyComp]):
        async def body(self):
            pass

    @zdc.dataclass
    class DmaXfer(zdc.Action[MyComp]):
        wr: WriteData = zdc.field(default=None)
        rd: ReadData = zdc.field(default=None)

        async def activity(self):
            await self.wr()
            await self.rd()

    @zdc.extend
    class DmaXferExt(DmaXfer):
        count: zdc.u8 = zdc.rand()

    assert DmaXferExt.__is_extension__ is True
    assert DmaXferExt.__extends__ is DmaXfer


def test_extend_component():
    """@zdc.extend works on a Component subclass."""
    @zdc.dataclass
    class SysComp(zdc.Component):
        pass

    @zdc.extend
    class SysCompExt(SysComp):
        pass

    assert SysCompExt.__is_extension__ is True
    assert SysCompExt.__extends__ is SysComp


def test_extend_struct():
    """@zdc.extend works on a Struct subclass."""
    @zdc.dataclass
    class MemDesc(zdc.Struct):
        base: zdc.u32 = zdc.rand()

    @zdc.extend
    class MemDescExt(MemDesc):
        size: zdc.u32 = zdc.rand()

    assert MemDescExt.__is_extension__ is True


def test_extend_buffer():
    """@zdc.extend works on a Buffer subclass."""
    @zdc.dataclass
    class DataBuff(zdc.Buffer):
        seg: zdc.u32 = zdc.rand()

    @zdc.extend
    class DataBuffExt(DataBuff):
        tag: zdc.u4 = zdc.rand()

    assert DataBuffExt.__is_extension__ is True


def test_extend_multiple_extensions_same_base():
    """Multiple @zdc.extend classes can extend the same base independently."""
    @zdc.dataclass
    class MyComp(zdc.Component):
        pass

    @zdc.dataclass
    class BaseAction(zdc.Action[MyComp]):
        async def body(self):
            pass

    @zdc.extend
    class Ext1(BaseAction):
        x: zdc.u8 = zdc.rand()

    @zdc.extend
    class Ext2(BaseAction):
        y: zdc.u8 = zdc.rand()

    assert Ext1.__extends__ is BaseAction
    assert Ext2.__extends__ is BaseAction
    assert Ext1 is not Ext2


# ---------------------------------------------------------------------------
# ActivityParser caching
# ---------------------------------------------------------------------------

def test_parser_cache_hit():
    """Parsing the same source twice returns the same IR object (cache hit)."""
    src = textwrap.dedent("""
        async def activity(self):
            await self.wr()
            await self.rd()
    """)

    parser = ActivityParser()
    with mock.patch("inspect.getsource", return_value=src):
        ir1 = parser.parse(mock.MagicMock())
    with mock.patch("inspect.getsource", return_value=src):
        ir2 = parser.parse(mock.MagicMock())

    assert ir1 is ir2, "Cache should return the same object for identical source"


def test_parser_cache_miss_different_source():
    """Different source strings produce different IR objects."""
    src1 = textwrap.dedent("""
        async def activity(self):
            await self.wr()
    """)
    src2 = textwrap.dedent("""
        async def activity(self):
            await self.rd()
    """)

    parser = ActivityParser()
    with mock.patch("inspect.getsource", return_value=src1):
        ir1 = parser.parse(mock.MagicMock())
    with mock.patch("inspect.getsource", return_value=src2):
        ir2 = parser.parse(mock.MagicMock())

    assert ir1 is not ir2
    assert ir1.stmts[0].handle == 'wr'
    assert ir2.stmts[0].handle == 'rd'


def test_parser_cache_populated():
    """After a parse call the result appears in _parse_cache."""
    src = textwrap.dedent("""
        async def activity(self):
            await self.unique_handle_xyz()
    """)
    key = (hash(src), "", 1)
    _parse_cache.pop(key, None)  # ensure clean state

    parser = ActivityParser()
    with mock.patch("inspect.getsource", return_value=src):
        ir = parser.parse(mock.MagicMock())

    assert key in _parse_cache
    assert _parse_cache[key] is ir
