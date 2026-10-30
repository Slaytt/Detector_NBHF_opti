"""Checkpoint of step 1: reading a chunk, compared with A*.

Verification tooling written by Claude (Anthropic); not part of the port itself.

Reference: octave_check/outputs/{infos,bounds}.csv, produced by
    octave --no-gui octave_check/export_bounds.m
The CSV columns keep A's variable names (fm, tamano_total, nbCanales, inicio, fin...).

Criterion: EXACT equality (max difference = 0) of the bounds and of the samples.

Expected interface of nbhf.reading:
    read_info(path)                                   -> object with .sample_rate, .n_samples, .n_channels
    n_chunks(n_samples, sample_rate, chunk_duration)  -> N
    chunk_bounds(i, chunk_duration, sample_rate, n_samples) -> (start, end)
        i starts at 1 as in A; start and end are Octave bounds
        (start at 1, end included), so directly comparable with audioread.
    read_chunk(path, start, end)                      -> float64 ndarray of shape (n, n_channels),
        like `extrait` in A
"""

import csv
from pathlib import Path

import numpy as np
import pytest

from nbhf.reading import chunk_bounds, n_chunks, read_chunk, read_info

CHUNK_DURATION = 29.99  # t_trozo, same as A*

HERE = Path(__file__).resolve().parent
WAV_DIR = HERE.parent.parent / "jeu_equivalence" / "wav"
REF_DIR = HERE.parent / "octave_check" / "outputs"

if not (REF_DIR / "bounds.csv").exists():
    pytest.skip(
        "missing reference: run `octave --no-gui octave_check/export_bounds.m`",
        allow_module_level=True,
    )


def _read_csv(name):
    with open(REF_DIR / name, newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


INFOS = {row["fichier"]: row for row in _read_csv("infos.csv")}

BOUNDS = {}  # file -> list of rows (one chunk x one channel)
for row in _read_csv("bounds.csv"):
    BOUNDS.setdefault(row["fichier"], []).append(row)

FILES = sorted(INFOS)


@pytest.mark.parametrize("file", FILES)
def test_info(file):
    ref = INFOS[file]
    info = read_info(WAV_DIR / file)
    assert info.sample_rate == int(ref["fm"])
    assert info.n_samples == int(ref["tamano_total"])
    assert info.n_channels == int(ref["nbCanales"])
    assert n_chunks(info.n_samples, info.sample_rate, CHUNK_DURATION) == int(ref["N"])


@pytest.mark.parametrize("file", FILES)
def test_bounds(file):
    ref = INFOS[file]
    sample_rate, n_samples = int(ref["fm"]), int(ref["tamano_total"])
    expected = {(int(r["i"]), int(r["inicio"]), int(r["fin"])) for r in BOUNDS[file]}
    obtained = {(i, *chunk_bounds(i, CHUNK_DURATION, sample_rate, n_samples)) for i, _, _ in expected}
    assert obtained == expected


@pytest.mark.parametrize("file", FILES)
def test_samples(file):
    path = WAV_DIR / file
    chunks = {}
    for ref in BOUNDS[file]:
        start, end = int(ref["inicio"]), int(ref["fin"])
        if (start, end) not in chunks:
            chunks = {(start, end): read_chunk(path, start, end)}
        chunk = chunks[(start, end)]
        x = chunk[:, int(ref["canal"]) - 1]
        n = int(ref["n"])
        context = f"chunk {ref['i']}, channel {ref['canal']}"

        assert chunk.dtype == np.float64, context
        assert len(x) == n, context
        assert x.sum() == float(ref["somme"]), context
        assert np.abs(x).sum() == float(ref["somme_abs"]), context
        assert x.min() == float(ref["minimum"]), context
        assert x.max() == float(ref["maximum"]), context
        ends = [x[0], x[1], x[2], x[n - 3], x[n - 2], x[n - 1]]
        ends_ref = [float(ref[c]) for c in ("x1", "x2", "x3", "xn_2", "xn_1", "xn")]
        assert ends == ends_ref, context
