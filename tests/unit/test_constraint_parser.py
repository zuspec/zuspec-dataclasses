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
"""Tests for constraint AST parser."""
import pytest
import zuspec.dataclasses as zdc


def test_parse_simple_comparison():
    """Test parsing simple comparison constraints."""
    @zdc.dataclass
    class Simple:
        x: int = zdc.rand(default=0)
        
        @zdc.constraint
        def c1(self):
            self.x < 10
    
    parser = zdc.ConstraintParser()
    constraints = parser.extract_constraints(Simple)
    
    assert len(constraints) == 1
    assert constraints[0]['name'] == 'c1'
    assert constraints[0]['kind'] == 'fixed'
    
    exprs = constraints[0]['exprs']
    assert len(exprs) == 1
    assert exprs[0]['type'] == 'compare'
    assert exprs[0]['ops'] == ['<']
    assert exprs[0]['left']['type'] == 'attribute'
    assert exprs[0]['left']['attr'] == 'x'
    assert exprs[0]['comparators'][0]['type'] == 'constant'
    assert exprs[0]['comparators'][0]['value'] == 10


def test_parse_multiple_comparisons():
    """Test parsing chained comparisons."""
    @zdc.dataclass
    class Range:
        x: int = zdc.rand(default=0)
        
        @zdc.constraint
        def bounds(self):
            0 <= self.x < 100
    
    parser = zdc.ConstraintParser()
    constraints = parser.extract_constraints(Range)
    
    exprs = constraints[0]['exprs']
    assert len(exprs) == 1
    assert exprs[0]['type'] == 'compare'
    assert exprs[0]['ops'] == ['<=', '<']
    assert len(exprs[0]['comparators']) == 2


def test_parse_boolean_operators():
    """Test parsing boolean and/or operators."""
    @zdc.dataclass
    class Logic:
        a: int = zdc.rand(default=0)
        b: int = zdc.rand(default=0)
        
        @zdc.constraint
        def both(self):
            (self.a > 0) and (self.b > 0)
        
        @zdc.constraint
        def either(self):
            (self.a > 10) or (self.b > 10)
    
    parser = zdc.ConstraintParser()
    constraints = parser.extract_constraints(Logic)
    
    # Find the 'both' constraint
    both = [c for c in constraints if c['name'] == 'both'][0]
    expr = both['exprs'][0]
    assert expr['type'] == 'bool_op'
    assert expr['op'] == 'and'
    assert len(expr['values']) == 2
    
    # Find the 'either' constraint
    either = [c for c in constraints if c['name'] == 'either'][0]
    expr = either['exprs'][0]
    assert expr['type'] == 'bool_op'
    assert expr['op'] == 'or'


def test_parse_unary_not():
    """Test parsing not operator."""
    @zdc.dataclass
    class Logic:
        flag: int = zdc.rand(default=0)
        
        @zdc.constraint
        def negation(self):
            not self.flag
    
    parser = zdc.ConstraintParser()
    constraints = parser.extract_constraints(Logic)
    
    expr = constraints[0]['exprs'][0]
    assert expr['type'] == 'unary_op'
    assert expr['op'] == 'not'
    assert expr['operand']['type'] == 'attribute'


def test_parse_arithmetic():
    """Test parsing arithmetic expressions."""
    @zdc.dataclass
    class Math:
        a: int = zdc.rand(default=0)
        b: int = zdc.rand(default=0)
        
        @zdc.constraint
        def sum_constraint(self):
            self.a + self.b < 100
    
    parser = zdc.ConstraintParser()
    constraints = parser.extract_constraints(Math)
    
    expr = constraints[0]['exprs'][0]
    assert expr['type'] == 'compare'
    
    left = expr['left']
    assert left['type'] == 'bin_op'
    assert left['op'] == '+'
    assert left['left']['attr'] == 'a'
    assert left['right']['attr'] == 'b'


def test_parse_implies():
    """Test parsing implies helper."""
    @zdc.dataclass
    class Imply:
        addr_type: int = zdc.rand(default=0)
        addr: int = zdc.rand(default=0)
        
        @zdc.constraint
        def type_implies_range(self):
            zdc.implies(self.addr_type == 0, self.addr < 16)
    
    parser = zdc.ConstraintParser()
    constraints = parser.extract_constraints(Imply)
    
    expr = constraints[0]['exprs'][0]
    assert expr['type'] == 'implies'
    assert expr['antecedent']['type'] == 'compare'
    assert expr['consequent']['type'] == 'compare'


def test_parse_dist():
    """Test parsing dist helper."""
    @zdc.dataclass
    class Distributed:
        pkt_type: int = zdc.rand(default=0)
        
        @zdc.constraint
        def type_dist(self):
            zdc.dist(self.pkt_type, {
                0: 40,
                1: 30,
                2: 20,
                3: 10
            })
    
    parser = zdc.ConstraintParser()
    constraints = parser.extract_constraints(Distributed)
    
    expr = constraints[0]['exprs'][0]
    assert expr['type'] == 'dist'
    assert expr['var']['attr'] == 'pkt_type'
    assert len(expr['weights']) == 4
    
    # Check weights
    weight_values = [w['weight']['value'] for w in expr['weights']]
    assert 40 in weight_values
    assert 30 in weight_values


def test_parse_unique():
    """Test parsing unique helper."""
    @zdc.dataclass
    class UniqueIDs:
        id1: int = zdc.rand(default=0)
        id2: int = zdc.rand(default=0)
        id3: int = zdc.rand(default=0)
        
        @zdc.constraint
        def all_unique(self):
            zdc.unique([self.id1, self.id2, self.id3])
    
    parser = zdc.ConstraintParser()
    constraints = parser.extract_constraints(UniqueIDs)
    
    expr = constraints[0]['exprs'][0]
    assert expr['type'] == 'unique'
    assert len(expr['vars']) == 3
    assert expr['vars'][0]['attr'] == 'id1'
    assert expr['vars'][1]['attr'] == 'id2'
    assert expr['vars'][2]['attr'] == 'id3'


