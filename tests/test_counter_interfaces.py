"""Phase 2 tests — Counter, ModuloCounter, WatchdogCounter interface dispatch.

Covers:
* Protocol membership (issubclass checks)
* elaborate_field() for all three counter types
* sv_module_text, rewrite_proc_stmts, SVA properties, bmc_depth, cutpoint_signals, c_header
* Registry registration via _register_standard_abstractions()
"""
from __future__ import annotations

import pytest

import zuspec.dataclasses as zdc
from zuspec.dataclasses.counter import Counter
from zuspec.dataclasses.modulo_counter import ModuloCounter
from zuspec.dataclasses.watchdog_counter import WatchdogCounter
from zuspec.dataclasses.counter_ir import CounterIR
from zuspec.ir.core.interfaces import (
    Lowerable,
    ElaboratableInterface,
    SVEmittableInterface,
    SVAEmittableInterface,
    CSimEmittableInterface,
)
from zuspec.ir.core.abstraction_field_ir import AbstractionFieldIR
from zuspec.ir.core.registry import global_registry


# ---------------------------------------------------------------------------
# Protocol membership
# ---------------------------------------------------------------------------

def test_counter_is_lowerable():
    assert issubclass(Counter, Lowerable)


def test_counter_is_elaboratable():
    assert issubclass(Counter, ElaboratableInterface)


def test_counter_is_sv_emittable():
    assert issubclass(Counter, SVEmittableInterface)


def test_counter_is_sva_emittable():
    assert issubclass(Counter, SVAEmittableInterface)


def test_counter_is_csim_emittable():
    assert issubclass(Counter, CSimEmittableInterface)


# ---------------------------------------------------------------------------
# elaborate_field — Counter
# ---------------------------------------------------------------------------

def test_elaborate_field_width_default():
    fir = Counter.elaborate_field("cnt", 0, {})
    assert fir.ir_node.width == 32
    assert fir.ir_node.period == 2 ** 32


def test_elaborate_field_width_explicit():
    fir = Counter.elaborate_field("cnt", 0, {"WIDTH": 8})
    assert fir.ir_node.width == 8
    assert fir.ir_node.period == 256


def test_elaborate_field_returns_abstraction_ir():
    fir = Counter.elaborate_field("cnt", 0, {})
    assert isinstance(fir, AbstractionFieldIR)
    assert fir.spec_type_name == "Counter"
    assert fir.field_name == "cnt"
    assert fir.field_index == 0
    assert fir.py_cls is Counter


def test_elaborate_field_ir_node_is_counter_ir():
    fir = Counter.elaborate_field("cnt", 2, {"WIDTH": 16})
    assert isinstance(fir.ir_node, CounterIR)
    assert fir.ir_node.is_free_running is True
    assert fir.field_index == 2


def test_elaborate_field_accepts_element_type_kwarg():
    # element_type=None is acceptable for non-generic abstractions
    fir = Counter.elaborate_field("c", 0, {}, element_type=None)
    assert fir is not None


# ---------------------------------------------------------------------------
# elaborate_field — ModuloCounter
# ---------------------------------------------------------------------------

def test_modulo_counter_reads_period():
    fir = ModuloCounter.elaborate_field("m", 0, {"PERIOD": 128})
    assert fir.ir_node.period == 128
    assert fir.ir_node.is_free_running is True


def test_modulo_counter_width_from_period():
    fir = ModuloCounter.elaborate_field("m", 0, {"PERIOD": 100})
    # 100 - 1 = 99 → 7 bits
    assert fir.ir_node.width == 7


def test_modulo_counter_default_period():
    fir = ModuloCounter.elaborate_field("m", 0, {})
    assert fir.ir_node.period == 256


def test_modulo_counter_spec_type_name():
    fir = ModuloCounter.elaborate_field("m", 0, {"PERIOD": 10})
    assert fir.spec_type_name == "ModuloCounter"


# ---------------------------------------------------------------------------
# elaborate_field — WatchdogCounter
# ---------------------------------------------------------------------------

def test_watchdog_counter_reads_timeout():
    fir = WatchdogCounter.elaborate_field("w", 0, {"TIMEOUT": 64})
    assert fir.ir_node.period == 64


def test_watchdog_counter_not_free_running():
    fir = WatchdogCounter.elaborate_field("w", 0, {"TIMEOUT": 100})
    assert fir.ir_node.is_free_running is False


