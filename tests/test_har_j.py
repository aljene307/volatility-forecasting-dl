"""Tests du modèle descriptif HAR-J (données synthétiques)."""

import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

import har_j as HJ  # noqa: E402
import regles as R  # noqa: E402

REGLES = R.charger_regles()


def _exemples(n=400, graine=0):
    rng = np.random.default_rng(graine)
    jours = [dt.date(2020, 1, 6) + dt.timedelta(days=k) for k in range(n)]          # 2020-01-06 est un lundi
    x = {f"log_rv_{f}": rng.normal(-3.5, 0.3, n) for f in REGLES["modeles"]["har_rv"]["fenetres_jours"]}
    effet = np.array([0.0, 0.1, 0.05, 0.0, -0.05, -0.3, -0.25])                  # lundi ... dimanche
    cible = 0.1 + 0.5 * x["log_rv_1"] + 0.2 * x["log_rv_7"] + 0.1 * x["log_rv_30"] + effet[[j.weekday() for j in jours]]
    return pd.DataFrame({"date_cible": jours, **x, "cible": cible}), effet


def test_matrice_six_indicatrices_lundi_en_reference():
    ex, _ = _exemples(14)
    m = HJ.matrice(ex, REGLES)
    assert m.shape == (14, 4 + 6)
    lundis = np.array([d.weekday() == 0 for d in ex["date_cible"]])
    assert (m[lundis, 4:] == 0).all() and (m[~lundis, 4:].sum(axis=1) == 1).all()


def test_ajustement_retrouve_les_coefficients_et_l_effet_du_jour():
    ex, effet = _exemples()
    coef = HJ.ajuster(ex, REGLES)
    assert coef[:4] == pytest.approx([0.1, 0.5, 0.2, 0.1], abs=1e-9)
    assert coef[4:] == pytest.approx(effet[1:] - effet[0], abs=1e-9)
    assert HJ.prevoir(ex, coef, REGLES) == pytest.approx(ex["cible"].to_numpy(), abs=1e-9)


def test_jour_de_la_cible_et_non_de_l_origine():
    """Témoin : décaler les dates de cible d'un jour change les indicatrices (le jour utilisé est celui de la cible)."""
    ex, _ = _exemples(14)
    decale = ex.assign(date_cible=[d + dt.timedelta(days=1) for d in ex["date_cible"]])
    assert not np.array_equal(HJ.matrice(ex, REGLES), HJ.matrice(decale, REGLES))
