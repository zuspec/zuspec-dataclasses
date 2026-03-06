"""
Phase 3 Tests: Cross Coverage

Tests cross-product coverage of multiple coverpoints.
"""
import pytest
from enum import IntEnum
from zuspec import dataclasses as zdc


class Opcode(IntEnum):
    READ = 0
    WRITE = 1
    COMPARE = 2
    DELETE = 3


def test_basic_two_way_cross():
    """Test simple cross of two coverpoints."""
    @zdc.dataclass
    class Transaction:
        addr: zdc.uint8_t = zdc.rand(domain=(0, 255))
        data: zdc.uint8_t = zdc.rand(domain=(0, 255))
    
    @zdc.dataclass
    class TransactionCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        
        addr_cp: zdc.uint8_t = zdc.coverpoint(
            ref=lambda s: s.parent.addr,
            bins={'low': range(0, 128), 'high': range(128, 256)}
        )
        
        data_cp: zdc.uint8_t = zdc.coverpoint(
            ref=lambda s: s.parent.data,
            bins={'even': [0, 2, 4, 6], 'odd': [1, 3, 5, 7]}
        )
        
        # Cross coverage: addr x data
        addr_data_cross = zdc.cross(
            lambda s: s.addr_cp,
            lambda s: s.data_cp
        )
    
    t = Transaction(addr=50, data=2)
    cov = TransactionCov(parent=t)
    cov.start()
    
    # Sample: addr=50 (low), data=2 (even) -> (low, even)
    cov.sample()
    
    # Should have 1 of 4 cross bins hit: (low,even), (low,odd), (high,even), (high,odd)
    cross = cov.addr_data_cross
    assert cross is not None
    assert cross.get_total_bins() == 4
    assert cross.get_hit_bins() == 1
    
    # Sample more combinations
    t.addr, t.data = 200, 3  # (high, odd)
    cov.sample()
    assert cross.get_hit_bins() == 2
    
    t.addr, t.data = 50, 5  # (low, odd)
    cov.sample()
    assert cross.get_hit_bins() == 3
    
    t.addr, t.data = 150, 4  # (high, even)
    cov.sample()
    assert cross.get_hit_bins() == 4
    
    # All bins covered
    coverage = cross.get_coverage()
    assert coverage == 100.0


def test_three_way_cross():
    """Test cross of three coverpoints."""
    @zdc.dataclass
    class Command:
        opcode: int = zdc.rand(domain=(0, 3))
        size: int = zdc.rand(domain=(1, 8))
        priority: int = zdc.rand(domain=(0, 1))
    
    @zdc.dataclass
    class CommandCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        
        op_cp: int = zdc.coverpoint(
            ref=lambda s: s.parent.opcode,
            bins={'read': [0], 'write': [1]}
        )
        
        size_cp: int = zdc.coverpoint(
            ref=lambda s: s.parent.size,
            bins={'small': range(1, 4), 'large': range(4, 9)}
        )
        
        pri_cp: int = zdc.coverpoint(
            ref=lambda s: s.parent.priority,
            bins={'low': [0], 'high': [1]}
        )
        
        # 3-way cross: 2 * 2 * 2 = 8 bins
        three_way = zdc.cross(
            lambda s: s.op_cp,
            lambda s: s.size_cp,
            lambda s: s.pri_cp
        )
    
    cmd = Command(opcode=0, size=2, priority=0)
    cov = CommandCov(parent=cmd)
    cov.start()
    
    # Sample: (read, small, low)
    cov.sample()
    cross = cov.three_way
    assert cross.get_total_bins() == 8
    assert cross.get_hit_bins() == 1
    
    # Coverage: 1/8 = 12.5%
    assert cross.get_coverage() == 12.5


