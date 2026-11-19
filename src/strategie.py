"""Stratégie de volatility targeting sur le développement (2020 à 2024). Le test final reste fermé.

Règles : config/regles.toml, sections strategie et strategie.precisions ; docs/REGLES.md, sections 9 et 15.

- Décision à la clôture du jour D (valide) : exposition = volatilité cible annuelle / (σ̂ de D+1 × racine(365)),
  bornée entre 0 et 1 ; appliquée au rendement simple de clôture à clôture de D+1 (décalage d'un jour).
- Jour non valide : aucune décision ; l'exposition de la dernière clôture valide reste en place.
- Frais = taux × |variation d'exposition| × valeur du portefeuille (0,10 % ; sensibilité 0,05 % et 0,20 %).
- Achat simple : exposition 1. Modèle retenu par actif et HAR-RV : comparaisons principales ; les autres : descriptifs.
- VaR à 1 jour à 95 % = quantile de la loi normale × σ̂ journalière ; taux de dépassement et test de Kupiec.

Aucune série journalière n'est commitée : sorties commitées = rapports/strategie.json, docs/STRATEGIE.md (généré),
figures/figure_6_strategie_{actif}.png.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sys
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
import variables as V  # noqa: E402

CHEMIN_JSON = C.DOSSIER_RAPPORTS / "strategie.json"
CHEMIN_MD = C.RACINE / "docs" / "STRATEGIE.md"
ACHAT = "Achat simple"
MODELES = K.SELECTIONNABLES + ["Persistance"]          # la persistance : descriptive
NOMS_CRISES = {"covid": "Covid", "terra_luna": "Terra-Luna", "ftx": "FTX"}


class ErreurStrategie(Exception):
    pass


# --- Exposition et portefeuille ---------------------------------------------------------------

def decisions(sigma_par_origine: pd.Series, valide: pd.Series, vol_cible: float, regles: dict) -> pd.Series:
    """Exposition décidée à la clôture de chaque jour D (index : jours de décision).

    sigma_par_origine[D] = σ̂ journalière prévue pour D+1 (NaN si aucune prévision). Si D n'est pas valide ou s'il n'y a
    pas de prévision, aucune décision : l'exposition précédente reste en place."""
    precedente = regles["strategie"]["precisions"]["exposition_initiale"]
    sortie = []
    for jour in sigma_par_origine.index:
        s = sigma_par_origine[jour]
        if bool(valide[jour]) and np.isfinite(s):
            precedente = R.exposition(regles, vol_cible, float(s))
        sortie.append(precedente)
    return pd.Series(sortie, index=sigma_par_origine.index, dtype="float64")


def exposition_appliquee(decision: pd.Series, jours: list[dt.date], decalage: int) -> np.ndarray:
    """Exposition du jour t = décision prise à la clôture du jour t − décalage (décalage = 1 dans les règles)."""
    return np.array([decision[t - dt.timedelta(days=decalage)] for t in jours], dtype="float64")


def simuler(exposition: np.ndarray, rendement: np.ndarray, taux_frais: float, regles: dict) -> dict:
    """Valeur du portefeuille (départ 1) : V_t = V_{t−1} × (1 − frais_t) × (1 + e_t × r_t), frais_t = taux × |e_t − e_{t−1}|.
    Liquidités à 0 %. Refuse une exposition hors des bornes des règles."""
    s = regles["strategie"]
    e = np.asarray(exposition, dtype="float64")
    r = np.asarray(rendement, dtype="float64")
    if not (np.isfinite(e).all() and (e >= s["exposition_min"]).all() and (e <= s["exposition_max"]).all()):
        raise ErreurStrategie(f"Exposition hors de [{s['exposition_min']} ; {s['exposition_max']}] : refusée.")
    variation = np.abs(np.diff(e, prepend=s["precisions"]["exposition_initiale"]))
    frais = taux_frais * variation
    croissance = (1 - frais) * (1 + e * r)
    valeur = np.cumprod(croissance)
    avant = np.r_[1.0, valeur[:-1]]
    return {"valeur": valeur, "rendement": croissance - 1, "variation": variation, "frais_valeur": avant * frais}


# --- Mesures --------------------------------------------------------------------------------

def sharpe(r: np.ndarray, jours_an: int = 365) -> float:
    return float(np.mean(r) / np.std(r, ddof=1) * math.sqrt(jours_an))


