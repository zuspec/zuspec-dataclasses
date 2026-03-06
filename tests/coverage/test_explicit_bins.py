"""
Tests for explicit bin specifications (Phase 2).
"""
import pytest
import zuspec.dataclasses as zdc


def test_bins_dict_ranges():
    """Test dictionary bins with ranges."""
    
    @zdc.dataclass
    class Transaction:
        addr: zdc.uint8_t = zdc.field()
    
    @zdc.dataclass
    class TransactionCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        addr_cp: zdc.uint8_t = zdc.coverpoint(
            ref=lambda s: s.parent.addr,
            bins={'low': range(0, 64), 'mid': range(64, 128), 'high': range(128, 256)}
        )
    
    trans = Transaction()
    cov = TransactionCov(parent=trans)
    
    # Sample low
    trans.addr = 10
    cov.sample()
    assert cov.get_coverage() == pytest.approx(33.33, abs=0.1)
    
    # Sample high
    trans.addr = 200
    cov.sample()
    assert cov.get_coverage() == pytest.approx(66.66, abs=0.1)
    
    # Sample mid
    trans.addr = 100
    cov.sample()
    assert cov.get_coverage() == 100.0


def test_bins_dict_lists():
    """Test dictionary bins with lists of values."""
    
    @zdc.dataclass
    class Data:
        val: zdc.uint8_t = zdc.field()
    
    @zdc.dataclass
    class DataCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        val_cp: zdc.uint8_t = zdc.coverpoint(
            ref=lambda s: s.parent.val,
            bins={'special': [0, 1, 255], 'normal': [10, 20, 30]}
        )
    
    obj = Data()
    cov = DataCov(parent=obj)
    
    # Initially 0%
    assert cov.get_coverage() == 0.0
    
    # Sample special bin
    obj.val = 0
    cov.sample()
    assert cov.get_coverage() == 50.0
    
    # Sample normal bin
    obj.val = 20
    cov.sample()
    assert cov.get_coverage() == 100.0


def test_bins_dict_single_values():
    """Test dictionary bins with single values."""
    
    @zdc.dataclass
    class Simple:
        flag: zdc.uint8_t = zdc.field()
    
    @zdc.dataclass
    class SimpleCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        flag_cp: zdc.uint8_t = zdc.coverpoint(
            ref=lambda s: s.parent.flag,
            bins={'zero': 0, 'one': 1, 'max': 255}
        )
    
    obj = Simple()
    cov = SimpleCov(parent=obj)
    
    obj.flag = 0
    cov.sample()
    assert cov.get_coverage() == pytest.approx(33.33, abs=0.1)
    
    obj.flag = 1
    cov.sample()
    assert cov.get_coverage() == pytest.approx(66.66, abs=0.1)
    
    obj.flag = 255
    cov.sample()
    assert cov.get_coverage() == 100.0


def test_bins_list():
    """Test list-based bin specification (one bin per value)."""
    
    @zdc.dataclass
    class Data:
        val: zdc.uint8_t = zdc.field()
    
    @zdc.dataclass
    class DataCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        val_cp: zdc.uint8_t = zdc.coverpoint(
            ref=lambda s: s.parent.val,
            bins=[0, 1, 2, 3]  # Creates bins 'bin_0', 'bin_1', etc.
        )
    
    obj = Data()
    cov = DataCov(parent=obj)
    
    # Sample each value
    for i in range(4):
        obj.val = i
        cov.sample()
    
    # All bins hit
    assert cov.get_coverage() == 100.0


def test_mixed_bin_types():
    """Test mixing ranges and lists in bins dict."""
    
    @zdc.dataclass
    class Transaction:
        addr: zdc.uint8_t = zdc.field()
    
    @zdc.dataclass
    class TransactionCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        addr_cp: zdc.uint8_t = zdc.coverpoint(
            ref=lambda s: s.parent.addr,
            bins={
                'zero': 0,
                'special': [1, 2, 3],
                'normal': range(4, 100),
                'high': range(100, 256)
            }
        )
    
    trans = Transaction()
    cov = TransactionCov(parent=trans)
    
    # Sample each bin type
    trans.addr = 0
    cov.sample()
    assert cov.get_coverage() == 25.0
    
    trans.addr = 2
    cov.sample()
    assert cov.get_coverage() == 50.0
    
    trans.addr = 50
    cov.sample()
    assert cov.get_coverage() == 75.0
    
    trans.addr = 150
    cov.sample()
    assert cov.get_coverage() == 100.0


