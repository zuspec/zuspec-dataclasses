"""Test that both assert and plain expression constraint syntax work"""

import pytest
from zuspec.dataclasses import dataclass, rand, constraint, randomize


@dataclass
class PacketWithAssert:
    """Test constraints using assert statements (fixed constraints)"""
    addr: rand(domain=(0, 255)) = 0
    data: rand(domain=(0, 255)) = 0
    
    @constraint
    def addr_aligned(self):
        """Fixed constraint using assert statement (type-checker friendly)"""
        assert self.addr % 4 == 0
    
    @constraint
    def data_nonzero(self):
        """Multiple fixed constraints using assert"""
        assert self.data > 0
        assert self.data < 128


@dataclass
class PacketWithExpr:
    """Test constraints using plain expressions (fixed constraints)"""
    addr: rand(domain=(0, 255)) = 0
    data: rand(domain=(0, 255)) = 0
    
    @constraint
    def addr_aligned(self):
        """Fixed constraint using plain expression"""
        self.addr % 4 == 0
    
    @constraint
    def data_nonzero(self):
        """Multiple fixed constraints using plain expressions"""
        self.data > 0
        self.data < 128


@dataclass
class PacketWithGeneric:
    """Test generic constraints (use return)"""
    addr: rand(domain=(0, 255)) = 0
    data: rand(domain=(0, 255)) = 0
    
    @constraint
    def addr_aligned(self):
        """Fixed constraint"""
        assert self.addr % 4 == 0
    
    @constraint.generic
    def addr_low(self):
        """Generic constraint - only applies when explicitly referenced"""
        return self.addr < 0x80


@dataclass
class PacketMixed:
    """Test mixing both styles"""
    addr: rand(domain=(0, 255)) = 0
    data: rand(domain=(0, 255)) = 0
    
    @constraint
    def addr_aligned(self):
        """Fixed: assert style"""
        assert self.addr % 4 == 0
    
    @constraint
    def data_nonzero(self):
        """Fixed: expression style"""
        self.data > 0


@pytest.mark.skip(reason="Constraint extraction not yet implemented")
def test_assert_syntax():
    """Test that assert statements work as constraints"""
    pkt = PacketWithAssert()
    randomize(pkt)
    
    # Verify constraints
    assert pkt.addr % 4 == 0, f"addr not aligned: {pkt.addr}"
    assert 0 < pkt.data < 128, f"data out of range: {pkt.data}"


@pytest.mark.skip(reason="Constraint extraction not yet implemented")
def test_expr_syntax():
    """Test that plain expressions work as constraints"""
    pkt = PacketWithExpr()
    randomize(pkt)
    
    # Verify constraints
    assert pkt.addr % 4 == 0, f"addr not aligned: {pkt.addr}"
    assert 0 < pkt.data < 128, f"data out of range: {pkt.data}"


@pytest.mark.skip(reason="Constraint extraction not yet implemented")
def test_mixed_syntax():
    """Test that mixing both styles works"""
    pkt = PacketMixed()
    randomize(pkt)
    
    # Verify constraints
    assert pkt.addr % 4 == 0, f"addr not aligned: {pkt.addr}"
    assert pkt.data > 0, f"data not positive: {pkt.data}"


def test_ir_extraction_assert():
    """Test that IR correctly extracts assert statements"""
    from zuspec.dataclasses.data_model_factory import DataModelFactory
    from zuspec.dataclasses.ir.stmt import StmtAssert
    
    factory = DataModelFactory()
    ctx = factory.build([PacketWithAssert])
    
    # Get the struct
    key = list(ctx.type_m.keys())[0]
    struct_ir = ctx.type_m[key]
    
    # Check that constraint functions exist
    assert len(struct_ir.functions) >= 2, f"Expected at least 2 constraint functions, got {len(struct_ir.functions)}"
    
    # Find addr_aligned function
    addr_aligned = [f for f in struct_ir.functions if f.name == 'addr_aligned'][0]
    
    # Verify it has StmtAssert in body (skip docstring if present)
    assert len(addr_aligned.body) > 0, "Function body is empty"
    
    # Find the first StmtAssert (skip docstrings)
    assert_stmts = [s for s in addr_aligned.body if isinstance(s, StmtAssert)]
    assert len(assert_stmts) > 0, f"No StmtAssert found in body: {[type(s).__name__ for s in addr_aligned.body]}"
    
    print(f"✓ IR correctly extracted assert statement")


