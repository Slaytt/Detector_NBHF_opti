"""infos du fichier, bornes et lecture d'un morceau"""
from dataclasses import dataclass
import math
import soundfile

@dataclass(frozen = True)
class AudioInfo:
    sample_rate : int
    n_samples : int
    n_channels : int


def read_info(path):
    info = soundfile.info(path)
    return AudioInfo(info.samplerate, info.frames, info.channels)

def n_chunks(n_samples, sample_rate, chunk_duration):
    total_time = n_samples/ sample_rate
    return math.floor(total_time/chunk_duration)+1

def chunk_bounds(i, chunk_duration, sample_rate, n_samples):
    c_entry = (i-1)*chunk_duration
    c_out = c_entry + chunk_duration
    initC = c_entry * sample_rate
    endC = c_out * sample_rate
    start = math.floor(max(initC,1))
    end = math.floor(min(endC, n_samples))

    return start, end

def read_chunk(path, start, end):
    data,_ = soundfile.read(path,start = start-1, stop = end, always_2d=True)
    return data
