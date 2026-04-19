"""CLI plugin for zuspec-dataclasses.

Registers :class:`PythonFrontend` with the zuspec-cli
:class:`~zuspec.cli.Registry`.
"""
from __future__ import annotations

import argparse
import importlib
from typing import List, TYPE_CHECKING

from zuspec.cli.plugin import Plugin
from zuspec.cli.frontend import Frontend
from zuspec.cli.ir import IR

if TYPE_CHECKING:
    from zuspec.cli.registry import Registry


class PythonFrontend(Frontend):
    """Python front-end — loads a ``@zdc.dataclass`` action class by module
    reference and produces a :class:`~zuspec.cli.IR` wrapping a
    ``ConstraintCompiler`` instance.

    The ``--top`` argument must be in the form ``module:ClassName``, e.g.::

        zuspec synth --fe python examples.04_constraints.rv32i_decode:RV32IDecode ...
    """

    @property
    def name(self) -> str:
        return "python"

    @property
    def description(self) -> str:
        return "Python @zdc.dataclass action class (module:ClassName)"

    @property
    def file_extensions(self) -> List[str]:
        return []

    def load(self, files: List[str], args: argparse.Namespace) -> IR:
        top = getattr(args, "top", None) or ""
        if ":" not in top:
            raise ValueError(
                f"Python frontend requires --top in 'module:ClassName' form, "
                f"got: '{top}'"
            )
        module_name, class_name = top.rsplit(":", 1)

        mod = importlib.import_module(module_name)
        cls = getattr(mod, class_name)

        # Deferred import to avoid a compile-time zuspec-synth dependency.
        from zuspec.synth.sprtl.constraint_compiler import ConstraintCompiler

        cc = ConstraintCompiler(cls, prefix=getattr(args, "be_prefix", "d"))
        cc.extract()

        return IR(
            payload=cc,
            kind="zuspec.constraint.compiler",
            provenance=f"python:{top}",
        )


class ZuspecDataclassesPlugin(Plugin):
    """Plugin that registers :class:`PythonFrontend` for Python action classes."""

    @property
    def name(self) -> str:
        return "zuspec-dataclasses"

    @property
    def description(self) -> str:
        return "Python @zdc.dataclass action class front-end"

    def register(self, registry: "Registry") -> None:
        registry.add_frontend(PythonFrontend())