def test_parse_solve_order():
    """Test parsing solve_order helper."""
    @zdc.dataclass
    class Ordered:
        a: int = zdc.rand(default=0)
        b: int = zdc.rand(default=0)
        c: int = zdc.rand(default=0)
        
        @zdc.constraint
        def order(self):
            zdc.solve_order(self.a, self.b, self.c)
    
    parser = zdc.ConstraintParser()
    constraints = parser.extract_constraints(Ordered)
    
    expr = constraints[0]['exprs'][0]
    assert expr['type'] == 'solve_order'
    assert len(expr['vars']) == 3


def test_parse_in_range():
    """Test parsing 'in range()' expressions."""
    @zdc.dataclass
    class InRange:
        addr: int = zdc.rand(default=0)
        
        @zdc.constraint
        def valid_range(self):
            self.addr in range(0, 16)
    
    parser = zdc.ConstraintParser()
    constraints = parser.extract_constraints(InRange)
    
    expr = constraints[0]['exprs'][0]
    assert expr['type'] == 'compare'
    assert expr['ops'] == ['in']
    
    # Check the range call
    range_expr = expr['comparators'][0]
    assert range_expr['type'] == 'range'
    assert range_expr['start']['value'] == 0
    assert range_expr['stop']['value'] == 16


def test_parse_subscript():
    """Test parsing array/bit subscript."""
    @zdc.dataclass
    class Subscripted:
        data: int = zdc.rand(default=0)
        
        @zdc.constraint
        def bit_check(self):
            self.data[0] == 0
    
    parser = zdc.ConstraintParser()
    constraints = parser.extract_constraints(Subscripted)
    
    expr = constraints[0]['exprs'][0]
    assert expr['type'] == 'compare'
    
    left = expr['left']
    assert left['type'] == 'subscript'
    assert left['value']['attr'] == 'data'
    assert left['slice']['type'] == 'index'
    assert left['slice']['value']['value'] == 0


def test_parse_multiple_statements():
    """Test parsing multiple constraint statements."""
    @zdc.dataclass
    class Multi:
        x: int = zdc.rand(default=0)
        y: int = zdc.rand(default=0)
        
        @zdc.constraint
        def multiple(self):
            self.x > 0
            self.y > 0
            self.x + self.y < 100
    
    parser = zdc.ConstraintParser()
    constraints = parser.extract_constraints(Multi)
    
    exprs = constraints[0]['exprs']
    assert len(exprs) == 3
    assert all(e['type'] == 'compare' for e in exprs)


def test_parse_generic_constraint():
    """Test parsing generic constraints."""
    @zdc.dataclass
    class WithGeneric:
        x: int = zdc.rand(default=0)
        
        @zdc.constraint
        def fixed_constraint(self):
            self.x >= 0
        
        @zdc.constraint.generic
        def generic_constraint(self):
            self.x < 100
    
    parser = zdc.ConstraintParser()
    constraints = parser.extract_constraints(WithGeneric)
    
    assert len(constraints) == 2
    
    fixed = [c for c in constraints if c['name'] == 'fixed_constraint'][0]
    assert fixed['kind'] == 'fixed'
    
    generic = [c for c in constraints if c['name'] == 'generic_constraint'][0]
    assert generic['kind'] == 'generic'


def test_extract_rand_fields():
    """Test extracting rand fields from a dataclass."""
    @zdc.dataclass
    class Transaction:
        addr: int = zdc.rand(bounds=(0, 255), default=0)
        data: int = zdc.rand(default=0)
        test_id: int = zdc.randc(bounds=(0, 15), default=0)
        normal_field: int = 0
    
    rand_fields = zdc.extract_rand_fields(Transaction)
    
    assert len(rand_fields) == 3
    
    # Check addr field
    addr = [f for f in rand_fields if f['name'] == 'addr'][0]
    assert addr['kind'] == 'rand'
    assert addr['bounds'] == (0, 255)
    
    # Check data field
    data = [f for f in rand_fields if f['name'] == 'data'][0]
    assert data['kind'] == 'rand'
    assert 'bounds' not in data
    
    # Check test_id field
    test_id = [f for f in rand_fields if f['name'] == 'test_id'][0]
    assert test_id['kind'] == 'randc'
    assert test_id['bounds'] == (0, 15)


def test_complete_parsing_example():
    """Test complete example with complex constraints."""
    @zdc.dataclass
    class Packet:
        length: int = zdc.rand(bounds=(64, 1500), default=64)
        header_len: int = zdc.rand(bounds=(20, 60), default=20)
        pkt_type: int = zdc.rand(bounds=(0, 3), default=0)
        
        @zdc.constraint
        def valid_length(self):
            self.length >= self.header_len
        
        @zdc.constraint
        def min_size(self):
            self.length >= 64
        
        @zdc.constraint
        def type_distribution(self):
            zdc.dist(self.pkt_type, {0: 40, 1: 30, 2: 20, 3: 10})
    
    parser = zdc.ConstraintParser()
    constraints = parser.extract_constraints(Packet)
    rand_fields = zdc.extract_rand_fields(Packet)
    
    # Check constraints
    assert len(constraints) == 3
    assert all(c['kind'] == 'fixed' for c in constraints)
    
    # Check rand fields
    assert len(rand_fields) == 3
    assert all(f['kind'] == 'rand' for f in rand_fields)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
