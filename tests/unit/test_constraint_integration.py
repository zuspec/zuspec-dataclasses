#****************************************************************************
# Copyright 2019-2025 Matthew Ballance and contributors
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
"""Integration tests for constraint frontend end-to-end workflows."""
import pytest
import zuspec.dataclasses as zdc


def test_end_to_end_packet_example():
    """Test complete workflow: define, parse, and analyze packet constraints."""
    
    @zdc.dataclass
    class Packet:
        length: int = zdc.rand(bounds=(64, 1500), default=64)
        header_len: int = zdc.rand(bounds=(20, 60), default=20)
        pkt_type: int = zdc.rand(bounds=(0, 3), default=0)
        
        @zdc.constraint
        def valid_length(self):
            self.length >= self.header_len
        
        @zdc.constraint
        def type_dist(self):
            zdc.dist(self.pkt_type, {0: 40, 1: 30, 2: 20, 3: 10})
    
    # Extract random fields
    rand_fields = zdc.extract_rand_fields(Packet)
    assert len(rand_fields) == 3
    
    field_names = {f['name'] for f in rand_fields}
    assert field_names == {'length', 'header_len', 'pkt_type'}
    
    # Check bounds
    length_field = [f for f in rand_fields if f['name'] == 'length'][0]
    assert length_field['bounds'] == (64, 1500)
    
    # Parse constraints
    parser = zdc.ConstraintParser()
    constraints = parser.extract_constraints(Packet)
    assert len(constraints) == 2
    
    # Check constraint details
    valid_length = [c for c in constraints if c['name'] == 'valid_length'][0]
    assert valid_length['kind'] == 'fixed'
    assert len(valid_length['exprs']) == 1
    assert valid_length['exprs'][0]['type'] == 'compare'
    
    type_dist = [c for c in constraints if c['name'] == 'type_dist'][0]
    assert type_dist['kind'] == 'fixed'
    assert len(type_dist['exprs']) == 1
    assert type_dist['exprs'][0]['type'] == 'dist'
    
    # Verify object instantiation
    pkt = Packet()
    assert pkt.length == 64
    assert pkt.header_len == 20
    assert pkt.pkt_type == 0


def test_end_to_end_bus_transaction():
    """Test complete workflow: define, parse bus transaction with implications."""
    
    @zdc.dataclass
    class BusTransaction:
        addr: int = zdc.rand(bounds=(0, 255), default=0)
        data: int = zdc.rand(bounds=(0, 255), default=0)
        read_enable: int = zdc.rand(default=0)
        write_enable: int = zdc.rand(default=0)
        
        @zdc.constraint
        def not_both_rw(self):
            not (self.read_enable and self.write_enable)
        
        @zdc.constraint
        def addr_aligned(self):
            self.addr % 4 == 0
        
        @zdc.constraint
        def solve_order_hint(self):
            zdc.solve_order(self.addr, self.data)
        
        @zdc.constraint.generic
        def low_addr(self):
            self.addr < 128
    
    # Extract and verify
    rand_fields = zdc.extract_rand_fields(BusTransaction)
    assert len(rand_fields) == 4
    
    parser = zdc.ConstraintParser()
    constraints = parser.extract_constraints(BusTransaction)
    assert len(constraints) == 4
    
    # Verify fixed vs generic
    fixed = [c for c in constraints if c['kind'] == 'fixed']
    generic = [c for c in constraints if c['kind'] == 'generic']
    assert len(fixed) == 3
    assert len(generic) == 1
    
    # Verify specific constraint types
    not_both = [c for c in constraints if c['name'] == 'not_both_rw'][0]
    assert not_both['exprs'][0]['type'] == 'unary_op'
    assert not_both['exprs'][0]['op'] == 'not'
    
    aligned = [c for c in constraints if c['name'] == 'addr_aligned'][0]
    assert aligned['exprs'][0]['type'] == 'compare'
    
    solve_order = [c for c in constraints if c['name'] == 'solve_order_hint'][0]
    assert solve_order['exprs'][0]['type'] == 'solve_order'
    assert len(solve_order['exprs'][0]['vars']) == 2


