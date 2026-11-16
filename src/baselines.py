"""Baselines sur le développement : persistance (descriptive), HAR-RV, GARCH(1,1) Student et XGBoost.

Règles : config/regles.toml (modeles, entrainement, evaluation) et docs/REGLES.md (sections 7, 8, 11, 12).
- Découpages : les 5 plis annuels, puis le modèle du test final (entraîné et enregistré, SANS AUCUNE
  prévision sur le test : la garde du test aveugle refuse toute prévision dont la cible est >= test_debut).
- Chaque calcul est une unité de reprise (src/reprise.py) ; les prévisions jour par jour vont dans
  sorties/ (ignoré par Git, jamais commité).
- GARCH : paramètres estimés avec arch sur la fenêtre d'ajustement, avec une variance de départ (backcast)
  calculée sur cette fenêtre et passée explicitement ; la récurrence de la variance est ensuite faite ici,
  avec ce backcast figé, pour qu'aucune donnée postérieure n'y entre.
- XGBoost : 12 combinaisons (budget_reglage) réglées une fois par actif sur le premier découpage, puis
  figées ; 3 graines par découpage ; prévision = moyenne des log des graines.

Sorties commitées : rapports/baselines.json, docs/RESULTATS_BASELINES.md (généré), figures,
rapports/modeles_test_final.json (empreintes des modèles du test final).

Usage : .venv\\Scripts\\python src/baselines.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import commun as C  # noqa: E402
import evaluation as E  # noqa: E402
import garde as G  # noqa: E402
import regles as R  # noqa: E402
import reprise as P  # noqa: E402
import variables as V  # noqa: E402

VERSION = "baselines-1"
DOSSIER_SORTIES = C.RACINE / "sorties"
DOSSIER_REPRISE = DOSSIER_SORTIES / "reprise" / "baselines"
DOSSIER_PREVISIONS = DOSSIER_SORTIES / "previsions"
DOSSIER_MODELES = DOSSIER_SORTIES / "modeles_test_final"
CHEMIN_JSON = C.DOSSIER_RAPPORTS / "baselines.json"
CHEMIN_MANIFESTE_MODELES = C.DOSSIER_RAPPORTS / "modeles_test_final.json"
CHEMIN_MD = C.RACINE / "docs" / "RESULTATS_BASELINES.md"
MODELES = ["Persistance", "HAR-RV", "GARCH(1,1)", "XGBoost"]
ECHELLE_GARCH = 100.0     # rendements × 100 pour la stabilité numérique ; variances ÷ 10 000


class ErreurBaselines(RuntimeError):
    pass


# --- Données -----------------------------------------------------------------------------------

def donnees_actif(bougies: pd.DataFrame, regles: dict, debut: dt.date | None = None, fin: dt.date | None = None):
    """(exemples, journalier) : exemples de src/variables.py et série journalière (rendement de la série
    remplacée, RV réalisée non remplacée, validité)."""
    exemples, lignes, _ = V.calculer_actif(bougies, regles, debut, fin)
    base, _ = V.appliquer_secours(lignes)
    variables = V.calculer_variables(base, regles)
    journalier = pd.DataFrame({"rendement": variables["log_rendement"], "rv": lignes["rv"],
                               "valide": lignes["valide"].astype(bool)}, index=lignes.index)
    return exemples, journalier


def masques(exemples: pd.DataFrame, decoupage: dict) -> dict[str, np.ndarray]:
    cibles = exemples["date_cible"]
    return {nom: ((cibles >= decoupage[nom][0]) & (cibles <= decoupage[nom][1])).to_numpy()
            for nom in ("ajustement", "validation", "evaluation")}


def entrees(exemples: pd.DataFrame, regles: dict) -> np.ndarray:
    colonnes = regles["entrainement"]["variables_continues"] + ["jour_semaine"]
    return exemples[colonnes].to_numpy(dtype="float64")


# --- Persistance et HAR-RV ---------------------------------------------------------------------

def prevoir_persistance(exemples: pd.DataFrame) -> np.ndarray:
    """log RV(J+1) prévu = log RV(J)."""
    return exemples["log_rv_1"].to_numpy(dtype="float64")


def ajuster_har(exemples: pd.DataFrame, regles: dict) -> np.ndarray:
    """Moindres carrés de log RV(J+1) sur une constante et log RV moyennes sur 1, 7 et 30 jours."""
    x = _matrice_har(exemples, regles)
    coef, *_ = np.linalg.lstsq(x, exemples["cible"].to_numpy(dtype="float64"), rcond=None)
    return coef


def _matrice_har(exemples: pd.DataFrame, regles: dict) -> np.ndarray:
    colonnes = [f"log_rv_{n}" for n in regles["modeles"]["har_rv"]["fenetres_jours"]]
    return np.column_stack([np.ones(len(exemples))] + [exemples[k].to_numpy(dtype="float64") for k in colonnes])


def prevoir_har(exemples: pd.DataFrame, coef: np.ndarray, regles: dict) -> np.ndarray:
    return _matrice_har(exemples, regles) @ coef


# --- GARCH(1,1) Student ----------------------------------------------------------------------

def variances_garch(r100: np.ndarray, params: dict, backcast: float) -> np.ndarray:
    """Variance conditionnelle de chaque rendement (information jusqu'à la veille), plus, en dernière
    position, la prévision du jour suivant le dernier rendement. Récurrence avec un backcast FIXÉ."""
    eps2 = (r100 - params["mu"]) ** 2
    s2 = np.empty(len(r100) + 1)
    s2[0] = params["omega"] + (params["alpha"] + params["beta"]) * backcast
    for t in range(1, len(r100) + 1):
        s2[t] = params["omega"] + params["alpha"] * eps2[t - 1] + params["beta"] * s2[t - 1]
    return s2


def backcast_ajustement(r100_ajustement: np.ndarray) -> float:
    """Variance de départ calculée sur la fenêtre d'ajustement seulement (formule d'arch)."""
    from arch.univariate import GARCH
    return float(GARCH().backcast(r100_ajustement - r100_ajustement.mean()))


def estimer_garch(journalier: pd.DataFrame, decoupage: dict, regles: dict) -> dict:
    """Paramètres, backcast et facteur d'échelle, appris sur la fenêtre d'ajustement seulement."""
    from arch import arch_model
    fin = decoupage["ajustement"][1]
    serie = journalier["rendement"].dropna()
    serie = serie[[j <= fin for j in serie.index]]
    r100 = serie.to_numpy(dtype="float64") * ECHELLE_GARCH
    backcast = backcast_ajustement(r100)
    resultat = arch_model(r100, mean="Constant", vol="GARCH", p=1, q=1, dist="t").fit(disp="off", backcast=backcast)
    p = resultat.params
    params = {"mu": float(p["mu"]), "omega": float(p["omega"]), "alpha": float(p["alpha[1]"]),
              "beta": float(p["beta[1]"]), "nu": float(p["nu"])}
    s2 = variances_garch(r100, params, backcast)[:-1]
    ecart_arch = float(np.max(np.abs(s2 - resultat.conditional_volatility ** 2)))
    jours = list(serie.index)
    debut_cibles = decoupage["ajustement"][0]
    choisis = [i for i, j in enumerate(jours) if j >= debut_cibles and bool(journalier.loc[j, "valide"])]
    rv2 = journalier["rv"].to_numpy()[[journalier.index.get_loc(jours[i]) for i in choisis]] ** 2
    facteur = float(np.mean(rv2) / np.mean(s2[choisis] / ECHELLE_GARCH ** 2))
    return {"params": params, "backcast": backcast, "facteur": facteur, "convergence": int(resultat.convergence_flag),
            "ecart_recurrence_arch": ecart_arch, "rendements_estimation": len(r100)}


def prevoir_garch(journalier: pd.DataFrame, origines: list[dt.date], modele: dict) -> np.ndarray:
    """Variance prévue de RV² du lendemain de chaque origine J, avec les rendements connus jusqu'à J."""
    if not origines:
        return np.array([])
    derniere = max(origines)
    serie = journalier["rendement"].dropna()
    serie = serie[[j <= derniere for j in serie.index]]          # série coupée à la dernière origine
    s2 = variances_garch(serie.to_numpy(dtype="float64") * ECHELLE_GARCH, modele["params"], modele["backcast"])
    position = {j: i for i, j in enumerate(serie.index)}
    return np.array([s2[position[j] + 1] for j in origines]) / ECHELLE_GARCH ** 2 * modele["facteur"]


