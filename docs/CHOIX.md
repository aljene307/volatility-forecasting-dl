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

## 2026-11-16 — Règles d'entraînement, écrites avant tout entraînement

Précisions datées du 2026-11-16, écrites et commitées avant tout entraînement, dans `config/regles.toml` (section `entrainement`) et dans `docs/REGLES.md` (section 11), avec la raison de chacune. Les trois valeurs « à fixer après mesure » restent à fixer à ce commit.

- **Un modèle par actif**, pour tous les modèles. Raison : comparaison directe avec HAR-RV et GARCH, univariés. Limite : moins de données par réseau.
- **Entrées** : les 13 variables continues et le jour de la semaine (entier pour XGBoost, one-hot pour les modèles séquentiels, catégorie connue pour le TFT). Les repères de comptage de la règle de secours ne sont jamais des entrées.
- **Normalisation** : moyenne et écart-type appris sur la fenêtre d'ajustement de chaque pli, enregistrés en JSON ; log(RV) est aussi normalisée pour les réseaux, et la sélection se fait en unités de log(RV).
- **Perte** : erreur quadratique sur log(RV) pour tous les modèles réglés. QLIKE reste la métrique d'évaluation finale.
- **Limite du TFT** : le TFT est entraîné en MSE comme les autres modèles, il ne fournit donc pas d'intervalles de quantiles. Ses normaliseurs internes sont désactivés.
- **Dropout** : avec 2 couches, la même valeur s'applique entre les couches et à la sortie ; avec 1 couche, à la sortie seulement (le dropout interne de torch n'agirait pas).
- **Arrêt anticipé** : patience de 20 époques, 200 au plus ; XGBoost : patience de 50 arbres, 2000 au plus.
- **Recherche aléatoire** : graine 42, même nombre N de combinaisons VALIDES pour chaque modèle réglé. Les tirages incohérents (TFT avec hidden_continuous_size > hidden_size) sont écartés et remplacés par la suite déterministe des tirages ; leur nombre sera rapporté.
- **Remarque sur XGBoost** : avec subsample = colsample = 1, il n'a aucun hasard ; ses 5 graines donnent alors le même modèle.
- **Reprise après interruption** : unités indépendantes, un fichier par unité, graine dérivée de l'identifiant par hachage, unités terminées sautées à la relance, mise en veille de Windows empêchée pendant le calcul. Le code complet sera construit à l'étape d'entraînement.
- **Mesures** : sur des données aléatoires de même forme que les vraies, avec 2441 exemples (tout le développement). C'est prudent : la plus grande fenêtre d'ajustement est un peu plus petite. Un crochet d'audit contrôle qu'aucune vraie donnée n'est lue.
- **Arrêts obligatoires** : N < 5, ou seuil de mémoire (pic × 1,5, arrondi au 0,5 Go supérieur) au-dessus de 2,5 Go.
- **Suivi** : si la durée réelle dépasse l'estimation de plus de 50 %, arrêt propre et exception datée ; N n'est jamais changé en silence.

## 2026-11-16 — Exceptions : la règle d'entraînement initiale était irréalisable

### Constat (dit honnêtement)

Les premières mesures, sur données aléatoires, ont donné N = −5 : la règle initiale demandait environ **124 heures** de deep learning pour N = 5, et même 62 heures pour N = 0, avec un budget de 12 heures.

- Temps d'une époque (2 fils, configuration médiane) : LSTM 0,93 s ; GRU 3,31 s ; CNN-LSTM 1,22 s ; Transformer 3,66 s ; TFT 11,24 s. Somme des 5 modèles × 100 époques : 2 035 s par entraînement.
- Calcul : 2 actifs × 11 découpages × (5 + 5) × 2 035 s, soit 447 735 s, environ 124 heures.
- Ces premières mesures ont été faites **sur batterie, à 22 %, en mode d'alimentation « Utilisation normale »**. Elles étaient bruitées (une même époque du LSTM : 9,9 s puis 0,9 s). Elles sont **remplacées** par de nouvelles mesures sur secteur (voir l'entrée suivante).
- Allègement du TFT (sans barre de progression, journaux, sauvegardes ni résumé de Lightning) : prévisions et poids identiques au bit près sur données aléatoires, mais aucun gain de temps mesurable (10,7 s contre 11,0 s par époque). Le coût du TFT vient de son calcul. L'allègement est gardé.

