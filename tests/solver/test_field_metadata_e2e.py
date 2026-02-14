"""End-to-end integration tests for field metadata extraction"""

import pytest
from zuspec.dataclasses import dataclass, rand, randc, randomize, randomize_with, constraint, RandomizationError


@dataclass
class SimplePacket:
    """Simple packet with rand fields"""
    addr: rand(domain=(0, 255)) = 0
    data: randc(domain=(0, 15)) = 0
    size: int = 64  # Non-random field


@dataclass
class ConstrainedPacket:
    """Packet with constraints"""
    addr: rand(domain=(0, 255)) = 0
    data: randc(domain=(0, 15)) = 0
    
    @constraint
    def addr_aligned(self):
        return self.addr % 4 == 0
    
    @constraint
    def data_nonzero(self):
        return self.data > 0


def test_simple_randomization():
    """Test randomization of fields with bounds"""
    pkt = SimplePacket()
    randomize(pkt)  # Should not raise
    
    assert 0 <= pkt.addr <= 255, f"addr out of bounds: {pkt.addr}"
    assert 0 <= pkt.data <= 15, f"data out of bounds: {pkt.data}"
    assert pkt.size == 64, "Non-random field changed"


def test_constrained_randomization():
    """Test randomization with constraints"""
    pkt = ConstrainedPacket()
    randomize(pkt)  # Should not raise
    
    assert 0 <= pkt.addr <= 255, f"addr out of bounds: {pkt.addr}"
    assert pkt.addr % 4 == 0, f"addr not aligned: {pkt.addr}"
    assert 0 < pkt.data <= 15, f"data out of bounds or zero: {pkt.data}"


def test_multiple_randomizations():
    """Test multiple randomizations produce different values"""
    pkt = SimplePacket()
    values = set()
    
    for _ in range(10):
        randomize(pkt)
        values.add((pkt.addr, pkt.data))
    
    # Should get at least some variety (not all the same)
    assert len(values) > 1, "Randomization produced same values"


@pytest.mark.skip(reason="randomize_with not yet implemented")
def test_randomize_with():
    """Test randomize_with for inline constraints"""
    pkt = SimplePacket()
    
    with pytest.raises(NotImplementedError):
        randomize_with(pkt, lambda: pkt.addr > 100)


@pytest.mark.skip(reason="randc cyclic behavior not yet implemented")
def test_randc_cyclic():
    """Test randc produces all values before repeating"""
    @dataclass
    class SmallRange:
        value: randc(domain=(0, 3)) = 0
    
    obj = SmallRange()
    seen = set()
    
    # Should see all 4 values in first 4 randomizations
    for _ in range(4):
        randomize(obj)
        seen.add(obj.value)
    
    assert len(seen) == 4, f"randc didn't produce all values: {seen}"


@pytest.mark.skip(reason="Constraint extraction not yet implemented")
def test_unsatisfiable_constraints():
    """Test that unsatisfiable constraints are detected"""
    @dataclass
    class Impossible:
        value: rand(domain=(0, 10)) = 0
        
        @constraint
        def impossible(self):
            return self.value > 20
    
    obj = Impossible()
    with pytest.raises(RandomizationError, match="No solution found"):
        randomize(obj)


def test_field_metadata_ir_flow():
    """Test that field metadata flows through IR correctly"""
    from zuspec.dataclasses.data_model_factory import DataModelFactory
    from zuspec.dataclasses.solver.frontend.variable_extractor import VariableExtractor
    from zuspec.dataclasses.solver.core.variable import VarKind
    
    # Build IR
    factory = DataModelFactory()
    ctx = factory.build([ConstrainedPacket])
    
    # Get the struct
    key = list(ctx.type_m.keys())[0]
    struct_ir = ctx.type_m[key]
    
    # Verify fields have metadata
    addr_field = [f for f in struct_ir.fields if f.name == 'addr'][0]
    assert addr_field.rand_kind == 'rand'
    assert addr_field.domain == (0, 255)
    
    data_field = [f for f in struct_ir.fields if f.name == 'data'][0]
    assert data_field.rand_kind == 'randc'
    assert data_field.domain == (0, 15)
    
    # Extract variables
    extractor = VariableExtractor()
    variables = extractor.extract_from_struct(struct_ir)
    
    assert len(variables) == 2, f"Expected 2 variables, got {len(variables)}"
    
    # Verify variable metadata
    addr_var = [v for v in variables if v.name == 'addr'][0]
    assert addr_var.kind == VarKind.RAND
    assert addr_var.domain.intervals[0] == (0, 255)
    
    data_var = [v for v in variables if v.name == 'data'][0]
    assert data_var.kind == VarKind.RANDC
    assert data_var.domain.intervals[0] == (0, 15)


def test_backward_compatibility():
    """Test that existing non-random fields still work"""
    from zuspec.dataclasses.data_model_factory import DataModelFactory
    
    @dataclass
    class LegacyClass:
        normal_field: int = 42
        string_field: str = "test"
    
    factory = DataModelFactory()
    ctx = factory.build([LegacyClass])
    
    key = list(ctx.type_m.keys())[0]
    struct_ir = ctx.type_m[key]
    
    # Verify fields exist
    assert len(struct_ir.fields) == 2
    
    # Verify no rand_kind or domain for non-random fields
    for field in struct_ir.fields:
        assert field.rand_kind is None
        assert field.domain is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
