"""chunk threshold and detection loop on one channel."""

import numpy as np
from typing import NamedTuple
import math

SCHEMA_VERSION = 1

class Candidate(NamedTuple):
    ix: int
    x: float
    energieClic: float
    energieBande: float
    accepted: bool
    windowStart : int
    windowStop : int
    peakFreq : float

CANDIDATE_DTYPE = np.dtype([
    ("chunk", np.int32),
    ("channel", np.int8),
    ("ix", np.int64),
    ("sample", np.int64),
    ("date", np.float64),
    ("amplitude", np.float64),
    ("threshold", np.float64),
    ("windowStart", np.int64),
    ("windowStop", np.int64),
    ("levelClick", np.float64),
    ("levelRef", np.float64),
    ("peakFreq", np.float64),
    ("accepted", np.bool_),
])


#x is senal1Hf in octave, ddof equal to calculus with n-1 (octave)
def chunkThreshold(x, coefUmbral):
    ecart_type = np.std(x, ddof = 1)
    return ecart_type * coefUmbral

def windowBounds(ix, sampleRate,n):
    half = sampleRate // 2000
    start = ix -(half - 1)
    stop = ix + half + 1

    #if detection start at the beginning of the trozo
    start =  max(start,0)
    stop = min(stop,n)

    return start, stop

def clickSpectrum(window):
    return np.abs(np.fft.fft(window))

def clickDate(chunkIndex, ix, sampleRate, chunkDuration):
    date_click = (chunkIndex - 1) * chunkDuration + (ix + 1) / sampleRate
    return date_click

#split clickEnergie with two other func to calcul just 1 time the spectrum
def bandLevels(spectre, f1clic, f2clic, f1, f2):
    f1clic = f1clic // 1000
    f2clic = f2clic // 1000
    f1 = f1 // 1000
    f2 = f2 // 1000

    slice = spectre[f1clic-1 : f2clic].mean()
    slice2 = spectre[f1-1 : f2].mean()

    return slice, slice2

def clickEnergies(window, f1clic, f2clic, f1, f2):
    return bandLevels(clickSpectrum(window), f1clic, f2clic, f1, f2)

def peakFrequency(spectre, sampleRate, fmin):
    nWin = len(spectre)
    k0 = math.ceil(fmin * nWin / sampleRate)
    k = k0 + int(np.argmax(spectre[k0 : nWin // 2 + 1]))
    return k * sampleRate / nWin

# while octave in python with class for candidate param, change for a for loop with type flag bool
def detectChannel(senal, senalHF, umbral, sampleRate, *, seuil, tMinimo, f1clic, f2clic, f1, f2):
    n = len(senal)
    zero = math.floor(tMinimo * sampleRate)
    candidates = []

    #new var for loop (for), replace max func
    idx = np.flatnonzero(senalHF > umbral)
    vals = senalHF[idx]
    order = np.argsort(-vals, kind="stable")
    idx = idx[order]
    vals = vals[order]
    dead = np.zeros(n, dtype=bool)

    for ix, x in zip(idx, vals): #
        ix = int(ix)
        if dead[ix]:    #si le pic est déjà passé on le skip et on passe au suivant (tour de boucle suivant) en gardant le +_ 1ms
            continue
        start, stop = windowBounds(ix, sampleRate, n)
        spectre = clickSpectrum(senal[start:stop])
        eClic, eBande = bandLevels(spectre, f1clic, f2clic, f1, f2)
        accepted = eClic > seuil * eBande
        peakFreq = peakFrequency(spectre, sampleRate, f1)
        candidates.append(Candidate(ix, x, eClic, eBande, accepted, start, stop, peakFreq))
        dead[max(0, ix - zero) : min(n, ix + zero + 1)] = True

    return candidates


def candidateRows(candidates, chunkIndex, channel, chunkStart, umbral, sampleRate, chunkDuration):
    rows = []
    for c in candidates:
        sample = chunkStart - 1 + c.ix
        date = clickDate(chunkIndex, c.ix, sampleRate, chunkDuration)
        rows.append((chunkIndex, channel, c.ix, sample, date, c.x, umbral,
                        c.windowStart, c.windowStop, c.energieClic, c.energieBande,
                        c.peakFreq, c.accepted))
    return rows
