"""Test Port Binding Validation (Phase 5)"""
import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.data_model_factory import DataModelFactory


def test_input_output_fields_create_fieldinout():
    """Test that input/output fields are recognized as FieldInOut"""
    
    @zdc.dataclass
    class SimplePort(zdc.Component):
        clock : zdc.bit = zdc.input()
        data_out : zdc.bit8 = zdc.output()
        data_in : zdc.bit8 = zdc.input()
    
    factory = DataModelFactory()
    ctx = factory.build(SimplePort)
    dm = ctx.type_m[SimplePort.__qualname__]
    
    # Check that fields are FieldInOut
    from zuspec.dataclasses.dm.fields import FieldInOut
    
    clock_field = dm.fields[0]
    assert isinstance(clock_field, FieldInOut)
    assert clock_field.is_out == False  # Input
    
    data_out_field = dm.fields[1]
    assert isinstance(data_out_field, FieldInOut)
    assert data_out_field.is_out == True  # Output
    
    data_in_field = dm.fields[2]
    assert isinstance(data_in_field, FieldInOut)
    assert data_in_field.is_out == False  # Input


def test_constant_binding_allowed():
    """Test that binding constants to inputs is allowed"""
    
    @zdc.dataclass
    class Child(zdc.Component):
        enable : zdc.bit = zdc.input()
        data : zdc.bit8 = zdc.input()
    
    @zdc.dataclass
    class Parent(zdc.Component):
        child : Child = zdc.field()
        
        @zdc.sync(clock=lambda s: s.child)  # Just to make it have sync processes
        def _proc(self):
            pass
        
        def __bind__(self):
            return {
                self.child.enable: 1,  # Tie enable high
                self.child.data: 0     # Tie data to 0
            }
    
    # Should not raise an error
    factory = DataModelFactory()
    ctx = factory.build(Parent)
    assert ctx is not None


def test_binding_validation_basics():
    """Test that binding validation runs for components with sync/comb processes"""
    
    @zdc.dataclass
    class Child(zdc.Component):
        data : zdc.bit8 = zdc.input()
    
    @zdc.dataclass
    class Parent(zdc.Component):
        child : Child = zdc.field()
        local_sig : zdc.bit8 = zdc.field()
        
        @zdc.sync(clock=lambda s: s.child)  # Make it have sync processes
        def _proc(self):
            pass
        
        def __bind__(self):
            return {
                self.child.data: self.local_sig  # Normal binding
            }
    
    # Should work fine
    factory = DataModelFactory()
    ctx = factory.build(Parent)
    assert ctx is not None


def test_non_sync_comb_component_no_validation():
    """Test that components without sync/comb processes don't get binding validation"""
    
    @zdc.dataclass
    class SimpleClass(zdc.Component):
        a : int = zdc.field()
        b : int = zdc.field()
        
        def __bind__(self):
            # Even if this looks wrong, it shouldn't be validated
            # because this component doesn't have @sync/@comb processes
            return {}
    
    # Should not raise
    factory = DataModelFactory()
    ctx = factory.build(SimpleClass)
    assert ctx is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
