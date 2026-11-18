"""What the interface computes from a candidate table, without Qt.

Nothing here detects anything: the table comes from nbhf. These functions apply a
decision rule to it and count. Every number shown is recomputed with the functions
of the core (thresholdRule, mergeChannels), never with a copy of them.
"""
import numpy as np

from nbhf.decision import thresholdRule
from nbhf.fusion import mergeChannels

# parameters that change the population of candidates: the file must be processed again
RECOMPUTE_FIELDS = ("fcutLow", "fcutHigh", "coefUmbral", "tMinimo",
                    "f1clic", "f2clic", "f1", "f2", "chunkDuration")
# the other two, seuil and tFusion, only choose among the candidates: applied at once


def needsRecompute(shown, used):
    """Names of the recompute parameters that differ between two Parameters."""
    return [name for name in RECOMPUTE_FIELDS if getattr(shown, name) != getattr(used, name)]


def decide(table, seuil):
    """The rule of A with another seuil: one boolean per candidate."""
    return thresholdRule(table, seuil)


def channelDates(table, mask, stereo):
    """dates1, dates2 as detectFile builds them (table order kept); dates2 is None in mono."""
    dates1 = table["date"][mask & (table["channel"] == 1)]
    dates2 = table["date"][mask & (table["channel"] == 2)] if stereo else None
    return dates1, dates2


def mergedRows(table, mask, stereo, tFusion):
    dates1, dates2 = channelDates(table, mask, stereo)
    return mergeChannels(dates1, dates2, tFusion)


def counts(table, mask, stereo, tFusion):
    """(candidates, accepted, after merge)."""
    return len(table), int(np.count_nonzero(mask)), len(mergedRows(table, mask, stereo, tFusion))
