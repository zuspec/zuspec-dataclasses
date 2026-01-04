"""Tests for VCD (Value Change Dump) signal tracing."""
import asyncio
import os
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.rt import with_tracer, VCDTracer, SignalTracer


def test_vcd_tracer_implements_signal_tracer(tmp_path):
    """Test that VCDTracer implements SignalTracer protocol."""
    vcd_path = tmp_path / "dummy.vcd"
    vcd = VCDTracer(str(vcd_path))
    assert isinstance(vcd, SignalTracer)


def test_vcd_basic_signal_recording(tmp_path):
    """Test basic signal value recording in VCD format."""
    
    @zdc.dataclass
    class SimpleSignal(zdc.Component):
        clock : zdc.bit = zdc.input()
        data : zdc.bit8 = zdc.output()
    
    vcd_path = tmp_path / "basic.vcd"
    vcd = VCDTracer(str(vcd_path))
    
    with with_tracer(vcd, enable_signals=True):
        comp = SimpleSignal()
    
    # Simulate some value changes
    async def run():
        comp.clock = 0
        comp.data = 0
        await comp.wait(zdc.Time.ns(10))
        
        comp.clock = 1
        comp.data = 42
        await comp.wait(zdc.Time.ns(10))
        
        comp.clock = 0
        comp.data = 100
        await comp.wait(zdc.Time.ns(10))
    
    asyncio.run(run())
    vcd.close()
    
    # Read and verify VCD content
    content = vcd_path.read_text()
    
    # Verify header elements
    assert '$date' in content
    assert '$version' in content
    assert '$timescale' in content
    assert '$enddefinitions $end' in content
    assert '$dumpvars' in content
    
    # Verify signal declarations
    assert '$var' in content
    assert 'clock' in content
    assert 'data' in content
    
    # Verify value changes exist
    assert '#' in content  # Timestamps


def test_vcd_counter_simulation(tmp_path):
    """Test VCD output for a counter component."""
    
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
    
    vcd_path = tmp_path / "counter.vcd"
    vcd = VCDTracer(str(vcd_path))
    
    with with_tracer(vcd, enable_signals=True):
        counter = Counter()
    
    async def run():
        # Reset sequence
        counter.reset = 1
        counter.clock = 0
        await counter.wait(zdc.Time.ns(5))
        counter.clock = 1
        await counter.wait(zdc.Time.ns(5))
        counter.clock = 0
        await counter.wait(zdc.Time.ns(5))
        
        # Release reset and count
        counter.reset = 0
        for _ in range(5):
            counter.clock = 1
            await counter.wait(zdc.Time.ns(5))
            counter.clock = 0
            await counter.wait(zdc.Time.ns(5))
    
    asyncio.run(run())
    vcd.close()
    
    # Read and verify VCD content
    content = vcd_path.read_text()
    
    # Verify signals are declared
    assert 'clock' in content
    assert 'reset' in content
    assert 'count' in content
    
    # Verify there are multiple timestamps (indicating simulation ran)
    lines = content.split('\n')
    timestamp_lines = [l for l in lines if l.startswith('#')]
    assert len(timestamp_lines) > 0, "Expected timestamp markers in VCD"


