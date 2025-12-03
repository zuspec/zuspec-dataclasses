import pytest
import zuspec.dataclasses as zdc


def test_empty_struct():

    @zdc.dataclass
    class MyS(zdc.Struct):
        pass

    ctxt = zdc.transform(MyS)

    # Datamodel Mapping
    # Expect the returned context to contain DataTypeStruct keyed by MyS.__qualname__
    assert MyS.__qualname__ in ctxt.type_m
    assert isinstance(ctxt.type_m[MyS.__qualname__], zdc.dm.DataTypeStruct)

def test_struct_int_field():

    @zdc.dataclass
    class MyS(zdc.Struct):
        a : int = zdc.field()
        pass

    ctxt = zdc.transform(MyS)

    # Datamodel Mapping
    # Expect DataTypeStruct:{fields:[Field[name:a, datatype:DataTypeInt{bits:-1,signed:True}]]}
    s = ctxt.type_m[MyS.__qualname__]
    assert isinstance(s, zdc.dm.DataTypeStruct)
    assert len(s.fields) == 1
    f = s.fields[0]
    assert f.name == 'a'
    assert isinstance(f.datatype, zdc.dm.DataTypeInt)
    assert f.datatype.bits == -1 and f.datatype.signed is True

def test_struct_uint32_field():
    from typing import Annotated

    @zdc.dataclass
    class MyS(zdc.Struct):
        a : Annotated[int, zdc.U(32)] = zdc.field()
        pass

    ctxt = zdc.transform(MyS)

    # Datamodel Mapping
    # Expect DataTypeStruct:{fields:[Field[name:a, datatype:DataTypeInt{bits:32,signed:False}]]}
    s = ctxt.type_m[MyS.__qualname__]
    assert isinstance(s, zdc.dm.DataTypeStruct)
    assert len(s.fields) == 1
    f = s.fields[0]
    assert f.name == 'a'
    assert isinstance(f.datatype, zdc.dm.DataTypeInt)
    assert f.datatype.bits == 32 and f.datatype.signed is False

def test_struct_string_field():
    @zdc.dataclass
    class MyS(zdc.Struct):
        s : str = zdc.field()
        pass

    ctxt = zdc.transform(MyS)
    # Datamodel Mapping
    # Expect DataTypeStruct:{fields:[Field[name:s, datatype:DataTypeString]]}
    s_t = ctxt.type_m[MyS.__qualname__]
    assert isinstance(s_t, zdc.dm.DataTypeStruct)
    assert len(s_t.fields) == 1
    f = s_t.fields[0]
    assert f.name == 's'
    assert isinstance(f.datatype, zdc.dm.DataTypeString)

def test_struct_inheritance():
    @zdc.dataclass
    class MyS(zdc.Struct):
        s : str = zdc.field()
        pass

    # Mapping: DataTypeStruct:{
    #   name:MyInhS.__qualname__, 
    #   fields:[Field[name:s, datatype:DataTypeString]]
    # }
    @zdc.dataclass
    class MyInhS(MyS):
        pass

    ctxt = zdc.transform(MyInhS)
    # Validate base and derived exist
    assert MyS.__qualname__ in ctxt.type_m
    assert MyInhS.__qualname__ in ctxt.type_m
    base_t = ctxt.type_m[MyS.__qualname__]
    derived_t = ctxt.type_m[MyInhS.__qualname__]
    assert isinstance(base_t, zdc.dm.DataTypeStruct)
    assert isinstance(derived_t, zdc.dm.DataTypeStruct)
    # Validate base fields
    assert len(base_t.fields) == 1
    f = base_t.fields[0]
    assert f.name == 's' and isinstance(f.datatype, zdc.dm.DataTypeString)
    # Validate inheritance linkage and derived fields when none declared
    assert derived_t.super is base_t
    assert len(derived_t.fields) == 0

