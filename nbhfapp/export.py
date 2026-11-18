"""Export of the results shown, with the direct settings of the moment. No Qt.

The files written at the end of a run (batch.py) use the parameters of the run, like A.
An export applies the seuil and tFusion currently displayed to the candidate tables,
without processing the audio again.
"""
from dataclasses import dataclass
from pathlib import Path

from nbhf.output import (
    bilanHeader, bilanLine, writeCandidates, writeChannel, writeMerged,
)
from nbhf.raven import (
    RAVEN_HEADER, TRAIN_HEADER, clickSelections, trainSelections, writeSelections,
)
from nbhfapp.analysis import channelDates, decide, mergedRows

CLICKS, TRAINS = "clicks", "trains"


@dataclass
class ExportOptions:
    res: bool = False               # Res_*.txt and BilanTot.txt
    raven: bool = True              # Raven selection tables
    ravenMode: str = CLICKS         # CLICKS or TRAINS
    maxGap: float = 0.5             # s, largest gap inside a train
    candidates: bool = False        # Candidats_*.csv


@dataclass
class FileRun:
    """What the interface keeps about a processed file."""
    path: Path
    table: object                   # candidate table
    sampleRate: int
    stereo: bool


def ravenName(wavName):
    return f"{Path(wavName).stem}.nbhf.selections.txt"


def exportRuns(runs, outDir, params, seuil, tFusion, options):
    """Write the chosen files for every run. params are those of the run (bands, cut-offs);
    seuil and tFusion are the displayed ones. Returns the list of files written."""
    outDir = Path(outDir)
    outDir.mkdir(parents=True, exist_ok=True)
    written = []
    bilanLines = []

    for run in runs:
        stem = Path(run.path).stem
        mask = decide(run.table, seuil)

        if options.res:
            dates1, dates2 = channelDates(run.table, mask, run.stereo)
            merged = mergedRows(run.table, mask, run.stereo, tFusion)
            if dates2 is not None:
                for channel, dates in ((1, dates1), (2, dates2)):
                    target = outDir / f"Res_{stem}_Canal{channel}.txt"
                    writeChannel(target, dates)
                    written.append(target)
            target = outDir / f"Res_{stem}.txt"
            writeMerged(target, merged)
            written.append(target)
            n2 = 0 if dates2 is None else len(dates2)
            bilanLines.append(bilanLine(Path(run.path).name, len(dates1), n2, len(merged)))

        if options.raven:
            target = outDir / ravenName(run.path)
            if options.ravenMode == TRAINS:
                rows = trainSelections(run.table, mask, run.sampleRate, params.f1clic, params.f2clic,
                                       maxGap=options.maxGap)
                writeSelections(target, rows, TRAIN_HEADER)
            else:
                rows = clickSelections(run.table, mask, run.sampleRate, params.f1clic, params.f2clic)
                writeSelections(target, rows, RAVEN_HEADER)
            written.append(target)

        if options.candidates:
            target = outDir / f"Candidats_{stem}.csv"
            writeCandidates(target, run.table)
            written.append(target)

    if options.res:
        # same header and lines as A; no "Duree totale": an export computes nothing
        target = outDir / "BilanTot.txt"
        with open(target, "w", encoding="utf-8") as bilan:
            bilan.write(bilanHeader(seuil, params.coefUmbral, params.fcutLow, params.fcutHigh,
                                    params.f1clic, params.f2clic, params.f1, params.f2))
            bilan.writelines(bilanLines)
        written.append(target)

    return written
