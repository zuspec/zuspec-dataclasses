import pytest
import dataclasses as dc
import zuspec.dataclasses as zdc
from typing import Self

import zuspec.dataclasses.api.visitor as zv

def test_elabBinds_extract():
    @zdc.dataclass
    class MyP(zdc.Component):
        dat_o : int = zdc.output(width=10)

    @zdc.dataclass
    class MyC(zdc.Component):
        dat_i : int = zdc.input(width=10)

    @zdc.dataclass
    class MyTop(zdc.Component):
        p : MyP = zdc.field()
        c : MyC = zdc.field(bind=zdc.bind[Self](lambda s:{
            s.p.dat_o : s.c.dat_i
        }))

    visitor = zv.Visitor()
    bind_lambda = lambda s: {s.p.dat_o : s.c.dat_i}
    result = visitor._elabBinds(bind_lambda, MyTop)
    assert len(result) == 1
    for (k_field, k_path), (v_field, v_path) in result.items():
        assert k_field.name == "dat_o"
        assert k_path == ("s", "p", "dat_o")
        assert v_field.name == "dat_i"
        assert v_path == ("s", "c", "dat_i")

def test_elabBinds_invalid_path():
    @zdc.dataclass
    class MyP(zdc.Component):
        dat_o : int = zdc.output(width=10)

    @zdc.dataclass
    class MyTop(zdc.Component):
        p : MyP = zdc.field()

    visitor = zv.Visitor()
    def bad_lambda(s):
        return {s.p.no_such_field: s.p.dat_o}
    with pytest.raises(AttributeError):
        visitor._elabBinds(bad_lambda, MyTop)

def test_elabBinds_multiple_paths():
    @zdc.dataclass
    class MyP(zdc.Component):
        dat_o : int = zdc.output(width=10)
        dat_x : int = zdc.output(width=8)

    @zdc.dataclass
    class MyC(zdc.Component):
        dat_i : int = zdc.input(width=10)
        dat_y : int = zdc.input(width=8)

    @zdc.dataclass
    class MyTop(zdc.Component):
        p : MyP = zdc.field()
        c : MyC = zdc.field(bind=zdc.bind[Self](lambda s:{
            s.p.dat_o : s.c.dat_i,
            s.p.dat_x : s.c.dat_y
        }))

    visitor = zv.Visitor()
    bind_lambda = lambda s: {s.p.dat_o : s.c.dat_i, s.p.dat_x : s.c.dat_y}
    result = visitor._elabBinds(bind_lambda, MyTop)
    assert len(result) == 2
    found = set()
    for (k_field, k_path), (v_field, v_path) in result.items():
        if k_field.name == "dat_o":
            assert k_path == ("s", "p", "dat_o")
            assert v_field.name == "dat_i"
            assert v_path == ("s", "c", "dat_i")
            found.add("dat_o")
        elif k_field.name == "dat_x":
            assert k_path == ("s", "p", "dat_x")
            assert v_field.name == "dat_y"
            assert v_path == ("s", "c", "dat_y")
            found.add("dat_x")
    assert found == {"dat_o", "dat_x"}
