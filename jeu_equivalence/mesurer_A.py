#!/usr/bin/env python3
"""Mesure de A* : temps de calcul (protocole, section 7) et profilage (étape 2 de la roadmap).

A* n'est pas modifié. Chaque passage se fait dans un dossier temporaire qui contient une copie
de A* et une liste d'un seul fichier (A* commence par `clear`, on ne peut donc pas le piloter
depuis un script Octave appelant).

Usage :
    python3 -I jeu_equivalence/mesurer_A.py temps                 # les 24 fichiers, environ 45 min
    python3 -I jeu_equivalence/mesurer_A.py temps --essais 1 --sans-echauffement   # environ 11 min
    python3 -I jeu_equivalence/mesurer_A.py temps --fichiers 6209.260514052458.wav
    python3 -I jeu_equivalence/mesurer_A.py profil 6209.260514052458.wav
    python3 -I jeu_equivalence/mesurer_A.py candidats             # les 24 fichiers, environ 11 min

Temps : pour chaque fichier, 1 échauffement non compté puis 3 essais (réglables avec --essais et
--sans-echauffement). Le temps d'un essai est la ligne « Duree totale » de BilanTot.txt (tic/toc
interne de A), donc sans le démarrage d'Octave. On garde la médiane. FTR = durée audio / temps de
calcul. Les conditions de la mesure sont écrites à côté du CSV, dans un .txt du même nom.

Profil : un passage sous `profile on`. Le temps sous profileur est plus long que le vrai temps :
on n'en garde que les proportions.

Candidats : un passage sous profileur par fichier, sans échauffement. Le nombre d'appels de `fft`
est le nombre de candidats examinés par le while (acceptés et rejetés), tous canaux confondus.

Les sorties vont dans jeu_equivalence/mesures_A/ et ne sont jamais écrasées.
"""
import argparse
import csv
import filecmp
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
from datetime import datetime

ICI = os.path.dirname(os.path.abspath(__file__))
DOSSIER_A = os.path.dirname(ICI)                    # Detector_NBHF_opti
A_ETOILE = os.path.join(DOSSIER_A, "run_bahia", "DetectorNBHF_todos_passe_bande.m")
MANIFESTE = os.path.join(ICI, "manifeste.csv")
REFERENCES = os.path.join(ICI, "references_A_v2")
SORTIES = os.path.join(ICI, "mesures_A")
ESSAIS = 3

# threads fixés (protocole, section 7.2)
ENV = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1")

# Code Octave lancé autour de A* pour le profil. A* apparaît comme un nœud de p.Hierarchical ;
# ses enfants sont les fonctions qu'il appelle directement, avec un TotalTime qui inclut leurs
# sous-appels. La première ligne du fichier donne le temps total de A* sous profileur.
PROFIL_OCTAVE = r"""
profile on
DetectorNBHF_todos_passe_bande
profile off
p = profile('info');
fid = fopen('profil_etapes.csv', 'w');
fprintf(fid, 'fonction;appels;temps_inclusif_s\n');
for a = p.Hierarchical'
  if strcmp(p.FunctionTable(a.Index).FunctionName, 'DetectorNBHF_todos_passe_bande')
    fprintf(fid, '%s;%d;%.6f\n', 'TOTAL_A', a.NumCalls, a.TotalTime);
    for h = a.Children'
      fprintf(fid, '%s;%d;%.6f\n', p.FunctionTable(h.Index).FunctionName, h.NumCalls, h.TotalTime);
    end
  end
end
fclose(fid);
fid = fopen('profil_fonctions.csv', 'w');
fprintf(fid, 'fonction;appels;temps_propre_s\n');
for f = p.FunctionTable'
  fprintf(fid, '%s;%d;%.6f\n', f.FunctionName, f.NumCalls, f.TotalTime);
end
fclose(fid);
"""


