# Journal des choix

Chaque entrée consigne une décision, sa raison et ce qui reste à vérifier.

## 2026-11-13 — Environnement et matériel

### Matériel mesuré

- Processeur : Intel Core i7-1255U, 10 cœurs (2 cœurs performance + 8 cœurs efficacité), 12 fils.
- Mémoire : 15,7 Go de RAM au total, environ 2,8 Go libres avec Chrome et VS Code ouverts.
- Carte graphique : Intel Iris Xe intégrée, sans CUDA (aucun GPU NVIDIA).

### Décision : où entraîner les modèles

- Entraînement en local d'abord.
- Google Colab seulement si un essai chronométré montre que c'est nécessaire.
- Raison : la reproductibilité est plus simple à garantir sur une seule machine.

### À mesurer plus tard

- Le nombre de fils de calcul le plus efficace pour l'entraînement : comparer 2, 4 et 8.
- Le seuil de mémoire libre au-dessous duquel les scripts lourds refusent de démarrer.

### Paramètres de reproductibilité

- Graine aléatoire et nombre de fils de calcul : placés dans une configuration commitée, pas dans .env (raison : reproductibilité).

### Fins de ligne

- `core.autocrlf = true` a été trouvé au niveau système de Git.
- Il est neutralisé localement dans le dépôt (`core.autocrlf = false`) et par le fichier `.gitattributes`, qui impose LF pour les fichiers texte (CRLF seulement pour les scripts `.ps1`).
- Raison : au projet 2, un fichier en CRLF a fait planter l'API.

### Python

- Python 3.11 dans l'environnement virtuel `.venv`, alors que la version par défaut du poste est 3.13.
- L'environnement se crée avec `py -3.11 -m venv .venv`.

### Documents du cours

- Les PDF du cours restent hors du dossier du projet.

### Outils

- Signature automatique des commits désactivée dans l'éditeur.
