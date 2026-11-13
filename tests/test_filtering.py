"""Checkpoint of step 2: filtering of a chunk, compared with A*.

Verification tooling written by Claude (Anthropic); not part of the port itself.

Reference: octave_check/outputs/, produced by
    octave --no-gui research/octave_check/export_filter.m
    - coefs_<fm>.txt            coefficients recomputed as in A* (same format as A* modif 4)
    - filtered.csv              fingerprints of senalHF for each chunk x channel
    - filtered_<fm>_head.bin    first / last 100 000 samples of senalHF (chunk 1, channel 1,
      filtered_<fm>_tail.bin    file named in filtered_<fm>_source.txt), float64 little-endian
B computes its own coefficients with scipy.signal.butter (it does not read A*'s files).

Criteria:
    - coefficients: NOT exact (scipy and Octave round differently, ~1e-15 measured 10/11):
      |b_coef - a_coef| <= TOL_COEFS * max|coef|
    - filtered signal: NOT exact (floating point, filter / lfilter may order the operations
      differently). Each value is compared relative to a scale (see _check):
      |b_value - a_value| <= TOL * scale.  TOL is to be fixed once the real errors are seen.
    - ix_max (position of the maximum): exact equality, unless two samples are almost equal

Expected interface of nbhf.filtering (rename here if you choose other names):
    filterCoefficients(sampleRate, fcutLow, fcutHigh) -> (b, a), two float64 1-D ndarrays,
        butter(5, ...) with the A* modif 3 rule: high-pass at fcutLow if fcutHigh >= fm/2,
        band-pass [fcutLow, fcutHigh] otherwise
    filterChunk(b, a, chunk)     -> float64 ndarray, same shape (n, n_channels) as chunk,
        each column filtered separately with a zero initial state, as
        senalHF = filter(butterBHF1, butterBHF2, senal) in A
"""

import csv
from pathlib import Path

import numpy as np
import pytest

from nbhf.filtering import filterChunk, filterCoefficients
from nbhf.reading import chunk_bounds, read_chunk, read_info

CHUNK_DURATION = 29.99  # t_trozo, same as A*
FCUT_LOW = 100000
FCUT_HIGH = 180000

# Relative tolerance on the filtered signal. Start strict, loosen if needed,
# and note the value retained (and why) in the work plan.
TOL = 1e-12
# Relative tolerance on the coefficients (scipy vs Octave): ~1e-15 measured, x10 margin.
TOL_COEFS = 1e-14

HERE = Path(__file__).resolve().parent
WAV_DIR = HERE.parent / "research" / "jeu_equivalence" / "wav"
REF_DIR = HERE.parent / "research" / "octave_check" / "outputs"

if not (REF_DIR / "filtered.csv").exists():
    pytest.skip(
        "missing reference: run `octave --no-gui research/octave_check/export_filter.m`",
        allow_module_level=True,
    )


