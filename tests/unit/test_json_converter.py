import json
import zuspec.dataclasses as zdc
import zuspec.dataclasses.ir as dm
from typing import Protocol


def test_json_converter_smoke():
    """Test basic JsonConverter functionality with data model objects."""

    class MemIF(Protocol):
        async def read(self, addr: int) -> int: ...
        async def write(self, addr: int, data: int): ...

    @zdc.dataclass
    class MyC(zdc.Component):
        m0: MemIF = zdc.port()

        @zdc.process
        async def _run(self):
            for i in range(16):
                await self.m0.write(4 * i, i + 1)
                val = await self.m0.read(4 * i)

    # Build data model from the component
    dm_ctxt = zdc.DataModelFactory().build(MyC)

    # Create a JsonConverter for the dm module
    @dm.json_converter(dm)
    class MyConverter(dm.JsonConverter):
        pass

    converter = MyConverter()

    # Convert each type in the context
    for type_name, type_dm in dm_ctxt.type_m.items():
        result = converter.convert(type_dm)
        
        assert isinstance(result, dict), f"Expected dict for {type_name}, got {type(result)}"
        assert "_type" in result, f"Result for {type_name} should have _type field"
        
        # Verify it's JSON serializable
        json_str = json.dumps(result, indent=2)
        assert len(json_str) > 0, f"JSON string for {type_name} should not be empty"
        
        print(f"\n=== {type_name} ===")
        print(json_str)


def test_json_converter_custom_method():
    """Test that custom convert methods can be provided."""

    @zdc.dataclass
    class SimpleC(zdc.Component):
        pass

    # Build data model
    dm_ctxt = zdc.DataModelFactory().build(SimpleC)

    @dm.json_converter(dm)
    class CustomConverter(dm.JsonConverter):
        def convertDataTypeComponent(self, obj):
            return {"custom": True, "_type": "DataTypeComponent", "name": obj.name}

    converter = CustomConverter()

    # Get the component type from context
    for type_name, type_dm in dm_ctxt.type_m.items():
        if isinstance(type_dm, dm.DataTypeComponent):
            result = converter.convert(type_dm)
            assert result["custom"] == True, "Custom converter should be used"
            assert result["name"] == type_name, "Name should be preserved"
            print(f"Custom result for {type_name}:", json.dumps(result, indent=2))


def test_json_converter_nested_structures():
    """Test conversion of nested data model structures."""

    class DataIF(Protocol):
        async def call(self, req: int) -> int: ...

    @zdc.dataclass
    class MyProdC(zdc.Component):
        prod: DataIF = zdc.port()

    @zdc.dataclass
    class MyConsC(zdc.Component):
        cons: DataIF = zdc.export()

        def __bind__(self):
            return {self.cons.call: self.target}

        async def target(self, req: int) -> int:
            return req + 2

    @zdc.dataclass
    class MyC(zdc.Component):
        p: MyProdC = zdc.field()
        c: MyConsC = zdc.field()

        def __bind__(self):
            return {self.p.prod: self.c.cons}

    # Build data model
    dm_ctxt = zdc.DataModelFactory().build(MyC)

    @dm.json_converter(dm)
    class MyConverter(dm.JsonConverter):
        pass

    converter = MyConverter()

    # Convert and verify all types
    for type_name, type_dm in dm_ctxt.type_m.items():
        result = converter.convert(type_dm)
        json_str = json.dumps(result, indent=2)
        print(f"\n=== {type_name} ===")
        print(json_str)

        # Basic structural assertions
        assert "_type" in result
        if isinstance(type_dm, dm.DataTypeComponent):
            assert "fields" in result
            assert "functions" in result


def test_json_converter_expressions():
    """Test conversion of expression types in the data model."""

    @zdc.dataclass
    class MyC(zdc.Component):
        @zdc.process
        async def _run(self):
            x = 1 + 2
            y = x * 3

    dm_ctxt = zdc.DataModelFactory().build(MyC)

    @dm.json_converter(dm)
    class MyConverter(dm.JsonConverter):
        pass

    converter = MyConverter()

    # Find the component and check its functions/processes
    for type_name, type_dm in dm_ctxt.type_m.items():
        if isinstance(type_dm, dm.DataTypeComponent):
            result = converter.convert(type_dm)
            json_str = json.dumps(result, indent=2)
            print(f"\n=== {type_name} with expressions ===")
            print(json_str)