# --- XGBoost -----------------------------------------------------------------------------------

def tirer_combinaisons(regles: dict, nom_espace: str, n: int, valide=lambda c: True) -> tuple[list[dict], int]:
    """N combinaisons VALIDES tirées au hasard (graine de la recherche) ; renvoie aussi le nombre de tirages écartés."""
    espace = regles["entrainement"]["espaces"][nom_espace]
    rng = np.random.default_rng(regles["entrainement"]["recherche"]["graine"])
    combinaisons, ecartes = [], 0
    while len(combinaisons) < n:
        tirage = {}
        for cle in sorted(espace):
            valeur = espace[cle]
            if isinstance(valeur, list):
                tirage[cle] = valeur[int(rng.integers(len(valeur)))]
            elif isinstance(valeur, dict) and valeur.get("loi") == "log_uniforme":
                tirage[cle] = float(math.exp(rng.uniform(math.log(valeur["min"]), math.log(valeur["max"]))))
        if valide(tirage):
            combinaisons.append(tirage)
        else:
            ecartes += 1
    return combinaisons, ecartes


def entrainer_xgboost(x_aj, y_aj, x_val, y_val, combinaison: dict, graine: int, regles: dict, arbres_max=None, patience=None):
    import xgboost as xgb
    ent = regles["entrainement"]
    modele = xgb.XGBRegressor(n_estimators=arbres_max or ent["xgboost_arbres_max"],
                              early_stopping_rounds=patience or ent["xgboost_patience_arbres"], eval_metric="rmse",
                              tree_method="hist", n_jobs=regles["projet"]["fils_calcul"], random_state=graine, **combinaison)
    modele.fit(x_aj, y_aj, eval_set=[(x_val, y_val)], verbose=False)
    return modele


