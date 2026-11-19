"""Modèle descriptif HAR-J : HAR-RV + 6 indicatrices du jour de la semaine de la CIBLE (lundi en référence).

Règles : config/regles.toml, section modeles.har_j (déclaré le 2026-11-19, avant l'ouverture du test final) ;
docs/REGLES.md, section 17. Mêmes règles que HAR-RV : moindres carrés sur la fenêtre d'ajustement de chaque
découpage, s² mesuré sur la validation interne (par src/comparer.py). Hors de la sélection et hors de la famille
de Holm principale.

Le jour de la semaine de la cible est connu d'avance (calendrier) : ce n'est pas une information future.
Unités de reprise dans sorties/reprise/har_j (ignoré par Git) ; modèle du test final dans
sorties/modeles_test_final/{actif}/har_j.json, empreinte dans rapports/modele_har_j.json. Aucune prévision sur le test.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import baselines as B  # noqa: E402
import commun as C  # noqa: E402
import garde as G  # noqa: E402
import regles as R  # noqa: E402
import reprise as P  # noqa: E402
import variables as V  # noqa: E402

VERSION = "har-j-1"
DOSSIER_REPRISE = B.DOSSIER_SORTIES / "reprise" / "har_j"
CHEMIN_MANIFESTE = C.DOSSIER_RAPPORTS / "modele_har_j.json"


def matrice(exemples: pd.DataFrame, regles: dict) -> np.ndarray:
    """Colonnes de HAR-RV, puis une indicatrice par jour de la semaine de la cible, sauf la référence."""
    reference = regles["modeles"]["har_j"]["jour_reference"]
    jours = np.array([pd.Timestamp(d).weekday() for d in exemples["date_cible"]])
    indicatrices = [(jours == k).astype("float64") for k in range(7) if k != reference]
    return np.column_stack([B._matrice_har(exemples, regles)] + indicatrices)


def ajuster(exemples: pd.DataFrame, regles: dict) -> np.ndarray:
    coef, *_ = np.linalg.lstsq(matrice(exemples, regles), exemples["cible"].to_numpy(dtype="float64"), rcond=None)
    return coef


def prevoir(exemples: pd.DataFrame, coef, regles: dict) -> np.ndarray:
    return matrice(exemples, regles) @ np.asarray(coef, dtype="float64")


def identifiant(actif: str, decoupage: dict, cle: str) -> str:
    return f"{VERSION}|{actif}|HAR-J|{decoupage['nom']}|{cle}"


def previsions_decoupage(exemples: pd.DataFrame, regles: dict, decoupage: dict, prevoir_evaluation: bool) -> dict:
    m = B.masques(exemples, decoupage)
    aj = exemples[m["ajustement"]]
    parties = {"validation": exemples[m["validation"]]}
    if prevoir_evaluation:
        G.refuser_si_test(exemples.loc[m["evaluation"], "date_cible"], f"HAR-J, {decoupage['nom']}")
        parties["evaluation"] = exemples[m["evaluation"]]
    coef = ajuster(aj, regles)
    sortie = {"coefficients": coef.tolist(), "noms": ["constante"] + [f"log_rv_{n}" for n in regles["modeles"]["har_rv"]["fenetres_jours"]]
              + [f"jour_{k}" for k in range(7) if k != regles["modeles"]["har_j"]["jour_reference"]]}
    for nom, p in parties.items():
        sortie[nom] = {"date_cible": [str(d) for d in p["date_cible"]], "prevision_log": prevoir(p, coef, regles).tolist()}
    return sortie


def executer(regles: dict) -> dict:
    import json
    manifeste = json.loads((C.RACINE / regles["variables"]["sorties"]["manifeste"]).read_text(encoding="utf-8"))
    cle = manifeste["empreinte_contenu_sha256"][:12]
    decoupages = R.decoupages(regles)
    empreintes = {}
    for actif in regles["donnees"]["actifs"]:
        exemples, _ = B.donnees_actif(V.lire_bougies(C.DOSSIER_TRAITE / f"{actif}_5m.parquet"), regles)
        for numero, d in enumerate(decoupages):
            final = numero == len(decoupages) - 1

            def calcul(_id: str, _graine: int, d=d, final=final) -> dict:
                return previsions_decoupage(exemples, regles, d, prevoir_evaluation=not final)

            P.executer([identifiant(actif, d, cle)], calcul, DOSSIER_REPRISE)
        u = P.lire_unite(DOSSIER_REPRISE, identifiant(actif, decoupages[-1], cle))
        dossier = B.DOSSIER_MODELES / actif
        dossier.mkdir(parents=True, exist_ok=True)
        chemin = dossier / "har_j.json"
        C.ecrire_texte(chemin, C.texte_json({"coefficients": u["coefficients"], "noms": u["noms"]}))
        empreintes[actif] = {"har_j.json": hashlib.sha256(chemin.read_bytes()).hexdigest()}
    C.ecrire_texte(CHEMIN_MANIFESTE, C.texte_json({
        "description": "Empreinte SHA-256 du modèle HAR-J du test final (enregistré dans sorties/, ignoré par Git) ; "
                       "aucune prévision n'a été faite sur le test.", "modeles": empreintes}))
    return empreintes


def main() -> int:
    C.proteger_sortie()
    regles = R.charger_regles()
    try:
        empreintes = executer(regles)
    except G.ErreurTestAveugle as erreur:
        print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1
    print("HAR-J : modèles du test final enregistrés (" + ", ".join(empreintes) + ").")
    return 0


if __name__ == "__main__":
    sys.exit(main())
