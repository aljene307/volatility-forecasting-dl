"""Conversion des zips Binance en un fichier Parquet par actif.

- Chaque zip est lu sans être modifié ; un éventuel en-tête est détecté.
- L'unité des horodatages est détectée fichier par fichier : 13 chiffres = millisecondes,
  16 chiffres = microsecondes. Tout autre cas (ou un mélange) est une ERREUR : on s'arrête.
- Les dates sont converties en UTC (précision microseconde, exacte pour les deux unités).
- Un mois à la fois est traité, pour limiter la mémoire.
- L'empreinte de CONTENU de chaque Parquet est calculée sur les valeurs relues (et non sur
  les octets du fichier), pour ne pas dépendre de la version de pyarrow.

Usage : .venv\\Scripts\\python src/convertir.py
"""

from __future__ import annotations

import hashlib
import io
import os
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))

import commun as C  # noqa: E402
import regles as R  # noqa: E402

# Colonnes des klines Binance, dans l'ordre du fichier, nommées en clair
COLONNES_BRUTES = [
    "date_ouverture", "ouverture", "plus_haut", "plus_bas", "cloture", "volume",
    "date_cloture", "volume_cotation", "nombre_transactions",
    "volume_achat_base", "volume_achat_cotation", "ignore",
]
COLONNES_DATES = ["date_ouverture", "date_cloture"]
COLONNES_REELS = ["ouverture", "plus_haut", "plus_bas", "cloture", "volume",
                  "volume_cotation", "volume_achat_base", "volume_achat_cotation"]
COLONNES_ENTIERS = ["nombre_transactions"]
COLONNES_SORTIE = ["date_ouverture", "date_cloture", "ouverture", "plus_haut", "plus_bas", "cloture",
                   "volume", "volume_cotation", "nombre_transactions", "volume_achat_base", "volume_achat_cotation"]
SCHEMA = pa.schema(
    [(c, pa.timestamp("us", tz="UTC")) if c in COLONNES_DATES
     else (c, pa.int64()) if c in COLONNES_ENTIERS
     else (c, pa.float64()) for c in COLONNES_SORTIE]
)
UNITES = {13: "ms", 16: "us"}


class ErreurConversion(ValueError):
    pass


def detecter_unite(valeurs: np.ndarray, contexte: str = "") -> str:
    """Unité d'un ensemble d'horodatages entiers : "ms" (13 chiffres) ou "us" (16 chiffres)."""
    valeurs = np.asarray(valeurs)
    if valeurs.size == 0:
        raise ErreurConversion(f"Aucun horodatage {contexte}".strip())
    if not np.issubdtype(valeurs.dtype, np.integer) or (valeurs <= 0).any():
        raise ErreurConversion(f"Horodatages non entiers ou non positifs {contexte}".strip())
    chiffres = set(np.char.str_len(valeurs.astype(str)).tolist())
    if len(chiffres) != 1 or next(iter(chiffres)) not in UNITES:
        raise ErreurConversion(
            f"Unité des horodatages ambiguë {contexte} : nombres de chiffres trouvés {sorted(chiffres)}, "
            "attendu uniquement 13 (millisecondes) ou uniquement 16 (microsecondes)".replace("  ", " "))
    return UNITES[next(iter(chiffres))]


def a_un_en_tete(premiere_ligne: str) -> bool:
    premier_champ = premiere_ligne.split(",")[0].strip().strip('"')
    return not premier_champ.isdigit()


def lire_zip(chemin: Path) -> tuple[pd.DataFrame, dict]:
    """Lit le CSV unique d'un zip (sans le modifier) et renvoie (bougies, informations)."""
    with zipfile.ZipFile(chemin) as archive:
        noms = [n for n in archive.namelist() if not n.endswith("/")]
        if len(noms) != 1:
            raise ErreurConversion(f"{chemin.name} : un seul fichier attendu dans le zip, trouvé {noms}")
        brut = archive.read(noms[0])
    texte = brut.decode("ascii")
    en_tete = a_un_en_tete(texte.split("\n", 1)[0])
    # round_trip : lecture exacte des nombres (arrondi correct), quelle que soit la version de pandas.
    df = pd.read_csv(io.StringIO(texte), header=None, skiprows=1 if en_tete else 0, names=COLONNES_BRUTES,
                     float_precision="round_trip",
                     dtype={**{c: "int64" for c in COLONNES_DATES + COLONNES_ENTIERS},
                            **{c: "float64" for c in COLONNES_REELS}, "ignore": "float64"})
    unites = {c: detecter_unite(df[c].to_numpy(), f"dans {chemin.name}, colonne {c}") for c in COLONNES_DATES}
    if len(set(unites.values())) != 1:
        raise ErreurConversion(f"{chemin.name} : unités différentes entre colonnes {unites}")
    unite = unites["date_ouverture"]
    for c in COLONNES_DATES:
        df[c] = pd.to_datetime(df[c], unit=unite, utc=True).astype("datetime64[us, UTC]")
    df = df[COLONNES_SORTIE]
    return df, {"fichier": chemin.name, "unite": unite, "en_tete": en_tete, "lignes": int(len(df))}


