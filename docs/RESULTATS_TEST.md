# Résultats du test final

Fichier généré par `src/resultats_test.py` à partir de `rapports/test_final.json` : ne pas le modifier à la main.

- Test ouvert une seule fois le 2026-11-19 par `src/ouvrir_test.py --ouvrir`, avec le code du commit `f5259b6` ; 42 empreintes de modèles et de normalisations vérifiées avant toute prévision.
- Période du test (dates de cible) : du 2025-01-01 au 2026-10-31, 669 jours par actif. Aucune crise n'est définie sur cette période : rien n'est rapporté par crise.
- Modèles du découpage du test final, sans réentraînement ; attentes écrites et poussées avant l'ouverture : [`docs/ATTENTES_TEST.md`](ATTENTES_TEST.md). Tous les résultats sont publiés tels quels.

## Verdicts des hypothèses

| Hypothèse | Énoncé | BTC | ETH |
|---|---|---|---|
| H1 | QLIKE(modèle retenu) < QLIKE(HAR-RV) (principale) | confirmée | confirmée |
| H2 | QLIKE(HAR-RV) < QLIKE(persistance) | confirmée | confirmée |
| H3 | QLIKE(GARCH(1,1)) > QLIKE(HAR-RV) | confirmée | confirmée |
| H4 | VaR de HAR-RV non rejetée par Kupiec | confirmée | confirmée |
| H5 | stratégie du modèle retenu : volatilité et drawdown plus faibles que l'achat simple | confirmée | confirmée |
| H6 | gain du modèle retenu sur HAR-J < gain sur HAR-RV (descriptive) | confirmée | confirmée |
| H7 | QLIKE(modèle retenu) < QLIKE(HAR-J) (secondaire, ajoutée le 2026-11-19) | confirmée | confirmée |

| Test (Holm sur les 2 actifs) | Actif | Modèle retenu | Différence moyenne d | Statistique | p-valeur brute | p-valeur ajustée |
|---|---|---|---:|---:|---:|---:|
| H1 (contre HAR-RV) | BTC | Transformer | −0,0866 | −5,57 | < 0,0001 | < 0,0001 |
| H1 (contre HAR-RV) | ETH | CNN-LSTM | −0,0706 | −5,39 | < 0,0001 | < 0,0001 |
| H7 (contre HAR-J) | BTC | Transformer | −0,0228 | −1,98 | 0,0483 | 0,0483 |
| H7 (contre HAR-J) | ETH | CNN-LSTM | −0,0289 | −3,33 | 0,0009 | 0,0018 |

## Comparaison avec les prévisions chiffrées écrites avant l'ouverture

| Prévision | Intervalle prévu | BTC | ETH |
|---|---|---|---|
| Gain du modèle retenu sur HAR-RV | 0 % à 15 % | 32,2 % (au-dessus de l'intervalle prévu) | 28,3 % (au-dessus de l'intervalle prévu) |
| Gain du modèle retenu sur HAR-J | 0 % à 9 % | 11,1 % (au-dessus de l'intervalle prévu) | 13,9 % (au-dessus de l'intervalle prévu) |

Textes écrits avant l'ouverture : « gain attendu du modèle retenu sur HAR-RV entre 0 % et 15 % ; significativité incertaine (elle disparaissait sans 2024 sur le développement) » ; « gain attendu du modèle retenu sur HAR-J entre 0 % et 9 % ; probablement non significatif ».

## BTCUSDT

Modèle retenu : **Transformer**.

### Tous les modèles