def test_ir_extraction_expr():
    """Test that IR correctly extracts plain expressions"""
    from zuspec.dataclasses.data_model_factory import DataModelFactory
    from zuspec.dataclasses.ir.stmt import StmtExpr
    
    factory = DataModelFactory()
    ctx = factory.build([PacketWithExpr])
    
    # Get the struct
    key = list(ctx.type_m.keys())[0]
    struct_ir = ctx.type_m[key]
    
    # Find addr_aligned function
    addr_aligned = [f for f in struct_ir.functions if f.name == 'addr_aligned'][0]
    
    # Verify it has StmtExpr in body
    assert len(addr_aligned.body) > 0, "Function body is empty"
    assert isinstance(addr_aligned.body[0], StmtExpr), f"Expected StmtExpr, got {type(addr_aligned.body[0])}"
    
    print(f"✓ IR correctly extracted expression statement")


def test_constraint_builder_accepts_both():
    """Test that constraint builder accepts both statement types"""
    from zuspec.dataclasses.data_model_factory import DataModelFactory
    from zuspec.dataclasses.solver.frontend.constraint_system_builder import ConstraintSystemBuilder
    
    # Test with assert syntax
    factory = DataModelFactory()
    ctx = factory.build([PacketWithAssert])
    key = list(ctx.type_m.keys())[0]
    struct_ir = ctx.type_m[key]
    
    builder = ConstraintSystemBuilder()
    # Should not raise
    cs = builder.build_from_struct(struct_ir)
    
    # Should have extracted constraints
    assert len(cs.constraints) > 0, "No constraints extracted from assert syntax"
    print(f"✓ Constraint builder extracted {len(cs.constraints)} constraints from assert syntax")
    
    # Test with expression syntax
    ctx2 = factory.build([PacketWithExpr])
    key2 = list(ctx2.type_m.keys())[0]
    struct_ir2 = ctx2.type_m[key2]
    
    builder2 = ConstraintSystemBuilder()
    cs2 = builder2.build_from_struct(struct_ir2)
    
    assert len(cs2.constraints) > 0, "No constraints extracted from expression syntax"
    print(f"✓ Constraint builder extracted {len(cs2.constraints)} constraints from expression syntax")
    
    # Both should produce same number of constraints
    assert len(cs.constraints) == len(cs2.constraints), \
        f"Different constraint counts: assert={len(cs.constraints)}, expr={len(cs2.constraints)}"


def test_generic_constraint_metadata():
    """Test that generic constraints have correct metadata"""
    from zuspec.dataclasses.data_model_factory import DataModelFactory
    
    factory = DataModelFactory()
    ctx = factory.build([PacketWithGeneric])
    key = list(ctx.type_m.keys())[0]
    struct_ir = ctx.type_m[key]
    
    # Find the generic constraint function
    addr_low = [f for f in struct_ir.functions if f.name == 'addr_low'][0]
    
    # Verify metadata
    assert addr_low.metadata.get('_is_constraint'), "Generic constraint not marked as constraint"
    assert addr_low.metadata.get('_constraint_kind') == 'generic', \
        f"Expected 'generic', got {addr_low.metadata.get('_constraint_kind')}"
    
    # Find the fixed constraint for comparison
    addr_aligned = [f for f in struct_ir.functions if f.name == 'addr_aligned'][0]
    assert addr_aligned.metadata.get('_constraint_kind') == 'fixed', \
        f"Expected 'fixed', got {addr_aligned.metadata.get('_constraint_kind')}"
    
    print("✓ Generic and fixed constraints have correct metadata")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