# --- s² et métriques ----------------------------------------------------------------------------

def s2_et_biais(cible_val: np.ndarray, prevision_val: np.ndarray) -> tuple[float, float]:
    residus = cible_val - prevision_val
    return float(np.var(residus)), float(np.mean(residus))


def pertes(cible_log: np.ndarray, h: np.ndarray) -> dict[str, np.ndarray]:
    """Pertes jour par jour : QLIKE sur la variance, erreurs sur RV avec σ̂ = racine(h)."""
    rv = np.exp(cible_log)
    sigma = np.sqrt(h)
    return {"qlike": E.qlike(rv, h), "erreur2": (rv - sigma) ** 2, "erreur_abs": np.abs(rv - sigma)}


def resume_pertes(p: dict[str, np.ndarray], regles: dict | None = None) -> dict:
    sortie = {"jours": int(len(p["qlike"])), "qlike": float(p["qlike"].mean()),
              "rmse": float(math.sqrt(p["erreur2"].mean())), "mae": float(p["erreur_abs"].mean())}
    if regles is not None:
        sortie["qlike_intervalle"] = E.bootstrap_selon_regles(p["qlike"], regles)
        b = E.bootstrap_selon_regles(p["erreur2"], regles)
        sortie["rmse_intervalle"] = {"moyenne": math.sqrt(b["moyenne"]), "bas": math.sqrt(b["bas"]), "haut": math.sqrt(b["haut"])}
        sortie["mae_intervalle"] = E.bootstrap_selon_regles(p["erreur_abs"], regles)
    return sortie


# --- Prévisions d'un découpage (fonction pure, utilisée par les unités et par le test de l'avenir modifié)

def previsions_decoupage(exemples: pd.DataFrame, journalier: pd.DataFrame, regles: dict, decoupage: dict,
                         combinaison_xgb: dict, graines_xgb: list[int], options_xgb: dict | None = None,
                         prevoir_evaluation: bool = True, estimer=estimer_garch) -> dict:
    """Prévisions (log pour persistance, HAR et XGBoost ; variance pour GARCH) sur la validation interne et,
    si demandé, sur l'évaluation. L'évaluation passe d'abord par la garde du test aveugle."""
    m = masques(exemples, decoupage)
    aj, val, ev = exemples[m["ajustement"]], exemples[m["validation"]], exemples[m["evaluation"]]
    if prevoir_evaluation:
        G.refuser_si_test(ev["date_cible"], f"prévisions de {decoupage['nom']}")
    parties = {"validation": val, "evaluation": ev} if prevoir_evaluation else {"validation": val}
    sortie = {nom: {"date_cible": [str(d) for d in p["date_cible"]], "cible": p["cible"].to_numpy().tolist()}
              for nom, p in parties.items()}
    coef = ajuster_har(aj, regles)
    garch = estimer(journalier, decoupage, regles)
    x_aj, x_val = entrees(aj, regles), entrees(val, regles)
    modeles_xgb = [entrainer_xgboost(x_aj, aj["cible"].to_numpy(), x_val, val["cible"].to_numpy(), combinaison_xgb, g, regles,
                                     **(options_xgb or {})) for g in graines_xgb]
    for nom, p in parties.items():
        x = entrees(p, regles)
        sortie[nom]["persistance_log"] = prevoir_persistance(p).tolist()
        sortie[nom]["har_log"] = prevoir_har(p, coef, regles).tolist()
        sortie[nom]["garch_variance"] = prevoir_garch(journalier, list(p["date_origine"]), garch).tolist()
        sortie[nom]["xgboost_log_par_graine"] = [mx.predict(x).astype("float64").tolist() for mx in modeles_xgb]
    sortie["har_coefficients"] = coef.tolist()
    sortie["garch"] = garch
    sortie["xgboost_arbres"] = [int(mx.best_iteration) + 1 for mx in modeles_xgb]
    sortie["_modeles_xgb"] = modeles_xgb
    return sortie


# --- Calcul complet avec la reprise ----------------------------------------------------------

def _empreinte(objet) -> str:
    return hashlib.sha256(json.dumps(objet, sort_keys=True).encode("utf-8")).hexdigest()


