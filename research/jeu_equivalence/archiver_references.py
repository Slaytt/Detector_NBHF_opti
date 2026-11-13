#!/usr/bin/env python3
"""Relance A* et archive ses sorties comme références d'équivalence (protocole, section 3).

Étapes :
  1. vérifie les WAV du jeu à partir des sha256 de manifeste.csv ;
  2. relance A* (run_bahia) dans un dossier temporaire, sans toucher à run_bahia/Resultats_passe_bande ;
  3. compare les deux passages octet par octet. Seule la ligne « Duree totale » de BilanTot.txt
     peut différer, puisque c'est un temps ;
  4. si tout est identique, copie le premier passage dans references_A/ (ou dans --sortie)
     et écrit VERSION.txt.

Le script refuse d'écraser une archive existante : une nouvelle référence va dans references_A_v2/.

Usage :
    python3 -I jeu_equivalence/archiver_references.py [--sortie references_A_v2]
"""
import argparse
import csv
import filecmp
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime

ICI = os.path.dirname(os.path.abspath(__file__))
RESEARCH = os.path.dirname(ICI)                     # research/
DOSSIER_A = os.path.dirname(RESEARCH)               # Detector_NBHF_opti
RACINE = os.path.dirname(os.path.dirname(DOSSIER_A))  # StageBioacousitc (inchangé : dépôt dans Detector_opti/)
A_ETOILE = os.path.join(RESEARCH, "run_bahia", "DetectorNBHF_todos_passe_bande.m")
A_ORIGINAL = os.path.join(DOSSIER_A, "ressources", "DetectorNBHF_todos_passe_bande.m")
PASSAGE_1 = os.path.join(RESEARCH, "run_bahia", "Resultats_passe_bande")
LISTE = os.path.join(ICI, "liste_fichiers_extrait.txt")
MANIFESTE = os.path.join(ICI, "manifeste.csv")


def sha256(chemin):
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 22), b""):
            h.update(bloc)
    return h.hexdigest()


def verifier_manifeste():
    with open(MANIFESTE, encoding="utf-8") as f:
        lignes = [l for l in csv.DictReader(f, delimiter=";") if l["statut"] == "present"]
    for l in lignes:
        chemin = os.path.join(ICI, "wav", l["fichier"])
        if sha256(chemin) != l["sha256"]:
            sys.exit(f"ÉCHEC : {l['fichier']} ne correspond plus au manifeste.")
    print(f"Manifeste : {len(lignes)} WAV conformes.")


