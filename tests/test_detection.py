"""Checkpoint of step 3: threshold of a chunk, compared with A*.

Verification tooling written by Claude (Anthropic); not part of the port itself.

Reference: octave_check/outputs/filtered.csv (produced by export_filter.m, step 2),
columns std_senalHF and umbral, for each chunk x channel of every file:
    umbral1 = std(senal1HF)*coef_umbral        (A*, coef_umbral = 9)
Octave's std divides by N-1.

Criteria:
    - threshold: NOT exact (std is a sum over millions of samples; numpy and Octave
      do not sum in the same order). |b_value - a_value| <= TOL * a_value.
      The same TOL as step 2 (1e-12): the std of the filtered signal was already
      under it in test_filtering.

Expected interface of nbhf.detection (rename here if you choose other names):
    chunkThreshold(x, coefUmbral) -> float
        x is ONE channel of the filtered chunk (1-D ndarray), as senal1HF in A.
        Returns std(x, N-1 normalisation) * coefUmbral.
"""

import csv
import math
from pathlib import Path

import numpy as np
import pytest

from nbhf.detection import chunkThreshold
from nbhf.filtering import filterChunk, filterCoefficients
from nbhf.reading import chunk_bounds, read_chunk, read_info

CHUNK_DURATION = 29.99  # t_trozo, same as A*
FCUT_LOW = 100000
FCUT_HIGH = 180000
COEF_UMBRAL = 9

TOL = 1e-12

HERE = Path(__file__).resolve().parent
WAV_DIR = HERE.parent / "research" / "jeu_equivalence" / "wav"
REF_DIR = HERE.parent / "research" / "octave_check" / "outputs"

if not (REF_DIR / "filtered.csv").exists():
    pytest.skip(
        "missing reference: run `octave --no-gui research/octave_check/export_filter.m`",
        allow_module_level=True,
    )


FILTERED = {}  # file -> list of rows (one chunk x one channel)
with open(REF_DIR / "filtered.csv", newline="") as f:
    for row in csv.DictReader(f, delimiter=";"):
        FILTERED.setdefault(row["fichier"], []).append(row)

FILES = sorted(FILTERED)


# --- small case, instant feedback (catches ddof=0 and the missing coefficient) --

def test_threshold_small():
    x = np.array([1.0, 2.0, 3.0, 4.0])
    # std with N-1: sqrt(((1.5^2 + 0.5^2) * 2) / 3) = sqrt(5/3)
    expected = math.sqrt(5 / 3) * COEF_UMBRAL
    value = chunkThreshold(x, COEF_UMBRAL)
    assert isinstance(value, float)
    assert math.isclose(value, expected, rel_tol=1e-15), f"{value} != {expected}"


# --- every chunk and every channel of every file, against A* ------------------

@pytest.mark.parametrize("file", FILES)
def test_threshold(file):
    path = WAV_DIR / file
    info = read_info(path)
    b, a = filterCoefficients(info.sample_rate, FCUT_LOW, FCUT_HIGH)

    filtered = {}
    worst = 0.0
    for ref in FILTERED[file]:
        i = int(ref["i"])
        if i not in filtered:  # filter each chunk once, for all its channels
            start, end = chunk_bounds(i, CHUNK_DURATION, info.sample_rate, info.n_samples)
            filtered = {i: filterChunk(b, a, read_chunk(path, start, end))}
        x = filtered[i][:, int(ref["canal"]) - 1]
        context = f"{file}, chunk {i}, channel {ref['canal']}"

        value = chunkThreshold(x, COEF_UMBRAL)
        expected = float(ref["umbral"])
        err = abs(value - expected) / expected
        worst = max(worst, err)
        assert err <= TOL, f"{context}, umbral: relative error {err:.3g} > TOL={TOL:g}"

    print(f"\n{file}: max relative error on umbral {worst:.3g}")