def empreinte_contenu(chemin_parquet: Path) -> str:
    """SHA-256 calculé sur les valeurs relues, colonne par colonne, sous une forme canonique.

    Dates : entiers en microsecondes ; réels : float64 petit-boutiste (NaN normalisé) ;
    entiers : int64 petit-boutiste. Indépendant du découpage en groupes de lignes et de la version de pyarrow.
    """
    fichier = pq.ParquetFile(chemin_parquet)
    h = hashlib.sha256()
    for nom in COLONNES_SORTIE:
        colonne = fichier.read(columns=[nom]).column(nom)
        if pa.types.is_timestamp(colonne.type):
            valeurs = colonne.cast(pa.timestamp("us", tz="UTC")).cast(pa.int64()).to_numpy().astype("<i8")
            sorte = "date_us"
        elif pa.types.is_integer(colonne.type):
            valeurs = colonne.to_numpy().astype("<i8")
            sorte = "entier64"
        else:
            valeurs = colonne.to_numpy().astype("<f8")
            valeurs = np.where(np.isnan(valeurs), np.float64("nan"), valeurs).astype("<f8")
            sorte = "reel64"
        h.update(f"{nom}:{sorte}:{len(valeurs)}\n".encode("utf-8"))
        h.update(valeurs.tobytes())
    return h.hexdigest()


def convertir_actif(actif: str, zips: list[Path], dossier_sortie: Path) -> dict:
    """Écrit <actif>_<intervalle>.parquet en traitant un mois à la fois."""
    dossier_sortie.mkdir(parents=True, exist_ok=True)
    nom_sortie = f"{actif}_5m.parquet"
    final = dossier_sortie / nom_sortie
    partiel = dossier_sortie / f"{nom_sortie}.part"
    sources, lignes = [], 0
    with pq.ParquetWriter(partiel, SCHEMA) as ecrivain:
        for chemin in zips:
            df, info = lire_zip(chemin)
            annee, mois = int(chemin.stem[-7:-3]), int(chemin.stem[-2:])
            dans_mois = (df["date_ouverture"].dt.year == annee) & (df["date_ouverture"].dt.month == mois)
            info["lignes_hors_mois"] = int((~dans_mois).sum())
            ecrivain.write_table(pa.Table.from_pandas(df, schema=SCHEMA, preserve_index=False))
            lignes += len(df)
            sources.append(info)
            del df
    os.replace(partiel, final)
    unites = sorted({s["unite"] for s in sources})
    return {
        "fichier": nom_sortie,
        "lignes": lignes,
        "colonnes": {champ.name: str(champ.type) for champ in SCHEMA},
        "empreinte_contenu_sha256": empreinte_contenu(final),
        "unites_trouvees": unites,
        "fichiers_avec_en_tete": sum(s["en_tete"] for s in sources),
        "lignes_hors_mois": sum(s["lignes_hors_mois"] for s in sources),
        "sources": sources,
    }


def executer(regles: dict, dossier_brut: Path, dossier_sortie: Path, chemin_manifeste: Path,
             chemin_manifeste_brut: Path) -> dict:
    d = regles["donnees"]
    resultat = {
        "manifeste_brut_sha256": hashlib.sha256(chemin_manifeste_brut.read_bytes()).hexdigest(),
        "actifs": {},
    }
    for actif in d["actifs"]:
        zips = [dossier_brut / C.nom_fichier_klines(actif, d["intervalle"], a, m)
                for a, m in C.mois_couverts(d["debut"], d["fin"])]
        manquants = [z.name for z in zips if not z.exists()]
        if manquants:
            raise ErreurConversion(f"{actif} : {len(manquants)} fichiers manquants, par exemple {manquants[:3]}")
        resultat["actifs"][actif] = convertir_actif(actif, zips, dossier_sortie)
        info = resultat["actifs"][actif]
        print(f"{actif} : {info['lignes']} lignes, unités {info['unites_trouvees']}, "
              f"{info['fichiers_avec_en_tete']} fichiers avec en-tête, {info['lignes_hors_mois']} lignes hors de leur mois")
    C.ecrire_texte(chemin_manifeste, C.texte_json(resultat))
    return resultat


def main() -> int:
    C.proteger_sortie()
    debut = time.perf_counter()
    regles = R.charger_regles()
    try:
        executer(regles, C.DOSSIER_BRUT, C.DOSSIER_TRAITE, C.MANIFESTE_TRAITE, C.MANIFESTE_BRUT)
    except ErreurConversion as erreur:
        print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1
    duree = time.perf_counter() - debut
    print(f"Manifeste : {C.chemin_relatif(C.MANIFESTE_TRAITE)}")
    print(f"Durée : {C.nombre_fr(duree, 1)} s | mémoire maximale du processus : {C.nombre_fr(C.memoire_max_mo(), 1)} Mo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
