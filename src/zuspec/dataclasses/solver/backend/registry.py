"""Back-end registry — discovers and selects solver back-ends.

Discovery order
---------------
1. Check ``ZSP_SOLVER_BACKEND`` environment variable for an explicit name.
2. Iterate registered entry-points in ``zuspec.solver.backend`` group.
3. Return the first *available* back-end whose ``name`` matches (or the
   first available one if no env-var is set).
4. Always fall back to ``PythonSolverBackend``.

The registry caches the discovered back-end list (expensive entry-point
scanning) but re-evaluates the *selection* on every call so that tests
can freely switch ``ZSP_SOLVER_BACKEND`` with ``monkeypatch.setenv``.
"""
from __future__ import annotations

import os
from typing import List, Optional

from .base import SolverBackend
from .python_backend import PythonSolverBackend

_PYTHON_BACKEND = PythonSolverBackend()

# Known error values that should raise instead of falling back
_SENTINEL = object()

# Cache for the discovered back-end list.  Entry-point scanning is expensive
# (~5 ms) and the installed packages don't change at runtime.
_BACKENDS_CACHE = None


def _discover_backends() -> List[SolverBackend]:
    """Load all back-ends declared via the ``zuspec.solver.backend`` entry-point group.

    The built-in Python back-end is always included at the end as a fallback.
    Results are cached after the first call.
    """
    global _BACKENDS_CACHE
    if _BACKENDS_CACHE is not None:
        return _BACKENDS_CACHE

    backends: List[SolverBackend] = []

    try:
        from importlib.metadata import entry_points
        eps = entry_points(group="zuspec.solver.backend")
        for ep in eps:
            # Skip the python entry-point — we include it explicitly below
            if ep.name == "python":
                continue
            try:
                cls = ep.load()
                backend = cls()
                if isinstance(backend, SolverBackend):
                    backends.append(backend)
            except Exception:
                pass  # unavailable or broken plug-in — skip silently
    except Exception:
        pass  # importlib.metadata not available (old Python) — use built-in only

    # Always include the Python back-end as the guaranteed fallback
    backends.append(_PYTHON_BACKEND)
    _BACKENDS_CACHE = backends
    return backends


def get_backend(name: Optional[str] = None) -> SolverBackend:
    """Return the active solver back-end.

    Parameters
    ----------
    name:
        Override the back-end name.  If *None*, the value of
        ``ZSP_SOLVER_BACKEND`` is used; if that is also unset, the first
        available back-end is returned (native preferred over python when
        both are registered).

    Raises
    ------
    ValueError
        When an explicit name is requested (via argument or env-var) but no
        registered back-end with that name exists or is available.
    """
    requested = name or os.environ.get("ZSP_SOLVER_BACKEND")

    backends = _discover_backends()

    if requested:
        for backend in backends:
            if backend.name == requested:
                if not backend.available:
                    raise ValueError(
                        f"Solver back-end {requested!r} is registered but not "
                        "available on this host (library missing or import failed)."
                    )
                return backend
        raise ValueError(
            f"Unknown solver back-end {requested!r}. "
            f"Available names: {[b.name for b in backends]}"
        )

    # No explicit request — return first available
    for backend in backends:
        if backend.available:
            return backend

    # Should never reach here because PythonSolverBackend.available is always True
    return _PYTHON_BACKEND  # pragma: no cover