def regler_xgboost(actif: str, exemples: pd.DataFrame, regles: dict, cle_donnees: str) -> dict:
    """Réglage unique sur le premier découpage : N combinaisons valides, une graine dérivée chacune."""
    n = regles["modeles"]["budget_reglage"]
    combinaisons, ecartes = tirer_combinaisons(regles, "xgboost", n)
    pli1 = R.decoupages(regles)[0]
    m = masques(exemples, pli1)
    aj, val = exemples[m["ajustement"]], exemples[m["validation"]]
    x_aj, x_val = entrees(aj, regles), entrees(val, regles)

    def calcul(identifiant: str, graine: int) -> dict:
        k = int(identifiant.split("|combinaison ")[1].split("|")[0])
        modele = entrainer_xgboost(x_aj, aj["cible"].to_numpy(), x_val, val["cible"].to_numpy(), combinaisons[k], graine, regles)
        prevision = modele.predict(x_val).astype("float64")
        return {"mse_log_validation": float(np.mean((val["cible"].to_numpy() - prevision) ** 2)),
                "arbres": int(modele.best_iteration) + 1}

    unites = [f"{VERSION}|{actif}|XGBoost|réglage|combinaison {k}|graine 0|{cle_donnees}" for k in range(n)]
    P.executer(unites, calcul, DOSSIER_REPRISE)
    scores = [P.lire_unite(DOSSIER_REPRISE, u) for u in unites]
    meilleure = int(np.argmin([s["mse_log_validation"] for s in scores]))
    return {"combinaisons": combinaisons, "tirages_ecartes": ecartes, "scores": scores, "meilleure": meilleure,
            "combinaison_retenue": combinaisons[meilleure]}


def calculer_actif(actif: str, bougies: pd.DataFrame, regles: dict, cle_donnees: str) -> dict:
    exemples, journalier = donnees_actif(bougies, regles)
    reglage = regler_xgboost(actif, exemples, regles, cle_donnees)
    graines = regles["modeles"]["graines_deep_learning"]
    decoupages = R.decoupages(regles)
    resultats = []
    for numero, d in enumerate(decoupages):
        test_final = numero == len(decoupages) - 1

        def calcul(identifiant: str, graine_unite: int, d=d, test_final=test_final) -> dict:
            graines_derivees = [P.graine_unite(f"{identifiant}|graine {g}") for g in graines]
            sortie = previsions_decoupage(exemples, journalier, regles, d, reglage["combinaison_retenue"], graines_derivees,
                                          prevoir_evaluation=not test_final)
            modeles_xgb = sortie.pop("_modeles_xgb")
            if test_final:
                dossier = DOSSIER_MODELES / actif
                dossier.mkdir(parents=True, exist_ok=True)
                for g, mx in zip(graines, modeles_xgb):
                    mx.save_model(str(dossier / f"xgboost_graine_{g}.json"))
                C.ecrire_texte(dossier / "har_garch.json", C.texte_json({"har_coefficients": sortie["har_coefficients"],
                                                                          "garch": sortie["garch"]}))
            return sortie

        unite = f"{VERSION}|{actif}|baselines|{d['nom']}|{cle_donnees}"
        P.executer([unite], calcul, DOSSIER_REPRISE)
        resultats.append({"decoupage": d, "sortie": P.lire_unite(DOSSIER_REPRISE, unite)})
    return {"reglage": reglage, "decoupages": resultats}


# --- Résultats -----------------------------------------------------------------------------------

def series_evaluation(calcul: dict, regles: dict) -> tuple[pd.DataFrame, dict]:
    """Prévisions des 5 plis réunis (variance h par modèle), et contrôles par pli."""
    lignes, controles = [], {"har": [], "garch": [], "xgboost_validation": [], "xgboost_par_graine": []}
    for bloc in calcul["decoupages"]:
        d, s = bloc["decoupage"], bloc["sortie"]
        val = s["validation"]
        cible_val = np.array(val["cible"])
        h_val = {}
        s2 = {}
        for nom, cle in (("Persistance", "persistance_log"), ("HAR-RV", "har_log")):
            s2[nom], biais = s2_et_biais(cible_val, np.array(val[cle]))
        moyenne_xgb_val = np.mean(np.array(val["xgboost_log_par_graine"]), axis=0)
        s2["XGBoost"], biais_xgb = s2_et_biais(cible_val, moyenne_xgb_val)
        coef = s["har_coefficients"]
        controles["har"].append({"decoupage": d["nom"], "constante": coef[0], "jour": coef[1], "semaine": coef[2], "mois": coef[3],
                                 "somme_pentes": coef[1] + coef[2] + coef[3], "s2": s2["HAR-RV"]})
        g = s["garch"]
        controles["garch"].append({"decoupage": d["nom"], **g["params"], "alpha_plus_beta": g["params"]["alpha"] + g["params"]["beta"],
                                   "facteur": g["facteur"], "convergence": g["convergence"],
                                   "ecart_recurrence_arch": g["ecart_recurrence_arch"]})
        controles["xgboost_validation"].append({"decoupage": d["nom"], "moyenne_residus_log": biais_xgb, "s2": s2["XGBoost"],
                                                "arbres_par_graine": s["xgboost_arbres"]})
        if "evaluation" not in s:
            continue
        ev = s["evaluation"]
        dates = [dt.date.fromisoformat(x) for x in ev["date_cible"]]
        G.refuser_si_test(dates, "évaluation des baselines")
        cible = np.array(ev["cible"])
        table = pd.DataFrame({"date_cible": dates, "pli": d["nom"], "cible": cible})
        table["Persistance"] = E.variance_depuis_log(ev["persistance_log"], s2["Persistance"])
        table["HAR-RV"] = E.variance_depuis_log(ev["har_log"], s2["HAR-RV"])
        table["GARCH(1,1)"] = np.array(ev["garch_variance"])
        table["XGBoost"] = E.variance_depuis_log(np.mean(np.array(ev["xgboost_log_par_graine"]), axis=0), s2["XGBoost"])
        for k, (pv, pe) in enumerate(zip(val["xgboost_log_par_graine"], ev["xgboost_log_par_graine"])):
            s2_g, _ = s2_et_biais(cible_val, np.array(pv))
            table[f"XGBoost graine {k}"] = E.variance_depuis_log(pe, s2_g)
        lignes.append(table)
    return pd.concat(lignes, ignore_index=True), controles


