"""``zdc.Queue[T]`` and ``zdc.queue(depth=N)`` — bounded FIFO.

At simulation time a ``QueueRT`` backed by ``asyncio.Queue`` is returned.
At synthesis the IR extractor records the depth and element type and maps
the FIFO to a synchronous FIFO RTL structure.

Usage::

    @zdc.dataclass
    class MyComp(zdc.Component):
        _req_q: zdc.Queue[LoadReq] = zdc.queue(depth=4)

        @zdc.proc
        async def _producer(self):
            while True:
                req = LoadReq(addr=self.addr)
                await self._req_q.put(req)

        @zdc.proc
        async def _consumer(self):
            while True:
                req = await self._req_q.get()
                ...
"""
from __future__ import annotations

import warnings
from typing import Generic, TypeVar

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Lowering protocols (optional — zuspec-ir-core may not be installed)
# ---------------------------------------------------------------------------
try:
    from zuspec.ir.core.interfaces import (
        Lowerable,
        ElaboratableInterface,
        SVEmittableInterface,
        SVAEmittableInterface,
        CSimEmittableInterface,
    )
    from zuspec.ir.core.abstraction_field_ir import AbstractionFieldIR
    _INTERFACES_AVAILABLE = True
except ImportError:
    class Lowerable:              pass  # noqa: E701
    class ElaboratableInterface:  pass  # noqa: E701
    class SVEmittableInterface:   pass  # noqa: E701
    class SVAEmittableInterface:  pass  # noqa: E701
    class CSimEmittableInterface: pass  # noqa: E701
    AbstractionFieldIR = None
    _INTERFACES_AVAILABLE = False


class Queue(
    Lowerable,
    ElaboratableInterface,
    SVEmittableInterface,
    SVAEmittableInterface,
    CSimEmittableInterface,
    Generic[T],
):
    """Bounded FIFO for inter-process communication inside a component.

    ``depth`` is mandatory and controls:
    - Python runtime: ``asyncio.Queue(maxsize=depth)``
    - C runtime: static ring buffer of ``depth`` elements
    - Synthesis: FIFO depth parameter

    Implements the Zuspec interface-dispatch protocols so that
    ``DataModelFactory`` can register it in the global lowering registry
    and ``AbstractionSVLowerPass`` can generate a synchronous FIFO module.
    """

    def __class_getitem__(cls, item):
        return _QueueAlias(cls, item)

    async def put(self, item: T) -> None:
        """Block until space is available, then enqueue ``item``."""
        raise NotImplementedError

    async def get(self) -> T:
        """Block until an item is available, then dequeue and return it."""
        raise NotImplementedError

    def qsize(self) -> int:
        """Return the number of items currently in the queue."""
        raise NotImplementedError

    def full(self) -> bool:
        """True if the queue has reached its depth limit."""
        raise NotImplementedError

    def empty(self) -> bool:
        """True if the queue contains no items."""
        raise NotImplementedError

    # ── Self-describing lowering interface ───────────────────────────────────

    @classmethod
    def elaborate_field(cls, *, field_name, field_index, inst_kwargs,
                        element_type=None):
        """Build an ``AbstractionFieldIR`` from a ``Queue[T]`` field.

        ``element_type`` is the element type ``T``; its bit width is used to
        size the generated FIFO.  ``inst_kwargs`` carries ``DEPTH``
        (from ``zdc.inst(zdc.Queue, kwargs={'DEPTH': N})``); default depth=8.
        """
        if AbstractionFieldIR is None:
            raise RuntimeError('zuspec-ir-core is not installed')
        depth = int(inst_kwargs.get('DEPTH', 8))
        elem_width = _extract_elem_width(element_type)
        ir_node = {
            'name': field_name,
            'elem_width': elem_width,
            'depth': depth,
            'element_type': element_type,
        }
        return AbstractionFieldIR(
            spec_type_name='Queue',
            field_name=field_name,
            field_index=field_index,
            py_cls=cls,
            inst_kwargs=inst_kwargs,
            ir_node=ir_node,
        )

    @classmethod
    def sv_module_text(cls, field_ir) -> str:
        """Return a complete synchronous FIFO SV module for this queue."""
        from zuspec.synth.ir.protocol_ir import QueueIR
        from zuspec.synth.sprtl.protocol_sv import generate_fifo_sv
        n = field_ir.ir_node
        q = QueueIR(name=n['name'], elem_width=n['elem_width'], depth=n['depth'])
        return generate_fifo_sv(q)

    @classmethod
    def sv_instance_text(cls, field_ir, parent_prefix: str = '') -> str:
        """Return the SV instantiation snippet for this FIFO."""
        n = field_ir.ir_node
        fn = n['name']
        return (
            f'{fn}_fifo u_{fn}_fifo (\n'
            f'  .clk(clk),\n'
            f'  .rst(rst),\n'
            f'  .wr_en({fn}_wr_en),\n'
            f'  .wr_data({fn}_wr_data),\n'
            f'  .full({fn}_full),\n'
            f'  .rd_en({fn}_rd_en),\n'
            f'  .rd_data({fn}_rd_data),\n'
            f'  .empty({fn}_empty),\n'
            f'  .count({fn}_count)\n'
            f');'
        )

    @classmethod
    def rewrite_proc_stmts(cls, stmts, field_ir):
        """Pass-through: FIFO signal connections are generated as port wires."""
        return stmts

    @classmethod
    def sva_assert_properties(cls, field_ir):
        """Return SVA properties asserting FIFO does not overflow or underflow."""
        fn = field_ir.ir_node['name']
        return [
            f'ap_{fn}_no_overflow: assert property (\n'
            f'  @(posedge clk) disable iff (rst)\n'
            f'  !({fn}_wr_en && {fn}_full)\n'
            f');',
            f'ap_{fn}_no_underflow: assert property (\n'
            f'  @(posedge clk) disable iff (rst)\n'
            f'  !({fn}_rd_en && {fn}_empty)\n'
            f');',
        ]

    @classmethod
    def sva_assume_properties(cls, field_ir):
        return []

    @classmethod
    def bmc_depth(cls, field_ir) -> int:
        return field_ir.ir_node.get('depth', 8) + 4

    @classmethod
    def cutpoint_signals(cls, field_ir):
        return []

    @classmethod
    def c_header(cls, field_ir) -> str:
        n = field_ir.ir_node
        fn, ew, depth = n['name'], n['elem_width'], n['depth']
        guard = f'_ZDC_{fn.upper()}_FIFO_H_'
        return (
            f'#ifndef {guard}\n#define {guard}\n#include <stdint.h>\n'
            f'// Queue {fn}: depth={depth}, elem_width={ew}\n'
            f'#endif\n'
        )

    @classmethod
    def c_impl(cls, field_ir) -> str:
        n = field_ir.ir_node
        fn, ew, depth = n['name'], n['elem_width'], n['depth']
        return (
            f'// Queue {fn} ring buffer: depth={depth}, elem_width={ew}\n'
        )


