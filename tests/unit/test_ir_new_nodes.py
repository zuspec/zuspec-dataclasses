"""Tier 1 IR unit tests for Phase 0 new IR nodes."""
import pytest
from zuspec.ir.core.data_type import (
    IfProtocolProperties, IfProtocolType, CompletionType, QueueType,
    DataTypeInt,
)
from zuspec.ir.core.stmt import (
    SpawnStmt, SelectStmt, CompletionSetStmt, QueuePutStmt,
)
from zuspec.ir.core.expr import (
    CompletionAwaitExpr, QueueGetExpr, ExprConstant,
)
from zuspec.ir.core.fields import FieldKind
from zuspec.ir.core.visitor import Visitor


# ---------------------------------------------------------------------------
# IfProtocolProperties
# ---------------------------------------------------------------------------

class TestIfProtocolProperties:
    def test_defaults(self):
        p = IfProtocolProperties()
        assert p.max_outstanding == 1
        assert p.in_order is True
        assert p.fixed_latency is None
        assert p.initiation_interval == 1

    def test_custom(self):
        p = IfProtocolProperties(max_outstanding=4, in_order=False, fixed_latency=2)
        assert p.max_outstanding == 4
        assert p.in_order is False
        assert p.fixed_latency == 2


# ---------------------------------------------------------------------------
# IfProtocolType / CompletionType / QueueType
# ---------------------------------------------------------------------------

class TestNewDataTypes:
    def test_if_protocol_type(self):
        props = IfProtocolProperties(max_outstanding=2)
        t = IfProtocolType(properties=props)
        assert t.properties.max_outstanding == 2

    def test_completion_type(self):
        inner = DataTypeInt(bits=32, signed=False)
        t = CompletionType(payload_type=inner)
        assert t.payload_type is inner

    def test_queue_type(self):
        inner = DataTypeInt(bits=8, signed=False)
        t = QueueType(element_type=inner, depth=4)
        assert t.element_type is inner
        assert t.depth == 4

    def test_queue_type_default_depth(self):
        t = QueueType()
        assert t.depth == 1


# ---------------------------------------------------------------------------
# New statement nodes
# ---------------------------------------------------------------------------

class TestNewStmtNodes:
    def _ref(self, val=None):
        return ExprConstant(value=val)

    def test_spawn_stmt(self):
        s = SpawnStmt(coro_call=self._ref("coro"))
        assert s.coro_call.value == "coro"

    def test_select_stmt(self):
        s = SelectStmt(
            queues=[(self._ref("q"), "tag")],
            result_var="item",
            tag_var="tag",
        )
        assert s.result_var == "item"
        assert len(s.queues) == 1

    def test_completion_set_stmt(self):
        s = CompletionSetStmt(
            completion_expr=self._ref("done"),
            value_expr=self._ref(42),
        )
        assert s.value_expr.value == 42

    def test_queue_put_stmt(self):
        s = QueuePutStmt(
            queue_expr=self._ref("q"),
            value_expr=self._ref("item"),
        )
        assert s.value_expr.value == "item"


# ---------------------------------------------------------------------------
# New expression nodes
# ---------------------------------------------------------------------------

class TestNewExprNodes:
    def _ref(self, val=None):
        return ExprConstant(value=val)

    def test_completion_await_expr(self):
        inner = DataTypeInt(bits=32, signed=False)
        e = CompletionAwaitExpr(completion_expr=self._ref("done"), result_type=inner)
        assert e.result_type is inner

    def test_queue_get_expr(self):
        inner = DataTypeInt(bits=8, signed=False)
        e = QueueGetExpr(queue_expr=self._ref("q"), result_type=inner)
        assert e.result_type is inner


# ---------------------------------------------------------------------------
# FieldKind.QueueField
# ---------------------------------------------------------------------------

class TestQueueFieldKind:
    def test_queue_field_kind_exists(self):
        assert hasattr(FieldKind, "QueueField")
        assert FieldKind.QueueField.name == "QueueField"


# ---------------------------------------------------------------------------
# Visitor stubs (no-op, compile without error)
# ---------------------------------------------------------------------------

class TestVisitorStubs:
    def test_all_visitor_stubs_callable(self):
        v = Visitor(None)
        ref = ExprConstant(value=0)
        # All new visitor methods should be no-ops
        v.visitSpawnStmt(SpawnStmt(coro_call=ref))
        v.visitSelectStmt(SelectStmt(result_var="r", tag_var="t"))
        v.visitCompletionSetStmt(CompletionSetStmt(completion_expr=ref, value_expr=ref))
        v.visitQueuePutStmt(QueuePutStmt(queue_expr=ref, value_expr=ref))
        v.visitCompletionAwaitExpr(CompletionAwaitExpr(completion_expr=ref))
        v.visitQueueGetExpr(QueueGetExpr(queue_expr=ref))
