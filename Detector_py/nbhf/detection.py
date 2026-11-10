"""chunk threshold and detection loop on one channel."""
import numpy as np
from typing import NamedTuple
import math

class Candidate(NamedTuple):
    ix: int
    x: float
    energieClic: float
    energieBande: float
    accepted: bool

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


def clickDate(chunkIndex, ix, sampleRate, chunkDuration):
    date_click = (chunkIndex - 1) * chunkDuration + (ix + 1) / sampleRate
    return date_click

def clickEnergies(window, f1clic, f2clic, f1, f2):
    spectre = np.abs(np.fft.fft(window))
    f1clic = f1clic // 1000
    f2clic = f2clic // 1000
    f1 = f1 // 1000
    f2 = f2 // 1000

    slice = spectre[f1clic-1 : f2clic].mean()
    slice2 = spectre[f1-1 : f2].mean()

    return slice, slice2


# while octave in python with class for candidate param
def detectChannel(senal, senalHF, umbral, sampleRate, *, seuil, tMinimo, f1clic, f2clic, f1, f2):
     senalHF = senalHF.copy()
     n = len(senal)
     zero = math.floor(tMinimo * sampleRate)
     candidates = []

     while( senalHF.max() > umbral):
        ix = int(np.argmax(senalHF))
        x = senalHF[ix]
        start, stop = windowBounds(ix, sampleRate, n)
        eClic, eBande = clickEnergies(senal[start:stop],f1clic, f2clic, f1, f2)
        accepted = eClic > seuil * eBande
        candidates.append(Candidate(ix, x, eClic, eBande, accepted))
        senalHF[max(0, ix - zero) : min(n, ix + zero + 1)] = 0.

     return candidates
