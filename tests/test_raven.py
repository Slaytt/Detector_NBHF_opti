"""Raven selection table, one click per line, built from the candidate table.

This file is not produced by A, so there is no Octave reference. Criteria:
  - one line per candidate kept by the mask, and nothing else;
  - the box is centred on the `date` of A (never recomputed from `sample`);
  - the free columns are the values of the table, bit for bit;
  - the file is tab separated, with the header Raven expects, and reads back exactly.

Expected interface of nbhf.raven:
    RAVEN_HEADER -> the ten column names, in order:
        Selection, View, Channel, Begin Time (s), End Time (s), Low Freq (Hz),
        High Freq (Hz), Amplitude, Ratio, Peak Freq (Hz)
    clickSelections(table, mask, sampleRate, lowFreq, highFreq, halfWidth=0.0005)
        -> list of rows, one per True of mask, sorted by date (stable), each row =
           (selection from 1, "Spectrogram 1", channel, max(0, date - halfWidth),
            date + halfWidth, lowFreq, min(highFreq, sampleRate / 2),
            amplitude, levelClick / levelRef, peakFreq)
    writeSelections(path, rows, header=RAVEN_HEADER) -> header line then one line per row,
        tab separated
    TRAIN_HEADER -> the seven Raven columns, then Clicks and Peak Freq (Hz)
    trainSelections(table, mask, sampleRate, lowFreq, highFreq, maxGap=0.5, halfWidth=0.0005)
        -> one row per train: channel by channel, a new train starts when two consecutive
           kept clicks are more than maxGap apart; row = (selection, "Spectrogram 1", channel,
           first date - halfWidth, last date + halfWidth, lowFreq, clipped highFreq,
           number of clicks, median peakFreq); rows sorted by begin time

    launch test :
        .venv/bin/python -m pytest tests/test_raven.py
"""

from pathlib import Path

import numpy as np
import pytest

from nbhf.decision import thresholdRule
from nbhf.detection import CANDIDATE_DTYPE
from nbhf.detector import Detector
from nbhf.parameters import Parameters
from nbhf.raven import RAVEN_HEADER, TRAIN_HEADER, clickSelections, trainSelections, writeSelections
from nbhf.reading import read_info

HERE = Path(__file__).resolve().parent
WAV_DIR = HERE.parent / "research" / "jeu_equivalence" / "wav"

EXPECTED_HEADER = [
    "Selection", "View", "Channel", "Begin Time (s)", "End Time (s)",
    "Low Freq (Hz)", "High Freq (Hz)", "Amplitude", "Ratio", "Peak Freq (Hz)",
]

# column positions in a row
SEL, VIEW, CHAN, BEGIN, END, LOW, HIGH, AMP, RATIO, PEAK = range(10)


def _table(dates, channels=None, accepted=None):
    """A small hand-made candidate table; levels chosen so that every ratio is exact."""
    n = len(dates)
    t = np.zeros(n, dtype=CANDIDATE_DTYPE)
    t["date"] = dates
    t["channel"] = 1 if channels is None else channels
    t["amplitude"] = 0.01 * (np.arange(n) + 1)
    t["levelClick"] = 3.0 * (np.arange(n) + 1)
    t["levelRef"] = 2.0
    t["peakFreq"] = 120000.0 + 1000.0 * np.arange(n)
    t["accepted"] = True if accepted is None else accepted
    return t


def _read_back(path):
    with open(path, encoding="utf-8", newline="") as f:
        lines = f.read().split("\n")
    assert lines[-1] == "", "the file must end with a newline"
    return [line.split("\t") for line in lines[:-1]]


# --- clickSelections -----------------------------------------------------------------

def test_header():
    assert list(RAVEN_HEADER) == EXPECTED_HEADER


def test_one_row_per_kept_candidate():
    table = _table([1.0, 2.0, 3.0, 4.0], accepted=[True, False, True, False])
    rows = clickSelections(table, table["accepted"], 288000, 120000, 140000)
    assert len(rows) == 2
    assert [r[BEGIN] + 0.0005 for r in rows] == pytest.approx([1.0, 3.0])


def test_row_content():
    table = _table([1.5, 2.5])
    rows = clickSelections(table, table["accepted"], 288000, 120000, 140000, halfWidth=0.001)
    r = rows[1]
    assert len(r) == len(EXPECTED_HEADER)
    assert r[SEL] == 2
    assert r[VIEW] == "Spectrogram 1"
    assert r[CHAN] == 1
    assert r[BEGIN] == 2.5 - 0.001
    assert r[END] == 2.5 + 0.001
    assert r[LOW] == 120000
    assert r[HIGH] == 140000
    assert r[AMP] == table["amplitude"][1]
    assert r[RATIO] == table["levelClick"][1] / table["levelRef"][1]
    assert r[PEAK] == table["peakFreq"][1]


