"""Tests des variables, de la cible, de la garde du test aveugle et de l'exploration (données synthétiques)."""

import ast
import datetime as dt
import inspect
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

import convertir as CV  # noqa: E402
import exploration as X  # noqa: E402
import garde as G  # noqa: E402
import regles as R  # noqa: E402
import variables as V  # noqa: E402

REGLES = R.charger_regles()
D = dt.date.fromisoformat
DEBUT, FIN = D("2019-12-01"), D("2020-04-30")
UTC = "UTC"


def bougies_synthetiques(debut=DEBUT, fin=FIN, graine=0, retirer=()) -> pd.DataFrame:
    """Bougies de 5 minutes aléatoires (marche au hasard), avec des intervalles retirés [a ; b[."""
    dates = pd.date_range(pd.Timestamp(debut, tz=UTC), pd.Timestamp(fin + dt.timedelta(days=1), tz=UTC),
                          freq="5min", inclusive="left").astype("datetime64[us, UTC]")
    rng = np.random.default_rng(graine)
    n = len(dates)
    cloture = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    ouverture = np.r_[100.0, cloture[:-1]]
    df = pd.DataFrame({
        "date_ouverture": dates, "ouverture": ouverture,
        "plus_haut": np.maximum(ouverture, cloture) * (1 + np.abs(rng.normal(0, 0.001, n))),
        "plus_bas": np.minimum(ouverture, cloture) * (1 - np.abs(rng.normal(0, 0.001, n))),
        "cloture": cloture, "volume_cotation": rng.uniform(1e5, 1e6, n),
    })
    for a, b in retirer:
        df = df[~((df["date_ouverture"] >= pd.Timestamp(a, tz=UTC)) & (df["date_ouverture"] < pd.Timestamp(b, tz=UTC)))]
    return df.reset_index(drop=True)


# Un jour non valide (trou de 95 minutes) pour exercer la règle de secours
TROU = [("2020-03-10 10:00", "2020-03-10 11:35")]
JOUR_REMPLACE = D("2020-03-10")
BOUGIES = bougies_synthetiques(retirer=TROU)


def calcul(b: pd.DataFrame) -> pd.DataFrame:
    return V.calculer_actif(b, REGLES, DEBUT, FIN)[0]


EXEMPLES = calcul(BOUGIES)
# Bord de mois (fin février, année bissextile), crise Covid, jour remplacé, fin de mois
JOURS_J = [D("2020-02-29"), D("2020-03-15"), JOUR_REMPLACE, D("2020-03-31")]


# --- Test de l'avenir modifié ------------------------------------------------------------

def test_avenir_multiplie_par_10_ne_change_aucune_variable_passee():
    assert V.ecarts_avenir_modifie(BOUGIES, JOURS_J, calcul) == []


def test_avenir_bruite_ne_change_aucune_variable_passee():
    """Variante plus sévère : facteur 10 multiplié par un bruit différent pour chaque bougie."""
    rng = np.random.default_rng(1)
    assert V.ecarts_avenir_modifie(BOUGIES, JOURS_J, calcul, lambda n: 10 * (1 + rng.uniform(-0.5, 0.5, n))) == []


def test_temoin_variable_tricheuse_detectee():
    """Une moyenne CENTRÉE de RV regarde 3 jours dans l'avenir : le même test doit l'attraper."""
    def calcul_tricheur(b):
        exemples, lignes, _ = V.calculer_actif(b, REGLES, DEBUT, FIN)
        centree = lignes["rv"].rolling(7, center=True, min_periods=1).mean()
        exemples["rv_centree"] = centree.loc[list(exemples["date_origine"])].to_numpy()
        return exemples

    ecarts = V.ecarts_avenir_modifie(BOUGIES, JOURS_J, calcul_tricheur)
    assert ecarts and all(e.endswith("rv_centree") for e in ecarts), ecarts
    assert len(ecarts) == len(JOURS_J)