| Modèle | QLIKE [IC 95 %] | Gain sur HAR-RV | Gain sur HAR-J | RMSE [IC 95 %] | MAE [IC 95 %] |
|---|---|---:|---:|---|---|
| Persistance (descriptive) | 0,369 [0,307 ; 0,442] | −37,3 % | −79,9 % | 0,0115 [0,0096 ; 0,0138] | 0,0079 [0,0070 ; 0,0091] |
| HAR-RV | 0,269 [0,217 ; 0,342] | 0,0 % | −31,1 % | 0,0086 [0,0073 ; 0,0101] | 0,0061 [0,0054 ; 0,0068] |
| HAR-J (descriptif) | 0,205 [0,154 ; 0,282] | 23,7 % | 0,0 % | 0,0074 [0,0060 ; 0,0090] | 0,0051 [0,0045 ; 0,0059] |
| GARCH(1,1) | 0,350 [0,300 ; 0,420] | −30,0 % | −70,5 % | 0,0101 [0,0089 ; 0,0115] | 0,0076 [0,0069 ; 0,0086] |
| XGBoost | 0,205 [0,156 ; 0,286] | 23,7 % | −0,0 % | 0,0075 [0,0061 ; 0,0091] | 0,0051 [0,0044 ; 0,0058] |
| LSTM | 0,181 [0,130 ; 0,273] | 32,5 % | 11,6 % | 0,0069 [0,0055 ; 0,0085] | 0,0047 [0,0042 ; 0,0054] |
| GRU | 0,183 [0,126 ; 0,281] | 32,1 % | 11,0 % | 0,0068 [0,0054 ; 0,0085] | 0,0046 [0,0041 ; 0,0052] |
| CNN-LSTM | 0,185 [0,130 ; 0,280] | 31,2 % | 9,9 % | 0,0069 [0,0055 ; 0,0086] | 0,0047 [0,0041 ; 0,0053] |
| Transformer (retenu) | 0,182 [0,128 ; 0,268] | 32,2 % | 11,1 % | 0,0069 [0,0055 ; 0,0086] | 0,0045 [0,0039 ; 0,0051] |
| TFT | 0,192 [0,137 ; 0,282] | 28,8 % | 6,6 % | 0,0071 [0,0057 ; 0,0087] | 0,0047 [0,0042 ; 0,0054] |

Modèles réglés : prévision = moyenne des log des 3 graines. QLIKE moyen de chaque graine seule (avec son propre s²) :

| Modèle | QLIKE moyen des graines (écart-type) |
|---|---|
| XGBoost | 0,206 (0,0013) |
| LSTM | 0,184 (0,0032) |
| GRU | 0,186 (0,0024) |
| CNN-LSTM | 0,189 (0,0060) |
| Transformer | 0,187 (0,0034) |
| TFT | 0,201 (0,0045) |

### Diebold-Mariano contre HAR-RV (QLIKE)

Le test principal est H1 (modèle retenu, Holm sur les 2 actifs, ci-dessus). Les 7 comparaisons ci-dessous sont descriptives (Holm sur 7).

| Modèle | Différence moyenne | Statistique (HLN) | p-valeur brute | p-valeur ajustée (Holm sur 7) |
|---|---:|---:|---:|---:|
| CNN-LSTM | −0,0840 | −5,18 | < 0,0001 | < 0,0001 |
| GARCH(1,1) | 0,0808 | 5,75 | < 0,0001 | < 0,0001 |
| GRU | −0,0863 | −5,44 | < 0,0001 | < 0,0001 |
| LSTM | −0,0875 | −6,13 | < 0,0001 | < 0,0001 |
| TFT | −0,0774 | −5,20 | < 0,0001 | < 0,0001 |
| Transformer | −0,0866 | −5,57 | < 0,0001 | < 0,0001 |
| XGBoost | −0,0638 | −7,07 | < 0,0001 | < 0,0001 |

| Comparaison descriptive | Différence moyenne | p-valeur brute |
|---|---:|---:|
| HAR-J contre HAR-RV | −0,0638 | < 0,0001 |
| HAR-RV contre persistance | −0,1002 | < 0,0001 |

### Stratégie de volatility targeting (frais de 0,10 %)