def lire_manifeste():
    with open(MANIFESTE, encoding="utf-8") as f:
        return [l for l in csv.DictReader(f, delimiter=";") if l["statut"] == "present"]


def sur_secteur():
    r = subprocess.run(["pmset", "-g", "ps"], capture_output=True, text=True)
    return "AC Power" in r.stdout


def economie_energie():
    r = subprocess.run(["pmset", "-g"], capture_output=True, text=True)
    return any(l.split()[:2] == ["lowpowermode", "1"] for l in r.stdout.splitlines())


def preparer(dossier, fichier):
    shutil.copy2(A_ETOILE, dossier)
    with open(os.path.join(dossier, "liste_fichiers_extrait.txt"), "w") as f:
        f.write(fichier + "\n")


def lancer(dossier, eval_octave=None):
    """Un passage de A* dans `dossier`, avec un Resultats_passe_bande vide. Renvoie la durée de A."""
    resultats = os.path.join(dossier, "Resultats_passe_bande")
    shutil.rmtree(resultats, ignore_errors=True)
    os.mkdir(resultats)
    cmd = ["octave", "--no-gui"]
    cmd += ["--eval", eval_octave] if eval_octave else [os.path.basename(A_ETOILE)]
    with open(os.path.join(dossier, "octave.log"), "w") as log:
        r = subprocess.run(cmd, cwd=dossier, env=ENV, stdout=log, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        sys.exit(f"ÉCHEC : Octave a renvoyé {r.returncode}, voir {dossier}/octave.log")
    with open(os.path.join(resultats, "BilanTot.txt"), encoding="utf-8", errors="replace") as f:
        for l in f:
            if l.startswith("Duree totale"):
                return float(l.split()[2])
    sys.exit(f"ÉCHEC : pas de ligne « Duree totale » dans {resultats}/BilanTot.txt")


def detections(dossier, fichier):
    with open(os.path.join(dossier, "Resultats_passe_bande", "BilanTot.txt"),
              encoding="utf-8", errors="replace") as f:
        for l in f:
            if l.startswith(fichier):
                return int(l.split()[-1])
    return -1


def acceptes_par_canal(dossier, fichier):
    """Somme des détections canal 1 + canal 2, avant la fusion des canaux (= candidats acceptés)."""
    with open(os.path.join(dossier, "Resultats_passe_bande", "BilanTot.txt"),
              encoding="utf-8", errors="replace") as f:
        for l in f:
            if l.startswith(fichier):
                return int(l.split()[1]) + int(l.split()[2])
    return -1


def conformes(dossier):
    """Les Res_* du passage sont-ils identiques à ceux de references_A_v2 ?"""
    resultats = os.path.join(dossier, "Resultats_passe_bande")
    noms = [n for n in os.listdir(resultats) if n.startswith("Res_")]
    return bool(noms) and all(
        filecmp.cmp(os.path.join(resultats, n), os.path.join(REFERENCES, n), shallow=False)
        for n in noms)


def nouveau_nom(prefixe, extension):
    os.makedirs(SORTIES, exist_ok=True)
    return os.path.join(SORTIES, f"{prefixe}_{datetime.now():%Y%m%d_%H%M}.{extension}")


def sortie_commande(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
    except OSError:
        return "?"


def ecrire_conditions(chemin, args):
    import hashlib
    with open(A_ETOILE, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    lignes = [
        f"date : {datetime.now():%Y-%m-%d %H:%M}",
        f"commande : mesurer_A.py temps --essais {args.essais}"
        + (" --sans-echauffement" if args.sans_echauffement else "")
        + (" --batterie" if args.batterie else "")
        + (f" --fichiers {' '.join(args.fichiers)}" if args.fichiers else ""),
        f"machine : {sortie_commande(['sysctl', '-n', 'hw.model'])} / "
        f"{sortie_commande(['sysctl', '-n', 'machdep.cpu.brand_string'])} / "
        f"{int(sortie_commande(['sysctl', '-n', 'hw.memsize']) or 0) / 2**30:.0f} Go / "
        f"macOS {sortie_commande(['sw_vers', '-productVersion'])}",
        f"alimentation : {sortie_commande(['pmset', '-g', 'ps']).splitlines()[0]}, "
        f"mode économie d'énergie {'activé' if economie_energie() else 'désactivé'}",
        f"octave : {sortie_commande(['octave', '--version']).splitlines()[0]}",
        "threads : OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1",
        f"A* : sha256 {sha}",
        "temps d'un essai : ligne « Duree totale » de BilanTot.txt (tic/toc de A, sans démarrage d'Octave)",
        "cache disque : chaud",
    ]
    with open(chemin, "w", encoding="utf-8") as f:
        f.write("\n".join(lignes) + "\n")


def mesurer_temps(args):
    if economie_energie():
        sys.exit("Le mode économie d'énergie est activé : désactive-le avant de mesurer.")
    if not sur_secteur() and not args.batterie:
        sys.exit("Le Mac est sur batterie : branche-le, ou relance avec --batterie "
                 "(à condition de mesurer B et C de la même façon, protocole, section 7.2).")
    secteur_au_debut = sur_secteur()
    lignes = lire_manifeste()
    if args.fichiers:
        lignes = [l for l in lignes if l["fichier"] in args.fichiers]
    chemin = nouveau_nom("temps_A", "csv")
    ecrire_conditions(chemin[:-4] + ".txt", args)
    print(f"{len(lignes)} fichier(s), {0 if args.sans_echauffement else 1} échauffement + "
          f"{args.essais} essai(s) chacun. Ne te sers pas du Mac pendant la mesure.\n"
          f"Résultats : {chemin}")
    total_audio = total_calcul = 0.0
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["fichier", "strate", "duree_audio_s", "detections", "echauffement_s"]
                   + [f"essai{i + 1}_s" for i in range(args.essais)]
                   + ["mediane_s", "FTR", "sorties_conformes"])
        for l in lignes:
            with tempfile.TemporaryDirectory(prefix="temps_A_") as tmp:
                preparer(tmp, l["fichier"])
                echauffement = "" if args.sans_echauffement else f"{lancer(tmp):.3f}"
                essais = [lancer(tmp) for _ in range(args.essais)]
                mediane = statistics.median(essais)
                duree = float(l["duree_s"])
                ok = conformes(tmp)
                w.writerow([l["fichier"], l["strate"], f"{duree:.3f}", detections(tmp, l["fichier"]),
                            echauffement] + [f"{e:.3f}" for e in essais]
                           + [f"{mediane:.3f}", f"{duree / mediane:.2f}", "oui" if ok else "NON"])
                f.flush()
            total_audio += duree
            total_calcul += mediane
            print(f"  {l['fichier']:28s} médiane {mediane:7.2f} s   FTR {duree / mediane:6.1f}"
                  + ("" if ok else "   ATTENTION : sorties différentes des références"))
    print(f"\nJeu entier : {total_audio / 60:.1f} min d'audio, {total_calcul:.1f} s de calcul, "
          f"FTR {total_audio / total_calcul:.1f}")
    if sur_secteur() != secteur_au_debut:
        print("ATTENTION : l'alimentation a changé pendant la mesure.")


def profiler(args):
    if args.fichier not in {l["fichier"] for l in lire_manifeste()}:
        sys.exit(f"{args.fichier} n'est pas dans le manifeste.")
    nom = args.fichier[:-4]
    with tempfile.TemporaryDirectory(prefix="profil_A_") as tmp:
        preparer(tmp, args.fichier)
        lancer(tmp)                                   # échauffement (cache disque chaud)
        lancer(tmp, PROFIL_OCTAVE)
        etapes = nouveau_nom(f"profil_{nom}_etapes", "csv")
        shutil.copy2(os.path.join(tmp, "profil_etapes.csv"), etapes)
        shutil.copy2(os.path.join(tmp, "profil_fonctions.csv"),
                     etapes.replace("_etapes_", "_fonctions_"))
    with open(etapes, encoding="utf-8") as f:
        rangs = sorted(csv.DictReader(f, delimiter=";"),
                       key=lambda r: -float(r["temps_inclusif_s"]))
    duree = float(rangs.pop(0)["temps_inclusif_s"])   # la ligne TOTAL_A, la plus grande
    attribue = sum(float(r["temps_inclusif_s"]) for r in rangs)
    print(f"{args.fichier} sous profileur : {duree:.1f} s (plus lent que le vrai temps)\n")
    print(f"{'fonction appelée par A':24s} {'appels':>8s} {'temps (s)':>10s} {'part':>6s}")
    for r in rangs:
        t = float(r["temps_inclusif_s"])
        if t >= 0.005 * duree:
            print(f"{r['fonction']:24s} {int(r['appels']):8d} {t:10.2f} {100 * t / duree:5.1f}%")
    print(f"{'(code propre au script)':24s} {'':8s} {duree - attribue:10.2f} "
          f"{100 * (duree - attribue) / duree:5.1f}%")
    print(f"\nTableaux complets : {etapes}\n"
          f"                    {etapes.replace('_etapes_', '_fonctions_')}")


def compter_candidats(args):
    lignes = lire_manifeste()
    chemin = nouveau_nom("candidats_A", "csv")
    print(f"{len(lignes)} fichier(s), un passage sous profileur chacun.\nRésultats : {chemin}")
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["fichier", "strate", "detections", "candidats", "rejetes",
                    "appels_max", "temps_max_s", "temps_profil_s", "sorties_conformes"])
        for l in lignes:
            with tempfile.TemporaryDirectory(prefix="candidats_A_") as tmp:
                preparer(tmp, l["fichier"])
                lancer(tmp, PROFIL_OCTAVE)
                with open(os.path.join(tmp, "profil_etapes.csv"), encoding="utf-8") as g:
                    p = {r["fonction"]: r for r in csv.DictReader(g, delimiter=";")}
                det = detections(tmp, l["fichier"])
                acc = acceptes_par_canal(tmp, l["fichier"])
                ok = conformes(tmp)
            cand = int(p["fft"]["appels"]) if "fft" in p else 0
            w.writerow([l["fichier"], l["strate"], det, cand, cand - acc,
                        p["max"]["appels"], p["max"]["temps_inclusif_s"],
                        p["TOTAL_A"]["temps_inclusif_s"], "oui" if ok else "NON"])
            f.flush()
            print(f"  {l['fichier']:28s} {cand:6d} candidats, {det:6d} détections"
                  + ("" if ok else "   ATTENTION : sorties différentes des références"))


def main():
    p = argparse.ArgumentParser()
    sous = p.add_subparsers(dest="mode", required=True)
    t = sous.add_parser("temps", help="temps de calcul selon le protocole, section 7")
    t.add_argument("--fichiers", nargs="+", help="limiter à ces fichiers (noms du manifeste)")
    t.add_argument("--essais", type=int, default=ESSAIS, help="essais comptés par fichier")
    t.add_argument("--sans-echauffement", action="store_true",
                   help="pas d'échauffement (WAV déjà en cache)")
    t.add_argument("--batterie", action="store_true",
                   help="accepter la batterie (mode économie d'énergie désactivé)")
    t.set_defaults(action=mesurer_temps)
    pr = sous.add_parser("profil", help="un passage sous profile on")
    pr.add_argument("fichier", help="nom du WAV, par exemple 6209.260514052458.wav")
    pr.set_defaults(action=profiler)
    c = sous.add_parser("candidats", help="nombre de candidats par fichier (profileur)")
    c.set_defaults(action=compter_candidats)
    args = p.parse_args()
    args.action(args)


if __name__ == "__main__":
    main()
