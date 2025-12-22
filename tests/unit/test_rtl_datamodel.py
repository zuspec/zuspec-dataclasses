"""Test datamodel generation for sync/comb processes (Phase 1A/1B)"""
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.data_model_factory import DataModelFactory
from zuspec.dataclasses.ir.data_type import Function


def test_sync_process_datamodel_generation():
    """Test that @sync methods are converted to datamodel Functions"""
    
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
                self.count = self.count + 1
    
    # Generate datamodel
    factory = DataModelFactory()
    ctx = factory.build(Counter)
    
    # Get the DataTypeComponent from the context
    type_name = Counter.__qualname__
    dm = ctx.type_m[type_name]
    
    # Verify sync_processes list is populated
    assert hasattr(dm, 'sync_processes')
    assert len(dm.sync_processes) == 1
    
    # Verify the function structure
    sync_func = dm.sync_processes[0]
    assert isinstance(sync_func, Function)
    assert sync_func.name == '_count_proc'
    
    # Verify metadata
    assert 'kind' in sync_func.metadata
    assert sync_func.metadata['kind'] == 'sync'
    assert 'clock' in sync_func.metadata
    assert 'reset' in sync_func.metadata
    assert 'method' in sync_func.metadata
    
    # Verify clock and reset expressions exist
    assert sync_func.metadata['clock'] is not None
    assert sync_func.metadata['reset'] is not None
    
    # Verify body was extracted
    assert len(sync_func.body) > 0


def test_comb_process_datamodel_generation():
    """Test that @comb methods are converted to datamodel Functions"""
    
    @zdc.dataclass
    class XorGate(zdc.Component):
        a : zdc.bit16 = zdc.input()
        b : zdc.bit16 = zdc.input()
        out : zdc.bit16 = zdc.output()
        
        @zdc.comb
        def _xor_calc(self):
            self.out = self.a ^ self.b
    
    # Generate datamodel
    factory = DataModelFactory()
    ctx = factory.build(XorGate)
    dm = ctx.type_m[XorGate.__qualname__]
    
    # Verify comb_processes list is populated
    assert hasattr(dm, 'comb_processes')
    assert len(dm.comb_processes) == 1
    
    # Verify the function structure
    comb_func = dm.comb_processes[0]
    assert isinstance(comb_func, Function)
    assert comb_func.name == '_xor_calc'
    
    # Verify metadata
    assert 'kind' in comb_func.metadata
    assert comb_func.metadata['kind'] == 'comb'
    assert 'sensitivity' in comb_func.metadata
    assert 'method' in comb_func.metadata
    
    # Verify sensitivity list was extracted
    sensitivity = comb_func.metadata['sensitivity']
    assert isinstance(sensitivity, list)
    # Should have reads from a and b
    assert len(sensitivity) >= 2
    
    # Verify body was extracted
    assert len(comb_func.body) > 0


def test_sync_no_reset():
    """Test sync process without reset signal"""
    
    @zdc.dataclass
    class SimpleReg(zdc.Component):
        clock : zdc.bit = zdc.input()
        d : zdc.bit8 = zdc.input()
        q : zdc.bit8 = zdc.output()
        
        @zdc.sync(clock=lambda s: s.clock)
        def _ff(self):
            self.q = self.d
    
    factory = DataModelFactory()
    ctx = factory.build(SimpleReg)
    dm = ctx.type_m[SimpleReg.__qualname__]
    
    assert len(dm.sync_processes) == 1
    sync_func = dm.sync_processes[0]
    assert sync_func.metadata['clock'] is not None
    assert sync_func.metadata['reset'] is None


def test_multiple_sync_comb_processes():
    """Test component with multiple sync and comb processes"""
    
    @zdc.dataclass
    class MixedLogic(zdc.Component):
        clock : zdc.bit = zdc.input()
        reset : zdc.bit = zdc.input()
        out : zdc.bit16 = zdc.output()
        
        _count : zdc.bit32 = zdc.field()
        _temp : zdc.bit16 = zdc.field()
        
        @zdc.sync(clock=lambda s: s.clock, reset=lambda s: s.reset)
        def _count_proc(self):
            if self.reset:
                self._count = 0
            else:
                self._count = self._count + 1
        
        @zdc.comb
        def _calc1(self):
            self._temp = (self._count >> 16) ^ (self._count & 0xFFFF)
        
        @zdc.comb
        def _calc2(self):
            self.out = self._temp
    
    factory = DataModelFactory()
    ctx = factory.build(MixedLogic)
    dm = ctx.type_m[MixedLogic.__qualname__]
    
    # Verify both lists are populated
    assert len(dm.sync_processes) == 1
    assert len(dm.comb_processes) == 2
    
    # Verify sync process
    assert dm.sync_processes[0].metadata['kind'] == 'sync'
    
    # Verify comb processes
    assert dm.comb_processes[0].metadata['kind'] == 'comb'
    assert dm.comb_processes[1].metadata['kind'] == 'comb'


def test_sensitivity_list_excludes_writes():
    """Test that sensitivity list only includes reads, not writes"""
    
    @zdc.dataclass
    class SensitivityTest(zdc.Component):
        a : zdc.bit8 = zdc.input()
        b : zdc.bit8 = zdc.input()
        out : zdc.bit8 = zdc.output()
        
        @zdc.comb
        def _logic(self):
            self.out = self.a + self.b
    
    factory = DataModelFactory()
    ctx = factory.build(SensitivityTest)
    dm = ctx.type_m[SensitivityTest.__qualname__]
    
    comb_func = dm.comb_processes[0]
    sensitivity = comb_func.metadata['sensitivity']
    
    # Should have 2 reads (a and b), not including out (which is written)
    assert len(sensitivity) == 2


def test_invalid_clock_lambda():
    """Test that invalid clock lambda raises error"""
    
    @zdc.dataclass
    class BadClock(zdc.Component):
        clock : zdc.bit = zdc.input()
        out : zdc.bit = zdc.output()
        
        @zdc.sync(clock=lambda s: None)  # Invalid - returns None
        def _proc(self):
            self.out = 1
    
    factory = DataModelFactory()
    with pytest.raises(RuntimeError, match="did not return a valid field reference"):
        ctx = factory.build(BadClock)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