| Stratégie | Rendement annualisé | Volatilité (÷ cible) | Sharpe [IC 95 %] | Sortino | Drawdown max | Rotation annuelle | Frais par an |
|---|---:|---:|---|---:|---:|---:|---:|
| Achat simple | −9,8 % | 43,0 % (0,75) | −0,02 [−1,36 ; 1,28] | −0,04 | −53,0 % | 0,5 | 0,05 % |
| HAR-RV | −8,4 % | 40,0 % (0,70) | −0,02 [−1,48 ; 1,34] | −0,03 | −51,9 % | 7,7 | 0,77 % |
| Transformer | −9,5 % | 39,6 % (0,69) | −0,05 [−1,53 ; 1,32] | −0,08 | −52,4 % | 7,5 | 0,75 % |
| Persistance | −7,2 % | 37,8 % (0,66) | −0,01 [−1,47 ; 1,36] | −0,01 | −49,7 % | 19,5 | 1,95 % |
| GARCH(1,1) | −10,8 % | 41,2 % (0,72) | −0,07 [−1,50 ; 1,32] | −0,10 | −54,1 % | 2,0 | 0,20 % |
| XGBoost | −12,3 % | 39,4 % (0,69) | −0,14 [−1,60 ; 1,23] | −0,19 | −53,3 % | 7,2 | 0,72 % |
| LSTM | −8,8 % | 39,2 % (0,68) | −0,04 [−1,52 ; 1,33] | −0,06 | −51,5 % | 7,6 | 0,76 % |
| GRU | −9,0 % | 39,5 % (0,69) | −0,04 [−1,54 ; 1,32] | −0,06 | −52,3 % | 7,2 | 0,72 % |
| CNN-LSTM | −8,4 % | 39,4 % (0,69) | −0,03 [−1,50 ; 1,33] | −0,04 | −51,7 % | 7,0 | 0,70 % |
| TFT | −9,2 % | 40,0 % (0,70) | −0,04 [−1,52 ; 1,33] | −0,06 | −53,1 % | 6,6 | 0,66 % |

Différence de Sharpe Transformer − HAR-RV (descriptif) : −0,036 [−0,153 ; 0,073].

### VaR à 1 jour à 95 % et test de Kupiec

Jours exclus (jour non valide ou lendemain) : 0.

| Modèle | Jours | Dépassements | Taux (attendu 5 %) | p-valeur | Rejet à 5 % |
|---|---:|---:|---:|---:|---|
| Persistance | 669 | 27 | 4,04 % | 0,2371 | non |
| HAR-RV | 669 | 27 | 4,04 % | 0,2371 | non |
| GARCH(1,1) | 669 | 22 | 3,29 % | 0,0307 | oui |
| XGBoost | 669 | 31 | 4,63 % | 0,6601 | non |
| LSTM | 669 | 21 | 3,14 % | 0,0181 | oui |
| GRU | 669 | 25 | 3,74 % | 0,1173 | non |
| CNN-LSTM | 669 | 26 | 3,89 % | 0,1697 | non |
| Transformer | 669 | 28 | 4,19 % | 0,3204 | non |
| TFT | 669 | 27 | 4,04 % | 0,2371 | non |

Figures : `figures/figure_10_test_previsions_BTCUSDT.png`, `figures/figure_11_test_strategie_BTCUSDT.png`.

## ETHUSDT

Modèle retenu : **CNN-LSTM**.

### Tous les modèles

