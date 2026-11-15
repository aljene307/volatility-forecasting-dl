# Analyse exploratoire

Fichier généré par `src/exploration.py` à partir de `rapports/exploration.json` : ne pas le modifier à la main.

- Période : jours du 2018-01-01 au 2024-12-31, **développement seulement** (le test final est aveugle : aucune valeur n'en est calculée ici).
- Seuls les jours valides sont utilisés ; les jours non valides sont laissés vides pour l'autocorrélation et retirés pour le test ADF (limite écrite dans les règles).
- Figures : `figures/figure_1_rv_annualisee.png`, `figures/figure_2_autocorrelation_log_rv.png`, `figures/figure_3_histogrammes_rv.png`.

## Comptages

| Actif | Jours | Jours valides | Jours non valides (retirés pour l'ADF) |
|---|---:|---:|---:|
| BTCUSDT | 2 557 | 2 527 | 30 |
| ETHUSDT | 2 557 | 2 527 | 30 |

## Autocorrélation de log(RV)

| Actif | 1 jour | 7 jours | 30 jours |
|---|---:|---:|---:|
| BTCUSDT | 0,73 | 0,58 | 0,28 |
| ETHUSDT | 0,74 | 0,55 | 0,30 |

Interprétation : l'autocorrélation reste nettement au-dessus de la zone « aucune autocorrélation » (± 0,039) même à 30 jours. Une journée agitée est suivie de journées agitées : c'est le regroupement de volatilité, que les modèles HAR et GARCH exploitent.

Pic tous les 7 jours (voir la figure 2) : l'autocorrélation au retard 7 dépasse la moyenne des retards 6 et 8 pour les deux actifs. La volatilité semble dépendre du jour de la semaine, ce qui justifie la variable « jour de la semaine ».

## Test ADF (racine unitaire, retards choisis par AIC)

| Actif | Série | Statistique | Valeur critique à 5 % | p-valeur | Retards | Observations |
|---|---|---:|---:|---:|---:|---:|
| BTCUSDT | log(RV) | -4,66 | -2,86 | < 0,0001 | 27 | 2 499 |
| BTCUSDT | log(clôture) | -0,33 | -2,86 | 0,9206 | 4 | 2 522 |
| ETHUSDT | log(RV) | -4,60 | -2,86 | 0,0001 | 27 | 2 499 |
| ETHUSDT | log(clôture) | -0,76 | -2,86 | 0,8315 | 10 | 2 516 |

- Interprétation pour log(RV) : p-valeur sous 5 % pour les deux actifs : on rejette la racine unitaire, la série revient vers sa moyenne (stationnaire).
- Interprétation pour log(clôture) : p-valeur au-dessus de 5 % pour les deux actifs : on ne peut pas rejeter la racine unitaire, la série dérive (non stationnaire).
- Conséquence : on modélise log(RV), et non le prix ; la cible est stable dans le temps, le prix ne l'est pas.

## Asymétrie

| Actif | Asymétrie de RV | Asymétrie de log(RV) |
|---|---:|---:|
| BTCUSDT | 3,73 | 0,16 |
| ETHUSDT | 3,79 | 0,17 |

Interprétation : la RV a une longue queue à droite (quelques journées extrêmes) ; en log, la distribution est bien plus symétrique. C'est pourquoi les modèles prévoient log(RV).

## Règle de secours (comptages)

| Actif | Jours remplacés : préchauffage | Jours remplacés : développement | Exemples gardés du développement | … dont la fenêtre de 30 jours contient un jour remplacé |
|---|---:|---:|---:|---:|
| BTCUSDT | 4 | 26 | 2 441 | 585 |
| ETHUSDT | 4 | 26 | 2 441 | 585 |

Limite : le rendement d'un jour remplacé est nul, et celui du lendemain porte sur deux jours.
