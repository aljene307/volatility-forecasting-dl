"""Comparaison de tous les modèles sur le développement (5 plis annuels) : baselines et deep learning.

Règles : config/regles.toml (sections evaluation et crises) ; docs/REGLES.md, sections 8, 12 et 13.

- Aucun entraînement : le script lit les unités déjà calculées (baselines : sorties/reprise/baselines ;
  deep learning : sorties/deep_learning/unites), dossiers ignorés par Git.
- Prévision d'un réseau = moyenne des log de ses 3 graines ; s² mesuré sur la validation interne pour
  cette prévision moyenne ; métriques de chaque graine avec son propre s².
- Diebold-Mariano contre HAR-RV (plis réunis) ; p-valeurs brutes et ajustées par Holm sur les 7
  comparaisons de chaque actif ; « significatif » selon la p-valeur ajustée.
- Classement de tous les modèles selon les deux définitions du QLIKE moyen ; la moyenne des QLIKE
  moyens par pli s'applique (précision du 2026-11-16).
- Alerte : si un réseau bat HAR-RV de plus de 20 % en QLIKE moyen, arrêt AVANT d'écrire quoi que ce soit.
- Le test final reste fermé : chaque série passe par la garde du test aveugle.

Sorties commitées : rapports/comparaison_modeles.json, rapports/modeles_deep_learning.json (empreintes des
poids, pas les poids), docs/RESULTATS_DL.md (généré), figures/figure_5_deep_learning_{actif}.png.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import baselines as B  # noqa: E402
import commun as C  # noqa: E402
import entrainer as T  # noqa: E402
import evaluation as EV  # noqa: E402
import garde as G  # noqa: E402
import regles as R  # noqa: E402
import reprise as P  # noqa: E402

VERSION = "comparaison-1"
DOSSIER_DL = C.RACINE / "sorties" / "deep_learning"
CHEMIN_JSON = C.DOSSIER_RAPPORTS / "comparaison_modeles.json"
CHEMIN_MANIFESTE = C.DOSSIER_RAPPORTS / "modeles_deep_learning.json"
CHEMIN_MD = C.RACINE / "docs" / "RESULTATS_DL.md"
BASELINES_SELECTIONNABLES = ["HAR-RV", "GARCH(1,1)", "XGBoost"]
RESEAUX = list(T.MODELES)
SELECTIONNABLES = BASELINES_SELECTIONNABLES + RESEAUX
REGLES_MODELES = ["XGBoost"] + RESEAUX                 # modèles réglés, avec 3 graines
TOUS = ["Persistance"] + SELECTIONNABLES
TOLERANCE = 1e-9


class ErreurComparaison(Exception):
    pass


class AlerteFuite(Exception):
    pass


# --- Lecture des unités -------------------------------------------------------------------------

def _unite(dossier: Path, identifiant: str) -> dict:
    u = P.lire_unite(dossier, identifiant)
    if u is None:
        raise ErreurComparaison(f"Unité absente ou abîmée : {identifiant}")
    return u


def calcul_baselines(actif: str, regles: dict, cle: str) -> dict:
    """Résultats des baselines, relus dans leurs unités de reprise (aucun recalcul)."""
    return {"decoupages": [{"decoupage": d, "sortie": _unite(B.DOSSIER_REPRISE, f"{B.VERSION}|{actif}|baselines|{d['nom']}|{cle}")}
                           for d in R.decoupages(regles)]}


def unites_reseau(actif: str, modele: str, decoupage: dict, regles: dict, cle: str, dossier: Path = DOSSIER_DL) -> list[dict]:
    return [_unite(dossier / "unites", T.id_pli(actif, modele, decoupage["nom"], g, cle))
            for g in regles["modeles"]["graines_deep_learning"]]


def ajouter_reseaux(table: pd.DataFrame, calcul: dict, actif: str, regles: dict, cle: str,
                    dossier: Path = DOSSIER_DL) -> tuple[pd.DataFrame, dict]:
    """Ajoute à la table des plis réunis la variance prévue de chaque réseau (moyenne des graines) et de chaque graine.

    Les dates de validation et d'évaluation des réseaux doivent être exactement celles des baselines."""
    table = table.copy()
    controles = {m: [] for m in RESEAUX}
    for bloc in calcul["decoupages"]:
        d, s = bloc["decoupage"], bloc["sortie"]
        cible_val = np.array(s["validation"]["cible"])
        avec_evaluation = "evaluation" in s
        masque = (table["pli"] == d["nom"]).to_numpy()
        if avec_evaluation:
            dates = [dt.date.fromisoformat(x) for x in s["evaluation"]["date_cible"]]
            G.refuser_si_test(dates, f"évaluation du deep learning, {d['nom']}")
            if list(table.loc[masque, "date_cible"]) != dates:
                raise ErreurComparaison(f"{actif} {d['nom']} : dates de la table différentes de celles des baselines.")
        for m in RESEAUX:
            unites = unites_reseau(actif, m, d, regles, cle, dossier)
            for u in unites:
                if u["validation"]["date_cible"] != s["validation"]["date_cible"]:
                    raise ErreurComparaison(f"{actif} {m} {d['nom']} : dates de validation différentes de celles des baselines.")
                if avec_evaluation and u["evaluation"]["date_cible"] != s["evaluation"]["date_cible"]:
                    raise ErreurComparaison(f"{actif} {m} {d['nom']} : dates d'évaluation différentes de celles des baselines.")
                if not avec_evaluation and "evaluation" in u:
                    raise ErreurComparaison(f"{actif} {m} {d['nom']} : le modèle du test final ne doit avoir aucune prévision d'évaluation.")
            val = np.array([u["validation"]["prevision_log"] for u in unites])
            s2, biais = B.s2_et_biais(cible_val, val.mean(axis=0))
            controles[m].append({
                "decoupage": d["nom"], "moyenne_residus_log": biais, "s2": s2,
                "mse_log_validation_par_graine": [u["mse_log_validation"] for u in unites],
                "epoques_par_graine": [u["epoques"] for u in unites],
                "meilleure_epoque_par_graine": [u["meilleure_epoque"] for u in unites],
                "valeurs_finies": bool(np.isfinite(val).all())})
            if not np.isfinite(val).all():
                raise ErreurComparaison(f"{actif} {m} {d['nom']} : prévision de validation non finie.")
            if not avec_evaluation:
                continue
            ev = np.array([u["evaluation"]["prevision_log"] for u in unites])
            if not np.isfinite(ev).all():
                raise ErreurComparaison(f"{actif} {m} {d['nom']} : prévision d'évaluation non finie.")
            table.loc[masque, m] = EV.variance_depuis_log(ev.mean(axis=0), s2)
            for k, (pv, pe) in enumerate(zip(val, ev)):
                s2_g, _ = B.s2_et_biais(cible_val, pv)
                table.loc[masque, f"{m} graine {k}"] = EV.variance_depuis_log(pe, s2_g)
    return table, controles


