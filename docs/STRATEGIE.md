# Stratégie de volatility targeting (développement, 2020 à 2024)

Fichier généré par `src/strategie.py` à partir de `rapports/strategie.json` : ne pas le modifier à la main.

- Exposition décidée à la clôture de J = volatilité cible annuelle / (σ̂ de J+1 × racine(365)), bornée entre 0 et 1, appliquée au rendement simple de J+1 ; liquidités à 0 % ; rééquilibrage quotidien.
- Frais : 0,10 % de la variation d'exposition ; sensibilité à 0,05 % et à 0,20 %.
- Jour non valide : aucune décision, l'exposition précédente reste en place (précision du 2026-11-19).
- Modèle retenu (règle de sélection sur QLIKE) et HAR-RV : comparaisons principales ; les autres modèles sont descriptifs. Aucune optimisation de la stratégie ; le test final est fermé.
- Sharpe et Sortino : taux sans risque nul, annualisation sur 365 jours ; intervalles à 95 % par bootstrap à blocs mobiles (20 jours, 1000 tirages, graine 42).

## BTCUSDT

Volatilité cible : 57,3 % par an. Modèle retenu : **Transformer**. Jours : 1 827, dont 15 non valides.

### Mesures (frais de 0,10 %)

| Stratégie | Rendement annualisé | Volatilité (÷ cible) | Sharpe [IC 95 %] | Sortino | Drawdown max | Rotation annuelle | Frais par an | Frais totaux | Exposition moyenne |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| Achat simple (principal) | 66,9 % | 64,8 % (1,13) | 1,12 [0,20 ; 2,13] | 1,64 | −76,6 % | 0,2 | 0,02 % | 0,10 % | 100,0 % |
| HAR-RV (principal) | 45,8 % | 52,8 % (0,92) | 0,98 [−0,06 ; 2,02] | 1,42 | −74,9 % | 19,8 | 1,98 % | 31,70 % | 88,2 % |
| Transformer (principal) | 42,3 % | 51,1 % (0,89) | 0,95 [−0,08 ; 1,98] | 1,37 | −74,2 % | 20,9 | 2,09 % | 29,40 % | 86,5 % |
| GARCH(1,1) (descriptif) | 51,8 % | 53,7 % (0,94) | 1,05 [0,02 ; 2,08] | 1,51 | −72,3 % | 6,0 | 0,60 % | 9,59 % | 87,7 % |
| XGBoost (descriptif) | 41,1 % | 53,0 % (0,93) | 0,92 [−0,11 ; 1,93] | 1,32 | −75,9 % | 20,4 | 2,04 % | 29,29 % | 88,2 % |
| LSTM (descriptif) | 44,7 % | 51,2 % (0,89) | 0,98 [−0,02 ; 2,00] | 1,43 | −74,4 % | 19,0 | 1,90 % | 29,15 % | 86,8 % |
| GRU (descriptif) | 43,8 % | 50,8 % (0,89) | 0,97 [−0,04 ; 2,01] | 1,41 | −73,8 % | 20,4 | 2,04 % | 30,29 % | 86,6 % |
| CNN-LSTM (descriptif) | 45,3 % | 50,8 % (0,89) | 0,99 [0,00 ; 2,01] | 1,45 | −73,7 % | 18,3 | 1,83 % | 28,42 % | 86,9 % |
| TFT (descriptif) | 44,5 % | 51,7 % (0,90) | 0,98 [−0,02 ; 1,99] | 1,40 | −73,8 % | 17,0 | 1,70 % | 24,57 % | 86,8 % |
| Persistance (descriptive) | 38,0 % | 49,7 % (0,87) | 0,90 [−0,12 ; 1,92] | 1,31 | −75,0 % | 39,9 | 3,99 % | 56,83 % | 83,8 % |

Différence de Sharpe Transformer − HAR-RV (descriptif) : −0,03 [−0,11 ; 0,05].
Frais par an : coût moyen en points de rendement par an. Frais totaux : somme des frais payés, en part du capital de départ (ils grossissent avec la valeur du portefeuille). Rotation annuelle : somme des variations d'exposition par an.

