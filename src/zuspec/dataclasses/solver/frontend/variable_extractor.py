"""Variable Extractor - extracts variables from IR structures"""

from typing import Dict, List, Optional, Set
from zuspec.dataclasses.ir.data_type import DataType, DataTypeStruct, DataTypeClass
from zuspec.dataclasses.ir.fields import Field
from ..core.variable import Variable, VarKind
from ..core.domain import Domain
from ..core.type_mapper import TypeMapper


class VariableExtractor:
    """Extracts solver variables from IR data structures"""
    
    def __init__(self):
        # Extracted variables: name -> Variable
        self.variables: Dict[str, Variable] = {}
        
        # Field index mapping: index -> name
        self.field_index_map: Dict[int, str] = {}
        
        # Array metadata for solution reconstruction: field_name -> {'size': N, 'element_names': [names]}
        self.array_metadata: Dict[str, dict] = {}
        
        # Type mapper for creating domains
        self.type_mapper = TypeMapper()
    
    def extract_from_struct(self, struct_type: DataTypeStruct, prefix: str = "") -> List[Variable]:
        """
        Extract variables from a struct or class type.
        
        Args:
            struct_type: IR struct/class type to extract from
            prefix: Optional prefix for nested field names (e.g., "parent.")
            
        Returns:
            List of extracted variables
        """
        extracted = []
        
        for idx, field in enumerate(struct_type.fields):
            vars = self._extract_from_field(field, idx, prefix)
            if vars is not None:
                if isinstance(vars, list):
                    extracted.extend(vars)
                else:
                    extracted.append(vars)
        
        return extracted
    
    def _extract_from_field(
        self, 
        field: Field, 
        index: int, 
        prefix: str
    ) -> Optional[Variable]:
        """
        Extract a variable from a single field (or multiple variables for arrays).
        
        Args:
            field: IR field to extract from
            index: Field index in parent struct
            prefix: Name prefix for nested fields
            
        Returns:
            Variable if field is rand/randc, List[Variable] for arrays, None otherwise
        """
        # Check if this is a randomizable type
        if not self.type_mapper.can_convert_to_domain(field.datatype):
            return None
        
        # Get field metadata - check for rand/randc markers
        rand_kind = self._get_rand_kind(field)
        
        if rand_kind is None:
            # Not a random variable
            return None
        
        # Check if this is an array field
        if field.is_array:
            return self._extract_array_field(field, index, prefix, rand_kind)
        
        # Build variable name
        var_name = f"{prefix}{field.name}" if prefix else field.name
        
        # Create domain from type
        domain = self.type_mapper.to_domain(field.datatype, use_bitvector=True)
        
        # Apply domain constraints if present
        domain = self._apply_domain(domain, field)
        
        # Determine variable kind
        if rand_kind == "randc":
            var_kind = VarKind.RANDC
        elif rand_kind == "rand":
            var_kind = VarKind.RAND
        else:
            var_kind = VarKind.RAND  # Default
        
        # Create variable
        variable = Variable(
            name=var_name,
            domain=domain,
            kind=var_kind
        )
        
        # Register variable
        self.variables[var_name] = variable
        self.field_index_map[index] = var_name
        
        return variable
    
    def _extract_array_field(
        self,
        field: Field,
        index: int,
        prefix: str,
        rand_kind: str
    ) -> List[Variable]:
        """
        Extract variables for an array field.
        
        For fixed-size: Creates N variables: field[0], field[1], ..., field[N-1]
        For variable-size: Creates max_size variables + length variable _length_field
        
        Args:
            field: IR field (must have size or max_size set)
            index: Field index in parent struct
            prefix: Name prefix for nested fields
            rand_kind: 'rand' or 'randc'
            
        Returns:
            List of variables (array elements + length variable for variable-size)
        """
        # Determine actual size to allocate
        if field.is_variable_size:
            actual_size = field.max_size if field.max_size else 32  # Default max
            assert actual_size is not None, f"Variable-size array {field.name} must have max_size"
        else:
            actual_size = field.size
            assert actual_size is not None, f"Fixed-size array {field.name} must have size"
        
        # Build base name
        base_name = f"{prefix}{field.name}" if prefix else field.name
        
        # Create domain from type
        domain = self.type_mapper.to_domain(field.datatype, use_bitvector=True)
        
        # Apply domain constraints if present
        domain = self._apply_domain(domain, field)
        
        # Determine variable kind
        if rand_kind == "randc":
            var_kind = VarKind.RANDC
        elif rand_kind == "rand":
            var_kind = VarKind.RAND
        else:
            var_kind = VarKind.RAND
        
        # Create variables list
        variables = []
        element_names = []
        
        # For variable-size arrays, create length variable first
        length_var_name = None
        if field.is_variable_size:
            length_var_name = f"_length_{base_name}"
            
            # Length domain: [0, max_size]
            # Use smallest power of 2 that can represent max_size
            from ..core.domain import IntDomain
            import math
            length_width = max(8, math.ceil(math.log2(actual_size + 1))) if actual_size > 0 else 8
            length_domain = IntDomain(intervals=[(0, actual_size)], width=length_width, signed=False)
            
            length_var = Variable(
                name=length_var_name,
                domain=length_domain,
                kind=var_kind
            )
            
            # Register length variable
            self.variables[length_var_name] = length_var
            variables.append(length_var)
        
        # Create actual_size variables for array elements
        for i in range(actual_size):
            var_name = f"{base_name}[{i}]"
            element_names.append(var_name)
            
            variable = Variable(
                name=var_name,
                domain=domain.copy(),  # Each element gets its own domain copy
                kind=var_kind
            )
            
            # Register variable
            self.variables[var_name] = variable
            variables.append(variable)
        
        # Store array metadata for solution reconstruction
        self.array_metadata[base_name] = {
            'size': actual_size,  # Max size for variable-size, actual size for fixed
            'element_names': element_names,
            'is_variable_size': field.is_variable_size,
            'length_var_name': length_var_name
        }
        
        # Register field index to base name mapping
        self.field_index_map[index] = base_name
        
        return variables
    
    def _get_rand_kind(self, field: Field) -> Optional[str]:
        """
        Determine if field is rand/randc and return the kind.
        
        Args:
            field: IR field
            
        Returns:
            'rand', 'randc', or None
        """
        # Check the field's rand_kind attribute (set by DataModelFactory)
        if field.rand_kind is not None:
            return field.rand_kind
        
        # Check for is_const flag - const fields are not random
        if field.is_const:
            return None
        
        return None  # Not a random variable by default
    
    def _apply_domain(self, domain: Domain, field: Field) -> Domain:
        """
        Apply domain constraints from field metadata to domain.
        
        Args:
            domain: Base domain from type
            field: IR field with potential domain metadata
            
        Returns:
            Domain with constraints applied (if any)
        """
        # Check if field has domain attribute (set by DataModelFactory)
        if field.domain is not None:
            from ..core.domain import IntDomain
            min_val, max_val = field.domain
            # Create a new domain with the interval
            # Use the width and signedness from the existing domain
            if isinstance(domain, IntDomain):
                domain_constraint = IntDomain([(min_val, max_val)], domain.width, domain.signed)
                # Intersect with existing domain
                domain = domain.intersect(domain_constraint)
        
        return domain
    
    def extract_with_metadata(
        self,
        struct_type: DataTypeStruct,
        field_metadata: Dict[str, Dict],
        prefix: str = ""
    ) -> List[Variable]:
        """
        Extract variables with explicit metadata provided.
        
        This is useful when the IR doesn't preserve Python metadata,
        but we have it available separately.
        
        Args:
            struct_type: IR struct/class type
            field_metadata: Dict mapping field name to metadata dict
                          metadata should contain: 'rand', 'rand_kind', 'bounds', etc.
            prefix: Optional prefix for nested field names
            
        Returns:
            List of extracted variables
        """
        extracted = []
        
        for idx, field in enumerate(struct_type.fields):
            var = self._extract_with_metadata(field, idx, prefix, field_metadata)
            if var is not None:
                extracted.append(var)
        
        return extracted
    
    def _extract_with_metadata(
        self,
        field: Field,
        index: int,
        prefix: str,
        field_metadata: Dict[str, Dict]
    ) -> Optional[Variable]:
        """Extract variable using explicit metadata"""
        
        var_name = f"{prefix}{field.name}" if prefix else field.name
        
        # Get metadata for this field
        metadata = field_metadata.get(field.name, {})
        
        # Check if field is marked as rand
        if not metadata.get('rand', False):
            return None
        
        # Check if type can be converted to domain
        if not self.type_mapper.can_convert_to_domain(field.datatype):
            return None
        
        # Create domain from type
        domain = self.type_mapper.to_domain(field.datatype, use_bitvector=True)
        
        # Apply domain constraints if present (try both 'domain' and legacy 'bounds')
        domain_constraint = metadata.get('domain') or metadata.get('bounds')
        if domain_constraint:
            if isinstance(domain_constraint, tuple) and len(domain_constraint) == 2:
                from ..core.domain import IntDomain
                if isinstance(domain, IntDomain):
                    # Intersect with domain constraint
                    constraint_domain = IntDomain(
                        [(domain_constraint[0], domain_constraint[1])],
                        domain.width,
                        domain.signed
                    )
                    domain = domain.intersect(constraint_domain)
        
        # Determine variable kind
        rand_kind = metadata.get('rand_kind', 'rand')
        if rand_kind == "randc":
            var_kind = VarKind.RANDC
        else:
            var_kind = VarKind.RAND
        
        # Create variable
        variable = Variable(
            name=var_name,
            domain=domain,
            kind=var_kind
        )
        
        # Register variable
        self.variables[var_name] = variable
        self.field_index_map[index] = var_name
        
        return variable
    
    def get_variable(self, name: str) -> Optional[Variable]:
        """Get a variable by name"""
        return self.variables.get(name)
    
    def get_field_name(self, index: int) -> Optional[str]:
        """Get field name by index"""
        return self.field_index_map.get(index)
    
    def clear(self):
        """Clear all extracted variables"""
        self.variables.clear()
        self.field_index_map.clear()
