"""Detector class: facade that chains the steps for one file."""
from dataclasses import dataclass

import numpy as np

from nbhf.detection import CANDIDATE_DTYPE, candidateRows, chunkThreshold, detectChannel
from nbhf.filtering import filterChunk, filterCoefficients
from nbhf.fusion import mergeChannels
from nbhf.reading import chunk_bounds, n_chunks, read_chunk, read_info


@dataclass
class FileResult:
    dates1: np.ndarray
    dates2: object
    merged: np.ndarray
    table: np.ndarray

class Detector:
    def __init__(self, params):
        self.params = params

    def detectFile(self, path):
        p = self.params
        info = read_info(path)
        fm = info.sample_rate
        b, a = filterCoefficients(fm, p.fcutLow, p.fcutHigh)
        rows = []

        for i in range(1, n_chunks(info.n_samples, fm, p.chunkDuration) + 1):
            start, end = chunk_bounds(i, p.chunkDuration, fm, info.n_samples)
            chunk = read_chunk(path, start, end)
            senalHF = filterChunk(b, a, chunk)
            for c in range(min(info.n_channels, 2)):
                umbral = chunkThreshold(senalHF[:, c], p.coefUmbral)
                candidates = detectChannel(
                    chunk[:, c], senalHF[:, c], umbral, fm,
                    seuil=p.seuil, tMinimo=p.tMinimo,
                    f1clic=p.f1clic, f2clic=p.f2clic, f1=p.f1, f2=p.f2,
                )
                rows += candidateRows(candidates, i, c + 1, start, umbral, fm, p.chunkDuration)

        table = np.array(rows, dtype=CANDIDATE_DTYPE)
        accepted = table["accepted"]
        dates1 = table["date"][accepted & (table["channel"] == 1)]
        dates2 = table["date"][accepted & (table["channel"] == 2)] if info.n_channels > 1 else None
        merged = mergeChannels(dates1, dates2, p.tFusion)
        return FileResult(dates1, dates2, merged, table)
        