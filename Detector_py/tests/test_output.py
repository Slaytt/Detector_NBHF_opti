"""Checkpoint of step 6: writing of the output files, compared with A*'s own files.

Verification tooling written by Claude (Anthropic); not part of the port itself.

A writes, per file (Resultats_passe_bande/):
    Res_<name>_Canal1.txt, Res_<name>_Canal2.txt   (stereo only) dlmwrite(path, dates):
        one date per line, in DETECTION order (chunk by chunk, strongest first), '%.16g'
    Res_<name>.txt                                 dlmwrite(path, dates_clicks, '\\t'):
        the merged (date, canal) rows, 'date<tab>canal', '%.16g' (canal prints as 1 or 2)
and once, BilanTot.txt:
    fprintf('Seuil: %f, coef_umbral %d, frequence coupure basse %d, frequence coupure haute %d,\\n', ...)
    fprintf('BP du clic %d - %d, BP de référence %d - %d  \\n', ...)
    fprintf('  \\n'); fprintf(' Detections : \\n'); fprintf('Fichier \\t canal 1 \\t canal 2 \\t total \\n')
    per file: fprintf('%s \\t %d \\t %d \\t %d \\n', name, nbclicksCanal1, nbclicksCanal2, nbclicks)
        nbclicksCanal2 is 0 for a mono file; nbclicks is the number of merged rows
    at the end: fprintf('\\n'); fprintf('Duree totale %f s \\n', duracion)
Every line ends with '\\n' (also the last one); the trailing spaces are part of the format.
Python's '%.16g' gives the same text as Octave's (checked on the reference files, 10/11).

References: jeu_equivalence/references_A_v2/ (A*'s own output). Inputs come from
octave_check/outputs/detection.csv (accepted candidates, in loop order = A's detection order)
and from nbhf.fusion.mergeChannels (step 5, validated).

Expected interface of nbhf.output (rename here if you choose other names):
    writeChannel(path, dates)        dates: 1-D array, one '%.16g' per line
    writeMerged(path, rows)          rows: (N, 2) array from mergeChannels, 'date<tab>canal'
    bilanHeader(seuil, coefUmbral, fcutLow, fcutHigh, f1clic, f2clic, f1, f2) -> str  (5 lines)
    bilanLine(fileName, n1, n2, n) -> str
    bilanFooter(duration) -> str     ('\\n' + 'Duree totale %f s \\n')
    Files are written in UTF-8 (the header holds 'référence').

Criteria: the TEXT must be identical, byte for byte (same separators, same precision, same
line endings). On a difference, the message shows the first differing line.
"""

import csv
from pathlib import Path

import numpy as np
import pytest

from nbhf.fusion import mergeChannels
from nbhf.output import bilanFooter, bilanHeader, bilanLine, writeChannel, writeMerged
from nbhf.reading import read_info

# same as A*
PARAMS = dict(seuil=0.4, coefUmbral=9, fcutLow=100000, fcutHigh=180000,
              f1clic=120000, f2clic=140000, f1=30000, f2=90000)
T_FUSION = 5 / 10000

HERE = Path(__file__).resolve().parent
WAV_DIR = HERE.parent.parent / "jeu_equivalence" / "wav"
RES_DIR = HERE.parent.parent / "jeu_equivalence" / "references_A_v2"
REF_DIR = HERE.parent / "octave_check" / "outputs"


def _same_text(ours, expected, context):
    if ours == expected:
        return
    a, b = ours.split("\n"), expected.split("\n")
    for k, (la, lb) in enumerate(zip(a, b), 1):
        if la != lb:
            raise AssertionError(f"{context}: line {k} differs:\n  B: {la!r}\n  A: {lb!r}")
    raise AssertionError(f"{context}: {len(a)} lines, A has {len(b)} (same up to the shorter one)")


# --- formats, small cases -------------------------------------------------------

