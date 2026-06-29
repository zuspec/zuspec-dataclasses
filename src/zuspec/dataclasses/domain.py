"""Compatibility shim — clock/reset domain value classes moved to ``zuspec.be.py.model.domain``.

``ClockDomain`` / ``ResetDomain`` (and friends) are default attributes of the
runtime ``Component`` base, so they relocated with the object model into the
Python backend.  Re-exported here so existing
``from zuspec.dataclasses.domain import X`` imports keep working unchanged.

See docs/be-py-runtime-relocation-design.md (Phase 2).
"""
from zuspec.be.py.model import domain as _src

for _name, _val in list(vars(_src).items()):
    if not _name.startswith("__"):
        globals()[_name] = _val

del _name, _val, _src