| Modèle | QLIKE [IC 95 %] | Gain sur HAR-RV | Gain sur HAR-J | RMSE [IC 95 %] | MAE [IC 95 %] |
|---|---|---:|---:|---|---|
| Persistance (descriptive) | 0,330 [0,268 ; 0,392] | −32,3 % | −58,9 % | 0,0154 [0,0132 ; 0,0179] | 0,0108 [0,0096 ; 0,0123] |
| HAR-RV | 0,250 [0,198 ; 0,305] | 0,0 % | −20,1 % | 0,0119 [0,0103 ; 0,0137] | 0,0084 [0,0075 ; 0,0095] |
| HAR-J (descriptif) | 0,208 [0,161 ; 0,259] | 16,7 % | 0,0 % | 0,0109 [0,0091 ; 0,0128] | 0,0075 [0,0067 ; 0,0085] |
| GARCH(1,1) | 0,298 [0,253 ; 0,347] | −19,2 % | −43,2 % | 0,0137 [0,0123 ; 0,0154] | 0,0104 [0,0094 ; 0,0117] |
| XGBoost | 0,205 [0,162 ; 0,257] | 17,8 % | 1,3 % | 0,0111 [0,0095 ; 0,0129] | 0,0078 [0,0070 ; 0,0088] |
| LSTM | 0,182 [0,143 ; 0,228] | 27,1 % | 12,5 % | 0,0102 [0,0088 ; 0,0118] | 0,0070 [0,0063 ; 0,0078] |
| GRU | 0,194 [0,149 ; 0,252] | 22,4 % | 6,8 % | 0,0103 [0,0088 ; 0,0121] | 0,0071 [0,0064 ; 0,0079] |
| CNN-LSTM (retenu) | 0,179 [0,140 ; 0,226] | 28,3 % | 13,9 % | 0,0102 [0,0087 ; 0,0120] | 0,0071 [0,0064 ; 0,0079] |
| Transformer | 0,182 [0,142 ; 0,224] | 27,2 % | 12,6 % | 0,0101 [0,0086 ; 0,0118] | 0,0070 [0,0063 ; 0,0078] |
| TFT | 0,183 [0,143 ; 0,231] | 26,6 % | 11,9 % | 0,0104 [0,0088 ; 0,0122] | 0,0071 [0,0063 ; 0,0079] |

Modèles réglés : prévision = moyenne des log des 3 graines. QLIKE moyen de chaque graine seule (avec son propre s²) :

| Modèle | QLIKE moyen des graines (écart-type) |
|---|---|
| XGBoost | 0,205 (0,0003) |
| LSTM | 0,184 (0,0027) |
| GRU | 0,198 (0,0145) |
| CNN-LSTM | 0,182 (0,0039) |
| Transformer | 0,187 (0,0048) |
| TFT | 0,188 (0,0053) |

### Diebold-Mariano contre HAR-RV (QLIKE)

Le test principal est H1 (modèle retenu, Holm sur les 2 actifs, ci-dessus). Les 7 comparaisons ci-dessous sont descriptives (Holm sur 7).

| Modèle | Différence moyenne | Statistique (HLN) | p-valeur brute | p-valeur ajustée (Holm sur 7) |
|---|---:|---:|---:|---:|
| CNN-LSTM | −0,0706 | −5,39 | < 0,0001 | < 0,0001 |
| GARCH(1,1) | 0,0480 | 3,10 | 0,0020 | 0,0020 |
| GRU | −0,0559 | −3,52 | 0,0005 | 0,0009 |
| LSTM | −0,0677 | −4,98 | < 0,0001 | < 0,0001 |
| TFT | −0,0664 | −5,40 | < 0,0001 | < 0,0001 |
| Transformer | −0,0679 | −5,39 | < 0,0001 | < 0,0001 |
| XGBoost | −0,0445 | −4,67 | < 0,0001 | < 0,0001 |

| Comparaison descriptive | Différence moyenne | p-valeur brute |
|---|---:|---:|
| HAR-J contre HAR-RV | −0,0417 | < 0,0001 |
| HAR-RV contre persistance | −0,0806 | < 0,0001 |

### Stratégie de volatility targeting (frais de 0,10 %)

