"""Detector parameters (frozen dataclass), loadable from species/*.toml.

Defaults: the parameter block of A* (run_bahia/DetectorNBHF_todos_passe_bande.m),
written as in Octave. t_detect is declared in A but never used, so it is not here.
"""
import tomllib
from dataclasses import dataclass


@dataclass(frozen=True)
class Parameters:
    coefUmbral: float = 9
    seuil: float = 0.4
    fcutLow: float = 100000
    fcutHigh: float = 180000
    f1clic: float = 120000
    f2clic: float = 140000
    f1: float = 30000
    f2: float = 90000
    tMinimo: float = 1 / 1000
    chunkDuration: float = 29.99
    tFusion: float = 5 / 10000

    @classmethod
    def fromToml(cls, path):
        with open(path, "rb") as f:
            return cls(**tomllib.load(f))