def test_vcd_multiple_widths(tmp_path):
    """Test VCD handles signals of different bit widths."""
    
    @zdc.dataclass
    class MultiWidth(zdc.Component):
        bit1_sig : zdc.bit = zdc.input()
        bit8_sig : zdc.bit8 = zdc.output()
        bit16_sig : zdc.bit16 = zdc.output()
        bit32_sig : zdc.bit32 = zdc.output()
    
    vcd_path = tmp_path / "multiwidth.vcd"
    vcd = VCDTracer(str(vcd_path))
    
    with with_tracer(vcd, enable_signals=True):
        comp = MultiWidth()
    
    async def run():
        comp.bit1_sig = 1
        comp.bit8_sig = 0xFF
        comp.bit16_sig = 0xABCD
        comp.bit32_sig = 0x12345678
        await comp.wait(zdc.Time.ns(10))
        
        comp.bit1_sig = 0
        comp.bit8_sig = 0
        comp.bit16_sig = 0
        comp.bit32_sig = 0
        await comp.wait(zdc.Time.ns(10))
    
    asyncio.run(run())
    vcd.close()
    
    # Read and verify VCD content
    content = vcd_path.read_text()
    
    # Verify signal width declarations
    # VCD format: $var wire WIDTH IDENTIFIER NAME $end
    assert '$var' in content
    
    # Check for different width declarations
    lines = content.split('\n')
    var_lines = [l for l in lines if l.startswith('$var')]
    
    # Should have 4 signals with different widths
    assert len(var_lines) >= 4


def test_vcd_hierarchical_components(tmp_path):
    """Test VCD scope hierarchy for nested components."""
    
    @zdc.dataclass  
    class Inner(zdc.Component):
        inner_sig : zdc.bit8 = zdc.output()
    
    @zdc.dataclass
    class Outer(zdc.Component):
        outer_sig : zdc.bit8 = zdc.output()
        inner : Inner = zdc.field(default_factory=Inner)
    
    vcd_path = tmp_path / "hierarchy.vcd"
    vcd = VCDTracer(str(vcd_path))
    
    with with_tracer(vcd, enable_signals=True):
        comp = Outer()
    
    async def run():
        comp.outer_sig = 10
        comp.inner.inner_sig = 20
        await comp.wait(zdc.Time.ns(10))
    
    asyncio.run(run())
    vcd.close()
    
    # Read and verify VCD content  
    content = vcd_path.read_text()
    
    # Verify scopes are created
    assert '$scope' in content
    assert '$upscope' in content
    
    # Verify both signals are present
    assert 'outer_sig' in content
    assert 'inner_sig' in content


def test_vcd_context_manager(tmp_path):
    """Test VCDTracer works as a context manager."""
    
    @zdc.dataclass
    class Simple(zdc.Component):
        sig : zdc.bit8 = zdc.output()
    
    vcd_path = tmp_path / "context.vcd"
    
    with VCDTracer(str(vcd_path)) as vcd:
        with with_tracer(vcd, enable_signals=True):
            comp = Simple()
        
        async def run():
            comp.sig = 42
            await comp.wait(zdc.Time.ns(10))
        
        asyncio.run(run())
    
    # File should be closed and readable
    content = vcd_path.read_text()
    assert '$date' in content


def test_vcd_timestamp_ordering(tmp_path):
    """Test that timestamps are properly ordered in VCD output."""
    
    @zdc.dataclass
    class TimedSignal(zdc.Component):
        sig : zdc.bit8 = zdc.output()
    
    vcd_path = tmp_path / "timestamps.vcd"
    vcd = VCDTracer(str(vcd_path))
    
    with with_tracer(vcd, enable_signals=True):
        comp = TimedSignal()
    
    async def run():
        comp.sig = 1
        await comp.wait(zdc.Time.ns(5))
        comp.sig = 2
        await comp.wait(zdc.Time.ns(10))
        comp.sig = 3
        await comp.wait(zdc.Time.ns(15))
        comp.sig = 4
        await comp.wait(zdc.Time.ns(20))
    
    asyncio.run(run())
    vcd.close()
    
    # Read and verify timestamp ordering
    content = vcd_path.read_text()
    
    # Extract timestamps
    lines = content.split('\n')
    timestamps = []
    for line in lines:
        if line.startswith('#'):
            try:
                ts = int(line[1:])
                timestamps.append(ts)
            except ValueError:
                pass
    
    # Verify timestamps are monotonically increasing
    for i in range(1, len(timestamps)):
        assert timestamps[i] >= timestamps[i-1], \
            f"Timestamps not ordered: {timestamps[i-1]} > {timestamps[i]}"


