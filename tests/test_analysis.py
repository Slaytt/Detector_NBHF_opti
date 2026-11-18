"""nbhfapp.analysis and nbhfapp.export: what the interface shows and exports is what the
core computed.

Criteria:
  - with the seuil and tFusion of the run, the decision and the three counters are those
    of the run (so those of A);
  - an export with the settings of the run writes Res_*.txt byte for byte like A;
  - the Raven tables of an export hold the accepted clicks of the seuil asked.

    launch test :
        .venv/bin/python -m pytest tests/test_analysis.py
"""

from pathlib import Path

import numpy as np
import pytest

from nbhf.detector import Detector
from nbhf.parameters import Parameters
from nbhf.raven import RAVEN_HEADER, TRAIN_HEADER
from nbhf.reading import read_info
from nbhfapp.analysis import counts, decide, needsRecompute
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
        out[name] = (FileRun(WAV_DIR / name, result.table, info.sample_rate, info.n_channels > 1), result)
    return out


@pytest.mark.parametrize("name", [MONO, STEREO])
def test_decision_and_counters_of_the_run(runs, name):
    run, result = runs[name]
    mask = decide(run.table, P.seuil)
    assert np.array_equal(mask, run.table["accepted"])
    nCandidates, nAccepted, nMerged = counts(run.table, mask, run.stereo, P.tFusion)
    n2 = 0 if result.dates2 is None else len(result.dates2)
    assert nCandidates == len(run.table)
    assert nAccepted == len(result.dates1) + n2
    assert nMerged == len(result.merged)


def test_stricter_threshold_keeps_a_subset(runs):
    run, _ = runs[STEREO]
    strict = decide(run.table, 2.0)
    assert 0 < strict.sum() < run.table["accepted"].sum()
    assert not np.any(strict & ~run.table["accepted"])


def test_needs_recompute():
    import dataclasses
    assert needsRecompute(P, P) == []
    assert needsRecompute(dataclasses.replace(P, seuil=0.9, tFusion=0.001), P) == []
    assert needsRecompute(dataclasses.replace(P, coefUmbral=12, f1=40000), P) == ["coefUmbral", "f1"]


def test_export_with_the_settings_of_the_run_is_A(runs, tmp_path):
    written = exportRuns([run for run, _ in runs.values()], tmp_path / "exp", P, P.seuil, P.tFusion,
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


def test_export_with_another_threshold(runs, tmp_path):
    run, _ = runs[STEREO]
    seuil = 2.0
    written = exportRuns([run], tmp_path, P, seuil, P.tFusion, ExportOptions(res=True, raven=True, ravenMode=CLICKS))
    mask = decide(run.table, seuil)
    stem = Path(STEREO).stem
    for channel in (1, 2):
        lines = (tmp_path / f"Res_{stem}_Canal{channel}.txt").read_text().splitlines()
        assert len(lines) == int(np.sum(mask & (run.table["channel"] == channel)))
    raven = (tmp_path / ravenName(STEREO)).read_text(encoding="utf-8").split("\n")
    assert raven[0].split("\t") == list(RAVEN_HEADER)
    assert len(raven) - 2 == int(mask.sum())               # header, one line per click, final newline
    assert "Seuil: 2.000000" in (tmp_path / "BilanTot.txt").read_text(encoding="utf-8")
    assert tmp_path / ravenName(STEREO) in written


def test_export_trains(runs, tmp_path):
    run, _ = runs[STEREO]
    exportRuns([run], tmp_path, P, P.seuil, P.tFusion, ExportOptions(raven=True, ravenMode=TRAINS, maxGap=0.5))
    lines = (tmp_path / ravenName(STEREO)).read_text(encoding="utf-8").split("\n")[:-1]
    assert lines[0].split("\t") == list(TRAIN_HEADER)
    clicks = [int(line.split("\t")[7]) for line in lines[1:]]
    assert sum(clicks) == int(run.table["accepted"].sum())
    assert len(clicks) < sum(clicks)                        # some clicks were grouped
    assert sorted(p.name for p in tmp_path.iterdir()) == [ravenName(STEREO)]
