# Comparaison de tous les modèles (développement, 5 plis annuels)

Fichier généré par `src/comparer.py` à partir de `rapports/comparaison_modeles.json` : ne pas le modifier à la main.

- Plis évalués (dates de cible) : du 2020-01-01 au 2024-12-31. Le test final est fermé : aucune prévision n'y a été faite.
- QLIKE sur la variance (forme de Patton), RMSE et MAE sur RV ; intervalles à 95 % par bootstrap à blocs mobiles.
- Modèles réglés (XGBoost et réseaux) : prévision = moyenne des log de leurs 3 graines, avec s² mesuré sur la validation interne pour cette moyenne (petit ensemble : léger avantage écrit dans les règles).
- La persistance est une référence descriptive : hors de la sélection et des tests principaux.
- Gain sur HAR-RV : (QLIKE de HAR-RV − QLIKE du modèle) / QLIKE de HAR-RV ; positif quand le modèle fait mieux.

## BTCUSDT

### Tableau de comparaison (plis réunis)

| Modèle | QLIKE [IC 95 %] | QLIKE moyen par pli | Gain sur HAR-RV (moyenne par pli) | RMSE [IC 95 %] | MAE [IC 95 %] |
|---|---|---:|---:|---|---|
| Persistance (descriptive) | 0,413 [0,339 ; 0,518] | 0,413 | — | 0,0197 [0,0157 ; 0,0244] | 0,0117 [0,0106 ; 0,0131] |
| HAR-RV | 0,344 [0,273 ; 0,442] | 0,344 | 0,0 % | 0,0152 [0,0119 ; 0,0194] | 0,0090 [0,0082 ; 0,0101] |
| GARCH(1,1) | 0,432 [0,356 ; 0,526] | 0,433 | −25,8 % | 0,0176 [0,0141 ; 0,0215] | 0,0114 [0,0101 ; 0,0129] |
| XGBoost | 0,321 [0,263 ; 0,396] | 0,321 | 6,7 % | 0,0151 [0,0119 ; 0,0195] | 0,0092 [0,0084 ; 0,0101] |
| LSTM | 0,305 [0,240 ; 0,394] | 0,306 | 11,2 % | 0,0149 [0,0116 ; 0,0193] | 0,0091 [0,0082 ; 0,0101] |
| GRU | 0,304 [0,239 ; 0,399] | 0,304 | 11,6 % | 0,0150 [0,0116 ; 0,0197] | 0,0091 [0,0083 ; 0,0102] |
| CNN-LSTM | 0,304 [0,238 ; 0,403] | 0,305 | 11,5 % | 0,0145 [0,0115 ; 0,0184] | 0,0089 [0,0081 ; 0,0100] |
| Transformer | 0,297 [0,236 ; 0,381] | 0,297 | 13,6 % | 0,0151 [0,0115 ; 0,0197] | 0,0090 [0,0081 ; 0,0101] |
| TFT | 0,322 [0,249 ; 0,437] | 0,323 | 6,3 % | 0,0155 [0,0117 ; 0,0206] | 0,0092 [0,0083 ; 0,0105] |

### Modèles réglés : métriques de chaque graine (chacune avec son propre s²)

| Modèle | QLIKE moyen des graines (écart-type) | QLIKE de la moyenne des graines | RMSE moyen (écart-type) | MAE moyen (écart-type) |
|---|---|---:|---|---|
| XGBoost | 0,322 (0,0022) | 0,321 | 0,0152 (0,0001) | 0,0092 (0,0000) |
| LSTM | 0,312 (0,0048) | 0,305 | 0,0151 (0,0002) | 0,0093 (0,0001) |
| GRU | 0,308 (0,0013) | 0,304 | 0,0152 (0,0000) | 0,0092 (0,0001) |
| CNN-LSTM | 0,310 (0,0017) | 0,304 | 0,0147 (0,0001) | 0,0091 (0,0001) |
| Transformer | 0,300 (0,0041) | 0,297 | 0,0152 (0,0002) | 0,0091 (0,0003) |
| TFT | 0,340 (0,0173) | 0,322 | 0,0160 (0,0004) | 0,0096 (0,0005) |

