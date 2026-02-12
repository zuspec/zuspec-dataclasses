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
            var = self._extract_from_field(field, idx, prefix)
            if var is not None:
                extracted.append(var)
        
        return extracted
    
    def _extract_from_field(
        self, 
        field: Field, 
        index: int, 
        prefix: str
    ) -> Optional[Variable]:
        """
        Extract a variable from a single field.
        
        Args:
            field: IR field to extract from
            index: Field index in parent struct
            prefix: Name prefix for nested fields
            
        Returns:
            Variable if field is rand/randc, None otherwise
        """
        # Check if this is a randomizable type
        if not self.type_mapper.can_convert_to_domain(field.datatype):
            return None
        
        # Get field metadata - check for rand/randc markers
        # In IR, metadata is typically stored on the Field's initial_value or in py_type
        rand_kind = self._get_rand_kind(field)
        
        if rand_kind is None:
            # Not a random variable
            return None
        
        # Build variable name
        var_name = f"{prefix}{field.name}" if prefix else field.name
        
        # Create domain from type
        domain = self.type_mapper.to_domain(field.datatype, use_bitvector=True)
        
        # Apply bounds constraints if present
        domain = self._apply_bounds(domain, field)
        
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
    
    def _get_rand_kind(self, field: Field) -> Optional[str]:
        """
        Determine if field is rand/randc and return the kind.
        
        Args:
            field: IR field
            
        Returns:
            'rand', 'randc', or None
        """
        # In the IR, the python dataclass metadata is typically preserved
        # in the py_type field or through the initial value
        
        # For now, we'll check if the datatype has metadata
        # This is a simplification - in practice, the metadata might be
        # stored differently depending on how the IR was generated
        
        if hasattr(field.datatype, 'py_type') and field.datatype.py_type is not None:
            py_type = field.datatype.py_type
            if hasattr(py_type, '__metadata__'):
                metadata = py_type.__metadata__
                if metadata.get('rand', False):
                    return metadata.get('rand_kind', 'rand')
        
        # Check for is_const flag - const fields are not random
        if field.is_const:
            return None
        
        # For testing/demo purposes, we'll also accept a simple heuristic:
        # If the field has initial_value=None and datatype is int, assume it might be rand
        # This is just for development - real implementation would use proper metadata
        
        return None  # Not a random variable by default
    
    def _apply_bounds(self, domain: Domain, field: Field) -> Domain:
        """
        Apply bounds constraints from field metadata to domain.
        
        Args:
            domain: Base domain from type
            field: IR field with potential bounds metadata
            
        Returns:
            Domain with bounds applied (if any)
        """
        # In practice, bounds would be extracted from metadata
        # For now, just return the domain as-is
        # This will be enhanced when we have access to the actual metadata
        
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
        
        # Apply bounds if present
        if 'bounds' in metadata:
            bounds = metadata['bounds']
            if isinstance(bounds, tuple) and len(bounds) == 2:
                from ..core.domain import IntDomain
                if isinstance(domain, IntDomain):
                    # Intersect with bounds
                    bounds_domain = IntDomain(
                        [(bounds[0], bounds[1])],
                        domain.width,
                        domain.signed
                    )
                    domain = domain.intersect(bounds_domain)
        
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
