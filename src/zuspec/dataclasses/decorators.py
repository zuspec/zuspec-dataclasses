"""Compatibility shim — the runtime declarators moved to ``zuspec.be.py.model.decorators``.

``zuspec.dataclasses`` is a frontend; the ``@dataclass`` runtime construction and
the field declarators (``field``, ``pool``, ``inst``, ``rand``, ``export``,
``input``/``output``, ``bundle``, …) now live in the Python backend.  This module
re-exports the full namespace of :mod:`zuspec.be.py.model.decorators` so existing
``from zuspec.dataclasses.decorators import X`` imports keep working unchanged
(including private ``_`` names such as ``_LegacyForwardingDecl``).

Transitional note: the relocated ``@dataclass`` still performs the
``activity()``-source → IR parse (an authoring concern) via a lazy back-edge to
``zuspec.dataclasses.activity_parser``; that authoring half lifts back into this
package as a later cleanup (see docs/be-py-runtime-relocation-design.md, Phase 2).
"""
from zuspec.be.py.model import decorators as _src

for _name, _val in list(vars(_src).items()):
    if not _name.startswith("__"):
        globals()[_name] = _val

del _name, _val, _src
