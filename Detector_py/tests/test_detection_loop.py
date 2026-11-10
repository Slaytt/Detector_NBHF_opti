"""Checkpoint of step 4: detection loop on one channel, compared with A*.

Verification tooling written by Claude (Anthropic); not part of the port itself.

Reference: octave_check/outputs/, produced by
    octave --no-gui octave_check/export_detection.m      (~10 min)
    - detection.csv         one line per candidate, in loop order (accepted or rejected):
                            fichier;i;canal;k;ix;x;umbral;win_start;win_end;n_win;
                            energieClic;energie_bande_passante;accepte;date
                            ix, win_start, win_end: Octave indices (start at 1, end included)
    - detection_chunks.csv  one line per chunk x channel: fichier;i;canal;umbral;n_candidats;n_acceptes

The loop of A, for one channel (senal = raw signal, senalHF = filtered, umbral = threshold):
    while max(senalHF) > umbral
        [x, ix] = max(senalHF)
        spectre = abs(fft(senal(max(ix-floor(fm/2000-1),1) : min(ix+floor(fm/2000),length(senal)))))
        energieClic = mean(spectre(f1clic/1000 : f2clic/1000))
        energie_bande_passante = mean(spectre(f1/1000 : f2/1000))
        if energieClic > seuil*energie_bande_passante: keep date (i-1)*t_trozo + ix/fm
        senalHF(max(1,ix-floor(t_minimo*fm)) : min(length(senal),ix+floor(t_minimo*fm))) = 0

Expected interface of nbhf.detection (rename here if you choose other names).
All indices are Python indices (start at 0, stop excluded); chunkIndex starts at 1 like
chunk_bounds. The test converts to Octave's convention where needed.
    windowBounds(ix, sampleRate, n) -> (start, stop)
        bounds of the FFT window around the sample ix, as a Python slice
    clickEnergies(window, f1clic, f2clic, f1, f2) -> (energieClic, energieBande)
        window: 1-D slice of the RAW signal; spectrum bins are indexed as in A
    clickDate(chunkIndex, ix, sampleRate, chunkDuration) -> float
        (i-1)*t_trozo + ix_octave/fm
    detectChannel(senal, senalHF, umbral, sampleRate, *, seuil, tMinimo, f1clic, f2clic, f1, f2)
        -> list of candidates, in loop order, each with attributes
           ix, x, energieClic, energieBande, accepted (a NamedTuple or dataclass)
        senal and senalHF are 1-D (one channel). senalHF must not be modified for the caller
        (work on a copy).

Criteria:
    - ix, window bounds, number of candidates, accepted: EXACT
    - x, energies, dates: relative tolerance TOL (floating point; fft / mean / filter)
    - when `accepted` differs, the message gives the margin energieClic - seuil*energieBande
      of A, to tell a real error from a candidate sitting on the threshold
"""

import csv
import math
from pathlib import Path

import numpy as np
import pytest

from nbhf.detection import chunkThreshold, clickDate, clickEnergies, detectChannel, windowBounds
from nbhf.filtering import filterChunk, filterCoefficients
from nbhf.reading import chunk_bounds, read_chunk, read_info

# same as A*
CHUNK_DURATION = 29.99
FCUT_LOW = 100000
FCUT_HIGH = 180000
COEF_UMBRAL = 9
PARAMS = dict(seuil=0.4, tMinimo=1 / 1000, f1clic=120000, f2clic=140000, f1=30000, f2=90000)

TOL = 1e-12

HERE = Path(__file__).resolve().parent
WAV_DIR = HERE.parent.parent / "jeu_equivalence" / "wav"
REF_DIR = HERE.parent / "octave_check" / "outputs"

if not (REF_DIR / "detection.csv").exists():
    pytest.skip(
        "missing reference: run `octave --no-gui octave_check/export_detection.m`",
        allow_module_level=True,
    )


