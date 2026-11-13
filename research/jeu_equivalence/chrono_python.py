#!/usr/bin/env python3
"""Temps de calcul de B ou de C selon le protocole (section 7), fichier par fichier.

Outillage de mesure écrit par Claude (Anthropic) le 13/11/2026 ; ne fait pas partie du portage.

Usage (depuis la racine du dépôt, avec le venv de la racine) :
    .venv/bin/python -I research/jeu_equivalence/chrono_python.py B --batterie
    .venv/bin/python -I research/jeu_equivalence/chrono_python.py C --batterie
    ... --fichiers 6209.260514052458.wav FichierTest_FitzRoy.wav
    ... --essais 1 --sans-echauffement        (mesure rapide, hors protocole)

B = paquet `nbhfB` (copie figée du portage fidèle), C = paquet `nbhf` (version optimisée).

Pour chaque fichier :
  - 1 échauffement non compté (cache disque chaud), puis `--essais` passages de
    `Detector(Parameters()).detectFile`, chronométrés avec time.perf_counter ; on garde la médiane ;
  - la lecture seule (read_chunk sur tous les morceaux) chronométrée à part, médiane de 3 ;
  - les sorties du dernier essai écrites avec nbhf*.output et comparées octet par octet à
    references_A_v2/ (colonne sorties_conformes) ;
  - le nombre de candidats est repris de mesures_A/candidats_A_*.csv (identique par équivalence),
    pour la régression temps = a + b × candidats.

Threads fixés à 1 (protocole 7.2). FTR = durée audio / temps de calcul.
Résultats dans mesures_B/ ou mesures_C/ (csv + txt des conditions), jamais écrasés.
"""
import argparse
import csv
import filecmp
import glob
import hashlib
import importlib
import os
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"

ICI = os.path.dirname(os.path.abspath(__file__))
DEPOT = os.path.dirname(os.path.dirname(ICI))      # Detector_NBHF_opti (ICI = research/jeu_equivalence)
RESEARCH = os.path.dirname(ICI)                      # research/ : contient nbhfB (B figé)
WAV = os.path.join(ICI, "wav")
MANIFESTE = os.path.join(ICI, "manifeste.csv")
REFERENCES = os.path.join(ICI, "references_A_v2")
PAQUETS = {"B": "nbhfB", "C": "nbhf"}
ESSAIS = 3

sys.path.insert(0, DEPOT)      # nbhf (C)
sys.path.insert(0, RESEARCH)   # nbhfB (B)
import numpy as np   # noqa: E402  (après le réglage des threads)


def lire_manifeste():
    with open(MANIFESTE, encoding="utf-8") as f:
        return [l for l in csv.DictReader(f, delimiter=";") if l["statut"] == "present"]


def candidats_de_A():
    """fichier -> nombre de candidats du while, d'après le dernier candidats_A_*.csv."""
    fichiers = sorted(glob.glob(os.path.join(ICI, "mesures_A", "candidats_A_*.csv")))
    if not fichiers:
        return {}
    with open(fichiers[-1], encoding="utf-8") as f:
        return {l["fichier"]: int(l["candidats"]) for l in csv.DictReader(f, delimiter=";")}


def sur_secteur():
    r = subprocess.run(["pmset", "-g", "ps"], capture_output=True, text=True)
    return "AC Power" in r.stdout


def economie_energie():
    r = subprocess.run(["pmset", "-g"], capture_output=True, text=True)
    return any(l.split()[:2] == ["lowpowermode", "1"] for l in r.stdout.splitlines())


def sortie_commande(cmd, cwd=None):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd).stdout.strip()
    except OSError:
        return "?"


def sha_paquet(paquet):
    """sha256 de la concaténation des .py du paquet, dans l'ordre des noms."""
    dossier = os.path.join(DETECTOR_PY, paquet)
    h = hashlib.sha256()
    for nom in sorted(os.listdir(dossier)):
        if nom.endswith(".py"):
            with open(os.path.join(dossier, nom), "rb") as f:
                h.update(nom.encode() + b"\n" + f.read())
    return h.hexdigest()


def blas():
    try:
        cfg = np.show_config(mode="dicts")
        b = cfg.get("Build Dependencies", {}).get("blas", {})
        return f"{b.get('name', '?')} {b.get('version', '')}".strip()
    except Exception:
        return "?"