def test_cross_auto_bins():
    """Test automatic cross-product bin generation with enum."""
    @zdc.dataclass
    class Packet:
        op: int = 0
        status: int = 0
    
    @zdc.dataclass
    class PacketCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        
        # Enum auto-binning: creates bins for each enum value
        op_cp: int = zdc.coverpoint(ref=lambda s: Opcode(s.parent.op))
        
        status_cp: int = zdc.coverpoint(
            ref=lambda s: s.parent.status,
            bins=[0, 1]  # Two explicit bins
        )
        
        # Cross with auto bins from op_cp
        op_status_cross = zdc.cross(
            lambda s: s.op_cp,
            lambda s: s.status_cp
        )
    
    pkt = Packet(op=int(Opcode.READ), status=0)
    cov = PacketCov(parent=pkt)
    cov.start()
    
    # First sample triggers auto-bin generation
    cov.sample()
    
    # Should have 4 enum values * 2 status bins = 8 cross bins
    cross = cov.op_status_cross
    assert cross.get_total_bins() == 8
    assert cross.get_hit_bins() == 1


def test_cross_with_iff():
    """Test cross with guard condition."""
    @zdc.dataclass
    class Transaction:
        valid: bool = True
        addr: int = 0
        data: int = 0
    
    @zdc.dataclass
    class TransactionCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        
        addr_cp: int = zdc.coverpoint(
            ref=lambda s: s.parent.addr,
            bins={'low': [0, 1], 'high': [2, 3]}
        )
        
        data_cp: int = zdc.coverpoint(
            ref=lambda s: s.parent.data,
            bins=[0, 1]
        )
        
        # Cross only samples when valid=True
        valid_cross = zdc.cross(
            lambda s: s.addr_cp,
            lambda s: s.data_cp,
            iff=lambda s: s.parent.valid
        )
    
    t = Transaction(valid=True, addr=0, data=0)
    cov = TransactionCov(parent=t)
    cov.start()
    
    # Sample with valid=True -> should hit
    cov.sample()
    cross = cov.valid_cross
    assert cross.get_hit_bins() == 1
    
    # Sample with valid=False -> should not hit
    t.valid = False
    t.addr, t.data = 2, 1
    cov.sample()
    assert cross.get_hit_bins() == 1  # Still 1, didn't sample
    
    # Sample with valid=True again -> should hit
    t.valid = True
    cov.sample()
    assert cross.get_hit_bins() == 2  # Now 2


def test_binsof_single():
    """Test binsof() to select all bins from a coverpoint."""
    from zuspec.dataclasses.coverage.bins import binsof
    
    @zdc.dataclass
    class Transaction:
        addr: int = 0
        data: int = 0
    
    @zdc.dataclass
    class TransactionCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        
        addr_cp: int = zdc.coverpoint(
            ref=lambda s: s.parent.addr,
            bins={'low': [0, 1], 'high': [2, 3]}
        )
        
        data_cp: int = zdc.coverpoint(
            ref=lambda s: s.parent.data,
            bins=[0, 1, 2]
        )
        
        # Cross with binsof selecting all addr_cp bins
        addr_all_cross = zdc.cross(
            lambda s: s.addr_cp,
            lambda s: s.data_cp,
            bins=[
                zdc.cross_bins('addr_low_data',
                               binsof(lambda s: s.addr_cp) &
                               binsof(lambda s: s.data_cp))
            ]
        )
    
    t = Transaction(addr=0, data=0)
    cov = TransactionCov(parent=t)
    cov.start()
    cov.sample()
    
    # Should have explicit bins from cross_bins spec
    cross = cov.addr_all_cross
    assert cross is not None


