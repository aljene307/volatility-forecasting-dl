"""Tests de la comparaison de tous les modèles (Holm, alerte, assemblage des graines des réseaux)."""

import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

import comparer as K  # noqa: E402
import entrainer as T  # noqa: E402
import evaluation as EV  # noqa: E402
import regles as R  # noqa: E402
import reprise as P  # noqa: E402

REGLES = R.charger_regles()


def test_holm_a_la_main():
    p = {"a": 0.01, "b": 0.04, "c": 0.03}
    # rangées : a (×3 = 0,03), c (×2 = 0,06), b (×1 = 0,04, mais le maximum déjà rencontré est 0,06)
    assert EV.holm(p) == pytest.approx({"a": 0.03, "b": 0.06, "c": 0.06}, abs=1e-12)
    assert EV.holm({"x": 0.6, "y": 0.7}) == {"x": 1.0, "y": 1.0}


def test_holm_identique_a_statsmodels():
    from statsmodels.stats.multitest import multipletests
    rng = np.random.default_rng(3)
    for _ in range(20):
        valeurs = rng.uniform(0, 0.2, 7)
        attendu = multipletests(valeurs, method="holm")[1]
        obtenu = EV.holm({str(k): v for k, v in enumerate(valeurs)})
        assert np.allclose([obtenu[str(k)] for k in range(7)], attendu, atol=1e-12, rtol=0)


def test_temoin_holm_different_des_p_brutes():
    p = {"a": 0.01, "b": 0.04, "c": 0.03}
    assert EV.holm(p) != p


def _resultats_avec_gain(gain: float) -> dict:
    g = {m: {"jours_reunis": 0.0, "moyenne_des_plis": 0.0} for m in K.SELECTIONNABLES}
    g["LSTM"] = {"jours_reunis": 0.0, "moyenne_des_plis": gain}
    return {"BTCUSDT": {"gain_relatif_qlike": g}}


def test_alerte_au_dela_du_seuil_des_regles():
    seuil = REGLES["evaluation"]["controles_fuite"]["seuil_alerte_gain_qlike"]
    assert seuil == 0.20
    K.verifier_alerte(_resultats_avec_gain(seuil), REGLES)              # exactement au seuil : pas d'arrêt
    with pytest.raises(K.AlerteFuite, match="fuite"):
        K.verifier_alerte(_resultats_avec_gain(seuil + 1e-4), REGLES)


def test_robustesse_gain_par_graine_et_par_pli_a_la_main():
    """Table synthétique : la graine k prévoit RV² × (1 + 0,2 k) ; HAR-RV prévoit RV² × 1,5 ; le LSTM bat HAR-RV
    dans le pli A seulement (variance exacte), et fait pire dans le pli B (× 3)."""
    rng = np.random.default_rng(4)
    n = 40
    dates = [D("2020-01-01") + dt.timedelta(days=k) for k in range(2 * n)]
    cible = rng.normal(-3.5, 0.4, 2 * n)
    v = np.exp(2 * cible)
    table = pd.DataFrame({"date_cible": dates, "pli": ["pli A"] * n + ["pli B"] * n, "cible": cible})
    for m in K.TOUS:
        table[m] = v * 1.5 * rng.uniform(0.8, 1.2, 2 * n)      # bruit : sinon la différence de Diebold-Mariano est nulle
    table["HAR-RV"] = v * 1.5
    table["LSTM"] = np.r_[v[:n], v[n:] * 3]
    for m in K.REGLES_MODELES:
        for k in range(3):
            table[f"{m} graine {k}"] = v * (1 + 0.2 * k)
    res = K.resultats_actif(table, REGLES)
    q = lambda h: float(np.mean(h - np.log(h) - 1))  # noqa: E731  (QLIKE si RV² / h est constant)
    h_har = q(np.full(n, 1 / 1.5))
    attendu = [(h_har - q(np.full(n, 1 / (1 + 0.2 * k)))) / h_har for k in range(3)]
    g = res["robustesse"]["gain_par_graine"]["LSTM"]
    assert g["graines"] == pytest.approx(attendu, abs=1e-12)
    assert g["effet_ensemble"] == pytest.approx(g["gain_de_la_moyenne_des_graines"] - np.mean(attendu), abs=1e-12)
    pli = res["robustesse"]["gain_par_pli"]["LSTM"]
    assert pli["pli A"] == pytest.approx(1.0, abs=1e-12)                      # QLIKE nul dans le pli A
    assert pli["pli B"] == pytest.approx((h_har - q(np.full(n, 1 / 3))) / h_har, abs=1e-12) and pli["pli B"] < 0