def test_default_half_width_is_half_a_millisecond():
    table = _table([10.0])
    (r,) = clickSelections(table, table["accepted"], 288000, 120000, 140000)
    assert r[BEGIN] == 10.0 - 0.0005
    assert r[END] == 10.0 + 0.0005


def test_sorted_by_date_and_numbered_from_one():
    # the table is in detection order (decreasing amplitude inside a chunk), not in time order
    table = _table([3.0, 1.0, 2.0])
    rows = clickSelections(table, table["accepted"], 288000, 120000, 140000)
    assert [r[SEL] for r in rows] == [1, 2, 3]
    assert [r[PEAK] for r in rows] == [121000.0, 122000.0, 120000.0]
    begins = [r[BEGIN] for r in rows]
    assert begins == sorted(begins)


def test_same_date_on_two_channels_keeps_table_order():
    table = _table([5.0, 5.0], channels=[1, 2])
    rows = clickSelections(table, table["accepted"], 512000, 120000, 140000)
    assert [r[CHAN] for r in rows] == [1, 2]


def test_high_frequency_clipped_at_nyquist():
    table = _table([1.0])
    (r,) = clickSelections(table, table["accepted"], 288000, 120000, 180000)
    assert r[HIGH] == 144000
    (r,) = clickSelections(table, table["accepted"], 512000, 120000, 180000)
    assert r[HIGH] == 180000


def test_box_never_starts_before_zero():
    # seen on 6209.260514035958.wav: first accepted click dated 1.7e-05 s
    table = _table([1.736111111111111e-05])
    (r,) = clickSelections(table, table["accepted"], 288000, 120000, 140000)
    assert r[BEGIN] == 0.0
    assert r[END] == 1.736111111111111e-05 + 0.0005


def test_mask_is_any_decision_rule():
    # a stricter seuil keeps fewer candidates, without touching the table
    table = _table([1.0, 2.0, 3.0])          # ratios 1.5, 3.0, 4.5
    before = table.copy()
    rows = clickSelections(table, thresholdRule(table, 2.0), 288000, 120000, 140000)
    assert [r[RATIO] for r in rows] == [3.0, 4.5]
    assert np.array_equal(table, before)


def test_nothing_kept():
    table = _table([1.0, 2.0], accepted=[False, False])
    assert clickSelections(table, table["accepted"], 288000, 120000, 140000) == []
    empty = np.zeros(0, dtype=CANDIDATE_DTYPE)
    assert clickSelections(empty, empty["accepted"], 288000, 120000, 140000) == []


def test_plain_python_values():
    # numpy scalars would be written as "np.float64(…)" by some writers
    table = _table([1.0])
    (r,) = clickSelections(table, table["accepted"], 288000, 120000, 140000)
    for k in (BEGIN, END, AMP, RATIO, PEAK):
        assert type(r[k]) is float, f"column {EXPECTED_HEADER[k]}: {type(r[k])}"
    for k in (SEL, CHAN):
        assert type(r[k]) is int, f"column {EXPECTED_HEADER[k]}: {type(r[k])}"


# --- writeSelections -----------------------------------------------------------------

def test_file_round_trip(tmp_path):
    table = _table([3.0, 1.0, 2.0], channels=[1, 2, 1])
    table["date"] += 1 / 3                    # dates that need all their digits
    rows = clickSelections(table, table["accepted"], 512000, 120000, 140000)
    out = tmp_path / "clics.selections.txt"

    writeSelections(out, rows)

    lines = _read_back(out)
    assert lines[0] == EXPECTED_HEADER
    assert len(lines) == 1 + len(rows)
    for row, line in zip(rows, lines[1:]):
        assert len(line) == len(EXPECTED_HEADER)
        assert int(line[SEL]) == row[SEL]
        assert line[VIEW] == "Spectrogram 1"
        assert int(line[CHAN]) == row[CHAN]
        for k in (BEGIN, END, LOW, HIGH, AMP, RATIO, PEAK):
            assert float(line[k]) == row[k], f"column {EXPECTED_HEADER[k]} differs after reading back"


def test_empty_file_has_only_the_header(tmp_path):
    out = tmp_path / "vide.selections.txt"
    writeSelections(out, [])
    assert _read_back(out) == [EXPECTED_HEADER]


def test_no_carriage_return(tmp_path):
    # Raven tables written by the researchers use \n; without newline="" Windows writes \r\r\n
    table = _table([1.0, 2.0])
    out = tmp_path / "clics.selections.txt"
    writeSelections(out, clickSelections(table, table["accepted"], 288000, 120000, 140000))
    raw = out.read_bytes()
    assert b"\r" not in raw
    assert raw.count(b"\n") == 3


# --- trainSelections -----------------------------------------------------------------

