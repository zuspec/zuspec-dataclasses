import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import zuspec.dataclasses as zdc
from zuspec.dataclasses.data_model_factory import DataModelFactory

def test_field_with_bounds_metadata():
    """Test that field with bounds parameter stores metadata correctly"""
    
    @zdc.dataclass
    class SimpleStruct(zdc.Struct):
        value: zdc.uint32_t = zdc.field(bounds=(0, 100))
    
    # Access field metadata via dataclass fields
    fields = SimpleStruct.__dataclass_fields__
    assert 'value' in fields
    
    field_info = fields['value']
    assert field_info.metadata is not None
    assert 'bounds' in field_info.metadata
    assert field_info.metadata['bounds'] == (0, 100)
    
    print("test_field_with_bounds_metadata PASSED")

def test_multiple_fields_with_bounds():
    """Test struct with multiple bounded fields"""
    
    @zdc.dataclass
    class DmaConfig(zdc.Struct):
        src: zdc.uint32_t = zdc.field(bounds=(0, 0xFFFF))
        dst: zdc.uint32_t = zdc.field(bounds=(0, 0xFFFF))
        xfer_sz: zdc.uint8_t = zdc.field(bounds=(1, 128))
        xfer_tot: zdc.uint16_t = zdc.field(bounds=(1, 1024))
    
    fields = DmaConfig.__dataclass_fields__
    
    # Check src field
    assert 'bounds' in fields['src'].metadata
    assert fields['src'].metadata['bounds'] == (0, 0xFFFF)
    
    # Check dst field
    assert 'bounds' in fields['dst'].metadata
    assert fields['dst'].metadata['bounds'] == (0, 0xFFFF)
    
    # Check xfer_sz field
    assert 'bounds' in fields['xfer_sz'].metadata
    assert fields['xfer_sz'].metadata['bounds'] == (1, 128)
    
    # Check xfer_tot field
    assert 'bounds' in fields['xfer_tot'].metadata
    assert fields['xfer_tot'].metadata['bounds'] == (1, 1024)
    
    print("test_multiple_fields_with_bounds PASSED")

def test_data_model_captures_bounds():
    """Test that data model factory can build a struct with bounds metadata"""
    
    @zdc.dataclass
    class TestStruct(zdc.Struct):
        addr: zdc.uint32_t = zdc.field(bounds=(0x1000, 0x2000))
        size: zdc.uint16_t = zdc.field(bounds=(1, 256))
    
    # Verify bounds are in dataclass metadata first
    fields = TestStruct.__dataclass_fields__
    assert 'bounds' in fields['addr'].metadata
    assert 'bounds' in fields['size'].metadata
    
    # Create data model - should complete without errors
    factory = DataModelFactory()
    context = factory.build(TestStruct)
    
    # Verify the struct was added to context
    assert len(context.type_m) > 0
    
    # Get the struct (may have qualified name)
    dtype = None
    for key, val in context.type_m.items():
        if 'TestStruct' in key:
            dtype = val
            break
    
    assert dtype is not None, f"TestStruct not found in {list(context.type_m.keys())}"
    
    # Verify it has the expected fields (using .fields attribute)
    assert len(dtype.fields) == 2
    
    print("test_data_model_captures_bounds PASSED")

def test_field_without_bounds():
    """Test that fields without bounds don't have bounds metadata"""
    
    @zdc.dataclass
    class MixedStruct(zdc.Struct):
        bounded: zdc.uint32_t = zdc.field(bounds=(0, 100))
        unbounded: zdc.uint32_t = zdc.field()
    
    fields = MixedStruct.__dataclass_fields__
    
    # Bounded field should have bounds metadata
    assert 'bounds' in fields['bounded'].metadata
    
    # Unbounded field should not have bounds metadata (or have None)
    unbounded_meta = fields['unbounded'].metadata
    if unbounded_meta:
        assert 'bounds' not in unbounded_meta
    
    print("test_field_without_bounds PASSED")

def test_bounds_with_other_metadata():
    """Test bounds combined with other field metadata"""
    
    @zdc.dataclass
    class ComplexStruct(zdc.Struct):
        value: zdc.uint32_t = zdc.field(bounds=(10, 20), size=32)
    
    fields = ComplexStruct.__dataclass_fields__
    metadata = fields['value'].metadata
    
    # Both bounds and size should be in metadata
    assert 'bounds' in metadata
    assert 'size' in metadata
    assert metadata['bounds'] == (10, 20)
    assert metadata['size'] == 32
    
    print("test_bounds_with_other_metadata PASSED")

if __name__ == '__main__':
    test_field_with_bounds_metadata()
    test_multiple_fields_with_bounds()
    test_data_model_captures_bounds()
    test_field_without_bounds()
    test_bounds_with_other_metadata()
    print("\nAll field bounds tests PASSED!")
