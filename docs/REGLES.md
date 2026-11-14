# Règles du projet

Ces règles ont été écrites et commitées **avant** tout téléchargement de données et tout calcul. Le code les lit dans `config/regles.toml`, et un test vérifie que chaque date de ce fichier est identique ici. Toute modification ultérieure est écrite et datée dans `docs/CHOIX.md`.

Une valeur notée « à fixer après mesure » sera choisie plus tard, à partir d'une mesure. Tant qu'elle n'est pas fixée, le code refuse de lancer un entraînement.

## 0. Convention de date

Un **exemple** réunit des variables arrêtées à la clôture du jour J et une cible : la volatilité réalisée du jour J+1. Cet exemple appartient à la période qui contient sa **cible** (J+1). Toutes les bornes de période et de pli ci-dessous sont donc des dates de cible.

Exemple : l'exemple dont la cible est le 2025-01-01 a ses variables arrêtées le 2024-12-31. Il appartient au test final, pas au développement.

## 1. Projet

| Règle | Valeur | Raison |
|---|---|---|
| Graine aléatoire | 42 | Rejouer un calcul donne exactement le même résultat. |
| Nombre de fils de calcul | à fixer après mesure (2, 4 ou 8) | Le meilleur choix dépend de la machine : on chronomètre avant de décider. |
| Seuil de mémoire libre | à fixer après mesure | Un script lourd ne doit pas démarrer s'il risque de saturer la mémoire. |

## 2. Données

| Règle | Valeur | Raison |
|---|---|---|
| Source | Binance spot, data.binance.vision, bougies (klines) de 5 minutes | Fichiers publics, gratuits et complets, sur le marché crypto le plus liquide. |
| Actifs | BTCUSDT et ETHUSDT | Les deux cryptos les plus échangées, avec un long historique. |
| Fuseau | UTC ; un jour va de 00:00 inclus à 24:00 exclu | Le marché crypto ne ferme jamais : il faut une définition du jour fixe et sans heure d'été. |
| Période | du 2018-01-01 au 2026-10-31, aucune donnée de 2017 | On évite les premiers mois de Binance (fin 2017) et on s'arrête au dernier mois complet. |
| Horodatage | unité (millisecondes ou microsecondes) détectée pour chaque fichier d'après l'ordre de grandeur des nombres ; testée avec un témoin dans chaque unité à l'étape des données | Binance a changé d'unité au cours du temps : une mauvaise lecture décalerait toutes les dates. |
| Licence | à vérifier à l'étape des données | Aucun extrait de données ne sera commité avant cette vérification. |

### Jours valides et trous

| Règle | Valeur | Raison |
|---|---|---|
| Nombre de bougies | au moins 274 sur 288 (95 %) | Un jour avec trop de trous donnerait une volatilité fausse. |
| Écart maximal | si deux bougies consécutives sont séparées de plus de 60 minutes, le jour est non valide | Un long trou cache peut-être un mouvement de prix important. |
| Rendement qui enjambe un trou | gardé, entre deux clôtures consécutives disponibles | Le mouvement de prix a bien eu lieu : le supprimer sous-estimerait la volatilité. |
| Premier rendement du jour | part de la dernière clôture disponible de la veille, avec la même règle des 60 minutes | Aucun mouvement de prix n'est perdu à minuit. |
| Rendement manquant | compte comme une bougie manquante dans la règle des 274 | Une seule règle de comptage pour tous les jours. |
| Premier jour des données | le 2018-01-01 n'a pas de veille (aucune donnée de 2017) : jour valide avec 287 rendements ; il sert au préchauffage et n'est jamais une cible | Un seul rendement manquant reste bien au-dessus du seuil de 274. |
| Jours non valides | exclus de la cible et de l'évaluation, et listés dans un rapport | On ne juge pas un modèle sur une mesure douteuse. |
| Exemples touchés | un exemple dont la fenêtre d'entrée de 30 jours contient un jour non valide est exclu ; le nombre d'exclusions est rapporté | Le modèle ne reçoit jamais de valeur douteuse en entrée. |
| Règle de secours | si les exclusions dépassent 5 % des exemples, les jours non valides en entrée prennent la dernière valeur valide connue (passé uniquement) | Éviter de perdre trop d'exemples, sans jamais utiliser le futur. Règle écrite avant de voir les données. |
| Mesure du seuil de 5 % | une seule fois, par actif, sur tout le développement (cibles du 2018-04-01 au 2024-12-31), jamais sur le test final ; si un actif dépasse 5 %, le secours s'applique aux deux actifs, partout | Décider sans regarder le test final, et garder la même préparation des données pour les deux actifs. |

## 3. Découpage dans le temps (dates de cible)