def test_vcd_scalar_value_format(tmp_path):
    """Test VCD scalar (1-bit) value format - no space between value and identifier."""
    
    @zdc.dataclass
    class ScalarSignal(zdc.Component):
        bit_sig : zdc.bit = zdc.input()
    
    vcd_path = tmp_path / "scalar.vcd"
    vcd = VCDTracer(str(vcd_path))
    
    with with_tracer(vcd, enable_signals=True):
        comp = ScalarSignal()
    
    async def run():
        comp.bit_sig = 0
        await comp.wait(zdc.Time.ns(5))
        comp.bit_sig = 1
        await comp.wait(zdc.Time.ns(5))
        comp.bit_sig = 0
        await comp.wait(zdc.Time.ns(5))
    
    asyncio.run(run())
    vcd.close()
    
    content = vcd_path.read_text()
    lines = content.split('\n')
    
    # Find scalar value changes (0X or 1X where X is identifier)
    # Scalar format: value immediately followed by identifier, no space
    # Identifiers are short (1-3 chars typically), so scalar changes are short
    scalar_changes = []
    for line in lines:
        line = line.strip()
        # Scalar value changes are short: 1 value char + 1-3 identifier chars
        # Skip lines that are too long or don't match the pattern
        if (line and 
            len(line) <= 5 and  # Short enough to be a scalar change
            line[0] in '01xXzZ' and 
            len(line) > 1 and 
            not line.startswith('b')):
            scalar_changes.append(line)
    
    # Should have scalar value changes
    assert len(scalar_changes) > 0, "Expected scalar value changes in VCD"
    
    # Each scalar change should have no space between value and identifier
    for change in scalar_changes:
        assert ' ' not in change, f"Scalar value should not have space: {change}"


def test_vcd_vector_value_format(tmp_path):
    """Test VCD vector (multi-bit) value format - space between value and identifier."""
    
    @zdc.dataclass
    class VectorSignal(zdc.Component):
        vec_sig : zdc.bit8 = zdc.output()
    
    vcd_path = tmp_path / "vector.vcd"
    vcd = VCDTracer(str(vcd_path))
    
    with with_tracer(vcd, enable_signals=True):
        comp = VectorSignal()
    
    async def run():
        comp.vec_sig = 0xAB
        await comp.wait(zdc.Time.ns(5))
        comp.vec_sig = 0
        await comp.wait(zdc.Time.ns(5))
    
    asyncio.run(run())
    vcd.close()
    
    content = vcd_path.read_text()
    lines = content.split('\n')
    
    # Find vector value changes (bXXXX ID format)
    vector_changes = []
    for line in lines:
        line = line.strip()
        if line.startswith('b') and ' ' in line:
            vector_changes.append(line)
    
    # Should have vector value changes
    assert len(vector_changes) > 0, "Expected vector value changes in VCD"
    
    # Each vector change should have format: b<binary> <identifier>
    for change in vector_changes:
        assert change.startswith('b'), f"Vector should start with 'b': {change}"
        parts = change.split(' ')
        assert len(parts) == 2, f"Vector should have space separator: {change}"


def test_signal_tracing_disabled_by_default(tmp_path):
    """Test that signal tracing is disabled when enable_signals=False."""
    
    @zdc.dataclass
    class Simple(zdc.Component):
        sig : zdc.bit8 = zdc.output()
    
    vcd_path = tmp_path / "disabled.vcd"
    vcd = VCDTracer(str(vcd_path))
    
    # Don't enable signal tracing
    with with_tracer(vcd, enable_signals=False):
        comp = Simple()
    
    async def run():
        comp.sig = 42
        await comp.wait(zdc.Time.ns(10))
    
    asyncio.run(run())
    vcd.close()
    
    # With no signals registered, file may not exist or be empty
    if vcd_path.exists():
        content = vcd_path.read_text()
        # With no signals registered, there should be no $var declarations
        assert '$var' not in content or content.strip() == ''
    # else: file not created, which is also acceptable


