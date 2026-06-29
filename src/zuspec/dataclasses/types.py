"""Compatibility shim — the runtime object model moved to ``zuspec.be.py.model.types``.

``zuspec.dataclasses`` is a frontend; the runtime object model (``Component``,
``Action``, scalar types, pools, field declarators) now lives in the Python
backend.  This module re-exports the full namespace of
:mod:`zuspec.be.py.model.types` so that existing
``from zuspec.dataclasses.types import X`` imports keep working unchanged
(including private ``_`` names that ``import *`` would drop).

See docs/be-py-runtime-relocation-design.md (Phase 2).
"""
from zuspec.be.py.model import types as _src

# Re-bind every public + single-underscore name (skip dunders) so the shim is a
# drop-in for the relocated module, preserving object identity.
for _name, _val in list(vars(_src).items()):
    if not _name.startswith("__"):
        globals()[_name] = _val

del _name, _val, _src
