"""Decision rule of A, recomputed from the candidate table.

Verification tooling written by Claude (Anthropic); not part of the core itself.

The rule of A, inside the detection loop:
    if (energieClic > seuil * energie_bande_passante)
In the table: levelClick > seuil * levelRef.

Criterion: with the seuil of the run, the rule applied to the table gives EXACTLY the
`accepted` column that the detection loop froze (itself compared with A by
test_detection_loop.py and test_equivalence.py).

Expected interface of nbhf.decision:
    thresholdRule(table, seuil) -> bool ndarray, one value per row of the table

    launch test :
        .venv/bin/python -m pytest tests/test_decision.py
"""

from pathlib import Path

import numpy as np
import pytest

from nbhf.decision import thresholdRule
from nbhf.detection import CANDIDATE_DTYPE
from nbhf.detector import Detector
from nbhf.parameters import Parameters

HERE = Path(__file__).resolve().parent
WAV_DIR = HERE.parent / "research" / "jeu_equivalence" / "wav"

# one Bahía file with many clicks, one with few, and the stereo FitzRoy file
FILES = ["6209.260514035958.wav", "6209.260514052458.wav", "FichierTest_FitzRoy.wav"]
FILES = [f for f in FILES if (WAV_DIR / f).exists()]

if not FILES:
    pytest.skip("missing wav files in research/jeu_equivalence/wav", allow_module_level=True)


@pytest.fixture(scope="module", params=FILES)
def table(request):
    return Detector(Parameters()).detectFile(WAV_DIR / request.param).table


def test_same_as_frozen_decision(table):
    decision = thresholdRule(table, Parameters().seuil)
    assert decision.dtype == np.bool_
    assert decision.shape == table.shape
    assert np.array_equal(decision, table["accepted"])


def test_table_is_not_modified(table):
    before = table.copy()
    thresholdRule(table, 0.9)
    assert np.array_equal(table, before)


def test_higher_seuil_keeps_a_subset(table):
    previous = thresholdRule(table, 0.0)
    for seuil in (0.2, 0.4, 0.6, 0.9, 2.0):
        current = thresholdRule(table, seuil)
        assert not np.any(current & ~previous), f"seuil {seuil} accepts a candidate rejected by a lower seuil"
        previous = current


def test_strict_comparison():
    # A uses >, not >=: a candidate exactly on the limit is rejected
    rows = np.zeros(3, dtype=CANDIDATE_DTYPE)
    rows["levelClick"] = [1.0, 0.5, 0.25]
    rows["levelRef"] = [1.0, 1.0, 1.0]
    assert thresholdRule(rows, 0.5).tolist() == [True, False, False]


def test_empty_table():
    empty = np.zeros(0, dtype=CANDIDATE_DTYPE)
    decision = thresholdRule(empty, 0.4)
    assert decision.shape == (0,)
    assert decision.dtype == np.bool_