def sortino(r: np.ndarray, jours_an: int = 365) -> float:
    return float(np.mean(r) / math.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * math.sqrt(jours_an))


def drawdown_max(valeur: np.ndarray) -> float:
    v = np.r_[1.0, valeur]
    return float(np.min(v / np.maximum.accumulate(v) - 1))


def mesures(sim: dict, exposition: np.ndarray, vol_cible: float, regles: dict, intervalle: bool = True) -> dict:
    a = regles["strategie"]["annualisation_jours"]
    r, n = sim["rendement"], len(sim["rendement"])
    vol = float(np.std(r, ddof=1) * math.sqrt(a))
    sortie = {"jours": n, "rendement_annualise": float(sim["valeur"][-1] ** (a / n) - 1), "valeur_finale": float(sim["valeur"][-1]),
              "volatilite_annualisee": vol, "volatilite_sur_cible": vol / vol_cible, "sharpe": sharpe(r, a), "sortino": sortino(r, a),
              "drawdown_max": drawdown_max(sim["valeur"]), "rotation_annuelle": float(sim["variation"].sum() * a / n),
              "frais_total": float(sim["frais_valeur"].sum()),
              "frais_annuels_en_rendement": float(np.mean(sim["frais_valeur"] / np.r_[1.0, sim["valeur"][:-1]]) * a),
              "exposition_moyenne": float(np.mean(exposition)),
              "part_jours_exposition_max": float(np.mean(exposition >= regles["strategie"]["exposition_max"]))}
    if intervalle:
        sortie["sharpe_intervalle"] = EV.bootstrap_statistique([r], lambda x: sharpe(x, a), regles)
    return sortie


def mesures_periode(sim: dict, masque: np.ndarray, regles: dict) -> dict:
    a = regles["strategie"]["annualisation_jours"]
    r = sim["rendement"][masque]
    v = np.cumprod(1 + r)
    return {"jours": int(masque.sum()), "rendement_cumule": float(v[-1] - 1), "volatilite_annualisee": float(np.std(r, ddof=1) * math.sqrt(a)),
            "sharpe": sharpe(r, a), "drawdown_max": drawdown_max(v)}


def var_kupiec(sigma: np.ndarray, rendement: np.ndarray, utilisable: np.ndarray, regles: dict) -> dict:
    """Dépassements de la VaR à 1 jour (perte > VaR) sur les jours utilisables ; test de Kupiec."""
    s, r = sigma[utilisable], rendement[utilisable]
    var = np.array([R.var_un_jour(regles, float(x)) for x in s])
    return EV.kupiec(int((r < -var).sum()), int(len(r)), 1 - regles["strategie"]["var_niveau"])


# --- Calcul par actif -------------------------------------------------------------------------

def donnees_strategie(actif: str, regles: dict, bougies: pd.DataFrame | None = None) -> tuple[pd.DataFrame, list[dt.date]]:
    """Table journalière des jours évalués : rendement simple, validité du jour et de la veille, σ̂ de chaque modèle."""
    cle = T._cle_donnees(regles)
    calcul = K.calcul_baselines(actif, regles, cle)
    table, _ = B.series_evaluation(calcul, regles)
    table, _ = K.ajouter_reseaux(table, calcul, actif, regles, cle)
    plis = [d["evaluation"] for d in R.decoupages(regles)[:-1]]
    debut, fin = plis[0][0], plis[-1][1]
    jours = [debut + dt.timedelta(days=k) for k in range((fin - debut).days + 1)]
    G.refuser_si_test(jours, "stratégie")
    if bougies is None:
        bougies = V.lire_bougies(C.DOSSIER_TRAITE / f"{actif}_5m.parquet")
    _, journalier = B.donnees_actif(bougies, regles)
    veilles = [debut - dt.timedelta(days=1)] + jours
    j = journalier.loc[veilles]
    if j["rendement"].loc[jours].isna().any():
        raise ErreurStrategie(f"{actif} : rendement manquant sur la période.")
    sortie = pd.DataFrame(index=pd.Index(veilles, name="jour"))
    sortie["valide"] = j["valide"].astype(bool).to_numpy()
    sortie["rendement"] = np.expm1(j["rendement"].to_numpy())
    t = table.set_index("date_cible")
    for m in MODELES:
        sortie[m] = np.sqrt(t[m]).reindex(sortie.index)          # σ̂ prévue POUR ce jour (date de cible)
    return sortie, jours