def resultats_actif(table: pd.DataFrame, regles: dict) -> dict:
    G.refuser_si_test(table["date_cible"], "résultats des baselines")
    sortie = {"modeles": {}, "diebold_mariano": {}}
    pertes_modele = {m: pertes(table["cible"].to_numpy(), table[m].to_numpy()) for m in MODELES}
    for m in MODELES:
        res = {"reunis": resume_pertes(pertes_modele[m], regles), "par_pli": {}, "crises": {}}
        for pli, groupe in table.groupby("pli", sort=False):
            res["par_pli"][pli] = resume_pertes(pertes(groupe["cible"].to_numpy(), groupe[m].to_numpy()))
        for nom, c in regles["crises"].items():
            dedans = ((table["date_cible"] >= c["debut"]) & (table["date_cible"] <= c["fin"])).to_numpy()
            res["crises"][nom] = resume_pertes({k: v[dedans] for k, v in pertes_modele[m].items()})
        sortie["modeles"][m] = res
    graines = [k for k in table.columns if k.startswith("XGBoost graine")]
    par_graine = [resume_pertes(pertes(table["cible"].to_numpy(), table[k].to_numpy())) for k in graines]
    sortie["modeles"]["XGBoost"]["par_graine"] = {
        mesure: {"valeurs": [g[mesure] for g in par_graine], "moyenne": float(np.mean([g[mesure] for g in par_graine])),
                 "ecart_type": float(np.std([g[mesure] for g in par_graine], ddof=1))} for mesure in ("qlike", "rmse", "mae")}
    ref = pertes_modele["HAR-RV"]["qlike"]
    for m in ("GARCH(1,1)", "XGBoost"):
        sortie["diebold_mariano"][m] = E.diebold_mariano(pertes_modele[m]["qlike"], ref)
    sortie["diebold_mariano_descriptif"] = {
        "HAR-RV contre persistance": E.diebold_mariano(ref, pertes_modele["Persistance"]["qlike"])}
    selectionnables = ["HAR-RV", "GARCH(1,1)", "XGBoost"]
    # Précision du 2026-11-16, décidée APRÈS avoir vu les résultats : les deux définitions sont calculées ;
    # si elles diffèrent, la définition littérale de la règle (moyenne des QLIKE moyens par pli) s'applique.
    for m in MODELES:
        sortie["modeles"][m]["qlike_moyenne_des_plis"] = float(np.mean([v["qlike"] for v in sortie["modeles"][m]["par_pli"].values()]))
    jours_reunis = sorted(selectionnables, key=lambda m: sortie["modeles"][m]["reunis"]["qlike"])
    par_pli = sorted(selectionnables, key=lambda m: sortie["modeles"][m]["qlike_moyenne_des_plis"])
    sortie["classement"] = {"jours_reunis": jours_reunis, "moyenne_des_plis": par_pli, "identiques": jours_reunis == par_pli,
                            "applique": par_pli}
    sortie["classement_provisoire"] = par_pli
    q_har, q_xgb = sortie["modeles"]["HAR-RV"]["reunis"]["qlike"], sortie["modeles"]["XGBoost"]["reunis"]["qlike"]
    sortie["xgboost_gain_relatif_qlike"] = (q_har - q_xgb) / q_har
    return sortie


