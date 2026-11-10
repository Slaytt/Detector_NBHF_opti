"""merge of the detections of both channels."""
import numpy as np

def mergeChannels(dates1, dates2, tFusion):
    rows = [(float(d), 1.0) for d in dates1]
    if dates2 is not None:
        rows += [(float(d), 2.0) for d in dates2]
    rows.sort()

    if dates2 is not None:
        n = 0
        while n < len(rows) - 2:
            if abs(rows[n + 1][0] - rows[n][0]) < tFusion:
                del rows[n + 1]
            n += 1
    return np.array(rows, dtype=np.float64).reshape(-1, 2)
