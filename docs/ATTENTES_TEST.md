# Attentes du test final

Écrites et commitées le 2026-11-19, AVANT l'ouverture du test final. Version lue par le programme : `config/attentes_test.toml`. Le programme d'ouverture (`src/ouvrir_test.py`) refuse d'ouvrir le test si ces deux fichiers ne sont pas dans le commit poussé.

## Ce qui est testé

- Période du test : dates de cible du 2025-01-01 au 2026-10-31. Le test est ouvert une seule fois.
- Modèle retenu par la règle de sélection sur le développement : **Transformer pour BTC**, **CNN-LSTM pour ETH**.
- Modèles du découpage du test final (ajustement jusqu'au 2024-06-30), chargés et vérifiés par empreinte, sans aucun réentraînement ; s² mesuré sur la validation interne de ce découpage (2024-07-01 à 2024-12-31) ; prévision d'un modèle réglé = moyenne des log de ses 3 graines.
- QLIKE moyen sur tous les jours du test (une seule période). Aucune crise n'est définie dans la période du test : il n'y aura rien à rapporter par crise.

## Hypothèses

| | Énoncé | Comment on juge |
|---|---|---|
| H1 (principale) | Pour chaque actif, QLIKE(modèle retenu) < QLIKE(HAR-RV) sur le test | Diebold-Mariano bilatéral (d = QLIKE du modèle retenu − QLIKE de HAR-RV ; Newey-West, Harvey-Leybourne-Newbold, Student à T − 1), p-valeurs ajustées par Holm sur les 2 actifs, seuil 5 %. Confirmée pour un actif si la moyenne de d est négative et la p-valeur ajustée est sous 0,05. |
| H2 | QLIKE(HAR-RV) < QLIKE(persistance) | QLIKE moyen du test, pour chaque actif ; Diebold-Mariano rapporté à titre descriptif. |
| H3 | QLIKE(GARCH(1,1)) > QLIKE(HAR-RV) | QLIKE moyen du test, pour chaque actif ; Diebold-Mariano rapporté à titre descriptif. |
| H4 | La VaR à 1 jour à 95 % de HAR-RV n'est pas rejetée par le test de Kupiec (p-valeur > 0,05) | Pour chaque actif. |
| H5 | La stratégie du modèle retenu a une volatilité réalisée et un drawdown maximal plus faibles que l'achat simple | Pour chaque actif : volatilité réalisée plus basse ET drawdown maximal moins profond (frais de 0,10 %). |
| H6 (descriptive) | Le gain du modèle retenu sur HAR-J est plus faible que son gain sur HAR-RV | Gains relatifs en QLIKE moyen du test, pour chaque actif. |

## Prévision chiffrée

Gain attendu du modèle retenu sur HAR-RV entre 0 % et 15 % ; significativité incertaine (elle disparaissait sans 2024 sur le développement).

Gain = (QLIKE de HAR-RV − QLIKE du modèle retenu) / QLIKE de HAR-RV, sur tous les jours du test.

## Rapporté à titre descriptif

- Les 7 comparaisons contre HAR-RV de chaque actif (GARCH, XGBoost, les 5 réseaux), avec les p-valeurs brutes et ajustées par Holm sur 7.
- HAR-J (HAR-RV + jour de la semaine de la cible), hors de la sélection et hors de la famille de Holm principale.
- Métriques et intervalles bootstrap de tous les modèles ; stratégie et VaR de tous les modèles.

## Règle de publication

Tous les résultats sont publiés, quels qu'ils soient. Tout bug découvert après l'ouverture est corrigé par une rectification datée, et les deux versions sont publiées.