### Robustesse (descriptif) : gain sur HAR-RV de chaque graine seule

Sans effet sur le classement ni la sélection. Gain en moyenne des QLIKE moyens par pli ; chaque graine avec son propre s². Effet d'ensemble = gain de la moyenne des 3 graines − moyenne des gains des graines seules (en points de pourcentage).

| Modèle | Graine 0 | Graine 1 | Graine 2 | Moyenne des graines seules | Moyenne des 3 graines (prévision retenue) | Effet d'ensemble |
|---|---:|---:|---:|---:|---:|---:|
| XGBoost | 6,6 % | 6,8 % | 5,6 % | 6,4 % | 6,7 % | 0,4 |
| LSTM | 9,4 % | 7,7 % | 10,5 % | 9,2 % | 11,2 % | 2,0 |
| GRU | 10,6 % | 10,5 % | 9,9 % | 10,3 % | 11,6 % | 1,2 |
| CNN-LSTM | 10,1 % | 9,9 % | 9,2 % | 9,7 % | 11,5 % | 1,8 |
| Transformer | 12,4 % | 11,5 % | 13,9 % | 12,6 % | 13,6 % | 1,1 |
| TFT | 4,5 % | 3,3 % | −4,8 % | 1,0 % | 6,3 % | 5,3 |

### Robustesse (descriptif) : gain sur HAR-RV pli par pli

| Modèle | pli 1 (2020) | pli 2 (2021) | pli 3 (2022) | pli 4 (2023) | pli 5 (2024) |
|---|---:|---:|---:|---:|---:|
| GARCH(1,1) | −39,9 % | −43,1 % | −40,1 % | −1,1 % | −18,3 % |
| XGBoost | −5,7 % | 10,0 % | −8,8 % | 15,3 % | 18,2 % |
| LSTM | −0,9 % | 14,3 % | 11,6 % | 6,5 % | 30,2 % |
| GRU | −6,9 % | 15,4 % | 9,8 % | 12,0 % | 30,7 % |
| CNN-LSTM | 3,1 % | 16,0 % | 13,1 % | 0,4 % | 34,4 % |
| Transformer | −10,0 % | 17,4 % | 8,8 % | 18,0 % | 35,3 % |
| TFT | −30,3 % | 13,7 % | −5,8 % | 19,8 % | 30,4 % |

### Diebold-Mariano contre HAR-RV (plis réunis, QLIKE)

Famille de Holm : les 7 comparaisons ci-dessous (test descriptif exclu). « Significatif » s'appuie sur la p-valeur ajustée.

| Modèle | Différence moyenne | Statistique (HLN) | p-valeur brute | p-valeur ajustée (Holm) | Sens | Significatif à 5 % (ajustée) |
|---|---:|---:|---:|---:|---|---|
| GARCH(1,1) | 0,0884 | 3,41 | 0,0007 | 0,0039 | référence meilleure | oui |
| XGBoost | −0,0232 | −1,15 | 0,2497 | 0,4994 | modèle meilleur | non |
| LSTM | −0,0386 | −3,29 | 0,0010 | 0,0050 | modèle meilleur | oui |
| GRU | −0,0400 | −3,95 | < 0,0001 | 0,0006 | modèle meilleur | oui |
| CNN-LSTM | −0,0396 | −2,59 | 0,0097 | 0,0291 | modèle meilleur | oui |
| Transformer | −0,0472 | −3,30 | 0,0010 | 0,0050 | modèle meilleur | oui |
| TFT | −0,0219 | −0,97 | 0,3335 | 0,4994 | modèle meilleur | non |

Test descriptif HAR-RV contre persistance (hors famille) : différence −0,0687, p-valeur < 0,0001, modèle meilleur (le « modèle » est HAR-RV). Jours : 1 812 ; retards HAC : 7.

### QLIKE par pli

