"""Tests for rt/debug_rt.py — _fire_line_event()."""
from __future__ import annotations

import sys
from unittest import mock

from zuspec.dataclasses.rt.debug_rt import _fire_line_event


def test_no_op_without_trace():
    """No-op when sys.gettrace() is None."""
    assert sys.gettrace() is None
    _fire_line_event("test.py", 10, {})  # must not raise


def test_no_op_empty_filename():
    """Empty filename is silently skipped even with trace active."""
    fired_lines = []
    def tracer(frame, event, arg):
        if event == "line" and frame.f_code.co_filename == "":
            fired_lines.append(event)
        return tracer
    sys.settrace(tracer)
    try:
        _fire_line_event("", 10, {})
    finally:
        sys.settrace(None)
    assert len(fired_lines) == 0


def test_no_op_zero_lineno():
    """lineno=0 is silently skipped."""
    fired_lines = []
    def tracer(frame, event, arg):
        if event == "line" and frame.f_lineno == 0:
            fired_lines.append(event)
        return tracer
    sys.settrace(tracer)
    try:
        _fire_line_event("test.py", 0, {})
    finally:
        sys.settrace(None)
    assert len(fired_lines) == 0


def test_trace_callback_called():
    """Installing a sys.settrace spy; _fire_line_event causes it to fire."""
    fired = []
    def tracer(frame, event, arg):
        if event == "line":
            fired.append(frame.f_code.co_filename)
        return tracer
    sys.settrace(tracer)
    try:
        _fire_line_event("my_source.py", 42, {})
    finally:
        sys.settrace(None)
    assert "my_source.py" in fired


def test_trace_filename_matches():
    """Trace callback receives frame.f_code.co_filename == filename."""
    seen_files = []
    def tracer(frame, event, arg):
        if event == "line":
            seen_files.append(frame.f_code.co_filename)
        return tracer
    sys.settrace(tracer)
    try:
        _fire_line_event("exact_file.py", 5, {})
    finally:
        sys.settrace(None)
    assert "exact_file.py" in seen_files


def test_trace_lineno_matches():
    """Trace callback receives frame.f_lineno == lineno."""
    seen_lines = []
    def tracer(frame, event, arg):
        if event == "line":
            seen_lines.append(frame.f_lineno)
        return tracer
    sys.settrace(tracer)
    try:
        _fire_line_event("test.py", 99, {})
    finally:
        sys.settrace(None)
    assert 99 in seen_lines


def test_trace_with_none_local_vars():
    """Passing local_vars=None does not raise."""
    def tracer(frame, event, arg):
        return tracer
    sys.settrace(tracer)
    try:
        _fire_line_event("test.py", 1, None)
    finally:
        sys.settrace(None)
