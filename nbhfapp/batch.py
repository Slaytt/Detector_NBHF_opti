"""The computation of a run: a list of files, one after the other, outputs written like A.

No Qt here: this module is what the separate process imports (see worker.py). It can
also be called directly, with a queue.Queue and a threading.Event, which is what the
tests do.

Messages put on the queue, in order:
    ("started", path)
    ("done", path, n1, n2, nMerged, table)      n2 is 0 for a mono file
    ("failed", path, message)                   the run goes on with the next file
    ("finished", nProcessed, seconds)           always the last one
"""
import time
from pathlib import Path

from nbhf.detector import Detector
from nbhf.output import (
    bilanFooter, bilanHeader, bilanLine, writeChannel, writeMerged,
)


def writeFileOutputs(outDir, name, result):
    """Res_<stem>.txt (+ one file per channel in stereo)."""
    stem = Path(name).stem
    if result.dates2 is not None:
        writeChannel(outDir / f"Res_{stem}_Canal1.txt", result.dates1)
        writeChannel(outDir / f"Res_{stem}_Canal2.txt", result.dates2)
    writeMerged(outDir / f"Res_{stem}.txt", result.merged)


def runBatch(paths, outDir, params, queue, stopEvent):
    """Process paths in order. stopEvent is looked at between two files only:
    a file that has started is always finished."""
    outDir = Path(outDir)
    outDir.mkdir(parents=True, exist_ok=True)
    detector = Detector(params)
    t0 = time.perf_counter()
    nProcessed = 0

    with open(outDir / "BilanTot.txt", "w", encoding="utf-8") as bilan:
        bilan.write(bilanHeader(params.seuil, params.coefUmbral, params.fcutLow, params.fcutHigh,
                                params.f1clic, params.f2clic, params.f1, params.f2))
        for path in paths:
            if stopEvent.is_set():
                break
            path = Path(path)
            queue.put(("started", str(path)))
            try:
                result = detector.detectFile(path)
                writeFileOutputs(outDir, path.name, result)
            except Exception as e:
                queue.put(("failed", str(path), f"{type(e).__name__}: {e}"))
                continue
            n1 = len(result.dates1)
            n2 = 0 if result.dates2 is None else len(result.dates2)
            bilan.write(bilanLine(path.name, n1, n2, len(result.merged)))
            bilan.flush()
            nProcessed += 1
            queue.put(("done", str(path), n1, n2, len(result.merged), result.table))
        seconds = time.perf_counter() - t0
        bilan.write(bilanFooter(seconds))

    queue.put(("finished", nProcessed, seconds))