| Règle | Valeur | Raison |
|---|---|---|
| Préchauffage | du 2018-01-01 au 2018-03-31 (90 jours), uniquement pour calculer les variables | Les variables les plus longues (moyennes sur 30 jours, MACD, séquences de 30 jours) ont besoin d'historique avant la première prévision. |
| Première cible | 2018-04-01 | Premier jour où toutes les variables sont calculables. |
| Développement | cibles du 2018-04-01 au 2024-12-31 | Toutes les mises au point se font sur cette période. |
| Test final | cibles du 2025-01-01 au 2026-10-31, ouvert une seule fois | Une période jamais vue donne une mesure honnête de la performance. |
| Walk-forward | premier apprentissage : cibles du 2018-04-01 au 2019-12-31 ; puis 10 plis de 6 mois, cibles du 2020-01-01 au 2024-12-31 | On imite l'usage réel : apprendre sur le passé, prévoir la suite, puis recommencer avec plus d'historique (fenêtre qui s'agrandit). |
| Validation interne | les 6 derniers mois de cibles de chaque apprentissage | Sert à l'arrêt anticipé, au réglage et à la mesure de s², sans toucher aux mois évalués. |
| Fenêtre d'ajustement commune | tous les modèles (HAR-RV, XGBoost, deep learning) sont ajustés sur la même fenêtre : l'apprentissage du pli sans sa validation interne | Mêmes données pour tous : la comparaison est équitable. |
| Modèle du test final | ajustement sur les cibles du 2018-04-01 au 2024-06-30, validation interne du 2024-07-01 au 2024-12-31 | Même règle que pour les plis, appliquée une dernière fois avant le test final. |
| Embargo | 0 jour | Avec la convention « date de la cible », aucune cible n'est commune entre apprentissage et évaluation pour un horizon d'un jour. Un test le vérifie pour chaque pli. |
| Transformations | réapprises sur l'apprentissage de chaque pli | Une normalisation calculée sur des données futures serait une fuite d'information. |

Exemple du premier pli : ajustement sur les cibles du 2018-04-01 au 2019-06-30, validation interne du 2019-07-01 au 2019-12-31, évaluation du 2020-01-01 au 2020-06-30. Le dernier pli évalue les cibles du 2024-07-01 au 2024-12-31.

La validation interne d'un pli est la période évaluée du pli précédent ; c'est du passé au moment du pli, donc ce n'est pas une fuite.

## 4. Périodes de crise

Fixées avant tout résultat, pour analyser les modèles par régime de marché. Elles sont analysées sur les prévisions hors échantillon des plis walk-forward : c'est voulu, car aucune de ces crises n'est dans le test final.

| Crise | Période | Raison |
|---|---|---|
| Covid | du 2020-03-01 au 2020-04-30 | Krach mondial de mars 2020. |
| Terra / Luna | du 2022-05-01 au 2022-06-30 | Effondrement d'un écosystème crypto majeur. |
| FTX | du 2022-11-01 au 2022-12-31 | Faillite d'une grande plateforme d'échange. |

## 5. Cible

| Règle | Valeur | Raison |
|---|---|---|
| Volatilité réalisée (RV) | racine de la somme des carrés des log-rendements de 5 minutes des clôtures du jour UTC | Mesure standard de l'agitation d'une journée. |
| Horizon | 1 jour : prévoir RV du jour J+1 avec l'information connue à la clôture de J | Projet complet et maîtrisable. |
| Échelle des modèles | log(RV) | La volatilité varie énormément ; en logarithme, les écarts sont plus réguliers et la prévision redevient toujours positive. |
| Variance prévue | exp(2·ŷ + 2·s²) pour les modèles en log ; variance GARCH mise à l'échelle pour GARCH ; utilisée pour QLIKE | Prendre seulement exp(ŷ) donne la médiane, donc une prévision trop basse en moyenne, ce que QLIKE punit fortement. |
| Volatilité prévue σ̂ | une seule pour tout le projet : σ̂ = racine(variance prévue) ; utilisée pour RMSE, MAE, la stratégie et la VaR | Une seule définition évite de choisir, après coup, la version qui arrange le résultat. |
| Mesure de s² | variance des résidus en log, toujours mesurée sur la validation interne, pour tous les modèles qui prévoient log(RV) | L'erreur est mesurée sur des jours que le modèle n'a pas appris, et sur les mêmes données pour tous. |
| Sensibilité | σ̂ non corrigée (s² = 0, soit exp(ŷ)) aussi rapportée, sans changer la décision | Montrer l'effet de la correction. |
| Limite | σ̂ est un peu au-dessus de la moyenne de la RV, ce qui pénalise légèrement le MAE | Écrite d'avance, pour que ce petit désavantage ne soit pas une surprise. |
| Annualisation | 365 jours | Le marché crypto est ouvert 7 jours sur 7. |

## 6. Variables

Toutes calculées uniquement sur le passé, jusqu'à la clôture du jour J incluse.

| Variable | Valeur | Raison |
|---|---|---|
| RV moyennes | sur 1, 7 et 30 jours | Adaptation du modèle HAR (jour, semaine, mois) à un marché ouvert 7 jours sur 7. |
| Estimateurs journaliers | Parkinson et Garman-Klass | Ils utilisent le plus haut et le plus bas du jour : une autre vue de la volatilité. |
| Rendement et volume | log-rendement du jour, log du volume du jour | La volatilité réagit aux fortes baisses et aux pics d'activité. |
| Indicateurs techniques | RSI 14 jours, MACD (12, 26, 9), largeur des bandes de Bollinger (20 jours, 2 écarts-types), sur les clôtures journalières | Indicateurs courants, pour tester s'ils apportent une information utile. |
| Calendrier | jour de la semaine | L'activité du week-end diffère de celle de la semaine. |
| Séquences | 30 jours pour les modèles séquentiels | Un mois d'historique, cohérent avec la plus longue moyenne de RV. |

## 7. Modèles

| Règle | Valeur | Raison |
|---|---|---|
| Références | HAR-RV (régression linéaire sur log RV, fenêtres 1, 7 et 30 jours), GARCH(1,1) (rendements journaliers, innovations de Student) | Un modèle de deep learning n'a d'intérêt que s'il bat ces références classiques. |
| Mise à l'échelle de GARCH | facteur unique = moyenne(RV²) / moyenne(variance GARCH), appris sur l'apprentissage de chaque pli, puis appliqué tel quel à l'évaluation ; σ̂ = racine de la variance mise à l'échelle | GARCH prévoit la variance du rendement d'un jour, pas la RV calculée sur 5 minutes : il faut ramener les deux à la même échelle, sans regarder la période évaluée. |
| Autres modèles | XGBoost, LSTM, GRU, CNN-LSTM, Transformer encodeur codé à la main, TFT | Du plus simple au plus complexe, pour voir ce que chaque complexité apporte. |
| Graines | 0, 1, 2, 3 et 4 pour le deep learning ; moyenne et écart-type rapportés | Un seul entraînement peut être chanceux : on mesure la variabilité. |
| Budget de réglage | à fixer après mesure, identique pour tous les modèles de deep learning | Comparaison équitable. Il sera fixé par un essai chronométré sur des données aléatoires de même taille. |

## 8. Évaluation

| Règle | Valeur | Raison |
|---|---|---|
| Métrique principale | QLIKE sur la variance (RV²) | Recommandée pour comparer des prévisions de volatilité, même si la RV mesurée est bruitée. |
| Métriques secondaires | RMSE et MAE sur RV | Plus faciles à lire, en unités de volatilité. |
| Test de Diebold-Mariano | contre HAR-RV, perte QLIKE, erreurs HAC, seuil de 5 % | Dire si un écart de performance est réel ou dû au hasard. |
| Retards HAC | floor(4·(T/100)^(2/9)), règle de Newey-West, T = nombre de jours évalués ; correction de Harvey-Leybourne-Newbold | Le nombre de retards est fixé par une formule, pas choisi après coup. La correction rend le test plus fiable sur de petits échantillons. |
| Portée du test | test principal sur les 10 plis réunis ; un seul test sur le test final ; par pli et par crise, résultats descriptifs seulement, sans conclusion de test | Multiplier les tests finit toujours par donner un résultat « significatif » par hasard. |
| Intervalles de confiance | 95 %, bootstrap par blocs, 1000 tirages, blocs de 20 jours | Les blocs gardent l'enchaînement des jours, qui ne sont pas indépendants. |
| Règle de sélection | le plus petit QLIKE moyen sur les 10 plis walk-forward ; sur le test final, tous les modèles sont rapportés et aucun choix n'est fait | Choisir sur le test reviendrait à tricher avec la période de contrôle. |

## 9. Stratégie

| Règle | Valeur | Raison |
|---|---|---|
| Principe | volatility targeting : exposition = volatilité cible / volatilité prévue σ̂ (annualisée), bornée entre 0 et 1 | On investit moins quand le marché s'agite, sans emprunt ni vente à découvert. Le reste est en liquidités, avec un rendement de 0. |
| Volatilité cible | médiane de la RV annualisée des jours valides de chaque actif, du 2018-01-01 au 2019-12-31, enregistrée dans un fichier | Calculée sur l'apprentissage seulement, pour ne rien emprunter au futur. |
| Exécution | l'exposition décidée à la clôture de J s'applique au rendement de J+1 | On ne peut pas trader au prix d'une clôture qu'on vient juste d'observer. |
| Frais | 0,10 % de la valeur échangée ; sensibilité à 0,05 % et à 0,20 % | Ordre de grandeur réaliste ; la sensibilité est décrite sans changer la décision. |
| Comparaisons | buy and hold, et stratégie pilotée par HAR-RV | Montrer ce que la prévision apporte par rapport à ne rien faire, et par rapport au modèle classique. |
| Risque | VaR à 95 % à partir de la volatilité prévue σ̂, avec le quantile de la loi normale pour tous les modèles ; test de Kupiec | La même règle pour tous rend la comparaison équitable. Les rendements crypto ont des queues épaisses : on s'attend à un test de Kupiec sévère. |

## 10. Explicabilité

| Règle | Valeur | Raison |
|---|---|---|
| Méthodes | SHAP sur XGBoost et LSTM ; attention du Transformer et du TFT | Comprendre quelles variables pèsent dans la prévision. |
| Règle de fidélité | permuter la variable la mieux classée par SHAP doit dégrader le QLIKE de validation plus que permuter la moins bien classée ; sinon, on écrit honnêtement que SHAP échoue sur ce modèle | Une explication n'a de valeur que si elle correspond au comportement réel du modèle. |
