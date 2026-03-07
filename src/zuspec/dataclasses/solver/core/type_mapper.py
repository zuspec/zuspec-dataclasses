"""Type system integration - maps IR data types to solver domains"""

from typing import Optional, Union
from zuspec.dataclasses.ir.data_type import DataType, DataTypeInt, DataTypeEnum, DataTypeUptr, DataTypeArray
from .domain import Domain, IntDomain, EnumDomain, BitVectorDomain


class TypeMapper:
    """Maps IR data types to solver domain types"""
    
    @staticmethod
    def to_domain(datatype: DataType, use_bitvector: bool = True) -> Domain:
        """
        Convert an IR DataType to a solver Domain.
        
        Args:
            datatype: IR data type to convert
            use_bitvector: If True, use BitVectorDomain for integers (with wrapping)
                          If False, use plain IntDomain
        
        Returns:
            Domain object representing the type's value space
            
        Raises:
            TypeError: If datatype cannot be converted to a domain
        """
        if isinstance(datatype, DataTypeInt):
            return TypeMapper._int_to_domain(datatype, use_bitvector)
        elif isinstance(datatype, DataTypeUptr):
            return TypeMapper._uptr_to_domain(datatype, use_bitvector)
        elif isinstance(datatype, DataTypeEnum):
            return TypeMapper._enum_to_domain(datatype)
        else:
            raise TypeError(
                f"Cannot convert {datatype.__class__.__name__} to solver domain. "
                f"Only int, uptr, and enum types are supported."
            )
    
    @staticmethod
    def _int_to_domain(datatype: DataTypeInt, use_bitvector: bool) -> Union[IntDomain, BitVectorDomain]:
        """Convert DataTypeInt to IntDomain or BitVectorDomain"""
        bits = datatype.bits
        signed = datatype.signed
        
        # Validate bit width
        if bits <= 0:
            raise ValueError(f"Invalid bit width: {bits}. Must be positive.")
        if bits > 64:
            raise ValueError(f"Bit width {bits} exceeds maximum supported width of 64 bits")
        
        # Calculate domain bounds
        if signed:
            min_val = -(2 ** (bits - 1))
            max_val = 2 ** (bits - 1) - 1
        else:
            min_val = 0
            max_val = 2 ** bits - 1
        
        # Create domain with full range
        intervals = [(min_val, max_val)]
        
        if use_bitvector:
            return BitVectorDomain(intervals, bits, signed)
        else:
            return IntDomain(intervals, bits, signed)
    
    @staticmethod
    def _uptr_to_domain(datatype: DataTypeUptr, use_bitvector: bool) -> Union[IntDomain, BitVectorDomain]:
        """Convert DataTypeUptr to IntDomain or BitVectorDomain"""
        # Get platform pointer size
        bits = DataTypeUptr.get_platform_width()
        
        # Uptr is always unsigned
        min_val = 0
        max_val = 2 ** bits - 1
        
        intervals = [(min_val, max_val)]
        
        if use_bitvector:
            return BitVectorDomain(intervals, bits, signed=False)
        else:
            return IntDomain(intervals, bits, signed=False)
    
    @staticmethod
    def _enum_to_domain(datatype: DataTypeEnum) -> EnumDomain:
        """Convert DataTypeEnum to EnumDomain"""
        # For enums, we need to extract the possible values
        # The py_type field should contain the Python enum type
        if datatype.py_type is None:
            # If no py_type, create empty domain
            # This will be populated later when we know the values
            return EnumDomain(set(), datatype.py_type)
        
        # Extract integer values from Python enum
        try:
            values = {member.value for member in datatype.py_type}
            return EnumDomain(values, datatype.py_type)
        except (AttributeError, TypeError):
            # If py_type is not a proper enum, create empty domain
            return EnumDomain(set(), datatype.py_type)
    
    @staticmethod
    def get_bit_width(datatype: DataType) -> int:
        """
        Get the bit width of a data type.
        
        Args:
            datatype: IR data type
            
        Returns:
            Bit width of the type
            
        Raises:
            TypeError: If type doesn't have a bit width
        """
        if isinstance(datatype, DataTypeInt):
            return datatype.bits
        elif isinstance(datatype, DataTypeUptr):
            return DataTypeUptr.get_platform_width()
        else:
            raise TypeError(f"{datatype.__class__.__name__} does not have a bit width")
    
    @staticmethod
    def is_signed(datatype: DataType) -> bool:
        """
        Check if a data type is signed.
        
        Args:
            datatype: IR data type
            
        Returns:
            True if signed, False if unsigned
            
        Raises:
            TypeError: If type doesn't have signedness
        """
        if isinstance(datatype, DataTypeInt):
            return datatype.signed
        elif isinstance(datatype, DataTypeUptr):
            return False  # Uptr is always unsigned
        else:
            raise TypeError(f"{datatype.__class__.__name__} does not have signedness")
    
    @staticmethod
    def can_convert_to_domain(datatype: DataType) -> bool:
        """
        Check if a data type can be converted to a solver domain.
        
        Args:
            datatype: IR data type
            
        Returns:
            True if type can be converted to a domain
        """
        return isinstance(datatype, (DataTypeInt, DataTypeEnum, DataTypeUptr)) or (
            isinstance(datatype, DataTypeArray) and TypeMapper.can_convert_to_domain(datatype.element_type)
        )


