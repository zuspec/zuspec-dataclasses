"""Unit tests for the zuspec-dataclasses CLI plugin (PythonFrontend)."""
from __future__ import annotations

import argparse
import sys
import pytest

import zuspec.dataclasses as zdc
from zuspec.dataclasses.cli_plugin import PythonFrontend, ZuspecDataclassesPlugin
from zuspec.cli.registry import Registry


# ---------------------------------------------------------------------------
# Test ZuspecDataclassesPlugin.register()
# ---------------------------------------------------------------------------

def test_plugin_registers_python_frontend():
    reg = Registry()
    reg.reset()
    ZuspecDataclassesPlugin().register(reg)
    fe = reg.get_frontend("python")
    assert fe is not None
    assert fe.name == "python"


def test_python_frontend_no_file_extensions():
    fe = PythonFrontend()
    assert fe.file_extensions == []


# ---------------------------------------------------------------------------
# Test PythonFrontend.load()
# ---------------------------------------------------------------------------

def test_python_frontend_requires_module_colon_class():
    fe = PythonFrontend()
    args = argparse.Namespace(top="no_colon", be_prefix="d")
    with pytest.raises(ValueError, match="module:ClassName"):
        fe.load([], args)


def test_python_frontend_loads_builtin_class(monkeypatch):
    """Load a @zdc.dataclass defined inline in this test module."""
    import types, sys

    # Build a tiny synthetic module with a known action class
    @zdc.dataclass
    class _Tiny(zdc.Action):
        x: zdc.u2 = zdc.input()
        y: zdc.u1 = zdc.rand()

        @zdc.constraint
        def c(self):
            self.y == self.x[0]

    mod = types.ModuleType("_test_tiny_mod")
    mod._Tiny = _Tiny
    monkeypatch.setitem(sys.modules, "_test_tiny_mod", mod)

    fe = PythonFrontend()
    args = argparse.Namespace(top="_test_tiny_mod:_Tiny", be_prefix="d")
    ir = fe.load([], args)

    assert ir.kind == "zuspec.constraint.compiler"
    assert ir.payload is not None
    assert ir.provenance == "python:_test_tiny_mod:_Tiny"


def test_python_frontend_ir_has_extracted_cc(monkeypatch):
    """After load(), the CC should already have run extract()."""
    import types, sys

    @zdc.dataclass
    class _TinyExtract(zdc.Action):
        x: zdc.u2 = zdc.input()
        y: zdc.u1 = zdc.rand()

        @zdc.constraint
        def c(self):
            self.y == self.x[0]

    mod = types.ModuleType("_test_extract_mod")
    mod._TinyExtract = _TinyExtract
    monkeypatch.setitem(sys.modules, "_test_extract_mod", mod)

    fe = PythonFrontend()
    args = argparse.Namespace(top="_test_extract_mod:_TinyExtract", be_prefix="d")
    ir = fe.load([], args)

    cc = ir.payload
    # cset is populated by extract(); its presence confirms extract() was called
    assert hasattr(cc, "cset") and cc.cset is not None
