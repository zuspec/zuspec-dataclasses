"""Tests for the solver back-end registry (Phase 1).

Covers:
- Python back-end is always discoverable and available.
- ``ZSP_SOLVER_BACKEND=python`` forces the Python back-end.
- Unknown back-end name raises ``ValueError``.
- ``get_backend()`` returns a ``SolverBackend``-protocol-compatible object.
- The Python back-end's ``randomize()`` method works end-to-end.
"""
import pytest

import zuspec.dataclasses as zdc
from zuspec.dataclasses.solver.backend import SolverBackend, get_backend, PythonSolverBackend
from zuspec.dataclasses.solver._core_solve import RandomizationError


# ------------------------------------------------------------------ #
# A minimal dataclass for end-to-end tests                            #
# ------------------------------------------------------------------ #

@zdc.dataclass
class _Simple:
    x: zdc.rand(domain=(0, 15), default=0)
    y: zdc.rand(domain=(0, 15), default=0)

    @zdc.constraint
    def c_xy(self):
        assert self.x < self.y


# ------------------------------------------------------------------ #
# Registry tests                                                      #
# ------------------------------------------------------------------ #

class TestGetBackend:
    def test_default_returns_available_backend(self):
        backend = get_backend()
        assert backend is not None
        assert backend.available

    def test_default_is_solver_backend(self):
        backend = get_backend()
        assert isinstance(backend, SolverBackend)

    def test_env_python_returns_python_backend(self, monkeypatch):
        monkeypatch.setenv("ZSP_SOLVER_BACKEND", "python")
        backend = get_backend()
        assert backend.name == "python"

    def test_explicit_name_python(self):
        backend = get_backend(name="python")
        assert backend.name == "python"
        assert isinstance(backend, PythonSolverBackend)

    def test_unknown_name_raises(self):
        with pytest.raises(ValueError, match="Unknown solver back-end"):
            get_backend(name="nonexistent_backend_xyz")

    def test_unknown_env_raises(self, monkeypatch):
        monkeypatch.setenv("ZSP_SOLVER_BACKEND", "nonexistent_backend_xyz")
        with pytest.raises(ValueError, match="Unknown solver back-end"):
            get_backend()

    def test_env_cleared_returns_default(self, monkeypatch):
        monkeypatch.delenv("ZSP_SOLVER_BACKEND", raising=False)
        backend = get_backend()
        assert backend.available


# ------------------------------------------------------------------ #
# PythonSolverBackend unit tests                                      #
# ------------------------------------------------------------------ #

class TestPythonSolverBackend:
    def setup_method(self):
        self.backend = PythonSolverBackend()

    def test_name(self):
        assert self.backend.name == "python"

    def test_available(self):
        assert self.backend.available is True

    def test_str_protocol(self):
        # Protocol check via isinstance
        assert isinstance(self.backend, SolverBackend)

    def test_randomize_updates_fields(self):
        obj = _Simple(x=0, y=0)
        self.backend.randomize(obj)
        assert 0 <= obj.x <= 15
        assert 0 <= obj.y <= 15
        assert obj.x < obj.y

    def test_randomize_with_seed_is_deterministic(self):
        obj1 = _Simple(x=0, y=0)
        obj2 = _Simple(x=0, y=0)
        self.backend.randomize(obj1, seed=42)
        self.backend.randomize(obj2, seed=42)
        assert obj1.x == obj2.x
        assert obj1.y == obj2.y

    def test_randomize_different_seeds_differ(self):
        results = set()
        for seed in range(20):
            obj = _Simple(x=0, y=0)
            self.backend.randomize(obj, seed=seed)
            results.add((obj.x, obj.y))
        # With 20 seeds and a 15-value domain, we expect some variety
        assert len(results) > 1

    def test_randomize_with_not_implemented(self):
        obj = _Simple(x=0, y=0)
        with pytest.raises(NotImplementedError):
            self.backend.randomize_with(obj, with_block=None)


# ------------------------------------------------------------------ #
# Integration: api.randomize() goes through the backend               #
# ------------------------------------------------------------------ #

class TestApiDelegation:
    def test_randomize_via_api(self, monkeypatch):
        monkeypatch.setenv("ZSP_SOLVER_BACKEND", "python")
        obj = _Simple(x=0, y=0)
        zdc.randomize(obj)
        assert obj.x < obj.y

    def test_backend_swap_via_env(self, monkeypatch):
        """Forcing python back-end via env var works transparently."""
        monkeypatch.setenv("ZSP_SOLVER_BACKEND", "python")
        obj = _Simple(x=0, y=0)
        zdc.randomize(obj, seed=7)
        x_with_env, y_with_env = obj.x, obj.y

        monkeypatch.delenv("ZSP_SOLVER_BACKEND")
        obj2 = _Simple(x=0, y=0)
        zdc.randomize(obj2, seed=7)
        # Both use python back-end (default), results must match
        assert obj2.x == x_with_env
        assert obj2.y == y_with_env
