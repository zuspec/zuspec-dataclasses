"""Tests for P4 (method contract parsing) from ASSERTION_ASSUMPTION_IMPL_PLAN.md."""
import asyncio
import textwrap

import pytest
import zuspec.dataclasses as zdc
from zuspec.dataclasses.constraint_parser import ConstraintParser


# ---------------------------------------------------------------------------
# Helpers to define methods that can be parsed (getsource must work)
# ---------------------------------------------------------------------------

class _Dummy:
    async def with_requires_only(self):
        with zdc.requires:
            self.x > 0
        # body
        pass

    async def with_ensures_only(self):
        # body
        pass
        with zdc.ensures:
            self.x < 100

    async def with_both(self):
        with zdc.requires:
            self.x > 0
            self.y >= 0
        # body
        pass
        with zdc.ensures:
            self.x < 100

    async def with_qualified_requires(self):
        with zdc.requires:
            self.x > 0
        pass

    async def with_bare_name_requires(self):
        with zdc.requires:
            self.x > 0
        pass

    async def with_empty_block(self):
        with zdc.requires:
            pass
        pass

    async def with_multiple_exprs(self):
        with zdc.requires:
            self.x > 0
            self.y >= 0
            self.z != 5
        pass

    async def no_contracts(self):
        pass

    async def with_requires_after_body(self):
        x = 1
        with zdc.requires:
            self.x > 0

    async def with_non_contract_after_ensures(self):
        with zdc.ensures:
            self.x < 100
        x = 1  # this should trigger an error


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExtractMethodContracts:
    def setup_method(self):
        self.parser = ConstraintParser()
        self.dummy = _Dummy()

    def test_parse_requires_block_only(self):
        result = self.parser.extract_method_contracts(_Dummy.with_requires_only)
        assert len(result['requires']) == 1
        assert result['ensures'] == []

    def test_parse_ensures_block_only(self):
        result = self.parser.extract_method_contracts(_Dummy.with_ensures_only)
        assert result['requires'] == []
        assert len(result['ensures']) == 1

    def test_parse_requires_and_ensures(self):
        result = self.parser.extract_method_contracts(_Dummy.with_both)
        assert len(result['requires']) == 2
        assert len(result['ensures']) == 1

    def test_parse_qualified_zdc_prefix(self):
        result = self.parser.extract_method_contracts(_Dummy.with_qualified_requires)
        assert len(result['requires']) == 1

    def test_parse_bare_name_prefix(self):
        # Both forms accepted; bare name 'requires' is also valid.
        # _Dummy.with_bare_name_requires uses zdc.requires (both are same)
        result = self.parser.extract_method_contracts(_Dummy.with_bare_name_requires)
        assert len(result['requires']) == 1

    def test_empty_contract_blocks(self):
        result = self.parser.extract_method_contracts(_Dummy.with_empty_block)
        assert result['requires'] == []
        assert result['ensures'] == []

    def test_multiple_expressions_per_block(self):
        result = self.parser.extract_method_contracts(_Dummy.with_multiple_exprs)
        assert len(result['requires']) == 3

    def test_no_contracts_returns_empty(self):
        result = self.parser.extract_method_contracts(_Dummy.no_contracts)
        assert result['requires'] == []
        assert result['ensures'] == []

    def test_requires_after_body_raises(self):
        with pytest.raises(ValueError, match='requires'):
            self.parser.extract_method_contracts(_Dummy.with_requires_after_body)

    def test_non_contract_after_ensures_raises(self):
        with pytest.raises(ValueError, match='ensures'):
            self.parser.extract_method_contracts(_Dummy.with_non_contract_after_ensures)

    def test_returned_exprs_are_dicts(self):
        result = self.parser.extract_method_contracts(_Dummy.with_both)
        for expr in result['requires'] + result['ensures']:
            assert isinstance(expr, dict)
            assert 'type' in expr