| Stratégie | Rendement annualisé | Volatilité (÷ cible) | Sharpe [IC 95 %] | Sortino | Drawdown max | Rotation annuelle | Frais par an |
|---|---:|---:|---|---:|---:|---:|---:|
| Achat simple | −19,3 % | 68,7 % (0,93) | 0,03 [−1,46 ; 1,48] | 0,04 | −67,6 % | 0,5 | 0,05 % |
| HAR-RV | −11,8 % | 63,7 % (0,86) | 0,12 [−1,42 ; 1,63] | 0,18 | −65,1 % | 12,0 | 1,20 % |
| CNN-LSTM | −16,5 % | 62,5 % (0,85) | 0,02 [−1,54 ; 1,54] | 0,03 | −65,5 % | 14,9 | 1,49 % |
| Persistance | −8,6 % | 60,6 % (0,82) | 0,15 [−1,35 ; 1,59] | 0,23 | −61,7 % | 27,6 | 2,76 % |
| GARCH(1,1) | −16,8 % | 64,1 % (0,87) | 0,03 [−1,49 ; 1,55] | 0,04 | −65,8 % | 5,0 | 0,50 % |
| XGBoost | −16,2 % | 62,5 % (0,85) | 0,03 [−1,54 ; 1,55] | 0,04 | −65,7 % | 15,7 | 1,57 % |
| LSTM | −15,2 % | 62,7 % (0,85) | 0,05 [−1,52 ; 1,57] | 0,07 | −65,0 % | 14,3 | 1,43 % |
| GRU | −15,7 % | 62,6 % (0,85) | 0,04 [−1,52 ; 1,56] | 0,05 | −65,3 % | 13,8 | 1,38 % |
| Transformer | −16,7 % | 63,3 % (0,86) | 0,02 [−1,54 ; 1,54] | 0,04 | −66,3 % | 14,8 | 1,48 % |
| TFT | −16,5 % | 63,7 % (0,86) | 0,03 [−1,53 ; 1,57] | 0,05 | −66,7 % | 12,0 | 1,20 % |

Différence de Sharpe CNN-LSTM − HAR-RV (descriptif) : −0,097 [−0,171 ; −0,032].

### VaR à 1 jour à 95 % et test de Kupiec

Jours exclus (jour non valide ou lendemain) : 0.

| Modèle | Jours | Dépassements | Taux (attendu 5 %) | p-valeur | Rejet à 5 % |
|---|---:|---:|---:|---:|---|
| Persistance | 669 | 33 | 4,93 % | 0,9362 | non |
| HAR-RV | 669 | 30 | 4,48 % | 0,5337 | non |
| GARCH(1,1) | 669 | 25 | 3,74 % | 0,1173 | non |
| XGBoost | 669 | 32 | 4,78 % | 0,7956 | non |
| LSTM | 669 | 33 | 4,93 % | 0,9362 | non |
| GRU | 669 | 33 | 4,93 % | 0,9362 | non |
| CNN-LSTM | 669 | 31 | 4,63 % | 0,6601 | non |
| Transformer | 669 | 33 | 4,93 % | 0,9362 | non |
| TFT | 669 | 32 | 4,78 % | 0,7956 | non |

Figures : `figures/figure_10_test_previsions_ETHUSDT.png`, `figures/figure_11_test_strategie_ETHUSDT.png`.

## Lecture des résultats

Chaque phrase ci-dessous est générée à partir des valeurs de `rapports/test_final.json`.

