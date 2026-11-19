# Explicabilité (développement, 2020 à 2024)

Fichier généré par `src/explicabilite.py` à partir de `rapports/explicabilite.json` : ne pas le modifier à la main.

- SHAP : XGBoost (TreeExplainer, exact) ; LSTM et modèle retenu de chaque actif (GradientExplainer, 1 000 tirages, fond de 100 séquences de la fenêtre d'ajustement). Contributions en unités de log(RV) ; importance = moyenne des valeurs absolues sur les jours évalués, puis somme ; moyenne des 3 graines, puis des 5 plis. Retard 1 = jour J, veille de la cible.
- Les modèles expliqués sont exactement ceux qui ont été évalués (réseaux rechargés, XGBoost ré-entraîné ; contrôle à 1e-9).
- Fidélité : sur la validation interne de chaque pli, la meilleure et la moins bonne variable SHAP sont permutées (20 répétitions, graine 42) ; fidèle si la meilleure dégrade plus le QLIKE.
- **Limite : l'attention montre où le modèle regarde, pas nécessairement pourquoi il décide.**

## BTCUSDT

Modèle retenu : **Transformer**.

### Les 5 variables les plus importantes

| Modèle | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| XGBoost (SHAP) | RV du jour (21,7 %) | largeur de Bollinger (12,9 %) | RV moyenne 7 j (12,7 %) | RSI 14 j (8,2 %) | RV moyenne 30 j (8,1 %) |
| LSTM (SHAP) | jour de la semaine (20,5 %) | log-volume (14,6 %) | log RV du jour (11,7 %) | largeur de Bollinger (7,6 %) | log-rendement (7,0 %) |
| Transformer (SHAP) | log-volume (19,9 %) | jour de la semaine (15,3 %) | largeur de Bollinger (10,4 %) | log RV du jour (8,3 %) | log RV moyenne 7 j (6,8 %) |
| TFT (sélection des variables) | y (log RV du jour, TFT) (13,4 %) | largeur de Bollinger (10,4 %) | Garman-Klass (9,6 %) | log-volume (8,3 %) | RV moyenne 30 j (7,2 %) |

### Importance par retard (part du total)

| Modèle | Retard 1 | Retard 2 | Retard 3 | Retards 1 à 5 | Retards 6 à 30 |
|---|---:|---:|---:|---:|---:|
| LSTM (SHAP) | 38,5 % | 18,1 % | 10,9 % | 79,7 % | 20,3 % |
| Transformer (SHAP) | 62,0 % | 1,4 % | 1,5 % | 67,7 % | 32,3 % |
| TFT (attention) | 3,7 % | 3,7 % | 3,5 % | 17,9 % | 82,1 % |
| Transformer (attention) | 3,6 % | 3,6 % | 3,6 % | 18,0 % | 82,0 % |

### Attention du Transformer : jours de crise contre autres jours

Jours de crise : 181 ; autres jours : 1 631.

| Jours | Retard 1 | Retard 2 | Retard 3 | Retards 1 à 5 | Retards 6 à 30 |
|---|---:|---:|---:|---:|---:|
| Crises | 4,0 % | 4,0 % | 4,0 % | 19,6 % | 80,4 % |
| Autres | 3,6 % | 3,6 % | 3,6 % | 17,8 % | 82,2 % |

### Fidélité par pli

| Modèle | Pli | Meilleure variable | Dégradation | Moins bonne variable | Dégradation | Fidèle |
|---|---|---|---:|---|---:|---|
| XGBoost | pli 1 | largeur de Bollinger | −0,0468 | log RV moyenne 30 j | −0,0022 | non |
| XGBoost | pli 2 | RV du jour | 0,0479 | log RV moyenne 30 j | 0,0012 | oui |
| XGBoost | pli 3 | RV du jour | −0,0087 | jour de la semaine | 0,0000 | non |
| XGBoost | pli 4 | RV du jour | 0,0605 | log-rendement | 0,0012 | oui |
| XGBoost | pli 5 | RV du jour | −0,0341 | log RV moyenne 30 j | 0,0045 | non |
| LSTM | pli 1 | log-volume | 0,0038 | RV moyenne 7 j | 0,0021 | oui |
| LSTM | pli 2 | log-volume | 0,0307 | Garman-Klass | 0,0008 | oui |
| LSTM | pli 3 | jour de la semaine | 0,0551 | log RV moyenne 7 j | −0,0012 | oui |
| LSTM | pli 4 | jour de la semaine | 0,1226 | Garman-Klass | 0,0011 | oui |
| LSTM | pli 5 | jour de la semaine | 0,1905 | Garman-Klass | 0,0038 | oui |
| Transformer | pli 1 | log-volume | 0,0036 | RV moyenne 30 j | −0,0090 | oui |
| Transformer | pli 2 | log-volume | 0,0400 | RV moyenne 30 j | 0,0012 | oui |
| Transformer | pli 3 | log-volume | 0,0021 | RV moyenne 30 j | 0,0003 | oui |
| Transformer | pli 4 | jour de la semaine | 0,0673 | Garman-Klass | 0,0003 | oui |
| Transformer | pli 5 | jour de la semaine | 0,1850 | Garman-Klass | 0,0024 | oui |

Dégradation : QLIKE moyen sur la validation interne avec la variable permutée, moins QLIKE sans permutation.

### Contrôles

| Modèle | Reproduction (écart maximal) | Additivité |
|---|---:|---|
| XGBoost | 0,000000000000 | écart maximal 0,0000100 (tolérance 0,0001) |
| LSTM | 0,000000000000 | erreur relative maximale 5,53 % (tolérance 6 %) |
| Transformer | 0,000000000000 | erreur relative maximale 5,52 % (tolérance 6 %) |
| Transformer (attention) | 0,000000000000 | — |
| TFT | 0,000000000000 | — |

Figures : `figures/figure_7_importance_variables_BTCUSDT.png`, `figures/figure_8_importance_retards_BTCUSDT.png`.

## ETHUSDT

Modèle retenu : **CNN-LSTM**.

### Les 5 variables les plus importantes

| Modèle | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| XGBoost (SHAP) | RV du jour (20,6 %) | RV moyenne 7 j (16,6 %) | Parkinson (15,0 %) | RSI 14 j (8,0 %) | largeur de Bollinger (6,7 %) |
| LSTM (SHAP) | jour de la semaine (20,7 %) | log RV du jour (15,4 %) | log-volume (9,6 %) | RV du jour (7,8 %) | Parkinson (7,1 %) |
| CNN-LSTM (SHAP) | jour de la semaine (19,7 %) | log RV du jour (12,9 %) | log-volume (11,7 %) | log RV moyenne 7 j (7,6 %) | log-rendement (6,7 %) |
| TFT (sélection des variables) | log RV du jour (17,1 %) | y (log RV du jour, TFT) (10,9 %) | log-rendement (8,7 %) | RV du jour (8,5 %) | RSI 14 j (8,3 %) |

### Importance par retard (part du total)

| Modèle | Retard 1 | Retard 2 | Retard 3 | Retards 1 à 5 | Retards 6 à 30 |
|---|---:|---:|---:|---:|---:|
| LSTM (SHAP) | 53,1 % | 17,7 % | 9,3 % | 90,3 % | 9,7 % |
| CNN-LSTM (SHAP) | 40,3 % | 23,4 % | 11,6 % | 86,0 % | 14,0 % |
| TFT (attention) | 3,6 % | 3,4 % | 3,5 % | 17,4 % | 82,6 % |
| Transformer (attention) | 3,4 % | 3,4 % | 3,4 % | 17,1 % | 82,9 % |

### Attention du Transformer : jours de crise contre autres jours

Jours de crise : 181 ; autres jours : 1 631.

| Jours | Retard 1 | Retard 2 | Retard 3 | Retards 1 à 5 | Retards 6 à 30 |
|---|---:|---:|---:|---:|---:|
| Crises | 3,6 % | 3,5 % | 3,5 % | 17,6 % | 82,4 % |
| Autres | 3,4 % | 3,4 % | 3,4 % | 17,0 % | 83,0 % |

### Fidélité par pli

| Modèle | Pli | Meilleure variable | Dégradation | Moins bonne variable | Dégradation | Fidèle |
|---|---|---|---:|---|---:|---|
| XGBoost | pli 1 | Parkinson | 0,0406 | log RV moyenne 30 j | 0,0000 | oui |
| XGBoost | pli 2 | Parkinson | 0,0437 | Garman-Klass | −0,0012 | oui |
| XGBoost | pli 3 | RV du jour | −0,0147 | MACD relatif | 0,0000 | non |
| XGBoost | pli 4 | RV du jour | 0,0537 | log RV moyenne 30 j | 0,0001 | oui |
| XGBoost | pli 5 | RV du jour | −0,0040 | log RV moyenne 30 j | −0,0000 | non |
| LSTM | pli 1 | jour de la semaine | 0,0252 | RV moyenne 30 j | 0,0028 | oui |
| LSTM | pli 2 | log-volume | 0,0107 | MACD relatif | −0,0018 | oui |
| LSTM | pli 3 | jour de la semaine | 0,0496 | log RV moyenne 30 j | −0,0013 | oui |
| LSTM | pli 4 | log RV du jour | 0,0419 | MACD relatif | −0,0008 | oui |
| LSTM | pli 5 | jour de la semaine | 0,0901 | RV moyenne 30 j | −0,0132 | oui |
| CNN-LSTM | pli 1 | log-volume | 0,0090 | RV moyenne 30 j | 0,0009 | oui |
| CNN-LSTM | pli 2 | log-volume | 0,0130 | Garman-Klass | −0,0004 | oui |
| CNN-LSTM | pli 3 | jour de la semaine | 0,0705 | Garman-Klass | −0,0008 | oui |
| CNN-LSTM | pli 4 | log RV du jour | 0,0368 | Garman-Klass | 0,0002 | oui |
| CNN-LSTM | pli 5 | jour de la semaine | 0,1908 | Garman-Klass | 0,0017 | oui |

Dégradation : QLIKE moyen sur la validation interne avec la variable permutée, moins QLIKE sans permutation.

### Contrôles

| Modèle | Reproduction (écart maximal) | Additivité |
|---|---:|---|
| XGBoost | 0,000000000000 | écart maximal 0,0000043 (tolérance 0,0001) |
| LSTM | 0,000000000000 | erreur relative maximale 4,95 % (tolérance 6 %) |
| CNN-LSTM | 0,000000000000 | erreur relative maximale 4,44 % (tolérance 6 %) |
| Transformer (attention) | 0,000000000000 | — |
| TFT | 0,000000000000 | — |

Figures : `figures/figure_7_importance_variables_ETHUSDT.png`, `figures/figure_8_importance_retards_ETHUSDT.png`.

Figure de l'attention du Transformer : `figures/figure_9_attention_transformer.png`.

## Lecture des résultats

Chaque phrase ci-dessous est générée à partir des valeurs de `rapports/explicabilite.json`.

- BTC : la variable en tête n'est pas la même pour tous les modèles : XGBoost : RV du jour ; LSTM : jour de la semaine ; Transformer : log-volume.
- BTC : pour XGBoost, les mesures de volatilité passée (RV, Parkinson, Garman-Klass) pèsent 61,0 % de l'importance : l’essentiel.
- BTC : pour LSTM, les mesures de volatilité passée (RV, Parkinson, Garman-Klass) pèsent 39,9 % de l'importance.
- BTC : pour Transformer, les mesures de volatilité passée (RV, Parkinson, Garman-Klass) pèsent 40,1 % de l'importance.
- BTC : pour LSTM, les 5 derniers jours portent 79,7 % de l'importance SHAP : le modèle s'appuie surtout sur le passé récent. Le retard le plus important est le retard 1.
- BTC : pour Transformer, les 5 derniers jours portent 67,7 % de l'importance SHAP : le modèle s'appuie surtout sur le passé récent. Le retard le plus important est le retard 1.
- BTC : le jour de la semaine est dans les 2 premières variables de LSTM et Transformer. Son importance SHAP additionne 7 colonnes (codage en one-hot), ce qui peut la grossir ; mais la permutation, qui ne dépend pas de ce codage, confirme son poids pour LSTM et Transformer (meilleure variable d'au moins un pli où le modèle est fidèle). HAR-RV n'utilise pas le jour de la semaine : c'est une explication possible, non démontrée, d'une partie du gain des réseaux.
- BTC : pour XGBoost, permuter la meilleure variable SHAP AMÉLIORE le QLIKE de validation sur pli 1, pli 3 et pli 5. Explication possible, non démontrée : les mesures de volatilité (RV, Parkinson, Garman-Klass) sont très corrélées ; SHAP répartit le mérite entre elles, et la permutation d'une seule crée des combinaisons irréalistes que les arbres traitent mal.
- BTC : l'attention du Transformer est presque uniforme : au plus 3,6 % par retard, pour 3,3 % si tous les retards avaient le même poids ; elle ne distingue presque pas les jours.
- BTC : le TFT voit deux fois le log de la RV du jour (sa série « y » et la variable log_rv_1) : leurs importances (13,4 % et 5,1 %) se partagent la même information.
- BTC : pendant les crises, l'attention du Transformer sur les 5 derniers jours est plus forte que les autres jours (19,6 % contre 17,8 %) (descriptif ; l'attention montre où le modèle regarde, pas nécessairement pourquoi il décide).
- BTC : XGBoost est fidèle sur 2 plis sur 5 ; pas fidèle sur pli 1, pli 3 et pli 5 : sur ces plis, le classement SHAP ne correspond pas à l'effet réel de la permutation, et SHAP échoue à expliquer ce modèle.
- BTC : LSTM est fidèle sur 5 plis sur 5 : le classement SHAP correspond à l'effet réel de la permutation sur chaque pli.
- BTC : Transformer est fidèle sur 5 plis sur 5 : le classement SHAP correspond à l'effet réel de la permutation sur chaque pli.
- ETH : la variable en tête n'est pas la même pour tous les modèles : XGBoost : RV du jour ; LSTM : jour de la semaine ; CNN-LSTM : jour de la semaine.
- ETH : pour XGBoost, les mesures de volatilité passée (RV, Parkinson, Garman-Klass) pèsent 66,9 % de l'importance : l’essentiel.
- ETH : pour LSTM, les mesures de volatilité passée (RV, Parkinson, Garman-Klass) pèsent 50,9 % de l'importance : l’essentiel.
- ETH : pour CNN-LSTM, les mesures de volatilité passée (RV, Parkinson, Garman-Klass) pèsent 47,5 % de l'importance.
- ETH : pour LSTM, les 5 derniers jours portent 90,3 % de l'importance SHAP : le modèle s'appuie surtout sur le passé récent. Le retard le plus important est le retard 1.
- ETH : pour CNN-LSTM, les 5 derniers jours portent 86,0 % de l'importance SHAP : le modèle s'appuie surtout sur le passé récent. Le retard le plus important est le retard 1.
- ETH : le jour de la semaine est dans les 2 premières variables de LSTM et CNN-LSTM. Son importance SHAP additionne 7 colonnes (codage en one-hot), ce qui peut la grossir ; mais la permutation, qui ne dépend pas de ce codage, confirme son poids pour LSTM et CNN-LSTM (meilleure variable d'au moins un pli où le modèle est fidèle). HAR-RV n'utilise pas le jour de la semaine : c'est une explication possible, non démontrée, d'une partie du gain des réseaux.
- ETH : pour XGBoost, permuter la meilleure variable SHAP AMÉLIORE le QLIKE de validation sur pli 3 et pli 5. Explication possible, non démontrée : les mesures de volatilité (RV, Parkinson, Garman-Klass) sont très corrélées ; SHAP répartit le mérite entre elles, et la permutation d'une seule crée des combinaisons irréalistes que les arbres traitent mal.
- ETH : l'attention du Transformer est presque uniforme : au plus 3,9 % par retard, pour 3,3 % si tous les retards avaient le même poids ; elle ne distingue presque pas les jours.
- ETH : l'attention du TFT est presque uniforme : au plus 3,8 % par retard, pour 3,3 % si tous les retards avaient le même poids ; elle ne distingue presque pas les jours.
- ETH : le TFT voit deux fois le log de la RV du jour (sa série « y » et la variable log_rv_1) : leurs importances (10,9 % et 17,1 %) se partagent la même information.
- ETH : pendant les crises, l'attention du Transformer sur les 5 derniers jours est plus forte que les autres jours (17,6 % contre 17,0 %) (descriptif ; l'attention montre où le modèle regarde, pas nécessairement pourquoi il décide).
- ETH : XGBoost est fidèle sur 3 plis sur 5 ; pas fidèle sur pli 3 et pli 5 : sur ces plis, le classement SHAP ne correspond pas à l'effet réel de la permutation, et SHAP échoue à expliquer ce modèle.
- ETH : LSTM est fidèle sur 5 plis sur 5 : le classement SHAP correspond à l'effet réel de la permutation sur chaque pli.
- ETH : CNN-LSTM est fidèle sur 5 plis sur 5 : le classement SHAP correspond à l'effet réel de la permutation sur chaque pli.

