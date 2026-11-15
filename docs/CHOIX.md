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

## 2026-11-14 — Exceptions datées

Décidées après le commit des règles (31b9dae) et avant tout téléchargement ou calcul. Chacune est aussi listée dans le README.

- **Exception 1 — GARCH(1,1) sur la fenêtre d'ajustement seule.**
  - Décision : les paramètres de GARCH et son facteur d'échelle sont appris sur la fenêtre d'ajustement du pli, sans la validation interne.
  - Raison : tous les modèles doivent être ajustés sur les mêmes données. La règle précédente (« apprentissage du pli ») donnait à GARCH six mois de plus que les autres.
- **Exception 2 — Limite de la mesure de s².**
  - Décision : s² reste mesuré sur la validation interne, même si celle-ci sert aussi à l'arrêt anticipé et au réglage d'XGBoost et du deep learning.
  - Limite : pour ces modèles, s² est légèrement trop petit. Leurs prévisions de variance sont donc un peu trop basses, ce que QLIKE punit : ce biais les désavantage, il ne les favorise pas.
  - Raison : garder une seule règle pour tous les modèles, avec un défaut connu et allant contre les modèles complexes.
- **Exception 3 — Annualisation.**
  - Décision : σ̂ est une volatilité journalière. Stratégie : exposition = volatilité cible annuelle / (σ̂ × racine(365)), bornée entre 0 et 1. VaR à 1 jour : σ̂ journalière, sans annualisation.
  - Raison : la volatilité cible est annuelle, alors que σ̂ et la VaR portent sur un jour. Sans cette précision, une erreur d'échelle d'un facteur racine(365), soit environ 19, était possible. Un test et un témoin la détectent.
- **Exception 4 — README.**
  - Décision : création d'un README minimal, qui renvoie vers `docs/REGLES.md` et `docs/CHOIX.md` et liste les exceptions datées.
  - Raison : la règle des exceptions demande de les lister dans le README, qui n'existait pas encore.

Vérification prévue : l'affirmation de l'exception 2 (le biais de s² désavantage les modèles réglés) suppose que leur ŷ est sans biais ; à vérifier sur la validation (moyenne des résidus en log proche de 0) avant de l'affirmer.

Note pour l'oral : le modèle du test final suit la même recette que les plis. Les 6 derniers mois du développement (cibles du 2024-07-01 au 2024-12-31) servent à l'arrêt anticipé et à la mesure de s², pas à l'ajustement.

## 2026-11-14 — Téléchargement et contrôle des données

### Choix techniques et raisons

- **Téléchargement avec la bibliothèque standard** (`urllib`) : aucune dépendance de plus pour l'étape la plus sensible. Un fichier à la fois, délai d'attente de 60 s, au plus 3 nouvelles tentatives (attente qui double), pause de 0,3 s entre les fichiers, pour respecter le serveur.
- **Vérification de chaque zip** avec le fichier `.CHECKSUM` publié par Binance (SHA-256). Le zip est écrit dans un fichier `.part`, renommé seulement après la vérification ; un fichier refusé est déplacé dans `data/raw/_rejets/`, jamais supprimé. Raison : un fichier abîmé ne peut jamais être pris pour un bon.
- **Relance sans risque** : le `.CHECKSUM` est gardé à côté du zip, donc une relance vérifie les fichiers présents sans aucune requête réseau.
- **Manifestes commités** (`data/manifeste_brut.json`, `data/manifeste_traite.json`) : triés, sans date de téléchargement ni chemin absolu, pour qu'une relance donne exactement les mêmes octets. Les données elles-mêmes restent hors du dépôt.
- **Un Parquet par actif**, écrit mois par mois (mémoire limitée), dates en UTC avec une précision à la microseconde, exacte pour les deux unités de Binance.
- **Unité des horodatages détectée par fichier** (13 chiffres = millisecondes, 16 = microsecondes) ; tout autre cas arrête la conversion. Constaté : millisecondes jusqu'en 2024-12, microsecondes à partir de 2025-01, pour les deux actifs.
- **Empreinte de contenu** des Parquet, calculée sur les valeurs relues et non sur les octets : elle ne dépend ni de la version de pyarrow, ni du découpage du fichier. Un test le vérifie.
- **Bibliothèques** : numpy, pandas et pyarrow épinglées en versions exactes dans `requirements.txt`, avec leurs dépendances (pandas a été baissé le 2026-11-15, voir plus bas).
- **Test aveugle** : pour la période du test final, le rapport de qualité ne contient que des comptages. Aucune statistique de prix, de rendement, de volume ou de volatilité n'est produite, pour aucune période.

