"""Checkpoint of step 5: fusion of the two channels, compared with A*.

Verification tooling written by Claude (Anthropic); not part of the port itself.

The code of A, once all chunks of a file are done (dates_clicks1 / dates_clicks2 are the
accepted dates of channel 1 / 2, in detection order):
    if (nbCanales > 1)
        dates_clicks = [[dates_clicks1; dates_clicks2], [1...; 2...]];   % columns (date, canal)
        dates_clicks = sortrows(dates_clicks);                           % by date, then canal
        n = 1;
        while (n < (length(dates_clicks) - 1))
            if (abs(dates_clicks(n+1,1) - dates_clicks(n,1)) < t_fusion)
                dates_clicks = [dates_clicks(1:n,:); dates_clicks(n+2:end,:)];   % drop row n+1
            endif
            n = n + 1;
        endwhile
    else
        dates_clicks = sortrows([dates_clicks1, ones]);                  % mono: NO fusion loop
    end
Two quirks of this loop are part of A and must be reproduced:
    - `n < length-1`: the last pair is never compared (and with 2 rows, nothing is compared)
    - after dropping row n+1, n is still incremented, so the new row n+1 is never compared
      with row n (a third click within t_fusion of the first one survives)
`length` of an N x 2 matrix is max(N, 2); this changes nothing here (checked: for N = 0, 1, 2
the loop does not run either way), the number of rows can be used.
The loop does not look at the channel: two close clicks of the SAME channel are merged too.

References:
    - input: the accepted candidates of octave_check/outputs/detection.csv (step 4), i.e.
      A's own dates_clicks1 / dates_clicks2
    - expected: research/jeu_equivalence/references_A_v2/Res_<file>.txt, A*'s own output
      (dlmwrite, tab separated, columns date and canal, 16 significant digits)

Expected interface of nbhf.fusion (rename here if you choose other names):
    mergeChannels(dates1, dates2, tFusion) -> float64 ndarray of shape (N, 2), columns (date, canal)
        dates1, dates2: 1-D arrays (or lists) of dates in seconds, any order
        dates2 is None for a mono file (A's else branch); an empty array is a stereo file
        with no click on channel 2 (the fusion loop still runs)

Criteria:
    - number of rows and canal column: EXACT
    - dates: |b - a| <= TOL_DATE seconds (the reference file has 16 digits, A's dates are
      exact doubles in detection.csv, so the only error is this rounding, ~3e-14 s)
"""

import csv
from pathlib import Path

import numpy as np
import pytest

from nbhf.fusion import mergeChannels
from nbhf.reading import read_info

T_FUSION = 5 / 10000  # same as A*

TOL_DATE = 1e-11  # seconds

HERE = Path(__file__).resolve().parent
WAV_DIR = HERE.parent / "research" / "jeu_equivalence" / "wav"
RES_DIR = HERE.parent / "research" / "jeu_equivalence" / "references_A_v2"
REF_DIR = HERE.parent / "research" / "octave_check" / "outputs"


def _merge(dates1, dates2, t=T_FUSION):
    out = mergeChannels(np.array(dates1, dtype=float), None if dates2 is None else np.array(dates2, dtype=float), t)
    assert isinstance(out, np.ndarray) and out.dtype == np.float64, type(out)
    assert out.ndim == 2 and out.shape[1] == 2, out.shape
    return out.tolist()


# --- synthetic cases: the semantics of A's loop ------------------------------

def test_sorted_by_date_then_channel():
    assert _merge([2.0], [2.0, 1.0]) == [[1.0, 2], [2.0, 1], [2.0, 2]]


def test_two_close_clicks_merged():
    # 4 rows: n=1 compares rows 1-2 (merged), n=2 compares rows 2-3 (far apart)
    assert _merge([1.0, 5.0], [1.0001, 9.0]) == [[1.0, 1], [5.0, 1], [9.0, 2]]


def test_strict_comparison():
    # exactly t_fusion apart: not merged (abs(...) < t_fusion is strict).
    # Dates 0 and T_FUSION so that the difference is exactly T_FUSION in floating point.
    assert _merge([0.0, 5.0], [T_FUSION, 9.0]) == [[0.0, 1], [T_FUSION, 2], [5.0, 1], [9.0, 2]]


def test_last_pair_never_compared():
    # 3 rows: only rows 1-2 are compared; rows 2-3 are close but both survive
    assert _merge([1.0, 2.0], [2.0001]) == [[1.0, 1], [2.0, 1], [2.0001, 2]]
    # 2 rows: nothing is compared at all
    assert _merge([1.0], [1.0001]) == [[1.0, 1], [1.0001, 2]]


def test_skip_after_merge():
    # rows 1.0, 1.0001, 1.0002, 5.0: n=1 drops 1.0001, then n=2 compares 1.0002 with 5.0,
    # so 1.0002 survives although it is within t_fusion of 1.0
    assert _merge([1.0, 1.0002], [1.0001, 5.0]) == [[1.0, 1], [1.0002, 1], [5.0, 2]]


def test_same_channel_merged():
    # the loop ignores the channel: two close clicks of channel 1 are merged too
    assert _merge([1.0, 1.0001, 5.0], [9.0]) == [[1.0, 1], [5.0, 1], [9.0, 2]]


def test_stereo_empty_channel_2():
    assert _merge([1.0, 1.0001, 5.0], []) == [[1.0, 1], [5.0, 1]]
    assert _merge([], []) == []


def test_mono_no_fusion():
    # A's else branch: sorted, canal 1, and the loop does NOT run
    assert _merge([5.0, 1.0001, 1.0], None) == [[1.0, 1], [1.0001, 1], [5.0, 1]]
    assert _merge([], None) == []


# --- every file, against A*'s own Res_<file>.txt -----------------------------

if not (REF_DIR / "detection.csv").exists():
    pytest.skip(
        "missing reference: run `octave --no-gui research/octave_check/export_detection.m`",
        allow_module_level=True,
    )

ACCEPTED = {}  # file -> {canal: [dates]}
with open(REF_DIR / "detection.csv", newline="") as f:
    for row in csv.DictReader(f, delimiter=";"):
        if row["accepte"] == "1":
            ACCEPTED.setdefault(row["fichier"], {}).setdefault(int(row["canal"]), []).append(float(row["date"]))

FILES = sorted(p.name for p in WAV_DIR.glob("*.wav"))


@pytest.mark.parametrize("file", FILES)
def test_against_A(file):
    info = read_info(WAV_DIR / file)
    dates = ACCEPTED.get(file, {})
    dates1 = np.array(dates.get(1, []), dtype=float)
    dates2 = np.array(dates.get(2, []), dtype=float) if info.n_channels > 1 else None

    expected = np.loadtxt(RES_DIR / f"Res_{Path(file).stem}.txt", delimiter="\t", ndmin=2)
    out = mergeChannels(dates1, dates2, T_FUSION)

    assert out.shape == expected.shape, (
        f"{file}: {out.shape[0]} rows, A has {expected.shape[0]} "
        f"(channel 1: {len(dates1)}, channel 2: {0 if dates2 is None else len(dates2)})")
    assert np.array_equal(out[:, 1], expected[:, 1]), f"{file}: canal column differs"
    err = np.abs(out[:, 0] - expected[:, 0]).max() if len(out) else 0.0
    assert err <= TOL_DATE, f"{file}: max date error {err:.3g} s > {TOL_DATE:g}"
    print(f"\n{file}: {len(dates1)} + {0 if dates2 is None else len(dates2)} -> {len(out)} rows, identical to A")