def ecrire_conditions(chemin, args, paquet):
    import scipy, soundfile
    lignes = [
        f"date : {datetime.now():%Y-%m-%d %H:%M}",
        f"commande : chrono_python.py {args.version} --essais {args.essais}"
        + (" --sans-echauffement" if args.sans_echauffement else "")
        + (" --batterie" if args.batterie else "")
        + (f" --fichiers {' '.join(args.fichiers)}" if args.fichiers else ""),
        f"version : {args.version} = paquet {paquet}/, sha256 des .py {sha_paquet(paquet)}",
        f"dépôt : commit {sortie_commande(['git', 'rev-parse', '--short', 'HEAD'], cwd=DEPOT)}"
        + (" (modifications non commitées)" if sortie_commande(['git', 'status', '--porcelain', 'nbhf', os.path.join('research', 'nbhfB')], cwd=DEPOT) else ""),
        f"machine : {sortie_commande(['sysctl', '-n', 'hw.model'])} / "
        f"{sortie_commande(['sysctl', '-n', 'machdep.cpu.brand_string'])} / "
        f"{int(sortie_commande(['sysctl', '-n', 'hw.memsize']) or 0) / 2**30:.0f} Go / "
        f"macOS {sortie_commande(['sw_vers', '-productVersion'])}",
        f"alimentation : {sortie_commande(['pmset', '-g', 'ps']).splitlines()[0]}, "
        f"mode économie d'énergie {'activé' if economie_energie() else 'désactivé'}",
        f"python : {sys.version.split()[0]}, numpy {np.__version__}, scipy {scipy.__version__}, "
        f"soundfile {soundfile.__version__}, BLAS {blas()}",
        "threads : OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1",
        "temps d'un essai : time.perf_counter autour de Detector.detectFile (lecture + filtre + "
        "détection + fusion, sans l'écriture des fichiers ni le démarrage de Python)",
        "lecture : read_chunk sur tous les morceaux, médiane de 3, chronométrée à part",
        "cache disque : chaud (échauffement non compté)",
    ]
    with open(chemin, "w", encoding="utf-8") as f:
        f.write("\n".join(lignes) + "\n")


def nouveau_nom(dossier, prefixe, extension):
    os.makedirs(dossier, exist_ok=True)
    return os.path.join(dossier, f"{prefixe}_{datetime.now():%Y%m%d_%H%M}.{extension}")


def conformes(mod_output, resultat, stem, tmp):
    """Sorties du passage identiques à references_A_v2/ ?"""
    noms = []
    p = os.path.join(tmp, f"Res_{stem}.txt")
    mod_output.writeMerged(p, resultat.merged)
    noms.append(p)
    if resultat.dates2 is not None:
        for canal, dates in ((1, resultat.dates1), (2, resultat.dates2)):
            p = os.path.join(tmp, f"Res_{stem}_Canal{canal}.txt")
            mod_output.writeChannel(p, dates)
            noms.append(p)
    return all(os.path.exists(os.path.join(REFERENCES, os.path.basename(n)))
               and filecmp.cmp(n, os.path.join(REFERENCES, os.path.basename(n)), shallow=False)
               for n in noms)


def temps_lecture(mod_reading, chemin, chunk_duration, essais=3):
    info = mod_reading.read_info(chemin)
    durees = []
    for _ in range(essais):
        t0 = time.perf_counter()
        for i in range(1, mod_reading.n_chunks(info.n_samples, info.sample_rate, chunk_duration) + 1):
            s, e = mod_reading.chunk_bounds(i, chunk_duration, info.sample_rate, info.n_samples)
            mod_reading.read_chunk(chemin, s, e)
        durees.append(time.perf_counter() - t0)
    return statistics.median(durees)


def regression(xs, ys):
    """Ajustement y = a + b x ; renvoie a, b, R²."""
    x, y = np.asarray(xs, float), np.asarray(ys, float)
    if len(x) < 3:
        return float("nan"), float("nan"), float("nan")
    b, a = np.polyfit(x, y, 1)
    pred = a + b * x
    r2 = 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    return a, b, r2