T_SEL, T_VIEW, T_CHAN, T_BEGIN, T_END, T_LOW, T_HIGH, T_CLICKS, T_PEAK = range(9)


def test_train_header():
    assert list(TRAIN_HEADER) == EXPECTED_HEADER[:7] + ["Clicks", "Peak Freq (Hz)"]


def test_trains_split_on_gaps_larger_than_max_gap():
    # gaps: 0.2, 0.5 (not larger than maxGap: same train), 0.6 (new train), then a lone click
    table = _table([1.0, 1.2, 1.7, 2.3, 9.0])
    rows = trainSelections(table, table["accepted"], 288000, 120000, 140000, maxGap=0.5)
    assert [r[T_CLICKS] for r in rows] == [3, 1, 1]
    assert [r[T_SEL] for r in rows] == [1, 2, 3]
    assert rows[0][T_BEGIN] == 1.0 - 0.0005 and rows[0][T_END] == 1.7 + 0.0005
    assert rows[1][T_BEGIN] == 2.3 - 0.0005 and rows[1][T_END] == 2.3 + 0.0005
    assert rows[0][T_VIEW] == "Spectrogram 1" and rows[0][T_LOW] == 120000 and rows[0][T_HIGH] == 140000
    assert rows[0][T_PEAK] == 121000.0            # median of 120, 121, 122 kHz
    assert sum(r[T_CLICKS] for r in rows) == len(table)


def test_trains_ignore_table_order_and_rejected_clicks():
    table = _table([1.2, 5.0, 1.0, 1.1], accepted=[True, True, True, False])
    rows = trainSelections(table, table["accepted"], 288000, 120000, 140000)
    assert [(r[T_BEGIN], r[T_END], r[T_CLICKS]) for r in rows] == [
        (1.0 - 0.0005, 1.2 + 0.0005, 2), (5.0 - 0.0005, 5.0 + 0.0005, 1)]


def test_trains_are_per_channel_and_sorted_by_begin():
    table = _table([1.0, 1.1, 1.05, 3.0], channels=[1, 1, 2, 2])
    rows = trainSelections(table, table["accepted"], 512000, 120000, 180000)
    assert [(r[T_CHAN], r[T_CLICKS]) for r in rows] == [(1, 2), (2, 1), (2, 1)]
    assert [r[T_SEL] for r in rows] == [1, 2, 3]
    assert all(r[T_HIGH] == 180000 for r in rows)
    (r,) = trainSelections(table[:1], table["accepted"][:1], 288000, 120000, 180000)
    assert r[T_HIGH] == 144000


def test_trains_edge_cases(tmp_path):
    empty = np.zeros(0, dtype=CANDIDATE_DTYPE)
    assert trainSelections(empty, empty["accepted"], 288000, 120000, 140000) == []
    table = _table([0.0001, 0.0002])
    (r,) = trainSelections(table, table["accepted"], 288000, 120000, 140000)
    assert r[T_BEGIN] == 0.0
    for k in (T_BEGIN, T_END, T_PEAK):
        assert type(r[k]) is float
    for k in (T_SEL, T_CHAN, T_CLICKS):
        assert type(r[k]) is int

    out = tmp_path / "trains.selections.txt"
    writeSelections(out, [r], TRAIN_HEADER)
    lines = _read_back(out)
    assert lines[0] == list(TRAIN_HEADER)
    assert len(lines) == 2 and len(lines[1]) == len(TRAIN_HEADER)
    assert int(lines[1][T_CLICKS]) == 2


# --- on real files -------------------------------------------------------------------

FILES = ["6209.260514052458.wav", "FichierTest_FitzRoy.wav"]
FILES = [f for f in FILES if (WAV_DIR / f).exists()]


@pytest.mark.skipif(not FILES, reason="missing wav files in research/jeu_equivalence/wav")
@pytest.mark.parametrize("file", FILES)
def test_selections_are_the_accepted_clicks_of_the_run(file):
    p = Parameters()
    result = Detector(p).detectFile(WAV_DIR / file)
    table = result.table
    fm = read_info(WAV_DIR / file).sample_rate

    rows = clickSelections(table, table["accepted"], fm, p.f1clic, p.f2clic)

    # per channel, the centres of the boxes are the dates of Res_<name>_Canal<c>.txt, sorted
    for channel, dates in ((1, result.dates1), (2, result.dates2)):
        if dates is None:
            continue
        begins = np.array([r[BEGIN] for r in rows if r[CHAN] == channel])
        assert len(begins) == len(dates), f"{file}: channel {channel}"
        expected = np.maximum(0.0, np.sort(dates) - 0.0005)
        assert np.array_equal(begins, expected), f"{file}: channel {channel}"
    assert len(rows) == int(table["accepted"].sum())
    assert all(r[HIGH] <= fm / 2 for r in rows)