def lancer_a_etoile(dossier):
    shutil.copy2(A_ETOILE, dossier)
    shutil.copy2(LISTE, dossier)
    os.mkdir(os.path.join(dossier, "Resultats_passe_bande"))
    debut = time.monotonic()
    with open(os.path.join(dossier, "octave.log"), "w") as log:
        r = subprocess.run(["octave", "--no-gui", os.path.basename(A_ETOILE)],
                           cwd=dossier, stdout=log, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        sys.exit(f"ÉCHEC : Octave a renvoyé {r.returncode}, voir {dossier}/octave.log")
    return time.monotonic() - debut


def bilan_sans_duree(chemin):
    with open(chemin, "rb") as f:
        return [l for l in f if not l.startswith(b"Duree totale")]


def comparer(d1, d2):
    noms1, noms2 = sorted(os.listdir(d1)), sorted(os.listdir(d2))
    if noms1 != noms2:
        return [f"listes de fichiers différentes : {set(noms1) ^ set(noms2)}"]
    ecarts = []
    for n in noms1:
        p1, p2 = os.path.join(d1, n), os.path.join(d2, n)
        if n == "BilanTot.txt":
            if bilan_sans_duree(p1) != bilan_sans_duree(p2):
                ecarts.append(n)
        elif not filecmp.cmp(p1, p2, shallow=False):
            ecarts.append(n)
    return ecarts


def sortie_commande(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
    except OSError:
        return "?"


def ecrire_version(dossier, duree_relance):
    octave = sortie_commande(["octave", "--no-gui", "--eval",
                              "pkg load signal; l = pkg('list', 'signal'); "
                              "printf('%s|%s', version, l{1}.version)"]).split("|")
    machine = [
        sortie_commande(["sysctl", "-n", "hw.model"]),
        sortie_commande(["sysctl", "-n", "machdep.cpu.brand_string"]),
        f"{int(sortie_commande(['sysctl', '-n', 'hw.memsize']) or 0) / 2**30:.0f} Go de RAM",
        f"macOS {platform.mac_ver()[0]}",
    ]
    with open(os.path.join(dossier, "BilanTot.txt"), encoding="utf-8", errors="replace") as f:
        duree_passage_1 = next((l.strip() for l in f if l.startswith("Duree totale")), "?")
    lignes = [
        "# Références d'équivalence : sorties de A*",
        f"date d'archivage : {datetime.now():%Y-%m-%d %H:%M}",
        f"Octave : {octave[0]}   paquet signal : {octave[-1]}",
        f"machine : {' / '.join(machine)}",
        "",
        f"A* : {os.path.relpath(A_ETOILE, RACINE)}",
        f"  sha256 {sha256(A_ETOILE)}",
        f"A d'origine : {os.path.relpath(A_ORIGINAL, RACINE)}",
        f"  sha256 {sha256(A_ORIGINAL)}",
        f"manifeste.csv : sha256 {sha256(MANIFESTE)}",
        "",
        "Filtre : si fcut_high >= fm/2, passe-haut Butterworth d'ordre 5 à fcut_low = 100 kHz",
        "(Bahía, 288 kHz) ; sinon, passe-bande 100–180 kHz d'origine (FitzRoy, 512 kHz).",
        "Coefficients exacts : coefs_filtre_<fm>.txt.",
        "Attention : l'en-tête de BilanTot.txt affiche toujours « frequence coupure haute 180000 »,",
        "car il est écrit avant la lecture du premier fichier. Il ne décrit donc pas le filtre réellement",
        "appliqué à Bahía.",
        "",
        "Déterminisme : vérifié par une relance complète, dont les sorties sont identiques à l'octet près",
        "(hors ligne « Duree totale » de BilanTot.txt).",
        f"Durée du passage archivé (tic/toc de A) : {duree_passage_1}",
        f"Durée de la relance de contrôle (avec démarrage d'Octave) : {duree_relance:.1f} s",
        "Ces durées ne sont pas des mesures de temps au sens du protocole (section 7).",
        "",
        "# sha256 des sorties",
    ]
    for n in sorted(os.listdir(dossier)):
        if n != "VERSION.txt":
            lignes.append(f"{sha256(os.path.join(dossier, n))}  {n}")
    with open(os.path.join(dossier, "VERSION.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lignes) + "\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sortie", default="references_A", help="dossier d'archive, dans jeu_equivalence/")
    args = p.parse_args()
    archive = os.path.join(ICI, args.sortie)
    if os.path.exists(archive):
        sys.exit(f"{archive} existe déjà : choisis une autre --sortie (par exemple references_A_v2).")
    with open(LISTE, "rb") as f1, open(os.path.join(RESEARCH, "run_bahia", "liste_fichiers_extrait.txt"), "rb") as f2:
        if f1.read() != f2.read():
            sys.exit("La liste de run_bahia ne correspond pas à jeu_equivalence/liste_fichiers_extrait.txt.")

    verifier_manifeste()
    with tempfile.TemporaryDirectory(prefix="relance_A_") as tmp:
        print("Relance de A* (environ 7 min)…")
        duree = lancer_a_etoile(tmp)
        ecarts = comparer(PASSAGE_1, os.path.join(tmp, "Resultats_passe_bande"))
        if ecarts:
            garde = os.path.join(ICI, "relance_divergente")
            shutil.copytree(tmp, garde, dirs_exist_ok=True)
            sys.exit(f"ÉCHEC : sorties différentes entre les deux passages : {ecarts}\n"
                     f"Relance conservée dans {garde}. Ne pas archiver avant d'avoir compris pourquoi.")
    print(f"Relance identique au premier passage ({duree:.0f} s).")
    shutil.copytree(PASSAGE_1, archive)
    ecrire_version(archive, duree)
    print(f"Archivé dans {archive}")


if __name__ == "__main__":
    main()
