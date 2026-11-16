"""Tests de l'évaluation et des baselines (exemples calculés à la main, données synthétiques, témoins)."""

import datetime as dt
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

import baselines as B  # noqa: E402
import evaluation as E  # noqa: E402
import garde as G  # noqa: E402
import regles as R  # noqa: E402

REGLES = R.charger_regles()
D = dt.date.fromisoformat
UTC = "UTC"


# --- QLIKE, RMSE, MAE -------------------------------------------------------------------------

def test_qlike_nul_si_prevision_exacte_et_valeur_a_la_main():
    assert E.qlike([0.02], [0.0004])[0] == pytest.approx(0.0, abs=1e-15)
    # RV² / h = 2 : 2 − ln 2 − 1 = 0,306852819…
    assert E.qlike([0.02], [0.0002])[0] == pytest.approx(1 - math.log(2), rel=1e-12)


def test_temoin_qlike_minimum_atteint_a_la_valeur_exacte():
    h = np.array([0.0004 * f for f in (0.5, 0.9, 1.0, 1.1, 2.0)])
    pertes = E.qlike(np.full(5, 0.02), h)
    assert np.argmin(pertes) == 2 and (pertes[[0, 1, 3, 4]] > 0).all()


def test_qlike_refuse_une_variance_nulle():
    with pytest.raises(ValueError):
        E.qlike([0.02], [0.0])


def test_rmse_mae_a_la_main():
    rv, sigma = np.array([0.02, 0.03]), np.array([0.01, 0.05])
    assert E.rmse(rv, sigma) == pytest.approx(math.sqrt((0.0001 + 0.0004) / 2), rel=1e-12)
    assert E.mae(rv, sigma) == pytest.approx(0.015, rel=1e-12)


def test_variance_depuis_log():
    assert E.variance_depuis_log([math.log(0.02)], 0.0)[0] == pytest.approx(0.0004, rel=1e-12)
    assert E.variance_depuis_log([0.0], 0.5)[0] == pytest.approx(math.e, rel=1e-12)


# --- Diebold-Mariano -----------------------------------------------------------------------------

def test_diebold_mariano_a_la_main():
    # d = 1, 2, 3, 4, 5 ; moyenne 3 ; T = 5 ; retards = floor(4 × 0,05^(2/9)) = 2
    # écarts : −2, −1, 0, 1, 2 ; γ0 = 10/5 = 2 ; γ1 = (2 + 0 + 0 + 2)/5 = 0,8 ; γ1 = 0,8 ; γ2 = (0 − 1 + 0)/5 = −0,2
    # variance de long terme = 2 + 2 × (2/3 × 0,8 + 1/3 × (−0,2)) = 2,9333… ; DM = 3 / racine(2,9333/5)
    # correction HLN (h = 1) : racine((5 + 1 − 2)/5) = racine(0,8)
    t = E.diebold_mariano([1, 2, 3, 4, 5], [0, 0, 0, 0, 0])
    lrv = 2 + 2 * (2 / 3 * 0.8 + 1 / 3 * -0.2)
    attendu = 3 / math.sqrt(lrv / 5) * math.sqrt(0.8)
    assert t["retards_hac"] == 2
    assert t["statistique"] == pytest.approx(attendu, rel=1e-12)
    assert t["p_valeur"] == pytest.approx(2 * stats.t.sf(attendu, 4), rel=1e-12)
    assert t["sens"] == "référence meilleure"


def test_temoin_diebold_mariano_sans_hac_different():
    """Sans correction HAC (retards = 0), la statistique change : le test ci-dessus l'aurait vu."""
    sans = E.diebold_mariano([1, 2, 3, 4, 5], [0] * 5, retards=0)["statistique"]
    assert sans == pytest.approx(3 / math.sqrt(2 / 5) * math.sqrt(0.8), rel=1e-12)
    assert sans != pytest.approx(E.diebold_mariano([1, 2, 3, 4, 5], [0] * 5)["statistique"], rel=1e-6)


def test_diebold_mariano_sens():
    rng = np.random.default_rng(0)
    bonne, mauvaise = rng.uniform(0, 1, 500), rng.uniform(0.5, 1.5, 500)
    t = E.diebold_mariano(bonne, mauvaise)
    assert t["sens"] == "modèle meilleur" and t["p_valeur"] < 0.05


# --- Bootstrap par blocs ---------------------------------------------------------------------

def test_bootstrap_serie_constante_et_graine_fixe():
    r = E.bootstrap_moyenne(np.full(100, 3.0), 200, 20, 42)
    assert (r["bas"], r["moyenne"], r["haut"]) == (3.0, 3.0, 3.0)
    x = np.random.default_rng(1).normal(size=300)
    assert E.bootstrap_moyenne(x, 200, 20, 42) == E.bootstrap_moyenne(x, 200, 20, 42)


