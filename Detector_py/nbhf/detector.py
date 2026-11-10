"""Detector class: facade that chains the steps for one file."""
from dataclasses import dataclass

import numpy as np

from nbhf.detection import chunkThreshold, clickDate, detectChannel
from nbhf.filtering import filterChunk, filterCoefficients
from nbhf.fusion import mergeChannels
from nbhf.reading import chunk_bounds, n_chunks, read_chunk, read_info


@dataclass
class FileResult:
    dates1: np.ndarray        # accepted dates of channel 1, in detection order
    dates2: object            # same for channel 2, or None for a mono file
    merged: np.ndarray        # (N, 2) from mergeChannels


class Detector:
    def __init__(self, params):
        self.params = params

    def detectFile(self, path):
        p = self.params
        info = read_info(path)
        fm = info.sample_rate
        b, a = filterCoefficients(fm, p.fcutLow, p.fcutHigh)
        dates = [[], []]

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
                for cand in candidates:
                    if cand.accepted:
                        dates[c].append(clickDate(i, cand.ix, fm, p.chunkDuration))

        dates1 = np.array(dates[0], dtype=float)
        dates2 = np.array(dates[1], dtype=float) if info.n_channels > 1 else None
        merged = mergeChannels(dates1, dates2, p.tFusion)
        return FileResult(dates1, dates2, merged)