# --- Cible, jours et secours ---------------------------------------------------------------

def _rv_independante(b: pd.DataFrame, jour: dt.date) -> float:
    """RV d'un jour calculée à la main : clôtures du jour et dernière clôture de la veille."""
    debut = pd.Timestamp(jour, tz=UTC)
    fin = debut + pd.Timedelta(days=1)
    veille = b.loc[b["date_ouverture"] < debut, "cloture"].iloc[-1:]
    jour_c = b.loc[(b["date_ouverture"] >= debut) & (b["date_ouverture"] < fin), "cloture"]
    c = np.concatenate([veille.to_numpy(), jour_c.to_numpy()])
    return math.sqrt(float(np.sum(np.diff(np.log(c)) ** 2)))


def test_cible_est_log_rv_du_lendemain():
    for j in [D("2020-01-15"), D("2020-03-11"), D("2020-04-29")]:
        ligne = EXEMPLES[EXEMPLES["date_origine"] == j].iloc[0]
        assert ligne["date_cible"] == j + dt.timedelta(days=1)
        assert abs(ligne["cible"] - math.log(_rv_independante(BOUGIES, ligne["date_cible"]))) < 1e-9


def test_cible_non_valide_exclue_et_origine_remplacee_gardee():
    assert JOUR_REMPLACE not in set(EXEMPLES["date_cible"]), "La cible du jour non valide doit être exclue."
    ligne = EXEMPLES[EXEMPLES["date_origine"] == JOUR_REMPLACE].iloc[0]
    lignes = V.lignes_journalieres(BOUGIES, REGLES, DEBUT, FIN)
    veille = JOUR_REMPLACE - dt.timedelta(days=1)
    assert not bool(lignes.loc[JOUR_REMPLACE, "valide"]) and bool(lignes.loc[veille, "valide"])
    # l'exemple d'origine « veille » n'existe pas : sa cible (le jour non valide) est exclue
    assert veille not in set(EXEMPLES["date_origine"])
    assert ligne["jour_remplace"] == 1
    assert ligne["rv_1"] == lignes.loc[veille, "rv"], "Le jour remplacé reprend la ligne du dernier jour valide."
    assert ligne["log_rendement"] == 0.0, "Limite écrite : rendement nul le jour remplacé."
    assert ligne["fenetre_avec_jour_remplace"] == 1


def test_frontiere_des_jours_utc():
    b = BOUGIES.copy()
    j = D("2020-01-20")
    i_2355 = b.index[b["date_ouverture"] == pd.Timestamp("2020-01-20 23:55", tz=UTC)][0]
    i_0000 = b.index[b["date_ouverture"] == pd.Timestamp("2020-01-21 00:00", tz=UTC)][0]
    b.loc[i_2355, "volume_cotation"] = 7e9
    b.loc[i_0000, "volume_cotation"] = 3e9
    lignes = V.lignes_journalieres(b, REGLES, DEBUT, FIN)
    assert lignes.loc[j, "volume"] >= 7e9 and lignes.loc[j, "volume"] < 8e9, "23:55 appartient à J."
    assert lignes.loc[j + dt.timedelta(days=1), "volume"] >= 3e9, "00:00 appartient à J+1."
    assert lignes.loc[j, "cloture"] == b.loc[i_2355, "cloture"]
    assert lignes.loc[j + dt.timedelta(days=1), "ouverture"] == b.loc[i_0000, "ouverture"]


def test_premier_jour_287_rendements():
    lignes = V.lignes_journalieres(BOUGIES, REGLES, DEBUT, FIN)
    assert lignes.loc[DEBUT, "rendements"] == 287 and bool(lignes.loc[DEBUT, "valide"])


def test_validite_en_entree_n_utilise_pas_l_avenir():
    assert V.calculer_actif(BOUGIES, REGLES, DEBUT, FIN)[2]["jours_controles_validite_passe"] == 0