def test_vcd_large_signal_count(tmp_path):
    """Test VCD with ~100 signals and 1000 timestamps."""
    
    # Create a component with many signals using dynamic class creation
    # We'll create 25 signals per component and nest 4 components = 100 signals
    @zdc.dataclass
    class SignalBlock(zdc.Component):
        sig_00 : zdc.bit8 = zdc.output()
        sig_01 : zdc.bit8 = zdc.output()
        sig_02 : zdc.bit8 = zdc.output()
        sig_03 : zdc.bit8 = zdc.output()
        sig_04 : zdc.bit8 = zdc.output()
        sig_05 : zdc.bit8 = zdc.output()
        sig_06 : zdc.bit8 = zdc.output()
        sig_07 : zdc.bit8 = zdc.output()
        sig_08 : zdc.bit8 = zdc.output()
        sig_09 : zdc.bit8 = zdc.output()
        sig_10 : zdc.bit8 = zdc.output()
        sig_11 : zdc.bit8 = zdc.output()
        sig_12 : zdc.bit8 = zdc.output()
        sig_13 : zdc.bit8 = zdc.output()
        sig_14 : zdc.bit8 = zdc.output()
        sig_15 : zdc.bit8 = zdc.output()
        sig_16 : zdc.bit8 = zdc.output()
        sig_17 : zdc.bit8 = zdc.output()
        sig_18 : zdc.bit8 = zdc.output()
        sig_19 : zdc.bit8 = zdc.output()
        sig_20 : zdc.bit8 = zdc.output()
        sig_21 : zdc.bit8 = zdc.output()
        sig_22 : zdc.bit8 = zdc.output()
        sig_23 : zdc.bit8 = zdc.output()
        sig_24 : zdc.bit8 = zdc.output()
    
    @zdc.dataclass
    class LargeDesign(zdc.Component):
        clock : zdc.bit = zdc.input()
        block_a : SignalBlock = zdc.field(default_factory=SignalBlock)
        block_b : SignalBlock = zdc.field(default_factory=SignalBlock)
        block_c : SignalBlock = zdc.field(default_factory=SignalBlock)
        block_d : SignalBlock = zdc.field(default_factory=SignalBlock)
    
    vcd_path = tmp_path / "large_signals.vcd"
    vcd = VCDTracer(str(vcd_path))
    
    with with_tracer(vcd, enable_signals=True):
        design = LargeDesign()
    
    async def run():
        # Run for 1000 clock cycles, changing signals each cycle
        for cycle in range(1000):
            design.clock = 1
            
            # Update signals in each block with different patterns
            for i in range(25):
                sig_name = f"sig_{i:02d}"
                # Different pattern for each block
                setattr(design.block_a, sig_name, (cycle + i) & 0xFF)
                setattr(design.block_b, sig_name, (cycle * 2 + i) & 0xFF)
                setattr(design.block_c, sig_name, (cycle ^ i) & 0xFF)
                setattr(design.block_d, sig_name, ((cycle + i) * 3) & 0xFF)
            
            await design.wait(zdc.Time.ns(5))
            design.clock = 0
            await design.wait(zdc.Time.ns(5))
    
    asyncio.run(run())
    vcd.close()
    
    # Verify VCD content
    content = vcd_path.read_text()
    lines = content.split('\n')
    
    # Count signal declarations (should have 100+ signals: 25*4 blocks + clock)
    var_lines = [l for l in lines if l.strip().startswith('$var')]
    assert len(var_lines) >= 100, f"Expected at least 100 signals, got {len(var_lines)}"
    
    # Count timestamps (should have many for 1000 cycles)
    timestamp_lines = [l for l in lines if l.startswith('#')]
    assert len(timestamp_lines) >= 500, f"Expected many timestamps, got {len(timestamp_lines)}"
    
    # Verify file is reasonably large (should be several KB)
    file_size = vcd_path.stat().st_size
    assert file_size > 10000, f"VCD file seems too small: {file_size} bytes"