def main():
    p = argparse.ArgumentParser()
    p.add_argument("version", choices=sorted(PAQUETS), help="B (nbhfB, figé) ou C (nbhf, optimisé)")
    p.add_argument("--fichiers", nargs="+", help="limiter à ces fichiers (noms du manifeste)")
    p.add_argument("--essais", type=int, default=ESSAIS, help="essais comptés par fichier")
    p.add_argument("--sans-echauffement", action="store_true", help="pas d'échauffement")
    p.add_argument("--batterie", action="store_true",
                   help="accepter la batterie (mode économie d'énergie désactivé)")
    args = p.parse_args()

    if economie_energie():
        sys.exit("Le mode économie d'énergie est activé : désactive-le avant de mesurer.")
    if not sur_secteur() and not args.batterie:
        sys.exit("Le Mac est sur batterie : branche-le, ou relance avec --batterie "
                 "(même alimentation que A, protocole 7.2).")
    secteur_au_debut = sur_secteur()

    paquet = PAQUETS[args.version]
    detector = importlib.import_module(f"{paquet}.detector")
    parameters = importlib.import_module(f"{paquet}.parameters")
    reading = importlib.import_module(f"{paquet}.reading")
    output = importlib.import_module(f"{paquet}.output")
    params = parameters.Parameters()
    det = detector.Detector(params)

    lignes = lire_manifeste()
    if args.fichiers:
        lignes = [l for l in lignes if l["fichier"] in args.fichiers]
    cand = candidats_de_A()
    dossier = os.path.join(ICI, f"mesures_{args.version}")
    chemin = nouveau_nom(dossier, f"temps_{args.version}", "csv")
    ecrire_conditions(chemin[:-4] + ".txt", args, paquet)
    print(f"{args.version} ({paquet}) : {len(lignes)} fichier(s), "
          f"{0 if args.sans_echauffement else 1} échauffement + {args.essais} essai(s) chacun. "
          f"Ne te sers pas du Mac pendant la mesure.\nRésultats : {chemin}", flush=True)

    total_audio = total_calcul = total_lecture = 0.0
    xs, ys = [], []
    with open(chemin, "w", newline="", encoding="utf-8") as f, \
            tempfile.TemporaryDirectory(prefix=f"temps_{args.version}_") as tmp:
        w = csv.writer(f, delimiter=";")
        w.writerow(["fichier", "strate", "duree_audio_s", "detections", "candidats", "echauffement_s"]
                   + [f"essai{i + 1}_s" for i in range(args.essais)]
                   + ["mediane_s", "lecture_mediane_s", "FTR", "sorties_conformes"])
        for l in lignes:
            nom = l["fichier"]
            wav = os.path.join(WAV, nom)
            duree = float(l["duree_s"])
            echauffement = ""
            if not args.sans_echauffement:
                t0 = time.perf_counter()
                det.detectFile(wav)
                echauffement = f"{time.perf_counter() - t0:.3f}"
            essais = []
            for _ in range(args.essais):
                t0 = time.perf_counter()
                resultat = det.detectFile(wav)
                essais.append(time.perf_counter() - t0)
            mediane = statistics.median(essais)
            lecture = temps_lecture(reading, wav, params.chunkDuration)
            ok = conformes(output, resultat, nom[:-4], tmp)
            n_det = len(resultat.merged)
            w.writerow([nom, l["strate"], f"{duree:.3f}", n_det, cand.get(nom, ""), echauffement]
                       + [f"{e:.3f}" for e in essais]
                       + [f"{mediane:.3f}", f"{lecture:.3f}", f"{duree / mediane:.2f}", "oui" if ok else "NON"])
            f.flush()
            total_audio += duree
            total_calcul += mediane
            total_lecture += lecture
            if l["fm_Hz"] == "288000" and l["canaux"] == "1" and nom in cand:
                xs.append(cand[nom])
                ys.append(mediane)
            print(f"  {nom:28s} médiane {mediane:7.2f} s   lecture {lecture:5.2f} s   FTR {duree / mediane:7.1f}"
                  + ("" if ok else "   ATTENTION : sorties différentes des références"), flush=True)

    print(f"\nJeu entier : {total_audio / 60:.1f} min d'audio, {total_calcul:.1f} s de calcul "
          f"(dont lecture {total_lecture:.1f} s), FTR {total_audio / total_calcul:.1f}")
    a, b, r2 = regression(xs, ys)
    if xs:
        print(f"Bahía (288 kHz, mono, {len(xs)} fichiers) : temps ≈ {a:.2f} s + {1000 * b:.3f} ms × candidats, R² = {r2:.4f}")
    if sur_secteur() != secteur_au_debut:
        print("ATTENTION : l'alimentation a changé pendant la mesure.")


if __name__ == "__main__":
    main()