### Sensibilité aux frais (descriptif)

| Stratégie | Sharpe à 0,05 % | Sharpe à 0,10 % | Sharpe à 0,20 % |
|---|---:|---:|---:|
| Achat simple | 1,12 | 1,12 | 1,12 |
| HAR-RV | 1,00 | 0,98 | 0,94 |
| Transformer | 0,97 | 0,95 | 0,91 |

### Par année (descriptif)

| Stratégie | Mesure | 2020 | 2021 | 2022 | 2023 | 2024 |
|---|---|---:|---:|---:|---:|---:|
| Achat simple | Rendement | 301,6 % | 59,8 % | −64,2 % | 155,6 % | 121,3 % |
| Achat simple | Volatilité | 75,1 % | 80,6 % | 63,7 % | 44,1 % | 53,1 % |
| Achat simple | Sharpe | 2,26 | 0,98 | −1,29 | 2,35 | 1,76 |
| Achat simple | Drawdown max | −53,6 % | −53,1 % | −66,9 % | −20,0 % | −26,2 % |
| HAR-RV | Rendement | 210,5 % | 18,7 % | −61,7 % | 135,0 % | 99,0 % |
| HAR-RV | Volatilité | 61,3 % | 56,5 % | 53,8 % | 42,4 % | 47,4 % |
| HAR-RV | Sharpe | 2,17 | 0,59 | −1,51 | 2,22 | 1,68 |
| HAR-RV | Drawdown max | −47,5 % | −46,0 % | −64,5 % | −19,4 % | −28,6 % |
| Transformer | Rendement | 177,9 % | 23,1 % | −62,0 % | 139,9 % | 87,3 % |
| Transformer | Volatilité | 57,0 % | 55,6 % | 51,8 % | 42,2 % | 47,0 % |
| Transformer | Sharpe | 2,09 | 0,65 | −1,60 | 2,29 | 1,57 |
| Transformer | Drawdown max | −45,8 % | −46,0 % | −64,4 % | −19,5 % | −29,9 % |

### Crises (descriptif)

| Stratégie | Covid : rendement / drawdown max | Terra-Luna : rendement / drawdown max | FTX : rendement / drawdown max |
|---|---:|---:|---:|
| Achat simple | 1,1 % / −47,4 % | −47,0 % / −52,2 % | −19,3 % / −25,9 % |
| HAR-RV | −7,5 % / −40,5 % | −39,6 % / −42,8 % | −16,5 % / −23,2 % |
| Transformer | −7,0 % / −38,6 % | −37,5 % / −40,7 % | −15,7 % / −21,7 % |

### VaR à 1 jour à 95 % et test de Kupiec

VaR = quantile de la loi normale (1,6449) × σ̂ journalière, sur le rendement de l'actif. Jours exclus (jour non valide ou lendemain : rendement nul ou sur deux jours) : 30.

| Modèle | Jours | Dépassements | Taux (attendu 5 %) | Statistique LR | p-valeur | Rejet à 5 % |
|---|---:|---:|---:|---:|---:|---|
| HAR-RV | 1 797 | 78 | 4,34 % | 1,72 | 0,1899 | non |
| GARCH(1,1) | 1 797 | 64 | 3,56 % | 8,66 | 0,0032 | oui |
| XGBoost | 1 797 | 70 | 3,90 % | 4,98 | 0,0257 | oui |
| LSTM | 1 797 | 68 | 3,78 % | 6,08 | 0,0136 | oui |
| GRU | 1 797 | 69 | 3,84 % | 5,52 | 0,0188 | oui |
| CNN-LSTM | 1 797 | 68 | 3,78 % | 6,08 | 0,0136 | oui |
| Transformer | 1 797 | 69 | 3,84 % | 5,52 | 0,0188 | oui |
| TFT | 1 797 | 68 | 3,78 % | 6,08 | 0,0136 | oui |
| Persistance (descriptive) | 1 797 | 82 | 4,56 % | 0,74 | 0,3888 | non |

