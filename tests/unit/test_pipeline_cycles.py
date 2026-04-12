"""Unit tests for pipeline cycles=N support (Form A decorator, Form B context manager)."""
from __future__ import annotations

import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.ir.pipeline import StageCallNode, StageMethodIR


# ---------------------------------------------------------------------------
# Helper: build a minimal DataModelFactory and invoke parse helpers
# ---------------------------------------------------------------------------

def _make_factory():
    from zuspec.dataclasses.data_model_factory import DataModelFactory
    return DataModelFactory()


# ---------------------------------------------------------------------------
# Form A — @zdc.stage(cycles=N) decorator
# ---------------------------------------------------------------------------

class TestDecoratorCycles:
    def test_bare_stage_default_cycles(self):
        """@zdc.stage bare form → _zdc_stage_cycles == 1."""
        @zdc.stage
        def IF(self) -> (zdc.u32,):
            ...

        assert getattr(IF, '_zdc_stage_cycles', 1) == 1

    def test_decorator_cycles_sets_attribute(self):
        """@zdc.stage(cycles=2) → _zdc_stage_cycles == 2."""
        @zdc.stage(cycles=2)
        def EX(self, insn: zdc.u32) -> (zdc.u32,):
            ...

        assert EX._zdc_stage_cycles == 2

    def test_decorator_cycles_zero_raises(self):
        """@zdc.stage(cycles=0) → ValueError."""
        with pytest.raises(ValueError, match="cycles must be >= 1"):
            @zdc.stage(cycles=0)
            def BAD(self): ...

    def test_decorator_cycles_negative_raises(self):
        """@zdc.stage(cycles=-1) → ValueError."""
        with pytest.raises(ValueError, match="cycles must be >= 1"):
            @zdc.stage(cycles=-1)
            def BAD(self): ...

    def test_parse_stage_method_cycles_stored(self):
        """_parse_stage_method stores decorator cycles in StageMethodIR."""
        @zdc.stage(cycles=3)
        def MEM(self, addr: zdc.u32) -> (zdc.u32,):
            ...

        factory = _make_factory()
        smir = factory._parse_stage_method('MEM', MEM)
        assert isinstance(smir, StageMethodIR)
        assert smir.cycles == 3

    def test_parse_stage_method_default_cycles(self):
        """Bare @zdc.stage → StageMethodIR.cycles == 1."""
        @zdc.stage
        def WB(self, result: zdc.u32) -> ():
            ...

        factory = _make_factory()
        smir = factory._parse_stage_method('WB', WB)
        assert smir.cycles == 1


# ---------------------------------------------------------------------------
# Form B — with zdc.stage.cycles(N): context manager
# ---------------------------------------------------------------------------

class TestContextManagerParsing:
    def _parse_root(self, method):
        factory = _make_factory()
        return factory._parse_pipeline_root(method)

    def test_default_cycles_no_cm(self):
        """Without a with-block the StageCallNode.cycles stays at 1."""
        @zdc.pipeline(clock='clk', reset='rst_n')
        def execute(self):
            (insn,) = self.IF()
            (result,) = self.EX(insn)
            self.WB(result)

        root = self._parse_root(execute)
        assert len(root.stage_calls) == 3
        for call in root.stage_calls:
            assert call.cycles == 1

    def test_context_manager_sets_cycles(self):
        """with zdc.stage.cycles(2): → StageCallNode.cycles == 2."""
        @zdc.pipeline(clock='clk', reset='rst_n')
        def execute(self):
            (insn,) = self.IF()
            with zdc.stage.cycles(2):
                (result,) = self.EX(insn)
            self.WB(result)

        root = self._parse_root(execute)
        assert len(root.stage_calls) == 3
        assert root.stage_calls[0].cycles == 1   # IF
        assert root.stage_calls[1].cycles == 2   # EX
        assert root.stage_calls[2].cycles == 1   # WB

    def test_context_manager_three_cycles(self):
        """with zdc.stage.cycles(3): → StageCallNode.cycles == 3."""
        @zdc.pipeline(clock='clk', reset='rst_n')
        def execute(self):
            (insn,) = self.IF()
            with zdc.stage.cycles(3):
                (result,) = self.EX(insn)
            self.WB(result)

        root = self._parse_root(execute)
        assert root.stage_calls[1].stage_name == 'EX'
        assert root.stage_calls[1].cycles == 3

    def test_cm_covers_multiple_stage_calls(self):
        """Two stage calls inside one with-block both get the cycles value."""
        @zdc.pipeline(clock='clk', reset='rst_n')
        def execute(self):
            (a,) = self.IF()
            with zdc.stage.cycles(2):
                (b,) = self.EX(a)
                (c,) = self.MEM(b)
            self.WB(c)

        root = self._parse_root(execute)
        names = [c.stage_name for c in root.stage_calls]
        assert names == ['IF', 'EX', 'MEM', 'WB']
        assert root.stage_calls[1].cycles == 2   # EX
        assert root.stage_calls[2].cycles == 2   # MEM

    def test_context_manager_runtime_no_op(self):
        """zdc.stage.cycles(N) is a no-op context manager at runtime."""
        with zdc.stage.cycles(5):
            pass  # should not raise

    def test_context_manager_zero_raises(self):
        """zdc.stage.cycles(0) raises ValueError."""
        with pytest.raises(ValueError, match="n must be >= 1"):
            with zdc.stage.cycles(0):
                pass


# ---------------------------------------------------------------------------
# StageCallNode.cycles field default
# ---------------------------------------------------------------------------

class TestStageCallNodeCycles:
    def test_default_cycles_field(self):
        """StageCallNode.cycles defaults to 1."""
        node = StageCallNode(stage_name='IF')
        assert node.cycles == 1

    def test_explicit_cycles_field(self):
        """StageCallNode can be constructed with cycles > 1."""
        node = StageCallNode(stage_name='EX', cycles=4)
        assert node.cycles == 4
