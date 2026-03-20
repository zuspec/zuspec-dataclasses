#!/usr/bin/env python3
"""PSS LRM Example 45 — DMA Transfer Scenario.

This example translates the canonical PSS DMA compound-action example into
zuspec-dataclasses Python syntax.  Run it directly:

    python examples/activity_dma.py

Expected output shows the parsed activity IR structure.
"""
import dataclasses
import zuspec.dataclasses as zdc
from zuspec.dataclasses.ir.activity import (
    ActivityBind,
    ActivitySequenceBlock,
    ActivityTraversal,
    ActivityAnonTraversal,
    ActivityParallel,
    ActivityRepeat,
    ActivitySelect,
)
from zuspec.dataclasses.ir.visitor import Visitor


# ---------------------------------------------------------------------------
# Model definition
# ---------------------------------------------------------------------------

@zdc.dataclass
class MemSegment(zdc.Struct):
    """Describes a contiguous memory region (base + size)."""
    base: zdc.u32 = zdc.rand()
    size: zdc.u32 = zdc.rand()


@zdc.dataclass
class DataBuff(zdc.Buffer):
    """PSS buffer flow-object — carries data between write and read actions."""
    seg: MemSegment = zdc.field(default=None)


@zdc.dataclass
class DmaChannel(zdc.Resource):
    """DMA hardware channel — exclusively locked by one action at a time."""
    priority: zdc.u4 = zdc.rand()


@zdc.dataclass
class DmaComponent(zdc.Component):
    """Top-level DMA component."""
    pass


@zdc.dataclass
class WriteData(zdc.Action[DmaComponent]):
    """Atomic action: write a data buffer to memory via a DMA channel."""
    data: DataBuff  = zdc.output()      # produces a DataBuff
    chan: DmaChannel = zdc.lock()        # exclusively claims a DMA channel
    size: zdc.u8    = zdc.rand()

    async def body(self):
        # Execution body would call C/SystemVerilog exec tasks
        pass


@zdc.dataclass
class ReadData(zdc.Action[DmaComponent]):
    """Atomic action: read a data buffer from memory via a DMA channel."""
    data: DataBuff  = zdc.input()        # consumes the DataBuff produced by WriteData
    chan: DmaChannel = zdc.lock()

    async def body(self):
        pass


@zdc.dataclass
class DmaXfer(zdc.Action[DmaComponent]):
    """Compound action: sequence a write then a read with a priority constraint."""
    wr: WriteData = zdc.field(default=None)
    rd: ReadData  = zdc.field(default=None)

    async def activity(self):
        self.wr()                        # traverse wr (produces DataBuff)
        with self.rd():                  # traverse rd (consumes DataBuff)
            self.rd.chan.priority > 5    # inline constraint: rd channel priority > 5


# ---------------------------------------------------------------------------
# Stress test: for-loop, parallel, and select
# ---------------------------------------------------------------------------

@zdc.dataclass
class StressTest(zdc.Action[DmaComponent]):
    """Compound action demonstrating repeat, parallel, and select."""
    count: zdc.u8 = zdc.rand()

    async def activity(self):
        for i in range(self.count):
            with zdc.parallel():
                with zdc.do(WriteData) as wr:
                    wr.size > 16
                await zdc.do(ReadData)
            with zdc.select():
                with zdc.branch(weight=70):
                    await zdc.do(DmaXfer)
                with zdc.branch(weight=30):
                    await zdc.do(ReadData)


# ---------------------------------------------------------------------------
# Simple activity printer visitor
# ---------------------------------------------------------------------------

