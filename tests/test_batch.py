"""nbhfapp.batch: the run started by the interface writes the same files as A.

runBatch is called here in the test process, with a queue.Queue and a threading.Event
(the interface gives it their multiprocessing equivalents). No Qt needed.

Criteria:
  - Res_*.txt written by the interface are byte for byte those of A (references_A_v2);
  - the messages arrive in order and "finished" is the last one;
  - a file that cannot be read is reported and does not stop the run;
  - a stop requested during a file lets it finish and skips the following ones.

    launch test :
        .venv/bin/python -m pytest tests/test_batch.py
"""

import queue
import threading
from pathlib import Path

import numpy as np
import pytest

from nbhf.detection import CANDIDATE_DTYPE
from nbhf.parameters import Parameters
from nbhfapp.batch import runBatch

HERE = Path(__file__).resolve().parent
WAV_DIR = HERE.parent / "research" / "jeu_equivalence" / "wav"
RES_DIR = HERE.parent / "research" / "jeu_equivalence" / "references_A_v2"

MONO = "6209.260514052458.wav"
STEREO = "FichierTest_FitzRoy.wav"

if not all((WAV_DIR / f).exists() for f in (MONO, STEREO)):
    pytest.skip("missing wav files in research/jeu_equivalence/wav", allow_module_level=True)


def _run(paths, outDir, stopEvent=None):
    q = queue.Queue()
    runBatch(paths, outDir, Parameters(), q, stopEvent or threading.Event())
    messages = []
    while not q.empty():
        messages.append(q.get())
    return messages


def test_outputs_are_those_of_A(tmp_path):
    out = tmp_path / "new" / "folder"            # created by the run
    messages = _run([WAV_DIR / MONO, WAV_DIR / STEREO], out)

    written = sorted(p.name for p in out.iterdir())
    stems = [Path(MONO).stem, Path(STEREO).stem]
    assert written == sorted([
        "BilanTot.txt",
        f"Res_{stems[0]}.txt", f"Candidats_{stems[0]}.csv",
        f"Res_{stems[1]}.txt", f"Res_{stems[1]}_Canal1.txt", f"Res_{stems[1]}_Canal2.txt",
        f"Candidats_{stems[1]}.csv",
    ])
    for name in written:
        if name.startswith("Res_"):
            assert (out / name).read_bytes() == (RES_DIR / name).read_bytes(), f"{name} differs from A"

    kinds = [m[0] for m in messages]
    assert kinds == ["started", "done", "started", "done", "finished"]
    assert messages[-1][1] == 2

    for m, name in ((messages[1], MONO), (messages[3], STEREO)):
        _, path, n1, n2, nMerged, table = m
        assert Path(path).name == name
        assert table.dtype == CANDIDATE_DTYPE
        accepted = table["accepted"]
        assert n1 == int(np.sum(accepted & (table["channel"] == 1)))
        assert n2 == int(np.sum(accepted & (table["channel"] == 2)))
        merged = (RES_DIR / f"Res_{Path(name).stem}.txt").read_text().splitlines()
        assert nMerged == len(merged)

    bilan = (out / "BilanTot.txt").read_text(encoding="utf-8")
    assert f"{MONO} \t {messages[1][2]} \t 0 \t {messages[1][4]} \n" in bilan
    assert "Duree totale" in bilan


def test_unreadable_file_does_not_stop_the_run(tmp_path):
    bad = tmp_path / "not_a_sound.wav"
    bad.write_text("x")
    messages = _run([bad, WAV_DIR / MONO], tmp_path / "out")

    kinds = [m[0] for m in messages]
    assert kinds == ["started", "failed", "started", "done", "finished"]
    assert messages[1][1] == str(bad)
    assert messages[1][2]                                   # a message for the user
    assert messages[-1][1] == 1
    assert bad.name not in (tmp_path / "out" / "BilanTot.txt").read_text(encoding="utf-8")


def test_stop_before_the_first_file(tmp_path):
    stop = threading.Event()
    stop.set()
    messages = _run([WAV_DIR / MONO], tmp_path / "out", stop)
    assert [m[0] for m in messages] == ["finished"]
    assert messages[0][1] == 0
    assert not (tmp_path / "out" / f"Res_{Path(MONO).stem}.txt").exists()


def test_stop_lets_the_current_file_finish(tmp_path):
    class StopOnStarted(queue.Queue):
        """Requests the stop as soon as the first file has started."""
        def put(self, item, *args, **kwargs):
            if item[0] == "started":
                stop.set()
            super().put(item, *args, **kwargs)

    stop = threading.Event()
    q = StopOnStarted()
    out = tmp_path / "out"
    runBatch([WAV_DIR / MONO, WAV_DIR / STEREO], out, Parameters(), q, stop)
    kinds = []
    while not q.empty():
        kinds.append(q.get()[0])

    assert kinds == ["started", "done", "finished"]
    name = f"Res_{Path(MONO).stem}.txt"
    assert (out / name).read_bytes() == (RES_DIR / name).read_bytes()
    assert not (out / f"Res_{Path(STEREO).stem}.txt").exists()