# --- Résultats --------------------------------------------------------------------------------

def _stat(valeurs: list[float]) -> dict:
    return {"valeurs": valeurs, "moyenne": float(np.mean(valeurs)), "ecart_type": float(np.std(valeurs, ddof=1))}


def resultats_actif(table: pd.DataFrame, regles: dict) -> dict:
    G.refuser_si_test(table["date_cible"], "comparaison des modèles")
    cible = table["cible"].to_numpy()
    pertes_m = {m: B.pertes(cible, table[m].to_numpy()) for m in TOUS}
    sortie = {"modeles": {}}
    for m in TOUS:
        res = {"reunis": B.resume_pertes(pertes_m[m], regles), "par_pli": {}, "crises": {}}
        for pli, groupe in table.groupby("pli", sort=False):
            res["par_pli"][pli] = B.resume_pertes(B.pertes(groupe["cible"].to_numpy(), groupe[m].to_numpy()))
        for nom, c in regles["crises"].items():
            dedans = ((table["date_cible"] >= c["debut"]) & (table["date_cible"] <= c["fin"])).to_numpy()
            res["crises"][nom] = B.resume_pertes({k: v[dedans] for k, v in pertes_m[m].items()})
        res["qlike_moyenne_des_plis"] = float(np.mean([v["qlike"] for v in res["par_pli"].values()]))
        sortie["modeles"][m] = res
    for m in REGLES_MODELES:
        colonnes = [k for k in table.columns if k.startswith(f"{m} graine ")]
        par_graine = [B.resume_pertes(B.pertes(cible, table[k].to_numpy())) for k in colonnes]
        sortie["modeles"][m]["par_graine"] = {mesure: _stat([g[mesure] for g in par_graine]) for mesure in ("qlike", "rmse", "mae")}
    # Diebold-Mariano contre HAR-RV, p-valeurs brutes et ajustées par Holm (famille : les 7 comparaisons de l'actif)
    ref = pertes_m["HAR-RV"]["qlike"]
    dm = {m: EV.diebold_mariano(pertes_m[m]["qlike"], ref) for m in SELECTIONNABLES if m != "HAR-RV"}
    ajustees = EV.holm({m: t["p_valeur"] for m, t in dm.items()})
    seuil = regles["evaluation"]["diebold_mariano"]["seuil"]
    for m, t in dm.items():
        t["p_valeur_holm"] = ajustees[m]
        t["significatif_brut"] = t["p_valeur"] < seuil
        t["significatif_holm"] = ajustees[m] < seuil
    sortie["diebold_mariano"] = dm
    sortie["diebold_mariano_descriptif"] = {"HAR-RV contre persistance": EV.diebold_mariano(ref, pertes_m["Persistance"]["qlike"])}
    # Gain relatif sur HAR-RV (positif : le modèle fait mieux), selon les deux définitions du QLIKE moyen
    h = sortie["modeles"]["HAR-RV"]
    sortie["gain_relatif_qlike"] = {m: {
        "jours_reunis": (h["reunis"]["qlike"] - sortie["modeles"][m]["reunis"]["qlike"]) / h["reunis"]["qlike"],
        "moyenne_des_plis": (h["qlike_moyenne_des_plis"] - sortie["modeles"][m]["qlike_moyenne_des_plis"]) / h["qlike_moyenne_des_plis"]}
        for m in SELECTIONNABLES}
    sortie["robustesse"] = robustesse(table, sortie)
    jours_reunis = sorted(SELECTIONNABLES, key=lambda m: sortie["modeles"][m]["reunis"]["qlike"])
    par_pli = sorted(SELECTIONNABLES, key=lambda m: sortie["modeles"][m]["qlike_moyenne_des_plis"])
    sortie["classement"] = {"jours_reunis": jours_reunis, "moyenne_des_plis": par_pli, "identiques": jours_reunis == par_pli,
                            "applique": par_pli, "modele_retenu": par_pli[0],
                            "meilleur_reseau": next(m for m in par_pli if m in RESEAUX)}
    return sortie