class ActivityPrinter(Visitor):
    """Walks activity IR nodes and prints them indented."""

    def __new__(cls, *args, **kwargs):
        return object.__new__(cls)

    def __init__(self):
        self._indent = 0

    def _p(self, text: str) -> None:
        print("  " * self._indent + text)

    def visitActivitySequenceBlock(self, node) -> None:
        self._p("sequence:")
        self._indent += 1
        for s in node.stmts:
            s.accept(self)
        self._indent -= 1

    def visitActivityTraversal(self, node) -> None:
        c = f" [+{len(node.inline_constraints)} constraint(s)]" if node.inline_constraints else ""
        self._p(f"traversal: {node.handle}{c}")

    def visitActivityAnonTraversal(self, node) -> None:
        label = f" as {node.label}" if node.label else ""
        c = f" [+{len(node.inline_constraints)} constraint(s)]" if node.inline_constraints else ""
        self._p(f"await do({node.action_type}){label}{c}")

    def visitActivityParallel(self, node) -> None:
        self._p("parallel:")
        self._indent += 1
        for s in node.stmts:
            s.accept(self)
        self._indent -= 1

    def visitActivitySchedule(self, node) -> None:
        self._p("schedule:")
        self._indent += 1
        for s in node.stmts:
            s.accept(self)
        self._indent -= 1

    def visitActivityRepeat(self, node) -> None:
        idx = node.index_var or "_"
        self._p(f"repeat ({idx} in range({node.count})):")
        self._indent += 1
        for s in node.body:
            s.accept(self)
        self._indent -= 1

    def visitActivitySelect(self, node) -> None:
        self._p("select:")
        self._indent += 1
        for b in node.branches:
            b.accept(self)
        self._indent -= 1

    def visitSelectBranch(self, node) -> None:
        w = f" weight={node.weight}" if node.weight else ""
        g = f" guard={node.guard}" if node.guard else ""
        self._p(f"branch{w}{g}:")
        self._indent += 1
        for s in node.body:
            s.accept(self)
        self._indent -= 1

    def visitActivityBind(self, node) -> None:
        self._p(f"bind({node.src} → {node.dst})")

    def visitActivityIfElse(self, node) -> None:
        self._p(f"if {node.condition}:")
        self._indent += 1
        for s in node.then_stmts:
            s.accept(self)
        self._indent -= 1
        if node.else_stmts:
            self._p("else:")
            self._indent += 1
            for s in node.else_stmts:
                s.accept(self)
            self._indent -= 1

    def visitActivityConstraint(self, node) -> None:
        self._p(f"constraint({len(node.constraints)} expr(s))")

    def visitActivityDoWhile(self, node) -> None:
        self._p(f"do_while({node.condition}):")
        self._indent += 1
        for s in node.body:
            s.accept(self)
        self._indent -= 1

    def visitActivityWhileDo(self, node) -> None:
        self._p(f"while_do({node.condition}):")
        self._indent += 1
        for s in node.body:
            s.accept(self)
        self._indent -= 1

    def visitActivityForeach(self, node) -> None:
        idx = f"{node.index_var}, " if node.index_var else ""
        self._p(f"foreach ({idx}{node.item_var} in {node.collection}):")
        self._indent += 1
        for s in node.body:
            s.accept(self)
        self._indent -= 1

    def visitActivityReplicate(self, node) -> None:
        label = f" [{node.label}]" if node.label else ""
        self._p(f"replicate{label}({node.count}):")
        self._indent += 1
        for s in node.body:
            s.accept(self)
        self._indent -= 1

    def visitActivityAtomic(self, node) -> None:
        self._p("atomic:")
        self._indent += 1
        for s in node.stmts:
            s.accept(self)
        self._indent -= 1

    def visitActivityMatch(self, node) -> None:
        self._p(f"match {node.subject}:")
        self._indent += 1
        for c in node.cases:
            c.accept(self)
        self._indent -= 1

    def visitMatchCase(self, node) -> None:
        self._p(f"case {node.pattern}:")
        self._indent += 1
        for s in node.body:
            s.accept(self)
        self._indent -= 1

    def visitActivitySuper(self, node) -> None:
        self._p("super().activity()")

    def visitJoinSpec(self, node) -> None:
        self._p(f"join_spec({node.kind})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    printer = ActivityPrinter()

    print("=" * 60)
    print("DmaXfer activity:")
    print("=" * 60)
    DmaXfer.__activity__.accept(printer)

    print()
    print("=" * 60)
    print("StressTest activity:")
    print("=" * 60)
    StressTest.__activity__.accept(printer)

    print()
    print("=" * 60)
    print("Field metadata:")
    print("=" * 60)
    for cls, name in [(WriteData, 'chan'), (WriteData, 'data'),
                      (ReadData, 'chan'), (ReadData, 'data')]:
        fields = {f.name: f for f in dataclasses.fields(cls)}
        f = fields[name]
        print(f"  {cls.__name__}.{name}: {dict(f.metadata)}")


if __name__ == '__main__':
    main()
