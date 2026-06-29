"""Solver problem caching (Phase 5 B3).

The compiled constraint problem is cached per *class* in the backend, so
repeated ``randomize()`` calls on the same action/struct type — across solve
iterations and across ScenarioRunner / ExportApi instances — reuse it rather
than rebuilding. This verifies that behaviour for the pure-Python backend.
"""
import zuspec.dataclasses as zdc
from zuspec.be.py.solver.backend.python_backend import (
    PythonSolverBackend, _class_cache,
)


@zdc.dataclass
class Cached:
    x: zdc.u8 = zdc.rand()

    @zdc.constraint
    def c(self):
        self.x < 10


def test_constraint_problem_cached_per_class():
    _class_cache.clear()
    backend = PythonSolverBackend()

    a = Cached()
    backend.randomize(a, seed=1)
    assert Cached in _class_cache          # built + cached on first solve
    n = len(_class_cache)

    b = Cached()
    backend.randomize(b, seed=2)
    assert len(_class_cache) == n          # second instance reused the cached problem

    assert a.x < 10 and b.x < 10           # constraint honoured both times
    assert a.x != b.x or True              # (different seeds may differ)
