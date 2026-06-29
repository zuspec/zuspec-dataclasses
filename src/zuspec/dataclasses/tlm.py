"""Compatibility shim — TLM port/channel protocols moved to ``zuspec.be.py.model.tlm``.

``Channel`` / ``GetIF`` / ``PutIF`` / ``Transport`` are object-model type protocols
(the component factory does identity checks against them), so they relocated with
the object model into the Python backend.  Re-exported here for compatibility.

See docs/be-py-runtime-relocation-design.md (Phase 4).
"""
from zuspec.be.py.model import tlm as _src

for _name, _val in list(vars(_src).items()):
    if not _name.startswith("__"):
        globals()[_name] = _val

del _name, _val, _src
