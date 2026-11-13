"""Main program: equivalent of DetectorNBHF_todos_passe_bande.m.

    python run_detector.py WAV_DIR LIST_FILE OUT_DIR [PARAMS.toml]
"""

import sys
import time
from pathlib import Path

from nbhf.detector import Detector
from nbhf.output import bilanFooter, bilanHeader, bilanLine, writeChannel, writeMerged
from nbhf.parameters import Parameters


def runDetector(wavDir, listFile, outDir, params):
    wavDir, outDir = Path(wavDir), Path(outDir)
    t0 = time.perf_counter()                                   # tic()
    with open(listFile, encoding="utf-8") as f:
        names = [line.strip() for line in f if line.strip()]
    detector = Detector(params)

    with open(outDir / "BilanTot.txt", "w", encoding="utf-8") as bilan:
        bilan.write(bilanHeader(params.seuil, params.coefUmbral, params.fcutLow, params.fcutHigh,
                                params.f1clic, params.f2clic, params.f1, params.f2))
        for name in names:
            result = detector.detectFile(wavDir / name)
            stem = Path(name).stem                             # NombreArchivo{k}(1:end-4)
            if result.dates2 is not None:                      # stereo only
                writeChannel(outDir / f"Res_{stem}_Canal1.txt", result.dates1)
                writeChannel(outDir / f"Res_{stem}_Canal2.txt", result.dates2)
            writeMerged(outDir / f"Res_{stem}.txt", result.merged)
            n2 = 0 if result.dates2 is None else len(result.dates2)
            bilan.write(bilanLine(name, len(result.dates1), n2, len(result.merged)))
        bilan.write(bilanFooter(time.perf_counter() - t0))    # toc()


if __name__ == "__main__":
    wavDir, listFile, outDir = sys.argv[1:4]
    params = Parameters.fromToml(sys.argv[4]) if len(sys.argv) > 4 else Parameters()
    runDetector(wavDir, listFile, outDir, params)