| Modèle | pli 1 | pli 2 | pli 3 | pli 4 | pli 5 |
|---|---:|---:|---:|---:|---:|
| Persistance | 0,344 | 0,376 | 0,329 | 0,637 | 0,377 |
| HAR-RV | 0,345 | 0,322 | 0,276 | 0,495 | 0,283 |
| GARCH(1,1) | 0,482 | 0,460 | 0,386 | 0,501 | 0,335 |
| XGBoost | 0,364 | 0,289 | 0,300 | 0,419 | 0,232 |
| LSTM | 0,348 | 0,276 | 0,244 | 0,463 | 0,197 |
| GRU | 0,368 | 0,272 | 0,249 | 0,436 | 0,196 |
| CNN-LSTM | 0,334 | 0,270 | 0,240 | 0,493 | 0,186 |
| Transformer | 0,379 | 0,265 | 0,251 | 0,406 | 0,183 |
| TFT | 0,449 | 0,277 | 0,292 | 0,397 | 0,197 |

### Crises (QLIKE, descriptif, sans test)

| Modèle | covid | terra_luna | ftx |
|---|---:|---:|---:|
| Persistance | 0,700 | 0,275 | 0,572 |
| HAR-RV | 0,858 | 0,289 | 0,533 |
| GARCH(1,1) | 1,207 | 0,379 | 0,961 |
| XGBoost | 0,902 | 0,352 | 0,633 |
| LSTM | 0,738 | 0,235 | 0,529 |
| GRU | 0,913 | 0,207 | 0,547 |
| CNN-LSTM | 0,595 | 0,217 | 0,483 |
| Transformer | 0,997 | 0,238 | 0,555 |
| TFT | 1,363 | 0,281 | 0,621 |

### Classement (persistance exclue)

| Définition | Classement |
|---|---|
| QLIKE moyen sur tous les jours évalués réunis | Transformer < GRU < CNN-LSTM < LSTM < XGBoost < TFT < HAR-RV < GARCH(1,1) |
| Moyenne des QLIKE moyens par pli (définition appliquée) | Transformer < GRU < CNN-LSTM < LSTM < XGBoost < TFT < HAR-RV < GARCH(1,1) |

Les deux définitions donnent le même classement.
**Modèle retenu par la règle de sélection : Transformer.** Meilleur réseau : Transformer.

### Vérification de l'exception 2 : moyenne des résidus en log sur la validation interne

| Modèle | pli 1 | pli 2 | pli 3 | pli 4 | pli 5 | test final |
|---|---:|---:|---:|---:|---:|---:|
| XGBoost | −0,020 | −0,073 | 0,041 | −0,119 | −0,130 | −0,005 |
| LSTM | −0,063 | −0,044 | −0,037 | −0,137 | −0,078 | −0,010 |
| GRU | −0,027 | −0,069 | −0,021 | −0,118 | −0,056 | 0,001 |
| CNN-LSTM | −0,030 | −0,002 | −0,019 | −0,089 | −0,056 | 0,003 |
| Transformer | −0,001 | −0,077 | −0,019 | −0,102 | −0,051 | 0,007 |
| TFT | −0,021 | −0,007 | −0,051 | −0,120 | −0,055 | 0,017 |

Une moyenne négative signifie que le modèle prévoit trop haut sur la validation interne.

Figure : `figures/figure_5_deep_learning_BTCUSDT.png`.

## ETHUSDT

### Tableau de comparaison (plis réunis)