def robustesse(table: pd.DataFrame, sortie: dict) -> dict:
    """Analyses descriptives (sans effet sur le classement ni la sélection), gain sur HAR-RV en moyenne des QLIKE par pli :
    - chaque graine SEULE (avec son propre s²), comparée à la moyenne des graines : part de l'effet d'ensemble ;
    - pli par pli, pour chaque modèle comparé à HAR-RV."""
    har = sortie["modeles"]["HAR-RV"]
    h = har["qlike_moyenne_des_plis"]
    par_graine = {}
    for m in REGLES_MODELES:
        colonnes = [k for k in table.columns if k.startswith(f"{m} graine ")]
        gains = [(h - float(np.mean([B.pertes(g["cible"].to_numpy(), g[k].to_numpy())["qlike"].mean()
                                     for _, g in table.groupby("pli", sort=False)]))) / h for k in colonnes]
        ensemble = sortie["gain_relatif_qlike"][m]["moyenne_des_plis"]
        par_graine[m] = {"graines": gains, "moyenne_des_graines_seules": float(np.mean(gains)), "minimum": float(min(gains)),
                         "gain_de_la_moyenne_des_graines": ensemble, "effet_ensemble": ensemble - float(np.mean(gains))}
    par_pli = {m: {p: (har["par_pli"][p]["qlike"] - v["qlike"]) / har["par_pli"][p]["qlike"]
                   for p, v in sortie["modeles"][m]["par_pli"].items()} for m in SELECTIONNABLES if m != "HAR-RV"}
    return {"definition": "gain sur HAR-RV, moyenne des QLIKE moyens par pli ; pli par pli : QLIKE moyen du pli",
            "gain_par_graine": par_graine, "gain_par_pli": par_pli}


def verifier_alerte(resultats: dict, regles: dict) -> None:
    """Arrêt si un réseau bat HAR-RV de plus que le seuil des règles en QLIKE moyen (l'une ou l'autre définition)."""
    seuil = regles["evaluation"]["controles_fuite"]["seuil_alerte_gain_qlike"]
    trop = [(a, m, v) for a, r in resultats.items() for m in RESEAUX for v in r["gain_relatif_qlike"][m].values() if v > seuil]
    if trop:
        raise AlerteFuite(f"ARRÊT : gain sur HAR-RV supérieur à {C.nombre_fr(100 * seuil, 0)} % en QLIKE moyen, chercher une "
                          "fuite avant tout : " + "; ".join(f"{a} {m} {100 * v:.1f} %" for a, m, v in trop))


def verifier_baselines(res: dict, publie: dict) -> float:
    """Écart maximal entre les métriques des baselines recalculées ici et celles de rapports/baselines.json."""
    ecarts = []
    for m in ("Persistance", "HAR-RV", "GARCH(1,1)", "XGBoost"):
        a, b = res["modeles"][m], publie["modeles"][m]
        ecarts += [abs(a["reunis"][k] - b["reunis"][k]) for k in ("qlike", "rmse", "mae")]
        ecarts += [abs(a["reunis"]["qlike_intervalle"][k] - b["reunis"]["qlike_intervalle"][k]) for k in ("bas", "haut")]
        ecarts += [abs(a["par_pli"][p]["qlike"] - b["par_pli"][p]["qlike"]) for p in b["par_pli"]]
        ecarts += [abs(a["crises"][c]["qlike"] - b["crises"][c]["qlike"]) for c in b["crises"]]
    for m in ("GARCH(1,1)", "XGBoost"):
        ecarts += [abs(res["diebold_mariano"][m][k] - publie["diebold_mariano"][m][k]) for k in ("statistique", "p_valeur")]
    ecart = max(ecarts)
    if ecart > TOLERANCE:
        raise ErreurComparaison(f"Les baselines recalculées diffèrent de rapports/baselines.json ({ecart}).")
    return ecart


# --- Manifeste des poids et temps de la phase « plis » --------------------------------------------

