"""Compatibility shim — the runtime factory config moved to ``zuspec.be.py.model.config``.

``Config`` (the component-factory singleton) and the ``ObjFactory`` protocol are
object-model infrastructure (``Component.__new__`` builds instances through them),
so they relocated with the object model into the Python backend.  Re-exported here
so existing ``from zuspec.dataclasses.config import X`` imports keep working.

See docs/be-py-runtime-relocation-design.md (Phase 4).
"""
from zuspec.be.py.model import config as _src

for _name, _val in list(vars(_src).items()):
    if not _name.startswith("__"):
        globals()[_name] = _val

del _name, _val, _src