def test_write_channel_small(tmp_path):
    path = tmp_path / "c.txt"
    writeChannel(path, np.array([1.736111111111111e-05, 16.5609296875, 2.0, 100.0]))
    assert path.read_text() == "1.736111111111111e-05\n16.5609296875\n2\n100\n"
    writeChannel(path, np.array([]))
    assert path.read_text() == ""


def test_write_merged_small(tmp_path):
    path = tmp_path / "m.txt"
    writeMerged(path, np.array([[2.338751953125, 2.0], [1.736111111111111e-05, 1.0]]))
    assert path.read_text() == "2.338751953125\t2\n1.736111111111111e-05\t1\n"
    writeMerged(path, np.zeros((0, 2)))
    assert path.read_text() == ""


def test_bilan_small():
    assert bilanLine("x.wav", 318, 298, 377) == "x.wav \t 318 \t 298 \t 377 \n"
    assert bilanLine("y.wav", 0, 0, 0) == "y.wav \t 0 \t 0 \t 0 \n"
    assert bilanFooter(645.122791) == "\nDuree totale 645.122791 s \n"
    header = bilanHeader(**PARAMS)
    assert header.endswith("\n") and header.count("\n") == 5
    assert header.split("\n")[0] == "Seuil: 0.400000, coef_umbral 9, frequence coupure basse 100000, frequence coupure haute 180000,"


# --- every file, against A*'s own files ------------------------------------------

if not (REF_DIR / "detection.csv").exists():
    pytest.skip(
        "missing reference: run `octave --no-gui octave_check/export_detection.m`",
        allow_module_level=True,
    )

ACCEPTED = {}  # file -> {canal: [dates in detection order]}
with open(REF_DIR / "detection.csv", newline="") as f:
    for row in csv.DictReader(f, delimiter=";"):
        if row["accepte"] == "1":
            ACCEPTED.setdefault(row["fichier"], {}).setdefault(int(row["canal"]), []).append(float(row["date"]))

FILES = sorted(p.name for p in WAV_DIR.glob("*.wav"))


def _results(file):
    """dates1, dates2 (None if mono), merged rows: A's inputs to the output step."""
    info = read_info(WAV_DIR / file)
    dates = ACCEPTED.get(file, {})
    dates1 = np.array(dates.get(1, []), dtype=float)
    dates2 = np.array(dates.get(2, []), dtype=float) if info.n_channels > 1 else None
    return dates1, dates2, mergeChannels(dates1, dates2, T_FUSION)


@pytest.mark.parametrize("file", FILES)
def test_result_files(file, tmp_path):
    dates1, dates2, merged = _results(file)
    stem = Path(file).stem

    path = tmp_path / f"Res_{stem}.txt"
    writeMerged(path, merged)
    _same_text(path.read_text(encoding="utf-8"), (RES_DIR / path.name).read_text(encoding="utf-8"), path.name)

    if dates2 is None:
        assert not (RES_DIR / f"Res_{stem}_Canal1.txt").exists()  # A writes none for mono
        return
    for canal, dates in ((1, dates1), (2, dates2)):
        path = tmp_path / f"Res_{stem}_Canal{canal}.txt"
        writeChannel(path, dates)
        _same_text(path.read_text(encoding="utf-8"), (RES_DIR / path.name).read_text(encoding="utf-8"), path.name)


def test_bilan():
    expected = (RES_DIR / "BilanTot.txt").read_text(encoding="utf-8")
    lines = expected.split("\n")
    # A's file order (liste_fichiers_extrait.txt) and total duration, taken from the reference
    order = [l.split(" \t ")[0] for l in lines[5:] if l.endswith(" \n"[:-1]) and l.split(" \t ")[0].endswith(".wav")]
    duration = float([l for l in lines if l.startswith("Duree totale")][0].split()[2])
    assert len(order) == len(FILES)

    text = bilanHeader(**PARAMS)
    for file in order:
        dates1, dates2, merged = _results(file)
        n2 = 0 if dates2 is None else len(dates2)
        text += bilanLine(file, len(dates1), n2, len(merged))
    text += bilanFooter(duration)
    _same_text(text, expected, "BilanTot.txt")