| Modèle | QLIKE [IC 95 %] | QLIKE moyen par pli | Gain sur HAR-RV (moyenne par pli) | RMSE [IC 95 %] | MAE [IC 95 %] |
|---|---|---:|---:|---|---|
| Persistance (descriptive) | 0,349 [0,276 ; 0,451] | 0,349 | — | 0,0229 [0,0177 ; 0,0292] | 0,0131 [0,0117 ; 0,0150] |
| HAR-RV | 0,293 [0,229 ; 0,379] | 0,293 | 0,0 % | 0,0181 [0,0140 ; 0,0230] | 0,0106 [0,0096 ; 0,0119] |
| GARCH(1,1) | 0,413 [0,341 ; 0,505] | 0,413 | −41,1 % | 0,0213 [0,0174 ; 0,0264] | 0,0145 [0,0132 ; 0,0162] |
| XGBoost | 0,292 [0,240 ; 0,358] | 0,293 | 0,0 % | 0,0190 [0,0146 ; 0,0243] | 0,0112 [0,0101 ; 0,0126] |
| LSTM | 0,262 [0,203 ; 0,341] | 0,262 | 10,5 % | 0,0180 [0,0135 ; 0,0233] | 0,0103 [0,0093 ; 0,0117] |
| GRU | 0,255 [0,206 ; 0,323] | 0,255 | 12,9 % | 0,0179 [0,0138 ; 0,0230] | 0,0107 [0,0097 ; 0,0120] |
| CNN-LSTM | 0,247 [0,195 ; 0,320] | 0,247 | 15,4 % | 0,0173 [0,0134 ; 0,0224] | 0,0104 [0,0093 ; 0,0118] |
| Transformer | 0,260 [0,207 ; 0,327] | 0,261 | 11,0 % | 0,0182 [0,0137 ; 0,0236] | 0,0103 [0,0092 ; 0,0117] |
| TFT | 0,259 [0,206 ; 0,327] | 0,260 | 11,3 % | 0,0183 [0,0138 ; 0,0236] | 0,0104 [0,0093 ; 0,0118] |

### Modèles réglés : métriques de chaque graine (chacune avec son propre s²)

| Modèle | QLIKE moyen des graines (écart-type) | QLIKE de la moyenne des graines | RMSE moyen (écart-type) | MAE moyen (écart-type) |
|---|---|---:|---|---|
| XGBoost | 0,293 (0,0008) | 0,292 | 0,0190 (0,0000) | 0,0112 (0,0000) |
| LSTM | 0,265 (0,0098) | 0,262 | 0,0181 (0,0003) | 0,0104 (0,0002) |
| GRU | 0,257 (0,0051) | 0,255 | 0,0180 (0,0000) | 0,0108 (0,0001) |
| CNN-LSTM | 0,252 (0,0045) | 0,247 | 0,0176 (0,0002) | 0,0105 (0,0003) |
| Transformer | 0,267 (0,0118) | 0,260 | 0,0184 (0,0003) | 0,0105 (0,0002) |
| TFT | 0,268 (0,0121) | 0,259 | 0,0186 (0,0005) | 0,0107 (0,0006) |

### Robustesse (descriptif) : gain sur HAR-RV de chaque graine seule

Sans effet sur le classement ni la sélection. Gain en moyenne des QLIKE moyens par pli ; chaque graine avec son propre s². Effet d'ensemble = gain de la moyenne des 3 graines − moyenne des gains des graines seules (en points de pourcentage).

| Modèle | Graine 0 | Graine 1 | Graine 2 | Moyenne des graines seules | Moyenne des 3 graines (prévision retenue) | Effet d'ensemble |
|---|---:|---:|---:|---:|---:|---:|
| XGBoost | −0,1 % | 0,2 % | −0,3 % | −0,1 % | 0,0 % | 0,1 |
| LSTM | 12,9 % | 8,7 % | 6,2 % | 9,3 % | 10,5 % | 1,2 |
| GRU | 13,8 % | 12,1 % | 10,3 % | 12,1 % | 12,9 % | 0,8 |
| CNN-LSTM | 13,4 % | 12,5 % | 15,5 % | 13,8 % | 15,4 % | 1,6 |
| Transformer | 8,7 % | 4,5 % | 12,6 % | 8,6 % | 11,0 % | 2,3 |
| TFT | 12,2 % | 8,3 % | 4,0 % | 8,2 % | 11,3 % | 3,1 |

### Robustesse (descriptif) : gain sur HAR-RV pli par pli

