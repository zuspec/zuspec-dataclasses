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
"""Tests for constraint decorators, helpers, and field functions."""
import pytest
import zuspec.dataclasses as zdc


def test_constraint_decorator():
    """Test that @constraint decorator marks methods correctly."""
    @zdc.dataclass
    class Simple:
        x: int = 0
        
        @zdc.constraint
        def c1(self):
            self.x < 10
    
    # Check that the method has the constraint marker
    assert hasattr(Simple.c1, '_is_constraint')
    assert Simple.c1._is_constraint is True
    assert Simple.c1._constraint_kind == 'fixed'


def test_constraint_generic_decorator():
    """Test that @constraint.generic decorator marks methods correctly."""
    @zdc.dataclass
    class Simple:
        x: int = 0
        
        @zdc.constraint.generic
        def c1(self):
            self.x < 10
    
    # Check that the method has the constraint marker
    assert hasattr(Simple.c1, '_is_constraint')
    assert Simple.c1._is_constraint is True
    assert Simple.c1._constraint_kind == 'generic'


def test_multiple_constraints():
    """Test class with multiple constraints."""
    @zdc.dataclass
    class Transaction:
        addr: int = 0
        data: int = 0
        
        @zdc.constraint
        def addr_valid(self):
            self.addr < 256
        
        @zdc.constraint
        def data_valid(self):
            self.data >= 0
        
        @zdc.constraint.generic
        def addr_low(self):
            self.addr < 128
    
    # Check all constraints are marked
    assert hasattr(Transaction.addr_valid, '_is_constraint')
    assert hasattr(Transaction.data_valid, '_is_constraint')
    assert hasattr(Transaction.addr_low, '_is_constraint')
    
    assert Transaction.addr_valid._constraint_kind == 'fixed'
    assert Transaction.data_valid._constraint_kind == 'fixed'
    assert Transaction.addr_low._constraint_kind == 'generic'


def test_rand_field():
    """Test rand() field function."""
    @zdc.dataclass
    class Packet:
        length: int = zdc.rand(bounds=(64, 1500), default=64)
    
    # Check field metadata
    fields = {f.name: f for f in Packet.__dataclass_fields__.values()}
    assert 'length' in fields
    
    metadata = fields['length'].metadata
    assert metadata.get('rand') is True
    assert metadata.get('rand_kind') == 'rand'
    assert metadata.get('bounds') == (64, 1500)
    
    # Check default value
    pkt = Packet()
    assert pkt.length == 64


def test_randc_field():
    """Test randc() field function."""
    @zdc.dataclass
    class TestSequence:
        test_id: int = zdc.randc(bounds=(0, 15), default=0)
    
    # Check field metadata
    fields = {f.name: f for f in TestSequence.__dataclass_fields__.values()}
    assert 'test_id' in fields
    
    metadata = fields['test_id'].metadata
    assert metadata.get('rand') is True
    assert metadata.get('rand_kind') == 'randc'
    assert metadata.get('bounds') == (0, 15)
    
    # Check default value
    seq = TestSequence()
    assert seq.test_id == 0


def test_rand_array_field():
    """Test rand() with array size."""
    @zdc.dataclass
    class Memory:
        data: int = zdc.rand(size=16, default=0)
    
    # Check field metadata
    fields = {f.name: f for f in Memory.__dataclass_fields__.values()}
    assert 'data' in fields
    
    metadata = fields['data'].metadata
    assert metadata.get('rand') is True
    assert metadata.get('size') == 16


def test_implies_helper():
    """Test implies() helper function."""
    result = zdc.implies(True, False)
    
    # Check that it returns a marker object
    from zuspec.dataclasses.constraint_helpers import _ImpliesExpr
    assert isinstance(result, _ImpliesExpr)
    assert result.antecedent is True
    assert result.consequent is False


def test_dist_helper():
    """Test dist() helper function."""
    var = "test_var"
    weights = {0: 40, 1: 30, 2: 20, 3: 10}
    result = zdc.dist(var, weights)
    
    # Check that it returns a marker object
    from zuspec.dataclasses.constraint_helpers import _DistExpr
    assert isinstance(result, _DistExpr)
    assert result.var == var
    assert result.weights == weights


def test_unique_helper():
    """Test unique() helper function."""
    vars = ["var1", "var2", "var3"]
    result = zdc.unique(vars)
    
    # Check that it returns a marker object
    from zuspec.dataclasses.constraint_helpers import _UniqueExpr
    assert isinstance(result, _UniqueExpr)
    assert result.vars == vars


def test_solve_order_helper():
    """Test solve_order() helper function."""
    var1, var2, var3 = "v1", "v2", "v3"
    result = zdc.solve_order(var1, var2, var3)
    
    # Check that it returns a marker object
    from zuspec.dataclasses.constraint_helpers import _SolveOrderExpr
    assert isinstance(result, _SolveOrderExpr)
    assert result.vars == (var1, var2, var3)


def test_complete_example():
    """Test a complete example with constraints and rand fields."""
    @zdc.dataclass
    class Transaction:
        addr: int = zdc.rand(bounds=(0, 255), default=0)
        data: int = zdc.rand(bounds=(0, 255), default=0)
        read_enable: int = zdc.rand(default=0)
        write_enable: int = zdc.rand(default=0)
        
        @zdc.constraint
        def not_both(self):
            # Can't read and write simultaneously
            not (self.read_enable and self.write_enable)
        
        @zdc.constraint
        def addr_aligned(self):
            self.addr % 4 == 0
        
        @zdc.constraint.generic
        def addr_low(self):
            self.addr < 128
    
    # Verify the class was created
    txn = Transaction()
    assert txn.addr == 0
    assert txn.data == 0
    
    # Verify constraints are marked
    assert hasattr(Transaction.not_both, '_is_constraint')
    assert hasattr(Transaction.addr_aligned, '_is_constraint')
    assert hasattr(Transaction.addr_low, '_is_constraint')
    
    assert Transaction.not_both._constraint_kind == 'fixed'
    assert Transaction.addr_low._constraint_kind == 'generic'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
