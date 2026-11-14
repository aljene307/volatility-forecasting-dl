# Journal des choix

Chaque entrée consigne une décision, sa raison et ce qui reste à vérifier.

## 2026-11-13 — Environnement et matériel

### Matériel mesuré

- Processeur : Intel Core i7-1255U, 10 cœurs (2 cœurs performance + 8 cœurs efficacité), 12 fils.
- Mémoire : 15,7 Go de RAM au total, environ 2,8 Go libres avec Chrome et VS Code ouverts.
- Carte graphique : Intel Iris Xe intégrée, sans CUDA (aucun GPU NVIDIA).

### Décision : où entraîner les modèles

- Entraînement en local d'abord.
- Google Colab seulement si un essai chronométré montre que c'est nécessaire.
- Raison : la reproductibilité est plus simple à garantir sur une seule machine.

### À mesurer plus tard

- Le nombre de fils de calcul le plus efficace pour l'entraînement : comparer 2, 4 et 8.
- Le seuil de mémoire libre au-dessous duquel les scripts lourds refusent de démarrer.

### Paramètres de reproductibilité

- Graine aléatoire et nombre de fils de calcul : placés dans une configuration commitée, pas dans .env (raison : reproductibilité).

### Fins de ligne

- `core.autocrlf = true` a été trouvé au niveau système de Git.
- Il est neutralisé localement dans le dépôt (`core.autocrlf = false`) et par le fichier `.gitattributes`, qui impose LF pour les fichiers texte (CRLF seulement pour les scripts `.ps1`).
- Raison : au projet 2, un fichier en CRLF a fait planter l'API.

### Python

- Python 3.11 dans l'environnement virtuel `.venv`, alors que la version par défaut du poste est 3.13.
- L'environnement se crée avec `py -3.11 -m venv .venv`.
- Version retenue : Python 3.11.9 (dernière version 3.11 avec installateur Windows), la même que celle prévue sur Render.
- Le 2026-11-13, Python 3.11.0 a été remplacé par 3.11.9, et `.venv` a été recréé (il était vide : seulement pip et setuptools).
- Raison : la même version en local et sur le serveur évite des écarts de comportement.

### Documents du cours

- Les PDF du cours restent hors du dossier du projet.

### Outils

- Signature automatique des commits désactivée dans l'éditeur.

## 2026-11-14 — Règles écrites avant le calcul

Les règles complètes sont dans `docs/REGLES.md` (version lisible) et `config/regles.toml` (version lue par le code). Voici les choix principaux et leurs raisons.

- **BTC et ETH seulement.** Ce sont les cryptos les plus liquides, avec un historique depuis 2017. SOL est écarté : il n'existait pas pendant le krach du Covid, donc on ne pourrait pas le comparer sur cette crise.
- **Horizon J+1 seulement.** Un seul horizon permet de mener le projet jusqu'au bout et de bien le maîtriser.
- **Sans VIX.** Licence de Yahoo incertaine, pas de valeur le week-end alors que la crypto cote 7 jours sur 7, et un autre fuseau horaire que l'UTC.
- **TOML plutôt que YAML.** Le TOML est lu par la bibliothèque standard de Python (`tomllib`) : aucune dépendance de plus.
- **Embargo.** Un embargo d'un jour avait d'abord été prévu ; il est remplacé par un embargo de 0 jour (voir le point 1-2 ci-dessous).
- **Valeurs « à fixer après mesure ».** Le nombre de fils de calcul, le seuil de mémoire libre et le budget de réglage seront fixés plus tard, à partir de mesures chronométrées. Tant qu'elles ne sont pas fixées, le code refuse de lancer un entraînement.

### Corrections avant le premier calcul

Une relecture des premières règles a relevé six points flous ou incohérents. Ils sont corrigés ici, avant tout téléchargement et tout calcul.

- **Points 1 et 2 — Appartenance d'un exemple et embargo.**
   - Décision : un exemple (variables à la clôture de J, cible RV de J+1) appartient à la période qui contient sa cible J+1. Toutes les bornes de période et de pli sont des dates de cible. Embargo : 0 jour.
   - Raison : sans convention, l'exemple du 2024-12-31 aurait eu sa cible dans le test final. Avec cette convention, aucune cible n'est commune entre apprentissage et évaluation pour un horizon d'un jour ; un test le vérifie pour chacun des 10 plis, pour la validation interne et pour le test final.
   - Correction honnête : l'embargo d'un jour proposé au départ venait d'une convention de date différente (les exemples datés par le jour J des variables). Avec la convention « date de la cible », il est devenu inutile.
- **Point 3 — Retour depuis le logarithme.**
   - Décision : variance prévue = exp(2·ŷ + 2·s²) pour QLIKE, RV prévue = exp(ŷ + s²/2) pour RMSE et MAE, où s² est la variance des résidus en log mesurée sur l'apprentissage du pli (la validation interne pour le deep learning). La version non corrigée est rapportée en sensibilité, sans changer la décision.
   - Raison : exp(ŷ) donne la médiane, donc une prévision trop basse en moyenne, que QLIKE punit fortement. La même correction s'applique à tous les modèles qui prévoient log(RV).
   - Remplacé en partie : la formule de la RV prévue et la mesure de s² sont remplacées par les précisions finales ci-dessous.
- **Point 4 — Échelle de GARCH(1,1).**
   - Décision : un facteur unique = moyenne(RV²) / moyenne(variance GARCH), appris sur l'apprentissage de chaque pli, puis appliqué tel quel à l'évaluation.
   - Raison : GARCH prévoit la variance du rendement d'un jour, qui n'a pas exactement la même échelle que la RV calculée sur 5 minutes.