def _read_csv(name):
    with open(REF_DIR / name, newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


FILTERED = {}  # file -> list of rows (one chunk x one channel)
for row in _read_csv("filtered.csv"):
    FILTERED.setdefault(row["fichier"], []).append(row)

FILES = sorted(FILTERED)
SAMPLE_RATES = sorted(int(p.stem.split("_")[1]) for p in REF_DIR.glob("coefs_*.txt"))


def _check(name, value, ref, scale, context):
    """|value - ref| <= TOL * scale, with the actual relative error in the message."""
    err = abs(value - ref) / scale
    assert err <= TOL, f"{context}, {name}: relative error {err:.3g} > TOL={TOL:g}"


# --- coefficients -------------------------------------------------------------

@pytest.mark.parametrize("sample_rate", SAMPLE_RATES)
def test_coefficients(sample_rate):
    b, a = filterCoefficients(sample_rate, FCUT_LOW, FCUT_HIGH)
    expected = {"b": [], "a": []}
    for line in (REF_DIR / f"coefs_{sample_rate}.txt").read_text().splitlines():
        key, value = line.split()
        expected[key].append(float(value))

    assert isinstance(b, np.ndarray) and isinstance(a, np.ndarray)
    assert b.dtype == np.float64 and a.dtype == np.float64
    assert len(b) == len(expected["b"]) and len(a) == len(expected["a"])  # right filter type
    assert a[0] == 1.0

    for name, ours, ref in (("b", b, np.array(expected["b"])), ("a", a, np.array(expected["a"]))):
        err = np.abs(ours - ref).max() / np.abs(ref).max()
        print(f"\n{sample_rate} Hz {name}: max relative error {err:.3g}")
        assert err <= TOL_COEFS, f"{sample_rate} Hz, {name}: relative error {err:.3g} > TOL_COEFS={TOL_COEFS:g}"


# --- sample by sample, start and end of one chunk -----------------------------

@pytest.mark.parametrize("sample_rate", SAMPLE_RATES)
def test_head_tail(sample_rate):
    source = (REF_DIR / f"filtered_{sample_rate}_source.txt").read_text().split(";")
    file = source[0]
    n_dump = int(source[-1].split("=")[1])
    path = WAV_DIR / file

    info = read_info(path)
    start, end = chunk_bounds(1, CHUNK_DURATION, info.sample_rate, info.n_samples)
    b, a = filterCoefficients(sample_rate, FCUT_LOW, FCUT_HIGH)
    x = filterChunk(b, a, read_chunk(path, start, end))[:, 0]

    head = np.fromfile(REF_DIR / f"filtered_{sample_rate}_head.bin", dtype="<f8")
    tail = np.fromfile(REF_DIR / f"filtered_{sample_rate}_tail.bin", dtype="<f8")
    assert len(head) == len(tail) == n_dump

    for name, ours, ref in (("head", x[:n_dump], head), ("tail", x[-n_dump:], tail)):
        scale = np.abs(ref).max()
        err = np.abs(ours - ref).max() / scale
        n_exact = int((ours == ref).sum())
        print(f"\n{file} {name}: max relative error {err:.3g}, "
              f"{n_exact}/{n_dump} samples bit-identical")
        assert err <= TOL, f"{file} {name}: relative error {err:.3g} > TOL={TOL:g}"


# --- fingerprints, every chunk and every channel ------------------------------

@pytest.mark.parametrize("file", FILES)
def test_fingerprints(file):
    path = WAV_DIR / file
    info = read_info(path)
    b, a = filterCoefficients(info.sample_rate, FCUT_LOW, FCUT_HIGH)

    filtered = {}
    for ref in FILTERED[file]:
        i = int(ref["i"])
        if i not in filtered:  # filter each chunk once, for all its channels
            start, end = chunk_bounds(i, CHUNK_DURATION, info.sample_rate, info.n_samples)
            chunk = read_chunk(path, start, end)
            filtered = {i: filterChunk(b, a, chunk)}
        senalHF = filtered[i]
        context = f"chunk {i}, channel {ref['canal']}"

        assert senalHF.dtype == np.float64, context
        x = senalHF[:, int(ref["canal"]) - 1]
        n = int(ref["n"])
        assert len(x) == n, context

        # scales: a sum is compared to the sum of |x|, a sample to max |x|
        peak = max(abs(float(ref["minimum"])), abs(float(ref["maximum"])))
        sum_abs = float(ref["somme_abs"])

        _check("somme", x.sum(), float(ref["somme"]), sum_abs, context)
        _check("somme_abs", np.abs(x).sum(), sum_abs, sum_abs, context)
        _check("somme_carres", (x**2).sum(), float(ref["somme_carres"]), float(ref["somme_carres"]), context)
        _check("std_senalHF", x.std(ddof=1), float(ref["std_senalHF"]), float(ref["std_senalHF"]), context)
        _check("minimum", x.min(), float(ref["minimum"]), peak, context)
        _check("maximum", x.max(), float(ref["maximum"]), peak, context)

        # Octave's ix starts at 1
        assert int(np.argmax(x)) + 1 == int(ref["ix_max"]), context

        ends = [x[0], x[1], x[2], x[n - 3], x[n - 2], x[n - 1]]
        for col, value in zip(("x1", "x2", "x3", "xn_2", "xn_1", "xn"), ends):
            _check(col, value, float(ref[col]), peak, context)
