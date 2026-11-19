# Prévision de la volatilité des cryptomonnaies par deep learning

Ce projet prévoit la volatilité réalisée du lendemain du bitcoin et de l'ether, à partir de bougies de 5 minutes. Il compare des modèles de deep learning (LSTM, GRU, CNN-LSTM, Transformer, TFT) à des références classiques (HAR-RV, GARCH) et à XGBoost, avec un découpage chronologique strict. Les prévisions pilotent ensuite une stratégie simple de gestion du risque.

**Statut : en construction.** Les résultats du développement (2020 à 2024) sont disponibles ; le test final reste fermé.

## Données et licence

- Source : bougies mensuelles de 5 minutes de Binance spot (data.binance.vision), pour BTCUSDT et ETHUSDT, de 2018-01 à 2026-10.
- Les données sont fournies par Binance sous la licence CC BY-NC-SA 4.0 et les conditions « Vision Dataset Terms ». Elles sont utilisées ici dans un cadre éducatif et non commercial.
  - Conditions : https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md
  - Page officielle : https://data.binance.vision/terms-of-use.html
- Le code de ce dépôt est sous licence MIT (le code seul).
- Tout ce qui est dérivé des données (graphiques, résultats, modèles entraînés, fichiers ONNX) est sous licence CC BY-NC-SA 4.0, avec la mention « Données : Binance Vision ».
- Aucune donnée brute ni aucune série journalière dérivée n'est stockée dans ce dépôt. Seuls sont commités les manifestes (noms, tailles et empreintes SHA-256 des fichiers) et le rapport de qualité, qui ne contient que des comptages.
- API et application : décision reportée à cette étape ; par défaut, seuls des résultats agrégés et des graphiques seront exposés, jamais un flux de données.
- Pour reconstruire les données : `src/telecharger.py`, puis `src/convertir.py`, puis `src/qualite.py`, puis `src/variables.py`, puis `src/exploration.py`.

## Documentation

- [Règles du projet](docs/REGLES.md) : chaque règle, sa valeur et sa raison.
- [Journal des choix](docs/CHOIX.md) : chaque décision, avec sa raison et ses mesures.
- [Qualité des données](docs/QUALITE_DONNEES.md) : comptages générés par le contrôle de qualité.

## Avancement

