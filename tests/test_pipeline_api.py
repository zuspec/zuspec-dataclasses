#****************************************************************************
# Copyright 2019-2026 Matthew Ballance and contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#****************************************************************************
"""Unit tests for the new @zdc.pipeline / @zdc.stage / @zdc.sync API.

Covers:
- PipelineError
- _StageDSL: @zdc.stage bare and parametric, DSL meta-methods
- @zdc.pipeline decorator — metadata attributes on the method
- @zdc.sync decorator — string clock/reset
"""

import pytest
import sys
import os

_this_dir = os.path.dirname(__file__)
_dc_src = os.path.join(_this_dir, "..", "src")
if "" in sys.path:
    sys.path.insert(1, _dc_src)
else:
    sys.path.insert(0, _dc_src)

import zuspec.dataclasses as zdc
from zuspec.dataclasses.decorators import (
    PipelineError,
    _StageDSL,
    ExecSync,
)


# ---------------------------------------------------------------------------
# PipelineError
# ---------------------------------------------------------------------------

class TestPipelineError:
    def test_is_exception(self):
        err = PipelineError("boom")
        assert isinstance(err, Exception)
        assert "boom" in str(err)


# ---------------------------------------------------------------------------
# _StageDSL singleton
# ---------------------------------------------------------------------------

class TestStageDSL:
    def test_singleton_is_instance(self):
        assert isinstance(zdc.stage, _StageDSL)

    def test_bare_decorator(self):
        @zdc.stage
        def IF(self):
            pass

        assert getattr(IF, "_zdc_stage", False) is True
        assert getattr(IF, "_zdc_stage_no_forward", None) is False

    def test_parametric_decorator_no_forward(self):
        @zdc.stage(no_forward=True)
        def MEM(self):
            pass

        assert getattr(MEM, "_zdc_stage", False) is True
        assert getattr(MEM, "_zdc_stage_no_forward", None) is True

    def test_parametric_decorator_default_forward(self):
        @zdc.stage(no_forward=False)
        def EX(self):
            pass

        assert getattr(EX, "_zdc_stage_no_forward", None) is False

    def test_stall_is_noop(self):
        result = zdc.stage.stall(True)
        assert result is None

    def test_cancel_is_noop(self):
        result = zdc.stage.cancel()
        assert result is None

    def test_flush_is_noop(self):
        result = zdc.stage.flush(None)
        assert result is None

    def test_valid_returns_false(self):
        assert zdc.stage.valid(None) is False

    def test_ready_returns_true(self):
        assert zdc.stage.ready(None) is True

    def test_stalled_returns_false(self):
        assert zdc.stage.stalled(None) is False


# ---------------------------------------------------------------------------
# @zdc.pipeline decorator
# ---------------------------------------------------------------------------

class TestPipelineDecorator:
    def _make_component(self, clock="clk", reset="rst_n", forward=True,
                        no_forward=None):
        class Alu:
            @zdc.stage
            def S1(self) -> int:
                return 0

            @zdc.stage
            def S2(self, x: int):
                pass

            @zdc.pipeline(clock=clock, reset=reset, forward=forward,
                          no_forward=no_forward)
            def execute(self):
                x = self.S1()
                self.S2(x)

        return Alu

    def test_metadata_present(self):
        Alu = self._make_component()
        m = Alu.execute
        assert getattr(m, "_zdc_pipeline", False) is True

    def test_clock_reset_stored_as_strings(self):
        Alu = self._make_component(clock="my_clk", reset="my_rst")
        m = Alu.execute
        assert m._zdc_pipeline_clock == "my_clk"
        assert m._zdc_pipeline_reset == "my_rst"

    def test_forward_default_true(self):
        Alu = self._make_component()
        assert Alu.execute._zdc_pipeline_forward is True

    def test_forward_false(self):
        Alu = self._make_component(forward=False)
        assert Alu.execute._zdc_pipeline_forward is False

    def test_no_forward_list_default_empty(self):
        Alu = self._make_component()
        assert Alu.execute._zdc_pipeline_no_forward == []

    def test_no_forward_list_stored(self):
        Alu = self._make_component(no_forward=["tag"])
        assert Alu.execute._zdc_pipeline_no_forward == ["tag"]

    def test_decorated_method_still_callable(self):
        Alu = self._make_component()
        # Pipeline root body runs without error at runtime
        alu = Alu()
        Alu.execute(alu)


# ---------------------------------------------------------------------------
# @zdc.sync decorator
# ---------------------------------------------------------------------------

class TestSyncDecorator:
    def test_sync_stores_string_clock_reset(self):
        class Ctr:
            @zdc.sync(clock="clk", reset="rst_n")
            def _count(self):
                pass

        es = Ctr._count
        assert isinstance(es, ExecSync)
        assert es.clock == "clk"
        assert es.reset == "rst_n"

    def test_sync_default_none(self):
        class Ctr:
            @zdc.sync()
            def _count(self):
                pass

        es = Ctr._count
        assert isinstance(es, ExecSync)
        assert es.clock is None
        assert es.reset is None