- BTC : H1 est confirmée : Transformer a un QLIKE plus faible que HAR-RV sur le test, et l'écart est significatif après ajustement de Holm (p-valeur ajustée < 0,0001).
- BTC : le gain de Transformer sur HAR-RV est de 32,2 % sur le test, au-dessus de l'intervalle prévu (0 % à 15 %) ; il était de 13,7 % sur le développement (jours réunis) : la prévision écrite avant l'ouverture a sous-estimé le gain.
- BTC : H7 est confirmée de justesse : Transformer fait mieux que HAR-J (p-valeur ajustée 0,0483, seuil 0,05) ; son gain sur HAR-J est de 11,1 %, au-dessus de l'intervalle prévu (0 % à 9 %), alors que la prévision écrite avant l'ouverture le disait « probablement non significatif ».
- BTC : sur le test, le plus petit QLIKE est celui de LSTM (0,181), pas celui du modèle retenu (0,182) ; la sélection a été faite sur le développement et ne change pas.
- BTC : HAR-J fait mieux que HAR-RV sur le test (23,7 % ; p-valeur descriptive < 0,0001) ; H6 est confirmée : le gain de Transformer est de 11,1 % sur HAR-J contre 32,2 % sur HAR-RV.
- BTC : H2 est confirmée (HAR-RV contre la persistance) et H3 est confirmée (GARCH(1,1) contre HAR-RV).
- BTC : H5 est confirmée : la stratégie de Transformer a une volatilité de 39,6 % contre 43,0 % pour l'achat simple, et un drawdown maximal de −52,4 % contre −53,0 % (réduction de moins de 3 points).
- BTC : le rendement annualisé est négatif sur le test pour l'achat simple, la stratégie de HAR-RV et la stratégie de Transformer ; la stratégie réduit le risque mais ne transforme pas une baisse du marché en gain.
- BTC : l'intervalle bootstrap de la différence de Sharpe entre Transformer et HAR-RV contient 0 : on ne peut pas dire qu'une stratégie fait mieux que l'autre (descriptif).
- BTC : H4 est confirmée (taux de dépassement de HAR-RV 4,04 %, p-valeur 0,2371) ; Kupiec rejette la VaR de GARCH(1,1) et LSTM (trop peu de dépassements : VaR trop prudente).
- ETH : H1 est confirmée : CNN-LSTM a un QLIKE plus faible que HAR-RV sur le test, et l'écart est significatif après ajustement de Holm (p-valeur ajustée < 0,0001).
- ETH : le gain de CNN-LSTM sur HAR-RV est de 28,3 % sur le test, au-dessus de l'intervalle prévu (0 % à 15 %) ; il était de 15,5 % sur le développement (jours réunis) : la prévision écrite avant l'ouverture a sous-estimé le gain.
- ETH : H7 est confirmée : CNN-LSTM fait mieux que HAR-J (p-valeur ajustée 0,0018, seuil 0,05) ; son gain sur HAR-J est de 13,9 %, au-dessus de l'intervalle prévu (0 % à 9 %), alors que la prévision écrite avant l'ouverture le disait « probablement non significatif ».
- ETH : sur le test, le modèle retenu (CNN-LSTM) a aussi le plus petit QLIKE de tous les modèles.
- ETH : HAR-J fait mieux que HAR-RV sur le test (16,7 % ; p-valeur descriptive < 0,0001) ; H6 est confirmée : le gain de CNN-LSTM est de 13,9 % sur HAR-J contre 28,3 % sur HAR-RV.
- ETH : H2 est confirmée (HAR-RV contre la persistance) et H3 est confirmée (GARCH(1,1) contre HAR-RV).
- ETH : H5 est confirmée : la stratégie de CNN-LSTM a une volatilité de 62,5 % contre 68,7 % pour l'achat simple, et un drawdown maximal de −65,5 % contre −67,6 % (réduction de moins de 3 points).
- ETH : le rendement annualisé est négatif sur le test pour l'achat simple, la stratégie de HAR-RV et la stratégie de CNN-LSTM ; la stratégie réduit le risque mais ne transforme pas une baisse du marché en gain.
- ETH : le Sharpe de la stratégie de CNN-LSTM est plus bas que celui de la stratégie de HAR-RV, et l'intervalle bootstrap de la différence ne contient pas 0 (descriptif) : un QLIKE plus faible que HAR-RV ne se traduit pas ici par une meilleure stratégie.
- ETH : H4 est confirmée (taux de dépassement de HAR-RV 4,48 %, p-valeur 0,5337) ; Kupiec ne rejette la VaR d'aucun modèle.

