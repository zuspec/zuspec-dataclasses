"""Test modeling features with sync/comb processes"""
import pytest
import zuspec.dataclasses as zdc


def test_bit_type_aliases():
    """Test that bit type aliases are available and properly defined"""
    # Test basic bit type
    assert hasattr(zdc, 'bit')
    assert zdc.bit == zdc.uint1_t
    
    # Test bit1 through bit64
    assert hasattr(zdc, 'bit1')
    assert zdc.bit1 == zdc.uint1_t
    
    assert hasattr(zdc, 'bit8')
    assert zdc.bit8 == zdc.uint8_t
    
    assert hasattr(zdc, 'bit16')
    assert zdc.bit16 == zdc.uint16_t
    
    assert hasattr(zdc, 'bit32')
    assert zdc.bit32 == zdc.uint32_t
    
    assert hasattr(zdc, 'bit64')
    assert zdc.bit64 == zdc.uint64_t


def test_port_declarations():
    """Test input/output port declarations"""
    
    @zdc.dataclass
    class SimplePort(zdc.Component):
        clock : zdc.bit = zdc.input()
        reset : zdc.bit = zdc.input()
        count : zdc.bit32 = zdc.output()
    
    # Verify the class can be defined
    assert hasattr(SimplePort, '__annotations__')
    assert 'clock' in SimplePort.__annotations__
    assert 'reset' in SimplePort.__annotations__
    assert 'count' in SimplePort.__annotations__


def test_sync_decorator_exists():
    """Test that @sync decorator is available"""
    assert hasattr(zdc, 'sync')
    assert callable(zdc.sync)


def test_comb_decorator_exists():
    """Test that @comb decorator is available"""
    assert hasattr(zdc, 'comb')
    assert callable(zdc.comb)


def test_sync_process_definition():
    """Test that sync processes can be defined"""
    
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
                self.count += 1
    
    # Verify the method was decorated
    assert hasattr(Counter, '_count_proc')
    # The decorator should return an ExecSync instance
    assert isinstance(Counter._count_proc, zdc.ExecSync)


def test_comb_process_definition():
    """Test that comb processes can be defined"""
    
    @zdc.dataclass
    class XorGate(zdc.Component):
        a : zdc.bit16 = zdc.input()
        b : zdc.bit16 = zdc.input()
        out : zdc.bit16 = zdc.output()
        
        @zdc.comb
        def _xor_calc(self):
            self.out = self.a ^ self.b
    
    # Verify the method was decorated
    assert hasattr(XorGate, '_xor_calc')
    # The decorator should return an ExecComb instance
    assert isinstance(XorGate._xor_calc, zdc.ExecComb)


def test_sync_and_comb_together():
    """Test component with both sync and comb processes"""
    
    @zdc.dataclass
    class MixedLogic(zdc.Component):
        clock : zdc.bit = zdc.input()
        reset : zdc.bit = zdc.input()
        out : zdc.bit16 = zdc.output()
        
        _count : zdc.bit32 = zdc.field()
        
        @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
        def _count_proc(self):
            if self.reset:
                self._count = 0
            else:
                self._count += 1
        
        @zdc.comb
        def _calc(self):
            self.out = (self._count >> 16) ^ (self._count & 0xFFFF)
    
    # Verify both decorators work
    assert hasattr(MixedLogic, '_count_proc')
    assert isinstance(MixedLogic._count_proc, zdc.ExecSync)
    assert hasattr(MixedLogic, '_calc')
    assert isinstance(MixedLogic._calc, zdc.ExecComb)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
