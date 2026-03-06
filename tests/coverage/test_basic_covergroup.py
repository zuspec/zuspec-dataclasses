"""
Tests for basic covergroup functionality (Phase 1).
"""
import pytest
from dataclasses import dataclass
from enum import IntEnum
import zuspec.dataclasses as zdc


class Status(IntEnum):
    IDLE = 0
    BUSY = 1
    ERROR = 2


def test_basic_covergroup():
    """Test basic covergroup with single coverpoint."""
    
    @zdc.dataclass
    class Transaction:
        addr: zdc.uint8_t = zdc.field()
    
    @zdc.dataclass
    class TransactionCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        addr_cp: zdc.uint8_t = zdc.coverpoint(ref=lambda s: s.parent.addr)
    
    # Create transaction and covergroup
    trans = Transaction()
    trans.addr = 10
    cov_inst = TransactionCov(parent=trans)
    
    # Sample
    cov_inst.sample()
    
    # Verify coverpoint was hit
    assert hasattr(cov_inst, '_coverpoints')
    assert 'addr_cp' in cov_inst._coverpoints
    # Coverage should be > 0 after sampling
    assert cov_inst.get_coverage() > 0.0


def test_multiple_coverpoints():
    """Test covergroup with multiple coverpoints."""
    
    @zdc.dataclass
    class Transaction:
        addr: zdc.uint8_t = zdc.field()
        data: zdc.uint8_t = zdc.field()
    
    @zdc.dataclass
    class TransactionCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        addr_cp: zdc.uint8_t = zdc.coverpoint(ref=lambda s: s.parent.addr)
        data_cp: zdc.uint8_t = zdc.coverpoint(ref=lambda s: s.parent.data)
    
    trans = Transaction()
    trans.addr = 5
    trans.data = 10
    cov_inst = TransactionCov(parent=trans)
    
    cov_inst.sample()
    
    # Both coverpoints should have some coverage
    assert cov_inst.get_coverage() > 0.0


def test_sample_basic():
    """Test that sampling updates hit counts."""
    
    @zdc.dataclass
    class Simple:
        value: zdc.uint8_t = zdc.field()
    
    @zdc.dataclass
    class SimpleCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        val_cp: zdc.uint8_t = zdc.coverpoint(ref=lambda s: s.parent.value)
    
    obj = Simple()
    obj.value = 42
    cov_inst = SimpleCov(parent=obj)
    
    # First sample
    cov_inst.sample()
    coverage_1 = cov_inst.get_coverage()
    
    # Same value again - coverage shouldn't change (already at 100% for single bin)
    cov_inst.sample()
    coverage_2 = cov_inst.get_coverage()
    
    assert coverage_2 == coverage_1


def test_get_coverage():
    """Test coverage percentage calculation."""
    
    @zdc.dataclass
    class Data:
        value: zdc.uint8_t = zdc.field()
    
    @zdc.dataclass
    class DataCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        val_cp: zdc.uint8_t = zdc.coverpoint(ref=lambda s: s.parent.value)
    
    obj = Data()
    cov_inst = DataCov(parent=obj)
    
    # Initially 0%
    assert cov_inst.get_coverage() == 0.0
    
    # After sampling, should be 100% (single auto bin)
    obj.value = 42
    cov_inst.sample()
    
    coverage = cov_inst.get_coverage()
    assert coverage == 100.0, f"Expected 100%, got {coverage}%"


def test_start_stop():
    """Test start/stop control."""
    
    @zdc.dataclass
    class Transaction:
        value: zdc.uint8_t = zdc.field()
    
    @zdc.dataclass
    class TransactionCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        val_cp: zdc.uint8_t = zdc.coverpoint(ref=lambda s: s.parent.value)
    
    trans = Transaction()
    trans.value = 10
    cov_inst = TransactionCov(parent=trans)
    
    # Stop before sampling
    cov_inst.stop()
    cov_inst.sample()
    
    # Coverage should be 0 (sampling disabled)
    assert cov_inst.get_coverage() == 0.0
    
    # Start and sample
    cov_inst.start()
    cov_inst.sample()
    
    # Now should have coverage
    assert cov_inst.get_coverage() > 0.0


def test_coverpoint_ref_lambda():
    """Test coverpoint ref lambda resolution."""
    
    @zdc.dataclass
    class Outer:
        inner_val: zdc.uint8_t = zdc.field()
    
    @zdc.dataclass
    class OuterCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        cp: zdc.uint8_t = zdc.coverpoint(ref=lambda s: s.parent.inner_val)
    
    obj = Outer()
    obj.inner_val = 99
    cov_inst = OuterCov(parent=obj)
    
    cov_inst.sample()
    
    # Should have sampled value 99
    assert cov_inst.get_coverage() > 0.0


def test_coverpoint_options():
    """Test coverpoint weight and goal options."""
    
    @zdc.dataclass
    class Transaction:
        addr: zdc.uint8_t = zdc.field()
    
    @zdc.dataclass
    class TransactionCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        addr_cp: zdc.uint8_t = zdc.coverpoint(
            ref=lambda s: s.parent.addr,
            weight=2,
            goal=90
        )
    
    trans = Transaction()
    trans.addr = 10
    cov_inst = TransactionCov(parent=trans)
    
    cov_inst.sample()
    
    # Should work with options
    assert cov_inst.get_coverage() >= 0.0
    # Verify weight is set
    assert cov_inst._coverpoints['addr_cp'].weight == 2
    assert cov_inst._coverpoints['addr_cp'].goal == 90


def test_auto_bins_enum():
    """Test auto-bin generation for enum types."""
    
    @zdc.dataclass
    class Packet:
        status: int = zdc.field()
    
    @zdc.dataclass
    class PacketCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        status_cp: int = zdc.coverpoint(ref=lambda s: s.parent.status)
    
    pkt = Packet()
    cov_inst = PacketCov(parent=pkt)
    
    # Sample each enum value
    for status_val in Status:
        pkt.status = status_val
        cov_inst.sample()
    
    # All enum values sampled → 100% coverage
    coverage = cov_inst.get_coverage()
    assert coverage == 100.0, f"Expected 100%, got {coverage}%"


@pytest.mark.skip(reason="Embedded covergroup - defer to later phase")
def test_embedded_covergroup():
    """Test covergroup embedded in struct."""
    
    @zdc.dataclass
    class Packet:
        addr: zdc.uint8_t = zdc.field()
        data: zdc.uint8_t = zdc.field()
    
    @zdc.dataclass
    class PacketCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        addr_cp: zdc.uint8_t = zdc.coverpoint(ref=lambda s: s.parent.addr)
        data_cp: zdc.uint8_t = zdc.coverpoint(ref=lambda s: s.parent.data)
    
    pkt = Packet()
    cov = PacketCov(parent=pkt)
    
    pkt.addr = 100
    pkt.data = 200
    cov.sample()
    
    assert cov.get_coverage() > 0.0


@pytest.mark.skip(reason="Auto-bins integral - need range-based binning")
def test_auto_bins_integral():
    """Test auto-bin generation for integral types with limited range."""
    
    @zdc.dataclass
    class Data:
        small_val: zdc.uint8_t = zdc.field()
    
    @zdc.dataclass
    class DataCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        val_cp: zdc.uint8_t = zdc.coverpoint(
            ref=lambda s: s.parent.small_val,
            auto_bin_max=16
        )
    
    obj = Data()
    cov_inst = DataCov(parent=obj)
    
    # Sample all 16 values
    for val in range(16):
        obj.small_val = val
        cov_inst.sample()
    
    # Should have 100% coverage
    assert cov_inst.get_coverage() == 100.0