| Modèle | pli 1 (2020) | pli 2 (2021) | pli 3 (2022) | pli 4 (2023) | pli 5 (2024) |
|---|---:|---:|---:|---:|---:|
| GARCH(1,1) | −12,1 % | −36,3 % | −43,3 % | −71,7 % | −28,1 % |
| XGBoost | −16,4 % | −1,2 % | −12,6 % | 8,2 % | 15,9 % |
| LSTM | −11,9 % | 3,5 % | 10,4 % | 17,4 % | 30,7 % |
| GRU | −10,5 % | 13,0 % | 11,4 % | 17,4 % | 30,1 % |
| CNN-LSTM | −5,5 % | 13,0 % | 16,6 % | 18,1 % | 34,0 % |
| Transformer | −17,8 % | −0,1 % | 11,0 % | 23,6 % | 34,0 % |
| TFT | −19,0 % | 7,0 % | 7,6 % | 23,9 % | 30,6 % |

### Diebold-Mariano contre HAR-RV (plis réunis, QLIKE)

Famille de Holm : les 7 comparaisons ci-dessous (test descriptif exclu). « Significatif » s'appuie sur la p-valeur ajustée.

| Modèle | Différence moyenne | Statistique (HLN) | p-valeur brute | p-valeur ajustée (Holm) | Sens | Significatif à 5 % (ajustée) |
|---|---:|---:|---:|---:|---|---|
| GARCH(1,1) | 0,1205 | 4,11 | < 0,0001 | 0,0003 | référence meilleure | oui |
| XGBoost | −0,0003 | −0,01 | 0,9903 | 0,9903 | modèle meilleur | non |
| LSTM | −0,0309 | −2,67 | 0,0076 | 0,0306 | modèle meilleur | oui |
| GRU | −0,0380 | −3,22 | 0,0013 | 0,0064 | modèle meilleur | oui |
| CNN-LSTM | −0,0454 | −3,97 | < 0,0001 | 0,0004 | modèle meilleur | oui |
| Transformer | −0,0325 | −1,98 | 0,0476 | 0,1420 | modèle meilleur | non |
| TFT | −0,0334 | −1,98 | 0,0473 | 0,1420 | modèle meilleur | non |

Test descriptif HAR-RV contre persistance (hors famille) : différence −0,0567, p-valeur < 0,0001, modèle meilleur (le « modèle » est HAR-RV). Jours : 1 812 ; retards HAC : 7.

### QLIKE par pli

| Modèle | pli 1 | pli 2 | pli 3 | pli 4 | pli 5 |
|---|---:|---:|---:|---:|---:|
| Persistance | 0,284 | 0,384 | 0,259 | 0,491 | 0,327 |
| HAR-RV | 0,256 | 0,332 | 0,220 | 0,391 | 0,264 |
| GARCH(1,1) | 0,287 | 0,452 | 0,315 | 0,672 | 0,338 |
| XGBoost | 0,298 | 0,336 | 0,247 | 0,359 | 0,222 |
| LSTM | 0,287 | 0,320 | 0,197 | 0,323 | 0,183 |
| GRU | 0,283 | 0,289 | 0,195 | 0,323 | 0,184 |
| CNN-LSTM | 0,270 | 0,289 | 0,183 | 0,321 | 0,174 |
| Transformer | 0,302 | 0,332 | 0,196 | 0,299 | 0,174 |
| TFT | 0,305 | 0,309 | 0,203 | 0,298 | 0,183 |

### Crises (QLIKE, descriptif, sans test)

| Modèle | covid | terra_luna | ftx |
|---|---:|---:|---:|
| Persistance | 0,416 | 0,214 | 0,522 |
| HAR-RV | 0,476 | 0,247 | 0,416 |
| GARCH(1,1) | 0,502 | 0,357 | 0,701 |
| XGBoost | 0,520 | 0,322 | 0,480 |
| LSTM | 0,535 | 0,221 | 0,378 |
| GRU | 0,507 | 0,205 | 0,380 |
| CNN-LSTM | 0,380 | 0,182 | 0,356 |
| Transformer | 0,549 | 0,206 | 0,387 |
| TFT | 0,607 | 0,244 | 0,375 |