def figure_previsions(actif: str, table: pd.DataFrame, regles: dict, chemin: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    import exploration as X
    G.refuser_si_test(table["date_cible"], "figure des prévisions")
    a = math.sqrt(regles["cible"]["annualisation_jours"])
    dates = pd.to_datetime([str(d) for d in table["date_cible"]])
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(dates, np.exp(table["cible"]) * a, color="#999999", linewidth=0.6, label="RV réalisée")
    ax.plot(dates, np.sqrt(table["HAR-RV"]) * a, color=X.COULEURS[actif], linewidth=1.0, label="Prévision HAR-RV")
    ax.plot(dates, np.sqrt(table["XGBoost"]) * a, color="#16A34A", linewidth=1.0, alpha=0.8, label="Prévision XGBoost")
    for nom, c in regles["crises"].items():
        ax.axvspan(pd.Timestamp(c["debut"]), pd.Timestamp(c["fin"]) + pd.Timedelta(days=1), color="#999999", alpha=0.2,
                   label="Crises" if nom == next(iter(regles["crises"])) else None)
    ax.yaxis.set_major_formatter(X.FORMAT_POURCENT)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_ylabel("Volatilité annualisée")
    ax.set_xlabel("Date de la cible (5 plis annuels, développement)")
    ax.set_title(f"{X.NOMS[actif]} : RV réalisée et prévisions à un jour de HAR-RV et de XGBoost")
    ax.legend(loc="upper right")
    ax.grid(alpha=0.3)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    X._finir(fig, chemin)


def _sha256(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def executer(regles: dict) -> dict:
    C.verifier_secteur(contexte="baselines")
    C.verifier_memoire_libre(regles)
    manifeste_variables = json.loads((C.RACINE / regles["variables"]["sorties"]["manifeste"]).read_text(encoding="utf-8"))
    cle_donnees = manifeste_variables["empreinte_contenu_sha256"][:12]
    rapport = {"version": VERSION, "plis": [[str(d["evaluation"][0]), str(d["evaluation"][1])] for d in R.decoupages(regles)[:-1]],
               "depend_de": {"variables_empreinte_contenu": manifeste_variables["empreinte_contenu_sha256"],
                             "regles_sha256": _sha256(R.CHEMIN_REGLES)},
               "actifs": {}}
    durees = {}
    modeles_test_final = {}
    for actif in regles["donnees"]["actifs"]:
        debut = time.perf_counter()
        bougies = V.lire_bougies(C.DOSSIER_TRAITE / f"{actif}_5m.parquet")
        calcul = calculer_actif(actif, bougies, regles, cle_donnees)
        durees[actif] = time.perf_counter() - debut   # affichées, pas écrites : la reprise saute les unités déjà faites
        table, controles = series_evaluation(calcul, regles)
        DOSSIER_PREVISIONS.mkdir(parents=True, exist_ok=True)
        table.to_csv(DOSSIER_PREVISIONS / f"{actif}_baselines.csv", index=False)       # ignoré par Git
        res = resultats_actif(table, regles)
        reglage = calcul["reglage"]
        res["controles"] = controles
        res["xgboost_reglage"] = {"combinaison_retenue": reglage["combinaison_retenue"], "numero": reglage["meilleure"],
                                  "tirages_ecartes": reglage["tirages_ecartes"],
                                  "mse_log_validation": [s["mse_log_validation"] for s in reglage["scores"]],
                                  "arbres": [s["arbres"] for s in reglage["scores"]]}
        rapport["actifs"][actif] = res
        figure_previsions(actif, table, regles, C.RACINE / "figures" / f"figure_4_previsions_{actif}.png")
        dossier = DOSSIER_MODELES / actif
        modeles_test_final[actif] = {f.name: _sha256(f) for f in sorted(dossier.glob("*.json"))}
    C.ecrire_texte(CHEMIN_MANIFESTE_MODELES, C.texte_json({
        "description": "Empreintes SHA-256 des modèles du test final (enregistrés dans sorties/, ignoré par Git) ; "
                       "aucune prévision n'a été faite sur le test.", "modeles": modeles_test_final}))
    mesures = json.loads((C.DOSSIER_RAPPORTS / "mesures_entrainement.json").read_text(encoding="utf-8"))
    rapport["estimation_xgboost_s"] = mesures["xgboost_total_estime_s"]
    C.ecrire_texte(CHEMIN_JSON, C.texte_json(rapport))
    C.ecrire_texte(CHEMIN_MD, rapport_markdown(rapport, regles))
    print("Durées par actif (unités déjà faites sautées) : "
          + ", ".join(f"{a} {C.nombre_fr(s, 1)} s" for a, s in durees.items()))
    return rapport


# --- Rapport Markdown généré ----------------------------------------------------------------------

def _n(x: float, d: int = 3) -> str:
    return C.nombre_fr(x, d).replace("-", "−")


def rapport_markdown(rapport: dict, regles: dict) -> str:
    lignes = ["# Résultats des baselines (développement, 5 plis annuels)", "",
              "Fichier généré par `src/baselines.py` à partir de `rapports/baselines.json` : ne pas le modifier à la main.", "",
              f"- Plis évalués (dates de cible) : du {rapport['plis'][0][0]} au {rapport['plis'][-1][1]}. Le test final est fermé : "
              "aucune prévision n'y a été faite.",
              "- QLIKE sur la variance (forme de Patton), RMSE et MAE sur RV ; intervalles à 95 % par bootstrap à blocs mobiles.",
              "- La persistance est une référence descriptive : hors de la sélection et des tests principaux.",
              "- XGBoost : prévision = moyenne des log de ses 3 graines (petit ensemble : léger avantage écrit dans les règles).", ""]
    for actif, res in rapport["actifs"].items():
        lignes += [f"## {actif}", "", "### Plis réunis", "",
                   "| Modèle | QLIKE [IC 95 %] | RMSE [IC 95 %] | MAE [IC 95 %] |", "|---|---|---|---|"]
        for m in MODELES:
            r = res["modeles"][m]["reunis"]
            lignes.append(f"| {m}{' (descriptive)' if m == 'Persistance' else ''} | {_n(r['qlike'])} [{_n(r['qlike_intervalle']['bas'])} ; "
                          f"{_n(r['qlike_intervalle']['haut'])}] | {_n(r['rmse'], 4)} [{_n(r['rmse_intervalle']['bas'], 4)} ; "
                          f"{_n(r['rmse_intervalle']['haut'], 4)}] | {_n(r['mae'], 4)} [{_n(r['mae_intervalle']['bas'], 4)} ; "
                          f"{_n(r['mae_intervalle']['haut'], 4)}] |")
        pg = res["modeles"]["XGBoost"]["par_graine"]
        lignes += ["", f"XGBoost par graine (chacune avec son propre s²) : QLIKE moyen {_n(pg['qlike']['moyenne'])} "
                   f"(écart-type {_n(pg['qlike']['ecart_type'], 4)}), RMSE {_n(pg['rmse']['moyenne'], 4)}, MAE {_n(pg['mae']['moyenne'], 4)}.", ""]
        lignes += ["### Diebold-Mariano contre HAR-RV (plis réunis, QLIKE)", "",
                   "| Modèle | Différence moyenne | Statistique (HLN) | p-valeur | Jours | Retards HAC | Sens | Significatif à 5 % |",
                   "|---|---:|---:|---:|---:|---:|---|---|"]
        seuil = regles["evaluation"]["diebold_mariano"]["seuil"]
        for m, t in list(res["diebold_mariano"].items()) + [(f"{k} (descriptif)", v) for k, v in res["diebold_mariano_descriptif"].items()]:
            p = t["p_valeur"]
            lignes.append(f"| {m} | {_n(t['moyenne_difference'], 4)} | {_n(t['statistique'], 2)} | "
                          f"{_n(p, 4) if p >= 0.0001 else '< 0,0001'} | {C.nombre_fr(t['jours'])} | {t['retards_hac']} | {t['sens']} | "
                          f"{'oui' if p < seuil else 'non'} |")
        lignes += ["", "Pour le test descriptif, le « modèle » est HAR-RV et la « référence » est la persistance.", "",
                   "### QLIKE par pli", "", "| Modèle | " + " | ".join(res["modeles"]["HAR-RV"]["par_pli"]) + " |",
                   "|---|" + "---:|" * len(res["modeles"]["HAR-RV"]["par_pli"])]
        for m in MODELES:
            lignes.append(f"| {m} | " + " | ".join(_n(v["qlike"]) for v in res["modeles"][m]["par_pli"].values()) + " |")
        lignes += ["", "### Crises (descriptif, sans test)", "", "| Modèle | " + " | ".join(regles["crises"]) + " |",
                   "|---|" + "---:|" * len(regles["crises"])]
        for m in MODELES:
            lignes.append(f"| {m} (QLIKE) | " + " | ".join(_n(res["modeles"][m]["crises"][c]["qlike"]) for c in regles["crises"]) + " |")
        cl = res["classement"]
        lignes += ["", "### Classement provisoire (persistance exclue)", "",
                   "| Définition | Classement |", "|---|---|",
                   f"| QLIKE moyen sur tous les jours évalués réunis | {' < '.join(cl['jours_reunis'])} |",
                   f"| Moyenne des QLIKE moyens par pli (définition littérale de la règle) | {' < '.join(cl['moyenne_des_plis'])} |", "",
                   ("Les deux définitions donnent le même classement." if cl["identiques"] else
                    "Les deux définitions donnent des classements différents : la définition littérale (moyenne par pli) s'applique."),
                   "Précision décidée après avoir vu les résultats des baselines (voir `docs/CHOIX.md`). "
                   "Le classement définitif viendra après le deep learning.", "",
                   "### Vérification de l'exception 2 : moyenne des résidus en log d'XGBoost sur la validation interne", "",
                   "| Découpage | Moyenne des résidus (cible − prévision) | s² |", "|---|---:|---:|"]
        for x in res["controles"]["xgboost_validation"]:
            lignes.append(f"| {x['decoupage']} | {_n(x['moyenne_residus_log'], 3)} | {_n(x['s2'], 3)} |")
        lignes += ["", "Une moyenne négative signifie que XGBoost prévoit trop haut sur la validation interne.", "",
                   f"Figure : `figures/figure_4_previsions_{actif}.png`.", ""]
    lignes += lecture_des_resultats(rapport, regles)
    return "\n".join(lignes) + "\n"


def lecture_des_resultats(rapport: dict, regles: dict) -> list[str]:
    """Phrases d'interprétation, chacune conditionnée par les valeurs du JSON."""
    seuil = regles["evaluation"]["diebold_mariano"]["seuil"]
    lignes = ["## Lecture des résultats", "", "Chaque phrase ci-dessous est générée à partir des valeurs de `rapports/baselines.json`.", ""]
    for actif, res in rapport["actifs"].items():
        nom = actif.replace("USDT", "")
        dm = res["diebold_mariano"]
        h = res["diebold_mariano_descriptif"]["HAR-RV contre persistance"]
        if h["p_valeur"] < seuil and h["moyenne_difference"] < 0:
            lignes.append(f"- {nom} : HAR-RV fait significativement mieux que la persistance (test descriptif) : "
                          "le modèle apporte plus que « demain comme aujourd'hui ».")
        else:
            lignes.append(f"- {nom} : HAR-RV ne fait pas significativement mieux que la persistance (test descriptif).")
        g = dm["GARCH(1,1)"]
        if g["p_valeur"] < seuil:
            lignes.append(f"- {nom} : GARCH(1,1) fait significativement {'moins bien' if g['moyenne_difference'] > 0 else 'mieux'} "
                          "que HAR-RV en QLIKE. Explication possible, non démontrée : GARCH n'utilise que les rendements "
                          "journaliers, sans l'information des données de 5 minutes." if g["moyenne_difference"] > 0 else
                          f"- {nom} : GARCH(1,1) fait significativement mieux que HAR-RV en QLIKE.")
        else:
            lignes.append(f"- {nom} : l'écart entre GARCH(1,1) et HAR-RV n'est pas significatif.")
        x = dm["XGBoost"]
        if x["p_valeur"] < seuil:
            lignes.append(f"- {nom} : XGBoost fait significativement {'mieux' if x['moyenne_difference'] < 0 else 'moins bien'} que HAR-RV.")
        else:
            lignes.append(f"- {nom} : XGBoost a un QLIKE moyen {'plus faible' if x['moyenne_difference'] < 0 else 'plus élevé'} "
                          f"que HAR-RV, mais l'écart n'est pas significatif (p-valeur {_n(x['p_valeur'], 2)}) : on ne peut pas "
                          "dire qu'XGBoost fait mieux.")
        crises = [c for c in regles["crises"]
                  if res["modeles"]["Persistance"]["crises"][c]["qlike"] < res["modeles"]["HAR-RV"]["crises"][c]["qlike"]]
        if crises:
            noms = {"covid": "le Covid", "terra_luna": "Terra-Luna", "ftx": "FTX"}
            liste = [noms.get(c, c) for c in crises]
            texte = liste[0] if len(liste) == 1 else ", ".join(liste[:-1]) + " et " + liste[-1]
            lignes.append(f"- {nom} : pendant {texte}, la persistance a un QLIKE plus faible que HAR-RV (descriptif, sans "
                          "test). Explication possible, non démontrée : quand la volatilité change brutalement, la valeur de la "
                          "veille suit mieux que les moyennes sur 7 et 30 jours.")
        q, r = res["modeles"]["XGBoost"]["reunis"], res["modeles"]["HAR-RV"]["reunis"]
        if (q["qlike"] < r["qlike"]) != (q["rmse"] < r["rmse"]):
            lignes.append(f"- {nom} : XGBoost est {'meilleur' if q['qlike'] < r['qlike'] else 'moins bon'} que HAR-RV en QLIKE "
                          f"mais {'moins bon' if q['qlike'] < r['qlike'] else 'meilleur'} en RMSE. Les deux mesures ne jugent pas "
                          "la même chose : QLIKE punit surtout une variance prévue trop basse, en relatif ; RMSE punit les grandes "
                          "erreurs en niveau, donc surtout les jours très agités.")
    return lignes + [""]


def main() -> int:
    C.proteger_sortie()
    regles = R.charger_regles()
    debut = time.perf_counter()
    try:
        rapport = executer(regles)
    except (G.ErreurTestAveugle, C.ErreurAlimentation, C.ErreurMemoire, ErreurBaselines) as erreur:
        print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1
    for actif, res in rapport["actifs"].items():
        q = {m: res["modeles"][m]["reunis"]["qlike"] for m in MODELES}
        print(f"{actif} | QLIKE : " + ", ".join(f"{m} {_n(v)}" for m, v in q.items())
              + f" | gain relatif d'XGBoost sur HAR-RV : {_n(100 * res['xgboost_gain_relatif_qlike'], 1)} %")
    print(f"Durée : {C.nombre_fr(time.perf_counter() - debut, 1)} s | mémoire maximale : {C.nombre_fr(C.memoire_max_mo(), 1)} Mo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