def test_multiple_coverpoints_explicit_bins():
    """Test multiple coverpoints with explicit bins."""
    
    @zdc.dataclass
    class Transaction:
        addr: zdc.uint8_t = zdc.field()
        data: zdc.uint8_t = zdc.field()
    
    @zdc.dataclass
    class TransactionCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        addr_cp: zdc.uint8_t = zdc.coverpoint(
            ref=lambda s: s.parent.addr,
            bins={'low': range(0, 128), 'high': range(128, 256)}
        )
        data_cp: zdc.uint8_t = zdc.coverpoint(
            ref=lambda s: s.parent.data,
            bins={'zero': 0, 'nonzero': range(1, 256)}
        )
    
    trans = Transaction()
    cov = TransactionCov(parent=trans)
    
    # Sample to hit all bins
    trans.addr = 10
    trans.data = 0
    cov.sample()
    
    trans.addr = 200
    trans.data = 50
    cov.sample()
    
    # Both coverpoints 100%
    assert cov.get_coverage() == 100.0


def test_overlapping_bins():
    """Test that first matching bin wins with overlapping ranges."""
    
    @zdc.dataclass
    class Data:
        val: zdc.uint8_t = zdc.field()
    
    @zdc.dataclass
    class DataCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        val_cp: zdc.uint8_t = zdc.coverpoint(
            ref=lambda s: s.parent.val,
            bins={'first': range(0, 100), 'second': range(50, 150)}
        )
    
    obj = Data()
    cov = DataCov(parent=obj)
    
    # Value 75 matches both bins, but should go to 'first' (defined first)
    obj.val = 75
    cov.sample()
    
    # Check that 'first' was hit
    assert cov._coverpoints['val_cp'].bins['first'].hit_count == 1
    assert cov._coverpoints['val_cp'].bins['second'].hit_count == 0


def test_no_matching_bin():
    """Test that values not in any bin don't affect coverage."""
    
    @zdc.dataclass
    class Data:
        val: zdc.uint8_t = zdc.field()
    
    @zdc.dataclass
    class DataCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        val_cp: zdc.uint8_t = zdc.coverpoint(
            ref=lambda s: s.parent.val,
            bins={'low': range(0, 10), 'high': range(90, 100)}
        )
    
    obj = Data()
    cov = DataCov(parent=obj)
    
    # Sample values not in any bin
    obj.val = 50
    cov.sample()
    assert cov.get_coverage() == 0.0
    
    # Sample value in bin
    obj.val = 5
    cov.sample()
    assert cov.get_coverage() == 50.0


def test_empty_bins_dict():
    """Test that empty bins dict falls back to auto-bins."""
    
    @zdc.dataclass
    class Data:
        val: zdc.uint8_t = zdc.field()
    
    @zdc.dataclass
    class DataCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        val_cp: zdc.uint8_t = zdc.coverpoint(
            ref=lambda s: s.parent.val,
            bins={}  # Empty dict -> auto-bins
        )
    
    obj = Data()
    cov = DataCov(parent=obj)
    
    obj.val = 42
    cov.sample()
    
    # Should behave like auto-bins
    assert cov.get_coverage() > 0.0


@pytest.mark.skip(reason="Bin guards - implement in Phase 2")
def test_bin_iff_guard():
    """Test bin-level iff guards."""
    
    @zdc.dataclass
    class Transaction:
        addr: zdc.uint8_t = zdc.field()
        valid: bool = zdc.field()
    
    @zdc.dataclass
    class TransactionCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        # Note: bin-level iff not yet implemented
        addr_cp: zdc.uint8_t = zdc.coverpoint(
            ref=lambda s: s.parent.addr,
            iff=lambda s: s.parent.valid,  # Coverpoint-level guard
            bins={'low': range(0, 128), 'high': range(128, 256)}
        )
    
    trans = Transaction()
    cov = TransactionCov(parent=trans)
    
    # Sample with valid=False - should not count
    trans.addr = 10
    trans.valid = False
    cov.sample()
    assert cov.get_coverage() == 0.0
    
    # Sample with valid=True - should count
    trans.valid = True
    cov.sample()
    assert cov.get_coverage() > 0.0


@pytest.mark.skip(reason="Ignore bins - implement in Phase 2")
def test_ignore_bins():
    """Test ignore_bins to exclude values from coverage."""
    pass


@pytest.mark.skip(reason="Illegal bins - implement in Phase 2")
def test_illegal_bins():
    """Test illegal_bins for error detection."""
    pass