Figure : `figures/figure_6_strategie_BTCUSDT.png`.

## ETHUSDT

Volatilité cible : 73,9 % par an. Modèle retenu : **CNN-LSTM**. Jours : 1 827, dont 15 non valides.

### Mesures (frais de 0,10 %)

| Stratégie | Rendement annualisé | Volatilité (÷ cible) | Sharpe [IC 95 %] | Sortino | Drawdown max | Rotation annuelle | Frais par an | Frais totaux | Exposition moyenne |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| Achat simple (principal) | 91,5 % | 84,4 % (1,14) | 1,20 [0,32 ; 2,16] | 1,78 | −79,3 % | 0,2 | 0,02 % | 0,10 % | 100,0 % |
| HAR-RV (principal) | 67,0 % | 67,8 % (0,92) | 1,10 [0,15 ; 2,10] | 1,63 | −77,9 % | 18,4 | 1,84 % | 82,79 % | 89,4 % |
| CNN-LSTM (principal) | 60,1 % | 64,9 % (0,88) | 1,05 [0,07 ; 2,07] | 1,55 | −77,9 % | 19,0 | 1,90 % | 69,38 % | 87,1 % |
| GARCH(1,1) (descriptif) | 85,5 % | 68,8 % (0,93) | 1,24 [0,30 ; 2,25] | 1,86 | −72,5 % | 9,4 | 0,94 % | 56,34 % | 88,7 % |
| XGBoost (descriptif) | 65,2 % | 68,2 % (0,92) | 1,08 [0,15 ; 2,06] | 1,60 | −78,7 % | 21,7 | 2,17 % | 94,88 % | 89,4 % |
| LSTM (descriptif) | 65,3 % | 66,7 % (0,90) | 1,09 [0,14 ; 2,08] | 1,61 | −78,1 % | 16,8 | 1,68 % | 72,92 % | 88,4 % |
| GRU (descriptif) | 66,1 % | 65,4 % (0,89) | 1,10 [0,17 ; 2,11] | 1,64 | −77,6 % | 19,3 | 1,93 % | 88,57 % | 87,4 % |
| Transformer (descriptif) | 68,7 % | 67,1 % (0,91) | 1,12 [0,19 ; 2,13] | 1,66 | −77,1 % | 18,9 | 1,89 % | 85,56 % | 88,9 % |
| TFT (descriptif) | 67,3 % | 67,0 % (0,91) | 1,11 [0,17 ; 2,12] | 1,64 | −78,9 % | 18,9 | 1,89 % | 89,10 % | 88,8 % |
| Persistance (descriptive) | 57,3 % | 64,4 % (0,87) | 1,03 [0,06 ; 2,01] | 1,53 | −78,4 % | 33,5 | 3,35 % | 126,96 % | 86,0 % |

Différence de Sharpe CNN-LSTM − HAR-RV (descriptif) : −0,05 [−0,13 ; 0,04].
Frais par an : coût moyen en points de rendement par an. Frais totaux : somme des frais payés, en part du capital de départ (ils grossissent avec la valeur du portefeuille). Rotation annuelle : somme des variations d'exposition par an.

### Sensibilité aux frais (descriptif)

| Stratégie | Sharpe à 0,05 % | Sharpe à 0,10 % | Sharpe à 0,20 % |
|---|---:|---:|---:|
| Achat simple | 1,20 | 1,20 | 1,20 |
| HAR-RV | 1,11 | 1,10 | 1,07 |
| CNN-LSTM | 1,07 | 1,05 | 1,02 |

### Par année (descriptif)

