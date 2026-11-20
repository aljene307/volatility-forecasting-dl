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

## 2026-11-19 — Précision écrite avant de lire les résultats du deep learning, et limites du réglage

La phase B (réglage, puis plis) est terminée. Cette entrée est écrite et commitée AVANT toute lecture des résultats du deep learning sur les plis (aucune prévision, aucune métrique des plis n'a été regardée). Le test final reste fermé.

### Précision : tests multiples (méthode de Holm)

- Par actif, 7 modèles sont comparés à HAR-RV (GARCH, XGBoost, LSTM, GRU, CNN-LSTM, Transformer, TFT). Avec 7 tests au seuil de 5 %, un résultat « significatif » peut apparaître par hasard bien plus souvent qu'une fois sur 20.
- Les p-valeurs de Diebold-Mariano sont donc rapportées brutes ET ajustées par la méthode de Holm, sur la famille des 7 comparaisons contre HAR-RV de chaque actif (plis réunis). Les phrases « significatif » de la lecture des résultats s'appuient sur les p-valeurs ajustées (`evaluation.tests_multiples` dans `config/regles.toml`, section 13 des règles).
- Décision prise seul (à valider) : le test descriptif de HAR-RV contre la persistance reste hors de la famille, puisqu'il est descriptif et ne compare pas un modèle à HAR-RV. Le test final n'est pas concerné par cette précision : sa règle sera écrite avant son ouverture.
- Les p-valeurs des baselines déjà publiées dans `docs/RESULTATS_BASELINES.md` restent brutes (3 tests à l'époque) ; leurs valeurs ajustées sur la famille de 7 tests figureront dans la comparaison de tous les modèles.
- Décision prise seul (à valider) : `rapports/baselines.json` et `rapports/exploration.json` citent l'empreinte de `config/regles.toml` d'avant cette précision. Ils ne sont pas recalculés : l'empreinte citée est celle des règles en vigueur au moment de leur calcul, et la précision n'ajoute qu'une section sans effet sur eux.

### Limites du réglage (constatées à la lecture de `reglage.json`, avant les plis)

- **Une seule graine par combinaison** : le choix de la combinaison est en partie dû au hasard de l'entraînement. Les écarts entre la 1re et la 2e combinaison sont parfois minuscules en MSE de validation sur log(RV) : Transformer ETH 0,1050 contre 0,1051 ; Transformer BTC 0,1057 contre 0,1061 ; LSTM ETH 0,1101 contre 0,1106. Une autre graine pourrait inverser ces classements.
- **Combinaisons au bord des espaces de recherche** : dropout 0,3 (le maximum) retenu 8 fois sur 10, sans être systématiquement le meilleur (des tirages à 0,3 se classent aussi 11e ou 12e sur 12) ; taux d'apprentissage du LSTM et du GRU sur BTC à 97 % de l'intervalle en échelle log (près de 3e-3) ; taille maximale retenue pour le TFT (hidden_size 32) et le CNN-LSTM (64 neurones, 32 filtres) sur les deux actifs. Piste d'amélioration : des espaces plus larges. Les espaces ne sont PAS modifiés (ils sont écrits d'avance).
- Aucune MSE NaN ; aucune meilleure époque inférieure à 6 ; aucune unité au plafond de 200 époques.
- Durée réelle du réglage : 54,5 min contre 9,6 h estimées (rapport 0,095). L'estimation supposait 100 époques par unité (67 en moyenne en réalité) et des temps mesurés sur 2 441 exemples (448 dans le premier découpage).

## 2026-11-19 — Étape 6, phase C : évaluation du deep learning et comparaison de tous les modèles

Les chiffres sont lus dans `rapports/comparaison_modeles.json` et présentés dans `docs/RESULTATS_DL.md`, tous deux générés par `src/comparer.py`. Ce script n'entraîne rien : il relit les unités déjà calculées (baselines et réseaux, dans `sorties/`, ignoré par Git). Aucune prévision n'a été faite sur le test final ; les 30 modèles du test final (5 réseaux × 3 graines × 2 actifs) sont enregistrés, avec leurs empreintes dans `rapports/modeles_deep_learning.json`.

### Décisions prises seul (à valider)

- **Seuil d'alerte de 20 %** : il venait de la consigne de l'étape. Il a d'abord été écrit comme constante dans `src/comparer.py`, puis déplacé dans `config/regles.toml` (section `evaluation.controles_fuite`, précision du 2026-11-19, sans effet sur les calculs). Il est vérifié avec les deux définitions du QLIKE moyen, AVANT toute écriture de fichier. Résultat : aucun réseau ne dépasse le seuil (le plus grand gain est lu dans le rapport généré).
- **Baselines relues, pas recalculées** : leurs métriques sont recalculées à partir de leurs unités de reprise et comparées à `rapports/baselines.json` ; écart maximal : 0 (tolérance 1e-9).
- **Cible des réseaux** : reprise dans les unités des baselines, avec un contrôle que les dates de validation et d'évaluation des réseaux sont exactement les mêmes (témoin : une date décalée est détectée).
- **Meilleur réseau de la figure** : le premier réseau du classement appliqué (moyenne des QLIKE moyens par pli).
- **Manifeste des poids** : empreinte de chaque fichier de poids recalculée et comparée à celle enregistrée dans l'unité au moment de l'entraînement ; le manifeste contient aussi les empreintes des normalisations et de `reglage.json`.
- **Temps de la phase « plis »** : repris du journal du calcul (fixé une fois le calcul terminé), donc le JSON reste identique d'une exécution à l'autre (vérifié : deux exécutions, fichiers identiques octet par octet).
- **Phrase sur le biais de validation** : la lecture des résultats signale un réseau dès qu'une moyenne des résidus en log sur la validation interne dépasse 0,1 en valeur absolue. Ce seuil de 0,1 est un choix de présentation, pris seul, sans effet sur aucun calcul.
- **README** : la phrase « Aucun résultat n'est encore disponible », devenue fausse depuis l'étape 5, est remplacée.

### Contrôles

- Aucune prévision non finie ; aucune unité au plafond de 200 époques. Quelques graines ont leur meilleure époque très tôt (5 au plus tôt : GRU BTC pli 4, TFT ETH pli 3), sans MSE de validation anormale par rapport aux autres graines.
- Méthode de Holm : vérifiée à la main et identique à celle de statsmodels (20 tirages de 7 p-valeurs) ; témoin : p-valeurs ajustées différentes des brutes.
- Aucune date de 2025 ou 2026 dans les fichiers générés ; la garde du test aveugle est appelée sur chaque série.

### Contrôles de fuite sur les vraies données (précision du 2026-11-19, section 14 des règles)

Les règles de ces contrôles (découpage, jour J, critère d'arrêt) ont été écrites dans `config/regles.toml` AVANT de les lancer ; dit honnêtement, elles sont commitées dans le même commit que les résultats, avec l'accord donné pour ce commit. Résultats lus dans `rapports/controles_fuite.json`, généré par `src/controles_fuite.py` (environ 2 minutes pour les deux actifs, sur secteur).

- **Avenir modifié (point 1)** : pli 5, J = 2024-07-01, 2 époques, pour les 5 réseaux et les 2 actifs : **0 écart** sur 368 prévisions des origines ≤ J (validation interne et première moitié de la période évaluée). Contrôle d'effet : les 182 prévisions après J ont toutes changé. Le premier lancement s'est arrêté sur une erreur de programmation de ma part (mauvais argument passé à la vérification), après les 5 réseaux de BTC (déjà 0 écart) ; corrigée, puis tout relancé.
- **Témoin « cible mélangée » (point 2)** : LSTM, combinaison retenue, graine 0, 5 plis, cibles d'ajustement permutées. Gain sur HAR-RV en moyenne par pli : **−91,8 % pour BTC et −147,9 % pour ETH** (jours réunis : −91,6 % et −147,6 %) : bien moins bon que HAR-RV, comme attendu. Le témoin ne montre aucun chemin par lequel la cible atteindrait le réseau sans passer par l'apprentissage.
- **Robustesse (point 3, descriptif, sans effet sur le classement ni la sélection)**, dans `docs/RESULTATS_DL.md` :
  - gain de chaque graine seule : pour ETH, chaque graine de chaque réseau bat HAR-RV ; pour BTC aussi, sauf une graine du TFT. L'effet d'ensemble (gain de la moyenne des graines moins la moyenne des gains des graines seules) va de 0,8 à 2,3 points pour le LSTM, le GRU, le CNN-LSTM et le Transformer, et il est le plus grand pour le TFT ;
  - gain pli par pli : le gain des réseaux n'est pas régulier ; il est négatif en 2020 pour presque tous les réseaux et le plus grand en 2024 (de l'ordre de 30 % en 2024 pour chacun des 5 réseaux, sur les deux actifs). XGBoost suit la même tendance. Le seuil d'alerte s'applique au QLIKE moyen, pas à une année seule : il n'est pas déclenché ; c'est signalé ici pour la lecture.
- Décisions prises seul (à valider) : critère « régulier » = gain positif chaque année de 2020 à 2024 ; sinon « pas régulier », avec les années positives et négatives ; la phrase sur l'année du plus grand gain est donnée comme explication possible, non démontrée. Le gain par graine est mesuré avec la moyenne des QLIKE moyens par pli (définition appliquée par la règle de sélection).
- Recherche des mots interdits : le numéro du dossier personnel du PC n'est plus cherché qu'en dehors d'un nombre (il apparaissait par hasard au milieu d'un taux d'apprentissage décimal) ; témoins : un chemin qui le contient est trouvé, un nombre décimal qui le contient ne l'est pas.

## 2026-11-19 — Étape 7 : sensibilité sans 2024, puis stratégie de volatility targeting (développement)

Le test final reste fermé. Chiffres lus dans `rapports/comparaison_modeles.json` et `rapports/strategie.json`, présentés dans `docs/RESULTATS_DL.md` et `docs/STRATEGIE.md` (générés).

### Sensibilité sans 2024 (décidée APRÈS avoir vu les gains par année)

- Dit honnêtement : cette analyse a été décidée après avoir vu que le gain des réseaux était le plus grand en 2024. Elle est descriptive et ne change ni le classement ni la sélection (le Transformer reste retenu pour BTC, le CNN-LSTM pour ETH).
- Résultat : sans 2024, les gains des réseaux sur HAR-RV restent positifs mais plus petits, et **aucun réseau ne fait significativement mieux que HAR-RV après ajustement de Holm**, sur aucun des deux actifs. L'avantage significatif constaté sur les 5 années dépend donc en partie de 2024.
- Calibration de HAR-RV par année : sur l'échelle de la variance (rapport moyen RV²/h), 2024 est l'année où HAR-RV surestime le plus, pour les deux actifs ; en log (avant la correction s²), non : l'année la plus basse est 2023.
- Erreur corrigée avant le commit : une première version comparait la moyenne des résidus « après correction s² ». Cette mesure est négative par construction (la correction relève volontairement la prévision pour viser la moyenne de RV² et non sa médiane) et conduisait à une phrase fausse. Elle est remplacée par le rapport moyen RV²/h.

### Stratégie : précisions écrites avant le calcul (section 15 des règles)

- **Jours non valides** : 15 par actif entre 2020 et 2024, les mêmes pour BTC et ETH, exactement les jours sans prévision. Problème de définition : la série remplacée y donne un rendement nul, et le lendemain porte un rendement sur deux jours ; une décision « à la clôture » d'un jour incomplet n'a pas de sens. Solution retenue, la plus prudente : aucune décision un jour non valide, l'exposition de la dernière clôture valide reste en place ; le mouvement sur deux jours est donc porté par une exposition décidée avant tout ce mouvement. Pour la VaR, le jour non valide et son lendemain sont exclus (30 jours par actif).
- Décisions prises seul (à valider), toutes écrites dans `config/regles.toml` avant le calcul et commitées avec les résultats : exposition initiale nulle (l'entrée paie des frais, achat simple compris) ; frais proportionnels à la valeur du portefeuille ; dérive du poids entre deux rééquilibrages ignorée (limite) ; quantile exact de la loi normale pour la VaR ; seuil de présentation de ±10 % pour dire « proche de la cible ».
- Ajouté pendant le calcul : une colonne « frais par an » (coût moyen en points de rendement), parce que les frais totaux, exprimés en part du capital de départ, grossissent avec la valeur du portefeuille et se lisaient mal.
- Erreur corrigée avant le commit : la première phrase générée sur Kupiec attribuait les rejets aux « queues épaisses » (trop de dépassements), alors que tous les taux de dépassement sont sous 5 % : la VaR est trop prudente. La phrase suit maintenant le sens des rejets.

### Résultats (lus dans le rapport généré)

- Les stratégies pilotées par HAR-RV et par le modèle retenu réduisent un peu le drawdown maximal par rapport à l'achat simple, mais ont un Sharpe plus bas que l'achat simple sur la période (marché très haussier).
- La différence de Sharpe entre le modèle retenu et HAR-RV est négative pour les deux actifs, avec un intervalle bootstrap qui contient 0.
- Le classement par Sharpe ne suit pas le classement par QLIKE (corrélation de rang négative pour les deux actifs ; GARCH(1,1) a le meilleur Sharpe). Explication possible, non démontrée : GARCH change moins souvent d'exposition (rotation plus faible, donc moins de frais).
- VaR : taux de dépassement sous 5 % pour tous les modèles ; Kupiec rejette surtout pour trop PEU de dépassements.
- Durée : environ 23 s pour la stratégie des deux actifs ; deux exécutions donnent des fichiers identiques.

## 2026-11-19 — Étape 8 : règles de l'explicabilité, écrites et commitées avant tout calcul

Retour à la méthode stricte : ces règles (`explicabilite.precisions` dans `config/regles.toml`, section 16 des règles) sont commitées et poussées dans un commit séparé, AVANT tout calcul d'explicabilité sur les vraies données.

- **Choix de la méthode pour les réseaux : GradientExplainer.** DeepExplainer de shap ne sait pas propager ses règles à travers les couches LSTM ni à travers l'attention écrite à la main avec torch. GradientExplainer (gradients espérés) n'a besoin que du gradient : il fonctionne avec le LSTM, le CNN-LSTM et le Transformer. C'est une approximation par tirages : l'additivité n'est vérifiée qu'à une tolérance près.
- **Mesure faite avant d'écrire les règles, sur des données ALÉATOIRES seulement** (aucune vraie donnée lue ; 365 séquences à expliquer, fond de 100, réseaux aux configurations retenues, 2 fils) : erreur relative moyenne d'additivité de 7,6 à 9,0 % avec 200 tirages, de 3,6 à 3,7 % avec 1000 tirages ; temps de 113 à 192 s par modèle avec 1000 tirages. D'où 1000 tirages et une tolérance de 0,06.
- **Temps estimé** : 60 modèles à expliquer par SHAP (2 actifs × 2 réseaux × 5 plis × 3 graines), soit environ 2,5 heures, avec la reprise après interruption ; XGBoost, l'attention et la fidélité sont rapides.
- Décisions prises seul (à valider) : contributions des réseaux remises en unités de log(RV) (× écart-type de la cible du pli) pour être comparables à XGBoost ; importance = moyenne des valeurs absolues puis somme ; XGBoost expliqué par TreeExplainer exact, sans fond, sur ses modèles des plis ré-entraînés à l'identique (ils n'avaient pas été enregistrés), avec un contrôle de reproduction à 1e-9 ; pour la fidélité, la même suite de 20 permutations sert à la meilleure et à la moins bonne variable (comparaison appariée) ; seuil du témoin de bruit : moins de 1 % de la dégradation de la meilleure variable.

## 2026-11-19 — Étape 8 : résultats de l'explicabilité (développement)

Calcul fait après le commit des règles (e158870). Chiffres lus dans `rapports/explicabilite.json`, présentés dans `docs/EXPLICABILITE.md` (généré par `src/explicabilite.py`). Le test final reste fermé.

- **Calcul** : 130 unités (65 par actif) en 1 h 51 sur secteur, sans arrêt. Reproduction : écart nul entre les modèles expliqués et les prévisions des unités (réseaux rechargés, XGBoost ré-entraîné, TFT reconstruit). Additivité : erreur relative maximale de 5,5 % pour les réseaux (tolérance 6 %, proche de la limite), écart maximal de 1e-5 pour XGBoost. Deux exécutions de l'agrégation donnent des fichiers identiques.
- **Fidélité** : LSTM, Transformer (BTC) et CNN-LSTM (ETH) fidèles sur 5 plis sur 5. **XGBoost fidèle sur 2 plis sur 5 (BTC) et 3 plis sur 5 (ETH)** : sur les autres plis, permuter sa meilleure variable SHAP améliore même le QLIKE de validation. Conformément à la règle, c'est écrit honnêtement : SHAP échoue à expliquer XGBoost sur ces plis. Explication possible, non démontrée : les mesures de volatilité sont très corrélées entre elles.
- **Jour de la semaine** en tête ou en 2e position pour les réseaux, confirmé par la permutation (c'est la meilleure variable de plis fidèles, avec les plus fortes dégradations sur les validations internes des plis 4 et 5, c'est-à-dire les seconds semestres de 2022 et de 2023). HAR-RV n'utilise pas le jour de la semaine : explication possible, non démontrée, d'une partie du gain des réseaux. Limite écrite : son importance SHAP additionne 7 colonnes.
- **Attention** : presque uniforme pour le Transformer et le TFT (au plus 3,6 à 3,9 % par retard, contre 3,3 % si tous les retards pesaient autant) ; l'écart entre jours de crise et autres jours est faible. SHAP du Transformer, lui, place 62 % de l'importance sur le retard 1 (BTC). Limite rappelée : l'attention montre où le modèle regarde, pas nécessairement pourquoi il décide.
- Décisions prises seul pendant le calcul (à valider) : phrases générées ajoutées après avoir vu les résultats, toutes conditionnées par les valeurs et sans effet sur les calculs (jour de la semaine et codage one-hot ; amélioration du QLIKE quand on permute la meilleure variable d'XGBoost ; attention presque uniforme, seuil de présentation 1,5 fois l'uniforme ; double présence du log RV du jour dans le TFT).

## 2026-11-19 — Étape 9A : règles de HAR-J et de l'ouverture du test final, écrites avant tout calcul

Commit séparé, poussé AVANT le calcul de HAR-J et avant l'écriture du programme d'ouverture. Le test final reste fermé : aucune valeur de 2025-2026 n'est lue ni affichée dans cette étape.

- **HAR-J** (`modeles.har_j`) : déclaré avant l'ouverture, à cause de l'explicabilité (les réseaux s'appuient sur le jour de la semaine). Descriptif : hors de la sélection et hors de la famille de Holm principale. Décision prise seul (à valider) : lundi comme modalité de référence.
- **Attentes** (`config/attentes_test.toml`, `docs/ATTENTES_TEST.md`) : le texte des hypothèses H1 à H6 et de la prévision est celui de la consigne. Décisions prises seul (à valider), pour rendre chaque verdict calculable sans ambiguïté : H1 est jugée pour chaque actif (moyenne de d négative et p-valeur ajustée sous 0,05) ; H2, H3 et H6 sont jugées sur les QLIKE moyens du test (Diebold-Mariano rapporté à titre descriptif pour H2 et H3) ; H5 demande les deux conditions à la fois ; la famille de Holm sur 7 comparaisons est rapportée à titre descriptif sur le test (la précision du 2026-11-19 sur Holm renvoyait la règle du test final à ce moment).
- **Ouverture** (`test_final`) : un seul chemin (`src/ouvrir_test.py`), quatre préconditions, aucun réentraînement, résultats en création exclusive, vérification sur 2024 dans un fichier différent. Décision prise seul (à valider) : les données sont coupées à la fin de la période évaluée, dans les deux modes (en vérification, aucune bougie de 2025 n'entre dans le calcul).

## 2026-11-19 — Étape 9A : HAR-J sur le développement et programme d'ouverture (test toujours fermé)

Calcul fait après le commit des règles et des attentes (96b896d). Aucune valeur de 2025-2026 n'a été lue ni affichée.

### HAR-J (descriptif)

- Calculé par `src/har_j.py` sur les 5 plis et le découpage du test final (sans aucune prévision sur le test) ; intégré à `src/comparer.py` comme modèle descriptif. Résultats dans `docs/RESULTATS_DL.md`, section « HAR-J ».
- HAR-J fait mieux que HAR-RV de 9,9 % (BTC) et 7,5 % (ETH) en QLIKE moyen par pli : le seul ajout du jour de la semaine de la cible apporte une grande partie de ce que les réseaux gagnaient sur HAR-RV. Le gain des réseaux sur HAR-J reste positif pour tous sur ETH et pour tous sauf le TFT sur BTC, mais il est plus petit (le modèle retenu : 4,2 % pour le Transformer sur BTC, 8,6 % pour le CNN-LSTM sur ETH, contre 13,6 % et 15,4 % sur HAR-RV).
- Contrôle : les 2 720 valeurs déjà publiées dans `rapports/comparaison_modeles.json` sont inchangées après l'ajout de HAR-J (comparaison valeur par valeur) ; les fichiers qui citent son empreinte (`strategie.json`, `explicabilite.json`) ont été régénérés, et seule cette empreinte y change.
- Modèle HAR-J du test final enregistré dans `sorties/` ; empreinte dans `rapports/modele_har_j.json`.

### Programme d'ouverture (`src/ouvrir_test.py`)

- Deux modes, une seule chaîne : `--verification` (2024, modèles du pli 5, garde fermée) et `--ouvrir` (test final, une seule fois, après accord explicite). Sans option, le programme n'ouvre rien.
- Garde (`src/garde.py`) : une seule porte privée, qui ne s'ouvre que si elle est appelée par la fonction `_chaine_sur_le_test_ouvert` de `src/ouvrir_test.py`, et seulement pendant ce bloc ; testée avec des témoins (appel depuis un test refusé ; fonction du même nom ailleurs refusée ; porte refermée après le bloc ; aucun autre fichier de `src/` ne l'utilise). Le test « aucune option de contournement » de la garde passe toujours.
- Décisions prises seul (à valider) :
  - en plus des préconditions écrites, le programme vérifie que le modèle retenu des attentes est celui de la règle de sélection, et il contrôle AVANT toute ouverture que les modèles du test final, chargés depuis leurs fichiers, redonnent exactement leurs prévisions de validation (2024-07-01 à 2024-12-31, développement). Ce contrôle a été ajouté parce que la vérification sur 2024 n'utilise pas ces fichiers : un défaut de chargement (par exemple d'un XGBoost enregistré) ne serait apparu qu'à l'ouverture ;
  - en vérification, les XGBoost du pli 5 (jamais enregistrés) sont ré-entraînés à l'identique ; tous les autres modèles sont chargés ;
  - la stratégie de la vérification commence avec une exposition nulle au 2024-01-01, comme le test commencera au 2025-01-01 : ses expositions jour par jour doivent être identiques à celles de la stratégie du développement ; seuls les frais du premier jour diffèrent (entrée depuis 0 contre ajustement depuis l'exposition du 2023-12-31), c'est attendu et rapporté ;
  - `src/strategie.py` accepte des bougies déjà coupées (argument facultatif, sans effet sur le calcul par défaut : `strategie.json` ne change que par l'empreinte citée).
- Essai de la chaîne sur 2024 sans les préconditions (avant le commit, garde fermée) : écart nul sur toutes les métriques, toutes les expositions et toutes les prévisions de validation ; modèles du test final : écart nul sur leur validation.

### Mode `--verification` officiel (après le commit 24fe5b4, dépôt propre et poussé)

- Résultat dans `rapports/verification_test_2024.json` : **conforme**. Préconditions passées ; 74 empreintes vérifiées (modèles et normalisations du test final et du pli 5) ; modèles du test final : écart nul sur leur validation ; 366 jours de 2024 par actif, aucun en crise.
- QLIKE, RMSE, MAE et nombre de jours des 10 modèles (persistance, HAR-RV, HAR-J, GARCH, XGBoost, 5 réseaux), pour les deux actifs : **écart nul** avec les chiffres publiés pour 2024 (pli 5 de `rapports/comparaison_modeles.json`).
- Stratégie : expositions jour par jour identiques (écart nul) à celles de la stratégie du développement ; volatilité, drawdown et Sharpe de 2024 ne diffèrent qu'à la 4e décimale, à cause des seuls frais d'entrée du premier jour, comme prévu.
- Les verdicts H1 à H6 calculés sur 2024 ne sont qu'un essai du programme : ils ne disent rien du test final.
- Durée : 25 s. Le fichier `rapports/test_final.json` n'existe pas : le test final reste fermé.

## 2026-11-19 — Ajout de H7 aux attentes, avant l'ouverture du test

- **Dit honnêtement** : H7 et la seconde prévision chiffrée ont été décidées APRÈS avoir vu les résultats de HAR-J sur le développement, et AVANT toute ouverture du test. H1 reste l'hypothèse principale ; la règle de sélection ne change pas. Texte dans `config/attentes_test.toml` (sections `H7` et `prevision_har_j`) et `docs/ATTENTES_TEST.md`.
- **Conclusion descriptive sur HAR-J** (développement, QLIKE moyen par pli, chiffres lus dans `rapports/comparaison_modeles.json`) : HAR-J fait 9,9 % (BTC) et 7,5 % (ETH) de mieux que HAR-RV ; le modèle retenu fait 13,6 % (Transformer, BTC) et 15,4 % (CNN-LSTM, ETH) de mieux que HAR-RV, mais seulement 4,2 % et 8,6 % de mieux que HAR-J. Le jour de la semaine de la cible, ajouté seul à HAR-RV, comble environ 72 % (BTC) et 49 % (ETH) de l'écart entre HAR-RV et le modèle retenu. Part = (QLIKE de HAR-RV − QLIKE de HAR-J) / (QLIKE de HAR-RV − QLIKE du modèle retenu).
- Le README reçoit cette conclusion dans un bloc GÉNÉRÉ par `src/comparer.py` à partir du JSON (aucun chiffre tapé à la main) ; un test vérifie que le bloc du README est exactement celui que donne le JSON.
- `src/ouvrir_test.py` calcule et juge H7 (Diebold-Mariano du modèle retenu contre HAR-J, Holm sur les 2 actifs) et la seconde prévision ; testé avec des résultats fictifs et des témoins (modèle retenu moins bon que HAR-J ; aucun écart net).
- Mode `--verification` relancé après le commit 0359186 (dépôt propre et poussé) : toujours **conforme**, écart nul sur les métriques et les expositions ; le verdict H7 calculé sur 2024 figure dans `rapports/verification_test_2024.json`, à titre de vérification du programme seulement (il ne dit rien du test). Le fichier `rapports/test_final.json` n'existe pas.

## 2026-11-19 — Ouverture du test final

- **Ouverture** : le 2026-11-19 à 20:12:22, par l'auteur, avec `src/ouvrir_test.py --ouvrir`, une seule exécution, avec le code du commit f5259b6. Intégrité contrôlée avant toute analyse : le fichier contient l'identifiant f5259b6 (égal au commit de HEAD), il a été modifié 0,9 s après l'horodatage d'ouverture qu'il contient et plus jamais ensuite, les empreintes des attentes et des règles qu'il cite sont celles du commit, 42 empreintes de modèles et de normalisations ont été vérifiées. `rapports/test_final.json` a été commité seul et poussé tel quel (commit 15cb1fe), avant toute autre analyse.
- **Aucun modèle, aucune règle, aucun réglage modifié** après l'ouverture. Les figures du test ont été produites par le seul chemin qui lève la garde (`src/ouvrir_test.py --figures`, commit 2e8f753) : il refuse si les résultats publiés ne sont pas intacts, recalcule la même chaîne sans modifier aucun modèle, et refuse de tracer si les résultats recalculés diffèrent des résultats publiés. Résultat : 0 écart.
- **Verdicts** (lus dans `rapports/test_final.json`, présentés dans `docs/RESULTATS_TEST.md`) : H1 à H7 **confirmées pour les deux actifs**.
  - H1 : Transformer (BTC) et CNN-LSTM (ETH) font mieux que HAR-RV, p-valeurs ajustées < 0,0001.
  - H7 : confirmée pour ETH (p-valeur ajustée 0,0018) et **de justesse pour BTC** (p-valeur ajustée 0,0483, pour un seuil de 0,05).
  - H2, H3, H4, H5, H6 : confirmées pour les deux actifs ; pour H5, la réduction du drawdown maximal est petite (moins de 3 points).
- **Ce qui a démenti les attentes** :
  - les deux prévisions chiffrées ont **sous-estimé** les gains : gain du modèle retenu sur HAR-RV de 32,2 % (BTC) et 28,3 % (ETH), au-dessus de l'intervalle prévu de 0 à 15 % ; gain sur HAR-J de 11,1 % et 13,9 %, au-dessus de l'intervalle prévu de 0 à 9 ;
  - H7 était annoncée « probablement non significative » : elle est significative pour les deux actifs (de justesse pour BTC) ;
  - sur BTC, le plus petit QLIKE du test est celui du LSTM, pas celui du Transformer retenu (écart très petit) ; la sélection, faite sur le développement, ne change pas.
- **Ce qui a confirmé les attentes** : la hiérarchie persistance > HAR-RV > HAR-J > réseaux en QLIKE, la faiblesse du GARCH, la VaR de HAR-RV non rejetée, et le fait que le jour de la semaine (HAR-J) explique une partie de l'avantage des réseaux (H6).
- **Stratégie** : rendement annualisé négatif sur le test pour l'achat simple et pour les stratégies (marché en baisse) ; volatilité et drawdown un peu plus faibles avec la stratégie ; pour ETH, le Sharpe de la stratégie du CNN-LSTM est plus bas que celui de HAR-RV, avec un intervalle bootstrap qui ne contient pas 0 (descriptif).
- **Décisions prises seul (à valider)** :
  - rapport et section du README générés depuis `rapports/test_final.json` seul (`src/resultats_test.py`), avec un test d'égalité et un témoin ; un verdict « confirmé de justesse » est écrit quand la p-valeur ajustée est au-dessus de la moitié du seuil ;
  - figures produites par un mode `--figures` ajouté au programme d'ouverture après l'ouverture (code commité et poussé avant de l'exécuter), et non par un autre chemin ;
  - la phrase « Le test final reste fermé » des étapes 5 à 8 du README est conservée : elle décrit l'état à chacune de ces étapes ; le statut en tête du README est mis à jour.

## 2026-11-19 — Étape 10A : règles de l'API, écrites et commitées avant le code

Section `api` de `config/regles.toml` et section 18 des règles, commitées et poussées AVANT tout code d'API.

- Modèles servis : les modèles retenus, 3 graines du découpage du test final, en ONNX (ancien exportateur), avec normalisations et s² ; prévision comme dans le projet ; aucune donnée Binance téléchargée ni diffusée ; exemple synthétique seulement.
- Installé dans `.venv` (autorisé sans arrêt) : fastapi 0.165.0, uvicorn 0.54.0, httpx 0.28.1 (pour le client de test), avec leurs dépendances ; un essai à blanc (`pip install --dry-run`) a montré qu'aucun paquet déjà installé n'était mis à jour ; `pip check` : aucun conflit.
- Décision prise seul (à valider) : l'utilisateur donne le jour de la semaine du DERNIER jour (lundi = 0) ; les 30 jours étant consécutifs, le jour de la semaine de chacun s'en déduit.

## 2026-11-19 — Étape 10A : code de l'API (après le commit des règles dd55c85)

- **Export** (`src/exporter_onnx.py`) : empreintes des poids vérifiées, puis export des 6 réseaux (3 graines × 2 modèles retenus) avec l'ancien exportateur (opset 17). Écart maximal onnxruntime / torch sur des entrées aléatoires (sortie normalisée) : de 2,7e-7 à 4,8e-7. Un avertissement de torch prévient qu'un LSTM exporté avec un lot de taille variable peut poser problème : vérifié sans problème sur des lots de 64 et de 1. Deux exports successifs donnent des fichiers identiques octet par octet. s² recalculé sur la validation interne du découpage du test final pour la prévision moyenne des 3 graines, comme dans le projet.
- **Test clé** (client HTTP de test, 184 jours de la validation interne 2024-H2 par actif, développement) : écart maximal API / torch en log de 3,3e-7 (BTC) et 3,2e-7 (ETH), sous la tolérance de 1e-5 ; écart entre la prévision moyenne de l'API et onnxruntime appelé directement : nul (tolérance 1e-9). Exposition et VaR égales à celles des fonctions du projet.
- **Témoins** : refus de démarrer si un octet d'un fichier ONNX est changé (la copie intacte démarre) ; erreurs 422 en français pour 29 jours, une valeur manquante, un actif inconnu, une RV négative, un RSI au-dessus de 100, un jour de la semaine hors de 0 à 6, et un log_rv incohérent avec sa RV ; l'API n'importe ni torch ni pandas (vérifié dans un processus séparé).
- **Mesures** (`api/mesurer.py`, uvicorn local, Windows, 300 requêtes) : démarrage 1,7 s ; mémoire du processus d'environ 84 à 86 Mo (WorkingSetSize), pour une limite visée de 512 Mo ; temps de réponse de /prevoir : médiane d'environ 2 ms, 95e centile d'environ 3 à 4 ms, maximum 4,5 ms (client local, sans réseau).
- **Taille ajoutée au dépôt** : dossier `api/` de 658 Ko (6 fichiers ONNX de 98 à 109 Ko, paramètres, manifeste, exemple synthétique de 18 Ko, code), plus le script d'export, les tests et `requirements-api.txt`.
- **Essai réel de bout en bout** avec les commandes PowerShell 5.1 du README : `/health`, une prévision sur l'exemple synthétique et une erreur 422 en français.
- **Erreur corrigée** : la première mesure de la mémoire sous Windows renvoyait « indisponible » (types des arguments non déclarés dans l'appel à `K32GetProcessMemoryInfo`) ; corrigé, et le test exige maintenant une valeur sous Windows et sous Linux.
- Décisions prises seul (à valider) :
  - validation stricte : RV moyennes strictement positives, Parkinson et largeur de Bollinger positives ou nulles, RSI entre 0 et 100, nombres finis, champs inconnus refusés, et cohérence exigée entre log_rv_k et log(rv_k) (à 1e-9 près) ; Garman-Klass peut être négatif par construction : aucun signe imposé ;
  - un seul fil de calcul par session onnxruntime ;
  - `requirements-api.txt` donne toutes les dépendances de l'API en versions exactes (résolution vérifiée à vide : exactement ces paquets) ; httpx, utile aux seuls tests, est dans `requirements-dev.txt` ;
  - la réponse donne aussi la prévision de chaque graine et s², pour la transparence.

## 2026-11-19 — Étape 10B : application Streamlit

- **Vérification de licence de l'exemple synthétique de l'API** : il est produit par `exemple_synthetique` dans `src/exporter_onnx.py`, au hasard avec une graine fixe (`default_rng(7)`), à partir d'une marche aléatoire de la RV ; cette fonction ne lit aucun fichier, ni donnée Binance ni série dérivée. Les ordres de grandeur (RV de départ, log-volume, plage du RSI, etc.) sont des constantes choisies à la main, pas calculées sur les données. Aucun remplacement nécessaire.
- **Installation** : un essai à blanc de Streamlit dans `.venv` n'ajoutait que des paquets nouveaux (aucune version existante changée) : Streamlit 1.67.0 est installé dans `.venv`, sans environnement séparé ; `pip check` : aucun conflit. `app/requirements.txt` donne Streamlit et toutes ses dépendances en versions exactes (Python 3.11) ; résolution vérifiée à vide : exactement ces paquets.
- **Application** (`app/`) : huit pages avec `st.navigation` (tous les imports avant), fichiers précalculés lus avec `st.cache_data`, nombres au format français, couleurs des figures, mention « Données : Binance Vision, CC BY-NC-SA 4.0 » sur chaque page ; aucun tableau de série journalière dérivée.
- **Tests** (`tests/test_app.py`, AppTest) : chaque page s'affiche sans exception et porte la mention de licence ; nombres affichés égaux à ceux du JSON (avec un témoin : une valeur fausse n'apparaît pas) ; l'application complète démarre sans fichier de secrets ; la démonstration affiche « L'API ne répond pas… » quand l'API est absente ; lecture du CSV validée (deux formats, et refus clairs pour 29 lignes, une colonne absente, une valeur non numérique).
- **Essai réel** : API et application lancées en local ; la page d'accueil répond ; la démonstration envoie l'exemple synthétique à l'API et affiche la volatilité, l'exposition et la VaR ; un CSV au format français (« ; » et virgule décimale) est accepté.
- **Erreurs corrigées** : la première lecture du CSV ne relisait pas les nombres au bit près (lecture par défaut de pandas) ; corrigé avec `float_precision="round_trip"`, comme à l'étape de conversion. Le module d'outils de l'application s'appelait d'abord `commun`, comme `src/commun.py` : les deux se masquaient quand toute la suite de tests tournait (14 échecs) ; renommé `app/outils_app.py`, ce qui évite aussi le conflit au déploiement.
- Décisions prises seul (à valider) :
  - les pages sont dans `app/vues/` (et non `app/pages/`, que Streamlit lirait automatiquement comme des pages) ;
  - délai d'attente de l'API : 90 s, avec le message de réveil, puis un message clair en cas d'échec ;
  - le CSV accepte « , » avec point décimal ou « ; » avec virgule décimale ; le jour de la semaine et l'actif sont choisis dans la page ; un modèle de fichier téléchargeable contient les valeurs SYNTHÉTIQUES de l'exemple (aucune donnée de marché) ;
  - les tableaux sont affichés avec `st.table` (sans bouton de téléchargement) ;
  - les phrases d'explication et la liste des limites sont conditionnées par les valeurs des JSON (par exemple, les réseaux plus mauvais que HAR-RV pendant le Covid sont listés à partir des QLIKE par crise) ;
  - les identifiants des commits de règles cités dans la page « Données et méthode » sont écrits dans le code (ce sont des identifiants, pas des résultats).

## 2026-11-20 — Revue de l'application par captures, et corrections

- **Outil** : Playwright 1.65.2 (avec greenlet 3.5.6) installé dans `.venv` après un essai à blanc (aucune bibliothèque existante changée ; `pip check` : aucun conflit), ajouté à `requirements-dev.txt` ; navigateur Chromium de Playwright (headless shell 1255) téléchargé dans le dossier de Playwright, hors du projet ; Chromium sans profil, sans affichage, contexte vierge. Le premier téléchargement, interrompu par la fin d'une session, a été relancé et a abouti. Captures dans `captures_brutes/` (ignoré par Git, rien n'est commité).
- **Exposition sur le réseau local, dite honnêtement** : lors du premier lancement des captures, Streamlit a été démarré sans `--server.address` ; pendant environ 6 minutes, l'application (lecture seule, aucune donnée sensible) écoutait sur toutes les interfaces, donc était joignable depuis le réseau local, et Streamlit a affiché dans la console l'adresse IP publique du poste (elle n'a été écrite dans aucun fichier). Correction : toutes les commandes locales (README, script de captures, test en navigateur) lancent Streamlit avec `--server.address 127.0.0.1`. L'adresse n'est pas fixée dans `config.toml`, pour ne pas empêcher Streamlit Cloud de servir l'application.
- **Corrections après la revue** (critique validée) :
  1. page par défaut servie à l'adresse « / » (plus de fenêtre « Page not found ») ;
  2. graphique des résultats : les 10 étiquettes affichées (le modèle retenu marqué « retenu »), axe au format français et resserré autour des valeurs ;
  3. Accueil : encadré « Ce qu'on a trouvé » (3 phrases générées depuis `rapports/test_final.json`), phrase « Comment c'est prouvé » avec un lien vers les attentes, bloc repliable « In English » généré par la même fonction et depuis les mêmes valeurs, énoncés courts des hypothèses, pourcentages avec une espace insécable ;
  4. Résultats : onglet « Test final » en premier, tableaux dans l'ordre des modèles ;
  5. Explicabilité : découverte HAR-J en haut, importance des variables en graphique, un modèle à la fois (remplace la figure 7 illisible dans la page), attention tracée pour l'actif choisi, fidélité résumée avec le détail repliable, colonnes sans doublon ;
  6. Démonstration : résultat affiché juste sous le bouton utilisé, consigne en français au-dessus de la zone d'envoi, adresse de l'API non affichée quand elle est locale ;
  7. bouton « Deploy » retiré (`client.toolbarMode = "minimal"`) et statistiques d'usage désactivées ;
  8. détails : « 1 840 », schéma du parcours vertical et lisible, « Jour J du test de l'avenir modifié », Stratégie avec un seul tableau de constat et le titre « Pilotage par la volatilité (volatility targeting) », Limites résumées et fusionnées, plus de « −0,0 % ».
- **Limite écrite** : les textes internes de la zone d'envoi de fichier de Streamlit (« Upload », « 200MB per file ») restent en anglais ; aucune astuce CSS fragile n'est utilisée ; la page le signale en français.
- **Tests ajoutés** : la page par défaut à l'adresse « / » dans un vrai navigateur, sans « Page not found » ; le résumé anglais utilise les mêmes valeurs que le français (avec un témoin) ; le format « 0,0 % » sans signe.
- **Erreurs corrigées pendant la revue** : le script de captures mesurait d'abord une hauteur qui suivait celle de la fenêtre (captures très allongées, avec un grand vide) ; il mesure maintenant le bas réel du contenu et attend une hauteur stable. Les couleurs de la légende de l'attention étaient inversées par rapport à la figure 9 (ordre alphabétique d'Altair) ; l'ordre est maintenant fixé.
- Décisions prises seul (à valider) :
  - `config.toml` est placé à la racine (`.streamlit/config.toml`) et non dans `app/.streamlit/` : Streamlit lit ce fichier dans le dossier de lancement (la racine du projet, en local comme sur Streamlit Cloud) ; dans `app/.streamlit/`, il serait ignoré. Vérifié sur les captures : le bouton « Deploy » a disparu ;
  - la part expliquée par le jour de la semaine, dans l'encadré de l'Accueil, est calculée sur le test final (74 % pour BTC, 59 % pour ETH) ; la page Explicabilité garde celle du développement (72 % et 49 %), chacune étant nommée ;
  - le résumé anglais écrit les nombres au format anglais (point décimal), avec les mêmes valeurs ;
  - la figure 7 reste dans le dépôt et dans le README ; dans l'application, elle est remplacée par un graphique natif lisible.

## 2026-11-20 — Étape 11A-1 : préparation du déploiement de l'API sur Render

Aucune connexion à un compte ; le dépôt reste privé.

- **`render.yaml`** (Blueprint) : service web gratuit, région Frankfurt, `PYTHON_VERSION` 3.11.9, construction `pip install -r requirements-api.txt`, démarrage `uvicorn api.app:app --host 0.0.0.0 --port $PORT`, contrôle de santé `/health`. Aucun secret.
- **Roues Linux** (`pip download --only-binary :all:` pour Python 3.11, dans un dossier temporaire hors du projet, supprimé ensuite ; rien installé dans `.venv`) : avec la seule norme `manylinux2014` (glibc 2.17), **onnxruntime 1.32.0 est introuvable** : ses roues Linux exigent glibc 2.28. En acceptant aussi `manylinux_2_27` et `manylinux_2_28`, les 20 paquets de `requirements-api.txt` existent en roues pour Python 3.11 (onnxruntime exige glibc ≥ 2.28 et numpy glibc ≥ 2.27). Hypothèse, à confirmer par le journal de construction de Render : son environnement Python natif repose sur une Ubuntu récente, dont la glibc est plus récente que 2.28. Sinon, il faudrait une version plus ancienne d'onnxruntime, ce qui serait une décision à valider.
- **Clone propre** (`git clone` du dépôt local dans un dossier temporaire, supprimé ensuite ; Python lancé en mode isolé) : l'API démarre, vérifie ses 7 fichiers et donne exactement la même prévision qu'au dossier de travail (écart nul) ; elle ne dépend d'aucun fichier ignoré par Git. Le clone contient seulement les manifestes commités dans `data/`, que l'API ne lit pas.
- **`api/verifier_en_ligne.py`** : attend jusqu'à 120 s le réveil, affiche l'état et la mémoire, envoie l'exemple synthétique pour les deux actifs et compare à la prévision locale (tolérance de 1e-6 en log). Testé contre l'API locale (CONFORME, écart nul) avec un témoin (un écart de 2e-6 est détecté).
- Décisions prises seul (à valider) : le script de vérification utilise seulement la bibliothèque standard pour les appels HTTP ; il vérifie les deux actifs (et non seulement BTC, l'actif de l'exemple).

## 2026-11-20 — Préparation de la publication (dépôt toujours privé)

### API en ligne (https://volatilite-api.onrender.com)

- Construction sur Render réussie : l'hypothèse sur la glibc de Render (onnxruntime 1.32.0 exige glibc ≥ 2.28) est confirmée par le déploiement.
- `api/verifier_en_ligne.py` : **conforme** pour les deux actifs, écart nul en log avec la prévision locale (onnxruntime sous Linux redonne exactement les valeurs obtenues sous Windows sur l'exemple synthétique) ; mémoire lue dans `/health` sur Render : 95,3 Mo (`/proc/self/status`, VmRSS), pour une limite de 512 Mo ; temps de réponse de 437 à 656 ms (service éveillé, depuis le poste, réseau compris).
- Le service était éveillé au premier essai : le temps de réveil n'a pas pu être mesuré à ce moment ; le script affiche maintenant le délai de la première réponse de `/health`, mesuré plus loin après une période sans requête.
- Application : l'adresse par défaut de l'API est maintenant l'adresse publique (toujours remplaçable par `st.secrets["API_URL"]` ou la variable d'environnement `API_URL`) ; la page « Démonstration » l'affiche ; une adresse locale n'est jamais affichée (testé, avec un témoin).

### Audit de tout l'historique (33 commits, tous les fichiers et tous les messages)

Chaque recherche est appliquée au dépôt réel ET à un dépôt témoin temporaire où le problème est planté (puis supprimé) : une recherche qui ne trouve pas son témoin ne vaut rien.

- gitleaks sur tout l'historique : aucune fuite.
- Une seule identité, pour l'auteur et le committer de chaque commit : Mohamed Aljene, adresse noreply (témoin : un commit d'une autre identité est détecté).
- Fichiers de tous les commits, binaires compris : aucun chemin ni identifiant du poste (dossier des utilisateurs de Windows, numéro du dossier personnel hors d'un nombre, dossier des données d'application, dossier temporaire), aucune mention d'un outil d'aide à l'écriture du code. Témoins : chaque motif planté est trouvé ; un nombre décimal contenant le numéro du dossier personnel n'est pas trouvé, comme voulu.
- Messages de tous les commits : aucune de ces mentions (témoin propre aux messages : un commit par mention, le mot seulement dans le message ; chacun est trouvé).
- Aucun fichier interdit dans aucun commit (données brutes et traitées, .env, fichier d'instructions de l'éditeur, son dossier de réglages, sorties/, poids .pt, PDF, captures brutes) ; témoins : un fichier de chaque est trouvé.
- Taille : dossier `.git` de 4,9 Mo ; plus gros fichier de l'historique : une figure PNG de 202 Ko.
- Erreurs de l'audit, corrigées : la première recherche du chemin du dossier des utilisateurs avait un échappement en trop et ne trouvait même pas son témoin ; corrigée et relancée. Le dépôt témoin n'était pas supprimé (fichiers internes de Git en lecture seule sous Windows) ; les dossiers restants ont été supprimés et la suppression corrigée.
- **Numéro d'étape dans un message** : un seul commit est concerné.

### Rectification datée du 2026-11-20

Le message du commit c58c48e contient un numéro d'étape, contraire à la convention du projet. Il est conservé tel quel : l'historique n'est jamais réécrit, parce qu'il sert de preuve que les règles ont été écrites avant les résultats.

### Synthèse PDF (`docs/synthese.pdf`, générée par `src/synthese.py`)

- Bibliothèque : reportlab 5.1.0, épinglée dans `requirements-dev.txt` avec ses dépendances (pillow, charset-normalizer). Raison : elle écrit le PDF directement en Python, sans navigateur ni LaTeX, et a un mode « invariant » prévu pour obtenir un fichier identique à chaque génération.
- Police : Vera, fournie avec reportlab. La police DejaVu de matplotlib n'est pas utilisée, parce que matplotlib n'est pas installé par la reproduction rapide. Vera n'a pas l'espace fine insécable : elle est remplacée dans le PDF par l'espace insécable ordinaire (le nombre reste sur une ligne).
- Date du document fixée au jour d'ouverture du test final, lue dans `rapports/test_final.json` (variable `SOURCE_DATE_EPOCH`, reconnue par reportlab), avec le mode invariant (identifiant de fichier fixe). Vérifié : trois générations, dans des processus séparés, dont une lancée depuis un autre dossier, donnent la même empreinte SHA-256. Un test le vérifie, ainsi que l'égalité avec le PDF commité, le nombre de pages (3 à 5), la date et l'absence de chemin du poste (motifs vérifiés sur des témoins).
- Une seule source de texte : le résumé « Ce qu'on a trouvé » et la liste des limites sont écrits par `src/resume.py`, utilisé par l'application, la synthèse et le README. Le code a été déplacé de l'application vers ce module ; les phrases et les limites produites avant et après le déplacement ont été comparées et sont identiques.
- Mise en page vérifiée en regardant chaque page en image. Pour cela, pypdfium2 a été installé dans `.venv`, puis désinstallé ; `pip check` est sans erreur. Première version : 6 pages, parce que la figure de la volatilité sur le développement ne tenait pas sur la page 1. Elle est retirée : la synthèse ne montre que des figures du test final. Résultat : 5 pages.
- Erreur trouvée par un témoin et corrigée avant le commit : le premier test « aucun chemin du poste » cherchait dans les octets du PDF. Or le texte des pages y est compressé et, avec une police TrueType, écrit en numéros de glyphes : un chemin planté dans le texte n'était pas trouvé. Le test cherche maintenant dans les flux décompressés et dans le texte de chaque paragraphe avant la mise en page, avec trois témoins (texte compressé avec et sans ASCII85, paragraphe). Les octets d'un début de chemin Windows (lettre de lecteur, deux-points, barre oblique inverse) trouvés par la recherche des mots interdits dans la première version du PDF étaient au hasard dans des images codées en ASCII85 ; ce codage est désactivé (PDF plus petit d'environ un quart).

### README final

- Structure : résumé et « In English » générés, liens en ligne, données et licence, résultats clés, trois captures, limites, installation, reproduction rapide, lancement local, reproduction complète, structure du dépôt, méthode, licences. La liste des règles et des exceptions datées, qui n'existe que dans le README, est gardée mot pour mot dans une section repliable.
- `src/readme.py` génère quatre blocs : le résumé, « In English », les limites (mêmes fonctions que l'application et la synthèse) et les durées. Ces dernières sont lues dans les JSON quand elles y sont : la phase des plis du deep learning et le pic de mémoire. Les autres restent dans ce journal, parce qu'une reprise après interruption fausserait une durée écrite dans un fichier de résultats. Un test vérifie que le README commité est exactement ce que le script écrit (témoin : un bloc modifié à la main est détecté, un marqueur supprimé est refusé). Le test des liens couvre aussi `api/`, `app/` et `figures/`.
- Chiffres tapés à la main retirés pendant la relecture : nombre de pages de la synthèse, numéros des captures, taille de la fenêtre d'entrée de l'API. Le nombre de réseaux et d'actifs du bloc des durées est lu dans le JSON.
- Liens externes vérifiés une fois à la main (code 200 pour Binance Vision, ses conditions, la licence Creative Commons, Git et Python) ; l'API et le dépôt (encore privé) sont vérifiés à part.

### Écart daté du 2026-11-20 à l'ordre de publication

Écart daté à l'ordre de publication : le dépôt est passé en public avant la fin du test sur un clone neuf, pour tenir une échéance. L'audit de sécurité de tout l'historique était terminé. Tout défaut trouvé ensuite par le clone sera corrigé par un commit daté.

- Licences : `LICENSE` (MIT, code seul) et `LICENSE-DONNEES.md` (données non incluses, fichiers dérivés sous CC BY-NC-SA 4.0, attribution et liens) existaient déjà, depuis le commit 4eafe2b ; ils n'ont pas été réécrits. La section « Licences » du README renvoie aux deux. Un test vérifie maintenant leur contenu et ces liens, avec un témoin.

### Test sur un clone neuf (2026-11-20) : défauts trouvés et corrigés dans le dépôt

Les commandes du README ont été copiées telles quelles et lancées sur un clone neuf, avec un nouvel environnement `.venv` (Python 3.11.9). Chaque défaut est corrigé dans le dépôt, jamais dans le clone.

1. **Clone interrompu par le réseau** (erreur SSL, fin de transfert prématurée, après 340 s). La même commande, relancée, a réussi. Ce n'est pas un défaut du dépôt ; le README dit maintenant de relancer la commande dans ce cas.
2. **Installation refusée par Windows** (`WinError 206`, chemin trop long). Le clone était dans un dossier très profond (142 caractères), et Playwright installe des fichiers très imbriqués : la limite de 260 caractères de Windows était dépassée (chemins longs non activés sur ce poste). Dans un dossier court (43 caractères, comparable au dossier Documents), l'installation réussit : clone en 65 s, environnement en 15 s, installation en 135 s, `pip check` sans erreur. Correction : le README dit de travailler dans un dossier au chemin court et cite l'erreur.
3. **Reproduction rapide : conforme.** Les trois générateurs se relancent sans erreur. `git diff --exit-code` est vide : le README, `docs/RESULTATS_TEST.md` et la synthèse PDF sont identiques au dépôt, octet pour octet, sur un autre dossier. 43 tests passent ; 2 sont sautés (données absentes). Durée totale : 31 s.
4. **Accents abîmés dans les réponses de l'API sous PowerShell 5.1.** Les réponses déclaraient `application/json` sans encodage, et `Invoke-RestMethod` (commande du README) les lisait en Latin-1 : « VolatilitÃ© ». Cela touchait aussi les erreurs 422 en français. Le contenu envoyé était déjà en UTF-8. Correction dans `api/app.py` : toutes les réponses déclarent `application/json; charset=utf-8` ; seul l'en-tête change, et la prévision reste identique (vérifié). Un test vérifie l'en-tête de `/health`, de `/prevoir` et d'une erreur 422, avec un témoin. Essai réel : l'API corrigée affiche correctement les accents dans PowerShell 5.1, l'ancienne non. Render redéploie l'API depuis la branche principale.
5. **Invite d'adresse e-mail au premier lancement de l'application.** Sur un poste où Streamlit n'a jamais servi (essai avec un dossier personnel vide), la commande du README s'arrêtait sur une question en anglais demandant une adresse e-mail. Correction : `headless = true` dans `.streamlit/config.toml`, donc ni invite ni navigateur ouvert automatiquement (le README dit d'ouvrir l'adresse). Essai refait avec un dossier personnel vide : pas d'invite, l'application répond en 1,6 s, et seulement sur 127.0.0.1.
6. **Renvoi sans cible.** La page « Démonstration » renvoie au README pour la définition des variables, mais le README n'en parlait pas. Il renvoie maintenant à la section 6 des règles.

L'API et l'application du clone ont été lancées avec les commandes du README. L'API (127.0.0.1 seulement) vérifie son manifeste et donne la même prévision que le dépôt principal. L'application (127.0.0.1 seulement) affiche l'accueil et le résumé, et envoie l'exemple synthétique à l'API locale ; la réponse est affichée, et l'adresse locale ne l'est pas.

**Suite du test du clone (2026-11-20, après la publication et l'étiquette v1.0).**

- Téléchargement sur le premier clone (commande du README) : 581 s, 424 fichiers, 90,3 Mo ; `git diff --exit-code -- data/manifeste_brut.json` est vide : les empreintes SHA-256 des fichiers téléchargés sont exactement celles du dépôt.
- Clone anonyme, sans aucun identifiant, après le passage en public : il réussit. Même commit que le dépôt local, mêmes 138 fichiers (contenus identiques octet pour octet), 40 commits, `git fsck` sans erreur, aucune donnée brute. Il a été supprimé.
- Second clone neuf, au commit de l'étiquette v1.0, pour vérifier les corrections. Installation en 123 s ; reproduction rapide en 31 s, avec `git diff` vide ; 44 tests passent et 2 sont sautés (données absentes). Accents corrects dans PowerShell 5.1, pour une réponse comme pour une erreur 422. Application lancée avec la commande du README et un dossier personnel vide : aucune invite, écoute sur 127.0.0.1 seulement, démonstration envoyée à l'API locale. Aucune nouvelle correction du dépôt n'a été nécessaire : l'étiquette v1.0 n'est pas déplacée, et aucune étiquette v1.0.1 n'est posée.
- API locale des clones arrêtée ; clones temporaires supprimés (y compris le premier essai dans un dossier trop profond et le clone anonyme).

**Temps de réveil de l'API en ligne : non mesuré, le service n'a jamais été vu endormi.**

- Essai 1, à 07 h 00, après 16 min 50 s sans requête de ma part : première réponse de `/health` en 0,3 s.
- Essai 2, à 10 h 45, plus de 30 min après ma dernière requête et 31 min après le dernier push (Render redéploie à chaque push) : première réponse en 1,5 s. Vérification conforme pour les deux actifs, écart nul ; 100,1 Mo de mémoire ; l'en-tête `application/json; charset=utf-8` est bien en ligne.
- Un vrai réveil de l'offre gratuite prend en général plusieurs dizaines de secondes : ces deux réponses rapides montrent que le service ne dormait pas. Explication possible, non vérifiée : d'autres requêtes que les miennes (l'application en ligne, des visites) ou la fin du redéploiement ont remis à zéro le délai d'inactivité. Le README garde l'avertissement : la première réponse peut prendre du temps.

Une application Streamlit lancée hors de cette séance, avec le Python global et sans l'option `--server.address 127.0.0.1`, écoutait sur le réseau local depuis 08 h 58. Elle a été arrêtée le 2026-11-20 en fin de matinée, à la demande du propriétaire du dépôt ; plus rien n'écoute sur le port 8501.