def test_binsof_with_bin_name():
    """Test binsof() with specific bin name."""
    from zuspec.dataclasses.coverage.bins import binsof
    
    @zdc.dataclass
    class Transaction:
        addr: int = 0
        data: int = 0
    
    @zdc.dataclass
    class TransactionCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        
        addr_cp: int = zdc.coverpoint(
            ref=lambda s: s.parent.addr,
            bins={'low': [0, 1], 'mid': [2, 3], 'high': [4, 5]}
        )
        
        data_cp: int = zdc.coverpoint(
            ref=lambda s: s.parent.data,
            bins={'zero': [0], 'one': [1]}
        )
        
        # Cross only 'low' addr with all data
        low_addr_cross = zdc.cross(
            lambda s: s.addr_cp,
            lambda s: s.data_cp,
            bins=[
                zdc.cross_bins('low_data',
                               binsof(lambda s: s.addr_cp, 'low') &
                               binsof(lambda s: s.data_cp))
            ]
        )
    
    t = Transaction(addr=0, data=0)
    cov = TransactionCov(parent=t)
    cov.start()
    cov.sample()
    
    cross = cov.low_addr_cross
    assert cross is not None
    # Explicit cross bins will be implemented in next step


def test_binsof_intersect():
    """Test binsof().intersect() to filter values."""
    from zuspec.dataclasses.coverage.bins import binsof
    
    @zdc.dataclass
    class Transaction:
        addr: int = 0
    
    @zdc.dataclass
    class TransactionCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        
        addr_cp: int = zdc.coverpoint(
            ref=lambda s: s.parent.addr,
            bins={'low': range(0, 64), 'mid': range(64, 128), 'high': range(128, 256)}
        )
        
        data_cp: int = zdc.coverpoint(
            ref=lambda s: 0,  # Dummy
            bins=[0]
        )
    
    # Test intersect evaluation
    t = Transaction(addr=50)
    cov = TransactionCov(parent=t)
    cov.start()
    cov.sample()
    
    # Create a binsof with intersect
    expr = binsof(lambda s: s.addr_cp).intersect(range(0, 100))
    
    # Create context for evaluation
    context = type('Context', (), {})()
    context.addr_cp = cov.addr_cp
    
    # Should return bins that intersect with range(0, 100): 'low' and 'mid'
    result = expr.evaluate(context)
    assert 'low' in result
    assert 'mid' in result
    assert 'high' not in result


def test_binsof_and():
    """Test binsof() & binsof() for explicit cross bins."""
    from zuspec.dataclasses.coverage.bins import binsof
    
    @zdc.dataclass
    class Transaction:
        addr: int = 0
        data: int = 0
    
    @zdc.dataclass
    class TransactionCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        
        addr_cp: int = zdc.coverpoint(
            ref=lambda s: s.parent.addr,
            bins={'low': [0, 1], 'high': [2, 3]}
        )
        
        data_cp: int = zdc.coverpoint(
            ref=lambda s: s.parent.data,
            bins={'even': [0, 2], 'odd': [1, 3]}
        )
    
    # Test AND expression evaluation
    t = Transaction(addr=0, data=0)
    cov = TransactionCov(parent=t)
    cov.start()
    cov.sample()
    
    # Create an AND expression
    expr = binsof(lambda s: s.addr_cp, 'low') & binsof(lambda s: s.data_cp, 'even')
    
    # Create context
    context = type('Context', (), {})()
    context.addr_cp = cov.addr_cp
    context.data_cp = cov.data_cp
    
    # Should return tuple of bin lists
    result = expr.evaluate(context)
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert 'low' in result[0]
    assert 'even' in result[1]


def test_binsof_or():
    """Test binsof() | binsof() for union of cross bins."""
    from zuspec.dataclasses.coverage.bins import binsof
    
    @zdc.dataclass
    class Transaction:
        addr: int = 0
    
    @zdc.dataclass
    class TransactionCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        
        addr_cp: int = zdc.coverpoint(
            ref=lambda s: s.parent.addr,
            bins={'low': [0, 1], 'mid': [2, 3], 'high': [4, 5]}
        )
        
        data_cp: int = zdc.coverpoint(
            ref=lambda s: 0,  # Dummy
            bins=[0]
        )
    
    # Test OR expression
    t = Transaction(addr=0)
    cov = TransactionCov(parent=t)
    cov.start()
    cov.sample()
    
    # Create OR expression
    expr = binsof(lambda s: s.addr_cp, 'low') | binsof(lambda s: s.addr_cp, 'high')
    
    # Create context
    context = type('Context', (), {})()
    context.addr_cp = cov.addr_cp
    
    # Should return union of bins
    result = expr.evaluate(context)
    assert 'low' in result
    assert 'high' in result
    assert 'mid' not in result