def test_temoin_validite_qui_utilise_l_avenir_detectee():
    """Trou de 23:25 (J) à 00:40 (J+1) : 80 min au total, mais 40 min seulement connues à la clôture de J.
    Avec le trou complet, J est non valide ; avec le passé seul, J serait valide : le contrôle doit refuser."""
    b = bougies_synthetiques(retirer=[("2020-02-10 23:25", "2020-02-11 00:40")])
    with pytest.raises(V.ErreurVariables, match="utilise l'avenir"):
        V.calculer_actif(b, REGLES, DEBUT, FIN)


def test_deux_executions_memes_empreintes(tmp_path):
    empreintes = []
    for k in range(2):
        chemin = tmp_path / f"v{k}.parquet"
        ex = calcul(BOUGIES)
        ex.insert(0, "actif", "TEST")
        V.ecrire_parquet(ex, chemin)
        empreintes.append(CV.empreinte_contenu(chemin, V.colonnes_sortie(ex.drop(columns="actif"))))
    assert empreintes[0] == empreintes[1]


# --- Formules vérifiées à la main ----------------------------------------------------------

def test_parkinson_et_garman_klass_a_la_main():
    # H = 110, L = 100, O = 102, C = 108 ; ln(1,1) = 0,0953101798043249 ; ln 2 = 0,6931471805599453
    ln_hl, ln_co, ln2 = 0.0953101798043249, math.log(108 / 102), 0.6931471805599453
    assert V.parkinson(110.0, 100.0) == pytest.approx(ln_hl ** 2 / (4 * ln2), rel=1e-12)
    assert V.parkinson(110.0, 100.0) == pytest.approx(0.0032763714, rel=1e-8)
    assert V.garman_klass(102.0, 110.0, 100.0, 108.0) == pytest.approx(0.5 * ln_hl ** 2 - (2 * ln2 - 1) * ln_co ** 2, rel=1e-12)


def test_rsi_de_wilder_a_la_main():
    # n = 3 ; variations 1 ; -0,5 ; 1 ; -0,5 ; 1
    # moyennes simples : hausses 2/3, baisses 1/6 -> RSI = 80
    # puis (2/3·2 + 0)/3 = 4/9 et (1/6·2 + 0,5)/3 = 5/18 -> RS = 8/5 -> RSI = 100 − 100/2,6
    # puis (4/9·2 + 1)/3 = 17/27 et (5/18·2 + 0)/3 = 5/27 -> RS = 3,4 -> RSI = 100 − 100/4,4
    rsi = V.rsi_wilder(pd.Series([10, 11, 10.5, 11.5, 11, 12.0]), 3).to_numpy()
    assert np.isnan(rsi[:3]).all()
    assert rsi[3:] == pytest.approx([80.0, 100 - 100 / 2.6, 100 - 100 / 4.4], rel=1e-12)


def test_rsi_vaut_100_sans_baisse():
    assert V.rsi_wilder(pd.Series([1.0, 2, 3, 4, 5]), 3).iloc[-1] == 100.0


def test_macd_a_la_main():
    # spans 2, 3 et 2 : alpha = 2/3, 1/2 et 2/3 ; clôtures 10, 12, 11
    # EMA2 : 10 ; 34/3 ; 100/9   EMA3 : 10 ; 11 ; 11   MACD : 0 ; 1/3 ; 1/9
    # signal : 0 ; 2/9 ; 4/27    histogramme : 0 ; 1/9 ; −1/27
    hist = V.macd_histogramme(pd.Series([10.0, 12.0, 11.0]), 2, 3, 2).to_numpy()
    assert hist == pytest.approx([0.0, 1 / 9, -1 / 27], abs=1e-12)


def test_bollinger_a_la_main():
    # clôtures 1, 2, 3 ; moyenne 2 ; écart-type de population racine(2/3) ; largeur 4·racine(2/3)/2
    largeur = V.bollinger_largeur(pd.Series([1.0, 2.0, 3.0]), 3, 2).to_numpy()
    assert np.isnan(largeur[:2]).all()
    assert largeur[2] == pytest.approx(2 * math.sqrt(2 / 3), rel=1e-12)


