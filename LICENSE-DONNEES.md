# Licence des données et des fichiers dérivés

## Les données ne sont pas incluses

Les données de marché utilisées par ce projet (bougies de 5 minutes de BTCUSDT et ETHUSDT, Binance spot) proviennent de **Binance Vision** (https://data.binance.vision). Elles ne sont **pas** incluses dans ce dépôt : ni les fichiers bruts, ni les fichiers convertis, ni aucune série journalière dérivée. Le dépôt contient seulement des manifestes (noms, tailles et empreintes SHA-256 des fichiers) qui permettent de vérifier des données téléchargées soi-même avec `src/telecharger.py`.

Ces données sont fournies par Binance sous la licence **Creative Commons Attribution - Pas d'utilisation commerciale - Partage dans les mêmes conditions 4.0 International (CC BY-NC-SA 4.0)** et selon les conditions « Vision Dataset Terms » :

- conditions : https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md
- page officielle : https://data.binance.vision/terms-of-use.html
- texte de la licence : https://creativecommons.org/licenses/by-nc-sa/4.0/deed.fr

Elles sont utilisées ici dans un cadre éducatif et non commercial.

## Fichiers dérivés des données : CC BY-NC-SA 4.0

Les fichiers suivants sont calculés à partir de ces données. Ce sont des œuvres dérivées, publiées sous la même licence **CC BY-NC-SA 4.0** :

- les figures (`figures/`) ;
- les captures de l'application (`docs/captures/`) ;
- les résultats agrégés (`rapports/`) ;
- la synthèse (`docs/synthese.pdf`) ;
- les modèles servis par l'API, au format ONNX, et leurs paramètres (`api/modeles/`).

**Attribution** : « Données : Binance Vision, CC BY-NC-SA 4.0 — projet volatility-forecasting-dl, Mohamed Aljene ». Toute réutilisation doit rester non commerciale, citer cette attribution et être partagée sous la même licence.

## Le code

Le code du dépôt (Python, tests, scripts, configuration) est sous licence MIT : voir `LICENSE`.