class _QueueAlias:
    """``Queue[T]`` subscript result — used for type annotations."""

    def __init__(self, origin, item):
        self._origin = origin
        self._item = item

    def __repr__(self):
        return f"Queue[{self._item!r}]"


def _extract_elem_width(element_type, default: int = 32) -> int:
    """Return the bit width of *element_type*, or *default* if not determinable.

    Handles ``Annotated[int, U(N)]`` types (e.g. ``zdc.u32``) directly.
    For complex ``@zdc.dataclass`` types the width is taken from
    ``ELEM_WIDTH`` if available, otherwise the *default* is returned.
    """
    if element_type is None:
        return default
    from typing import get_args, get_origin, Annotated
    if get_origin(element_type) is Annotated:
        for meta in get_args(element_type)[1:]:
            if hasattr(meta, 'width'):
                return meta.width
    return default


def queue(depth: int, *, element_type=None) -> "Queue":
    """Factory: declare a Queue field on a component.

    ``depth`` is mandatory.  At simulation time returns a ``QueueRT``
    instance backed by ``asyncio.Queue(maxsize=depth)``.

    Example::

        _req_q: zdc.Queue[LoadReq] = zdc.queue(depth=4)

    .. deprecated::
        Prefer ``zdc.inst(zdc.Queue, kwargs={'DEPTH': depth})`` to integrate
        with the interface-dispatch lowering pipeline.
    """
    if depth < 1:
        raise ValueError(f"queue(depth=...) requires depth >= 1, got {depth}")
    warnings.warn(
        "zdc.queue(depth=N) is deprecated; use "
        "zdc.inst(zdc.Queue, kwargs={'DEPTH': N}) instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from zuspec.be.py.rt.queue_rt import QueueRT
    return QueueRT(depth=depth, element_type=element_type)