def _read_csv(name):
    with open(REF_DIR / name, newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


CANDIDATES = {}  # file -> {(i, canal): [rows in loop order]}
for row in _read_csv("detection.csv"):
    key = (int(row["i"]), int(row["canal"]))
    CANDIDATES.setdefault(row["fichier"], {}).setdefault(key, []).append(row)

CHUNKS = {}  # file -> {(i, canal): row}
for row in _read_csv("detection_chunks.csv"):
    CHUNKS.setdefault(row["fichier"], {})[(int(row["i"]), int(row["canal"]))] = row

FILES = sorted(CHUNKS)


def _rel(value, ref):
    return abs(value - ref) / abs(ref) if ref != 0 else abs(value - ref)


def _check(name, value, ref, context):
    err = _rel(value, ref)
    assert err <= TOL, f"{context}, {name}: {value!r} vs A {ref!r}, relative error {err:.3g} > TOL={TOL:g}"


def _filtered_chunk(path, info, i):
    """Raw chunk and filtered chunk, (n, n_channels)."""
    b, a = filterCoefficients(info.sample_rate, FCUT_LOW, FCUT_HIGH)
    start, end = chunk_bounds(i, CHUNK_DURATION, info.sample_rate, info.n_samples)
    chunk = read_chunk(path, start, end)
    return chunk, filterChunk(b, a, chunk)


# --- window bounds: synthetic edge cases, then every candidate of A -----------

def _octave_window(ix_octave, fm, n):
    """A's formula, Octave convention (1-based, end included)."""
    return (max(ix_octave - math.floor(fm / 2000 - 1), 1), min(ix_octave + math.floor(fm / 2000), n))


@pytest.mark.parametrize("sample_rate", [288000, 512000])
@pytest.mark.parametrize("ix", [0, 1, 100, 1000, 8637120 - 300, 8637120 - 1])
def test_window_bounds_edges(sample_rate, ix):
    n = 8637120
    start, stop = windowBounds(ix, sample_rate, n)
    assert isinstance(start, int) and isinstance(stop, int)
    assert (start + 1, stop) == _octave_window(ix + 1, sample_rate, n), f"ix={ix}"
    assert 0 <= start <= ix < stop <= n


@pytest.mark.parametrize("file", FILES)
def test_window_bounds(file):
    info = read_info(WAV_DIR / file)
    for (i, canal), rows in CANDIDATES.get(file, {}).items():
        start_c, end_c = chunk_bounds(i, CHUNK_DURATION, info.sample_rate, info.n_samples)
        n = end_c - start_c + 1
        for ref in rows:
            start, stop = windowBounds(int(ref["ix"]) - 1, info.sample_rate, n)
            context = f"{file}, chunk {i}, channel {canal}, candidate {ref['k']}"
            assert (start + 1, stop) == (int(ref["win_start"]), int(ref["win_end"])), context
            assert stop - start == int(ref["n_win"]), context


# --- energies of the FFT window, on A's own windows --------------------------

@pytest.mark.parametrize("file", FILES)
def test_click_energies(file):
    path = WAV_DIR / file
    info = read_info(path)
    for (i, canal), rows in CANDIDATES.get(file, {}).items():
        start_c, end_c = chunk_bounds(i, CHUNK_DURATION, info.sample_rate, info.n_samples)
        senal = read_chunk(path, start_c, end_c)[:, canal - 1]
        for ref in rows:
            context = f"{file}, chunk {i}, channel {canal}, candidate {ref['k']}"
            window = senal[int(ref["win_start"]) - 1 : int(ref["win_end"])]
            e_clic, e_bande = clickEnergies(window, PARAMS["f1clic"], PARAMS["f2clic"], PARAMS["f1"], PARAMS["f2"])
            _check("energieClic", e_clic, float(ref["energieClic"]), context)
            _check("energie_bande_passante", e_bande, float(ref["energie_bande_passante"]), context)


# --- date of a click ----------------------------------------------------------

def test_click_date_small():
    # chunk 1, first sample (ix_octave = 1) at 512 kHz: 0 + 1/512000
    assert clickDate(1, 0, 512000, CHUNK_DURATION) == 1 / 512000
    # chunk 3 at 288 kHz, ix_octave = 1000
    assert math.isclose(clickDate(3, 999, 288000, CHUNK_DURATION), 2 * 29.99 + 1000 / 288000, rel_tol=1e-15)


# --- the whole loop, every chunk and channel of every file --------------------

@pytest.mark.parametrize("file", FILES)
def test_detect_channel(file):
    path = WAV_DIR / file
    info = read_info(path)
    fm = info.sample_rate
    n_cand = n_acc = 0

    for (i, canal), chunk_ref in sorted(CHUNKS[file].items()):
        if canal == 1:
            chunk, senalHF_all = _filtered_chunk(path, info, i)
        context = f"{file}, chunk {i}, channel {canal}"
        senal = chunk[:, canal - 1]
        senalHF = senalHF_all[:, canal - 1].copy()
        umbral = chunkThreshold(senalHF, COEF_UMBRAL)
        before = senalHF.copy()

        candidates = detectChannel(senal, senalHF, umbral, fm, **PARAMS)
        assert np.array_equal(senalHF, before), f"{context}: detectChannel modified senalHF in place"

        refs = CANDIDATES.get(file, {}).get((i, canal), [])
        assert len(refs) == int(chunk_ref["n_candidats"])  # reference self-consistent
        assert len(candidates) == len(refs), (
            f"{context}: {len(candidates)} candidates, A has {len(refs)}; "
            f"first ix: {[c.ix + 1 for c in candidates[:5]]} vs {[int(r['ix']) for r in refs[:5]]}")

        for cand, ref in zip(candidates, refs):
            ctx = f"{context}, candidate {ref['k']}"
            assert cand.ix + 1 == int(ref["ix"]), f"{ctx}: ix {cand.ix + 1} vs A {ref['ix']}"
            _check("x", cand.x, float(ref["x"]), ctx)
            _check("energieClic", cand.energieClic, float(ref["energieClic"]), ctx)
            _check("energie_bande_passante", cand.energieBande, float(ref["energie_bande_passante"]), ctx)
            margin = float(ref["energieClic"]) - PARAMS["seuil"] * float(ref["energie_bande_passante"])
            assert bool(cand.accepted) == bool(int(ref["accepte"])), (
                f"{ctx}: accepted={cand.accepted}, A says {ref['accepte']} "
                f"(A's margin energieClic - seuil*energie_bande = {margin:.3g})")
            if cand.accepted:
                _check("date", clickDate(i, cand.ix, fm, CHUNK_DURATION), float(ref["date"]), ctx)

        n_cand += len(candidates)
        n_acc += sum(bool(c.accepted) for c in candidates)

    print(f"\n{file}: {n_cand} candidates, {n_acc} accepted, identical to A")
