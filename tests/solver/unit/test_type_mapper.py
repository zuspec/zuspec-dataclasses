"""Tests for TypeMapper and TypeInference"""

import pytest
from enum import Enum as PyEnum
from zuspec.ir.core.data_type import DataTypeInt, DataTypeEnum, DataTypeUptr
from zuspec.dataclasses.solver.core.type_mapper import TypeMapper, TypeInference
from zuspec.dataclasses.solver.core.domain import IntDomain, BitVectorDomain, EnumDomain


class TestTypeMapper:
    """Test TypeMapper functionality"""
    
    def test_int_to_intdomain(self):
        """Test converting DataTypeInt to IntDomain"""
        dt = DataTypeInt(bits=8, signed=False)
        domain = TypeMapper.to_domain(dt, use_bitvector=False)
        
        assert isinstance(domain, IntDomain)
        assert domain.width == 8
        assert not domain.signed
        assert domain.size() == 256
        assert list(domain.values())[0] == 0
        assert list(domain.values())[-1] == 255
    
    def test_int_to_bitvectordomain(self):
        """Test converting DataTypeInt to BitVectorDomain"""
        dt = DataTypeInt(bits=8, signed=False)
        domain = TypeMapper.to_domain(dt, use_bitvector=True)
        
        assert isinstance(domain, BitVectorDomain)
        assert domain.width == 8
        assert not domain.signed
        assert domain.size() == 256
    
    def test_signed_int_to_domain(self):
        """Test converting signed DataTypeInt"""
        dt = DataTypeInt(bits=8, signed=True)
        domain = TypeMapper.to_domain(dt)
        
        assert domain.width == 8
        assert domain.signed
        assert domain.size() == 256
        values = list(domain.values())
        assert values[0] == -128
        assert values[-1] == 127
    
    def test_various_bit_widths(self):
        """Test various bit widths"""
        for bits in [1, 4, 8, 16, 32, 64]:
            dt = DataTypeInt(bits=bits, signed=False)
            domain = TypeMapper.to_domain(dt)
            
            assert domain.width == bits
            assert domain.size() == 2 ** bits
    
    def test_invalid_bit_width_zero(self):
        """Test that zero bit width raises error"""
        dt = DataTypeInt(bits=0, signed=False)
        
        with pytest.raises(ValueError, match="Invalid bit width"):
            TypeMapper.to_domain(dt)
    
    def test_invalid_bit_width_negative(self):
        """Test that negative bit width raises error"""
        dt = DataTypeInt(bits=-1, signed=False)
        
        with pytest.raises(ValueError, match="Invalid bit width"):
            TypeMapper.to_domain(dt)
    
    def test_excessive_bit_width(self):
        """Test that > 64 bit width raises error"""
        dt = DataTypeInt(bits=128, signed=False)
        
        with pytest.raises(ValueError, match="exceeds maximum"):
            TypeMapper.to_domain(dt)
    
    def test_uptr_to_domain(self):
        """Test converting DataTypeUptr to domain"""
        dt = DataTypeUptr()
        domain = TypeMapper.to_domain(dt)
        
        assert isinstance(domain, (IntDomain, BitVectorDomain))
        assert not domain.signed
        # Should be platform width (32 or 64 typically)
        assert domain.width in [32, 64]
    
    def test_enum_to_domain_with_py_type(self):
        """Test converting DataTypeEnum with Python enum type"""
        # Create a Python enum
        class Color(PyEnum):
            RED = 1
            GREEN = 2
            BLUE = 3
        
        dt = DataTypeEnum(py_type=Color)
        domain = TypeMapper.to_domain(dt)
        
        assert isinstance(domain, EnumDomain)
        assert domain.size() == 3
        assert set(domain.values()) == {1, 2, 3}
    
    def test_enum_to_domain_without_py_type(self):
        """Test converting DataTypeEnum without Python enum type"""
        dt = DataTypeEnum(py_type=None)
        domain = TypeMapper.to_domain(dt)
        
        assert isinstance(domain, EnumDomain)
        assert domain.is_empty()
    
    def test_get_bit_width(self):
        """Test getting bit width from data types"""
        dt_int = DataTypeInt(bits=16, signed=True)
        assert TypeMapper.get_bit_width(dt_int) == 16
        
        dt_uptr = DataTypeUptr()
        width = TypeMapper.get_bit_width(dt_uptr)
        assert width in [32, 64]
    
    def test_get_bit_width_invalid_type(self):
        """Test getting bit width from non-integer type raises error"""
        dt_enum = DataTypeEnum()
        
        with pytest.raises(TypeError):
            TypeMapper.get_bit_width(dt_enum)
    
    def test_is_signed(self):
        """Test checking if type is signed"""
        dt_signed = DataTypeInt(bits=8, signed=True)
        assert TypeMapper.is_signed(dt_signed)
        
        dt_unsigned = DataTypeInt(bits=8, signed=False)
        assert not TypeMapper.is_signed(dt_unsigned)
        
        dt_uptr = DataTypeUptr()
        assert not TypeMapper.is_signed(dt_uptr)
    
    def test_is_signed_invalid_type(self):
        """Test checking signedness of non-integer type raises error"""
        dt_enum = DataTypeEnum()
        
        with pytest.raises(TypeError):
            TypeMapper.is_signed(dt_enum)
    
    def test_can_convert_to_domain(self):
        """Test checking if type can be converted to domain"""
        assert TypeMapper.can_convert_to_domain(DataTypeInt(bits=8, signed=False))
        assert TypeMapper.can_convert_to_domain(DataTypeEnum())
        assert TypeMapper.can_convert_to_domain(DataTypeUptr())


