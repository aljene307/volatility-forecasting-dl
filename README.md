# Prévision de la volatilité des cryptomonnaies par deep learning

Ce projet prévoit la volatilité réalisée du lendemain du bitcoin et de l'ether, à partir de bougies de 5 minutes. Il compare des modèles de deep learning (LSTM, GRU, CNN-LSTM, Transformer, TFT) à des références classiques (HAR-RV, GARCH) et à XGBoost, avec un découpage chronologique strict. Les prévisions pilotent ensuite une stratégie simple de gestion du risque.

**Statut : en construction.** Aucun résultat n'est encore disponible.

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

## Règles et exceptions

Les règles ont été écrites et commitées avant tout téléchargement de données et tout calcul (commit 31b9dae). Les précisions apportées ensuite sont des exceptions datées, expliquées dans le [journal des choix](docs/CHOIX.md) :

1. 2026-11-14 — GARCH(1,1) : paramètres et facteur d'échelle appris sur la fenêtre d'ajustement seule, comme tous les autres modèles.
2. 2026-11-14 — Mesure de s² sur la validation interne, qui sert aussi au réglage : limite acceptée et écrite (elle désavantage XGBoost et le deep learning sous QLIKE).
3. 2026-11-14 — Annualisation : la volatilité prévue est journalière ; elle est annualisée pour la stratégie, pas pour la VaR à 1 jour.
4. 2026-11-14 — Création de ce README pour lister les exceptions.
5. 2026-11-14 — Les 241 bougies désalignées de février 2018 (cas non prévu par les règles) sont traitées comme manquantes.
6. 2026-11-14 — Un trou entre deux bougies est attribué aux deux jours qu'il touche.

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