### Exceptions datées du 2026-11-16, écrites avant tout entraînement sur les vraies données

- **Plis annuels** : 5 plis de 12 mois, du 2020-01-01 au 2024-12-31, au lieu de 10 plis de 6 mois. La validation interne (6 derniers mois de la fenêtre d'ajustement) et le modèle du test final ne changent pas. Raison : le réentraînement annuel est courant en pratique, et les jours évalués sont les mêmes.
- **Réglage unique** : les hyperparamètres sont réglés une seule fois par actif et par modèle, sur le premier découpage (ajustement du 2018-04-01 au 2019-06-30, validation interne du 2019-07-01 au 2019-12-31), puis figés pour les 5 plis et le test final. Raison : décision prise avec l'information disponible fin 2019, sans regarder l'avenir. Limite : réglage sur peu de données.
- **3 graines** au lieu de 5 : 0, 1 et 2.
- **Optimiseur AdamW** pour tous les modèles de deep learning.
- **XGBoost** suit les mêmes règles : même N, réglé une fois, 3 graines.
- **Budget de 24 heures** pour le deep learning, réparties sur plusieurs nuits grâce à la reprise.
- **Formule de N** : le plus grand entier tel que 2 actifs × somme sur les 5 modèles de (médiane d'une époque × 100) × (N + 3 graines × 6 découpages) ≤ 24 heures. Si N < 5 : arrêt et rapport.
- **Mesures** : 5 répétitions, médiane et écart min-max ; 2 et 4 fils (8 fils écarté, mesuré plus lent).
- **Alimentation** : les scripts d'entraînement et de mesure refusent de démarrer sur batterie, avec un message clair. Si le PC passe sur batterie pendant un calcul, ils s'arrêtent proprement après l'unité en cours, et la reprise permet de continuer. Raison : des temps et un calcul fiables, et pas de calcul interrompu par une batterie vide. Test avec un état d'alimentation simulé, et témoin.
- **Règle de suivi** inchangée : arrêt propre si la durée réelle dépasse l'estimation de plus de 50 %.
- **Tests mis à jour** : 5 plis annuels, séparation des plis, validation interne égale à la seconde moitié du pli précédent, réglage sur le premier découpage, Diebold-Mariano sur les plis réunis, avec des témoins.

## 2026-11-16 — Mesures sur secteur et valeurs fixées

Les chiffres sont lus dans `rapports/mesures_entrainement.json`, généré par `src/mesures.py`. Toutes les mesures sont faites sur des données aléatoires de même forme que les vraies.

### Conditions

- PC sur secteur pendant toutes les mesures (batterie en charge), mode d'alimentation de Windows 11 « Performances optimales » ; le mode de gestion de `powercfg` reste « Balanced ». Chrome allégé.
- Mémoire libre : 2,59 Go au début, 2,95 Go avant les mesures de mémoire, 2,90 Go à la fin.
- Aucune vraie donnée lue : le crochet d'audit refuse toute ouverture dans `data/` et les fonctions de lecture de pandas et pyarrow sont remplacées par un refus, dans le processus principal et dans chaque processus de mesure. Les tests le prouvent, avec un témoin (sans le crochet, la même lecture réussit).

### Temps d'une époque (configuration médiane, 5 répétitions : médiane, min-max)

| Modèle | 2 fils | 4 fils |
|---|---|---|
| LSTM | 0,73 s (0,68 – 0,75) | 0,89 s (0,84 – 1,12) |
| GRU | 2,21 s (2,14 – 2,36) | 3,31 s (2,79 – 3,88) |
| CNN-LSTM | 0,96 s (0,92 – 1,17) | 1,38 s (1,04 – 1,55) |
| Transformer | 2,30 s (2,16 – 2,41) | 2,98 s (2,42 – 3,17) |
| TFT | 8,16 s (8,10 – 9,79) | 10,25 s (9,51 – 12,35) |
| XGBoost (2000 arbres) | 1,68 s (1,54 – 2,05) | 1,38 s (1,17 – 1,75) |

Les 5 répétitions donnent des poids (ou des prévisions pour XGBoost) identiques, pour chaque modèle, TFT compris, avec 2 comme avec 4 fils. Le GRU est plus lent que le LSTM de façon stable ; la cause n'a pas été étudiée.

### Valeurs fixées

- **fils_calcul = 2** : la plus petite somme des médianes des 5 modèles, parmi les nombres de fils reproductibles.
- **seuil_memoire_libre_go = 1,0** : pic de 564 Mo (TFT dans sa plus grande configuration ; Transformer : 353 Mo), × 1,5, arrondi au 0,5 Go supérieur. Inchangé par rapport à la première mesure.
- **budget_reglage = N = 12** :
  - un entraînement de chaque modèle (médiane × 100 époques) : LSTM 73 s, GRU 221 s, CNN-LSTM 96 s, Transformer 230 s, TFT 816 s ; somme 1 436 s ;
  - N = plus grand entier tel que 2 × 1 436 s × (N + 3 × 6) ≤ 86 400 s, soit N + 18 ≤ 30,09, donc **N = 12** ;
  - total estimé : 2 × 1 436 s × 30 = 86 149 s, environ **23,9 heures** de deep learning ; XGBoost en plus, environ 2 minutes.
- `src/regles.py --entrainement` est maintenant accepté ; un témoin vérifie qu'il est refusé si une des trois valeurs redevient « à fixer ». Un test vérifie que les trois valeurs du TOML sont égales à celles du rapport de mesures.

### Reprise et alimentation (test de principe sur de petites données aléatoires)

- Un calcul interrompu exprès, puis relancé, donne des fichiers identiques à un calcul sans interruption ; les unités terminées sont sautées ; l'ordre d'exécution ne change rien ; un fichier abîmé ou un reste de fichier temporaire est recalculé. Témoin : une graine tirée de l'ordre d'exécution donne des fichiers différents.
- Alimentation simulée : refus de démarrer sur batterie ; passage sur batterie pendant le calcul : arrêt propre après l'unité en cours, sans fichier à moitié écrit, puis reprise identique.

### Décisions prises seul

- La perte MSE du TFT est dans son propre fichier (`src/perte_tft.py`) : une classe définie dans une fonction ne peut pas être sauvegardée avec le modèle.
- Le temps retenu pour un réseau est celui de la 2e époque (la 1re contient le démarrage).
- Les manifestes des variables et de l'exploration ont été recalculés, parce qu'ils citent l'empreinte de `config/regles.toml`, qui a changé. Leur contenu est identique : même empreinte de contenu des variables, mêmes figures.
- Un profil rapide du Transformer montre que la génération des masques de dropout est l'opération la plus coûteuse (environ un tiers du temps) ; aucune modification n'en découle. Le mode déterministe de torch n'est pas la cause des temps : 10,5 s sans lui contre 11,4 s avec lui, mesuré sur batterie.

## 2026-11-16 — Précisions écrites avant le calcul des baselines

Écrites et commitées avant tout calcul de baseline, dans `config/regles.toml` (sections `modeles.persistance`, `modeles.garch_precisions`, `modeles.xgboost`, `evaluation.precisions`, compléments de `evaluation.diebold_mariano` et `evaluation.bootstrap`) et dans `docs/REGLES.md` (section 12), avec la raison de chacune.

- **Persistance** : référence descriptive (log RV de J+1 prévu = log RV de J, même correction s²), hors de la sélection et des tests principaux, avec un Diebold-Mariano descriptif de HAR-RV contre elle. Raison : montrer ce qu'apporte HAR-RV par rapport à « ne rien faire ».
- **QLIKE** de Patton ; **Diebold-Mariano** (Newey-West, Harvey-Leybourne-Newbold, Student à T − 1, bilatéral) ; **bootstrap** par blocs mobiles de 20 jours, graine 42, intervalle par percentiles.
- **Prévision d'un modèle réglé** = moyenne des log de ses 3 graines, avec s² mesuré pour elle ; métriques par graine rapportées (moyenne et écart-type). Limite : petit ensemble, léger avantage par rapport à HAR-RV et GARCH ; la même règle s'appliquera au deep learning.
- **GARCH** : log-rendements des variables × 100, moyenne constante ; facteur d'échelle aligné sur les jours ; paramètres figés et mise à jour quotidienne sans réajustement ; variance de départ calculée sur la fenêtre d'ajustement puis fixée explicitement. Limite : la série de rendements contient les effets de la règle de secours.
- **XGBoost** : mêmes 12 combinaisons pour les deux actifs, graines dérivées de l'identifiant, arrêt anticipé sur chaque validation interne, sans normalisation.
- **Modèles du test final** entraînés et enregistrés sans aucune prévision ; **sorties journalières** dans `sorties/`, ignoré par Git.
- **Test de l'avenir modifié des prévisions**, pour les quatre baselines, avec un témoin (GARCH dont la variance de départ utilise toute la série).

## 2026-11-16 — Baselines sur le développement (5 plis annuels)

Les chiffres sont lus dans `rapports/baselines.json` et présentés dans `docs/RESULTATS_BASELINES.md`, tous deux générés par `src/baselines.py`. Aucune prévision n'a été faite sur le test final. Les modèles du test final (HAR-RV, GARCH, 3 XGBoost par actif) sont enregistrés dans `sorties/` (ignoré par Git), avec leurs empreintes dans `rapports/modeles_test_final.json`.

### Décisions prises pendant le calcul

- **GARCH, récurrence faite à la main** : arch estime les paramètres avec la variance de départ (backcast) calculée sur la fenêtre d'ajustement et passée explicitement. Mais sa fonction de prévision recalcule cette variance de départ à partir de la série qu'on lui donne. La récurrence σ²ₜ = ω + α·ε²ₜ₋₁ + β·σ²ₜ₋₁ est donc faite dans `src/baselines.py`, avec le backcast figé. Vérifié : elle redonne les variances d'arch sur la fenêtre d'ajustement, à moins de 2·10⁻¹³ près.
- **Témoin du GARCH à corriger (à valider)** : le témoin demandé (backcast calculé sur toute la série) n'est pas détectable. L'effet de la variance de départ décroît comme β à la puissance du nombre de jours ; avec β ≈ 0,93 et environ 730 jours avant le premier jour évalué, il vaut environ 10⁻²⁴, bien moins que la précision des nombres. Un test le prouve (prévisions identiques au bit près). Le témoin détectable retenu est un GARCH dont le facteur d'échelle est calculé avec les RV² de toute la série, avenir compris : il est bien détecté.
- **Durées hors du JSON** : à une relance, la reprise saute les unités déjà faites ; une durée écrite dans le JSON ne serait donc pas celle du calcul. Les durées sont affichées et notées ici. `rapports/baselines.json` est identique d'une exécution à l'autre, et un calcul complet à neuf (dossier de reprise vide) redonne le même fichier.
- **Rapport généré** : une colonne « significatif à 5 % » accompagne le sens du test de Diebold-Mariano, pour qu'un écart non significatif ne se lise pas comme une victoire.
- **Classement provisoire** : par le QLIKE moyen sur tous les jours évalués des 5 plis réunis.

### Contrôles de bon sens

- **HAR-RV** : coefficients des trois composantes presque toujours positifs (une seule exception : ETH, pli 1, composante mensuelle légèrement négative) ; somme des pentes entre 0,76 et 0,92, donc inférieure à 1 : le modèle revient vers une moyenne.
- **GARCH(1,1)** : α + β égal à 1 (à l'arrondi près) pour BTC dans tous les découpages, et pour ETH dans le pli 1 et le modèle du test final : la persistance de la variance est à la limite de la stationnarité (cas proche d'un IGARCH). Degrés de liberté de la loi de Student entre 2,75 et 3,6 : queues très épaisses. Le facteur d'échelle d'ETH (0,61 à 0,92) montre que la variance GARCH surestime RV² sur la fenêtre d'ajustement.
- **XGBoost** : combinaison retenue, de profondeur 2 pour les deux actifs ; aucun tirage écarté.
- **Vérification de l'exception 2** (moyenne des résidus en log sur la validation interne) : proche de 0 dans les plis 1 à 3 (entre −0,07 et +0,04) et pour le modèle du test final, mais **pas proche de 0 dans les plis 4 et 5** (−0,12 et −0,13 pour BTC ; −0,07 et −0,14 pour ETH) : XGBoost prévoit trop haut sur ces validations. L'affirmation de l'exception 2 (« ŷ sans biais ») n'est donc pas vérifiée partout ; c'est écrit ici, sans rien corriger.
- **Seuil d'alerte** : XGBoost bat HAR-RV de 6,8 % (BTC) et de 0,1 % (ETH) en QLIKE moyen, sous le seuil de 20 % : pas d'arrêt.

### Durées (calcul complet, sur secteur)

- Calcul complet des baselines : 18,9 s pour les deux actifs, dont 11,9 s pour XGBoost (réglage et 3 graines sur 6 découpages). Estimation de l'étape des mesures pour XGBoost : 101 s, calculée avec 2000 arbres sans arrêt anticipé ; l'arrêt anticipé arrête bien avant, d'où l'écart.

### Précision datée du 2026-11-16, décidée APRÈS avoir vu les résultats des baselines : définition du QLIKE moyen

- Dit honnêtement : cette précision a été décidée après avoir vu les résultats des baselines. Elle remplace la phrase « classement provisoire : par le QLIKE moyen sur tous les jours évalués réunis » écrite plus haut dans cette entrée.
- Les deux définitions sont calculées et rapportées : QLIKE moyen sur tous les jours évalués réunis, et moyenne des QLIKE moyens par pli. Si elles donnent des classements différents, la définition littérale de la règle (« QLIKE moyen sur les plis », c'est-à-dire la moyenne des moyennes par pli) s'applique (`evaluation.selection.qlike_moyen` dans `config/regles.toml`).
- Résultat sur les baselines : les deux définitions donnent le même classement pour chaque actif (lu dans `rapports/baselines.json`, champ `classement.identiques`).

### Rectification de l'exception 2 (2026-11-16)

L'affirmation selon laquelle le biais de s² désavantage les modèles réglés n'est vérifiée que pour les plis 1 à 3. Dans les plis 4 et 5, XGBoost prévoit trop haut sur la validation interne (moyenne des résidus de −0,07 à −0,14). L'affirmation est retirée. Explication probable, non démontrée : un modèle à arbres ne peut pas prévoir sous les valeurs vues à l'apprentissage, et ces validations tombent sur des périodes calmes.

- Les valeurs sont lues dans `rapports/baselines.json` (champ `controles.xgboost_validation`) et reprises dans `docs/RESULTATS_BASELINES.md`, section « Vérification de l'exception 2 ».
- L'exception 2 elle-même (s² mesuré sur la validation interne, qui sert aussi au réglage) reste en vigueur ; seule l'affirmation sur le sens de son effet est retirée. L'historique n'est pas réécrit : l'entrée d'origine reste plus haut.

## 2026-11-19 — Étape 6, phase A : code du deep learning, vérifié avant le long calcul

Le code (`src/entrainer.py`, `src/reseaux.py`, `src/suivi.py`) est construit, testé et commité avant tout entraînement long. La phase B (réglage, puis plis) sera lancée à part. Le test final reste fermé : les modèles du test final seront entraînés, sans aucune prévision sur le test.

### Choix techniques

- **Données** : les séquences utilisent les variables de TOUS les jours (série remplacée par la règle de secours), y compris les jours dont la cible n'est pas valide ; seuls les exemples à cible valide servent à apprendre et à évaluer.
- **Normalisation** par découpage : entrées sur les jours d'origine jusqu'à la dernière origine de l'ajustement ; cible sur les exemples d'ajustement ; enregistrée en JSON dans `sorties/`.
- **TFT** : la série « y » de l'encodeur est le log de RV de la série remplacée (égale à la vraie valeur les jours valides) ; les échantillons ne gardent que les jours prédits à cible valide ; seul le jour de la semaine est connu pour le jour prédit. Les meilleurs poids sont gardés en mémoire (aucun fichier de sauvegarde de Lightning).
- **Réseaux torch** : meilleurs poids sur la validation interne gardés en mémoire, puis rechargés.
- **Tirage des combinaisons** : la fonction de tirage d'XGBoost a été rendue générale (`tirer_dans_espace`), pour une seule source ; le GRU a le même espace que le LSTM, donc les mêmes 12 combinaisons.
- **Règle de suivi** : vérifiée avant chaque nouvelle unité, sur le temps réel cumulé des unités terminées comparé à leur estimation (médiane d'une époque × 100) ; arrêt propre au-delà de +50 %. Journal dans `sorties/deep_learning/journal.json`, lu par `src/suivi.py`.
- **Options d'essai** (`--combinaisons`, `--epoques-max`, `--graines`, `--decoupages`) : réservées à l'essai à blanc ; les valeurs par défaut sont celles des règles.

### Tests (données synthétiques, 2 époques)

- Test de l'avenir modifié pour chacun des 5 réseaux : 0 écart au bit près. Témoin : une séquence qui se termine à J+1 est détectée.
- Déterminisme : la même unité deux fois donne les mêmes poids et les mêmes prévisions (LSTM, Transformer, TFT).
- Reprise : interruption puis relance, fichiers identiques.
- Règle de suivi : déclenchée au-delà de +50 % (temps simulé), avec la 1re unité gardée.
- TFT : seul le jour de la semaine de la cible est connu pour le jour prédit ; encodeur de 30 jours.

### Essai à blanc sur les vraies données (développement)

1 combinaison, 2 époques, 1 graine, premier découpage, 5 réseaux, 2 actifs, dans un dossier supprimé ensuite. Les deux phases fonctionnent de bout en bout (réglage : 34 s ; plis : 33 s).

- Premier découpage (448 exemples d'ajustement pour BTC) : temps par époque de 0,09 s (LSTM) à 4,28 s (TFT), tous sous la mesure.
- Plus grand découpage (modèle du test final, 2 257 exemples d'ajustement), 2e époque, BTC, avec la combinaison de l'essai : LSTM 0,23 s, GRU 0,59 s, CNN-LSTM 0,83 s, Transformer 1,74 s, TFT 9,66 s. Mesures sur données aléatoires (2 441 exemples, configuration médiane) : 0,73 ; 2,21 ; 0,96 ; 2,30 ; 8,16 s.
- Lecture : sur le plus grand découpage, seul le TFT dépasse la mesure (+18 %) ; les autres découpages sont plus petits. Le risque principal pour la règle de suivi est un TFT qui s'entraîne longtemps (jusqu'à 200 époques) avec une grande combinaison.