# --- Assemblage des graines des réseaux sur des unités synthétiques ---------------------------

D = dt.date.fromisoformat
DEC = {"nom": "pli test"}
VAL = [str(D("2019-07-01") + dt.timedelta(days=k)) for k in range(30)]
EVA = [str(D("2020-01-01") + dt.timedelta(days=k)) for k in range(25)]
CLE = "cle"


def _calcul(rng):
    return {"decoupages": [{"decoupage": DEC, "sortie": {
        "validation": {"date_cible": VAL, "cible": rng.normal(-3.5, 0.4, len(VAL)).tolist()},
        "evaluation": {"date_cible": EVA, "cible": rng.normal(-3.5, 0.4, len(EVA)).tolist()}}}]}


def _ecrire_unites(dossier, rng, decaler=False):
    previsions = {}
    for m in K.RESEAUX:
        for g in REGLES["modeles"]["graines_deep_learning"]:
            val, ev = rng.normal(-3.5, 0.3, len(VAL)), rng.normal(-3.5, 0.3, len(EVA))
            previsions[(m, g)] = (val, ev)
            dates_ev = EVA[1:] + ["2020-02-01"] if decaler and m == "GRU" and g == 1 else EVA
            P.ecrire_unite(dossier / "unites", T.id_pli("BTCUSDT", m, DEC["nom"], g, CLE), 0, {
                "validation": {"date_cible": VAL, "prevision_log": val.tolist()},
                "evaluation": {"date_cible": dates_ev, "prevision_log": ev.tolist()},
                "mse_log_validation": 0.1, "epoques": 30, "meilleure_epoque": 10})
    return previsions


def _table(calcul):
    s = calcul["decoupages"][0]["sortie"]["evaluation"]
    return pd.DataFrame({"date_cible": [D(x) for x in s["date_cible"]], "pli": DEC["nom"], "cible": s["cible"]})


def test_reseau_moyenne_des_log_des_graines_et_s2_de_la_moyenne(tmp_path):
    rng = np.random.default_rng(0)
    calcul = _calcul(rng)
    previsions = _ecrire_unites(tmp_path, rng)
    table, controles = K.ajouter_reseaux(_table(calcul), calcul, "BTCUSDT", REGLES, CLE, tmp_path)
    cible_val = np.array(calcul["decoupages"][0]["sortie"]["validation"]["cible"])
    graines = REGLES["modeles"]["graines_deep_learning"]
    for m in K.RESEAUX:
        moy_val = np.mean([previsions[(m, g)][0] for g in graines], axis=0)
        moy_ev = np.mean([previsions[(m, g)][1] for g in graines], axis=0)
        s2 = float(np.var(cible_val - moy_val))
        assert np.allclose(table[m], EV.variance_depuis_log(moy_ev, s2), rtol=1e-12, atol=0)
        assert controles[m][0]["s2"] == pytest.approx(s2, abs=1e-12)
        assert controles[m][0]["moyenne_residus_log"] == pytest.approx(float(np.mean(cible_val - moy_val)), abs=1e-12)
        s2_g0 = float(np.var(cible_val - previsions[(m, 0)][0]))
        assert np.allclose(table[f"{m} graine 0"], EV.variance_depuis_log(previsions[(m, 0)][1], s2_g0), rtol=1e-12, atol=0)


def test_temoin_dates_decalees_detectees(tmp_path):
    rng = np.random.default_rng(1)
    calcul = _calcul(rng)
    _ecrire_unites(tmp_path, rng, decaler=True)
    with pytest.raises(K.ErreurComparaison, match="dates d'évaluation"):
        K.ajouter_reseaux(_table(calcul), calcul, "BTCUSDT", REGLES, CLE, tmp_path)