def calculer_actif(actif: str, regles: dict, vol_cible: float, retenu: str, bougies: pd.DataFrame | None = None) -> tuple[dict, dict]:
    d, jours = donnees_strategie(actif, regles, bougies)
    decalage = regles["strategie"]["decalage_execution_jours"]
    r = d.loc[jours, "rendement"].to_numpy()
    origines = list(d.index[:-1])                                    # jours de décision : veille de chaque jour de cible
    expositions = {ACHAT: np.ones(len(jours))}
    for m in MODELES:
        sigma_par_origine = pd.Series([d.loc[o + dt.timedelta(days=1), m] for o in origines], index=origines)
        dec = decisions(sigma_par_origine, d["valide"], vol_cible, regles)
        expositions[m] = exposition_appliquee(dec, jours, decalage)
    frais = regles["strategie"]["frais"]
    sims = {m: simuler(e, r, frais, regles) for m, e in expositions.items()}
    res = {"vol_cible": vol_cible, "modele_retenu": retenu, "jours": len(jours),
           "jours_non_valides": int((~d.loc[jours, "valide"]).sum()), "strategies": {}}
    annees = sorted({t.year for t in jours})
    for m, sim in sims.items():
        x = mesures(sim, expositions[m], vol_cible, regles)
        x["par_annee"] = {str(a): mesures_periode(sim, np.array([t.year == a for t in jours]), regles) for a in annees}
        x["crises"] = {c: mesures_periode(sim, np.array([v["debut"] <= t <= v["fin"] for t in jours]), regles)
                       for c, v in regles["crises"].items()}
        x["sensibilite_frais"] = {}
        for taux in regles["strategie"]["frais_sensibilite"]:
            s2 = simuler(expositions[m], r, taux, regles)
            y = mesures(s2, expositions[m], vol_cible, regles, intervalle=False)
            x["sensibilite_frais"][str(taux)] = {k: y[k] for k in ("rendement_annualise", "sharpe", "frais_total")}
        res["strategies"][m] = x
    a = regles["strategie"]["annualisation_jours"]
    res["difference_sharpe_retenu_moins_har"] = EV.bootstrap_statistique(
        [sims[retenu]["rendement"], sims["HAR-RV"]["rendement"]], lambda u, v: sharpe(u, a) - sharpe(v, a), regles)
    # VaR : jours dont le rendement est un vrai rendement à un jour (jour et veille valides) et qui ont une prévision
    valide = d["valide"].to_numpy()
    un_jour = valide[1:] & valide[:-1]
    res["var"] = {"jours_exclus_non_valides": int((~un_jour).sum()), "modeles": {}}
    for m in MODELES:
        sigma = d.loc[jours, m].to_numpy()
        res["var"]["modeles"][m] = var_kupiec(sigma, r, un_jour & np.isfinite(sigma), regles)
    series = {"jours": jours, "valeur": {m: sims[m]["valeur"] for m in (ACHAT, "HAR-RV", retenu)},
              "exposition": {m: expositions[m] for m in ("HAR-RV", retenu)}}
    return res, series


# --- Figure ---------------------------------------------------------------------------------

