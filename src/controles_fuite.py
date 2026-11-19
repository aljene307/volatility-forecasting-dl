"""Contrôles de fuite des réseaux sur les vraies données (développement seulement).

Règles : config/regles.toml, section evaluation.controles_fuite (précision du 2026-11-19, écrite avant ces contrôles).

1. Test de l'avenir modifié : sur le pli 5, toutes les bougies après la fin du jour J sont multipliées par 10 avec
   un bruit ; chaque réseau (combinaison retenue, graine 0 des plis, 2 époques) est entraîné sur les données
   d'origine puis sur les données modifiées. Les prévisions des origines <= J (validation interne comprise) doivent
   être identiques au bit près. Contrôle d'effet : des prévisions après J doivent, elles, changer.
2. Témoin « cible mélangée » : LSTM, combinaison retenue, graine 0 des plis, 5 plis ; les cibles de la fenêtre
   d'ajustement sont permutées au hasard (graine fixe) ; la validation interne et l'évaluation gardent les vraies
   cibles. Un réseau qui n'apprend rien d'utile doit faire moins bien que HAR-RV. Sinon : arrêt, fuite probable.

Aucune prévision n'est faite sur le test final (garde du test aveugle). Sortie : rapports/controles_fuite.json
(comptages et métriques, aucune valeur journalière).
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import baselines as B  # noqa: E402
import commun as C  # noqa: E402
import comparer as K  # noqa: E402
import entrainer as T  # noqa: E402
import evaluation as EV  # noqa: E402
import garde as G  # noqa: E402
import regles as R  # noqa: E402
import reprise as P  # noqa: E402
import variables as V  # noqa: E402

CHEMIN_JSON = C.DOSSIER_RAPPORTS / "controles_fuite.json"
COLONNES_BOUGIES = ("ouverture", "plus_haut", "plus_bas", "cloture", "volume_cotation")


class ArretFuite(Exception):
    pass


def modifier_apres(bougies: pd.DataFrame, j: dt.date, graine: int = 5) -> pd.DataFrame:
    """Toutes les bougies après la fin de J : prix et volumes × 10 avec un bruit (comme aux étapes 4 et 6)."""
    b = bougies.copy()
    apres = (b["date_ouverture"] >= pd.Timestamp(j + dt.timedelta(days=1), tz="UTC")).to_numpy()
    f = 10 * (1 + np.random.default_rng(graine).uniform(-0.5, 0.5, int(apres.sum())))
    for k in COLONNES_BOUGIES:
        b.loc[apres, k] = b.loc[apres, k].to_numpy() * f
    return b


def _bits(x) -> np.ndarray:
    return np.asarray(x, dtype="float64").view("<i8")


def comparer_avant_j(a: dict, b: dict, j: dt.date) -> dict:
    """Écarts au bit près des prévisions des origines <= J ; et nombre de prévisions après J qui ont changé."""
    if a["validation"]["date_cible"] != b["validation"]["date_cible"] or a["evaluation"]["date_cible"] != b["evaluation"]["date_cible"]:
        raise ArretFuite("Avenir modifié : les dates des exemples ont changé.")
    origine = np.array([dt.date.fromisoformat(x) - dt.timedelta(days=1) for x in a["evaluation"]["date_cible"]])
    avant = origine <= j
    va, vb = _bits(a["validation"]["prevision_log"]), _bits(b["validation"]["prevision_log"])
    ea, eb = _bits(a["evaluation"]["prevision_log"]), _bits(b["evaluation"]["prevision_log"])
    return {"previsions_comparees": int(len(va) + avant.sum()),
            "ecarts": int((va != vb).sum() + (ea[avant] != eb[avant]).sum()),
            "previsions_apres_j": int((~avant).sum()), "previsions_apres_j_modifiees": int((ea[~avant] != eb[~avant]).sum())}


def avenir_modifie(actif: str, bougies: pd.DataFrame, regles: dict, choix: dict, cle: str) -> dict:
    cf = regles["evaluation"]["controles_fuite"]
    pli = next(d for d in R.decoupages(regles) if d["nom"] == cf["avenir_modifie_decoupage"])
    j = cf["avenir_modifie_jour"]
    origine = T.donnees_reseaux(bougies, regles)
    modifie = T.donnees_reseaux(modifier_apres(bougies, j), regles)
    sortie = {}
    for m in K.RESEAUX:
        graine = P.graine_unite(T.id_pli(actif, m, pli["nom"], 0, cle))
        a, _, _ = T.entrainer_unite(m, choix[actif][m]["combinaison"], *origine, pli, graine, regles, avec_evaluation=True,
                                    epoques_max=cf["avenir_modifie_epoques"])
        b, _, _ = T.entrainer_unite(m, choix[actif][m]["combinaison"], *modifie, pli, graine, regles, avec_evaluation=True,
                                    epoques_max=cf["avenir_modifie_epoques"])
        sortie[m] = comparer_avant_j(a, b, j)
        print(f"  avenir modifié {actif} {m} : {sortie[m]['ecarts']} écart(s) sur {sortie[m]['previsions_comparees']} ; "
              f"{sortie[m]['previsions_apres_j_modifiees']} prévision(s) après J modifiée(s) sur {sortie[m]['previsions_apres_j']}")
    return {"decoupage": pli["nom"], "jour_j": str(j), "epoques": cf["avenir_modifie_epoques"], "modeles": sortie}


def cible_melangee(actif: str, exemples: pd.DataFrame, journalier: pd.DataFrame, table: pd.DataFrame, regles: dict,
                   choix: dict, cle: str) -> dict:
    cf = regles["evaluation"]["controles_fuite"]
    modele = cf["temoin_cible_melangee_modele"]
    lignes, par_pli = [], {}
    for numero, d in enumerate(R.decoupages(regles)[:-1]):
        ex = exemples.copy()
        m = B.masques(ex, d)
        vraies = ex.loc[m["ajustement"], "cible"].to_numpy()
        melangees = np.random.default_rng([cf["temoin_cible_melangee_graine"], numero]).permutation(vraies)
        ex.loc[m["ajustement"], "cible"] = melangees
        graine = P.graine_unite(T.id_pli(actif, modele, d["nom"], 0, cle))
        r, _, _ = T.entrainer_unite(modele, choix[actif][modele]["combinaison"], ex, journalier, d, graine, regles,
                                    avec_evaluation=True)
        cible_val = exemples.loc[m["validation"], "cible"].to_numpy()
        s2, biais = B.s2_et_biais(cible_val, np.array(r["validation"]["prevision_log"]))
        dates = [dt.date.fromisoformat(x) for x in r["evaluation"]["date_cible"]]
        G.refuser_si_test(dates, "témoin cible mélangée")
        bloc = table[table["pli"] == d["nom"]]
        if list(bloc["date_cible"]) != dates:
            raise ArretFuite(f"Témoin cible mélangée {actif} {d['nom']} : dates différentes de celles des baselines.")
        bloc = bloc[["date_cible", "pli", "cible", "HAR-RV", "Persistance"]].copy()
        bloc["temoin"] = EV.variance_depuis_log(r["evaluation"]["prevision_log"], s2)
        lignes.append(bloc)
        par_pli[d["nom"]] = {"part_des_cibles_deplacees": float(np.mean(melangees != vraies)), "epoques": r["epoques"],
                             "meilleure_epoque": r["meilleure_epoque"], "mse_log_validation": r["mse_log_validation"],
                             "moyenne_residus_log_validation": biais, "s2": s2,
                             "ecart_type_prevision_log_evaluation": float(np.std(r["evaluation"]["prevision_log"]))}
        print(f"  cible mélangée {actif} {d['nom']} : {r['epoques']} époques, MSE de validation {r['mse_log_validation']:.4f}")
    t = pd.concat(lignes, ignore_index=True)
    pertes = {k: B.pertes(t["cible"].to_numpy(), t[k].to_numpy()) for k in ("temoin", "HAR-RV", "Persistance")}
    reunis = {k: float(p["qlike"].mean()) for k, p in pertes.items()}
    moy_plis = {k: float(np.mean([B.pertes(g["cible"].to_numpy(), g[k].to_numpy())["qlike"].mean() for _, g in t.groupby("pli", sort=False)]))
                for k in pertes}
    for nom, g in t.groupby("pli", sort=False):
        par_pli[nom]["qlike_temoin"] = float(B.pertes(g["cible"].to_numpy(), g["temoin"].to_numpy())["qlike"].mean())
        par_pli[nom]["qlike_har_rv"] = float(B.pertes(g["cible"].to_numpy(), g["HAR-RV"].to_numpy())["qlike"].mean())
    return {"modele": modele, "graine_permutation": cf["temoin_cible_melangee_graine"], "jours": int(len(t)),
            "qlike_jours_reunis": reunis, "qlike_moyenne_des_plis": moy_plis,
            "gain_sur_har_rv": {"jours_reunis": (reunis["HAR-RV"] - reunis["temoin"]) / reunis["HAR-RV"],
                                "moyenne_des_plis": (moy_plis["HAR-RV"] - moy_plis["temoin"]) / moy_plis["HAR-RV"]},
            "diebold_mariano_contre_har_rv": EV.diebold_mariano(pertes["temoin"]["qlike"], pertes["HAR-RV"]["qlike"]),
            "par_pli": par_pli}


def verifier(rapport: dict) -> None:
    problemes = []
    for actif, r in rapport["actifs"].items():
        for m, x in r["avenir_modifie"]["modeles"].items():
            if x["ecarts"] != 0:
                problemes.append(f"{actif} {m} : {x['ecarts']} écart(s) avant J (avenir modifié)")
            if x["previsions_apres_j_modifiees"] == 0:
                problemes.append(f"{actif} {m} : aucune prévision après J n'a changé (la modification n'a eu aucun effet)")
        if r["cible_melangee"] is not None:
            g = r["cible_melangee"]["gain_sur_har_rv"]
            if g["jours_reunis"] >= 0 or g["moyenne_des_plis"] >= 0:
                problemes.append(f"{actif} : le LSTM à cible mélangée ne fait pas moins bien que HAR-RV (fuite probable)")
    if problemes:
        raise ArretFuite("ARRÊT : " + " ; ".join(problemes))


def executer(regles: dict) -> dict:
    C.verifier_secteur(contexte="contrôles de fuite")
    C.verifier_memoire_libre(regles)
    T.configurer_torch(regles)
    cle = T._cle_donnees(regles)
    choix = json.loads((K.DOSSIER_DL / "reglage.json").read_text(encoding="utf-8"))
    rapport = {"regles": {k: str(v) for k, v in regles["evaluation"]["controles_fuite"].items()},
               "depend_de": {"reglage_json_sha256": K._sha256(K.DOSSIER_DL / "reglage.json"),
                             "variables_empreinte_contenu": cle}, "actifs": {}}
    for actif in regles["donnees"]["actifs"]:
        debut = time.perf_counter()
        bougies = V.lire_bougies(C.DOSSIER_TRAITE / f"{actif}_5m.parquet")
        resultat = {"avenir_modifie": avenir_modifie(actif, bougies, regles, choix, cle), "cible_melangee": None}
        rapport["actifs"][actif] = resultat
        verifier({"actifs": {actif: resultat}})                       # arrêt immédiat si l'avenir modifié échoue
        exemples, journalier = T.donnees_reseaux(bougies, regles)
        table, _ = B.series_evaluation(K.calcul_baselines(actif, regles, cle), regles)
        resultat["cible_melangee"] = cible_melangee(actif, exemples, journalier, table, regles, choix, cle)
        verifier({"actifs": {actif: resultat}})
        print(f"{actif} : contrôles terminés en {C.nombre_fr(time.perf_counter() - debut, 1)} s")
    C.ecrire_texte(CHEMIN_JSON, C.texte_json(rapport))
    return rapport


def main() -> int:
    C.proteger_sortie()
    regles = R.charger_regles()
    try:
        rapport = executer(regles)
    except ArretFuite as arret:
        print(str(arret), file=sys.stderr)
        return 2
    except (G.ErreurTestAveugle, C.ErreurAlimentation, C.ErreurMemoire, K.ErreurComparaison) as erreur:
        print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1
    for actif, r in rapport["actifs"].items():
        g = r["cible_melangee"]["gain_sur_har_rv"]
        print(f"{actif} | avenir modifié : {sum(x['ecarts'] for x in r['avenir_modifie']['modeles'].values())} écart(s) | "
              f"cible mélangée : gain sur HAR-RV {C.nombre_fr(100 * g['moyenne_des_plis'], 1)} % (moyenne par pli), "
              f"{C.nombre_fr(100 * g['jours_reunis'], 1)} % (jours réunis)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