### Classement (persistance exclue)

| Définition | Classement |
|---|---|
| QLIKE moyen sur tous les jours évalués réunis | CNN-LSTM < GRU < TFT < Transformer < LSTM < XGBoost < HAR-RV < GARCH(1,1) |
| Moyenne des QLIKE moyens par pli (définition appliquée) | CNN-LSTM < GRU < TFT < Transformer < LSTM < XGBoost < HAR-RV < GARCH(1,1) |

Les deux définitions donnent le même classement.
**Modèle retenu par la règle de sélection : CNN-LSTM.** Meilleur réseau : CNN-LSTM.

### Vérification de l'exception 2 : moyenne des résidus en log sur la validation interne

| Modèle | pli 1 | pli 2 | pli 3 | pli 4 | pli 5 | test final |
|---|---:|---:|---:|---:|---:|---:|
| XGBoost | 0,008 | −0,015 | −0,002 | −0,073 | −0,139 | −0,006 |
| LSTM | −0,017 | −0,046 | −0,034 | −0,031 | −0,052 | −0,004 |
| GRU | −0,017 | −0,036 | −0,038 | −0,043 | −0,032 | 0,004 |
| CNN-LSTM | −0,007 | −0,029 | −0,014 | −0,030 | −0,038 | −0,016 |
| Transformer | 0,008 | −0,009 | −0,005 | −0,041 | −0,050 | 0,001 |
| TFT | −0,001 | 0,003 | 0,003 | −0,003 | −0,082 | 0,015 |

Une moyenne négative signifie que le modèle prévoit trop haut sur la validation interne.

Figure : `figures/figure_5_deep_learning_ETHUSDT.png`.

## Temps de la phase « plis »