- **Point 5 — Préchauffage et trous.**
   - Décision : du 2018-01-01 au 2018-03-31 (90 jours), les données servent uniquement à calculer les variables ; première cible le 2018-04-01 ; aucune donnée de 2017. Un rendement entre deux clôtures consécutives disponibles est gardé même s'il enjambe des bougies manquantes, mais un écart de plus de 60 minutes rend le jour non valide (en plus de la règle des 274 bougies). Le premier rendement du jour part de la dernière clôture disponible de la veille, avec la même règle. Un exemple dont la fenêtre d'entrée de 30 jours contient un jour non valide est exclu, et les exclusions sont comptées ; au-delà de 5 % d'exclusions, les jours non valides en entrée prennent la dernière valeur valide connue. La volatilité cible de la stratégie reste la médiane de la RV annualisée des jours valides du 2018-01-01 au 2019-12-31.
   - Raison : les variables les plus longues ont besoin d'historique, et la façon de traiter les trous doit être fixée avant de voir les données.
- **Point 6 — Diebold-Mariano.**
   - Décision : nombre de retards HAC = floor(4·(T/100)^(2/9)) (règle de Newey-West, T = nombre de jours évalués), avec la correction de Harvey-Leybourne-Newbold.
   - Raison : le nombre de retards est fixé par une formule et non choisi après avoir vu les résultats ; la correction rend le test plus fiable sur de petits échantillons.

Précisions finales, après une seconde relecture (même jour, toujours avant tout calcul) :

- **Premier apprentissage et modèle du test final.**
  - Décision : le premier apprentissage commence à la première cible, le 2018-04-01. Le modèle du test final est ajusté sur les cibles du 2018-04-01 au 2024-06-30, avec une validation interne du 2024-07-01 au 2024-12-31. Ces dates sont écrites dans le TOML, et un test vérifie qu'elles suivent la règle des plis.
  - Raison : aucune cible n'existe avant le 2018-04-01, et le modèle du test final suit la même règle que les plis.
- **Fenêtre d'ajustement commune et mesure de s².**
  - Décision : tous les modèles (HAR-RV, XGBoost, deep learning) sont ajustés sur la même fenêtre d'ajustement, c'est-à-dire l'apprentissage du pli sans sa validation interne. s² est toujours mesuré sur la validation interne, pour tous les modèles qui prévoient log(RV).
  - Raison : mesurer l'erreur sur des jours que le modèle n'a pas appris, avec les mêmes données pour tous. Mesuré sur l'apprentissage, s² serait presque nul pour XGBoost, qui retient très bien ses propres données.
- **Une seule volatilité prévue.**
  - Décision : σ̂ = racine(variance prévue), avec variance prévue = exp(2·ŷ + 2·s²) pour les modèles en log, et variance GARCH mise à l'échelle pour GARCH. σ̂ sert pour RMSE, MAE, la stratégie et la VaR. La formule exp(ŷ + s²/2) est supprimée. La sensibilité « non corrigée » s'applique à cette définition (s² = 0).
  - Raison : une seule définition pour tout le projet, sans possibilité de choisir après coup la plus favorable.
  - Limite : σ̂ est un peu au-dessus de la moyenne de la RV, ce qui pénalise légèrement le MAE.
- **Premier jour des données.**
  - Décision : le 2018-01-01 est un jour valide avec 287 rendements (un rendement manquant compte comme une bougie manquante). Il fait partie du préchauffage et n'est jamais une cible.
  - Raison : sans donnée de 2017, ce jour n'a pas de veille ; un seul rendement manquant reste bien au-dessus du seuil de 274.
- **Seuil de secours de 5 %.**
  - Décision : mesuré une seule fois, par actif, sur tout le développement (cibles du 2018-04-01 au 2024-12-31), jamais sur le test final. Si un actif dépasse 5 %, la règle de secours s'applique aux deux actifs, partout.
  - Raison : décider sans regarder le test final, et traiter les deux actifs de la même façon.
- **Portée du test de Diebold-Mariano.**
  - Décision : le test principal porte sur les 10 plis réunis (T = jours évalués, retards par la règle de Newey-West). Sur le test final, un seul test. Les résultats par pli et par crise sont uniquement descriptifs, sans conclusion de test.
  - Raison : éviter les tests multiples, qui finissent toujours par donner un résultat « significatif » par hasard.
- **Validation interne et pli précédent.**
  - La validation interne d'un pli est la période évaluée du pli précédent ; c'est du passé au moment du pli, donc ce n'est pas une fuite. Un test le vérifie.

Règle pour la suite : toute question apparue après ce commit et avant le premier calcul sera consignée comme exception datée dans CHOIX.md et listée dans le README.

Remarques écrites en même temps :

- **VaR** : loi normale pour tous les modèles, pour que la règle soit la même pour tous. Les rendements crypto ayant des queues épaisses, on s'attend à un test de Kupiec sévère.
- **Horodatage Binance** : le chargeur détectera l'unité (millisecondes ou microsecondes) de chaque fichier d'après l'ordre de grandeur des nombres. Ce sera testé avec un témoin dans chaque unité à l'étape des données.
- **Crises** : les trois crises sont analysées sur les prévisions hors échantillon des plis walk-forward. C'est voulu, car aucune n'est dans le test final.
- **Dépendances de test** : pytest et toutes ses dépendances sont épinglés en versions exactes dans `requirements-dev.txt`.

Ces règles sont commitées et poussées avant tout téléchargement de données.