def test_binsof_not():
    """Test ~binsof() to exclude bins from cross."""
    from zuspec.dataclasses.coverage.bins import binsof
    
    @zdc.dataclass
    class Transaction:
        addr: int = 0
    
    @zdc.dataclass
    class TransactionCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        
        addr_cp: int = zdc.coverpoint(
            ref=lambda s: s.parent.addr,
            bins={'low': [0, 1], 'mid': [2, 3], 'high': [4, 5]}
        )
        
        data_cp: int = zdc.coverpoint(
            ref=lambda s: 0,  # Dummy
            bins=[0]
        )
    
    # Test NOT expression
    t = Transaction(addr=0)
    cov = TransactionCov(parent=t)
    cov.start()
    cov.sample()
    
    # Create NOT expression
    expr = ~binsof(lambda s: s.addr_cp, 'mid')
    
    # Create context
    context = type('Context', (), {})()
    context.addr_cp = cov.addr_cp
    
    # Should return all bins except 'mid'
    result = expr.evaluate(context)
    assert 'low' in result
    assert 'high' in result
    assert 'mid' not in result


def test_cross_bins_explicit():
    """Test cross_bins() helper for explicit cross bin specs."""
    @zdc.dataclass
    class Transaction:
        addr: int = 0
        data: int = 0
    
    @zdc.dataclass
    class TransactionCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        
        addr_cp: int = zdc.coverpoint(
            ref=lambda s: s.parent.addr,
            bins={'low': [0, 1], 'high': [2, 3]}
        )
        
        data_cp: int = zdc.coverpoint(
            ref=lambda s: s.parent.data,
            bins={'even': [0, 2], 'odd': [1, 3]}
        )
        
        # Explicit cross bins using binsof
        explicit_cross = zdc.cross(
            lambda s: s.addr_cp,
            lambda s: s.data_cp,
            bins=[
                zdc.cross_bins('low_even',
                               zdc.binsof(lambda s: s.addr_cp, 'low') &
                               zdc.binsof(lambda s: s.data_cp, 'even')),
                zdc.cross_bins('high_odd',
                               zdc.binsof(lambda s: s.addr_cp, 'high') &
                               zdc.binsof(lambda s: s.data_cp, 'odd'))
            ]
        )
    
    t = Transaction(addr=0, data=0)
    cov = TransactionCov(parent=t)
    cov.start()
    
    # Sample low_even (addr=0, data=0)
    cov.sample()
    cross = cov.explicit_cross
    
    # Should have only 2 explicit bins
    assert cross.get_total_bins() == 2
    assert cross.get_hit_bins() == 1
    
    # Sample high_odd (addr=3, data=3)
    t.addr, t.data = 3, 3
    cov.sample()
    assert cross.get_hit_bins() == 2
    assert cross.get_coverage() == 100.0