def test_variables_lues_dans_les_regles():
    noms = set(EXEMPLES.columns)
    assert {f"rv_{n}" for n in REGLES["variables"]["rv_moyennes_jours"]} <= noms
    assert f"rsi_{REGLES['variables']['rsi_jours']}" in noms
    assert set(EXEMPLES["jour_semaine"]) == set(range(7))


# --- Garde du test aveugle -----------------------------------------------------------------

def test_garde_rejette_une_statistique_sur_le_test():
    with pytest.raises(G.ErreurTestAveugle, match="aveugle"):
        G.refuser_si_test([D("2024-12-31"), D("2025-01-01")], "moyenne")
    G.refuser_si_test([D("2024-12-31")], "moyenne")          # développement : permis
    assert G.compter([D("2025-01-01"), D("2026-10-31")]) == 2  # comptage : toujours permis


def test_temoin_exploration_refuse_une_serie_de_2025():
    serie = pd.DataFrame({"rv": [0.02, 0.03, 0.025], "cloture": [1.0, 1.1, 1.2], "valide": [True] * 3},
                         index=pd.DatetimeIndex(pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"])))
    with pytest.raises(G.ErreurTestAveugle):
        X.statistiques(serie, REGLES)


INTERDITS = {"environ", "getenv", "putenv", "argv", "getopt", "argparse"}
PARAMETRES_PERMIS = {"refuser_si_test": ["dates_cible", "usage"], "compter": ["dates_cible"]}


def options_de_contournement(source: str, parametres_permis: dict[str, list[str]]) -> list[str]:
    """Liste toute option qui permettrait de contourner la garde : paramètre en trop ou avec une valeur par
    défaut, lecture de l'environnement ou de la ligne de commande, lecture d'un réglage du test aveugle."""
    arbre = ast.parse(source)
    problemes = []
    publiques = [n for n in arbre.body if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")]
    if sorted(f.name for f in publiques) != sorted(parametres_permis):
        problemes.append(f"fonctions publiques : {sorted(f.name for f in publiques)}")
    for f in publiques:
        a = f.args
        noms = [x.arg for x in a.posonlyargs + a.args + a.kwonlyargs]
        if noms != parametres_permis.get(f.name) or a.vararg or a.kwarg or a.defaults or a.kw_defaults:
            problemes.append(f"paramètres de {f.name} : {noms}")
    for noeud in ast.walk(arbre):
        nom = getattr(noeud, "id", None) or getattr(noeud, "attr", None)
        if nom in INTERDITS:
            problemes.append(f"lecture de {nom}")
        if isinstance(noeud, ast.alias) and noeud.name.split(".")[0] in INTERDITS:
            problemes.append(f"import de {noeud.name}")
        if isinstance(noeud, ast.Constant) and noeud.value == "test_aveugle":
            problemes.append("lecture d'un réglage test_aveugle")
    return problemes


def test_garde_sans_aucune_option_de_contournement():
    assert options_de_contournement(inspect.getsource(G), PARAMETRES_PERMIS) == []


def test_temoin_options_de_contournement_detectees():
    fausses = '''
import os
def refuser_si_test(dates_cible, usage, forcer=False):
    if os.environ.get("OUVRIR_TEST") or forcer:
        return
def compter(dates_cible):
    return 0
def ouvrir(regles):
    return regles["test_aveugle"]["ouvert"]
'''
    problemes = options_de_contournement(fausses, PARAMETRES_PERMIS)
    assert any("paramètres de refuser_si_test" in p for p in problemes)
    assert any("environ" in p for p in problemes)
    assert any("fonctions publiques" in p for p in problemes)
    assert any("test_aveugle" in p for p in problemes)
