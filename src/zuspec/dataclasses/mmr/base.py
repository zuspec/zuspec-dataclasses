"""RegisterFile base class: elaboration, bus access, and named register access.

Lowering
--------
``RegisterFile`` participates in the Zuspec structured-lowering pipeline by
inheriting all five interface protocols from ``zuspec.ir.core.interfaces``.
The ``elaborate_field()`` classmethod is called by ``DataModelFactory`` when a
component declares a ``RegisterFile`` field; it returns an ``AbstractionFieldIR``
whose ``ir_node`` is a plain dict capturing ``regfile_cls`` and ``module_name``.

``sv_module_text()`` delegates to the standalone ``synthesize_regfile()``
function in ``zuspec-synth`` via a lazy import (avoiding a circular dependency
since ``zuspec-dataclasses`` does not depend on ``zuspec-synth`` at module load
time).
"""
from __future__ import annotations

import re as _re
from typing import Dict, List, Optional, Callable

from .field_rt import FieldRT
from .register_rt import RegisterRT
from .descriptor import FieldDescriptor

try:
    from zuspec.ir.core.interfaces import (
        Lowerable,
        ElaboratableInterface,
        SVEmittableInterface,
        SVAEmittableInterface,
        CSimEmittableInterface,
    )
    _HAS_INTERFACES = True
except ImportError:
    # Graceful degradation when zuspec-ir-core is not installed.
    Lowerable = object
    ElaboratableInterface = object
    SVEmittableInterface = object
    SVAEmittableInterface = object
    CSimEmittableInterface = object
    _HAS_INTERFACES = False


def _snake(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s = _re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
    s = _re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s)
    return s.lower()


