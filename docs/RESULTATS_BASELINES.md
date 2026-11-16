# Résultats des baselines (développement, 5 plis annuels)

Fichier généré par `src/baselines.py` à partir de `rapports/baselines.json` : ne pas le modifier à la main.

- Plis évalués (dates de cible) : du 2020-01-01 au 2024-12-31. Le test final est fermé : aucune prévision n'y a été faite.
- QLIKE sur la variance (forme de Patton), RMSE et MAE sur RV ; intervalles à 95 % par bootstrap à blocs mobiles.
- La persistance est une référence descriptive : hors de la sélection et des tests principaux.
- XGBoost : prévision = moyenne des log de ses 3 graines (petit ensemble : léger avantage écrit dans les règles).

## BTCUSDT

### Plis réunis

| Modèle | QLIKE [IC 95 %] | RMSE [IC 95 %] | MAE [IC 95 %] |
|---|---|---|---|
| Persistance (descriptive) | 0,413 [0,339 ; 0,518] | 0,0197 [0,0157 ; 0,0244] | 0,0117 [0,0106 ; 0,0131] |
| HAR-RV | 0,344 [0,273 ; 0,442] | 0,0152 [0,0119 ; 0,0194] | 0,0090 [0,0082 ; 0,0101] |
| GARCH(1,1) | 0,432 [0,356 ; 0,526] | 0,0176 [0,0141 ; 0,0215] | 0,0114 [0,0101 ; 0,0129] |
| XGBoost | 0,321 [0,263 ; 0,396] | 0,0151 [0,0119 ; 0,0195] | 0,0092 [0,0084 ; 0,0101] |

XGBoost par graine (chacune avec son propre s²) : QLIKE moyen 0,322 (écart-type 0,0022), RMSE 0,0152, MAE 0,0092.

### Diebold-Mariano contre HAR-RV (plis réunis, QLIKE)

| Modèle | Différence moyenne | Statistique (HLN) | p-valeur | Jours | Retards HAC | Sens | Significatif à 5 % |
|---|---:|---:|---:|---:|---:|---|---|
| GARCH(1,1) | 0,0884 | 3,41 | 0,0007 | 1 812 | 7 | référence meilleure | oui |
| XGBoost | −0,0232 | −1,15 | 0,2497 | 1 812 | 7 | modèle meilleur | non |
| HAR-RV contre persistance (descriptif) | −0,0687 | −4,49 | < 0,0001 | 1 812 | 7 | modèle meilleur | oui |

Pour le test descriptif, le « modèle » est HAR-RV et la « référence » est la persistance.

### QLIKE par pli

| Modèle | pli 1 | pli 2 | pli 3 | pli 4 | pli 5 |
|---|---:|---:|---:|---:|---:|
| Persistance | 0,344 | 0,376 | 0,329 | 0,637 | 0,377 |
| HAR-RV | 0,345 | 0,322 | 0,276 | 0,495 | 0,283 |
| GARCH(1,1) | 0,482 | 0,460 | 0,386 | 0,501 | 0,335 |
| XGBoost | 0,364 | 0,289 | 0,300 | 0,419 | 0,232 |

### Crises (descriptif, sans test)

| Modèle | covid | terra_luna | ftx |
|---|---:|---:|---:|
| Persistance (QLIKE) | 0,700 | 0,275 | 0,572 |
| HAR-RV (QLIKE) | 0,858 | 0,289 | 0,533 |
| GARCH(1,1) (QLIKE) | 1,207 | 0,379 | 0,961 |
| XGBoost (QLIKE) | 0,902 | 0,352 | 0,633 |

### Classement provisoire (persistance exclue)

| Définition | Classement |
|---|---|
| QLIKE moyen sur tous les jours évalués réunis | XGBoost < HAR-RV < GARCH(1,1) |
| Moyenne des QLIKE moyens par pli (définition littérale de la règle) | XGBoost < HAR-RV < GARCH(1,1) |

Les deux définitions donnent le même classement.
Précision décidée après avoir vu les résultats des baselines (voir `docs/CHOIX.md`). Le classement définitif viendra après le deep learning.

### Vérification de l'exception 2 : moyenne des résidus en log d'XGBoost sur la validation interne

| Découpage | Moyenne des résidus (cible − prévision) | s² |
|---|---:|---:|
| pli 1 | −0,020 | 0,126 |
| pli 2 | −0,073 | 0,089 |
| pli 3 | 0,041 | 0,081 |
| pli 4 | −0,119 | 0,131 |
| pli 5 | −0,130 | 0,170 |
| test final | −0,005 | 0,080 |

Une moyenne négative signifie que XGBoost prévoit trop haut sur la validation interne.

Figure : `figures/figure_4_previsions_BTCUSDT.png`.

## ETHUSDT

### Plis réunis

| Modèle | QLIKE [IC 95 %] | RMSE [IC 95 %] | MAE [IC 95 %] |
|---|---|---|---|
| Persistance (descriptive) | 0,349 [0,276 ; 0,451] | 0,0229 [0,0177 ; 0,0292] | 0,0131 [0,0117 ; 0,0150] |
| HAR-RV | 0,293 [0,229 ; 0,379] | 0,0181 [0,0140 ; 0,0230] | 0,0106 [0,0096 ; 0,0119] |
| GARCH(1,1) | 0,413 [0,341 ; 0,505] | 0,0213 [0,0174 ; 0,0264] | 0,0145 [0,0132 ; 0,0162] |
| XGBoost | 0,292 [0,240 ; 0,358] | 0,0190 [0,0146 ; 0,0243] | 0,0112 [0,0101 ; 0,0126] |

