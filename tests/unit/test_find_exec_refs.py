import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.api.visitor import Visitor
from typing import Literal

def test_smoke():

    @zdc.dataclass
    class MyC(zdc.Component):
        dat_i : zdc.Bit[32] = zdc.input()
        dat_o : zdc.Bit[32] = zdc.output()

        def _inc(self):
            self.dat_o = self.dat_i + 1

def test_find_field_refs():
    @zdc.dataclass
    class MyC(zdc.Component):
        dat_i : zdc.Bit[32] = zdc.input()
        dat_o : zdc.Bit[32] = zdc.output()

        def _inc(self):
            self.dat_o = self.dat_i + 1

    v = Visitor()
    refs = v._findFieldRefs(MyC, MyC._inc)
    result = set((is_write, f.name, path) for (is_write, f, path) in refs)
    expected = set([
        (True, "dat_o", ("self", "dat_o")),
        (False, "dat_i", ("self", "dat_i"))
    ])
    assert result == expected

def test_multiple_reads():
    @zdc.dataclass
    class MyC(zdc.Component):
        a : zdc.Bit[32] = zdc.input()
        b : zdc.Bit[32] = zdc.input()
        c : zdc.Bit[32] = zdc.output()

        def _sum(self):
            self.c = self.a + self.b

    v = Visitor()
    refs = v._findFieldRefs(MyC, MyC._sum)
    result = set((is_write, f.name, path) for (is_write, f, path) in refs)
    expected = set([
        (True, "c", ("self", "c")),
        (False, "a", ("self", "a")),
        (False, "b", ("self", "b"))
    ])
    assert result == expected

def test_multiple_writes():
    @zdc.dataclass
    class MyC(zdc.Component):
        x : zdc.Bit[32] = zdc.input()
        y : zdc.Bit[32] = zdc.input()
        z : zdc.Bit[32] = zdc.output()

        def _set(self):
            self.z = self.x
            self.y = self.z

    v = Visitor()
    refs = v._findFieldRefs(MyC, MyC._set)
    result = set((is_write, f.name, path) for (is_write, f, path) in refs)
    expected = set([
        (True, "z", ("self", "z")),
        (True, "y", ("self", "y")),
        (False, "x", ("self", "x")),
        (False, "z", ("self", "z"))
    ])
    assert result == expected

def test_conditional_access():
    @zdc.dataclass
    class MyC(zdc.Component):
        flag : zdc.Bit[32] = zdc.input()
        out : zdc.Bit[32] = zdc.output()

        def _cond(self):
            if self.flag:
                self.out = 1
            else:
                self.out = 0

    v = Visitor()
    refs = v._findFieldRefs(MyC, MyC._cond)
    result = set((is_write, f.name, path) for (is_write, f, path) in refs)
    expected = set([
        (False, "flag", ("self", "flag")),
        (True, "out", ("self", "out"))
    ])
    assert result == expected

def test_no_access():
    @zdc.dataclass
    class MyC(zdc.Component):
        a : zdc.Bit[32] = zdc.input()
        b : zdc.Bit[32] = zdc.output()

        def _noop(self):
            pass

    v = Visitor()
    refs = v._findFieldRefs(MyC, MyC._noop)
    assert refs == []

def test_local_variable():
    @zdc.dataclass
    class MyC(zdc.Component):
        a : zdc.Bit[32] = zdc.input()
        b : zdc.Bit[32] = zdc.output()

        def _local(self):
            x = 42
            y = x + 1
            z = y * 2

    v = Visitor()
    refs = v._findFieldRefs(MyC, MyC._local)
    assert refs == []

def test_local_shadows_field():
    @zdc.dataclass
    class MyC(zdc.Component):
        val : zdc.Bit[32] = zdc.input()
        out : zdc.Bit[32] = zdc.output()

        def _shadow(self):
            val = 123
            out = val + 1

    v = Visitor()
    refs = v._findFieldRefs(MyC, MyC._shadow)
    assert refs == []
