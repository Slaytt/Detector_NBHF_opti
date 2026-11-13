"""Checkpoint of step 7a: the Parameters dataclass, compared with A*'s parameter block.

Verification tooling written by Claude (Anthropic); not part of the port itself.

The defaults of Parameters must be EXACTLY the values of A* (run_bahia/DetectorNBHF_todos_passe_bande.m,
block %%% PARAMETROS), written as in Octave (t_minimo = 1/1000, t_fusion = 5/10000). They are read
from the .m file here, so that the test fails if A* changes.
t_detect (0.0015) is declared in A but never used: not a field of Parameters.

Expected interface of nbhf.parameters (rename here if you choose other names):
    @dataclass(frozen=True)
    class Parameters:
        coefUmbral, seuil, fcutLow, fcutHigh, f1clic, f2clic, f1, f2, tMinimo, chunkDuration, tFusion
    Parameters.fromToml(path) -> Parameters
        a TOML file with some of the field names: the others keep their default.
        An unknown name is an error (TypeError from the dataclass).
"""

import dataclasses
import re
from pathlib import Path

import pytest

from nbhf.parameters import Parameters

HERE = Path(__file__).resolve().parent
A_STAR = HERE.parent / "research" / "run_bahia" / "DetectorNBHF_todos_passe_bande.m"

# Parameters field -> variable of A*
NAMES = {
    "coefUmbral": "coef_umbral",
    "seuil": "seuil",
    "fcutLow": "fcut_low",
    "fcutHigh": "fcut_high",
    "f1clic": "f1clic",
    "f2clic": "f2clic",
    "f1": "f1",
    "f2": "f2",
    "tMinimo": "t_minimo",
    "chunkDuration": "t_trozo",
    "tFusion": "t_fusion",
}


def _a_star_values():
    """The parameter block of A*, evaluated as Octave would (plain numbers and divisions)."""
    text = A_STAR.read_text(encoding="utf-8", errors="replace")
    values = {}
    for name in NAMES.values():
        m = re.search(rf"^{re.escape(name)}\s*=\s*([0-9./]+)\s*;?\s*$", text, re.MULTILINE)
        assert m, f"{name} not found in A*"
        values[name] = eval(m.group(1), {"__builtins__": {}})  # noqa: S307 - digits and '/' only
    return values


def test_fields():
    fields = {f.name for f in dataclasses.fields(Parameters)}
    assert fields == set(NAMES), f"fields: {sorted(fields)}"


def test_defaults_are_a_star():
    a_star = _a_star_values()
    params = Parameters()
    for field, name in NAMES.items():
        assert getattr(params, field) == a_star[name], f"{field}: {getattr(params, field)!r} vs A* {name} = {a_star[name]!r}"


def test_frozen():
    params = Parameters()
    with pytest.raises(dataclasses.FrozenInstanceError):
        params.seuil = 0.5  # type: ignore[misc]


def test_from_toml(tmp_path):
    path = tmp_path / "species.toml"
    path.write_text('seuil = 0.6\nf1clic = 110000\n', encoding="utf-8")
    params = Parameters.fromToml(path)
    assert params.seuil == 0.6 and params.f1clic == 110000
    assert params.coefUmbral == Parameters().coefUmbral  # others keep A*'s default

    path.write_text('seuil = 0.6\nunknown = 1\n', encoding="utf-8")
    with pytest.raises(TypeError):
        Parameters.fromToml(path)
