"""Micro-benchmark: cost of one full pass of max/argmax on a chunk-sized array (see RESULTATS_B.md §2.4).
Octave counterpart: bench_max.m. Run with Detector_py/.venv/bin/python."""
import numpy as np, time

n = int(29.99 * 288000)
x = np.random.randn(n)

def bench(f, k=20):
    f()
    t = time.perf_counter()
    for _ in range(k):
        f()
    return (time.perf_counter() - t) / k * 1000

print(f"n={n}  taille={n*8/1e6:.0f} Mo")
print(f"x.max()      : {bench(lambda: x.max()):.2f} ms")
print(f"np.argmax(x) : {bench(lambda: np.argmax(x)):.2f} ms")
print(f"boucle python sur 100k elements (extrapolee a n) : {bench(lambda: max(x[:100000].tolist()), 3)*n/100000:.0f} ms")