def test_end_to_end_mixed_constraints():
    """Test workflow with all constraint types."""
    
    @zdc.dataclass
    class ComplexClass:
        # Different random field types
        normal_rand: int = zdc.rand(bounds=(0, 100), default=0)
        cyclic_rand: int = zdc.randc(bounds=(0, 15), default=0)
        array_rand: int = zdc.rand(size=8, default=0)
        
        # IDs for uniqueness
        id1: int = zdc.rand(bounds=(0, 31), default=0)
        id2: int = zdc.rand(bounds=(0, 31), default=0)
        id3: int = zdc.rand(bounds=(0, 31), default=0)
        
        @zdc.constraint
        def bounds_check(self):
            self.normal_rand >= 10
            self.normal_rand <= 90
        
        @zdc.constraint
        def cyclic_valid(self):
            self.cyclic_rand < 12
        
        @zdc.constraint
        def unique_ids(self):
            zdc.unique([self.id1, self.id2, self.id3])
    
    # Extract everything
    rand_fields = zdc.extract_rand_fields(ComplexClass)
    assert len(rand_fields) == 6
    
    # Check field kinds
    normal = [f for f in rand_fields if f['name'] == 'normal_rand'][0]
    assert normal['kind'] == 'rand'
    
    cyclic = [f for f in rand_fields if f['name'] == 'cyclic_rand'][0]
    assert cyclic['kind'] == 'randc'
    
    array = [f for f in rand_fields if f['name'] == 'array_rand'][0]
    assert 'size' in array
    assert array['size'] == 8
    
    # Parse constraints
    parser = zdc.ConstraintParser()
    constraints = parser.extract_constraints(ComplexClass)
    assert len(constraints) == 3
    
    # Check unique constraint
    unique = [c for c in constraints if c['name'] == 'unique_ids'][0]
    assert unique['exprs'][0]['type'] == 'unique'
    assert len(unique['exprs'][0]['vars']) == 3
    
    # Check bounds constraint has multiple statements
    bounds = [c for c in constraints if c['name'] == 'bounds_check'][0]
    assert len(bounds['exprs']) == 2


def test_parser_handles_complex_expressions():
    """Test parser with nested and complex expressions."""
    
    @zdc.dataclass
    class Complex:
        a: int = zdc.rand(default=0)
        b: int = zdc.rand(default=0)
        c: int = zdc.rand(default=0)
        
        @zdc.constraint
        def complex_expr(self):
            ((self.a + self.b) * 2) <= (self.c - 5)
            (self.a > 0) and (self.b > 0) or (self.c > 100)
    
    parser = zdc.ConstraintParser()
    constraints = parser.extract_constraints(Complex)
    
    assert len(constraints) == 1
    assert len(constraints[0]['exprs']) == 2
    
    # First expression should be a comparison with nested arithmetic
    expr1 = constraints[0]['exprs'][0]
    assert expr1['type'] == 'compare'
    assert expr1['left']['type'] == 'bin_op'
    
    # Second expression should be nested boolean operations
    expr2 = constraints[0]['exprs'][1]
    assert expr2['type'] == 'bool_op'


def test_extract_metadata_completeness():
    """Test that all metadata is preserved through parsing."""
    
    @zdc.dataclass
    class WithMetadata:
        bounded: int = zdc.rand(bounds=(10, 20), default=15)
        sized_array: int = zdc.rand(size=16, default=0)
        cyclic: int = zdc.randc(bounds=(0, 7), default=0)
        
        @zdc.constraint
        def c1(self):
            self.bounded > 12
        
        @zdc.constraint.generic
        def c2(self):
            self.cyclic in [0, 2, 4, 6]
    
    # Check field metadata preservation
    rand_fields = zdc.extract_rand_fields(WithMetadata)
    
    bounded = [f for f in rand_fields if f['name'] == 'bounded'][0]
    assert bounded['kind'] == 'rand'
    assert bounded['bounds'] == (10, 20)
    
    sized = [f for f in rand_fields if f['name'] == 'sized_array'][0]
    assert sized['size'] == 16
    
    cyclic = [f for f in rand_fields if f['name'] == 'cyclic'][0]
    assert cyclic['kind'] == 'randc'
    assert cyclic['bounds'] == (0, 7)
    
    # Check constraint metadata preservation
    parser = zdc.ConstraintParser()
    constraints = parser.extract_constraints(WithMetadata)
    
    c1 = [c for c in constraints if c['name'] == 'c1'][0]
    assert c1['kind'] == 'fixed'
    
    c2 = [c for c in constraints if c['name'] == 'c2'][0]
    assert c2['kind'] == 'generic'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
