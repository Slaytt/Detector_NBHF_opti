# Protocole d'équivalence A / B / C

*Étape 1 de la roadmap. Rédigé le 24/10/2026, **avant** l'écriture de B. Ce document fixe d'avance le jeu de fichiers, le critère d'équivalence et la mesure du temps.*

Ce protocole répond à une seule question : **B et C produisent-ils les mêmes détections que A, et en combien de temps ?** Il ne mesure pas la qualité du détecteur, qui se juge par rapport à Raven et relève de `test_cld/outils_evaluation/PROTOCOLE.md`. Ici, **la référence est la sortie de A**. Les annotations Raven ne servent à rien.

## 0. Place dans le stage

| | Ce qui change | Ce qui doit rester identique | Référence | Jeu |
|---|---|---|---|---|
| **A → B** | le langage (traduction ligne à ligne) | les détections, ordre compris | A | jeu d'équivalence (ce document) |
| **B → C** | l'implémentation : *comment* on calcule (structures de données, vectorisation, lecture) | les détections | A et B | jeu d'équivalence (ce document) |
| **C → étape 7** | l'algorithme : *ce que* l'on calcule (seuils, filtre, fusion…) | rien, on cherche à faire mieux | Raven | développement, puis test figé |

- **C n'est pas un nouvel algorithme.** Toute optimisation qui change une détection (hors écarts expliqués au §5) est un bug de C. Un changement voulu du comportement va à l'étape 7.
- **Pourquoi pas de séparation développement / test ici ?** On ne règle aucun paramètre sur ce jeu : un écart à A se corrige, il ne s'optimise pas. Il n'y a donc pas de surapprentissage possible, et on peut examiner ces fichiers autant qu'il le faut. La séparation redevient obligatoire à l'étape 7, quand on compare à Raven.
- **Ce que chaque étape produit avec ce protocole :**
  1. **Étape 1 (ce document)** : le jeu figé, les règles, les catégories d'écarts. Rien n'est encore mesuré.
  2. **Étape 2, mesurer A** : `references_A/`, le temps de A sur tout le jeu, le profilage d'un fichier calme et d'un fichier dense (temps par étape et temps en fonction du nombre d'itérations du `while`). En parallèle, et hors de ce protocole, la base de qualité de A\* sur le jeu de test figé, lancée **une seule fois**.
  3. **Étape 3, B** : la comparaison automatique à A après chaque modification. On commence par FitzRoy, puis on passe à tout le jeu. On remplit `ecarts.csv` et on vérifie la couverture (§6).
  4. **Étape 4, C** : la même comparaison, contre A et contre B. Les temps sont mesurés selon le §7 dès qu'une optimisation est en place, pour voir le gain de chacune.
  5. **Étape 5, validation** : un second jeu tiré selon les mêmes règles avec une autre graine (équivalence hors du jeu de travail), et la mesure finale des temps de A, B et C.

---

## 1. La référence : A\*

A (`ressources/DetectorNBHF_todos_passe_bande.m`) n'est jamais modifié. La sortie de référence vient d'une **copie** appelée A\*. Seules les modifications suivantes y sont permises, et chacune doit être listée en tête du fichier :

| Modification | Raison | Effet sur les détections |
|---|---|---|
| `Camino` pointe vers `jeu_equivalence/wav/` | chemin codé en dur | aucun |
| `NombreArchivo{k}(1:end-4)` au lieu de `(1:25)` | plante sur les noms de moins de 25 caractères (FitzRoy, `6209.*.wav`) | aucun |
| si `fcut_high ≥ fm/2` : passe-haut à `fcut_low` (ligne 107 de A) au lieu du passe-bande | `butter` plante à 288 kHz | **oui**, sur Bahía seulement |

> [!warning] `fcut_high` à 288 kHz : décision provisoire du 24/10/2026
> Vérifié avec Octave 11.3.0 et `signal` 1.4.8 : `butter(5, [100000 180000]/(288000/2))` s'arrête sur l'erreur `all elements of Wc must be in the range [0,1]`. A tel quel ne tourne sur **aucun** fichier Bahía, seulement sur FitzRoy (512 kHz). Aucune sortie de A sur Bahía n'a été trouvée sur le Mac. Le disque TOSHIBA reste à fouiller (`BilanTot.txt` contient `fcut_high`).
> **Choix provisoire : un passe-haut Butterworth d'ordre 5 à 100 kHz**, `butter(5, fcut_low/(fm/2), 'high')`, la ligne 107 de A (en commentaire). Les raisons :
> - c'est le filtre décrit pour les Franciscanas dans Malige et al. 2026 (*« all files are high pass filtered (100 kHz) »*) ;
> - on décommente du code de A, on n'invente pas de paramètre ;
> - à 288 kHz, un passe-bande 100–180 kHz revient à garder tout ce qui est au-dessus de 100 kHz : c'est exactement un passe-haut ;
> - il est bien conditionné (pôles de module 0,772). Un `fcut_high` placé juste sous la fréquence de Nyquist ne le serait pas ;
> - il ne coupe pas le haut des clics de Franciscana (pic vers 130–140 kHz, fréquence de Nyquist à 144 kHz), contrairement à un passe-bande 100–140 kHz.
>
> À faire confirmer par l'encadrant. Ce choix est **sans effet sur l'équivalence** : A\*, B et C appliquent la même règle. Il compte pour la base de qualité par rapport à Raven et pour l'étape 7. Si la valeur change, on produit `references_A_v2/` et on relance.

A\* applique donc une règle conditionnelle, et B et C appliquent exactement la même :
- si `fm/2 > fcut_high` (FitzRoy, 512 kHz), on garde le passe-bande 100–180 kHz d'origine, et la référence est bien A lui-même sur ce fichier ;
- sinon (Bahía, 288 kHz), on utilise le passe-haut à 100 kHz.

> [!note] Coefficients du filtre
> Pour le passe-haut à 288 kHz, Octave et scipy donnent des coefficients `a` qui diffèrent **d'un bit** (`a(2)` = 1,9206579378648254 contre 1,9206579378648256). Pour viser une tolérance de 0 échantillon sur B, la solution la plus sûre est que B **lise les coefficients exportés par Octave** (`%.17g`) au lieu de rappeler `scipy.signal.butter`. On garde l'appel à `butter` comme variante, pour mesurer l'effet de ce bit sur les détections.

La copie de A\* est figée à son tour, avec son sha256, une fois les références produites.

---

## 2. Le jeu de fichiers

### 2.1 Règles de choix (fixées avant tout résultat)

Toutes ces règles sont codées dans `construire_jeu.py`, avec la graine `20261024`. Le script **ne doit plus être modifié** une fois qu'un écart entre deux versions a été observé.

**Le tirage stratifié** se fait parmi les 30 fichiers de `selection_tests_detecteur/`, à partir des indicateurs de `index_selection.csv` (calculés sur les 10 s entre t = 140 s et t = 150 s). Les 5 strates sont disjointes :

| Strate | Définition | Chemin du code visé |
|---|---|---|
| `sature` | `pct_ecrete > 0` | beaucoup de candidats rejetés, seuil gonflé |
| `actif_nbhf` | pas d'écrêtage, `transitoires_NBHF_10s > 0` | beaucoup de candidats acceptés |
| `calme_niveau_bas` / `moyen` / `haut` | les autres, réparties en tertiles de `niveau_110_140kHz_dB` | coût fixe (lecture et filtrage), peu de candidats |

On tire 2 fichiers par strate.

**Les fichiers imposés :**

| Rôle | Fichier | Ce qu'il couvre |
|---|---|---|
| `plus_dense_raven` | celui qui a le plus de sélections Raven (`6209.260514082959`, 70 sélections) | le pire cas pour le temps. Raven sert ici à **choisir** le fichier, jamais à juger l'équivalence. |
| `stereo_512kHz` | `FichierTest_FitzRoy.wav` (2 canaux, 512 kHz, 219 s) | canal 2, fusion, autre `fm`, dernier morceau de 9,1 s |
| `tronque_180s` | `6209.260520182507.wav` (180 s) | fichier tronqué, nom de 21 caractères |
| `bloc_une_heure` | la session `bahia_muelle_2026_3` du jeu de test figé (de 070459 à 075959) : 12 fichiers consécutifs, 1 h, session entière, déjà sur le disque interne | échelle réaliste, régularité du temps de calcul |

Le recouvrement avec le jeu de développement est permis : on n'y règle rien, donc rien ne peut être surappris.

Le bloc d'une heure vient du **jeu de test figé**. On l'accepte parce que l'équivalence ne règle rien. Une règle s'applique toutefois : pour ces 12 fichiers, on compare seulement A, B et C entre eux. **On n'ouvre ni leurs annotations Raven ni les erreurs de détection**, puisque la session 3 sert aussi à la mesure finale de l'étape 7. C'est une limite à mentionner dans le rapport.

### 2.2 Le jeu obtenu (version 1)

| Strate | Fichier |
|---|---|
| sature | 6209.260522003008, 6209.260521112008 |
| actif_nbhf | 6209.260523223511, 6209.260514035958 |
| calme_niveau_bas | 6209.260520021506, 6209.260514142459 |
| calme_niveau_moyen | 6209.260514080459, 6209.260521110008 |
| calme_niveau_haut | 6209.260514052458, 6209.260521181508 |
| plus_dense_raven | 6209.260514082959 |
| stereo_512kHz | FichierTest_FitzRoy |
| bloc_une_heure | 6209.260514070459 à 6209.260514075959 (12 fichiers) |
| **en attente du disque TOSHIBA** | 6209.260520182507 |

Au total : 24 fichiers et 118,7 min d'audio, puis 25 fichiers quand le disque sera branché (version 2 du manifeste, le 26/10/2026). La version 1 (12 fichiers) correspond à `references_A/`. Pour ajouter le fichier tronqué :

    python3 jeu_equivalence/construire_jeu.py --disque "/Volumes/TOSHIBA EXT/bahia 2026/6209"

### 2.3 Gel du jeu
- `manifeste.csv` donne, pour chaque fichier, son rôle, sa strate, `fm`, le nombre de canaux, la durée et le **sha256**. Avant chaque campagne de mesure, on recalcule les sha256 et on les compare au manifeste.
- `wav/` contient des liens physiques vers les originaux. Ils ne prennent pas de place, et le fichier reste présent même si l'original est déplacé.
- Si un fichier est ajouté, il faut une nouvelle version du manifeste, avec sa justification **écrite avant** de lancer les versions.

---

## 3. Production des sorties de référence

1. Lancer A\* une fois sur `liste_fichiers_extrait.txt`, depuis `jeu_equivalence/`.
2. Archiver `Resultats_passe_bande/` dans `references_A/`, avec un `VERSION.txt` qui donne :
   - les versions d'Octave et de `signal` ;
   - le sha256 de A\* et la valeur de `fcut_high` ;
   - la date et la machine.
3. Lancer A\* une deuxième fois et vérifier que les sorties sont **identiques à l'octet près**, puisque A est déterministe. Si ce n'est pas le cas, s'arrêter et comprendre pourquoi avant d'aller plus loin.
4. Ne plus jamais régénérer `references_A/` : une nouvelle référence va dans `references_A_v2/`.

À noter : FitzRoy a déjà une sortie de A dans `run_fitzroy/` (318, 298 et 377 détections, 25,4 s). Elle doit être retrouvée à l'identique par A\*. C'est le premier contrôle.

---

## 4. Critère d'équivalence

### 4.1 Ce que A écrit, et donc ce qu'on peut comparer
A n'écrit **que des dates** :
- `Res_<nom>_Canal1.txt` et `_Canal2.txt` : une date par ligne. **Ces lignes ne sont pas triées** : dans chaque morceau, elles suivent l'ordre dans lequel la boucle `while` a accepté les pics (amplitude décroissante).
- `Res_<nom>.txt` : les dates après la fusion, avec le canal, triées.
- `BilanTot.txt` : les nombres de détections.

Les intensités, les rapports d'énergie, les seuils et les candidats rejetés ne sont pas écrits. On ne peut pas les comparer à A : ils servent uniquement au diagnostic (§5).

### 4.2 Les règles
- On convertit chaque date en **indice d'échantillon** : `n = round(t × fm)`. A écrit `ix/fm` en `%.16g`, donc la conversion est exacte. On compare des entiers, pas des flottants.
- On apparie les détections une à une, avec une tolérance de **0 échantillon** pour B et de **±1 échantillon** pour C (sauf tolérance plus large annoncée et justifiée avant le lancement). On compare séparément le canal 1, le canal 2 et la sortie fusionnée.
- Pour **B uniquement**, on compare aussi **l'ordre des lignes** des fichiers par canal. B doit reproduire la séquence de la boucle `while`, ce qui est un test bien plus fort que l'égalité des ensembles. C peut changer cet ordre.
- On calcule, par fichier et sur tout le jeu, les vrais positifs, les faux positifs, les faux négatifs, la précision, le rappel et le F1 (voir `MetriqueClassificateurs.pdf`). Ici, « faux positif » veut dire « présent dans B ou C, absent de A ».

### 4.3 Seuil d'acceptation
- **B est équivalent** si tous les fichiers ont des sorties identiques, ou si chaque écart entre dans une catégorie expliquée du §5 (sauf « bug »). Un écart inexpliqué fait échouer le test, même si le F1 vaut 0,999.
- **C est équivalent** sous la même condition. On le compare à A **et** à B : si C s'écarte de A mais pas de B, l'écart vient du portage ; s'il s'écarte aussi de B, il vient de l'optimisation.
- On rapporte le nombre d'écarts par catégorie, pas seulement le F1.

---

## 5. Explication des écarts

### 5.1 Les catégories (fixées d'avance)

| Catégorie | Signature | Comment la confirmer |
|---|---|---|
| `seuil_limite` | le pic est à moins de 1e-9 (en relatif) de `umbral`, ou le rapport est à moins de 1e-9 de `seuil` | comparer les valeurs dans la sortie diagnostique de B et dans celle de A\*-diag |
| `ex_aequo` | deux échantillons ont la même valeur maximale (`max` rend le premier) | `np.flatnonzero(x == x.max())` contient plus d'un indice |
| `cascade` | conséquence d'un écart précédent dans le **même morceau** : l'effacement de ±`t_minimo` a déplacé les pics suivants | aucun écart avant la première divergence du morceau, et la première divergence a sa propre explication |
| `frontiere_morceau` | pic à moins de 144 échantillons d'une frontière (fenêtre FFT tronquée) ou doublon entre deux morceaux | position dans le morceau |
| `fusion` | les canaux sont identiques, seule la sortie fusionnée diffère | comparer `_Canal1`, `_Canal2` et `Res_` |
| `bug` | tout le reste | à corriger dans B ou C, puis relancer **tout** le jeu |

### 5.2 Méthode
1. Pour chaque morceau qui présente un écart, chercher la **première** divergence dans la séquence des pics. Seule celle-ci a besoin d'une explication indépendante, les suivantes sont des cascades jusqu'à preuve du contraire.
2. Pour le diagnostic, utiliser :
   - côté B, une sortie diagnostique (numéro du morceau, `umbral`, `ix`, valeur du pic, deux moyennes spectrales, décision) ;
   - côté A, une copie **A\*-diag** qui écrit les mêmes valeurs. Elle n'est jamais une référence, elle sert seulement à expliquer.
3. Noter chaque écart dans `ecarts.csv` : fichier, canal, morceau, échantillon, catégorie, preuve.

---

## 6. Couverture des chemins du code

On vérifie la couverture au lieu de la supposer :
- `coverage run --branch` sur B, pour tout le jeu. Toute branche non couverte doit être justifiée (code mort recensé dans *Problèmes identifiés*, §7).
- Liste de contrôle, à cocher à partir de la sortie diagnostique de B :
  - [ ] au moins un pic à moins de 144 échantillons d'une frontière de morceau ;
  - [ ] au moins un pic rejeté, et au moins un pic accepté dans la zone effacée d'un pic rejeté ;
  - [ ] un morceau sans aucun candidat ;
  - [ ] un dernier morceau court : 0,1 s pour un fichier de 5 min, environ 0,06 s pour le fichier tronqué ;
  - [ ] une fusion qui supprime au moins une détection, et une qui laisse passer un triplet (le bug de la comparaison sautée) ;
  - [ ] un doublon à la frontière de deux morceaux.

S'il manque un cas, on ajoute un fichier selon une règle écrite (§2.3), jamais un fichier repéré en regardant les écarts.

---

## 7. Mesure du temps

### 7.1 La définition
**Facteur temps réel (FTR) = durée de l'audio / temps de calcul.** Plus il est grand, mieux c'est. *Attention : `test_cld/outils_evaluation/PROTOCOLE.md` utilise l'inverse. On garde ici celle de la roadmap, et on l'écrit dans chaque tableau.*

### 7.2 Les conditions
- La même machine pour A, B et C, décrite dans le rapport : modèle, puce, RAM, macOS, autres applications fermées.
- **La même alimentation pour A, B et C**, notée dans le fichier de conditions. Sur une puce Apple, la batterie est acceptable si le mode économie d'énergie est désactivé (il bride le processeur). La mesure officielle de A du 26/10/2026 a été faite sur batterie : B et C doivent l'être aussi (`--batterie`).
- Les WAV sur le disque interne (c'est déjà le cas avec les liens physiques de `wav/`).
- Les versions logicielles notées : Octave et `signal` ; Python, numpy, scipy et la bibliothèque BLAS (`np.show_config()`).
- **Les threads fixés** : `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1` et `VECLIB_MAXIMUM_THREADS=1` pour la mesure principale. Une mesure multithread peut être ajoutée, mais à part.
- Un échauffement non compté, puis **3 essais**, dont on retient la **médiane**. On l'applique par fichier, puis on additionne les médianes pour l'ensemble du jeu.
- **Exception pour A** (décidée le 26/10/2026) : un seul essai par fichier, sans échauffement séparé (`mesurer_A.py temps --essais 1 --sans-echauffement`). Deux passages complets du jeu concordent déjà à 0,3 % près (645,1 s et 643,5 s, voir `mesures_A/RESULTATS_A.md`), et 3 essais de A coûteraient environ 45 min. Les WAV sont en cache après ces passages. B et C gardent la médiane de 3.

### 7.3 Séparer la lecture du calcul
- **B et C** : on chronomètre la lecture (`audioread` ou son équivalent, tous morceaux compris) à part du reste.
- **A** : la lecture est mêlée à la boucle des morceaux, et A n'est pas modifié. On la mesure donc avec `profile on` (étape 2) : temps passé dans `audioread` contre temps total. On rapporte le temps total de A tel quel.
- Un essai à cache disque froid ne se fait pas proprement sous macOS sans `sudo purge`. On mesure donc à **cache chaud** (c'est l'échauffement) et on le précise.

### 7.4 Ce qu'on rapporte
- Le FTR par fichier et sur tout le jeu, pour A, B et C.
- Les rapports A/B (gain du langage) et B/C (gain de l'implémentation).
- Le temps en fonction du nombre de candidats examinés (repris à l'étape 2). Les strates sont choisies pour couvrir cette gamme.

---

## 8. Arborescence

    jeu_equivalence/
      PROTOCOLE_EQUIVALENCE.md     ce document
      construire_jeu.py            règles de choix, graine
      manifeste.csv                fichiers, rôles, sha256
      liste_fichiers_extrait.txt   entrée de A*
      wav/                         liens physiques
      references_A/                sorties de A*, v1 (12 fichiers) + VERSION.txt
      references_A_v2/             sorties de A*, jeu v2 (24 fichiers) + VERSION.txt
      archiver_references.py       relance de contrôle et archivage (section 3)
      mesurer_A.py                 temps (section 7) et profil de A*
      mesures_A/                   résultats datés de mesurer_A.py
      ecarts.csv                   un écart expliqué par ligne   (à produire)

## 9. Questions ouvertes
- [ ] **`fcut_high` à 288 kHz** (bloquant, voir §1) : à demander à l'encadrant.
- [ ] `6209.260520182507.wav` : on garde ici le fichier tronqué tel quel, puisque c'est le cas à tester. S'il est réextrait depuis son `.sud` pour d'autres usages, il ne faut pas écraser la version tronquée (son sha256 est dans le manifeste).
- [ ] `test_cld/jeu_test_fige/wav/6209.260514101959.wav` ne fait que 524 Ko : la copie a été interrompue. Il faut relancer `copier_jeu_test.sh` (ce fichier ne fait pas partie de ce jeu).