XGBoost par graine (chacune avec son propre s²) : QLIKE moyen 0,293 (écart-type 0,0008), RMSE 0,0190, MAE 0,0112.

### Diebold-Mariano contre HAR-RV (plis réunis, QLIKE)

| Modèle | Différence moyenne | Statistique (HLN) | p-valeur | Jours | Retards HAC | Sens | Significatif à 5 % |
|---|---:|---:|---:|---:|---:|---|---|
| GARCH(1,1) | 0,1205 | 4,11 | < 0,0001 | 1 812 | 7 | référence meilleure | oui |
| XGBoost | −0,0003 | −0,01 | 0,9903 | 1 812 | 7 | modèle meilleur | non |
| HAR-RV contre persistance (descriptif) | −0,0567 | −4,08 | < 0,0001 | 1 812 | 7 | modèle meilleur | oui |

Pour le test descriptif, le « modèle » est HAR-RV et la « référence » est la persistance.

### QLIKE par pli

| Modèle | pli 1 | pli 2 | pli 3 | pli 4 | pli 5 |
|---|---:|---:|---:|---:|---:|
| Persistance | 0,284 | 0,384 | 0,259 | 0,491 | 0,327 |
| HAR-RV | 0,256 | 0,332 | 0,220 | 0,391 | 0,264 |
| GARCH(1,1) | 0,287 | 0,452 | 0,315 | 0,672 | 0,338 |
| XGBoost | 0,298 | 0,336 | 0,247 | 0,359 | 0,222 |

### Crises (descriptif, sans test)

| Modèle | covid | terra_luna | ftx |
|---|---:|---:|---:|
| Persistance (QLIKE) | 0,416 | 0,214 | 0,522 |
| HAR-RV (QLIKE) | 0,476 | 0,247 | 0,416 |
| GARCH(1,1) (QLIKE) | 0,502 | 0,357 | 0,701 |
| XGBoost (QLIKE) | 0,520 | 0,322 | 0,480 |

### Classement provisoire (persistance exclue)

| Définition | Classement |
|---|---|
| QLIKE moyen sur tous les jours évalués réunis | XGBoost < HAR-RV < GARCH(1,1) |
| Moyenne des QLIKE moyens par pli (définition littérale de la règle) | XGBoost < HAR-RV < GARCH(1,1) |

Les deux définitions donnent le même classement.
Précision décidée après avoir vu les résultats des baselines (voir `docs/CHOIX.md`). Le classement définitif viendra après le deep learning.

### Vérification de l'exception 2 : moyenne des résidus en log d'XGBoost sur la validation interne

| Découpage | Moyenne des résidus (cible − prévision) | s² |
|---|---:|---:|
| pli 1 | 0,008 | 0,106 |
| pli 2 | −0,015 | 0,083 |
| pli 3 | −0,002 | 0,074 |
| pli 4 | −0,073 | 0,097 |
| pli 5 | −0,139 | 0,129 |
| test final | −0,006 | 0,074 |

Une moyenne négative signifie que XGBoost prévoit trop haut sur la validation interne.

Figure : `figures/figure_4_previsions_ETHUSDT.png`.

## Lecture des résultats

Chaque phrase ci-dessous est générée à partir des valeurs de `rapports/baselines.json`.

- BTC : HAR-RV fait significativement mieux que la persistance (test descriptif) : le modèle apporte plus que « demain comme aujourd'hui ».
- BTC : GARCH(1,1) fait significativement moins bien que HAR-RV en QLIKE. Explication possible, non démontrée : GARCH n'utilise que les rendements journaliers, sans l'information des données de 5 minutes.
- BTC : XGBoost a un QLIKE moyen plus faible que HAR-RV, mais l'écart n'est pas significatif (p-valeur 0,25) : on ne peut pas dire qu'XGBoost fait mieux.
- BTC : pendant le Covid et Terra-Luna, la persistance a un QLIKE plus faible que HAR-RV (descriptif, sans test). Explication possible, non démontrée : quand la volatilité change brutalement, la valeur de la veille suit mieux que les moyennes sur 7 et 30 jours.
- ETH : HAR-RV fait significativement mieux que la persistance (test descriptif) : le modèle apporte plus que « demain comme aujourd'hui ».
- ETH : GARCH(1,1) fait significativement moins bien que HAR-RV en QLIKE. Explication possible, non démontrée : GARCH n'utilise que les rendements journaliers, sans l'information des données de 5 minutes.
- ETH : XGBoost a un QLIKE moyen plus faible que HAR-RV, mais l'écart n'est pas significatif (p-valeur 0,99) : on ne peut pas dire qu'XGBoost fait mieux.
- ETH : pendant le Covid et Terra-Luna, la persistance a un QLIKE plus faible que HAR-RV (descriptif, sans test). Explication possible, non démontrée : quand la volatilité change brutalement, la valeur de la veille suit mieux que les moyennes sur 7 et 30 jours.
- ETH : XGBoost est meilleur que HAR-RV en QLIKE mais moins bon en RMSE. Les deux mesures ne jugent pas la même chose : QLIKE punit surtout une variance prévue trop basse, en relatif ; RMSE punit les grandes erreurs en niveau, donc surtout les jours très agités.