Temps de calcul cumulé : 2,91 h, contre 14,36 h estimées (rapport 0,202 ; seuil d'arrêt de la règle de suivi : 1,5).

| Modèle | Réel (min) | Estimé (min) | Époques | Par époque réel / estimé (s) |
|---|---:|---:|---:|---|
| CNN-LSTM | 9,3 | 57,4 | 1 306 | 0,43 / 0,96 |
| GRU | 6,2 | 132,3 | 1 559 | 0,24 / 2,21 |
| LSTM | 3,5 | 43,8 | 1 658 | 0,13 / 0,73 |
| TFT | 123,2 | 489,9 | 1 732 | 4,27 / 8,16 |
| Transformer | 32,2 | 138,1 | 2 434 | 0,79 / 2,30 |

Empreintes des poids : `rapports/modeles_deep_learning.json` (les poids eux-mêmes ne sont pas dans le dépôt).

## Lecture des résultats

Chaque phrase ci-dessous est générée à partir des valeurs de `rapports/comparaison_modeles.json`.

- BTC : la règle de sélection retient Transformer (un réseau).
- BTC : LSTM, GRU, CNN-LSTM et Transformer font significativement mieux que HAR-RV en QLIKE, après ajustement de Holm.
- BTC : pour TFT, l'écart avec HAR-RV n'est pas significatif après ajustement de Holm : on ne peut pas dire que ce réseau fait mieux ou moins bien que HAR-RV.
- BTC : le meilleur réseau, Transformer, a un QLIKE moyen par pli plus faible que HAR-RV et plus faible qu'XGBoost.
- BTC : pour LSTM, GRU, CNN-LSTM, Transformer et TFT, la moyenne des 3 graines a un QLIKE plus faible que la moyenne des QLIKE des graines : c'est l'effet de petit ensemble annoncé dans les règles, qui avantage les modèles réglés par rapport à HAR-RV et GARCH.
- BTC : pour LSTM, GRU, CNN-LSTM et Transformer, chaque graine seule bat déjà HAR-RV : le gain ne vient pas seulement de la moyenne des graines (robustesse, descriptif).
- BTC : pour TFT, au moins une graine seule ne bat pas HAR-RV : une partie du gain vient de la moyenne des graines (robustesse, descriptif).
- BTC : l'effet d'ensemble le plus grand est celui de TFT (5,3 points de gain sur HAR-RV).
- BTC : le gain de CNN-LSTM sur HAR-RV est régulier : positif chaque année de 2020 à 2024 (robustesse, descriptif).
- BTC : le gain de LSTM, GRU et Transformer sur HAR-RV n'est pas régulier (concentré sur certaines années) : positif en 2021, 2022, 2023 et 2024, négatif ou nul en 2020 (robustesse, descriptif).
- BTC : le gain de TFT sur HAR-RV n'est pas régulier (concentré sur certaines années) : positif en 2021, 2023 et 2024, négatif ou nul en 2020 et 2022 (robustesse, descriptif).
- BTC : pendant le Covid, le plus petit QLIKE (descriptif, sans test) est celui de CNN-LSTM.
- BTC : pendant Terra-Luna, le plus petit QLIKE (descriptif, sans test) est celui de GRU.
- BTC : pendant FTX, le plus petit QLIKE (descriptif, sans test) est celui de CNN-LSTM.
- BTC : LSTM, GRU, Transformer et TFT ont au moins une validation interne où la moyenne des résidus en log dépasse 0,1 en valeur absolue : la correction s² y est mesurée sur une prévision décalée (même constat que pour XGBoost, voir la rectification de l'exception 2).
- ETH : la règle de sélection retient CNN-LSTM (un réseau).
- ETH : LSTM, GRU et CNN-LSTM font significativement mieux que HAR-RV en QLIKE, après ajustement de Holm.
- ETH : pour Transformer et TFT, l'écart avec HAR-RV n'est pas significatif après ajustement de Holm : on ne peut pas dire que ces réseaux font mieux ou moins bien que HAR-RV.
- ETH : Transformer et TFT seraient significatifs avec la p-valeur brute, mais plus après ajustement : c'est exactement le risque des tests multiples.
- ETH : le meilleur réseau, CNN-LSTM, a un QLIKE moyen par pli plus faible que HAR-RV et plus faible qu'XGBoost.
- ETH : pour LSTM, GRU, CNN-LSTM, Transformer et TFT, la moyenne des 3 graines a un QLIKE plus faible que la moyenne des QLIKE des graines : c'est l'effet de petit ensemble annoncé dans les règles, qui avantage les modèles réglés par rapport à HAR-RV et GARCH.
- ETH : pour LSTM, GRU, CNN-LSTM, Transformer et TFT, chaque graine seule bat déjà HAR-RV : le gain ne vient pas seulement de la moyenne des graines (robustesse, descriptif).
- ETH : l'effet d'ensemble le plus grand est celui de TFT (3,1 points de gain sur HAR-RV).
- ETH : le gain de LSTM, GRU, CNN-LSTM et TFT sur HAR-RV n'est pas régulier (concentré sur certaines années) : positif en 2021, 2022, 2023 et 2024, négatif ou nul en 2020 (robustesse, descriptif).
- ETH : le gain de Transformer sur HAR-RV n'est pas régulier (concentré sur certaines années) : positif en 2022, 2023 et 2024, négatif ou nul en 2020 et 2021 (robustesse, descriptif).
- ETH : pour les 5 réseaux, le plus grand gain annuel sur HAR-RV est en 2024 et le plus petit en 2020 (robustesse, descriptif). XGBoost a aussi son plus grand gain en 2024. Explication possible, non démontrée : HAR-RV est moins bon cette année-là, et l'écart ne tient pas seulement aux réseaux.
- ETH : pendant le Covid, le plus petit QLIKE (descriptif, sans test) est celui de CNN-LSTM.
- ETH : pendant Terra-Luna, le plus petit QLIKE (descriptif, sans test) est celui de CNN-LSTM.
- ETH : pendant FTX, le plus petit QLIKE (descriptif, sans test) est celui de CNN-LSTM.

