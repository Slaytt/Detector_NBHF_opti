"""Candidats_<name>.csv: the candidate table written to disk and read back.

This file is not produced by A (A keeps no trace of rejected candidates), so there is no
Octave reference. Criterion: reading the CSV back gives EXACTLY the table in memory
(same columns, same order, every float bit for bit).

Expected interface of nbhf.output:
    writeCandidates(path, table) -> writes one header line (the column names of
        CANDIDATE_DTYPE, comma separated) then one line per candidate
And run_detector.runDetector writes Candidats_<stem>.csv next to Res_<stem>.txt.

    launch test :
        .venv/bin/python -m pytest tests/test_candidates_csv.py
"""

import csv
from pathlib import Path

import numpy as np
import pytest

from nbhf.detection import CANDIDATE_DTYPE
from nbhf.detector import Detector
from nbhf.output import writeCandidates
from nbhf.parameters import Parameters
from run_detector import runDetector

HERE = Path(__file__).resolve().parent
WAV_DIR = HERE.parent / "research" / "jeu_equivalence" / "wav"

# one mono Bahía file with few candidates, and the stereo FitzRoy file
FILES = ["6209.260514052458.wav", "FichierTest_FitzRoy.wav"]
FILES = [f for f in FILES if (WAV_DIR / f).exists()]

if not FILES:
    pytest.skip("missing wav files in research/jeu_equivalence/wav", allow_module_level=True)


def _read_back(path):
    """The CSV as a structured array of CANDIDATE_DTYPE, plus its header."""
    with open(path, encoding="utf-8", newline="") as f:
        lines = list(csv.reader(f))
    header, body = lines[0], lines[1:]
    table = np.zeros(len(body), dtype=CANDIDATE_DTYPE)
    for k, line in enumerate(body):
        assert len(line) == len(header), f"line {k + 2}: {len(line)} fields, header has {len(header)}"
        for name, text in zip(header, line):
            kind = CANDIDATE_DTYPE[name].kind
            if kind == "b":
                assert text in ("True", "False"), f"line {k + 2}: {name} = {text!r}"
                table[name][k] = text == "True"
            elif kind == "i":
                table[name][k] = int(text)
            else:
                table[name][k] = float(text)
    return header, table


@pytest.mark.parametrize("file", FILES)
def test_round_trip(file, tmp_path):
    table = Detector(Parameters()).detectFile(WAV_DIR / file).table
    assert len(table) > 0, f"{file}: no candidate, the test would check nothing"
    out = tmp_path / "Candidats.csv"

    writeCandidates(out, table)

    header, back = _read_back(out)
    assert header == list(CANDIDATE_DTYPE.names)
    assert len(back) == len(table)
    for name in CANDIDATE_DTYPE.names:
        assert np.array_equal(back[name], table[name]), f"{file}: column {name} differs after reading back"


def test_empty_table(tmp_path):
    out = tmp_path / "Candidats.csv"
    writeCandidates(out, np.zeros(0, dtype=CANDIDATE_DTYPE))
    header, back = _read_back(out)
    assert header == list(CANDIDATE_DTYPE.names)
    assert len(back) == 0


def test_no_blank_lines(tmp_path):
    # without newline="" the csv module writes \r\r\n on Windows
    table = np.zeros(2, dtype=CANDIDATE_DTYPE)
    out = tmp_path / "Candidats.csv"
    writeCandidates(out, table)
    raw = out.read_bytes()
    assert b"\r\r" not in raw
    assert len(raw.splitlines()) == 3


def test_program_writes_candidates(tmp_path):
    name = FILES[0]
    list_file = tmp_path / "liste.txt"
    list_file.write_text(name + "\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    runDetector(WAV_DIR, list_file, out_dir, Parameters())

    out = out_dir / f"Candidats_{Path(name).stem}.csv"
    assert out.exists(), f"{out.name} not written by runDetector"
    _, back = _read_back(out)
    table = Detector(Parameters()).detectFile(WAV_DIR / name).table
    assert np.array_equal(back, table)
