# Règles du projet

Ces règles ont été écrites et commitées **avant** tout téléchargement de données et tout calcul. Le code les lit dans `config/regles.toml`, et un test vérifie que chaque date de ce fichier est identique ici. Toute modification ultérieure est écrite et datée dans `docs/CHOIX.md`.

Une valeur notée « à fixer après mesure » sera choisie plus tard, à partir d'une mesure. Tant qu'elle n'est pas fixée, le code refuse de lancer un entraînement.

Les règles marquées « exception du 2026-11-14 » ont été précisées après le commit des règles et avant tout téléchargement ou calcul ; elles sont expliquées dans `docs/CHOIX.md`.

Les règles marquées « précisions du 2026-11-15 » ont été écrites et commitées avant le calcul des variables. Celles de la section 11 (précisions du 2026-11-16) ont été écrites et commitées avant tout entraînement. Les règles marquées « exception du 2026-11-16 » (plis annuels, réglage unique, 3 graines, AdamW, budget de 24 heures, répétitions, alimentation) ont remplacé, avant tout entraînement réel, une règle initiale irréalisable ; la raison et les mesures sont dans `docs/CHOIX.md`.

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
| Walk-forward | premier apprentissage : cibles du 2018-04-01 au 2019-12-31 ; puis 5 plis annuels de 12 mois, cibles du 2020-01-01 au 2024-12-31 (exception du 2026-11-16 ; au départ, 10 plis de 6 mois) | On imite l'usage réel : apprendre sur le passé, prévoir la suite, puis recommencer avec plus d'historique (fenêtre qui s'agrandit). Le réentraînement annuel est courant en pratique, et les jours évalués sont les mêmes. |
| Validation interne | les 6 derniers mois de cibles de chaque apprentissage | Sert à l'arrêt anticipé, au réglage et à la mesure de s², sans toucher aux mois évalués. |
| Fenêtre d'ajustement commune | tous les modèles (HAR-RV, XGBoost, deep learning) sont ajustés sur la même fenêtre : l'apprentissage du pli sans sa validation interne | Mêmes données pour tous : la comparaison est équitable. |
| Modèle du test final | ajustement sur les cibles du 2018-04-01 au 2024-06-30, validation interne du 2024-07-01 au 2024-12-31 | Même règle que pour les plis, appliquée une dernière fois avant le test final. |
| Embargo | 0 jour | Avec la convention « date de la cible », aucune cible n'est commune entre apprentissage et évaluation pour un horizon d'un jour. Un test le vérifie pour chaque pli. |
| Transformations | réapprises sur l'apprentissage de chaque pli | Une normalisation calculée sur des données futures serait une fuite d'information. |

Exemple du premier pli : ajustement sur les cibles du 2018-04-01 au 2019-06-30, validation interne du 2019-07-01 au 2019-12-31, évaluation du 2020-01-01 au 2020-12-31. Le dernier pli évalue les cibles du 2024-01-01 au 2024-12-31.

La validation interne d'un pli (6 mois) est la seconde moitié de la période évaluée du pli précédent ; c'est du passé au moment du pli, donc ce n'est pas une fuite.

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
| Limite de s² (exception du 2026-11-14) | la validation interne sert aussi à l'arrêt anticipé et au réglage : s² est légèrement trop petit pour XGBoost et le deep learning | Ce biais rend leurs prévisions un peu trop basses et les désavantage sous QLIKE : il ne les favorise pas. **Rectification du 2026-11-16 : cette affirmation est retirée** (voir ci-dessous). |

Rectification du 2026-11-16 (exception 2) : l'affirmation selon laquelle le biais de s² désavantage les modèles réglés n'est vérifiée que pour les plis 1 à 3. Dans les plis 4 et 5, XGBoost prévoit trop haut sur la validation interne (moyenne des résidus de −0,07 à −0,14, lue dans `rapports/baselines.json`). L'affirmation est retirée. Explication probable, non démontrée : un modèle à arbres ne peut pas prévoir sous les valeurs vues à l'apprentissage, et ces validations tombent sur des périodes calmes. La règle de mesure de s² elle-même ne change pas.
| Échelle de σ̂ | journalière (volatilité sur 1 jour) | La cible est la RV d'un jour ; l'annualisation n'est faite que là où elle est écrite. |
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

### Précisions datées du 2026-11-15, écrites avant le calcul des variables

| Précision | Valeur | Raison |
|---|---|---|
| Ligne journalière | ouverture de la première bougie, plus haut et plus bas du jour, clôture de la dernière bougie, volume = somme du volume en USDT (`volume_cotation`) | Le volume en USDT est comparable entre BTC et ETH et dans le temps ; le volume en unités de crypto ne l'est pas, car le prix a beaucoup changé. |
| Bougies désalignées | traitées comme manquantes, comme au contrôle de qualité | Une seule source de vérité pour les jours valides. |
| RV moyennes en log | log de la moyenne de RV sur 1, 7 ou 30 jours | Le modèle HAR moyenne la volatilité, puis on passe au log, comme pour la cible. |
| Log-rendement du jour | ln(clôture de J / clôture de J-1) | Rendement de clôture à clôture, celui de la stratégie. |
| Parkinson | ln(H/L)² / (4 ln 2) | Variance estimée à partir du plus haut et du plus bas du jour. |
| Garman-Klass | 0,5 ln(H/L)² − (2 ln 2 − 1) ln(C/O)² | Ajoute l'ouverture et la clôture à Parkinson. |
| RSI 14 jours | lissage de Wilder (alpha = 1/14), première moyenne = moyenne simple des 14 premières variations | Définition d'origine de Wilder, vérifiable à la main sur un petit exemple. |
| MACD (12, 26, 9) | moyennes exponentielles démarrées à la première clôture ; variable = histogramme divisé par la clôture | Un écart de 100 $ n'a pas le même sens à 4 000 $ et à 100 000 $ : divisé par le prix, il est comparable dans le temps. |
| Bollinger (20 jours, 2 écarts-types) | écart-type de population (ddof = 0) ; variable = (bande haute − bande basse) / moyenne mobile | Définition d'origine ; divisée par la moyenne pour être comparable dans le temps. |
| Jour de la semaine | entier de 0 (lundi) à 6 (dimanche) ; encodage choisi à l'étape des modèles | Le bon encodage dépend du modèle. |
| Cible | log(RV de J+1) | Échelle des modèles (section 5). |
| Règle de secours | la ligne journalière entière d'un jour non valide (ouverture, haut, bas, clôture, volume, RV) est remplacée par celle du dernier jour valide ; toutes les variables sont ensuite calculées sur cette série | Une seule règle, simple, qui n'utilise que le passé. |
| Limite du secours | le rendement du jour remplacé est nul, et celui du lendemain porte sur deux jours | Conséquence directe de la règle, acceptée et écrite d'avance. |
| Comptages du secours | remplacements par actif et par période ; exemples du développement dont la fenêtre d'entrée de 30 jours contient au moins un jour remplacé, par actif | Mesurer combien d'exemples sont touchés par la règle. |
| Validité en entrée | contrôle automatique : la validité d'un jour, utilisée en entrée, n'utilise jamais l'avenir | Un trou qui passe minuit pourrait sinon faire dépendre la validité de J du jour J+1. |
| Sorties | `data/processed/variables.parquet` (jamais commité) ; son empreinte de contenu va dans `data/manifeste_variables.json`, qui cite les empreintes du manifeste traité et du rapport de qualité | Chaîne sans boucle : brut, traité, qualité, variables. Une relance de la conversion n'efface rien. |

### Test aveugle et exploration (précisions du 2026-11-15)

| Règle | Valeur | Raison |
|---|---|---|
| Garde du test aveugle | une fonction centrale refuse toute statistique, tout graphique et tout affichage de valeurs dont la date de cible est postérieure ou égale au début du test final ; seuls les comptages sont permis ; aucune option de contournement (paramètre, variable d'environnement ou réglage) | Le test ne doit jamais influencer une décision avant son ouverture unique. |
| Ouverture du test | mécanisme construit à l'étape du test final | Rien ne doit permettre de l'ouvrir avant. |
| Période explorée | développement seulement (cibles jusqu'au 2024-12-31) | Même raison. |
| Autocorrélation | log(RV), jusqu'à 60 jours, valeurs rapportées à 1, 7 et 30 jours ; jours non valides laissés vides | Montrer le regroupement de volatilité sans inventer de valeurs. |
| Test ADF | sur log(RV) et sur le log du prix de clôture, retards choisis par AIC ; jours non valides retirés (limite écrite ; leur nombre est rapporté) | Contraster une série qui revient vers sa moyenne et une série qui dérive. |

## 7. Modèles

| Règle | Valeur | Raison |
|---|---|---|
| Références | HAR-RV (régression linéaire sur log RV, fenêtres 1, 7 et 30 jours), GARCH(1,1) (rendements journaliers, innovations de Student) | Un modèle de deep learning n'a d'intérêt que s'il bat ces références classiques. |
| Mise à l'échelle de GARCH | paramètres et facteur unique = moyenne(RV²) / moyenne(variance GARCH) appris sur la fenêtre d'ajustement du pli (sans la validation interne, comme tous les modèles ; exception du 2026-11-14), puis appliqués tels quels à l'évaluation ; σ̂ = racine de la variance mise à l'échelle | GARCH prévoit la variance du rendement d'un jour, pas la RV calculée sur 5 minutes : il faut ramener les deux à la même échelle, sans regarder la période évaluée. |
| Autres modèles | XGBoost, LSTM, GRU, CNN-LSTM, Transformer encodeur codé à la main, TFT | Du plus simple au plus complexe, pour voir ce que chaque complexité apporte. |
| Graines | 0, 1 et 2 pour le deep learning et XGBoost (exception du 2026-11-16 ; au départ, 5 graines) ; moyenne et écart-type rapportés | Un seul entraînement peut être chanceux : on mesure la variabilité. Trois graines restent le minimum pour un écart-type. |
| Budget de réglage | à fixer après mesure, identique pour tous les modèles de deep learning | Comparaison équitable. Il sera fixé par un essai chronométré sur des données aléatoires de même taille. |

## 8. Évaluation

| Règle | Valeur | Raison |
|---|---|---|
| Métrique principale | QLIKE sur la variance (RV²) | Recommandée pour comparer des prévisions de volatilité, même si la RV mesurée est bruitée. |
| Métriques secondaires | RMSE et MAE sur RV | Plus faciles à lire, en unités de volatilité. |
| Test de Diebold-Mariano | contre HAR-RV, perte QLIKE, erreurs HAC, seuil de 5 % | Dire si un écart de performance est réel ou dû au hasard. |
| Retards HAC | floor(4·(T/100)^(2/9)), règle de Newey-West, T = nombre de jours évalués ; correction de Harvey-Leybourne-Newbold | Le nombre de retards est fixé par une formule, pas choisi après coup. La correction rend le test plus fiable sur de petits échantillons. |
| Portée du test | test principal sur les plis réunis (5 plis annuels, mêmes jours qu'avec 10 plis) ; un seul test sur le test final ; par pli et par crise, résultats descriptifs seulement, sans conclusion de test | Multiplier les tests finit toujours par donner un résultat « significatif » par hasard. |
| Intervalles de confiance | 95 %, bootstrap par blocs, 1000 tirages, blocs de 20 jours | Les blocs gardent l'enchaînement des jours, qui ne sont pas indépendants. |
| Règle de sélection | le plus petit QLIKE moyen sur les 5 plis walk-forward ; sur le test final, tous les modèles sont rapportés et aucun choix n'est fait | Choisir sur le test reviendrait à tricher avec la période de contrôle. |
| QLIKE moyen (précision du 2026-11-16, décidée APRÈS avoir vu les résultats des baselines) | les deux définitions sont rapportées : QLIKE sur tous les jours évalués réunis, et moyenne des QLIKE moyens par pli ; si les classements diffèrent, la définition littérale (moyenne des moyennes par pli) s'applique | La règle ne précisait pas la définition. Décidée après les résultats : c'est écrit honnêtement, et les deux classements restent visibles. |

## 9. Stratégie

| Règle | Valeur | Raison |
|---|---|---|
| Principe | volatility targeting : exposition = volatilité cible annuelle / (σ̂ × racine(365)), bornée entre 0 et 1 (exception du 2026-11-14) | On investit moins quand le marché s'agite, sans emprunt ni vente à découvert. Le reste est en liquidités, avec un rendement de 0. |
| Volatilité cible | médiane de la RV annualisée des jours valides de chaque actif, du 2018-01-01 au 2019-12-31, enregistrée dans un fichier | Calculée sur l'apprentissage seulement, pour ne rien emprunter au futur. |
| Exécution | l'exposition décidée à la clôture de J s'applique au rendement de J+1 | On ne peut pas trader au prix d'une clôture qu'on vient juste d'observer. |
| Frais | 0,10 % de la valeur échangée ; sensibilité à 0,05 % et à 0,20 % | Ordre de grandeur réaliste ; la sensibilité est décrite sans changer la décision. |
| Comparaisons | buy and hold, et stratégie pilotée par HAR-RV | Montrer ce que la prévision apporte par rapport à ne rien faire, et par rapport au modèle classique. |
| Risque | VaR à 1 jour à 95 % = quantile de la loi normale × σ̂ journalière, sans annualisation (exception du 2026-11-14), pour tous les modèles ; test de Kupiec | La même règle pour tous rend la comparaison équitable. Les rendements crypto ont des queues épaisses : on s'attend à un test de Kupiec sévère. |

## 10. Explicabilité

| Règle | Valeur | Raison |
|---|---|---|
| Méthodes | SHAP sur XGBoost et LSTM ; attention du Transformer et du TFT | Comprendre quelles variables pèsent dans la prévision. |
| Règle de fidélité | permuter la variable la mieux classée par SHAP doit dégrader le QLIKE de validation plus que permuter la moins bien classée ; sinon, on écrit honnêtement que SHAP échoue sur ce modèle | Une explication n'a de valeur que si elle correspond au comportement réel du modèle. |

## 11. Entraînement (précisions datées du 2026-11-16, écrites avant tout entraînement)

### Données d'entrée et apprentissage

| Règle | Valeur | Raison |
|---|---|---|
| Un modèle par actif | BTC et ETH séparément, pour tous les modèles | Comparaison directe avec HAR-RV et GARCH, qui sont univariés. Limite : chaque réseau a moins de données. |
| Entrées | les 13 variables continues du jour J et le jour de la semaine ; les repères de comptage (`jour_remplace`, `fenetre_avec_jour_remplace`) ne sont jamais des entrées | Ces repères servent à compter les effets de la règle de secours, pas à prévoir. |
| XGBoost | tableau des variables du jour J, sans séquence ; jour de la semaine en entier | Un arbre coupe directement sur un entier. |
| Modèles séquentiels | séquences de 30 jours ; jour de la semaine en one-hot (7 colonnes de 0 et de 1) | Un réseau ne doit pas croire que dimanche (6) vaut « six fois » mardi (1). |
| TFT | jour de la semaine en variable catégorielle connue d'avance | C'est la façon prévue par le TFT de traiter un calendrier. |
| Normalisation | moyenne et écart-type appris sur la fenêtre d'ajustement de chaque pli, enregistrés en JSON et réappliqués tels quels ; log(RV) aussi normalisée pour les réseaux | Aucune information de la validation ou de l'évaluation ne sert à préparer les données. |
| Perte | erreur quadratique sur log(RV) pour tous les modèles réglés, TFT compris | Cohérent avec HAR-RV, ajusté par moindres carrés sur log(RV). QLIKE reste la métrique d'évaluation finale. |
| Limite du TFT | le TFT est entraîné en MSE comme les autres modèles, il ne fournit donc pas d'intervalles de quantiles ; ses normaliseurs internes sont désactivés (les données sont déjà normalisées avec le JSON du pli) | Même perte et même préparation pour tous : la comparaison est équitable. |
| Lightning allégé pour le TFT | sans barre de progression, journaux, sauvegardes automatiques ni résumé du modèle ; jeux de données construits une seule fois | Moins de fichiers inutiles. Vérifié le 2026-11-16 sur données aléatoires : prévisions identiques au bit près, sans gain de temps mesurable. |
| Choix des hyperparamètres | la plus petite erreur quadratique en log(RV), remise en unités de log(RV), sur la validation interne | Le choix ne regarde jamais la période évaluée. |
| Arrêt anticipé | réseaux : patience de 20 époques, 200 époques au plus ; XGBoost : patience de 50 arbres, 2000 arbres au plus ; sur la validation interne | On arrête quand le modèle cesse de progresser sur des jours non appris. |
| Dropout des réseaux récurrents | la même valeur entre les couches et à la sortie de la couche récurrente ; avec 1 couche, à la sortie seulement | Le dropout interne de torch n'agit qu'entre deux couches : sans cette règle, il ne ferait rien avec 1 couche. |

### Recherche des hyperparamètres

| Règle | Valeur | Raison |
|---|---|---|
| Méthode | recherche aléatoire, graine fixe (42), dans des espaces écrits d'avance | Rejouable, et aucun espace n'est élargi après avoir vu un résultat. |
| Nombre de combinaisons | le même N de combinaisons VALIDES pour XGBoost et pour chaque modèle de deep learning ; N fixé par une mesure de temps | Comparaison équitable : chaque modèle a la même chance d'être bien réglé. |
| Tirages incohérents | écartés et remplacés par la suite déterministe des tirages (même graine) ; leur nombre est rapporté | N reste le même pour tous, et le tirage reste rejouable. |
| Réglage (exception du 2026-11-16) | UNE SEULE FOIS par actif et par modèle (XGBoost compris), sur le premier découpage : ajustement du 2018-04-01 au 2019-06-30, validation interne du 2019-07-01 au 2019-12-31 ; N combinaisons avec une graine ; les hyperparamètres sont ensuite figés pour les 5 plis et le test final | Décision prise avec l'information disponible fin 2019, sans regarder l'avenir. Limite : réglage sur peu de données (un an et demi). |
| Graines | la combinaison retenue est entraînée avec les 3 graines (0, 1, 2) sur chacun des 6 découpages (5 plis et test final) | Mesurer la variabilité due au hasard de l'entraînement. Remarque : XGBoost avec subsample = colsample = 1 n'a aucun hasard, et ses graines donnent alors le même modèle. |
| Optimiseur (exception du 2026-11-16) | AdamW pour tous les modèles de deep learning | Le même optimiseur pour tous, avec un weight decay correctement appliqué. |

Espaces :

| Modèle | Espace |
|---|---|
| XGBoost | max_depth {2, 3, 4, 6} ; learning_rate log-uniforme [0,01 ; 0,1] ; au plus 2000 arbres avec arrêt anticipé ; subsample et colsample_bytree {0,6 ; 0,8 ; 1,0} ; min_child_weight {1, 5, 10} ; reg_lambda log-uniforme [0,1 ; 10] |
| LSTM et GRU | taille cachée {16, 32, 64} ; couches {1, 2} ; dropout {0 ; 0,1 ; 0,2 ; 0,3} ; taux d'apprentissage log-uniforme [1e-4 ; 3e-3] ; lot {32, 64} ; weight decay log-uniforme [1e-6 ; 1e-3] |
| CNN-LSTM | filtres {16, 32} ; noyau {3, 5} ; puis l'espace du LSTM |
| Transformer | d_model {16, 32, 64} ; têtes {2, 4} ; couches {1, 2} ; dimension feed-forward {64, 128} ; dropout, taux d'apprentissage, lot et weight decay comme le LSTM |
| TFT | hidden_size {8, 16, 32} ; têtes d'attention {1, 2, 4} ; hidden_continuous_size {8, 16}, avec hidden_continuous_size ≤ hidden_size ; dropout, taux d'apprentissage, lot et weight decay comme le LSTM |

### Reprise, mesures et suivi

| Règle | Valeur | Raison |
|---|---|---|
| Unités de calcul | une unité = (actif, modèle, pli, combinaison, graine), enregistrée dans son propre fichier dès qu'elle est finie (fichier temporaire, puis renommage) | Une coupure ne fait perdre que l'unité en cours. |
| Graine d'une unité | dérivée de son identifiant par hachage, jamais de l'ordre d'exécution | Une relance donne exactement les mêmes résultats, dans n'importe quel ordre. |
| Relance | les unités terminées et intactes sont sautées | Reprendre là où le calcul s'est arrêté. |
| Mise en veille | empêchée pendant le calcul, puis rétablie à la fin, même en cas d'erreur | Un calcul de plusieurs heures ne doit pas s'arrêter parce que l'écran se met en veille. |
| Mesures | sur des données aléatoires de même forme que les vraies (2441 exemples, prudent) ; aucune vraie donnée lue, contrôlé par un crochet d'audit | Fixer les réglages sans rien regarder des vraies données. |
| Fils de calcul | le plus rapide (médiane) parmi les nombres de fils (2, 4 ; 8 écarté le 2026-11-16, mesuré plus lent) qui donnent des exécutions identiques | La vitesse ne doit jamais coûter la reproductibilité. |
| Répétitions (exception du 2026-11-16) | 5 répétitions par mesure ; la médiane est retenue, l'écart min-max est rapporté | Les temps varient d'un essai à l'autre : la médiane résiste aux essais perturbés. |
| Alimentation (exception du 2026-11-16) | les scripts d'entraînement et de mesure refusent de démarrer sur batterie ; si le PC passe sur batterie pendant un calcul, ils s'arrêtent proprement après l'unité en cours (la reprise permet de continuer) | Des temps et un calcul fiables, et pas de calcul interrompu par une batterie vide. |
| Seuil de mémoire libre | pic du TFT et du Transformer dans leur plus grande configuration × 1,5, arrondi au 0,5 Go supérieur ; au-delà de 2,5 Go, arrêt et rapport avant de le fixer | Marge de sécurité, sur un poste où Chrome reste ouvert. |
| Budget N (exception du 2026-11-16) | plus grand entier N tel que 2 actifs × somme sur les 5 modèles de deep learning de (médiane d'une époque × 100) × (N + 3 graines × 6 découpages) ≤ 24 heures, réparties sur plusieurs nuits grâce à la reprise ; si N < 5, arrêt et rapport. Au départ : 11 découpages, 5 graines et 12 heures, soit environ 124 heures estimées : irréalisable | Un budget écrit d'avance, identique pour tous les modèles. |
| Suivi | si la durée réelle dépasse l'estimation de plus de 50 %, le calcul s'arrête proprement ; la décision est écrite comme exception datée ; N n'est jamais changé en silence | Garder la maîtrise du temps sans changer les règles en cours de route. |

## 12. Évaluation et baselines (précisions datées du 2026-11-16, écrites avant le calcul des baselines)

| Règle | Valeur | Raison |
|---|---|---|
| Persistance | référence descriptive : log RV(J+1) prévu = log RV(J), avec la même correction s² mesurée sur la validation interne ; hors de la règle de sélection et des tests de Diebold-Mariano principaux ; un test de Diebold-Mariano DESCRIPTIF de HAR-RV contre la persistance | Montrer ce qu'apporte HAR-RV par rapport à « ne rien faire ». |
| QLIKE | forme de Patton : RV²/h − ln(RV²/h) − 1, avec h la variance prévue | Elle vaut 0 si et seulement si la prévision est exacte : facile à vérifier à la main. |
| Diebold-Mariano | d = QLIKE(modèle) − QLIKE(HAR-RV) ; variance de long terme de Newey-West (noyau de Bartlett) ; correction de Harvey-Leybourne-Newbold ; loi de Student à T − 1 degrés de liberté ; test bilatéral ; moyenne négative : le modèle fait mieux que HAR-RV | Méthode standard, fixée avant de voir un résultat. |
| Bootstrap | blocs mobiles de 20 jours consécutifs, 1000 tirages, graine 42 ; intervalle par les percentiles 2,5 % et 97,5 % de la moyenne | Les blocs gardent l'enchaînement des jours. |
| Prévision d'un modèle réglé | moyenne des prévisions en log de ses 3 graines ; elle sert pour Diebold-Mariano, le bootstrap, les crises, les figures et le classement ; s² est mesuré sur la validation interne pour cette prévision moyenne ; les métriques de chaque graine (avec leur propre s²) sont rapportées avec leur moyenne et leur écart-type | Une seule série de prévisions est nécessaire pour un test. |
| Limite de la moyenne des graines | elle forme un petit ensemble : léger avantage par rapport à HAR-RV et GARCH, qui sont déterministes ; la même règle s'appliquera au deep learning | Écrite d'avance, pour ne pas surestimer un gain. |
| s² | variance centrée (ddof = 0) des résidus en log ; la moyenne des résidus est rapportée à part (vérification de l'exception 2) | Fidèle à la règle « variance des résidus en log ». |
| GARCH : données | log-rendements journaliers des variables (règle de secours comprise) multipliés par 100 pour la stabilité numérique ; moyenne constante ; estimation sur les rendements du début des données à la fin de la fenêtre d'ajustement | Même série que les autres modèles. Limite : rendement nul le jour remplacé et rendement sur deux jours le lendemain. |
| GARCH : facteur d'échelle | variance conditionnelle du jour t (information jusqu'à t − 1) comparée à RV² du jour t, sur les cibles de la fenêtre d'ajustement ; variance remise à l'échelle des rendements (÷ 10 000) | Alignement exact des jours, sans regarder la période évaluée. |
| GARCH : mise à jour | paramètres figés ; chaque jour, prévision à un jour avec les rendements connus jusqu'à J, sans réajustement ; série coupée à la dernière origine ; variance de départ (backcast) calculée sur la fenêtre d'ajustement puis fixée explicitement | Aucune donnée après J, ni après l'ajustement, n'entre dans une prévision. |
| XGBoost | les mêmes 12 combinaisons pour les deux actifs (graine 42) ; chaque combinaison entraînée avec une graine dérivée de son identifiant ; arrêt anticipé sur la validation interne de chaque découpage ; aucune normalisation (sans effet sur un arbre) | Comparaison équitable entre actifs. |
| Modèles du test final | entraînés et enregistrés (dossier ignoré par Git, empreintes dans un manifeste), sans AUCUNE prévision sur le test | Le test reste fermé. |
| Sorties journalières | prévisions jour par jour, unités de reprise et modèles dans `sorties/`, ignoré par Git, jamais commité | Règle de licence : aucune série journalière dérivée dans le dépôt. |
| Test de l'avenir modifié des prévisions | pour la persistance, HAR-RV, GARCH et XGBoost : toutes les données après J sont modifiées (facteur 10 avec bruit) ; les prévisions des origines ≤ J doivent rester identiques au bit près ; témoin : un GARCH dont la variance de départ est calculée sur toute la série doit être détecté | Prouver qu'aucune prévision n'utilise l'avenir. |

## 13. Tests multiples (précision datée du 2026-11-19, écrite AVANT de lire les résultats du deep learning)

| Règle | Valeur | Raison |
|---|---|---|
| Ajustement | méthode de Holm, appliquée par actif à toutes les comparaisons contre HAR-RV sur les plis réunis : GARCH, XGBoost, LSTM, GRU, CNN-LSTM, Transformer et TFT, soit 7 tests ; le test descriptif de HAR-RV contre la persistance n'en fait pas partie | Avec 7 tests au seuil de 5 %, la probabilité d'au moins un « significatif » dû au hasard dépasse nettement 5 %. Holm la ramène à 5 % au plus, sans hypothèse sur la dépendance entre les tests. |
| Méthode de Holm | les p-valeurs sont rangées de la plus petite à la plus grande ; la k-ième (k = 1 à m) est multipliée par (m − k + 1) ; on garde la plus grande valeur rencontrée jusque-là, plafonnée à 1 | Méthode standard, plus puissante que Bonferroni, fixée avant de voir un résultat. |
| Rapport | les p-valeurs brutes ET ajustées sont rapportées ; les phrases « significatif » de la lecture des résultats s'appuient sur les p-valeurs AJUSTÉES | Les deux restent visibles, mais la conclusion tient compte du nombre de tests. |

## 14. Contrôles de fuite (précision datée du 2026-11-19, écrite AVANT les contrôles sur les vraies données)

| Règle | Valeur | Raison |
|---|---|---|
| Seuil d'alerte | si un réseau bat HAR-RV de plus de 20 % en QLIKE moyen (jours réunis ou moyenne par pli), arrêt avant d'écrire quoi que ce soit, et recherche d'une fuite ; sans effet sur les calculs | Un gain trop beau est d'abord un signal d'erreur. Le seuil était une consigne ; il est maintenant écrit dans les règles. |
| Avenir modifié, vraies données | pli 5 (le plus grand découpage qui a une période évaluée) ; J = 2024-07-01, au milieu de la période évaluée ; bougies après la fin de J multipliées par 10 avec un bruit ; 5 réseaux, combinaison retenue, graine 0 des plis, 2 époques ; 0 écart admis au bit près sur les prévisions des origines ≤ J ; contrôle d'effet : des prévisions après J doivent changer | Prouver sur les vraies données qu'aucun réseau n'utilise l'avenir. Le découpage du test final n'a pas de période évaluée ouverte. |
| Témoin « cible mélangée » | LSTM, combinaison retenue, graine 0 des plis, 5 plis, chaque actif ; cibles de la fenêtre d'ajustement permutées au hasard (graine 42) ; validation interne et évaluation avec les vraies cibles ; arrêt si son gain sur HAR-RV est positif ou nul (l'une ou l'autre définition du QLIKE moyen) | Un réseau qui ne peut rien apprendre doit faire moins bien que HAR-RV. S'il fait aussi bien, c'est que l'information vient d'ailleurs que de l'apprentissage : fuite probable. |

## 15. Stratégie (précisions datées du 2026-11-19, écrites AVANT le calcul de la stratégie)

| Règle | Valeur | Raison |
|---|---|---|
| Période | jours du 2020-01-01 au 2024-12-31 (les 5 plis) ; le test final reste fermé | Les prévisions n'existent que sur les plis évalués. |
| Rendement | rendement simple de clôture à clôture de la série remplacée : seuls les prix des jours valides servent | Pas de prix tiré d'une journée incomplète. |
| Jour non valide | aucune décision à sa clôture ; l'exposition de la dernière clôture valide reste en place jusqu'à la clôture valide suivante ; aucun frais ce jour-là. Le mouvement sur deux jours qui suit est donc porté par une exposition décidée avant tout ce mouvement | Solution la plus prudente : on ne décide jamais sur une journée incomplète, et aucun mouvement de prix n'est caché. |
| Départ et frais | exposition nulle avant le 2020-01-01 : l'entrée paie des frais, achat simple compris ; frais = taux × variation d'exposition × valeur du portefeuille ; la dérive du poids entre deux rééquilibrages est ignorée (limite) | Même traitement pour toutes les stratégies. |
| Mesures | rendement annualisé géométrique sur 365 jours ; Sharpe = moyenne / écart-type des rendements journaliers × racine(365) ; Sortino avec l'écart à la baisse racine(moyenne(min(r, 0)²)) ; rotation = somme des variations d'exposition × 365 / nombre de jours | Formules fixées avant de voir un résultat. |
| Intervalles | bootstrap à blocs mobiles (20 jours, 1000 tirages, graine 42) du Sharpe, et de la différence de Sharpe entre le modèle retenu et HAR-RV avec les mêmes indices pour les deux séries | La différence garde le lien jour par jour entre les deux stratégies. |
| VaR | quantile exact de la loi normale (1,6448536…) × σ̂ journalière ; jours exclus : jour non valide et son lendemain (rendement nul ou sur deux jours) | Comparer une VaR à un jour à un vrai rendement à un jour. |
| Comparaisons | principales : modèle retenu, HAR-RV, achat simple ; autres modèles : descriptifs | La sélection est faite par QLIKE ; la stratégie ne choisit rien. |
| Présentation | volatilité réalisée à ±10 % de la cible = « proche de la cible » | Seuil de présentation, sans effet sur aucun calcul. |

## 16. Explicabilité (précisions datées du 2026-11-19, écrites et commitées AVANT tout calcul)

| Règle | Valeur | Raison |
|---|---|---|
| Période | jours évalués des 5 plis (2020 à 2024) ; le test final reste fermé | Expliquer sans rien regarder du test. |
| Modèles SHAP | XGBoost et LSTM (règle d'origine), plus le modèle retenu de chaque actif : Transformer (BTC) et CNN-LSTM (ETH) ; extension descriptive décidée avant le calcul | Expliquer aussi les modèles choisis par la règle de sélection. |
| Méthode pour les réseaux | GradientExplainer de shap (gradients espérés), 1000 tirages ; fond de 100 séquences tirées dans la fenêtre d'ajustement du pli (graine 42) | DeepExplainer ne gère pas les couches LSTM ni l'attention écrites avec torch ; GradientExplainer fonctionne avec tout réseau dérivable. Mesuré sur des données aléatoires : erreur d'additivité d'environ 3,7 % avec 1000 tirages, 8 % avec 200. |
| Méthode pour XGBoost | TreeExplainer (calcul exact sur les arbres, sans fond), sur les modèles des plis ré-entraînés à l'identique | Méthode exacte pour les arbres. Les modèles des plis n'avaient pas été enregistrés : on les ré-entraîne avec les mêmes graines. |
| Reproduction | modèles rechargés (réseaux) ou ré-entraînés (XGBoost) : prévisions identiques à celles des unités du calcul, à 1e-9 près | On explique exactement les modèles évalués. |
| Additivité | réseaux : moyenne de \|prévision − base − somme des contributions\| divisée par la moyenne de \|prévision − base\| ≤ 0,06, par modèle et pli ; XGBoost : écart maximal ≤ 1e-4 (float32) ; au-delà, arrêt avant toute écriture | SHAP répartit l'écart à la valeur de base entre les entrées : la somme doit le retrouver. GradientExplainer est une approximation par tirages, d'où la tolérance. |
| Importance | contributions en unités de log(RV) (réseaux : × écart-type de la cible du pli) ; moyenne des valeurs absolues sur les jours, puis somme sur les 30 retards (par variable) ou sur les variables (par retard) ; jour de la semaine = somme de ses 7 colonnes ; moyenne des 3 graines, puis des 5 plis | Même unité pour tous les modèles ; une seule valeur par variable et par retard. |
| Retard | 1 = jour J (veille de la cible), 30 = jour J − 29 | Le retard compte les jours avant la cible. |
| Attention du Transformer | ligne du jour J des poids d'attention, moyenne sur les têtes et les couches, par retard ; jours de crise (date de cible dans une crise) comparés aux autres jours évalués | La prévision part du jour J : c'est sa ligne d'attention qui compte. |
| TFT | importance des variables de l'encodeur et attention par retard (interpret_output de pytorch-forecasting) | Outils prévus par le TFT. |
| Fidélité (règle d'origine, précisée) | sur la validation interne de chaque pli : la variable la mieux classée et la moins bien classée par SHAP (importance du pli) sont permutées entre les jours (la variable entière, sur ses 30 jours), 20 répétitions, graine 42 ; prévision = moyenne des log des 3 graines avec le s² de la validation sans permutation ; dégradation = QLIKE moyen permuté − QLIKE sans permutation ; fidèle si la meilleure dégrade plus que la moins bonne ; conclusion « fidèle sur k plis sur 5 » | Vérifier que le classement SHAP correspond au comportement réel du modèle. |
| Témoin de fidélité | une variable de bruit pur ajoutée à un petit modèle sur données synthétiques doit être classée dernière, et sa permutation doit dégrader le QLIKE de moins de 1 % de la dégradation due à la meilleure variable | Montrer que la méthode sait reconnaître une variable inutile. |
| Limite | l'attention montre où le modèle regarde, pas nécessairement pourquoi il décide | Une attention forte n'est pas une preuve de cause. |