class RegisterFile(
    Lowerable,
    ElaboratableInterface,
    SVEmittableInterface,
    SVAEmittableInterface,
    CSimEmittableInterface,
):
    """Base class for all abstract register files.

    Subclasses must be decorated with :func:`~.decorators.regfile` and contain
    inner classes decorated with :func:`~.decorators.reg`::

        @zdc.regfile
        class MyRegs(zdc.RegisterFile):

            @zdc.reg(offset=0x00)
            class CTRL:
                START: zdc.u1 = zdc.reg_field(singlepulse=True, default=0)

    Instantiate inside a component::

        regs: MyRegs = zdc.regfile()

    After instantiation, registers are accessible by name::

        self.regs.CTRL           # → RegisterRT
        self.regs.CTRL.START     # → int (current value) in comb/sync context
    """

    # ------------------------------------------------------------------
    # Lowering interface (ElaboratableInterface / SVEmittableInterface /
    # SVAEmittableInterface / CSimEmittableInterface)
    # ------------------------------------------------------------------

    @classmethod
    def elaborate_field(cls, field_name, field_index, inst_kwargs, element_type=None):
        """Return an AbstractionFieldIR capturing this RegisterFile for synthesis."""
        from zuspec.ir.core.abstraction_field_ir import AbstractionFieldIR
        module_name = _snake(cls.__name__)
        ir_node = {
            'regfile_cls': cls,
            'module_name': module_name,
            'reg_classes': getattr(cls, '_mmr_reg_classes', []),
        }
        return AbstractionFieldIR(
            spec_type_name='RegisterFile',
            field_name=field_name,
            field_index=field_index,
            py_cls=cls,
            inst_kwargs=inst_kwargs or {},
            ir_node=ir_node,
        )

    @classmethod
    def sv_module_text(cls, field_ir):
        """Return the register-file SV module, emitted by ``zuspec.be.sv`` (the sole
        SV backend) for the plain-CSR shape, else the legacy ``synthesize_regfile``.

        The be.sv path (``build_mmr_regfile_sv``) is functionally equivalent to the
        legacy emitter (verified by a 600-transaction APB co-simulation); register
        files using field semantics it doesn't map yet raise ``MmrSVUnsupported`` and
        fall back — regression-safe (process→FSM unification U-5).
        """
        ir_node = field_ir.ir_node
        rfcls, mn = ir_node['regfile_cls'], ir_node['module_name']
        try:
            from zuspec.be.sv.passes.mmr_to_sv import build_mmr_regfile_sv, MmrSVUnsupported
            from zuspec.be.sv.ir.sv_emit import SVEmitter
            return SVEmitter().emit_all(build_mmr_regfile_sv(rfcls, module_name=mn))
        except MmrSVUnsupported:
            from zuspec.synth.passes.mmr_regfile_emit import synthesize_regfile
            return synthesize_regfile(rfcls, module_name=mn)

    @classmethod
    def sv_instance_text(cls, field_ir, parent_prefix):
        """Return an APB4 instantiation snippet for the register file module."""
        ir_node = field_ir.ir_node
        module_name = ir_node['module_name']
        field_name = field_ir.field_name
        prefix = f"{parent_prefix}{field_name}" if parent_prefix else field_name
        lines = [
            f"    {module_name} u_{field_name} (",
            f"        .clk     (clk),",
            f"        .rst     (rst),",
            f"        .psel    ({prefix}_psel),",
            f"        .penable ({prefix}_penable),",
            f"        .pwrite  ({prefix}_pwrite),",
            f"        .paddr   ({prefix}_paddr),",
            f"        .pwdata  ({prefix}_pwdata),",
            f"        .prdata  ({prefix}_prdata),",
            f"        .pready  ({prefix}_pready),",
            f"        .pslverr ({prefix}_pslverr),",
            f"        .hwif_in ({prefix}_hwif_in),",
            f"        .hwif_out({prefix}_hwif_out)",
            f"    );",
        ]
        return "\n".join(lines)

    @classmethod
    def rewrite_proc_stmts(cls, stmts, field_ir):
        """RegisterFile accesses do not require proc-body rewriting."""
        return stmts

    @classmethod
    def sva_assert_properties(cls, field_ir):
        """Generate singlepulse reset assertions for all singlepulse fields."""
        ir_node = field_ir.ir_node
        reg_classes = ir_node.get('reg_classes', [])
        properties = []
        for reg_name, reg_cls in reg_classes:
            for fname, fd in getattr(reg_cls, '_mmr_fields', []):
                if getattr(fd, 'singlepulse', False):
                    sig = f"field_storage_{reg_name}_{fname}"
                    properties.append(
                        f"assert property (@(posedge clk) disable iff (rst)"
                        f" {sig} |=> !{sig});"
                    )
        return properties

    @classmethod
    def sva_assume_properties(cls, field_ir):
        return []

    @classmethod
    def bmc_depth(cls, field_ir):
        return 0

    @classmethod
    def cutpoint_signals(cls, field_ir):
        return []

    @classmethod
    def c_header(cls, field_ir):
        return ""

    @classmethod
    def c_impl(cls, field_ir):
        return ""

    # ------------------------------------------------------------------
    # Runtime elaboration
    # ------------------------------------------------------------------

    def __init__(self):
        # Maps are filled by _elaborate()
        self._reg_map:     Dict[int, RegisterRT]  = {}   # offset → RegisterRT
        self._reg_by_name: Dict[str, RegisterRT]  = {}   # attr_name → RegisterRT
        self._bus_port = None
        self._elaborate()

    def _elaborate(self) -> None:
        """Build FieldRT / RegisterRT instances from class-level metadata."""
        reg_classes = getattr(self.__class__, '_mmr_reg_classes', [])
        for attr_name, inner_cls in reg_classes:
            offset = inner_cls._mmr_offset
            width  = inner_cls._mmr_width
            reg_rt = RegisterRT(attr_name, offset, width)
            for fname, fd in inner_cls._mmr_fields:
                field_rt = FieldRT(fd, fname)
                reg_rt._add_field(fname, field_rt, fd.lsb)
            self._reg_map[offset]     = reg_rt
            self._reg_by_name[attr_name] = reg_rt

    # ------------------------------------------------------------------
    # Named register access
    # ------------------------------------------------------------------

    def __getattribute__(self, name: str):
        # Intercept register names before Python finds the inner class definition
        if not name.startswith('_'):
            try:
                by_name = object.__getattribute__(self, '_reg_by_name')
                if name in by_name:
                    return by_name[name]
            except AttributeError:
                pass
        return object.__getattribute__(self, name)

    # ------------------------------------------------------------------
    # Bus interface
    # ------------------------------------------------------------------

    def bus_write(self, offset: int, data: int, strobe: int = 0xF) -> None:
        """Bus-side write to the register at *offset*.

        *strobe* is a byte-enable mask (AXI WSTRB style).  An unknown offset
        is silently ignored in simulation; it is a decode error in RTL.
        """
        reg = self._reg_map.get(offset)
        if reg is None:
            return
        reg.bus_write(data, strobe)

    def bus_read(self, offset: int) -> int:
        """Bus-side read from the register at *offset*; applies onread effects."""
        reg = self._reg_map.get(offset)
        if reg is None:
            return 0
        return reg.bus_read()

    def connect(self, bus_port) -> None:
        """Bind to a bus port.

        The port's ``bind(regfile)`` method is called; after that, the port
        drives :meth:`bus_write` / :meth:`bus_read` automatically.
        """
        self._bus_port = bus_port
        bus_port.bind(self)

    def reset(self) -> None:
        """Restore all fields in all registers to their declared reset values."""
        for reg in self._reg_map.values():
            reg.reset()

    def read_all(self, regs: List[RegisterRT]):
        """Return list of :class:`~.register_rt.RegisterValue` snapshots."""
        return [r.read() for r in regs]
