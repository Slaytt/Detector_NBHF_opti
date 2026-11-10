"""Step 7: end-to-end equivalence of B with A*, file by file, then the whole program.

Verification tooling written by Claude (Anthropic); not part of the port itself.

For each of the 24 files of jeu_equivalence/wav/, B runs the whole chain (read, filter,
threshold, detection, fusion) and is compared with A*'s own output files
(jeu_equivalence/references_A_v2/):
    - number of clicks per channel and after fusion
    - max date error, in samples (objective: 0)
    - precision, recall and F1 of B against A, a click matching within 1 sample (objective: 1)
    - the output files, written with nbhf.output, identical byte for byte
Then the main program (run_detector.runDetector) is run on a 2-file list, and its files
(Res_*.txt and BilanTot.txt, except the duration line) are compared with A*'s.

Expected interface (rename here if you choose other names):
    nbhf.detector.Detector(params)
        .detectFile(path) -> result with attributes
            dates1: 1-D float64 array, accepted dates of channel 1, in detection order
            dates2: same for channel 2, or None for a mono file
            merged: (N, 2) float64 array, from mergeChannels
    run_detector.runDetector(wavDir, listFile, outDir, params) -> None
        reads the file names in listFile (one per line, A's liste.txt), runs the detector
        on each, writes Res_<name>.txt (+ _Canal1/_Canal2 for stereo) and BilanTot.txt
        in outDir, in the order of the list; the last line holds the elapsed time.

Takes ~5 min (the detection loop is the cost, as in A).
"""

from pathlib import Path

import numpy as np
import pytest

from nbhf.detector import Detector
from nbhf.output import writeChannel, writeMerged
from nbhf.parameters import Parameters
from nbhf.reading import read_info
from run_detector import runDetector

HERE = Path(__file__).resolve().parent
WAV_DIR = HERE.parent.parent / "jeu_equivalence" / "wav"
RES_DIR = HERE.parent.parent / "jeu_equivalence" / "references_A_v2"
A_LIST = HERE.parent.parent / "run_bahia" / "liste_fichiers_extrait.txt"

FILES = sorted(p.name for p in WAV_DIR.glob("*.wav"))


def _same_text(ours, expected, context):
    if ours == expected:
        return
    a, b = ours.split("\n"), expected.split("\n")
    for k, (la, lb) in enumerate(zip(a, b), 1):
        if la != lb:
            raise AssertionError(f"{context}: line {k} differs:\n  B: {la!r}\n  A: {lb!r}")
    raise AssertionError(f"{context}: {len(a)} lines, A has {len(b)} (same up to the shorter one)")


def _compare_dates(ours, a_dates, fm, context):
    """Counts, max error in samples, precision / recall / F1 with a 1-sample matching."""
    ours = np.sort(np.asarray(ours, dtype=float))
    a_dates = np.sort(np.asarray(a_dates, dtype=float))
    tol = 1.0 / fm  # one sample

    matched = 0
    j = 0
    for d in ours:
        while j < len(a_dates) and a_dates[j] < d - tol:
            j += 1
        if j < len(a_dates) and abs(a_dates[j] - d) <= tol:
            matched += 1
            j += 1
    precision = matched / len(ours) if len(ours) else 1.0
    recall = matched / len(a_dates) if len(a_dates) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    err_samples = (np.abs(ours - a_dates).max() * fm) if len(ours) == len(a_dates) and len(ours) else float("nan")

    print(f"\n{context}: B {len(ours)} clicks, A {len(a_dates)}; "
          f"precision {precision:.4f}, recall {recall:.4f}, F1 {f1:.4f}; "
          f"max date error {err_samples:.3g} samples")
    assert len(ours) == len(a_dates), f"{context}: {len(ours)} clicks, A has {len(a_dates)}"
    assert matched == len(a_dates), f"{context}: only {matched}/{len(a_dates)} clicks match A within 1 sample"
    assert err_samples <= 1e-6, f"{context}: max date error {err_samples:.3g} samples"


@pytest.mark.parametrize("file", FILES)
def test_file(file, tmp_path):
    path = WAV_DIR / file
    info = read_info(path)
    stem = Path(file).stem

    result = Detector(Parameters()).detectFile(path)

    a_merged = np.loadtxt(RES_DIR / f"Res_{stem}.txt", delimiter="\t", ndmin=2)
    if info.n_channels > 1:
        for canal, dates in ((1, result.dates1), (2, result.dates2)):
            a_dates = np.loadtxt(RES_DIR / f"Res_{stem}_Canal{canal}.txt", ndmin=1)
            _compare_dates(dates, a_dates, info.sample_rate, f"{file} channel {canal}")
    else:
        assert result.dates2 is None, f"{file} is mono, dates2 should be None"
    _compare_dates(result.merged[:, 0], a_merged[:, 0], info.sample_rate, f"{file} merged")
    assert np.array_equal(result.merged[:, 1], a_merged[:, 1]), f"{file}: canal column differs after fusion"

    # the files, byte for byte
    out = tmp_path / f"Res_{stem}.txt"
    writeMerged(out, result.merged)
    _same_text(out.read_text(encoding="utf-8"), (RES_DIR / out.name).read_text(encoding="utf-8"), out.name)
    if info.n_channels > 1:
        for canal, dates in ((1, result.dates1), (2, result.dates2)):
            out = tmp_path / f"Res_{stem}_Canal{canal}.txt"
            writeChannel(out, dates)
            _same_text(out.read_text(encoding="utf-8"), (RES_DIR / out.name).read_text(encoding="utf-8"), out.name)


def test_program(tmp_path):
    """The main program on a 2-file list (one stereo, one mono), against A*'s files."""
    names = ["FichierTest_FitzRoy.wav", "6209.260521181508.wav"]
    list_file = tmp_path / "liste.txt"
    list_file.write_text("".join(n + "\n" for n in names), encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    runDetector(WAV_DIR, list_file, out_dir, Parameters())

    for name in names:
        stem = Path(name).stem
        for suffix in ("", "_Canal1", "_Canal2"):
            ref = RES_DIR / f"Res_{stem}{suffix}.txt"
            out = out_dir / ref.name
            if not ref.exists():
                assert not out.exists(), f"{out.name} written for a mono file"
                continue
            _same_text(out.read_text(encoding="utf-8"), ref.read_text(encoding="utf-8"), out.name)

    # BilanTot.txt: header, the two file lines, blank line, then 'Duree totale %f s '
    a_lines = (RES_DIR / "BilanTot.txt").read_text(encoding="utf-8").split("\n")
    b_lines = (out_dir / "BilanTot.txt").read_text(encoding="utf-8").split("\n")
    assert b_lines[:5] == a_lines[:5], "BilanTot.txt: header differs"
    a_file_lines = {l.split(" \t ")[0]: l for l in a_lines[5:] if l.endswith(".wav") or " \t " in l}
    for k, name in enumerate(names):
        assert b_lines[5 + k] == a_file_lines[name], f"BilanTot.txt: line for {name} differs"
    assert b_lines[5 + len(names)] == ""
    assert b_lines[6 + len(names)].startswith("Duree totale ") and b_lines[6 + len(names)].endswith(" s ")
    assert b_lines[7 + len(names):] == [""]
