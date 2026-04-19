"""Tests for Variable Extractor"""

import pytest
from zuspec.ir.core.data_type import DataTypeInt, DataTypeStruct, DataTypeEnum
from zuspec.ir.core.fields import Field
from zuspec.dataclasses.solver.frontend import VariableExtractor
from zuspec.dataclasses.solver.core import Variable, VarKind, IntDomain


class TestVariableExtractor:
    """Test variable extraction from IR structures"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.extractor = VariableExtractor()
    
    def test_extract_with_metadata_single_rand(self):
        """Test extracting single rand variable with metadata"""
        # Create a simple struct with one field
        struct = DataTypeStruct(
            name="TestStruct",
            super=None,
            fields=[
                Field(
                    name="x",
                    datatype=DataTypeInt(bits=8, signed=False)
                )
            ]
        )
        
        # Provide metadata indicating x is rand
        metadata = {
            "x": {
                "rand": True,
                "rand_kind": "rand"
            }
        }
        
        variables = self.extractor.extract_with_metadata(struct, metadata)
        
        assert len(variables) == 1
        assert variables[0].name == "x"
        assert variables[0].kind == VarKind.RAND
        assert isinstance(variables[0].domain, IntDomain)
        assert variables[0].domain.size() == 256
    
    def test_extract_with_metadata_single_randc(self):
        """Test extracting single randc variable"""
        struct = DataTypeStruct(
            name="TestStruct",
            super=None,
            fields=[
                Field(
                    name="id",
                    datatype=DataTypeInt(bits=4, signed=False)
                )
            ]
        )
        
        metadata = {
            "id": {
                "rand": True,
                "rand_kind": "randc"
            }
        }
        
        variables = self.extractor.extract_with_metadata(struct, metadata)
        
        assert len(variables) == 1
        assert variables[0].name == "id"
        assert variables[0].kind == VarKind.RANDC
        assert variables[0].randc_state is not None
        assert variables[0].domain.size() == 16
    
    def test_extract_with_metadata_multiple_variables(self):
        """Test extracting multiple variables"""
        struct = DataTypeStruct(
            name="TestStruct",
            super=None,
            fields=[
                Field(name="x", datatype=DataTypeInt(bits=8, signed=False)),
                Field(name="y", datatype=DataTypeInt(bits=16, signed=True)),
                Field(name="z", datatype=DataTypeInt(bits=4, signed=False))
            ]
        )
        
        metadata = {
            "x": {"rand": True, "rand_kind": "rand"},
            "y": {"rand": True, "rand_kind": "rand"},
            "z": {"rand": True, "rand_kind": "randc"}
        }
        
        variables = self.extractor.extract_with_metadata(struct, metadata)
        
        assert len(variables) == 3
        names = [v.name for v in variables]
        assert "x" in names
        assert "y" in names
        assert "z" in names
        
        # Check randc
        z_var = [v for v in variables if v.name == "z"][0]
        assert z_var.kind == VarKind.RANDC
    
    def test_extract_with_metadata_bounds(self):
        """Test extracting variable with bounds constraint"""
        struct = DataTypeStruct(
            name="TestStruct",
            super=None,
            fields=[
                Field(
                    name="port",
                    datatype=DataTypeInt(bits=16, signed=False)
                )
            ]
        )
        
        metadata = {
            "port": {
                "rand": True,
                "rand_kind": "rand",
                "bounds": (1024, 65535)  # Valid port range
            }
        }
        
        variables = self.extractor.extract_with_metadata(struct, metadata)
        
        assert len(variables) == 1
        var = variables[0]
        assert var.name == "port"
        
        # Domain should be restricted to bounds
        assert var.domain.size() == (65535 - 1024 + 1)
        values = list(var.domain.values())
        assert min(values) == 1024
        assert max(values) == 65535
    
    def test_extract_non_rand_fields_ignored(self):
        """Test that non-rand fields are not extracted"""
        struct = DataTypeStruct(
            name="TestStruct",
            super=None,
            fields=[
                Field(name="x", datatype=DataTypeInt(bits=8, signed=False)),
                Field(name="y", datatype=DataTypeInt(bits=8, signed=False)),
                Field(name="z", datatype=DataTypeInt(bits=8, signed=False))
            ]
        )
        
        # Only mark x as rand
        metadata = {
            "x": {"rand": True, "rand_kind": "rand"}
            # y and z have no rand marker
        }
        
        variables = self.extractor.extract_with_metadata(struct, metadata)
        
        assert len(variables) == 1
        assert variables[0].name == "x"
    
    def test_extract_enum_types_not_supported_yet(self):
        """Test that enum types are handled (currently skipped)"""
        struct = DataTypeStruct(
            name="TestStruct",
            super=None,
            fields=[
                Field(name="status", datatype=DataTypeEnum())
            ]
        )
        
        metadata = {
            "status": {"rand": True, "rand_kind": "rand"}
        }
        
        variables = self.extractor.extract_with_metadata(struct, metadata)
        
        # EnumDomain is supported, so this should work
        assert len(variables) == 1
        assert variables[0].name == "status"
    
    def test_get_variable_by_name(self):
        """Test retrieving variable by name"""
        struct = DataTypeStruct(
            name="TestStruct",
            super=None,
            fields=[
                Field(name="x", datatype=DataTypeInt(bits=8, signed=False))
            ]
        )
        
        metadata = {"x": {"rand": True}}
        self.extractor.extract_with_metadata(struct, metadata)
        
        var = self.extractor.get_variable("x")
        assert var is not None
        assert var.name == "x"
        
        # Non-existent variable
        assert self.extractor.get_variable("nonexistent") is None
    
    def test_get_field_name_by_index(self):
        """Test retrieving field name by index"""
        struct = DataTypeStruct(
            name="TestStruct",
            super=None,
            fields=[
                Field(name="x", datatype=DataTypeInt(bits=8, signed=False)),
                Field(name="y", datatype=DataTypeInt(bits=8, signed=False))
            ]
        )
        
        metadata = {
            "x": {"rand": True},
            "y": {"rand": True}
        }
        self.extractor.extract_with_metadata(struct, metadata)
        
        assert self.extractor.get_field_name(0) == "x"
        assert self.extractor.get_field_name(1) == "y"
        assert self.extractor.get_field_name(999) is None
    
    def test_extract_with_prefix(self):
        """Test extraction with name prefix"""
        struct = DataTypeStruct(
            name="TestStruct",
            super=None,
            fields=[
                Field(name="x", datatype=DataTypeInt(bits=8, signed=False))
            ]
        )
        
        metadata = {"x": {"rand": True}}
        variables = self.extractor.extract_with_metadata(
            struct, metadata, prefix="parent."
        )
        
        assert len(variables) == 1
        assert variables[0].name == "parent.x"
    
    def test_extract_signed_integers(self):
        """Test extracting signed integer variables"""
        struct = DataTypeStruct(
            name="TestStruct",
            super=None,
            fields=[
                Field(name="offset", datatype=DataTypeInt(bits=8, signed=True))
            ]
        )
        
        metadata = {"offset": {"rand": True}}
        variables = self.extractor.extract_with_metadata(struct, metadata)
        
        assert len(variables) == 1
        var = variables[0]
        assert var.domain.signed
        assert var.domain.size() == 256
        
        # Check range
        values = list(var.domain.values())
        assert min(values) == -128
        assert max(values) == 127
    
    def test_extract_various_widths(self):
        """Test extracting variables with various bit widths"""
        struct = DataTypeStruct(
            name="TestStruct",
            super=None,
            fields=[
                Field(name="a", datatype=DataTypeInt(bits=1, signed=False)),
                Field(name="b", datatype=DataTypeInt(bits=4, signed=False)),
                Field(name="c", datatype=DataTypeInt(bits=16, signed=False)),
                Field(name="d", datatype=DataTypeInt(bits=32, signed=False))
            ]
        )
        
        metadata = {
            "a": {"rand": True},
            "b": {"rand": True},
            "c": {"rand": True},
            "d": {"rand": True}
        }
        
        variables = self.extractor.extract_with_metadata(struct, metadata)
        
        assert len(variables) == 4
        
        # Check domain sizes
        var_a = [v for v in variables if v.name == "a"][0]
        assert var_a.domain.size() == 2  # 1-bit: 0, 1
        
        var_b = [v for v in variables if v.name == "b"][0]
        assert var_b.domain.size() == 16  # 4-bit: 0-15
        
        var_c = [v for v in variables if v.name == "c"][0]
        assert var_c.domain.size() == 65536  # 16-bit
        
        var_d = [v for v in variables if v.name == "d"][0]
        assert var_d.domain.size() == 2**32  # 32-bit
    
    def test_clear_extracted_variables(self):
        """Test clearing extracted variables"""
        struct = DataTypeStruct(
            name="TestStruct",
            super=None,
            fields=[
                Field(name="x", datatype=DataTypeInt(bits=8, signed=False))
            ]
        )
        
        metadata = {"x": {"rand": True}}
        self.extractor.extract_with_metadata(struct, metadata)
        
        assert len(self.extractor.variables) == 1
        
        self.extractor.clear()
        
        assert len(self.extractor.variables) == 0
        assert len(self.extractor.field_index_map) == 0
    
    def test_extract_preserves_domain_properties(self):
        """Test that domain properties are preserved"""
        struct = DataTypeStruct(
            name="TestStruct",
            super=None,
            fields=[
                Field(name="x", datatype=DataTypeInt(bits=8, signed=False))
            ]
        )
        
        metadata = {"x": {"rand": True}}
        variables = self.extractor.extract_with_metadata(struct, metadata)
        
        var = variables[0]
        domain = var.domain
        
        assert domain.width == 8
        assert not domain.signed
        assert not domain.is_empty()
        assert not domain.is_singleton()
