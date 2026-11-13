"""filter coefficients and filtering of a chunk."""
from scipy.signal import butter
from scipy.signal import lfilter

def filterCoefficients(sampleRate, fcutLow, fcutHigh):
    fNyquist = sampleRate/2

    if fcutHigh >= fNyquist :
        b,a = butter(5, fcutLow / fNyquist, btype="highpass") #butter renvoie un tupple de coef
    else :
        b,a = butter(5, [fcutLow / fNyquist, fcutHigh / fNyquist], btype="bandpass")

    return b,a

def filterChunk(b,a,chunk):
    res = lfilter(b, a, chunk,axis = 0)
    return res