| Stratégie | Mesure | 2020 | 2021 | 2022 | 2023 | 2024 |
|---|---|---:|---:|---:|---:|---:|
| Achat simple | Rendement | 469,6 % | 399,2 % | −67,5 % | 90,8 % | 46,3 % |
| Achat simple | Volatilité | 98,5 % | 109,2 % | 86,7 % | 46,9 % | 64,8 % |
| Achat simple | Sharpe | 2,30 | 2,02 | −0,86 | 1,61 | 0,90 |
| Achat simple | Drawdown max | −62,2 % | −57,2 % | −74,0 % | −27,3 % | −45,3 % |
| HAR-RV | Rendement | 462,4 % | 187,9 % | −67,7 % | 88,2 % | 32,4 % |
| HAR-RV | Volatilité | 78,8 % | 76,3 % | 71,6 % | 46,5 % | 60,0 % |
| HAR-RV | Sharpe | 2,59 | 1,77 | −1,21 | 1,59 | 0,76 |
| HAR-RV | Drawdown max | −48,4 % | −47,4 % | −71,2 % | −27,2 % | −47,1 % |
| CNN-LSTM | Rendement | 357,8 % | 191,9 % | −67,8 % | 91,2 % | 28,1 % |
| CNN-LSTM | Volatilité | 72,4 % | 71,6 % | 70,1 % | 46,7 % | 59,5 % |
| CNN-LSTM | Sharpe | 2,47 | 1,85 | −1,26 | 1,62 | 0,71 |
| CNN-LSTM | Drawdown max | −48,0 % | −44,0 % | −71,0 % | −27,2 % | −48,6 % |

### Crises (descriptif)

| Stratégie | Covid : rendement / drawdown max | Terra-Luna : rendement / drawdown max | FTX : rendement / drawdown max |
|---|---:|---:|---:|
| Achat simple | −5,1 % / −56,0 % | −60,7 % / −66,2 % | −23,9 % / −33,0 % |
| HAR-RV | 7,9 % / −42,8 % | −52,0 % / −55,6 % | −21,8 % / −30,4 % |
| CNN-LSTM | 2,3 % / −42,9 % | −51,1 % / −54,7 % | −22,2 % / −30,3 % |

### VaR à 1 jour à 95 % et test de Kupiec

VaR = quantile de la loi normale (1,6449) × σ̂ journalière, sur le rendement de l'actif. Jours exclus (jour non valide ou lendemain : rendement nul ou sur deux jours) : 30.

| Modèle | Jours | Dépassements | Taux (attendu 5 %) | Statistique LR | p-valeur | Rejet à 5 % |
|---|---:|---:|---:|---:|---:|---|
| HAR-RV | 1 797 | 79 | 4,40 % | 1,44 | 0,2309 | non |
| GARCH(1,1) | 1 797 | 67 | 3,73 % | 6,68 | 0,0097 | oui |
| XGBoost | 1 797 | 88 | 4,90 % | 0,04 | 0,8408 | non |
| LSTM | 1 797 | 76 | 4,23 % | 2,37 | 0,1240 | non |
| GRU | 1 797 | 72 | 4,01 % | 3,99 | 0,0457 | oui |
| CNN-LSTM | 1 797 | 76 | 4,23 % | 2,37 | 0,1240 | non |
| Transformer | 1 797 | 84 | 4,67 % | 0,41 | 0,5222 | non |
| TFT | 1 797 | 81 | 4,51 % | 0,95 | 0,3303 | non |
| Persistance (descriptive) | 1 797 | 82 | 4,56 % | 0,74 | 0,3888 | non |

Figure : `figures/figure_6_strategie_ETHUSDT.png`.

## Lecture des résultats

Chaque phrase ci-dessous est générée à partir des valeurs de `rapports/strategie.json`.

