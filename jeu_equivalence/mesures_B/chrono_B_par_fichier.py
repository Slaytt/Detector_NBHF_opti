"""Per-file timing of B (one run per file, warm cache, threads fixed to 1). Writes a CSV."""
import os, sys, time
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
sys.path.insert(0, os.getcwd())
from pathlib import Path
from nbhf.detector import Detector
from nbhf.parameters import Parameters
from nbhf.reading import read_info

wav = Path("../jeu_equivalence/wav")
names = [l.strip() for l in open("../run_bahia/liste_fichiers_extrait.txt") if l.strip()]
det = Detector(Parameters())
out = Path(sys.argv[1])
with open(out, "w") as f:
    f.write("fichier,n1,n2,total,temps_s,ftr\n")
    for n in names:
        info = read_info(wav / n)
        dur = info.n_samples / info.sample_rate
        t0 = time.perf_counter()
        r = det.detectFile(wav / n)
        t = time.perf_counter() - t0
        n2 = 0 if r.dates2 is None else len(r.dates2)
        f.write(f"{n},{len(r.dates1)},{n2},{len(r.merged)},{t:.2f},{dur/t:.1f}\n")
        f.flush()
        print(n, f"{t:.2f}s", flush=True)