def _sha256(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def manifeste_poids(regles: dict, cle: str, dossier: Path = DOSSIER_DL) -> dict:
    """Empreintes des poids (recalculées et comparées à celles enregistrées dans chaque unité) et des normalisations."""
    poids = {}
    for actif in regles["donnees"]["actifs"]:
        for m in RESEAUX:
            for d in R.decoupages(regles):
                for u in unites_reseau(actif, m, d, regles, cle, dossier):
                    empreinte = _sha256(dossier / u["poids"])
                    if empreinte != u["poids_sha256"]:
                        raise ErreurComparaison(f"Poids modifiés depuis l'entraînement : {u['poids']}")
                    poids[u["poids"]] = empreinte
    normalisations = {f.relative_to(dossier).as_posix(): _sha256(f) for f in sorted((dossier / "normalisation").rglob("*.json"))}
    return {"description": "Empreintes SHA-256 des poids des réseaux (5 plis et test final, 3 graines) et des normalisations, "
                           "enregistrés dans sorties/deep_learning/ (ignoré par Git). Les modèles du test final n'ont fait "
                           "aucune prévision sur le test.",
            "reglage_json_sha256": _sha256(dossier / "reglage.json"), "poids": dict(sorted(poids.items())),
            "normalisations": normalisations}


def temps_plis(dossier: Path = DOSSIER_DL) -> dict:
    j = json.loads((dossier / "journal.json").read_text(encoding="utf-8"))
    if j["phase"] != "plis" or j["statut"] != "terminé":
        raise ErreurComparaison(f"La phase « plis » n'est pas terminée (journal : {j['phase']}, {j['statut']}).")
    return {"reel_s": j["cumul_reel_s"], "estime_s": j["cumul_estime_s"], "rapport": j["rapport_reel_sur_estime"],
            "unites": j["unites_terminees"],
            "par_modele": {m: {k: v[k] for k in ("temps_reel_s", "temps_estime_s", "epoques", "temps_par_epoque_reel_s",
                                                 "temps_par_epoque_estime_s")} for m, v in j["par_modele"].items()}}


# --- Figure -----------------------------------------------------------------------------------

def figure(actif: str, table: pd.DataFrame, meilleur: str, regles: dict, chemin: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    import exploration as X
    G.refuser_si_test(table["date_cible"], "figure du deep learning")
    a = math.sqrt(regles["cible"]["annualisation_jours"])
    dates = pd.to_datetime([str(d) for d in table["date_cible"]])
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(dates, np.exp(table["cible"]) * a, color="#999999", linewidth=0.6, label="RV réalisée")
    ax.plot(dates, np.sqrt(table["HAR-RV"]) * a, color=X.COULEURS[actif], linewidth=1.0, label="Prévision HAR-RV")
    ax.plot(dates, np.sqrt(table[meilleur]) * a, color="#7C3AED", linewidth=1.0, alpha=0.85,
            label=f"Prévision {meilleur} (meilleur réseau)")
    for nom, c in regles["crises"].items():
        ax.axvspan(pd.Timestamp(c["debut"]), pd.Timestamp(c["fin"]) + pd.Timedelta(days=1), color="#999999", alpha=0.2,
                   label="Crises" if nom == next(iter(regles["crises"])) else None)
    ax.yaxis.set_major_formatter(X.FORMAT_POURCENT)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_ylabel("Volatilité annualisée")
    ax.set_xlabel("Date de la cible (5 plis annuels, développement)")
    ax.set_title(f"{X.NOMS[actif]} : RV réalisée et prévisions à un jour de HAR-RV et de {meilleur}")
    ax.legend(loc="upper right")
    ax.grid(alpha=0.3)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    X._finir(fig, chemin)


# --- Rapport Markdown généré ----------------------------------------------------------------------

def _n(x: float, d: int = 3) -> str:
    return C.nombre_fr(x, d).replace("-", "−")


def _p(p: float) -> str:
    return _n(p, 4) if p >= 0.0001 else "< 0,0001"


def _liste(noms: list[str]) -> str:
    return noms[0] if len(noms) == 1 else ", ".join(noms[:-1]) + " et " + noms[-1]


def rapport_markdown(rapport: dict, regles: dict) -> str:
    lignes = ["# Comparaison de tous les modèles (développement, 5 plis annuels)", "",
              "Fichier généré par `src/comparer.py` à partir de `rapports/comparaison_modeles.json` : ne pas le modifier à la main.", "",
              f"- Plis évalués (dates de cible) : du {rapport['plis'][0][0]} au {rapport['plis'][-1][1]}. Le test final est fermé : "
              "aucune prévision n'y a été faite.",
              "- QLIKE sur la variance (forme de Patton), RMSE et MAE sur RV ; intervalles à 95 % par bootstrap à blocs mobiles.",
              "- Modèles réglés (XGBoost et réseaux) : prévision = moyenne des log de leurs 3 graines, avec s² mesuré sur la validation "
              "interne pour cette moyenne (petit ensemble : léger avantage écrit dans les règles).",
              "- La persistance est une référence descriptive : hors de la sélection et des tests principaux.",
              "- Gain sur HAR-RV : (QLIKE de HAR-RV − QLIKE du modèle) / QLIKE de HAR-RV ; positif quand le modèle fait mieux.", ""]
    for actif, res in rapport["actifs"].items():
        lignes += [f"## {actif}", "", "### Tableau de comparaison (plis réunis)", "",
                   "| Modèle | QLIKE [IC 95 %] | QLIKE moyen par pli | Gain sur HAR-RV (moyenne par pli) | RMSE [IC 95 %] | MAE [IC 95 %] |",
                   "|---|---|---:|---:|---|---|"]
        for m in TOUS:
            r = res["modeles"][m]["reunis"]
            g = res["gain_relatif_qlike"].get(m)
            lignes.append(f"| {m}{' (descriptive)' if m == 'Persistance' else ''} | {_n(r['qlike'])} [{_n(r['qlike_intervalle']['bas'])} ; "
                          f"{_n(r['qlike_intervalle']['haut'])}] | {_n(res['modeles'][m]['qlike_moyenne_des_plis'])} | "
                          f"{'—' if g is None else _n(100 * g['moyenne_des_plis'], 1) + ' %'} | "
                          f"{_n(r['rmse'], 4)} [{_n(r['rmse_intervalle']['bas'], 4)} ; {_n(r['rmse_intervalle']['haut'], 4)}] | "
                          f"{_n(r['mae'], 4)} [{_n(r['mae_intervalle']['bas'], 4)} ; {_n(r['mae_intervalle']['haut'], 4)}] |")
        lignes += ["", "### Modèles réglés : métriques de chaque graine (chacune avec son propre s²)", "",
                   "| Modèle | QLIKE moyen des graines (écart-type) | QLIKE de la moyenne des graines | RMSE moyen (écart-type) | MAE moyen (écart-type) |",
                   "|---|---|---:|---|---|"]
        for m in REGLES_MODELES:
            pg = res["modeles"][m]["par_graine"]
            lignes.append(f"| {m} | {_n(pg['qlike']['moyenne'])} ({_n(pg['qlike']['ecart_type'], 4)}) | "
                          f"{_n(res['modeles'][m]['reunis']['qlike'])} | {_n(pg['rmse']['moyenne'], 4)} ({_n(pg['rmse']['ecart_type'], 4)}) | "
                          f"{_n(pg['mae']['moyenne'], 4)} ({_n(pg['mae']['ecart_type'], 4)}) |")
        rb = res["robustesse"]
        annees = {p: a for p, a in zip(res["modeles"]["HAR-RV"]["par_pli"], [x[0][:4] for x in rapport["plis"]])}
        lignes += ["", "### Robustesse (descriptif) : gain sur HAR-RV de chaque graine seule", "",
                   "Sans effet sur le classement ni la sélection. Gain en moyenne des QLIKE moyens par pli ; chaque graine avec son propre s². "
                   "Effet d'ensemble = gain de la moyenne des 3 graines − moyenne des gains des graines seules (en points de pourcentage).", "",
                   "| Modèle | Graine 0 | Graine 1 | Graine 2 | Moyenne des graines seules | Moyenne des 3 graines (prévision retenue) | Effet d'ensemble |",
                   "|---|---:|---:|---:|---:|---:|---:|"]
        for m in REGLES_MODELES:
            g = rb["gain_par_graine"][m]
            lignes.append(f"| {m} | " + " | ".join(_n(100 * x, 1) + " %" for x in g["graines"])
                          + f" | {_n(100 * g['moyenne_des_graines_seules'], 1)} % | {_n(100 * g['gain_de_la_moyenne_des_graines'], 1)} % | "
                          f"{_n(100 * g['effet_ensemble'], 1)} |")
        lignes += ["", "### Robustesse (descriptif) : gain sur HAR-RV pli par pli", "",
                   "| Modèle | " + " | ".join(f"{p} ({annees[p]})" for p in annees) + " |", "|---|" + "---:|" * len(annees)]
        for m in [x for x in SELECTIONNABLES if x != "HAR-RV"]:
            lignes.append(f"| {m} | " + " | ".join(_n(100 * rb["gain_par_pli"][m][p], 1) + " %" for p in annees) + " |")
        lignes += ["", "### Diebold-Mariano contre HAR-RV (plis réunis, QLIKE)", "",
                   "Famille de Holm : les 7 comparaisons ci-dessous (test descriptif exclu). « Significatif » s'appuie sur la p-valeur ajustée.", "",
                   "| Modèle | Différence moyenne | Statistique (HLN) | p-valeur brute | p-valeur ajustée (Holm) | Sens | Significatif à 5 % (ajustée) |",
                   "|---|---:|---:|---:|---:|---|---|"]
        for m, t in res["diebold_mariano"].items():
            lignes.append(f"| {m} | {_n(t['moyenne_difference'], 4)} | {_n(t['statistique'], 2)} | {_p(t['p_valeur'])} | "
                          f"{_p(t['p_valeur_holm'])} | {t['sens']} | {'oui' if t['significatif_holm'] else 'non'} |")
        t = res["diebold_mariano_descriptif"]["HAR-RV contre persistance"]
        lignes += ["", f"Test descriptif HAR-RV contre persistance (hors famille) : différence {_n(t['moyenne_difference'], 4)}, "
                   f"p-valeur {_p(t['p_valeur'])}, {t['sens']} (le « modèle » est HAR-RV). Jours : {C.nombre_fr(t['jours'])} ; "
                   f"retards HAC : {t['retards_hac']}.", "",
                   "### QLIKE par pli", "", "| Modèle | " + " | ".join(res["modeles"]["HAR-RV"]["par_pli"]) + " |",
                   "|---|" + "---:|" * len(res["modeles"]["HAR-RV"]["par_pli"])]
        for m in TOUS:
            lignes.append(f"| {m} | " + " | ".join(_n(v["qlike"]) for v in res["modeles"][m]["par_pli"].values()) + " |")
        lignes += ["", "### Crises (QLIKE, descriptif, sans test)", "", "| Modèle | " + " | ".join(regles["crises"]) + " |",
                   "|---|" + "---:|" * len(regles["crises"])]
        for m in TOUS:
            lignes.append(f"| {m} | " + " | ".join(_n(res["modeles"][m]["crises"][c]["qlike"]) for c in regles["crises"]) + " |")
        cl = res["classement"]
        lignes += ["", "### Classement (persistance exclue)", "", "| Définition | Classement |", "|---|---|",
                   f"| QLIKE moyen sur tous les jours évalués réunis | {' < '.join(cl['jours_reunis'])} |",
                   f"| Moyenne des QLIKE moyens par pli (définition appliquée) | {' < '.join(cl['moyenne_des_plis'])} |", "",
                   ("Les deux définitions donnent le même classement." if cl["identiques"] else
                    "Les deux définitions donnent des classements différents : la moyenne des QLIKE moyens par pli s'applique."),
                   f"**Modèle retenu par la règle de sélection : {cl['modele_retenu']}.** Meilleur réseau : {cl['meilleur_reseau']}.", "",
                   "### Vérification de l'exception 2 : moyenne des résidus en log sur la validation interne", "",
                   "| Modèle | " + " | ".join(x["decoupage"] for x in res["controles"]["XGBoost"]) + " |",
                   "|---|" + "---:|" * len(res["controles"]["XGBoost"])]
        for m in REGLES_MODELES:
            lignes.append(f"| {m} | " + " | ".join(_n(x["moyenne_residus_log"]) for x in res["controles"][m]) + " |")
        lignes += ["", "Une moyenne négative signifie que le modèle prévoit trop haut sur la validation interne.", "",
                   f"Figure : `figures/figure_5_deep_learning_{actif}.png`.", ""]
    tp = rapport["temps_phase_plis"]
    lignes += ["## Temps de la phase « plis »", "",
               f"Temps de calcul cumulé : {_n(tp['reel_s'] / 3600, 2)} h, contre {_n(tp['estime_s'] / 3600, 2)} h estimées "
               f"(rapport {_n(tp['rapport'], 3)} ; seuil d'arrêt de la règle de suivi : 1,5).", "",
               "| Modèle | Réel (min) | Estimé (min) | Époques | Par époque réel / estimé (s) |", "|---|---:|---:|---:|---|"]
    for m, v in tp["par_modele"].items():
        lignes.append(f"| {m} | {_n(v['temps_reel_s'] / 60, 1)} | {_n(v['temps_estime_s'] / 60, 1)} | {C.nombre_fr(v['epoques'])} | "
                      f"{_n(v['temps_par_epoque_reel_s'], 2)} / {_n(v['temps_par_epoque_estime_s'], 2)} |")
    lignes += ["", "Empreintes des poids : `rapports/modeles_deep_learning.json` (les poids eux-mêmes ne sont pas dans le dépôt).", ""]
    lignes += lecture_des_resultats(rapport, regles)
    return "\n".join(lignes) + "\n"


def lecture_des_resultats(rapport: dict, regles: dict) -> list[str]:
    """Phrases d'interprétation, chacune conditionnée par les valeurs du JSON."""
    noms_crises = {"covid": "le Covid", "terra_luna": "Terra-Luna", "ftx": "FTX"}
    lignes = ["## Lecture des résultats", "",
              "Chaque phrase ci-dessous est générée à partir des valeurs de `rapports/comparaison_modeles.json`.", ""]
    for actif, res in rapport["actifs"].items():
        nom = actif.replace("USDT", "")
        cl, dm, mod = res["classement"], res["diebold_mariano"], res["modeles"]
        retenu = cl["modele_retenu"]
        lignes.append(f"- {nom} : la règle de sélection retient {retenu}"
                      + (" (un réseau)." if retenu in RESEAUX else " (une baseline : aucun réseau ne fait mieux en QLIKE moyen par pli)."))
        mieux_sig = [m for m in RESEAUX if dm[m]["significatif_holm"] and dm[m]["moyenne_difference"] < 0]
        moins_sig = [m for m in RESEAUX if dm[m]["significatif_holm"] and dm[m]["moyenne_difference"] > 0]
        perdus = [m for m in RESEAUX if dm[m]["significatif_brut"] and not dm[m]["significatif_holm"]]
        if mieux_sig:
            lignes.append(f"- {nom} : {_liste(mieux_sig)} {'fait' if len(mieux_sig) == 1 else 'font'} significativement mieux que "
                          "HAR-RV en QLIKE, après ajustement de Holm.")
        if moins_sig:
            lignes.append(f"- {nom} : {_liste(moins_sig)} {'fait' if len(moins_sig) == 1 else 'font'} significativement moins bien "
                          "que HAR-RV en QLIKE, après ajustement de Holm.")
        autres = [m for m in RESEAUX if m not in mieux_sig + moins_sig]
        if autres:
            un = len(autres) == 1
            lignes.append(f"- {nom} : pour {_liste(autres)}, l'écart avec HAR-RV n'est pas significatif après ajustement de Holm : "
                          f"on ne peut pas dire que {'ce réseau fait' if un else 'ces réseaux font'} mieux ou moins bien que HAR-RV.")
        if perdus:
            lignes.append(f"- {nom} : {_liste(perdus)} serai{'t' if len(perdus) == 1 else 'ent'} significatif{'' if len(perdus) == 1 else 's'} "
                          "avec la p-valeur brute, mais plus après ajustement : c'est exactement le risque des tests multiples.")
        b = cl["meilleur_reseau"]
        qb, qh, qx = mod[b]["qlike_moyenne_des_plis"], mod["HAR-RV"]["qlike_moyenne_des_plis"], mod["XGBoost"]["qlike_moyenne_des_plis"]
        lignes.append(f"- {nom} : le meilleur réseau, {b}, a un QLIKE moyen par pli {'plus faible' if qb < qh else 'plus élevé'} que HAR-RV "
                      f"et {'plus faible' if qb < qx else 'plus élevé'} qu'XGBoost.")
        ecart = abs(mod[b]["reunis"]["qlike"] - mod["HAR-RV"]["reunis"]["qlike"])
        if mod[b]["par_graine"]["qlike"]["ecart_type"] > ecart:
            lignes.append(f"- {nom} : l'écart-type du QLIKE entre les graines de {b} est plus grand que son écart avec HAR-RV : "
                          "le hasard de l'entraînement pèse autant que la différence entre les modèles.")
        ensemble = [m for m in RESEAUX if mod[m]["reunis"]["qlike"] < mod[m]["par_graine"]["qlike"]["moyenne"]]
        if ensemble:
            lignes.append(f"- {nom} : pour {_liste(ensemble)}, la moyenne des 3 graines a un QLIKE plus faible que la moyenne des QLIKE "
                          "des graines : c'est l'effet de petit ensemble annoncé dans les règles, qui avantage les modèles réglés par "
                          "rapport à HAR-RV et GARCH.")
        rb = res["robustesse"]
        seules = [m for m in RESEAUX if rb["gain_par_graine"][m]["minimum"] > 0]
        pas_seules = [m for m in RESEAUX if m not in seules]
        if seules:
            lignes.append(f"- {nom} : pour {_liste(seules)}, chaque graine seule bat déjà HAR-RV : le gain ne vient pas seulement "
                          "de la moyenne des graines (robustesse, descriptif).")
        if pas_seules:
            lignes.append(f"- {nom} : pour {_liste(pas_seules)}, au moins une graine seule ne bat pas HAR-RV : une partie du gain "
                          "vient de la moyenne des graines (robustesse, descriptif).")
        plus_grand = max(RESEAUX, key=lambda m: rb["gain_par_graine"][m]["effet_ensemble"])
        lignes.append(f"- {nom} : l'effet d'ensemble le plus grand est celui de {plus_grand} "
                      f"({_n(100 * rb['gain_par_graine'][plus_grand]['effet_ensemble'], 1)} points de gain sur HAR-RV).")
        annees = {p: a for p, a in zip(mod["HAR-RV"]["par_pli"], [x[0][:4] for x in rapport["plis"]])}
        reguliers = [m for m in RESEAUX if all(v > 0 for v in rb["gain_par_pli"][m].values())]
        if reguliers:
            lignes.append(f"- {nom} : le gain de {_liste(reguliers)} sur HAR-RV est régulier : positif chaque année de 2020 à 2024 "
                          "(robustesse, descriptif).")
        profils = {}
        for m in RESEAUX:
            if m in reguliers:
                continue
            g = rb["gain_par_pli"][m]
            cle_profil = (tuple(annees[p] for p, v in g.items() if v > 0), tuple(annees[p] for p, v in g.items() if v <= 0))
            profils.setdefault(cle_profil, []).append(m)
        for (positifs, negatifs), modeles in profils.items():
            lignes.append(f"- {nom} : le gain de {_liste(modeles)} sur HAR-RV n'est pas régulier (concentré sur certaines années) : "
                          f"positif en {_liste(list(positifs)) if positifs else 'aucune année'}, négatif ou nul en "
                          f"{_liste(list(negatifs))} (robustesse, descriptif).")
        extremes = {m: (annees[max(rb["gain_par_pli"][m], key=rb["gain_par_pli"][m].get)],
                        annees[min(rb["gain_par_pli"][m], key=rb["gain_par_pli"][m].get)]) for m in RESEAUX}
        if len(set(extremes.values())) == 1:
            haut, bas = next(iter(extremes.values()))
            lignes.append(f"- {nom} : pour les 5 réseaux, le plus grand gain annuel sur HAR-RV est en {haut} et le plus petit en "
                          f"{bas} (robustesse, descriptif)."
                          + (f" XGBoost a aussi son plus grand gain en {haut}. Explication possible, non démontrée : HAR-RV "
                             "est moins bon cette année-là, et l'écart ne tient pas seulement aux réseaux."
                             if annees[max(rb["gain_par_pli"]["XGBoost"], key=rb["gain_par_pli"]["XGBoost"].get)] == haut else ""))
        q, r = mod[b]["reunis"], mod["HAR-RV"]["reunis"]
        if (q["qlike"] < r["qlike"]) != (q["rmse"] < r["rmse"]):
            lignes.append(f"- {nom} : {b} est {'meilleur' if q['qlike'] < r['qlike'] else 'moins bon'} que HAR-RV en QLIKE mais "
                          f"{'moins bon' if q['qlike'] < r['qlike'] else 'meilleur'} en RMSE : QLIKE punit surtout une variance prévue "
                          "trop basse, en relatif ; RMSE punit les grandes erreurs en niveau, donc surtout les jours très agités.")
        for c in regles["crises"]:
            meilleur_crise = min(SELECTIONNABLES, key=lambda m: mod[m]["crises"][c]["qlike"])
            lignes.append(f"- {nom} : pendant {noms_crises.get(c, c)}, le plus petit QLIKE (descriptif, sans test) est celui de "
                          f"{meilleur_crise}" + (" ; la persistance fait encore mieux." if mod["Persistance"]["crises"][c]["qlike"]
                                                  < mod[meilleur_crise]["crises"][c]["qlike"] else "."))
        biais = [m for m in RESEAUX if any(abs(x["moyenne_residus_log"]) > 0.1 for x in res["controles"][m])]
        if biais:
            lignes.append(f"- {nom} : {_liste(biais)} {'a' if len(biais) == 1 else 'ont'} au moins une validation interne où la moyenne "
                          "des résidus en log dépasse 0,1 en valeur absolue : la correction s² y est mesurée sur une prévision "
                          "décalée (même constat que pour XGBoost, voir la rectification de l'exception 2).")
    return lignes + [""]


# --- Exécution ---------------------------------------------------------------------------------

def executer(regles: dict) -> dict:
    cle = T._cle_donnees(regles)
    publie = json.loads(B.CHEMIN_JSON.read_text(encoding="utf-8"))
    rapport = {"version": VERSION, "plis": publie["plis"],
               "depend_de": {"baselines_json_sha256": _sha256(B.CHEMIN_JSON), "regles_sha256": _sha256(R.CHEMIN_REGLES),
                             "variables_empreinte_contenu": publie["depend_de"]["variables_empreinte_contenu"]},
               "actifs": {}}
    tables = {}
    for actif in regles["donnees"]["actifs"]:
        calcul = calcul_baselines(actif, regles, cle)
        table, controles = B.series_evaluation(calcul, regles)
        table, controles_dl = ajouter_reseaux(table, calcul, actif, regles, cle)
        res = resultats_actif(table, regles)
        res["controles"] = {"XGBoost": controles["xgboost_validation"], **controles_dl,
                            "ecart_baselines_publiees": verifier_baselines(res, publie["actifs"][actif]),
                            "jours_evalues": G.compter(table["date_cible"])}
        res["reglage"] = json.loads((DOSSIER_DL / "reglage.json").read_text(encoding="utf-8"))[actif]
        rapport["actifs"][actif] = res
        tables[actif] = table
    verifier_alerte(rapport["actifs"], regles)      # avant toute écriture
    rapport["temps_phase_plis"] = temps_plis()
    for actif, table in tables.items():
        table.to_csv(B.DOSSIER_PREVISIONS / f"{actif}_tous_modeles.csv", index=False)       # ignoré par Git
        figure(actif, table, rapport["actifs"][actif]["classement"]["meilleur_reseau"], regles,
               C.RACINE / "figures" / f"figure_5_deep_learning_{actif}.png")
    C.ecrire_texte(CHEMIN_MANIFESTE, C.texte_json(manifeste_poids(regles, cle)))
    C.ecrire_texte(CHEMIN_JSON, C.texte_json(rapport))
    C.ecrire_texte(CHEMIN_MD, rapport_markdown(rapport, regles))
    return rapport


def main() -> int:
    C.proteger_sortie()
    regles = R.charger_regles()
    try:
        rapport = executer(regles)
    except AlerteFuite as alerte:
        print(str(alerte), file=sys.stderr)
        return 2
    except (G.ErreurTestAveugle, ErreurComparaison) as erreur:
        print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1
    for actif, res in rapport["actifs"].items():
        print(f"{actif} | retenu : {res['classement']['modele_retenu']} | meilleur réseau : {res['classement']['meilleur_reseau']} | "
              "gain sur HAR-RV (moyenne par pli) : "
              + ", ".join(f"{m} {_n(100 * res['gain_relatif_qlike'][m]['moyenne_des_plis'], 1)} %" for m in RESEAUX))
    return 0


if __name__ == "__main__":
    sys.exit(main())
