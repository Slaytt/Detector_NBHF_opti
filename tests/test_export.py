"""nbhfapp.export: what the interface exports is what the run computed.

Criteria:
  - an export writes Res_*.txt byte for byte like A;
  - the Raven tables hold the accepted clicks of the run, one per line or grouped in trains.

    launch test :
        .venv/bin/python -m pytest tests/test_export.py
"""

from pathlib import Path

import pytest

from nbhf.detector import Detector
from nbhf.parameters import Parameters
from nbhf.raven import RAVEN_HEADER, TRAIN_HEADER
from nbhf.reading import read_info
from nbhfapp.export import CLICKS, TRAINS, ExportOptions, FileRun, exportRuns, ravenName

HERE = Path(__file__).resolve().parent
WAV_DIR = HERE.parent / "research" / "jeu_equivalence" / "wav"
RES_DIR = HERE.parent / "research" / "jeu_equivalence" / "references_A_v2"

MONO = "6209.260514052458.wav"
STEREO = "FichierTest_FitzRoy.wav"

if not all((WAV_DIR / f).exists() for f in (MONO, STEREO)):
    pytest.skip("missing wav files in research/jeu_equivalence/wav", allow_module_level=True)

P = Parameters()


@pytest.fixture(scope="module")
def runs():
    out = {}
    for name in (MONO, STEREO):
        info = read_info(WAV_DIR / name)
        result = Detector(P).detectFile(WAV_DIR / name)
        out[name] = FileRun(WAV_DIR / name, result.table, info.sample_rate, info.n_channels > 1,
                            len(result.merged))
    return out


def test_export_is_A(runs, tmp_path):
    written = exportRuns(list(runs.values()), tmp_path / "exp", P,
                         ExportOptions(res=True, raven=False, candidates=True))
    names = sorted(p.name for p in written)
    stems = [Path(MONO).stem, Path(STEREO).stem]
    assert names == sorted([
        "BilanTot.txt",
        f"Res_{stems[0]}.txt", f"Candidats_{stems[0]}.csv",
        f"Res_{stems[1]}.txt", f"Res_{stems[1]}_Canal1.txt", f"Res_{stems[1]}_Canal2.txt",
        f"Candidats_{stems[1]}.csv",
    ])
    for path in written:
        if path.name.startswith("Res_"):
            assert path.read_bytes() == (RES_DIR / path.name).read_bytes(), f"{path.name} differs from A"
    bilan = (tmp_path / "exp" / "BilanTot.txt").read_text(encoding="utf-8")
    assert bilan.startswith("Seuil: 0.400000")
    assert MONO in bilan and STEREO in bilan


def test_export_clicks(runs, tmp_path):
    run = runs[STEREO]
    written = exportRuns([run], tmp_path, P, ExportOptions(raven=True, ravenMode=CLICKS))
    raven = (tmp_path / ravenName(STEREO)).read_text(encoding="utf-8").split("\n")
    assert raven[0].split("\t") == list(RAVEN_HEADER)
    assert len(raven) - 2 == int(run.table["accepted"].sum())   # header, one line per click, final newline
    assert written == [tmp_path / ravenName(STEREO)]


def test_export_trains(runs, tmp_path):
    run = runs[STEREO]
    exportRuns([run], tmp_path, P, ExportOptions(raven=True, ravenMode=TRAINS, maxGap=0.5))
    lines = (tmp_path / ravenName(STEREO)).read_text(encoding="utf-8").split("\n")[:-1]
    assert lines[0].split("\t") == list(TRAIN_HEADER)
    clicks = [int(line.split("\t")[7]) for line in lines[1:]]
    assert sum(clicks) == int(run.table["accepted"].sum())
    assert len(clicks) < sum(clicks)                        # some clicks were grouped
    assert sorted(p.name for p in tmp_path.iterdir()) == [ravenName(STEREO)]