def test_cross_ignore():
    """Test cross_ignore() to exclude cross bins."""
    @zdc.dataclass
    class Transaction:
        addr: int = 0
        data: int = 0
    
    @zdc.dataclass
    class TransactionCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        
        addr_cp: int = zdc.coverpoint(
            ref=lambda s: s.parent.addr,
            bins={'low': [0, 1], 'high': [2, 3]}
        )
        
        data_cp: int = zdc.coverpoint(
            ref=lambda s: s.parent.data,
            bins={'even': [0, 2], 'odd': [1, 3]}
        )
        
        # Cross with ignore bin
        filtered_cross = zdc.cross(
            lambda s: s.addr_cp,
            lambda s: s.data_cp,
            bins=[
                zdc.cross_bins('low_even',
                               zdc.binsof(lambda s: s.addr_cp, 'low') &
                               zdc.binsof(lambda s: s.data_cp, 'even')),
                zdc.cross_bins('high_odd',
                               zdc.binsof(lambda s: s.addr_cp, 'high') &
                               zdc.binsof(lambda s: s.data_cp, 'odd')),
                # Ignore low_odd combination
                zdc.cross_ignore('ignore_low_odd',
                                 zdc.binsof(lambda s: s.addr_cp, 'low') &
                                 zdc.binsof(lambda s: s.data_cp, 'odd'))
            ]
        )
    
    t = Transaction(addr=0, data=0)
    cov = TransactionCov(parent=t)
    cov.start()
    
    # Sample low_even
    cov.sample()
    cross = cov.filtered_cross
    assert cross.get_total_bins() == 2  # Only 2 non-ignored bins
    assert cross.get_hit_bins() == 1
    
    # Sample ignored combination low_odd - should not count
    t.addr, t.data = 1, 1
    cov.sample()
    assert cross.get_hit_bins() == 1  # Still 1, ignored doesn't count


def test_cross_illegal():
    """Test cross_illegal() to mark illegal combinations."""
    @zdc.dataclass
    class Transaction:
        addr: int = 0
        data: int = 0
    
    @zdc.dataclass
    class TransactionCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        
        addr_cp: int = zdc.coverpoint(
            ref=lambda s: s.parent.addr,
            bins={'low': [0, 1], 'high': [2, 3]}
        )
        
        data_cp: int = zdc.coverpoint(
            ref=lambda s: s.parent.data,
            bins={'zero': [0], 'nonzero': [1, 2, 3]}
        )
        
        # Mark high_zero as illegal
        checked_cross = zdc.cross(
            lambda s: s.addr_cp,
            lambda s: s.data_cp,
            bins=[
                zdc.cross_illegal('illegal_high_zero',
                                  zdc.binsof(lambda s: s.addr_cp, 'high') &
                                  zdc.binsof(lambda s: s.data_cp, 'zero'))
            ]
        )
    
    t = Transaction(addr=0, data=0)
    cov = TransactionCov(parent=t)
    cov.start()
    
    # Sample legal combination
    cov.sample()
    
    # Sampling illegal combination should raise error
    t.addr, t.data = 2, 0  # high_zero is illegal
    with pytest.raises(Exception):  # Should raise coverage error
        cov.sample()


def test_cross_where_filter():
    """Test where= filter on cross bins."""
    @zdc.dataclass
    class Transaction:
        addr: int = 0
        data: int = 0
    
    @zdc.dataclass
    class TransactionCov(zdc.Covergroup):
        parent: object = zdc.field(default=None)
        
        addr_cp: int = zdc.coverpoint(
            ref=lambda s: s.parent.addr,
            bins={'low': [0, 1], 'high': [2, 3]}
        )
        
        data_cp: int = zdc.coverpoint(
            ref=lambda s: s.parent.data,
            bins=[0, 1]
        )
        
        # Cross bin with where filter
        filtered_cross = zdc.cross(
            lambda s: s.addr_cp,
            lambda s: s.data_cp,
            bins=[
                zdc.cross_bins('low_only',
                               zdc.binsof(lambda s: s.addr_cp) &
                               zdc.binsof(lambda s: s.data_cp),
                               where=lambda s: s.parent.addr < 2)
            ]
        )
    
    t = Transaction(addr=0, data=0)
    cov = TransactionCov(parent=t)
    cov.start()
    
    # Sample with addr < 2 (passes filter)
    cov.sample()
    cross = cov.filtered_cross
    assert cross.get_hit_bins() >= 1
    
    # Sample with addr >= 2 (fails filter, should not count)
    initial_hits = cross.get_hit_bins()
    t.addr, t.data = 2, 0
    cov.sample()
    assert cross.get_hit_bins() == initial_hits  # Unchanged due to filter


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