- BTC : la stratégie pilotée par HAR-RV a une volatilité réalisée proche de sa cible (à 10 % près).
- BTC : la stratégie pilotée par Transformer a une volatilité réalisée sous sa cible (89 % de la cible) : l'exposition est plafonnée à 1 (pas d'emprunt) 46 % des jours, quand la volatilité prévue est sous la cible.
- BTC : la stratégie pilotée par HAR-RV réduit le drawdown maximal par rapport à l'achat simple (−74,9 % contre −76,6 %).
- BTC : la stratégie pilotée par Transformer réduit le drawdown maximal par rapport à l'achat simple (−74,2 % contre −76,6 %).
- BTC : le Sharpe de Transformer est inférieur ou égal à celui de HAR-RV, mais l'intervalle bootstrap de la différence contient 0 : on ne peut pas dire que l'une fait mieux que l'autre (descriptif).
- BTC : la stratégie pilotée par HAR-RV n'a pas un Sharpe plus élevé que l'achat simple.
- BTC : la stratégie pilotée par Transformer n'a pas un Sharpe plus élevé que l'achat simple.
- BTC : le classement par Sharpe ne garde pas en tête le modèle retenu par QLIKE (Transformer ; meilleur Sharpe : GARCH(1,1)) ; corrélation de rang de Spearman entre les deux classements des 8 modèles : −0,52 (les deux classements ne vont pas dans le même sens ; descriptif).
- BTC : le taux de dépassement de la VaR est sous 5 % pour 9 modèles sur 9 : la VaR est plutôt trop prudente que trop optimiste.
- BTC : le test de Kupiec rejette la VaR de GARCH(1,1), XGBoost, LSTM, GRU, CNN-LSTM, Transformer et TFT, chaque fois pour trop PEU de dépassements (VaR trop prudente).
- BTC : explication possible, non démontrée, des rejets pour trop peu de dépassements : la variance prévue vise la moyenne de RV², que les jours très agités tirent vers le haut (correction s² des modèles en log, facteur d'échelle du GARCH) ; et, au niveau de 95 %, une loi à queues épaisses dépasse moins souvent que la loi normale le quantile normal de même variance (ses dépassements sont plus rares, mais plus grands).
- BTC : l'ordre des Sharpe entre Transformer et HAR-RV ne change pas quand les frais vont de 0,05 % à 0,20 %.
- ETH : la stratégie pilotée par HAR-RV a une volatilité réalisée proche de sa cible (à 10 % près).
- ETH : la stratégie pilotée par CNN-LSTM a une volatilité réalisée sous sa cible (88 % de la cible) : l'exposition est plafonnée à 1 (pas d'emprunt) 49 % des jours, quand la volatilité prévue est sous la cible.
- ETH : la stratégie pilotée par HAR-RV réduit le drawdown maximal par rapport à l'achat simple (−77,9 % contre −79,3 %).
- ETH : la stratégie pilotée par CNN-LSTM réduit le drawdown maximal par rapport à l'achat simple (−77,9 % contre −79,3 %).
- ETH : le Sharpe de CNN-LSTM est inférieur ou égal à celui de HAR-RV, mais l'intervalle bootstrap de la différence contient 0 : on ne peut pas dire que l'une fait mieux que l'autre (descriptif).
- ETH : la stratégie pilotée par HAR-RV n'a pas un Sharpe plus élevé que l'achat simple.
- ETH : la stratégie pilotée par CNN-LSTM n'a pas un Sharpe plus élevé que l'achat simple.
- ETH : le classement par Sharpe ne garde pas en tête le modèle retenu par QLIKE (CNN-LSTM ; meilleur Sharpe : GARCH(1,1)) ; corrélation de rang de Spearman entre les deux classements des 8 modèles : −0,33 (les deux classements ne vont pas dans le même sens ; descriptif).
- ETH : le taux de dépassement de la VaR est sous 5 % pour 9 modèles sur 9 : la VaR est plutôt trop prudente que trop optimiste.
- ETH : le test de Kupiec rejette la VaR de GARCH(1,1) et GRU, chaque fois pour trop PEU de dépassements (VaR trop prudente).
- ETH : explication possible, non démontrée, des rejets pour trop peu de dépassements : la variance prévue vise la moyenne de RV², que les jours très agités tirent vers le haut (correction s² des modèles en log, facteur d'échelle du GARCH) ; et, au niveau de 95 %, une loi à queues épaisses dépasse moins souvent que la loi normale le quantile normal de même variance (ses dépassements sont plus rares, mais plus grands).
- ETH : l'ordre des Sharpe entre CNN-LSTM et HAR-RV ne change pas quand les frais vont de 0,05 % à 0,20 %.