class TypeInference:
    """Type inference for expressions"""
    
    @staticmethod
    def infer_result_type(op: str, left_type: DataType, right_type: Optional[DataType] = None) -> DataType:
        """
        Infer the result type of an operation.
        
        Args:
            op: Operation name (e.g., 'add', 'lt', 'and')
            left_type: Type of left operand
            right_type: Type of right operand (None for unary operations)
            
        Returns:
            Result type of the operation
            
        Raises:
            TypeError: If operation is not valid for given types
        """
        # Comparison operations always return bool (represented as 1-bit int)
        if op in ('lt', 'le', 'gt', 'ge', 'eq', 'ne'):
            return DataTypeInt(bits=1, signed=False)
        
        # Boolean operations return bool
        if op in ('and', 'or', 'not'):
            return DataTypeInt(bits=1, signed=False)
        
        # Unary operations
        if right_type is None:
            if op == 'neg':
                # Negation of unsigned should produce signed
                if isinstance(left_type, DataTypeInt) and not left_type.signed:
                    return DataTypeInt(bits=left_type.bits + 1, signed=True)
                return left_type
            elif op == 'invert':
                return left_type
            else:
                raise TypeError(f"Unknown unary operation: {op}")
        
        # Binary arithmetic operations
        if isinstance(left_type, DataTypeInt) and isinstance(right_type, DataTypeInt):
            return TypeInference._infer_int_result_type(op, left_type, right_type)
        
        # Enum comparisons
        if isinstance(left_type, DataTypeEnum) and isinstance(right_type, DataTypeEnum):
            if op in ('eq', 'ne'):
                return DataTypeInt(bits=1, signed=False)
            raise TypeError(f"Operation {op} not supported for enum types")
        
        raise TypeError(
            f"Operation {op} not supported for types "
            f"{left_type.__class__.__name__} and {right_type.__class__.__name__}"
        )
    
    @staticmethod
    def _infer_int_result_type(op: str, left: DataTypeInt, right: DataTypeInt) -> DataTypeInt:
        """Infer result type for integer operations"""
        # For most operations, result width is max of operands
        result_width = max(left.bits, right.bits)
        
        # Result is signed if either operand is signed
        result_signed = left.signed or right.signed
        
        # Special cases
        if op in ('add', 'sub'):
            # Addition/subtraction may need extra bit to prevent overflow
            result_width = max(left.bits, right.bits) + 1
        elif op == 'mult':
            # Multiplication width is sum of operand widths
            result_width = left.bits + right.bits
        elif op in ('shl', 'shr'):
            # Shift result has width of left operand
            result_width = left.bits
            result_signed = left.signed
        elif op in ('div', 'mod'):
            # Division/modulo result has width of dividend
            result_width = left.bits
            result_signed = left.signed or right.signed
        
        # Cap at 64 bits
        result_width = min(result_width, 64)
        
        return DataTypeInt(bits=result_width, signed=result_signed)
    
    @staticmethod
    def need_type_coercion(left_type: DataType, right_type: DataType) -> bool:
        """
        Check if type coercion is needed for two operands.
        
        Args:
            left_type: Type of left operand
            right_type: Type of right operand
            
        Returns:
            True if coercion is needed
        """
        # Same types don't need coercion
        if type(left_type) != type(right_type):
            return True
        
        # For integers, check if widths or signedness differ
        if isinstance(left_type, DataTypeInt) and isinstance(right_type, DataTypeInt):
            return left_type.bits != right_type.bits or left_type.signed != right_type.signed
        
        return False
    
    @staticmethod
    def coerce_types(left_type: DataType, right_type: DataType) -> tuple[DataType, DataType]:
        """
        Coerce two types to a common type.
        
        Args:
            left_type: Type of left operand
            right_type: Type of right operand
            
        Returns:
            Tuple of (coerced_left_type, coerced_right_type)
            
        Raises:
            TypeError: If types cannot be coerced
        """
        # Both integers - coerce to larger width and signed if either is signed
        if isinstance(left_type, DataTypeInt) and isinstance(right_type, DataTypeInt):
            result_width = max(left_type.bits, right_type.bits)
            result_signed = left_type.signed or right_type.signed
            common_type = DataTypeInt(bits=result_width, signed=result_signed)
            return (common_type, common_type)
        
        # Cannot coerce incompatible types
        raise TypeError(
            f"Cannot coerce types {left_type.__class__.__name__} "
            f"and {right_type.__class__.__name__}"
        )
