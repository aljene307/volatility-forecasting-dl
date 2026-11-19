"""Tests de l'explicabilité (données synthétiques, témoins)."""

import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

import entrainer as T  # noqa: E402
import explicabilite as X  # noqa: E402
import garde as G  # noqa: E402
import regles as R  # noqa: E402

REGLES = R.charger_regles()
T.configurer_torch(REGLES)
XP = REGLES["explicabilite"]["precisions"]


def _donnees(n=400, graine=0):
    """Séquences synthétiques (n, 30, 3) : a et b portent le signal, la 3e variable est du bruit pur."""
    rng = np.random.default_rng(graine)
    x = rng.normal(size=(n, 30, 3)).astype("float32")
    y = (0.8 * x[:, -1, 0] + 0.4 * x[:, -3, 1] + 0.05 * rng.normal(size=n)).astype("float32")
    return x, y


def _petit_lstm(x, y):
    import torch
    import reseaux
    torch.manual_seed(0)
    r = reseaux.construire_reseau("LSTM", {"taille_cachee": 8, "couches": 1, "dropout": 0.0}, 3, 30)
    opt = torch.optim.Adam(r.parameters(), lr=0.02)
    xt, yt = torch.from_numpy(x), torch.from_numpy(y)
    r.train()
    for _ in range(200):
        opt.zero_grad()
        torch.nn.functional.mse_loss(r(xt), yt).backward()
        opt.step()
    return r.eval()


@pytest.fixture(scope="module")
def modele_et_shap():
    x, y = _donnees()
    r = _petit_lstm(x, y)
    s = X.shap_reseau(r, x[:80], x[300:400], tirages=XP["shap_tirages_reseaux"], graine=42)
    return x, y, r, s


def test_additivite_shap_reseau_dans_la_tolerance(modele_et_shap):
    _, _, _, s = modele_et_shap
    assert s["additivite_erreur_relative"] <= XP["additivite_tolerance_reseaux"]


def test_temoin_additivite_contributions_tronquees_detectees(modele_et_shap):
    _, _, _, s = modele_et_shap
    phi = s["phi"].copy()
    phi[:, -1, 0] = 0.0                                      # on retire la contribution principale
    assert X.additivite(s["prevision"], s["base"], phi)["additivite_erreur_relative"] > XP["additivite_tolerance_reseaux"]


def test_temoin_bruit_classe_dernier_et_permutation_sans_effet_reseau(modele_et_shap):
    import torch
    x, y, r, s = modele_et_shap
    importance = dict(zip(["a", "b", "bruit"], np.abs(s["phi"]).mean(axis=0).sum(axis=0).tolist()))
    assert min(importance, key=importance.get) == "bruit"

    def predire(z):
        with torch.no_grad():
            return r(torch.from_numpy(np.asarray(z, dtype="float32"))).numpy().astype("float64") - 3.5

    cible = y[200:300].astype("float64") - 3.5
    s2 = float(np.var(cible - predire(x[200:300])))
    f = X.fidelite(predire, x[200:300], cible, s2, importance, {"a": [0], "b": [1], "bruit": [2]}, 20, 42)
    assert f["meilleure"] == "a" and f["moins_bonne"] == "bruit" and f["fidele"]
    assert abs(f["degradation_moins_bonne"]) < 0.01 * f["degradation_meilleure"]


def test_temoin_bruit_xgboost_tree_explainer_additivite_et_fidelite():
    import shap
    import xgboost as xgb
    x, y = _donnees(600, 1)
    z = x[:, -1, :].astype("float64")
    cible = 0.8 * z[:, 0] + 0.4 * z[:, 1] - 3.5
    m = xgb.XGBRegressor(n_estimators=200, max_depth=2, learning_rate=0.1, random_state=0, n_jobs=1).fit(z[:400], cible[:400])
    ex = shap.TreeExplainer(m)
    phi = np.asarray(ex.shap_values(z[400:]), dtype="float64")
    base = float(np.ravel(ex.expected_value)[0])
    assert X.additivite(m.predict(z[400:], output_margin=True), base, phi)["additivite_residu_max"] <= XP["additivite_tolerance_xgboost"]
    importance = dict(zip(["a", "b", "bruit"], np.abs(phi).mean(axis=0).tolist()))
    assert min(importance, key=importance.get) == "bruit"
    predire = lambda q: m.predict(q).astype("float64")  # noqa: E731
    s2 = float(np.var(cible[400:] - predire(z[400:])))
    f = X.fidelite(predire, z[400:], cible[400:], s2, importance, {"a": [0], "b": [1], "bruit": [2]}, 20, 42)
    assert f["fidele"] and abs(f["degradation_moins_bonne"]) < 0.01 * f["degradation_meilleure"]


def test_importance_par_retard_et_jour_de_la_semaine_a_la_main():
    n_cont = len(REGLES["entrainement"]["variables_continues"])
    phi = np.zeros((2, 30, n_cont + 7))
    phi[:, -1, 0] = [1.0, -3.0]                       # jour J (retard 1), 1re variable : moyenne |φ| = 2
    phi[:, 0, n_cont:] = 0.5                          # jour J − 29 (retard 30), 7 colonnes du jour de la semaine
    imp = X.importance_par_element(phi, REGLES)
    assert imp.shape == (30, n_cont + 1)
    assert imp[0, 0] == pytest.approx(2.0) and imp[29, -1] == pytest.approx(3.5)
    assert imp.sum() == pytest.approx(5.5)


def test_garde_active_sur_le_decoupage_du_test_final():
    ctx = object.__new__(X.Contexte)
    jours = [dt.date(2024, 1, 1) + dt.timedelta(days=k) for k in range(500)]
    ctx.exemples = pd.DataFrame({"date_cible": jours, "date_origine": [j - dt.timedelta(days=1) for j in jours], "cible": 0.0})
    with pytest.raises(G.ErreurTestAveugle):
        ctx.parties(R.decoupages(REGLES)[-1])


def test_fidelite_permutations_appariees_et_reproductibles():
    x, y = _donnees(100, 2)
    z = x[:, -1, :].astype("float64")
    cible = 0.8 * z[:, 0] - 3.5
    predire = lambda q: 0.8 * q[:, 0] - 3.5  # noqa: E731
    imp = {"a": 1.0, "b": 0.5, "bruit": 0.0}
    a = X.fidelite(predire, z, cible, 0.01, imp, {"a": [0], "b": [1], "bruit": [2]}, 20, 42)
    b = X.fidelite(predire, z, cible, 0.01, imp, {"a": [0], "b": [1], "bruit": [2]}, 20, 42)
    assert a == b and a["degradation_moins_bonne"] == 0.0 and a["degradation_meilleure"] > 0
