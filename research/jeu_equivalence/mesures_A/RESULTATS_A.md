# Mesures de A* : journal des résultats (étape 2)

Machine : MacBookPro18,1, Apple M1 Pro, 16 Go, macOS 26.5.2. Octave 11.3.0, signal 1.4.8.
A* : `run_bahia/DetectorNBHF_todos_passe_bande.m`, sha256 d795e40c…90d9 jusqu'au 26/10 à 13:50,
puis c61369ce…fa93. Seul changement : `Camino` (ligne 43) suit le déplacement de `jeu_equivalence/`
dans le dépôt `Detector_NBHF_opti/`. Les 24 sorties de la version corrigée sont identiques à
`references_A_v2/` (vérifié le 26/10 à 13:55, section 4).
Jeu : manifeste v2, 24 fichiers, 118,7 min d'audio.
FTR = durée audio / temps de calcul (plus grand = mieux).

## 1. Passages complets du jeu (26/10/2026)

| Passage | Heure | Durée | FTR | Alimentation | Threads |
|---|---|---|---|---|---|
| Premier passage (référence archivée) | fin à 11:59 | 645,1 s (tic/toc de A) | 11,0 | **batterie** | non fixés |
| Relance de contrôle (`archiver_references.py`) | 11:59 → 12:10 | 643,5 s (avec démarrage d'Octave) | 11,1 | **batterie** | non fixés |

- Sorties identiques à l'octet près : A* est déterministe. Archive : `references_A_v2/`.
- Les deux durées concordent à 0,3 % : la variabilité d'un passage à l'autre est faible.
  C'est ce qui justifie un seul essai par fichier pour A (protocole, §7.2).
- Ces deux passages ne respectent pas les conditions du §7 (batterie, threads non fixés) :
  ils ne sont pas le temps officiel de A.

## 2. Profils (`mesurer_A.py profil`, 26/10/2026, sur batterie)

Temps sous profileur : seules les proportions comptent.

| | 052458 (calme) | 035958 (chargé) |
|---|---|---|
| Temps total sous profileur | 2,5 s | 58,9 s |
| Candidats examinés (appels de `fft`) | 26 | 2 516 |
| Détections gardées | 21 | 2 374 |
| `max` | 0,69 s (27,1 %) | 55,31 s (**93,9 %**) |
| `audioread` | 0,76 s (30,1 %) | 1,45 s (2,5 %) |
| `filter` | 0,61 s (24,2 %) | 0,61 s (1,0 %) |
| `std` | 0,32 s (12,6 %) | 0,47 s (0,8 %) |
| `fft` + `abs` + `mean` | 0,01 s | 0,56 s (1,0 %) |
| Code propre au script | 0,04 s | 0,34 s (0,6 %) |

Lecture :
- Chaque candidat coûte deux parcours complets d'un morceau de 8,6 M d'échantillons
  (condition du `while` et `[x, ix] = max(...)`), environ 11 ms chacun.
- **Temps de A ≈ 2 s + 22 ms × nombre de candidats** par fichier de 5 min.
  Le coût suit le nombre de candidats, pas la durée de l'audio.
- Le test spectral (`fft`) est négligeable. C doit d'abord supprimer les parcours répétés de `max`.
- Sur le fichier calme, lecture, filtre et `std` font environ 67 % : ce sera le plancher une fois `max` réglé.

Tableaux complets : `profil_<fichier>_etapes_*.csv` (appels directs de A, temps inclusifs) et
`profil_<fichier>_fonctions_*.csv` (toutes les fonctions, temps propres).

## 3. Temps officiel par fichier (§7), 26/10/2026 à 13:24

Commande : `mesurer_A.py temps --essais 1 --sans-echauffement --batterie`.
Conditions : **batterie**, mode économie d'énergie désactivé, threads fixés à 1, cache chaud
(détail dans `temps_A_20261026_1324.txt`). B et C devront être mesurés sur batterie aussi.
Les 24 sorties sont identiques à `references_A_v2/`.

**Jeu entier : 118,7 min d'audio, 654,5 s de calcul, FTR = 10,9.**
(Les deux passages du matin, threads non fixés : 645,1 s et 643,5 s. L'écart de 1,5 % est de l'ordre
du bruit de mesure ; fixer les threads n'a pas d'effet visible sur A.)

| Fichier | Strate | Détections | Temps (s) | FTR |
|---|---|---|---|---|
| 260522003008 | sature | 1 240 | 44,48 | 6,7 |
| 260521112008 | sature | 1 295 | 48,11 | 6,2 |
| 260523223511 | actif_nbhf | 468 | 13,30 | 22,6 |
| 260514035958 | actif_nbhf | 2 374 | 59,12 | 5,1 |
| 260520021506 | calme_niveau_bas | 1 758 | 54,43 | 5,5 |
| 260514142459 | calme_niveau_bas | 381 | 20,49 | 14,6 |
| 260514080459 | calme_niveau_moyen | 914 | 41,53 | 7,2 |
| 260521110008 | calme_niveau_moyen | 1 133 | 54,99 | 5,5 |
| 260514052458 | calme_niveau_haut | 21 | 2,64 | 113,4 |
| 260521181508 | calme_niveau_haut | 88 | 4,92 | 61,0 |
| 260514082959 | plus_dense_raven | 1 325 | 47,98 | 6,3 |
| FitzRoy (stéréo, 219 s) | stereo_512kHz | 377 | 25,96 | 8,4 |
| 260514070459 | bloc_une_heure | 32 | 3,24 | 92,7 |
| 260514070959 | bloc_une_heure | 32 | 4,12 | 72,9 |
| 260514071459 | bloc_une_heure | 19 | 3,58 | 83,9 |
| 260514071959 | bloc_une_heure | 44 | 3,86 | 77,6 |
| 260514072459 | bloc_une_heure | 81 | 6,60 | 45,5 |
| 260514072959 | bloc_une_heure | 70 | 5,05 | 59,4 |
| 260514073459 | bloc_une_heure | 127 | 8,13 | 36,9 |
| 260514073959 | bloc_une_heure | 468 | 24,57 | 12,2 |
| 260514074459 | bloc_une_heure | 728 | 36,15 | 8,3 |
| 260514074959 | bloc_une_heure | 819 | 39,88 | 7,5 |
| 260514075459 | bloc_une_heure | 1 273 | 52,10 | 5,8 |
| 260514075959 | bloc_une_heure | 1 063 | 49,23 | 6,1 |

Lecture :
- Le FTR va de **5,1 à 113** selon le fichier, pour la même durée d'audio : il dépend du nombre de
  candidats, pas de la durée. Un FTR global n'a de sens qu'avec la composition du jeu.
- Le bloc d'une heure (07:04 → 08:04) le montre en continu : FTR de 73 à 93 en début d’heure,
  puis de 6 quand une activité NBHF (rencontre ou bruit) commence vers 07:40.
- Ajustement temps / détections sur les 23 fichiers Bahía : temps ≈ 6,4 s + 30,5 ms × détections,
  R² = 0,89. L'ajustement est imparfait parce que les détections ne comptent pas les candidats
  rejetés : 260521110008 (1 133 détections, 55 s) en a sans doute beaucoup. La loi du profil
  (2 s + 22 ms × **candidats**) reste la bonne description ; le nombre de candidats n'est connu
  que pour les deux fichiers profilés.

## 4. Temps en fonction du nombre de candidats, 26/10/2026 à 13:55

Commande : `mesurer_A.py candidats` (un passage sous profileur par fichier, batterie, A* c61369ce).
Résultats : `candidats_A_20261026_1355.csv`. Les 24 sorties sont identiques aux références.
(`candidats_A_20261026_1345.csv` est un passage interrompu après 6 fichiers par le déplacement du
dossier ; ses 6 valeurs sont identiques à celles du passage complet.)

Candidat = un tour du `while` (un appel de `fft`), accepté ou rejeté par le test spectral.

| Fichier | Strate | Candidats | Détections | Rejetés | Temps officiel (s) | Part de `max` |
|---|---|---|---|---|---|---|
| 260522003008 | sature | 1 877 | 1 240 | 637 (34 %) | 44,48 | 93 % |
| 260521112008 | sature | 2 023 | 1 295 | 728 (36 %) | 48,11 | 94 % |
| 260523223511 | actif_nbhf | 506 | 468 | 38 (8 %) | 13,30 | 83 % |
| 260514035958 | actif_nbhf | 2 516 | 2 374 | 142 (6 %) | 59,12 | 95 % |
| 260520021506 | calme_niveau_bas | 2 298 | 1 758 | 540 (23 %) | 54,43 | 94 % |
| 260514142459 | calme_niveau_bas | 828 | 381 | 447 (54 %) | 20,50 | 89 % |
| 260514080459 | calme_niveau_moyen | 1 710 | 914 | 796 (47 %) | 41,53 | 93 % |
| 260521110008 | calme_niveau_moyen | 2 380 | 1 133 | 1 247 (52 %) | 54,99 | 94 % |
| 260514052458 | calme_niveau_haut | 26 | 21 | 5 (19 %) | 2,65 | 26 % |
| 260521181508 | calme_niveau_haut | 131 | 88 | 43 (33 %) | 4,92 | 61 % |
| 260514082959 | plus_dense_raven | 2 067 | 1 325 | 742 (36 %) | 47,98 | 94 % |
| FitzRoy (2 canaux) | stereo_512kHz | 741 | 377 (616 avant fusion) | 125 (17 %) | 25,96 | 73 % |
| 260514070459 | bloc_une_heure | 60 | 32 | 28 (47 %) | 3,23 | 43 % |
| 260514070959 | bloc_une_heure | 98 | 32 | 66 (67 %) | 4,12 | 54 % |
| 260514071459 | bloc_une_heure | 77 | 19 | 58 (75 %) | 3,58 | 49 % |
| 260514071959 | bloc_une_heure | 88 | 44 | 44 (50 %) | 3,86 | 52 % |
| 260514072459 | bloc_une_heure | 213 | 81 | 132 (62 %) | 6,60 | 71 % |
| 260514072959 | bloc_une_heure | 141 | 70 | 71 (50 %) | 5,05 | 63 % |
| 260514073459 | bloc_une_heure | 282 | 127 | 155 (55 %) | 8,13 | 76 % |
| 260514073959 | bloc_une_heure | 1 017 | 468 | 549 (54 %) | 24,57 | 90 % |
| 260514074459 | bloc_une_heure | 1 529 | 728 | 801 (52 %) | 36,15 | 93 % |
| 260514074959 | bloc_une_heure | 1 723 | 819 | 904 (52 %) | 39,88 | 94 % |
| 260514075459 | bloc_une_heure | 2 285 | 1 273 | 1 012 (44 %) | 52,10 | 94 % |
| 260514075959 | bloc_une_heure | 2 141 | 1 063 | 1 078 (50 %) | 49,23 | 93 % |

Ajustement linéaire du temps officiel sur les 23 fichiers Bahía (5 min, 288 kHz) :

| Variable | Loi | R² | Écart max |
|---|---|---|---|
| Détections | 6,43 s + 30,5 ms × détections | 0,886 | 19,7 s |
| **Candidats** | **1,89 s + 22,5 ms × candidats** | **0,9994** | **1,2 s** |

Lecture :
- **Le temps de A est entièrement expliqué par le nombre de candidats.** 1,9 s de coût fixe par
  fichier (lecture, filtre, `std`), puis 22,5 ms par candidat, soit deux parcours de `max` sur un
  morceau de 8,6 M d'échantillons.
- Les candidats rejetés coûtent autant que les acceptés. Ils représentent souvent **la moitié** des
  candidats, jusqu'à 75 % : c'est pour ça que les détections expliquaient mal le temps.
- FitzRoy sort de la loi (26 s mesurés, 18,6 s prédits) : à 512 kHz, un morceau compte 15,4 M
  d'échantillons, et les deux canaux ont chacun leur filtre et leur `while`. La loi est propre à
  Bahía (288 kHz, mono).
- Le temps sous profileur est à moins de 4 % du temps officiel (sauf FitzRoy, + 4 %) : le profileur
  ralentit très peu A, qui fait peu d'appels de fonctions.
- Pour C : le critère de réussite peut être formulé directement sur cette loi. Le coût par candidat
  (22,5 ms) doit devenir négligeable devant le coût fixe.