### Mesures (essai réel)

Les chiffres de qualité sont dans `docs/QUALITE_DONNEES.md`, généré par `src/qualite.py`. Mesures de l'essai sur ce poste :

- Téléchargement de 212 fichiers : environ 1 115 s (le serveur répond lentement, environ 5 s par fichier), 424 requêtes, 0 rejet, 0 échec.
- Conversion : environ 10 s. Contrôle de qualité : environ 4 s.
- Taille : 90 Mo pour `data/raw` (212 zips et 212 `.CHECKSUM`), 141 Mo pour `data/processed`.
- Mémoire maximale du vrai processus Python (mesurée de l'intérieur ; le lanceur de `.venv` est un processus parent séparé) : environ 30 Mo pour le téléchargement, 168 Mo pour la conversion, 385 Mo pour le contrôle de qualité.
- Mémoire libre avant l'essai : environ 3,4 Go ; disque libre : environ 477 Go avant comme après.
- Seconde exécution complète : 0 requête réseau, environ 15 s, manifestes, rapports et fichiers Parquet identiques octet pour octet.

### Anomalies constatées (développement seulement)

- **Bougies désalignées** : après la maintenance de Binance de février 2018, 241 bougies (du 2018-02-09 vers 09:58 au 2018-02-10 vers 05:58 UTC) commencent 3 min 14 s après la grille de 5 minutes, sur les deux actifs. Les règles ne prévoient pas ce cas : le contrôle de qualité les compte à part et les traite comme manquantes (exception 5 ci-dessous). Ces jours sont dans le préchauffage et étaient de toute façon non valides à cause de l'arrêt de plus de 50 heures.
- **Jours non valides** : 30 par actif dans le développement, aux mêmes dates pour BTC et ETH (arrêts de toute la plateforme), aucun dans le test final. Le premier mois (2018-01) n'est pas complet à cause du 2018-01-04 ; le dernier mois (2026-10) est complet ; le 2018-01-01 est valide avec 287 rendements.
- **Seuil de secours** : la règle d'exclusion par fenêtre de 30 jours s'est révélée bien plus sévère que prévu : elle exclut 24,16 % des exemples du développement pour chaque actif (chiffre lu dans `docs/QUALITE_DONNEES.md`), alors que le seuil était de 5 %. Un seul jour non valide exclut les 30 cibles qui le suivent. La règle de secours, écrite avant de voir les données, s'est donc déclenchée sans aucun choix après coup : elle s'applique aux deux actifs, partout.
- **Attribution d'un trou** : un écart entre deux bougies est compté pour chaque jour qui contient une partie des bougies manquantes, et pour le jour de la bougie qui suit l'écart (exception 6 ci-dessous). Exemple : un arrêt de 23:00 à 01:00 rend non valides les deux jours.

### Exceptions datées de l'étape (2026-11-14)

- **Exception 5 — Bougies désalignées de février 2018.**
  - Décision : les 241 bougies désalignées sont traitées comme manquantes.
  - Raison : cas non prévu par les règles ; ces bougies sont dans le préchauffage, et les jours concernés étaient déjà non valides.
- **Exception 6 — Attribution d'un trou aux deux jours qu'il touche.**
  - Décision : validée.
  - Raison : le premier jour perd des bougies, et le premier rendement du second jour enjambe le trou ; les deux mesures de volatilité sont donc faussées.

### Licence des données (lue le 2026-11-14, décision prise le même jour)

Décision : licence acceptée (CC BY-NC-SA 4.0 et Vision Dataset Terms), pour un usage éducatif et non commercial, avec ces règles :

- le code du dépôt est sous licence MIT (le code seul) ;
- tout ce qui est dérivé des données (graphiques, résultats, modèles entraînés, fichiers ONNX) est sous CC BY-NC-SA 4.0, avec la mention « Données : Binance Vision » ;
- jamais de données brutes ni de séries journalières dérivées dans le dépôt ;
- API et application : décision reportée à cette étape ; règle prudente par défaut (résultats agrégés et graphiques, pas de flux de données) ;
- le fichier de licence du dépôt sera créé à la publication.

Ce qui a été lu :

- Les conditions de Binance Vision (`TERMS_AND_CONDITIONS.md` du dépôt public `binance/binance-public-data`, et la page « Terms of Use » de data.binance.vision) placent les données sous la licence CC BY-NC-SA 4.0, avec des règles plus strictes qui l'emportent en cas de conflit.
- Usage non commercial seulement (recherche universitaire, projets éducatifs non rémunérés, backtests personnels) ; l'hébergement ou la redistribution des fichiers bruts est interdit ; une œuvre dérivée redistribuée doit citer Binance Vision et rester sous la même licence.
- Point non clair : si publier une série journalière dérivée compte comme « héberger un flux historique dérivé » (interdit). La règle prudente retenue (aucune série journalière dans le dépôt) évite la question.
- Vérification complémentaire (2026-11-15) : les clauses 2.4, 3.1, 3.3 et 4.5 ont été vérifiées dans le PDF officiel des conditions de Binance Vision. Les conditions générales de binance.com, auxquelles ce texte renvoie, n'ont pas été lues : limite acceptée pour un usage éducatif et non commercial.
- Sources : https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md et https://data.binance.vision/terms-of-use.html.
- Seuls les manifestes et des comptages sont commités à cette étape.

## 2026-11-15 — Vérification de la pile de bibliothèques

But : vérifier, avant de calculer les variables, que toutes les bibliothèques prévues s'installent et fonctionnent ensemble sous Python 3.11.

### Corrections préalables

- **Recherche des mots interdits** : un mot trop général, qui détectait à tort l'en-tête HTTP « User-Agent », est remplacé par deux expressions plus précises, recherchées sans tenir compte des majuscules ; « User-Agent » est explicitement permis. Témoins : un fichier qui contient une des expressions est trouvé ; un fichier qui ne contient que « User-Agent » ne l'est pas.
- **Test du README** : chaque chemin de fichier cité entre accents graves dans le README doit exister et être suivi par git, avec un témoin.

### Versions retenues et raisons

Toutes les versions exactes, dépendances comprises, sont dans `requirements.txt`, en deux sections (calcul ; apprentissage profond). numpy (2.4.6) et pyarrow (26.0.1) sont inchangés.

- **pandas baissé de 3.1.1 à 3.0.6** (dernière 3.0.x). Raison : pytorch-forecasting 1.8.0, la version la plus récente, qui fournit le TFT, exige `pandas<3.1.0`. Ses versions plus anciennes refusent elles aussi pandas 3.1. On reste sur pandas 3.
- **lightning 2.6.6** : pytorch-forecasting exige `lightning<2.7.0`, sauf 2.6.2 et 2.6.3. **scikit-base 1.0.2** : pytorch-forecasting exige `scikit-base<1.1.0`.
- **xgboost 3.2.0 et shap 0.51.0** : les versions plus récentes (xgboost 3.4.1, shap 0.54.1) exigent Python 3.12. On reste en Python 3.11, la version fixée dans les règles et prévue pour le déploiement. On prend donc les dernières versions encore publiées pour Python 3.11 sous Windows.
- numba 0.68.1 (dépendance de shap) accepte numpy < 2.6 : compatible avec numpy 2.4.6.
- Méthode : les exigences déclarées sur PyPI ont été lues avant l'installation, puis un fichier de contraintes avec une version exacte par bibliothèque a été construit, pour que pip n'ait plus à chercher.

### Temps perdu (dit honnêtement)

- Première tentative : pip est revenu à un paquet source et a échoué à le construire (`pkg_resources` absent).
- Deuxième tentative, sans les contraintes exactes : pip a fait un « retour arrière » pendant environ 1 h 20. Il a essayé une à une des versions de plus en plus anciennes de pytorch-forecasting, jusqu'à la 0.1.0, pour trouver une version compatible avec pandas 3.1.1, sans en trouver. Arrêtée à la main.
- Troisième tentative, avec les contraintes exactes : le choix des versions a pris environ 1 min 30, sans aucun retour arrière. Elle a été arrêtée par la limite de 10 minutes pendant les téléchargements, à cause de la connexion lente.
- Vitesse de connexion mesurée : torch (126,7 Mo) en 8 min 44 s, soit environ 0,24 Mo/s.
- Solution : tous les fichiers ont d'abord été téléchargés dans un dossier temporaire hors du projet (63 fichiers, 423,4 Mo, 94 s, torch étant déjà dans le cache de pip). L'installation s'est faite ensuite depuis ce dossier, sans réseau.

### Installation et mesures

- Environnement temporaire hors du projet : installation sans réseau en 399 s, `pip check` sans problème, 1 557,6 Mo installés. Cet environnement a été supprimé à la fin de l'étape.
- `.venv` du projet : installation sans réseau en 441 s, `pip check` sans problème, 1 572,2 Mo au total.

### Essais rapides sur données aléatoires

Les 7 essais ont réussi, en 41 s au total, avec une mémoire maximale du processus de 616 Mo.

- torch, LSTM, un pas d'entraînement avec `use_deterministic_algorithms(True)` : deux exécutions avec la même graine donnent des poids identiques (écart 0). Le déterminisme de torch a été vérifié avec 10 fils de calcul ; il n'est garanti que pour un nombre de fils fixé, d'où l'importance de figer `fils_calcul` après la mesure.
- xgboost : ajustement et prévision.
- arch : GARCH(1,1) avec loi de Student, convergé.
- statsmodels : régression avec erreurs HAC (Newey-West).
- shap : TreeExplainer sur le petit XGBoost, la somme des contributions retrouve la prévision (écart 3,0e-07).
- pytorch-forecasting : TFT construit sur un DataFrame pandas 3.0.6, un pas d'entraînement, les poids changent. Pendant cet essai, le mode déterministe de torch était désactivé ; le déterminisme du TFT reste à vérifier.
- onnx et onnxruntime : export du LSTM, écart avec torch de 4,1e-08 (tolérance 1e-5).
- Point ouvert : le nouvel exportateur ONNX de torch (« dynamo ») demande la bibliothèque `onnxscript`, qui n'est pas dans la pile prévue. L'ancien exportateur fonctionne. À revoir à l'étape de l'export.

### Lecture exacte des nombres (correction de `src/convertir.py`)

- Constat : après la baisse de pandas, la conversion a donné une empreinte de contenu différente pour BTCUSDT (ETHUSDT identique). Seules deux colonnes de volume en monnaie de cotation différaient, sur 141 lignes sur 927 482, d'un ulp (le plus petit écart possible entre deux nombres à virgule). Pour la période de test, seules ces lignes ont été comptées ; aucune valeur n'a été regardée.
- Cause : le lecteur CSV par défaut de pandas 3.0.6 arrondit parfois au voisin d'à côté des nombres à 17 chiffres. pandas 3.1.1 donnait la valeur exacte, vérifiée avec `float()` de Python sur toutes les lignes de développement concernées.
- Correction : `float_precision="round_trip"` dans la lecture du CSV, ce qui donne une lecture exacte quelle que soit la version de pandas. Test témoin : le texte `92242008.04830823` doit être lu comme `float()` le lit ; ce test échoue sans l'option et passe avec elle.
- L'écart d'un ulp serait resté sous la tolérance de 1e-9 des règles, mais la lecture exacte rend les empreintes identiques à celles déjà commitées et protège contre les futures versions de pandas.
- Résultat : après la correction, le manifeste des données traitées, le rapport de qualité et les deux fichiers Parquet sont identiques octet pour octet à ceux d'avant le changement de pile.

## 2026-11-15 — Précisions écrites avant le calcul des variables

Ces précisions sont datées du 2026-11-15. Elles ont été écrites et commitées avant tout calcul de variable, dans `config/regles.toml` (sections `variables.precisions`, `variables.secours`, `variables.sorties`, `test_aveugle`, `exploration`) et dans `docs/REGLES.md`, avec la raison de chacune.

- **Ligne journalière** : ouverture de la première bougie, plus haut et plus bas du jour, clôture de la dernière bougie, volume en USDT. Raison : le volume en USDT est comparable entre actifs et dans le temps.
- **Formules** : RV moyennes en log = log de la moyenne ; log-rendement de clôture à clôture ; RSI de Wilder amorcé par la moyenne simple des 14 premières variations ; moyennes du MACD démarrées à la première clôture, histogramme divisé par la clôture ; Bollinger avec l'écart-type de population, largeur divisée par la moyenne mobile. Raison : définitions d'origine, vérifiables à la main, et comparables dans le temps.
- **Règle de secours** : la ligne journalière entière d'un jour non valide est remplacée par celle du dernier jour valide, puis toutes les variables sont calculées sur cette série. Raison : une seule règle, simple, qui n'utilise que le passé.
- **Limite du secours** : le rendement du jour remplacé est nul, et celui du lendemain porte sur deux jours.
- **Comptages** : remplacements par actif et par période ; exemples du développement dont la fenêtre d'entrée de 30 jours contient au moins un jour remplacé, par actif.
- **Validité en entrée** : un contrôle automatique vérifie que la validité d'un jour, utilisée en entrée, n'utilise jamais l'avenir. Vérification préalable, en lecture seule : un seul trou du développement passe minuit (du 2018-02-08 au 2018-02-10), et le jour où il commence est déjà non valide avec ce qu'on sait à sa clôture.
- **Manifeste séparé** : l'empreinte de `variables.parquet` va dans `data/manifeste_variables.json`, et non dans `data/manifeste_traite.json`. Raison : le rapport de qualité enregistre l'empreinte du manifeste traité (elle deviendrait fausse), et une relance de la conversion effacerait l'ajout.
- **Garde du test aveugle** : refus sans aucune option de contournement ; l'ouverture du test sera construite à l'étape du test final.
- **Exploration** : développement seulement ; autocorrélation de log(RV) jusqu'à 60 jours avec les jours non valides laissés vides ; ADF (AIC) sur log(RV) et sur le log de la clôture, jours non valides retirés (limite écrite).

## 2026-11-15 — Volatilité réalisée, variables, cible et analyse exploratoire

### Choix techniques et raisons

- **Une seule source de vérité** : `src/variables.py` reprend les fonctions de `src/qualite.py` (bougies alignées, trous, `bilan_jours`) pour les jours valides. Aucune logique de validité n'est dupliquée.
- **Agrégats journaliers** : ouverture de la première bougie, plus haut, plus bas, clôture de la dernière bougie, volume en USDT. Raison du volume en USDT : il est comparable entre BTC et ETH et dans le temps.
- **MACD divisé par la clôture** et **Bollinger divisé par la moyenne** : sans division, ces indicateurs grandissent avec le prix. Divisés, ils sont comparables entre 2018 et 2024.
- **Garde du test aveugle** (`src/garde.py`) : deux fonctions seulement. `refuser_si_test` refuse toute valeur dont la date de cible est dans le test final ; `compter` permet les comptages. Un test vérifie, par l'analyse du code source, qu'il n'existe aucun paramètre en plus, aucune valeur par défaut, aucune lecture de l'environnement ou de la ligne de commande et aucun réglage d'ouverture. Un témoin (une fausse garde avec ces options) est bien détecté.
- **Exploration** : les lignes journalières ne sont calculées que jusqu'au 2024-12-31. Aucune valeur du test final n'est donc calculée dans l'exploration, et chaque statistique et chaque figure passe en plus par la garde.
- **Empreinte de contenu** : la fonction de `src/convertir.py` accepte maintenant d'autres colonnes, des jours et du texte. Vérifié : après relance de la conversion et du contrôle de qualité, le manifeste traité et les rapports de qualité sont identiques octet pour octet.

### Décisions prises seul pendant le calcul (à valider)

- Le manifeste des variables cite aussi l'empreinte de `config/regles.toml`, pour savoir avec quelles règles les variables ont été calculées.
- Le test de l'avenir modifié a une seconde variante, plus sévère : facteur 10 multiplié par un bruit différent pour chaque bougie. Raison : la RV ne dépend pas du niveau des prix. Une multiplication par 10 seule ne change que le premier rendement du lendemain, donc une variable qui tricherait avec la RV d'un jour plus lointain pourrait passer inaperçue.
- Les jours remplacés sont comptés par date du jour (préchauffage, développement, test final). Les exemples touchés par un jour remplacé sont comptés parmi les exemples gardés (cible valide). Ce chiffre est donc un peu plus petit que le taux d'exclusion du rapport de qualité, qui compte toutes les cibles.
- Asymétrie : coefficient de pandas (Fisher, corrigé du biais). Zone « aucune autocorrélation » : ± 1,96 / racine(n), avec n le plus petit nombre de jours valides des deux actifs.
- `docs/EXPLORATION.md` signale le pic d'autocorrélation tous les 7 jours, quand il est présent, avec une phrase générée à partir des valeurs.
- Le README renvoie vers les trois fichiers de figures un par un, et non vers le dossier : le test du README n'accepte que des liens vers des fichiers suivis.

### Limites

- La règle de secours : rendement nul le jour remplacé, rendement sur deux jours le lendemain.
- Le RSI et le MACD ont une mémoire plus longue que 30 jours. Un jour remplacé les influence donc un peu au-delà de la fenêtre de 30 jours comptée.

### Résultats et mesures (essai réel)

Les chiffres sont lus dans `data/manifeste_variables.json`, `rapports/volatilite_cible.json` et `rapports/exploration.json` (développement seulement), qui sont générés.

- Règle de secours, pour chaque actif : 4 jours remplacés dans le préchauffage, 26 dans le développement, 0 dans le test final (comptage). Exemples gardés du développement : 2 441, dont 585 avec au moins un jour remplacé dans leur fenêtre de 30 jours.
- Contrôle « la validité d'un jour en entrée n'utilise jamais l'avenir » : 2 jours contrôlés par actif (le trou de février 2018 passe deux minuits), aucun écart. Témoin : un trou synthétique de 23:25 à 00:40 est bien refusé.
- Test de l'avenir modifié : 0 écart au bit près, sur des données synthétiques (bord de mois, crise Covid, jour remplacé, fin de mois) et sur les vraies données (5 jours par actif, dont la crise Covid et deux fins de mois), pour les deux variantes. Témoin : une moyenne centrée de RV est détectée pour chacun des jours choisis.
- Deux exécutions complètes : variables, manifeste, volatilité cible, rapport exploratoire et figures identiques octet pour octet.
- Durée et mémoire maximale du vrai processus Python : environ 0,7 s et 470 Mo pour les variables ; environ 1,9 s et 550 Mo pour l'exploration.