def test_temoin_blocs_plus_larges_que_tirages_independants_sur_une_serie_dependante():
    """Sur une série très autocorrélée, des blocs de 20 jours donnent un intervalle plus large que des
    tirages jour par jour (blocs de 1), qui ignorent la dépendance."""
    rng = np.random.default_rng(2)
    x = np.zeros(2000)
    for t in range(1, 2000):
        x[t] = 0.9 * x[t - 1] + rng.normal()
    large = E.bootstrap_moyenne(x, 1000, 20, 42)
    etroit = E.bootstrap_moyenne(x, 1000, 1, 42)
    assert large["haut"] - large["bas"] > 2 * (etroit["haut"] - etroit["bas"])


# --- Données synthétiques ------------------------------------------------------------------------

DEBUT, FIN = D("2018-01-01"), D("2020-12-31")
PLI1 = R.decoupages(REGLES)[0]
COMBINAISON = {"max_depth": 3, "learning_rate": 0.05, "subsample": 0.8, "colsample_bytree": 0.8, "min_child_weight": 5,
               "reg_lambda": 1.0}
OPTIONS = {"arbres_max": 40, "patience": 10}


def bougies_synthetiques(graine=0) -> pd.DataFrame:
    """Bougies de 5 minutes aléatoires, avec une volatilité qui varie lentement (pour un GARCH non dégénéré)."""
    dates = pd.date_range(pd.Timestamp(DEBUT, tz=UTC), pd.Timestamp(FIN + dt.timedelta(days=1), tz=UTC),
                          freq="5min", inclusive="left").astype("datetime64[us, UTC]")
    rng = np.random.default_rng(graine)
    n = len(dates)
    jours = n // 288
    vol_jour = np.exp(np.cumsum(rng.normal(0, 0.15, jours)) * 0.3) * 0.002
    vol = np.repeat(vol_jour, 288)[:n]
    cloture = 100 * np.exp(np.cumsum(rng.normal(0, 1, n) * vol))
    ouverture = np.r_[100.0, cloture[:-1]]
    return pd.DataFrame({
        "date_ouverture": dates, "ouverture": ouverture,
        "plus_haut": np.maximum(ouverture, cloture) * (1 + np.abs(rng.normal(0, 0.0005, n))),
        "plus_bas": np.minimum(ouverture, cloture) * (1 - np.abs(rng.normal(0, 0.0005, n))),
        "cloture": cloture, "volume_cotation": rng.uniform(1e5, 1e6, n)})


BOUGIES = bougies_synthetiques()


def previsions(b: pd.DataFrame, estimer=B.estimer_garch) -> dict:
    exemples, journalier = B.donnees_actif(b, REGLES, DEBUT, FIN)
    sortie = B.previsions_decoupage(exemples, journalier, REGLES, PLI1, COMBINAISON, [11, 22, 33], OPTIONS, estimer=estimer)
    sortie.pop("_modeles_xgb")
    return sortie


REFERENCE = previsions(BOUGIES)


def _origines(sortie: dict) -> list[dt.date]:
    return [D(x) - dt.timedelta(days=1) for x in sortie["evaluation"]["date_cible"]]


def ecarts_avenir(calcul, reference: dict, jours: list[dt.date]) -> list[str]:
    """Modifie toutes les bougies après la fin de J (× 10 avec bruit), recalcule, compare les prévisions
    des origines <= J au bit près."""
    rng = np.random.default_rng(5)
    ecarts = []
    for j in jours:
        b = BOUGIES.copy()
        apres = (b["date_ouverture"] >= pd.Timestamp(j + dt.timedelta(days=1), tz=UTC)).to_numpy()
        f = 10 * (1 + rng.uniform(-0.5, 0.5, int(apres.sum())))
        for k in ("ouverture", "plus_haut", "plus_bas", "cloture", "volume_cotation"):
            b.loc[apres, k] = b.loc[apres, k].to_numpy() * f
        nouveau = calcul(b)
        garder = np.array([o <= j for o in _origines(reference)])
        assert sum(garder) > 0
        for cle in ("persistance_log", "har_log", "garch_variance"):
            a = np.array(reference["evaluation"][cle])[garder]
            n = np.array(nouveau["evaluation"][cle])[: len(a)]
            if not np.array_equal(a.view("<i8"), n.view("<i8")):
                ecarts.append(f"{j} : {cle}")
        for k, (a, n) in enumerate(zip(reference["evaluation"]["xgboost_log_par_graine"], nouveau["evaluation"]["xgboost_log_par_graine"])):
            a, n = np.array(a)[garder], np.array(n)[: garder.sum()]
            if not np.array_equal(a.view("<i8"), n.view("<i8")):
                ecarts.append(f"{j} : xgboost graine {k}")
    return ecarts


JOURS_J = [D("2020-03-15"), D("2020-06-30")]


def test_avenir_modifie_aucune_prevision_passee_ne_change():
    assert ecarts_avenir(previsions, REFERENCE, JOURS_J) == []


