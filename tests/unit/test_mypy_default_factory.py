import pathlib

from mypy import api


def test_retargetable_default_factory_requires_zuspec_base(tmp_path: pathlib.Path):
    p = tmp_path / "t_default_factory.py"
    p.write_text(
        """
import zuspec.dataclasses as zdc
from zuspec.dataclasses import profiles
from zuspec.dataclasses.rt.lock_rt import LockRT


@zdc.dataclass(profile=profiles.RetargetableProfile)
class C(zdc.Component):
    memif_lock: zdc.Lock = zdc.field(default_factory=LockRT)
""".lstrip()
    )

    cfg = pathlib.Path(__file__).parent.parent.parent / "pyproject.toml"
    out, err, status = api.run(["--config-file", str(cfg), str(p)])

    assert status != 0
    assert "default_factory" in (out + err)
    assert "LockRT" in (out + err)
