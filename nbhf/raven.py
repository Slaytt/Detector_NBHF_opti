"""Raven selection tables built from the candidate table: one click per line, or one
train of clicks per line.

Not produced by A: Res_*.txt stays the reference output. The table of selections is
derived from the candidate table and a decision rule (a boolean per candidate).
"""
import csv

import numpy as np

RAVEN_HEADER = (
    "Selection", "View", "Channel", "Begin Time (s)", "End Time (s)",
    "Low Freq (Hz)", "High Freq (Hz)", "Amplitude", "Ratio", "Peak Freq (Hz)",
)

TRAIN_HEADER = (
    "Selection", "View", "Channel", "Begin Time (s)", "End Time (s)",
    "Low Freq (Hz)", "High Freq (Hz)", "Clicks", "Peak Freq (Hz)",
)

VIEW = "Spectrogram 1"


def clickSelections(table, mask, sampleRate, lowFreq, highFreq, halfWidth=0.0005):
    """One row per candidate kept by mask, sorted by date, numbered from 1.

    The box is centred on the date of A (never recomputed from `sample`), from
    lowFreq to highFreq, the latter clipped at Nyquist; a box never starts before
    0 s (A can date a click in the first half millisecond). Ratio is for display only:
    the decision of A is levelClick > seuil * levelRef, not a test on the ratio.
    """
    kept = table[mask]
    kept = kept[np.argsort(kept["date"], kind="stable")]
    high = min(highFreq, sampleRate / 2)

    channels = kept["channel"].tolist()
    dates = kept["date"].tolist()
    amplitudes = kept["amplitude"].tolist()
    levelsClick = kept["levelClick"].tolist()
    levelsRef = kept["levelRef"].tolist()
    peaks = kept["peakFreq"].tolist()

    rows = []
    for k in range(len(dates)):
        ratio = levelsClick[k] / levelsRef[k] if levelsRef[k] != 0 else float("inf")
        rows.append((
            k + 1, VIEW, channels[k],
            max(0.0, dates[k] - halfWidth), dates[k] + halfWidth,
            lowFreq, high,
            amplitudes[k], ratio, peaks[k],
        ))
    return rows


def trainSelections(table, mask, sampleRate, lowFreq, highFreq, maxGap=0.5, halfWidth=0.0005):
    """One row per train of clicks, sorted by begin time, numbered from 1.

    Channel by channel, the kept clicks are sorted by date; a new train starts when
    the gap to the previous click is larger than maxGap. A lone click is a train of
    one. The box goes from the first click - halfWidth to the last click + halfWidth.
    Clicks is the number of clicks, Peak Freq the median of their peakFreq.
    """
    kept = table[mask]
    high = min(highFreq, sampleRate / 2)

    trains = []
    for channel in np.unique(kept["channel"]).tolist():
        sel = kept[kept["channel"] == channel]
        sel = sel[np.argsort(sel["date"], kind="stable")]
        if len(sel) == 0:
            continue
        dates = sel["date"]
        starts = np.flatnonzero(np.diff(dates) > maxGap) + 1
        bounds = [0, *starts.tolist(), len(sel)]
        for a, b in zip(bounds[:-1], bounds[1:]):
            trains.append((
                max(0.0, float(dates[a]) - halfWidth), float(dates[b - 1]) + halfWidth,
                channel, b - a, float(np.median(sel["peakFreq"][a:b])),
            ))
    trains.sort(key=lambda t: t[0])   

    return [
        (k + 1, VIEW, channel, begin, end, lowFreq, high, nClicks, peak)
        for k, (begin, end, channel, nClicks, peak) in enumerate(trains)
    ]


def writeSelections(path, rows, header=RAVEN_HEADER):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
