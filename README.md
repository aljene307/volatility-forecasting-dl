# Prévision de la volatilité des cryptomonnaies par deep learning

Ce projet prévoit la volatilité réalisée du lendemain du bitcoin et de l'ether, à partir de bougies de 5 minutes. Il compare des modèles de deep learning (LSTM, GRU, CNN-LSTM, Transformer, TFT) à des références classiques (HAR-RV, GARCH) et à XGBoost, avec un découpage chronologique strict. Les prévisions pilotent ensuite une stratégie simple de gestion du risque.

**Statut : en construction.** Aucun résultat n'est encore disponible.

## Données

- Source : bougies de 5 minutes de Binance spot (data.binance.vision), pour BTCUSDT et ETHUSDT.
- Licence : en cours de vérification.
- Aucune donnée brute n'est stockée dans ce dépôt.

## Documentation

- [Règles du projet](docs/REGLES.md) : chaque règle, sa valeur et sa raison.
- [Journal des choix](docs/CHOIX.md) : chaque décision, avec sa raison et ses mesures.

## Règles et exceptions

Les règles ont été écrites et commitées avant tout téléchargement de données et tout calcul (commit 31b9dae). Les précisions apportées ensuite sont des exceptions datées, expliquées dans le [journal des choix](docs/CHOIX.md) :

1. 2026-11-14 — GARCH(1,1) : paramètres et facteur d'échelle appris sur la fenêtre d'ajustement seule, comme tous les autres modèles.
2. 2026-11-14 — Mesure de s² sur la validation interne, qui sert aussi au réglage : limite acceptée et écrite (elle désavantage XGBoost et le deep learning sous QLIKE).
3. 2026-11-14 — Annualisation : la volatilité prévue est journalière ; elle est annualisée pour la stratégie, pas pour la VaR à 1 jour.
4. 2026-11-14 — Création de ce README pour lister les exceptions.
