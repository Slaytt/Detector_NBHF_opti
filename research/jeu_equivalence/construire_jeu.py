#!/usr/bin/env python3
"""Construit le jeu d'équivalence A / B / C (étape 1 de la roadmap).

Les règles de choix sont décrites dans PROTOCOLE_EQUIVALENCE.md, section 2.
Elles sont appliquées ici telles quelles : ne pas modifier ce script après
avoir vu des écarts entre versions (sinon le jeu n'est plus choisi à l'aveugle).

Usage :
    python3 construire_jeu.py                      # fichiers disponibles en local
    python3 construire_jeu.py --disque "/Volumes/TOSHIBA EXT/bahia 2026/6209"
                                                   # ajoute le fichier tronqué

Sortie (dans le dossier du script) :
    wav/                       les WAV, en liens physiques (aucun espace disque en plus)
    liste_fichiers_extrait.txt l'entrée attendue par A (un nom par ligne)
    manifeste.csv              un fichier par ligne : rôle, strate, format, sha256
"""
import argparse
import csv
import hashlib
import os
import random
import shutil
import wave

GRAINE = 20261024
PAR_STRATE = 2
SESSION_BLOC = "bahia_muelle_2026_3"   # 12 fichiers consécutifs = 1 h, session entière
TRONQUE = "6209.260520182507.wav"

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(os.path.dirname(os.path.dirname(ICI)))   # StageBioacousitc
DEV = os.path.join(RACINE, "selection_tests_detecteur")
TEST_FIGE = os.path.join(RACINE, "test_cld", "jeu_test_fige")
FITZROY = os.path.join(RACINE, "StageTeo (1).zip", "FichierTest_FitzRoy.wav")


def lire_index():
    with open(os.path.join(DEV, "index_selection.csv"), encoding="utf-8-sig") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))
    for l in lignes:
        l["niveau"] = float(l["niveau_110_140kHz_dB"])
        l["ecrete"] = float(l["pct_ecrete"])
        l["nbhf"] = int(l["transitoires_NBHF_10s"])
        l["n_sel"] = int(l["n_selections"])
        l["chemin"] = os.path.join(DEV, l["categorie"], l["fichier"])
    return lignes


def strates(index):
    """Cinq strates disjointes, définies uniquement par les indicateurs de bruit."""
    sature = [l for l in index if l["ecrete"] > 0]
    actif = [l for l in index if l["ecrete"] == 0 and l["nbhf"] > 0]
    reste = sorted((l for l in index if l["ecrete"] == 0 and l["nbhf"] == 0),
                   key=lambda l: (l["niveau"], l["fichier"]))
    n = len(reste)
    return {
        "sature": sature,
        "actif_nbhf": actif,
        "calme_niveau_bas": reste[: n // 3],
        "calme_niveau_moyen": reste[n // 3: 2 * n // 3],
        "calme_niveau_haut": reste[2 * n // 3:],
    }


def tirer(index):
    rng = random.Random(GRAINE)
    choix = []
    for nom, membres in strates(index).items():
        membres = sorted(membres, key=lambda l: l["fichier"])
        for l in rng.sample(membres, min(PAR_STRATE, len(membres))):
            choix.append((l["chemin"], "tirage", nom))
    dense = max(index, key=lambda l: l["n_sel"])
    if dense["chemin"] not in {c for c, _, _ in choix}:
        choix.append((dense["chemin"], "impose", "plus_dense_raven"))
    return choix


def bloc_une_heure():
    """La session 3 du jeu de test figé : 1 h continue, déjà sur le disque interne.
    On ne regarde ni ses annotations Raven ni ses erreurs (voir le protocole, section 2.1)."""
    with open(os.path.join(TEST_FIGE, "liste_fichiers_test.csv"), encoding="utf-8-sig") as f:
        noms = sorted(l["fichier"] for l in csv.DictReader(f, delimiter=";")
                      if l["session"] == SESSION_BLOC)
    return [(os.path.join(TEST_FIGE, "wav", n), "impose", "bloc_une_heure") for n in noms]


def decrire(chemin):
    with wave.open(chemin, "rb") as w:
        fm, canaux, n = w.getframerate(), w.getnchannels(), w.getnframes()
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 22), b""):
            h.update(bloc)
    return fm, canaux, n / fm, os.path.getsize(chemin), h.hexdigest()


def lier(source, dossier):
    cible = os.path.join(dossier, os.path.basename(source))
    if not os.path.exists(cible):
        try:
            os.link(source, cible)
        except OSError:          # disque externe : lien physique impossible, on copie
            shutil.copy2(source, cible)
    return cible


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--disque", help="dossier des WAV Bahía sur le disque TOSHIBA")
    args = p.parse_args()

    choix = tirer(lire_index())
    choix.append((FITZROY, "impose", "stereo_512kHz"))
    choix += bloc_une_heure()
    en_attente = []
    if args.disque:
        choix.append((os.path.join(args.disque, TRONQUE), "impose", "tronque_180s"))
    else:
        en_attente = [(TRONQUE, "impose", "tronque_180s")]

    dossier_wav = os.path.join(ICI, "wav")
    os.makedirs(dossier_wav, exist_ok=True)
    lignes = []
    for source, role, strate in choix:
        cible = lier(source, dossier_wav)
        fm, canaux, duree, octets, sha = decrire(cible)
        lignes.append([os.path.basename(cible), role, strate, "present", fm, canaux,
                       f"{duree:.3f}", octets, sha, os.path.relpath(source, RACINE)])
        print(f"{strate:20s} {os.path.basename(cible)}  {fm} Hz  {canaux} can.  {duree:.1f} s")
    for nom, role, strate in en_attente:
        lignes.append([nom, role, strate, "en_attente_disque", "", "", "", "", "", ""])
        print(f"{strate:20s} {nom}  (en attente du disque TOSHIBA)")

    with open(os.path.join(ICI, "manifeste.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["fichier", "role", "strate", "statut", "fm_Hz", "canaux", "duree_s",
                    "octets", "sha256", "source"])
        w.writerows(lignes)
    with open(os.path.join(ICI, "liste_fichiers_extrait.txt"), "w") as f:
        f.writelines(l[0] + "\n" for l in lignes if l[3] == "present")
    total = sum(float(l[6]) for l in lignes if l[3] == "present")
    print(f"\n{sum(l[3] == 'present' for l in lignes)} fichiers, {total / 60:.1f} min d'audio, "
          f"{len(en_attente)} élément(s) en attente.")


if __name__ == "__main__":
    main()