def figure(actif: str, series: dict, retenu: str, regles: dict, chemin: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    import exploration as X
    G.refuser_si_test(series["jours"], "figure de la stratégie")
    dates = pd.to_datetime([str(t) for t in series["jours"]])
    couleurs = {ACHAT: "#999999", "HAR-RV": X.COULEURS[actif], retenu: "#7C3AED"}
    fig, (h, b) = plt.subplots(2, 1, figsize=(11, 7), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    for m, v in series["valeur"].items():
        h.plot(dates, v, color=couleurs[m], linewidth=1.0, label=m if m != retenu else f"{m} (modèle retenu)")
    h.set_yscale("log")
    h.yaxis.set_major_formatter(FuncFormatter(lambda x, _p: X.nombre_fr_auto(round(x, 6))))
    h.yaxis.set_minor_formatter(FuncFormatter(lambda x, _p: ""))
    h.set_ylabel("Valeur du portefeuille (départ 1, échelle log)")
    for m, e in series["exposition"].items():
        b.plot(dates, e, color=couleurs[m], linewidth=0.7, label=m if m != retenu else f"{m} (modèle retenu)")
    b.set_ylim(-0.02, 1.05)
    b.yaxis.set_major_formatter(X.FORMAT_POURCENT)
    b.set_ylabel("Exposition")
    for ax in (h, b):
        for nom, c in regles["crises"].items():
            ax.axvspan(pd.Timestamp(c["debut"]), pd.Timestamp(c["fin"]) + pd.Timedelta(days=1), color="#999999", alpha=0.2,
                       label="Crises" if nom == next(iter(regles["crises"])) and ax is h else None)
        ax.grid(alpha=0.3)
    h.legend(loc="upper left")
    b.legend(loc="lower left")
    b.xaxis.set_major_locator(mdates.YearLocator())
    b.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    b.set_xlabel("Date (développement, frais de 0,10 % compris)")
    h.set_title(f"{X.NOMS[actif]} : volatility targeting, achat simple, HAR-RV et {retenu}")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    X._finir(fig, chemin)


# --- Rapport Markdown généré ----------------------------------------------------------------------

def _n(x: float, d: int = 2) -> str:
    return C.nombre_fr(x, d).replace("-", "−")


def _pc(x: float, d: int = 1) -> str:
    return _n(100 * x, d) + " %"


def _p(p: float) -> str:
    return _n(p, 4) if p >= 0.0001 else "< 0,0001"


def rapport_markdown(rapport: dict, regles: dict) -> str:
    lignes = ["# Stratégie de volatility targeting (développement, 2020 à 2024)", "",
              "Fichier généré par `src/strategie.py` à partir de `rapports/strategie.json` : ne pas le modifier à la main.", "",
              "- Exposition décidée à la clôture de J = volatilité cible annuelle / (σ̂ de J+1 × racine(365)), bornée entre 0 et 1, "
              "appliquée au rendement simple de J+1 ; liquidités à 0 % ; rééquilibrage quotidien.",
              f"- Frais : {_n(100 * regles['strategie']['frais'])} % de la variation d'exposition ; sensibilité à "
              + " % et à ".join(_n(100 * x) for x in regles["strategie"]["frais_sensibilite"]) + " %.",
              "- Jour non valide : aucune décision, l'exposition précédente reste en place (précision du 2026-11-19).",
              "- Modèle retenu (règle de sélection sur QLIKE) et HAR-RV : comparaisons principales ; les autres modèles sont descriptifs. "
              "Aucune optimisation de la stratégie ; le test final est fermé.",
              "- Sharpe et Sortino : taux sans risque nul, annualisation sur 365 jours ; intervalles à 95 % par bootstrap à blocs mobiles "
              "(20 jours, 1000 tirages, graine 42).", ""]
    for actif, res in rapport["actifs"].items():
        retenu = res["modele_retenu"]
        lignes += [f"## {actif}", "", f"Volatilité cible : {_pc(res['vol_cible'])} par an. Modèle retenu : **{retenu}**. "
                   f"Jours : {C.nombre_fr(res['jours'])}, dont {res['jours_non_valides']} non valides.", "",
                   "### Mesures (frais de 0,10 %)", "",
                   "| Stratégie | Rendement annualisé | Volatilité (÷ cible) | Sharpe [IC 95 %] | Sortino | Drawdown max | Rotation annuelle | Frais par an | Frais totaux | Exposition moyenne |",
                   "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|"]
        ordre = [ACHAT, "HAR-RV", retenu] + [m for m in MODELES if m not in ("HAR-RV", retenu)]
        for m in ordre:
            x = res["strategies"][m]
            role = " (principal)" if m in (ACHAT, "HAR-RV", retenu) else (" (descriptive)" if m == "Persistance" else " (descriptif)")
            lignes.append(f"| {m}{role} | {_pc(x['rendement_annualise'])} | {_pc(x['volatilite_annualisee'])} ({_n(x['volatilite_sur_cible'])}) | "
                          f"{_n(x['sharpe'])} [{_n(x['sharpe_intervalle']['bas'])} ; {_n(x['sharpe_intervalle']['haut'])}] | "
                          f"{_n(x['sortino'])} | {_pc(x['drawdown_max'])} | {_n(x['rotation_annuelle'], 1)} | "
                          f"{_pc(x['frais_annuels_en_rendement'], 2)} | {_pc(x['frais_total'], 2)} | "
                          f"{_pc(x['exposition_moyenne'])} |")
        ds = res["difference_sharpe_retenu_moins_har"]
        lignes += ["", f"Différence de Sharpe {retenu} − HAR-RV (descriptif) : {_n(ds['valeur'])} [{_n(ds['bas'])} ; {_n(ds['haut'])}].",
                   "Frais par an : coût moyen en points de rendement par an. Frais totaux : somme des frais payés, en part du capital de "
                   "départ (ils grossissent avec la valeur du portefeuille). Rotation annuelle : somme des variations d'exposition par an.", "",
                   "### Sensibilité aux frais (descriptif)", ""]
        taux = sorted([float(t) for t in res["strategies"][ACHAT]["sensibilite_frais"]] + [regles["strategie"]["frais"]])
        lignes += ["| Stratégie | " + " | ".join(f"Sharpe à {_n(100 * t)} %" for t in taux) + " |", "|---|" + "---:|" * len(taux)]
        for m in (ACHAT, "HAR-RV", retenu):
            x = res["strategies"][m]
            valeurs = {float(t): v["sharpe"] for t, v in x["sensibilite_frais"].items()} | {regles["strategie"]["frais"]: x["sharpe"]}
            lignes.append(f"| {m} | " + " | ".join(_n(valeurs[t]) for t in taux) + " |")
        annees = list(res["strategies"][ACHAT]["par_annee"])
        lignes += ["", "### Par année (descriptif)", "", "| Stratégie | Mesure | " + " | ".join(annees) + " |", "|---|---|" + "---:|" * len(annees)]
        for m in (ACHAT, "HAR-RV", retenu):
            for cle, nom, f in (("rendement_cumule", "Rendement", _pc), ("volatilite_annualisee", "Volatilité", _pc),
                                ("sharpe", "Sharpe", _n), ("drawdown_max", "Drawdown max", _pc)):
                lignes.append(f"| {m} | {nom} | " + " | ".join(f(res["strategies"][m]["par_annee"][a][cle]) for a in annees) + " |")
        lignes += ["", "### Crises (descriptif)", "", "| Stratégie | " + " | ".join(f"{NOMS_CRISES.get(c, c)} : rendement / drawdown max"
                                                                          for c in regles["crises"]) + " |", "|---|" + "---:|" * len(regles["crises"])]
        for m in (ACHAT, "HAR-RV", retenu):
            lignes.append(f"| {m} | " + " | ".join(f"{_pc(res['strategies'][m]['crises'][c]['rendement_cumule'])} / "
                                                   f"{_pc(res['strategies'][m]['crises'][c]['drawdown_max'])}" for c in regles["crises"]) + " |")
        v = res["var"]
        lignes += ["", "### VaR à 1 jour à 95 % et test de Kupiec", "",
                   f"VaR = quantile de la loi normale (1,6449) × σ̂ journalière, sur le rendement de l'actif. Jours exclus (jour non valide "
                   f"ou lendemain : rendement nul ou sur deux jours) : {v['jours_exclus_non_valides']}.", "",
                   "| Modèle | Jours | Dépassements | Taux (attendu 5 %) | Statistique LR | p-valeur | Rejet à 5 % |", "|---|---:|---:|---:|---:|---:|---|"]
        for m in MODELES:
            k = v["modeles"][m]
            lignes.append(f"| {m}{' (descriptive)' if m == 'Persistance' else ''} | {C.nombre_fr(k['jours'])} | {k['depassements']} | "
                          f"{_pc(k['taux'], 2)} | {_n(k['statistique'])} | {_p(k['p_valeur'])} | "
                          f"{'oui' if k['p_valeur'] < regles['evaluation']['diebold_mariano']['seuil'] else 'non'} |")
        lignes += ["", f"Figure : `figures/figure_6_strategie_{actif}.png`.", ""]
    lignes += lecture_des_resultats(rapport, regles)
    return "\n".join(lignes) + "\n"


def _liste(noms: list[str]) -> str:
    return noms[0] if len(noms) == 1 else ", ".join(noms[:-1]) + " et " + noms[-1]


def _rangs(valeurs: dict, croissant: bool) -> dict:
    ordre = sorted(valeurs, key=valeurs.get, reverse=not croissant)
    return {m: k for k, m in enumerate(ordre)}


def lecture_des_resultats(rapport: dict, regles: dict) -> list[str]:
    """Phrases d'interprétation, chacune conditionnée par les valeurs du JSON."""
    from scipy import stats
    tol = regles["strategie"]["precisions"]["cible_atteinte_tolerance"]
    seuil = regles["evaluation"]["diebold_mariano"]["seuil"]
    lignes = ["## Lecture des résultats", "", "Chaque phrase ci-dessous est générée à partir des valeurs de `rapports/strategie.json`.", ""]
    for actif, res in rapport["actifs"].items():
        nom, retenu, st = actif.replace("USDT", ""), res["modele_retenu"], res["strategies"]
        for m in ("HAR-RV", retenu):
            x = st[m]
            q = x["volatilite_sur_cible"]
            if abs(q - 1) <= tol:
                texte = f"proche de sa cible (à {_n(100 * tol, 0)} % près)"
            elif q < 1:
                texte = (f"sous sa cible ({_n(100 * q, 0)} % de la cible) : l'exposition est plafonnée à 1 (pas d'emprunt) "
                         f"{_pc(x['part_jours_exposition_max'], 0)} des jours, quand la volatilité prévue est sous la cible")
            else:
                texte = f"au-dessus de sa cible ({_n(100 * q, 0)} % de la cible)"
            lignes.append(f"- {nom} : la stratégie pilotée par {m} a une volatilité réalisée {texte}.")
        for m in ("HAR-RV", retenu):
            reduit = st[m]["drawdown_max"] > st[ACHAT]["drawdown_max"]
            lignes.append(f"- {nom} : la stratégie pilotée par {m} {'réduit' if reduit else 'ne réduit pas'} le drawdown maximal "
                          f"par rapport à l'achat simple ({_pc(st[m]['drawdown_max'])} contre {_pc(st[ACHAT]['drawdown_max'])}).")
        ds = res["difference_sharpe_retenu_moins_har"]
        if ds["bas"] > 0 or ds["haut"] < 0:
            lignes.append(f"- {nom} : le Sharpe de {retenu} est {'supérieur' if ds['valeur'] > 0 else 'inférieur'} à celui de HAR-RV, "
                          "et l'intervalle bootstrap de la différence ne contient pas 0 (descriptif).")
        else:
            lignes.append(f"- {nom} : le Sharpe de {retenu} est {'supérieur' if ds['valeur'] > 0 else 'inférieur ou égal'} à celui de HAR-RV, "
                          "mais l'intervalle bootstrap de la différence contient 0 : on ne peut pas dire que l'une fait mieux que l'autre (descriptif).")
        for m in ("HAR-RV", retenu):
            if st[m]["sharpe"] > st[ACHAT]["sharpe"]:
                lignes.append(f"- {nom} : la stratégie pilotée par {m} a un Sharpe plus élevé que l'achat simple.")
            else:
                lignes.append(f"- {nom} : la stratégie pilotée par {m} n'a pas un Sharpe plus élevé que l'achat simple.")
        qlike = rapport["qlike_moyenne_des_plis"][actif]
        modeles = list(qlike)
        rq = _rangs(qlike, croissant=True)
        rs = _rangs({m: st[m]["sharpe"] for m in modeles}, croissant=False)
        rho = stats.spearmanr([rq[m] for m in modeles], [rs[m] for m in modeles]).statistic
        meilleur_s = min(rs, key=rs.get)
        lignes.append(f"- {nom} : le classement par Sharpe {'garde' if meilleur_s == retenu else 'ne garde pas'} en tête le modèle retenu par "
                      f"QLIKE ({retenu}{'' if meilleur_s == retenu else ' ; meilleur Sharpe : ' + meilleur_s}) ; corrélation de rang de "
                      f"Spearman entre les deux classements des {len(modeles)} modèles : {_n(rho)} "
                      f"({'les deux classements vont dans le même sens' if rho > 0 else 'les deux classements ne vont pas dans le même sens'} ; descriptif).")
        vm = res["var"]["modeles"]
        rejets = [m for m, k in vm.items() if k["p_valeur"] < seuil]
        sous = [m for m, k in vm.items() if k["taux"] < k["attendu"]]
        lignes.append(f"- {nom} : le taux de dépassement de la VaR est sous 5 % pour {len(sous)} modèle{'s' if len(sous) > 1 else ''} sur {len(vm)}"
                      + (" : la VaR est plutôt trop prudente que trop optimiste." if len(sous) > len(vm) / 2 else "."))
        if rejets:
            peu = [m for m in rejets if vm[m]["taux"] < vm[m]["attendu"]]
            trop = [m for m in rejets if vm[m]["taux"] > vm[m]["attendu"]]
            if peu == rejets:
                lignes.append(f"- {nom} : le test de Kupiec rejette la VaR de {_liste(rejets)}, chaque fois pour trop PEU de "
                              "dépassements (VaR trop prudente).")
            else:
                lignes.append(f"- {nom} : le test de Kupiec rejette la VaR de {_liste(rejets)}"
                              + (f" ; {_liste(peu)} : trop PEU de dépassements (VaR trop prudente)" if peu else "")
                              + (f" ; {_liste(trop)} : trop de dépassements (VaR trop optimiste)" if trop else "") + ".")
            if peu:
                lignes.append(f"- {nom} : explication possible, non démontrée, des rejets pour trop peu de dépassements : la variance prévue "
                              "vise la moyenne de RV², que les jours très agités tirent vers le haut (correction s² des modèles en log, "
                              "facteur d'échelle du GARCH) ; et, au niveau de 95 %, une loi à queues épaisses dépasse moins souvent que la "
                              "loi normale le quantile normal de même variance (ses dépassements sont plus rares, mais plus grands).")
        else:
            lignes.append(f"- {nom} : le test de Kupiec ne rejette la VaR d'aucun modèle à 5 %.")
        ordre_frais = [st[retenu]["sensibilite_frais"][t]["sharpe"] > st["HAR-RV"]["sensibilite_frais"][t]["sharpe"]
                       for t in st[retenu]["sensibilite_frais"]] + [st[retenu]["sharpe"] > st["HAR-RV"]["sharpe"]]
        lignes.append(f"- {nom} : l'ordre des Sharpe entre {retenu} et HAR-RV "
                      f"{'ne change pas' if len(set(ordre_frais)) == 1 else 'change'} quand les frais vont de 0,05 % à 0,20 %.")
    return lignes + [""]


# --- Exécution ---------------------------------------------------------------------------------

def executer(regles: dict) -> dict:
    vc = json.loads(V.CHEMIN_VOL_CIBLE.read_text(encoding="utf-8"))["actifs"]
    comparaison = json.loads(K.CHEMIN_JSON.read_text(encoding="utf-8"))
    plis = R.decoupages(regles)[:-1]
    rapport = {"periode": [str(plis[0]["evaluation"][0]), str(plis[-1]["evaluation"][1])],
               "depend_de": {"comparaison_modeles_sha256": K._sha256(K.CHEMIN_JSON), "volatilite_cible_sha256": K._sha256(V.CHEMIN_VOL_CIBLE)},
               "qlike_moyenne_des_plis": {}, "actifs": {}}
    for actif in regles["donnees"]["actifs"]:
        retenu = comparaison["actifs"][actif]["classement"]["modele_retenu"]
        rapport["qlike_moyenne_des_plis"][actif] = {m: comparaison["actifs"][actif]["modeles"][m]["qlike_moyenne_des_plis"]
                                                     for m in K.SELECTIONNABLES}
        res, series = calculer_actif(actif, regles, vc[actif]["valeur_annualisee"], retenu)
        rapport["actifs"][actif] = res
        figure(actif, series, retenu, regles, C.RACINE / "figures" / f"figure_6_strategie_{actif}.png")
    C.ecrire_texte(CHEMIN_JSON, C.texte_json(rapport))
    C.ecrire_texte(CHEMIN_MD, rapport_markdown(rapport, regles))
    return rapport


def main() -> int:
    C.proteger_sortie()
    regles = R.charger_regles()
    try:
        rapport = executer(regles)
    except (G.ErreurTestAveugle, ErreurStrategie, K.ErreurComparaison) as erreur:
        print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1
    for actif, res in rapport["actifs"].items():
        s = res["strategies"]
        print(f"{actif} | Sharpe : achat simple {_n(s[ACHAT]['sharpe'])}, HAR-RV {_n(s['HAR-RV']['sharpe'])}, "
              f"{res['modele_retenu']} {_n(s[res['modele_retenu']]['sharpe'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