def test_garch_backcast_sur_toute_la_serie_sans_effet_mesurable_sur_l_evaluation():
    """Le témoin demandé (backcast calculé sur toute la série) n'est PAS détectable : son effet décroît comme
    β^t et vaut moins que la précision des nombres après environ 730 jours. On le prouve ici, au bit près."""
    def estimer_tricheur(journalier, decoupage, regles):
        modele = B.estimer_garch(journalier, decoupage, regles)
        r = journalier["rendement"].dropna().to_numpy() * B.ECHELLE_GARCH
        modele["backcast"] = float(np.mean((r - modele["params"]["mu"]) ** 2))   # toute la série : avenir compris
        return modele

    tricheur = previsions(BOUGIES, estimer_tricheur)
    assert tricheur["garch"]["backcast"] != REFERENCE["garch"]["backcast"]
    assert REFERENCE["garch"]["params"]["beta"] ** 730 < 1e-16
    assert np.array_equal(np.array(tricheur["evaluation"]["garch_variance"]), np.array(REFERENCE["evaluation"]["garch_variance"]))


def test_temoin_garch_avec_facteur_d_echelle_sur_toute_la_serie_detecte():
    """Témoin détectable : un facteur d'échelle calculé avec les RV² de toute la série (avenir compris)."""
    def estimer_tricheur(journalier, decoupage, regles):
        modele = B.estimer_garch(journalier, decoupage, regles)
        modele["facteur"] = float(np.nanmean(journalier["rv"].to_numpy() ** 2)) * 1e4   # toute la série
        return modele

    calcul = lambda b: previsions(b, estimer_tricheur)  # noqa: E731
    ecarts = ecarts_avenir(calcul, calcul(BOUGIES), JOURS_J)
    assert ecarts and all("garch_variance" in e for e in ecarts), ecarts


# --- HAR, GARCH, XGBoost -------------------------------------------------------------------------

def test_har_retrouve_des_coefficients_exacts():
    rng = np.random.default_rng(3)
    ex = pd.DataFrame({k: rng.normal(size=200) for k in ("log_rv_1", "log_rv_7", "log_rv_30")})
    ex["cible"] = -0.5 + 0.4 * ex["log_rv_1"] + 0.3 * ex["log_rv_7"] + 0.2 * ex["log_rv_30"]
    assert B.ajuster_har(ex, REGLES) == pytest.approx([-0.5, 0.4, 0.3, 0.2], abs=1e-12)


def test_recurrence_garch_egale_a_arch_sur_l_ajustement():
    modele = REFERENCE["garch"]
    assert modele["convergence"] == 0
    assert modele["ecart_recurrence_arch"] < 1e-9


def test_garch_a_la_main_sur_trois_jours():
    p = {"mu": 0.1, "omega": 0.2, "alpha": 0.1, "beta": 0.8, "nu": 5.0}
    s2 = B.variances_garch(np.array([1.1, -0.9, 0.1]), p, backcast=2.0)
    # σ²0 = 0,2 + 0,9 × 2 = 2,0 ; σ²1 = 0,2 + 0,1 × 1² + 0,8 × 2 = 1,9 ; σ²2 = 0,2 + 0,1 × 1² + 0,8 × 1,9 = 1,82
    # σ²3 (prévision) = 0,2 + 0,1 × 0² + 0,8 × 1,82 = 1,656
    assert s2 == pytest.approx([2.0, 1.9, 1.82, 1.656], rel=1e-12)


def test_combinaisons_deterministes_et_valides():
    a, ecartes_a = B.tirer_combinaisons(REGLES, "xgboost", 12)
    b, _ = B.tirer_combinaisons(REGLES, "xgboost", 12)
    assert a == b and len(a) == 12 and ecartes_a == 0
    e = REGLES["entrainement"]["espaces"]["xgboost"]
    for c in a:
        assert c["max_depth"] in e["max_depth"] and e["learning_rate"]["min"] <= c["learning_rate"] <= e["learning_rate"]["max"]


def test_tirages_incoherents_ecartes_et_remplaces_de_facon_deterministe():
    valide = lambda c: c["hidden_continuous_size"] <= c["hidden_size"]  # noqa: E731
    a, ecartes = B.tirer_combinaisons(REGLES, "tft", 12, valide)
    b, ecartes_b = B.tirer_combinaisons(REGLES, "tft", 12, valide)
    assert a == b and ecartes == ecartes_b and len(a) == 12 and all(valide(c) for c in a)


def test_s2_variance_centree_et_biais():
    s2, biais = B.s2_et_biais(np.array([1.0, 2.0, 3.0]), np.array([0.0, 0.0, 0.0]))
    assert (s2, biais) == (pytest.approx(2 / 3), pytest.approx(2.0))


# --- Garde du test aveugle --------------------------------------------------------------------

def test_temoin_resultats_refuses_sur_le_test():
    table = pd.DataFrame({"date_cible": [D("2025-01-01")], "pli": ["x"], "cible": [math.log(0.02)]})
    for m in B.MODELES:
        table[m] = [0.0004]
    with pytest.raises(G.ErreurTestAveugle):
        B.resultats_actif(table, REGLES)


def test_temoin_prevision_refusee_sur_le_test_final():
    exemples = pd.DataFrame({"date_cible": [D("2025-01-02")], "date_origine": [D("2025-01-01")], "cible": [0.0]})
    final = R.decoupages(REGLES)[-1]
    with pytest.raises(G.ErreurTestAveugle):
        B.previsions_decoupage(exemples, pd.DataFrame(), REGLES, final, COMBINAISON, [0])
