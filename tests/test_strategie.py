"""Tests de la stratégie de volatility targeting (données synthétiques, témoins)."""

import datetime as dt
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

import evaluation as EV  # noqa: E402
import regles as R  # noqa: E402
import strategie as S  # noqa: E402

REGLES = R.charger_regles()
D0 = dt.date(2020, 1, 1)
JOURS = [D0 + dt.timedelta(days=k) for k in range(90)]
ORIGINES = [D0 - dt.timedelta(days=1)] + JOURS                 # une décision possible chaque jour, veille comprise


def _cas(graine=0):
    rng = np.random.default_rng(graine)
    sigma = pd.Series(rng.uniform(0.01, 0.06, len(ORIGINES)), index=ORIGINES)
    valide = pd.Series(True, index=ORIGINES)
    r = rng.normal(0, 0.03, len(JOURS))
    return sigma, valide, r


def _valeur(sigma, valide, r, decalage):
    dec = S.decisions(sigma, valide, 0.6, REGLES)
    e = S.exposition_appliquee(dec, JOURS, decalage)
    return S.simuler(e, r, REGLES["strategie"]["frais"], REGLES)["valeur"]


def test_decision_de_j_n_agit_qu_a_partir_de_j_plus_1():
    """Changer la décision prise à la clôture de J ne doit changer aucune valeur du portefeuille jusqu'à J inclus."""
    sigma, valide, r = _cas()
    j = JOURS[40]
    modifie = sigma.copy()
    modifie[j] = sigma[j] * 5
    a, b = _valeur(sigma, valide, r, 1), _valeur(modifie, valide, r, 1)
    k = JOURS.index(j)
    assert np.array_equal(a[: k + 1], b[: k + 1]) and not np.array_equal(a[k + 1:], b[k + 1:])


def test_temoin_exposition_appliquee_le_jour_de_la_decision_detectee():
    sigma, valide, r = _cas()
    j = JOURS[40]
    modifie = sigma.copy()
    modifie[j] = sigma[j] * 5
    a, b = _valeur(sigma, valide, r, 0), _valeur(modifie, valide, r, 0)
    k = JOURS.index(j)
    assert not np.array_equal(a[: k + 1], b[: k + 1])            # la valeur du jour J change : triche détectée


def test_decalage_des_regles_est_un_jour():
    assert REGLES["strategie"]["decalage_execution_jours"] == 1


def test_jour_non_valide_ou_sans_prevision_garde_l_exposition_precedente():
    sigma, valide, _ = _cas(1)
    valide[JOURS[10]] = False
    sigma[JOURS[20]] = np.nan
    dec = S.decisions(sigma, valide, 0.6, REGLES)
    assert dec[JOURS[10]] == dec[JOURS[9]] and dec[JOURS[20]] == dec[JOURS[19]]
    assert dec[JOURS[11]] == R.exposition(REGLES, 0.6, float(sigma[JOURS[11]]))


@pytest.mark.parametrize("e", [[0.5, 1.2], [0.5, -0.1], [0.5, float("nan")]])
def test_exposition_hors_bornes_refusee(e):
    with pytest.raises(S.ErreurStrategie, match="hors de"):
        S.simuler(np.array(e), np.zeros(len(e)), 0.001, REGLES)


def test_frais_a_la_main():
    e = np.array([0.5, 0.8, 0.8, 0.2])
    r = np.array([0.02, -0.01, 0.03, 0.0])
    sim = S.simuler(e, r, 0.001, REGLES)
    v1 = (1 - 0.001 * 0.5) * (1 + 0.5 * 0.02)          # entrée depuis 0 : frais sur 0,5
    v2 = v1 * (1 - 0.001 * 0.3) * (1 - 0.8 * 0.01)
    v3 = v2 * 1.0 * (1 + 0.8 * 0.03)                   # aucune variation : aucun frais
    v4 = v3 * (1 - 0.001 * 0.6) * 1.0
    assert sim["valeur"] == pytest.approx([v1, v2, v3, v4], abs=1e-15)
    assert sim["frais_valeur"] == pytest.approx([0.0005, v1 * 0.0003, 0.0, v3 * 0.0006], abs=1e-15)
    assert sim["variation"] == pytest.approx([0.5, 0.3, 0.0, 0.6], abs=1e-15)


def test_kupiec_exemple_calcule_a_la_main():
    # n = 100, x = 10, p = 5 % : LR = −2 [90 ln 0,95 + 10 ln 0,05 − 90 ln 0,9 − 10 ln 0,1] ≈ 4,1308 ; p ≈ 0,0421
    k = EV.kupiec(10, 100, 0.05)
    assert k["statistique"] == pytest.approx(4.1308, abs=1e-3)
    assert k["p_valeur"] == pytest.approx(0.0421, abs=1e-3)
    assert EV.kupiec(50, 1000, 0.05)["p_valeur"] == pytest.approx(1.0, abs=1e-12)        # exactement le taux attendu
    assert EV.kupiec(0, 200, 0.05)["statistique"] == pytest.approx(-2 * 200 * math.log(0.95), abs=1e-9)


def test_kupiec_identique_au_rapport_de_vraisemblance_binomial():
    from scipy import stats
    for x, n, p in [(3, 250, 0.01), (17, 500, 0.05), (80, 1800, 0.05)]:
        lr = 2 * (stats.binom.logpmf(x, n, x / n) - stats.binom.logpmf(x, n, p))
        assert EV.kupiec(x, n, p)["statistique"] == pytest.approx(lr, abs=1e-8)


def test_mesures_a_la_main():
    r = np.array([0.01, -0.02, 0.015, -0.005, 0.0])
    assert S.sharpe(r) == pytest.approx(np.mean(r) / np.std(r, ddof=1) * math.sqrt(365), abs=1e-12)
    assert S.sortino(r) == pytest.approx(np.mean(r) / math.sqrt((0.02 ** 2 + 0.005 ** 2) / 5) * math.sqrt(365), abs=1e-12)
    assert S.drawdown_max(np.array([1.1, 0.88, 0.99, 1.2])) == pytest.approx(0.88 / 1.1 - 1, abs=1e-12)


def test_bootstrap_difference_avec_les_memes_indices():
    rng = np.random.default_rng(2)
    a = rng.normal(0.001, 0.02, 400)
    nulle = EV.bootstrap_statistique([a, a], lambda u, v: S.sharpe(u) - S.sharpe(v), REGLES)
    assert nulle["bas"] == nulle["haut"] == nulle["valeur"] == 0.0          # mêmes indices : différence nulle à chaque tirage