def test_watchdog_counter_default_timeout():
    fir = WatchdogCounter.elaborate_field("w", 0, {})
    assert fir.ir_node.period == 1000


def test_watchdog_counter_spec_type_name():
    fir = WatchdogCounter.elaborate_field("w", 0, {})
    assert fir.spec_type_name == "WatchdogCounter"


# ---------------------------------------------------------------------------
# sv_module_text / sv_instance_text
# ---------------------------------------------------------------------------

def test_sv_module_text_empty():
    fir = Counter.elaborate_field("cnt", 0, {"WIDTH": 8})
    assert Counter.sv_module_text(fir) == ""


def test_sv_instance_text_empty():
    fir = Counter.elaborate_field("cnt", 0, {"WIDTH": 8})
    assert Counter.sv_instance_text(fir, "u_top") == ""


# ---------------------------------------------------------------------------
# SVA properties
# ---------------------------------------------------------------------------

def _fir(cls=Counter, name="cnt", idx=0, kwargs=None):
    return cls.elaborate_field(name, idx, kwargs or {})


def test_sva_assert_range_invariant_power_of_two():
    fir = Counter.elaborate_field("cnt", 0, {"WIDTH": 8})
    props = Counter.sva_assert_properties(fir)
    # WIDTH=8 → period=256 == 2**8; tautological comment, no assert property
    assert any("tautological" in p or "range_invariant" in p for p in props)
    # There must be no "assert property" for the range check
    range_asserts = [p for p in props if "assert property" in p and "256" in p]
    assert range_asserts == []


def test_sva_assert_range_invariant_non_power_of_two():
    fir = ModuloCounter.elaborate_field("cnt", 0, {"PERIOD": 200})
    props = ModuloCounter.sva_assert_properties(fir)
    assert any("200" in p and "assert property" in p for p in props)


def test_sva_assert_monotone_progress():
    fir = Counter.elaborate_field("cnt", 0, {"WIDTH": 4})
    props = Counter.sva_assert_properties(fir)
    combined = " ".join(props)
    assert "$past" in combined
    assert "15" in combined  # period - 1 for WIDTH=4 is 15


def test_sva_assume_contains_assume_keyword():
    fir = Counter.elaborate_field("cnt", 0, {"WIDTH": 4})
    props = Counter.sva_assume_properties(fir)
    combined = " ".join(props)
    assert "assume" in combined
    # Must NOT contain "assert property"
    assert "assert property" not in combined


# ---------------------------------------------------------------------------
# bmc_depth and cutpoint_signals
# ---------------------------------------------------------------------------

def test_bmc_depth_equals_period():
    fir = Counter.elaborate_field("cnt", 0, {"WIDTH": 8})
    assert Counter.bmc_depth(fir) == 256


def test_bmc_depth_modulo():
    fir = ModuloCounter.elaborate_field("m", 0, {"PERIOD": 868})
    assert ModuloCounter.bmc_depth(fir) == 868


def test_cutpoint_signals_returns_field_name():
    fir = Counter.elaborate_field("my_cnt", 0, {})
    assert Counter.cutpoint_signals(fir) == ["my_cnt"]


# ---------------------------------------------------------------------------
# c_header / c_impl
# ---------------------------------------------------------------------------

def test_c_header_contains_type_and_name():
    fir = Counter.elaborate_field("cnt", 0, {"WIDTH": 8})
    hdr = Counter.c_header(fir)
    assert "uint8_t" in hdr
    assert "cnt" in hdr


def test_c_header_width_32():
    fir = Counter.elaborate_field("free_cnt", 0, {})  # default WIDTH=32
    hdr = Counter.c_header(fir)
    assert "uint32_t" in hdr
    assert "free_cnt" in hdr


def test_c_impl_empty():
    fir = Counter.elaborate_field("cnt", 0, {})
    assert Counter.c_impl(fir) == ""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_counter_registered_in_global_registry():
    r = global_registry()
    assert r.get_sv_model(Counter) is not None


def test_modulo_counter_registered_in_global_registry():
    r = global_registry()
    assert r.get_sv_model(ModuloCounter) is not None


def test_watchdog_counter_registered_in_global_registry():
    r = global_registry()
    assert r.get_sv_model(WatchdogCounter) is not None


def test_counter_elab_model_in_registry():
    r = global_registry()
    assert r.get_elab_model(Counter) is not None