- Étape 4 — Volatilité réalisée, variables, cible et analyse exploratoire (développement seulement) : [analyse exploratoire](docs/EXPLORATION.md) ; figures : [RV annualisée](figures/figure_1_rv_annualisee.png), [autocorrélation de log(RV)](figures/figure_2_autocorrelation_log_rv.png), [histogrammes](figures/figure_3_histogrammes_rv.png).
- Étape 5 — Baselines sur le développement (persistance, HAR-RV, GARCH, XGBoost ; 5 plis annuels) : [résultats](docs/RESULTATS_BASELINES.md) ; figures : [BTC](figures/figure_4_previsions_BTCUSDT.png), [ETH](figures/figure_4_previsions_ETHUSDT.png). Le test final reste fermé.
- Étape 6 — Deep learning (LSTM, GRU, CNN-LSTM, Transformer, TFT ; entraînement `src/entrainer.py`, suivi `src/suivi.py`) : [comparaison de tous les modèles](docs/RESULTATS_DL.md) (`src/comparer.py`) ; figures : [BTC](figures/figure_5_deep_learning_BTCUSDT.png), [ETH](figures/figure_5_deep_learning_ETHUSDT.png) ; empreintes des poids : [manifeste](rapports/modeles_deep_learning.json). Le test final reste fermé.
- Étape 7 — Stratégie de volatility targeting sur le développement (`src/strategie.py`) : [résultats](docs/STRATEGIE.md) ; figures : [BTC](figures/figure_6_strategie_BTCUSDT.png), [ETH](figures/figure_6_strategie_ETHUSDT.png). Le test final reste fermé.
- Étape 8 — Explicabilité sur le développement (SHAP, attention, fidélité ; `src/explicabilite.py`) : [résultats](docs/EXPLICABILITE.md) ; figures : importance des variables ([BTC](figures/figure_7_importance_variables_BTCUSDT.png), [ETH](figures/figure_7_importance_variables_ETHUSDT.png)), importance par retard ([BTC](figures/figure_8_importance_retards_BTCUSDT.png), [ETH](figures/figure_8_importance_retards_ETHUSDT.png)), [attention du Transformer](figures/figure_9_attention_transformer.png). Le test final reste fermé.
- Étape 9 — Test final : **en préparation, le test reste fermé**. [Attentes écrites avant l'ouverture](docs/ATTENTES_TEST.md) ; modèle descriptif HAR-J (`src/har_j.py`, résultats dans la [comparaison](docs/RESULTATS_DL.md)) ; programme d'ouverture `src/ouvrir_test.py`, vérifié sur 2024.

## Règles et exceptions

Les règles ont été écrites et commitées avant tout téléchargement de données et tout calcul (commit 31b9dae). Les précisions apportées ensuite sont des exceptions datées, expliquées dans le [journal des choix](docs/CHOIX.md) :

1. 2026-11-14 — GARCH(1,1) : paramètres et facteur d'échelle appris sur la fenêtre d'ajustement seule, comme tous les autres modèles.
2. 2026-11-14 — Mesure de s² sur la validation interne, qui sert aussi au réglage : limite acceptée et écrite (elle désavantage XGBoost et le deep learning sous QLIKE ; affirmation retirée le 2026-11-16, voir la rectification ci-dessous).
3. 2026-11-14 — Annualisation : la volatilité prévue est journalière ; elle est annualisée pour la stratégie, pas pour la VaR à 1 jour.
4. 2026-11-14 — Création de ce README pour lister les exceptions.
5. 2026-11-14 — Les 241 bougies désalignées de février 2018 (cas non prévu par les règles) sont traitées comme manquantes.
6. 2026-11-14 — Un trou entre deux bougies est attribué aux deux jours qu'il touche.
7. 2026-11-16 — Plis annuels : 5 plis de 12 mois au lieu de 10 plis de 6 mois (mêmes jours évalués).
8. 2026-11-16 — Hyperparamètres réglés une seule fois par actif et par modèle, sur le premier découpage (information disponible fin 2019), puis figés.
9. 2026-11-16 — 3 graines au lieu de 5 ; optimiseur AdamW ; XGBoost suit les mêmes règles.
10. 2026-11-16 — Budget de 24 heures pour le deep learning, avec une nouvelle formule de N et des mesures répétées 5 fois (médiane).
11. 2026-11-16 — Les calculs refusent de démarrer sur batterie, et s'arrêtent proprement si le PC passe sur batterie.

Ces exceptions du 2026-11-16 remplacent une règle initiale irréalisable (mesures dans le [journal des choix](docs/CHOIX.md)), avant tout entraînement sur les vraies données.

Précisions datées du 2026-11-16, écrites avant le calcul des baselines (section 12 des [règles](docs/REGLES.md)) :

- référence descriptive « persistance » (demain comme aujourd'hui), hors de la sélection et des tests principaux ;
- formes exactes de QLIKE, du test de Diebold-Mariano et du bootstrap par blocs ;
- prévision d'un modèle réglé = moyenne des prévisions de ses graines (limite : petit ensemble) ;
- GARCH sans aucune information postérieure à la fenêtre d'ajustement ou à l'origine de la prévision ;
- prévisions journalières jamais commitées ; aucune prévision sur le test final ;
- test de l'avenir modifié appliqué aux prévisions de chaque baseline.

Précision et rectification datées du 2026-11-16, décidées APRÈS avoir vu les résultats des baselines (détails dans le [journal des choix](docs/CHOIX.md)) :

- QLIKE moyen de la règle de sélection : les deux définitions (tous les jours réunis, moyenne des moyennes par pli) sont rapportées ; si elles diffèrent, la moyenne des moyennes par pli s'applique ;
- rectification de l'exception 2 : l'affirmation selon laquelle le biais de s² désavantage les modèles réglés n'est vérifiée que pour les plis 1 à 3 ; dans les plis 4 et 5, XGBoost prévoit trop haut sur la validation interne (valeurs dans les [résultats des baselines](docs/RESULTATS_BASELINES.md)) ; l'affirmation est retirée. Explication probable, non démontrée : un modèle à arbres ne peut pas prévoir sous les valeurs vues à l'apprentissage, et ces validations tombent sur des périodes calmes.

Précision datée du 2026-11-19, écrite AVANT de lire les résultats du deep learning (section 13 des [règles](docs/REGLES.md)) :

- tests multiples : les p-valeurs de Diebold-Mariano contre HAR-RV (GARCH, XGBoost et les 5 réseaux, par actif) sont rapportées brutes et ajustées par la méthode de Holm ; « significatif » s'appuie sur la p-valeur ajustée.

Précision datée du 2026-11-19, écrite avant les contrôles de fuite sur les vraies données (section 14 des [règles](docs/REGLES.md)) :

- seuil d'alerte de fuite (gain sur HAR-RV de plus de 20 %) écrit dans les règles ; test de l'avenir modifié des 5 réseaux sur les vraies données ; témoin « cible mélangée » (résultats : [contrôles de fuite](rapports/controles_fuite.json)).

Précisions datées du 2026-11-19 pour la stratégie, écrites avant son calcul (section 15 des [règles](docs/REGLES.md)) :

- jour non valide : aucune décision, l'exposition précédente reste en place ; exposition initiale nulle (l'entrée paie des frais) ; formules exactes des mesures, du bootstrap du Sharpe et de la VaR (jours non valides et leurs lendemains exclus).

Précisions datées du 2026-11-19 pour l'explicabilité, écrites et commitées avant tout calcul (section 16 des [règles](docs/REGLES.md)) :

- SHAP sur XGBoost, le LSTM et le modèle retenu de chaque actif (GradientExplainer pour les réseaux, TreeExplainer pour XGBoost) ; attention du Transformer et du TFT ; règle de fidélité précisée, avec un témoin ; limite : l'attention montre où le modèle regarde, pas nécessairement pourquoi il décide.

Précisions datées du 2026-11-19, écrites AVANT l'ouverture du test final (section 17 des [règles](docs/REGLES.md)) :

- modèle descriptif HAR-J (HAR-RV + jour de la semaine de la cible) ; [attentes du test final](docs/ATTENTES_TEST.md) (hypothèses H1 à H6 et prévision chiffrée) ; un seul chemin d'ouverture, avec ses préconditions et un mode de vérification sur 2024.

Sensibilité descriptive du 2026-11-19, décidée APRÈS avoir vu les gains par année (détails dans le [journal des choix](docs/CHOIX.md)) :

- gain sur HAR-RV et Diebold-Mariano (p-valeurs brutes et ajustées par Holm) sans 2024, et calibration de HAR-RV par année ; sans effet sur le classement ni la sélection.

Précisions datées du 2026-11-15, écrites avant le calcul des variables (détail et raisons dans les [règles](docs/REGLES.md)) :

- ligne journalière (ouverture, plus haut, plus bas, clôture, volume en USDT) et formules exactes des variables (RV moyennes, Parkinson, Garman-Klass, RSI de Wilder, MACD divisé par la clôture, largeur de Bollinger) ;
- règle de secours : la ligne entière d'un jour non valide est remplacée par celle du dernier jour valide, avec sa limite (rendement nul ce jour-là, rendement sur deux jours le lendemain) et ses comptages ;
- validité d'un jour en entrée calculée sur le passé seulement, avec un contrôle automatique ;
- empreinte des variables dans un manifeste séparé ;
- garde du test aveugle sans aucune option de contournement ;
- exploration sur le développement seulement (autocorrélation, test ADF).

Précisions datées du 2026-11-16, écrites avant tout entraînement (section 11 des [règles](docs/REGLES.md)) :

- un modèle par actif ; entrées et encodage du jour de la semaine propres à chaque famille de modèles ; normalisation apprise sur la fenêtre d'ajustement de chaque pli ;
- perte en erreur quadratique sur log(RV) pour tous les modèles réglés, TFT compris (limite : pas d'intervalles de quantiles pour le TFT) ; arrêt anticipé ;
- recherche aléatoire dans des espaces écrits d'avance, avec le même nombre de combinaisons valides pour chaque modèle réglé ;
- reprise après interruption avec des graines dérivées de l'identifiant de chaque calcul ;
- mesures sur des données aléatoires pour fixer les fils de calcul, le seuil de mémoire et le budget, avec une règle de suivi de la durée.