class TestTypeInference:
    """Test TypeInference functionality"""
    
    def test_comparison_returns_bool(self):
        """Test that comparison operations return bool type"""
        dt_left = DataTypeInt(bits=8, signed=False)
        dt_right = DataTypeInt(bits=8, signed=False)
        
        for op in ['lt', 'le', 'gt', 'ge', 'eq', 'ne']:
            result = TypeInference.infer_result_type(op, dt_left, dt_right)
            assert isinstance(result, DataTypeInt)
            assert result.bits == 1
            assert not result.signed
    
    def test_boolean_operations_return_bool(self):
        """Test that boolean operations return bool type"""
        dt = DataTypeInt(bits=1, signed=False)
        
        # Binary operations
        for op in ['and', 'or']:
            result = TypeInference.infer_result_type(op, dt, dt)
            assert result.bits == 1
        
        # Unary operation
        result = TypeInference.infer_result_type('not', dt)
        assert result.bits == 1
    
    def test_addition_result_width(self):
        """Test that addition increases width by 1"""
        dt_left = DataTypeInt(bits=8, signed=False)
        dt_right = DataTypeInt(bits=8, signed=False)
        
        result = TypeInference.infer_result_type('add', dt_left, dt_right)
        assert isinstance(result, DataTypeInt)
        assert result.bits == 9  # 8 + 1
    
    def test_subtraction_result_width(self):
        """Test that subtraction increases width by 1"""
        dt_left = DataTypeInt(bits=8, signed=False)
        dt_right = DataTypeInt(bits=8, signed=False)
        
        result = TypeInference.infer_result_type('sub', dt_left, dt_right)
        assert result.bits == 9
    
    def test_multiplication_result_width(self):
        """Test that multiplication sums widths"""
        dt_left = DataTypeInt(bits=8, signed=False)
        dt_right = DataTypeInt(bits=4, signed=False)
        
        result = TypeInference.infer_result_type('mult', dt_left, dt_right)
        assert result.bits == 12  # 8 + 4
    
    def test_shift_result_width(self):
        """Test that shift preserves left operand width"""
        dt_left = DataTypeInt(bits=8, signed=False)
        dt_right = DataTypeInt(bits=3, signed=False)
        
        result = TypeInference.infer_result_type('shl', dt_left, dt_right)
        assert result.bits == 8
        
        result = TypeInference.infer_result_type('shr', dt_left, dt_right)
        assert result.bits == 8
    
    def test_result_signed_if_any_signed(self):
        """Test that result is signed if any operand is signed"""
        dt_signed = DataTypeInt(bits=8, signed=True)
        dt_unsigned = DataTypeInt(bits=8, signed=False)
        
        # Signed + unsigned = signed
        result = TypeInference.infer_result_type('add', dt_signed, dt_unsigned)
        assert result.signed
        
        # Unsigned + signed = signed
        result = TypeInference.infer_result_type('add', dt_unsigned, dt_signed)
        assert result.signed
    
    def test_negation_makes_unsigned_signed(self):
        """Test that negating unsigned produces signed with extra bit"""
        dt_unsigned = DataTypeInt(bits=8, signed=False)
        
        result = TypeInference.infer_result_type('neg', dt_unsigned)
        assert result.signed
        assert result.bits == 9  # Extra bit for sign
    
    def test_negation_keeps_signed(self):
        """Test that negating signed keeps it signed"""
        dt_signed = DataTypeInt(bits=8, signed=True)
        
        result = TypeInference.infer_result_type('neg', dt_signed)
        assert result.signed
        assert result.bits == 8
    
    def test_invert_preserves_type(self):
        """Test that bitwise invert preserves type"""
        dt = DataTypeInt(bits=8, signed=False)
        
        result = TypeInference.infer_result_type('invert', dt)
        assert result.bits == 8
        assert not result.signed
    
    def test_width_capped_at_64(self):
        """Test that result width is capped at 64 bits"""
        dt_left = DataTypeInt(bits=60, signed=False)
        dt_right = DataTypeInt(bits=60, signed=False)
        
        # Multiplication would be 120 bits, should cap at 64
        result = TypeInference.infer_result_type('mult', dt_left, dt_right)
        assert result.bits == 64
    
    def test_enum_comparison(self):
        """Test enum comparison operations"""
        dt_enum = DataTypeEnum()
        
        result = TypeInference.infer_result_type('eq', dt_enum, dt_enum)
        assert result.bits == 1
        
        result = TypeInference.infer_result_type('ne', dt_enum, dt_enum)
        assert result.bits == 1
    
    def test_enum_invalid_operation(self):
        """Test that non-comparison operations on enums raise error"""
        dt_enum = DataTypeEnum()
        
        with pytest.raises(TypeError, match="not supported for enum"):
            TypeInference.infer_result_type('add', dt_enum, dt_enum)
    
    def test_need_type_coercion_different_types(self):
        """Test that different types need coercion"""
        dt_int = DataTypeInt(bits=8, signed=False)
        dt_enum = DataTypeEnum()
        
        assert TypeInference.need_type_coercion(dt_int, dt_enum)
    
    def test_need_type_coercion_different_widths(self):
        """Test that different widths need coercion"""
        dt1 = DataTypeInt(bits=8, signed=False)
        dt2 = DataTypeInt(bits=16, signed=False)
        
        assert TypeInference.need_type_coercion(dt1, dt2)
    
    def test_need_type_coercion_different_signedness(self):
        """Test that different signedness needs coercion"""
        dt1 = DataTypeInt(bits=8, signed=True)
        dt2 = DataTypeInt(bits=8, signed=False)
        
        assert TypeInference.need_type_coercion(dt1, dt2)
    
    def test_no_coercion_needed_same_type(self):
        """Test that same types don't need coercion"""
        dt1 = DataTypeInt(bits=8, signed=False)
        dt2 = DataTypeInt(bits=8, signed=False)
        
        assert not TypeInference.need_type_coercion(dt1, dt2)
    
    def test_coerce_to_larger_width(self):
        """Test coercing to larger width"""
        dt1 = DataTypeInt(bits=8, signed=False)
        dt2 = DataTypeInt(bits=16, signed=False)
        
        coerced1, coerced2 = TypeInference.coerce_types(dt1, dt2)
        
        assert coerced1.bits == 16
        assert coerced2.bits == 16
        assert not coerced1.signed
    
    def test_coerce_to_signed_if_any_signed(self):
        """Test coercing to signed if any operand is signed"""
        dt1 = DataTypeInt(bits=8, signed=True)
        dt2 = DataTypeInt(bits=8, signed=False)
        
        coerced1, coerced2 = TypeInference.coerce_types(dt1, dt2)
        
        assert coerced1.signed
        assert coerced2.signed
    
    def test_coerce_incompatible_types_raises_error(self):
        """Test that coercing incompatible types raises error"""
        dt_int = DataTypeInt(bits=8, signed=False)
        dt_enum = DataTypeEnum()
        
        with pytest.raises(TypeError, match="Cannot coerce"):
            TypeInference.coerce_types(dt_int, dt_enum)
