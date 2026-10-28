"""Point de controle de l'etape 1 : lecture d'un morceau, comparee a A*.

Outillage de verification ecrit par Claude (Anthropic) ; ce n'est pas du code du portage.

Reference : verif_octave/sorties/{infos,bornes}.csv, produits par
    octave --no-gui verif_octave/exporter_bornes.m

Critere : egalite EXACTE (difference max = 0) des bornes et des echantillons.

Interface attendue de nbhf.lecture (a adapter si tu choisis d'autres noms) :
    lire_infos(chemin)                         -> objet avec .fm, .tamano_total, .nb_canales
    nombre_morceaux(tamano_total, fm, t_trozo) -> N
    bornes_morceau(i, t_trozo, fm, tamano_total) -> (inicio, fin)
        i commence a 1 comme dans A ; inicio et fin sont les bornes Octave
        (commencent a 1, fin incluse), donc directement comparables a audioread.
    lire_morceau(chemin, inicio, fin)          -> ndarray float64 de forme (n, nb_canales),
        comme `extrait` dans A
"""

import csv
from pathlib import Path

import numpy as np
import pytest

from nbhf.lecture import bornes_morceau, lire_infos, lire_morceau, nombre_morceaux

T_TROZO = 29.99  # identique a A*

ICI = Path(__file__).resolve().parent
DOSSIER_WAV = ICI.parent.parent / "jeu_equivalence" / "wav"
DOSSIER_REF = ICI.parent / "verif_octave" / "sorties"

if not (DOSSIER_REF / "bornes.csv").exists():
    pytest.skip(
        "reference absente : lancer `octave --no-gui verif_octave/exporter_bornes.m`",
        allow_module_level=True,
    )


def _lire_csv(nom):
    with open(DOSSIER_REF / nom, newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


INFOS = {ligne["fichier"]: ligne for ligne in _lire_csv("infos.csv")}

BORNES = {}  # fichier -> liste des lignes (un morceau x un canal)
for ligne in _lire_csv("bornes.csv"):
    BORNES.setdefault(ligne["fichier"], []).append(ligne)

FICHIERS = sorted(INFOS)


@pytest.mark.parametrize("fichier", FICHIERS)
def test_infos(fichier):
    ref = INFOS[fichier]
    infos = lire_infos(DOSSIER_WAV / fichier)
    assert infos.fm == int(ref["fm"])
    assert infos.tamano_total == int(ref["tamano_total"])
    assert infos.nb_canales == int(ref["nbCanales"])
    assert nombre_morceaux(infos.tamano_total, infos.fm, T_TROZO) == int(ref["N"])


@pytest.mark.parametrize("fichier", FICHIERS)
def test_bornes(fichier):
    ref = INFOS[fichier]
    fm, tamano_total = int(ref["fm"]), int(ref["tamano_total"])
    attendu = {(int(l["i"]), int(l["inicio"]), int(l["fin"])) for l in BORNES[fichier]}
    obtenu = {(i, *bornes_morceau(i, T_TROZO, fm, tamano_total)) for i, _, _ in attendu}
    assert obtenu == attendu


@pytest.mark.parametrize("fichier", FICHIERS)
def test_echantillons(fichier):
    chemin = DOSSIER_WAV / fichier
    morceaux = {}
    for ref in BORNES[fichier]:
        inicio, fin = int(ref["inicio"]), int(ref["fin"])
        if (inicio, fin) not in morceaux:
            morceaux = {(inicio, fin): lire_morceau(chemin, inicio, fin)}
        extrait = morceaux[(inicio, fin)]
        x = extrait[:, int(ref["canal"]) - 1]
        n = int(ref["n"])
        contexte = f"morceau {ref['i']}, canal {ref['canal']}"

        assert extrait.dtype == np.float64, contexte
        assert len(x) == n, contexte
        assert x.sum() == float(ref["somme"]), contexte
        assert np.abs(x).sum() == float(ref["somme_abs"]), contexte
        assert x.min() == float(ref["minimum"]), contexte
        assert x.max() == float(ref["maximum"]), contexte
        bouts = [x[0], x[1], x[2], x[n - 3], x[n - 2], x[n - 1]]
        bouts_ref = [float(ref[c]) for c in ("x1", "x2", "x3", "xn_2", "xn_1", "xn")]
        assert bouts == bouts_ref, contexte