def test_vcd_long_simulation_single_component(tmp_path):
    """Test VCD with single component running for 1000+ timestamps."""
    
    @zdc.dataclass
    class DataProcessor(zdc.Component):
        clock : zdc.bit = zdc.input()
        reset : zdc.bit = zdc.input()
        data_in : zdc.bit32 = zdc.input()
        data_out : zdc.bit32 = zdc.output()
        status : zdc.bit8 = zdc.output()
        error : zdc.bit = zdc.output()
        count : zdc.bit16 = zdc.output()
        
        # Internal state signals
        state : zdc.bit8 = zdc.output()
        buffer : zdc.bit32 = zdc.output()
        checksum : zdc.bit16 = zdc.output()
    
    vcd_path = tmp_path / "long_sim.vcd"
    vcd = VCDTracer(str(vcd_path))
    
    with with_tracer(vcd, enable_signals=True):
        proc = DataProcessor()
    
    async def run():
        # Initialize
        proc.reset = 1
        proc.clock = 0
        proc.data_in = 0
        await proc.wait(zdc.Time.ns(10))
        
        proc.reset = 0
        
        # Run 1000 cycles with varying data patterns
        for cycle in range(1000):
            # Rising edge
            proc.clock = 1
            
            # Generate test patterns
            proc.data_in = (cycle * 0x12345678) & 0xFFFFFFFF
            proc.data_out = proc.data_in ^ 0xAAAAAAAA
            proc.status = (cycle % 8) & 0xFF
            proc.error = 1 if (cycle % 100 == 99) else 0
            proc.count = cycle & 0xFFFF
            proc.state = (cycle // 100) & 0xFF
            proc.buffer = proc.data_in
            proc.checksum = (proc.checksum + proc.data_in) & 0xFFFF if hasattr(proc, '_impl') else 0
            
            await proc.wait(zdc.Time.ns(5))
            
            # Falling edge
            proc.clock = 0
            await proc.wait(zdc.Time.ns(5))
    
    asyncio.run(run())
    vcd.close()
    
    # Verify VCD content
    content = vcd_path.read_text()
    lines = content.split('\n')
    
    # Count timestamps
    timestamp_lines = [l for l in lines if l.startswith('#')]
    assert len(timestamp_lines) >= 1000, f"Expected at least 1000 timestamps, got {len(timestamp_lines)}"
    
    # Verify all signals are present
    assert 'clock' in content
    assert 'reset' in content
    assert 'data_in' in content
    assert 'data_out' in content
    assert 'status' in content
    assert 'error' in content
    assert 'count' in content
    assert 'state' in content
    assert 'buffer' in content
    assert 'checksum' in content


def test_vcd_mixed_width_stress(tmp_path):
    """Test VCD with many signals of different widths over many timestamps."""
    
    @zdc.dataclass
    class MixedWidthBlock(zdc.Component):
        # 1-bit signals (10)
        bit_0 : zdc.bit = zdc.output()
        bit_1 : zdc.bit = zdc.output()
        bit_2 : zdc.bit = zdc.output()
        bit_3 : zdc.bit = zdc.output()
        bit_4 : zdc.bit = zdc.output()
        bit_5 : zdc.bit = zdc.output()
        bit_6 : zdc.bit = zdc.output()
        bit_7 : zdc.bit = zdc.output()
        bit_8 : zdc.bit = zdc.output()
        bit_9 : zdc.bit = zdc.output()
        
        # 8-bit signals (10)
        byte_0 : zdc.bit8 = zdc.output()
        byte_1 : zdc.bit8 = zdc.output()
        byte_2 : zdc.bit8 = zdc.output()
        byte_3 : zdc.bit8 = zdc.output()
        byte_4 : zdc.bit8 = zdc.output()
        byte_5 : zdc.bit8 = zdc.output()
        byte_6 : zdc.bit8 = zdc.output()
        byte_7 : zdc.bit8 = zdc.output()
        byte_8 : zdc.bit8 = zdc.output()
        byte_9 : zdc.bit8 = zdc.output()
        
        # 16-bit signals (5)
        word_0 : zdc.bit16 = zdc.output()
        word_1 : zdc.bit16 = zdc.output()
        word_2 : zdc.bit16 = zdc.output()
        word_3 : zdc.bit16 = zdc.output()
        word_4 : zdc.bit16 = zdc.output()
        
        # 32-bit signals (5)
        dword_0 : zdc.bit32 = zdc.output()
        dword_1 : zdc.bit32 = zdc.output()
        dword_2 : zdc.bit32 = zdc.output()
        dword_3 : zdc.bit32 = zdc.output()
        dword_4 : zdc.bit32 = zdc.output()
    
    @zdc.dataclass
    class StressTest(zdc.Component):
        clock : zdc.bit = zdc.input()
        unit_0 : MixedWidthBlock = zdc.field(default_factory=MixedWidthBlock)
        unit_1 : MixedWidthBlock = zdc.field(default_factory=MixedWidthBlock)
        unit_2 : MixedWidthBlock = zdc.field(default_factory=MixedWidthBlock)
    
    vcd_path = tmp_path / "mixed_stress.vcd"
    vcd = VCDTracer(str(vcd_path))
    
    with with_tracer(vcd, enable_signals=True):
        test = StressTest()
    
    async def run():
        units = [test.unit_0, test.unit_1, test.unit_2]
        
        for cycle in range(1000):
            test.clock = 1
            
            for unit_idx, unit in enumerate(units):
                # Update 1-bit signals
                for i in range(10):
                    setattr(unit, f"bit_{i}", (cycle + i + unit_idx) & 1)
                
                # Update 8-bit signals
                for i in range(10):
                    setattr(unit, f"byte_{i}", (cycle * (i + 1) + unit_idx) & 0xFF)
                
                # Update 16-bit signals
                for i in range(5):
                    setattr(unit, f"word_{i}", (cycle * 100 + i + unit_idx * 1000) & 0xFFFF)
                
                # Update 32-bit signals
                for i in range(5):
                    val = (cycle * 0x10001 + i * 0x1000 + unit_idx * 0x100000) & 0xFFFFFFFF
                    setattr(unit, f"dword_{i}", val)
            
            await test.wait(zdc.Time.ns(5))
            test.clock = 0
            await test.wait(zdc.Time.ns(5))
    
    asyncio.run(run())
    vcd.close()
    
    # Verify VCD content
    content = vcd_path.read_text()
    lines = content.split('\n')
    
    # Count signal declarations
    # Each MixedWidthBlock has 30 signals, 3 units = 90 + clock = 91
    var_lines = [l for l in lines if l.strip().startswith('$var')]
    assert len(var_lines) >= 90, f"Expected at least 90 signals, got {len(var_lines)}"
    
    # Count timestamps
    timestamp_lines = [l for l in lines if l.startswith('#')]
    assert len(timestamp_lines) >= 1000, f"Expected at least 1000 timestamps, got {len(timestamp_lines)}"
    
    # Verify different value formats are present
    # Scalar changes (1-bit): pattern like "0!" or "1!" (short lines)
    scalar_changes = [l for l in lines if l.strip() and len(l.strip()) <= 3 
                      and l.strip()[0] in '01' and not l.startswith('#')]
    assert len(scalar_changes) > 0, "Expected scalar value changes"
    
    # Vector changes: pattern like "b10101 X"
    vector_changes = [l for l in lines if l.strip().startswith('b') and ' ' in l]
    assert len(vector_changes) > 0, "Expected vector value changes"
    
    # Verify file size is substantial
    file_size = vcd_path.stat().st_size
    assert file_size > 50000, f"VCD file seems too small for stress test: {file_size} bytes"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
