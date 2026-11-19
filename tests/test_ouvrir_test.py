"""Tests du mécanisme d'ouverture du test final (dépôts et fichiers temporaires ; le test n'est JAMAIS ouvert ici)."""

import datetime as dt
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

import garde as G  # noqa: E402
import ouvrir_test as O  # noqa: E402
import regles as R  # noqa: E402

REGLES = R.charger_regles()
D = dt.date.fromisoformat


def _git(dossier, *args):
    subprocess.run(["git", *args], cwd=dossier, check=True, capture_output=True)


@pytest.fixture
def depot(tmp_path):
    """Dépôt temporaire avec un dépôt distant nu, les fichiers des attentes commités et poussés."""
    distant, local = tmp_path / "distant.git", tmp_path / "local"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(distant)], check=True, capture_output=True)
    local.mkdir()
    _git(local, "init", "-b", "main")
    _git(local, "config", "user.name", "Test")
    _git(local, "config", "user.email", "test@example.invalid")
    for f in O.FICHIERS_ATTENTES:
        (local / f).parent.mkdir(parents=True, exist_ok=True)
        (local / f).write_text("attentes\n", encoding="utf-8")
    _git(local, "add", ".")
    _git(local, "commit", "-m", "attentes")
    _git(local, "remote", "add", "origin", str(distant))
    _git(local, "push", "-q", "origin", "main")
    return local


def test_depot_propre_et_pousse_accepte(depot):
    assert len(O.verifier_depot(depot)) == 40


def test_refus_si_le_depot_est_modifie(depot):
    (depot / "docs" / "ATTENTES_TEST.md").write_text("modifié\n", encoding="utf-8")
    with pytest.raises(O.ErreurOuverture, match="pas propre"):
        O.verifier_depot(depot)


def test_refus_si_le_commit_n_est_pas_pousse(depot):
    (depot / "nouveau.txt").write_text("x\n", encoding="utf-8")
    _git(depot, "add", ".")
    _git(depot, "commit", "-m", "non poussé")
    with pytest.raises(O.ErreurOuverture, match="diffère de origin/main"):
        O.verifier_depot(depot)


def test_refus_si_les_attentes_ne_sont_pas_dans_le_commit(depot):
    _git(depot, "rm", "-q", "config/attentes_test.toml")
    _git(depot, "commit", "-m", "sans attentes")
    _git(depot, "push", "-q", "origin", "main")
    with pytest.raises(O.ErreurOuverture, match="attentes absents"):
        O.verifier_depot(depot)


def test_refus_si_le_fichier_de_resultats_existe(tmp_path):
    chemin = tmp_path / "test_final.json"
    O.ecrire_exclusif(chemin, "{}\n")
    with pytest.raises(O.ErreurOuverture, match="existe déjà"):
        O.ecrire_exclusif(chemin, "{\"autre\": 1}\n")
    assert chemin.read_text(encoding="utf-8") == "{}\n"            # le premier contenu n'est pas écrasé


def test_refus_si_une_empreinte_de_modele_est_alteree(tmp_path):
    modele = tmp_path / "poids.pt"
    modele.write_bytes(b"poids d'origine")
    attendus = {modele: hashlib.sha256(b"poids d'origine").hexdigest()}
    assert O.verifier_fichiers(attendus) == 1
    modele.write_bytes(b"poids alteres")
    with pytest.raises(O.ErreurOuverture, match="empreinte différente"):
        O.verifier_fichiers(attendus)
    modele.unlink()
    with pytest.raises(O.ErreurOuverture, match="absent"):
        O.verifier_fichiers(attendus)


def test_manifestes_reels_complets_pour_le_test_final_et_le_pli_5():
    final, pli5 = R.decoupages(REGLES)[-1], R.decoupages(REGLES)[-2]
    assert len(O.empreintes_attendues(REGLES, final)) == 2 * (5 * 3 + 1) + 2 * 5
    assert len(O.empreintes_attendues(REGLES, pli5)) == 2 * (5 * 3 + 1)


# --- Verdicts : H7 (modèle retenu contre HAR-J, Holm sur les 2 actifs) -----------------------------

def _sortie_synthetique(decalage_retenu: dict) -> dict:
    """Résultats fictifs pour 2 actifs : pertes QLIKE de HAR-J et du modèle retenu (HAR-J + décalage)."""
    import numpy as np
    import evaluation as EV
    rng = np.random.default_rng(0)
    actifs = {}
    for k, (a, dec) in enumerate(decalage_retenu.items()):
        har_j = rng.gamma(2.0, 0.15, 600)
        retenu = har_j + dec + rng.normal(0, 0.02, 600)
        modele = "Transformer" if k == 0 else "CNN-LSTM"
        dm = EV.diebold_mariano(retenu, har_j)
        actifs[a] = {"modele_retenu": modele, "diebold_mariano": {modele: dm}, "diebold_mariano_contre_har_j": {modele: dm},
                     "modeles": {m: {"qlike": 0.3} for m in ("HAR-RV", "Persistance", "GARCH(1,1)")},
                     "var": {"modeles": {"HAR-RV": {"p_valeur": 0.5, "taux": 0.05}}},
                     "strategie": {modele: {"volatilite_annualisee": 0.5, "drawdown_max": -0.3},
                                   "Achat simple": {"volatilite_annualisee": 0.6, "drawdown_max": -0.4}},
                     "gain_sur_har_rv": {modele: 0.1}, "gain_sur_har_j": {modele: float(-dec / har_j.mean())}}
    return {"actifs": actifs}


def test_h7_confirmee_si_le_modele_retenu_bat_nettement_har_j():
    import tomllib
    attentes = tomllib.loads(O.CHEMIN_ATTENTES.read_text(encoding="utf-8"))
    h = O.hypotheses(_sortie_synthetique({"BTCUSDT": -0.015, "ETHUSDT": -0.015}), attentes, REGLES)   # gain d'environ 5 %
    assert all(x["confirmee"] for x in h["H7"].values())
    assert all(x["p_valeur_holm_2_actifs"] >= x["p_valeur"] for x in h["H7"].values())
    assert all(x["dans_l_intervalle"] for x in h["prevision_har_j"].values())


def test_temoin_h7_refusee_si_le_modele_retenu_fait_moins_bien_ou_sans_ecart_net():
    import tomllib
    attentes = tomllib.loads(O.CHEMIN_ATTENTES.read_text(encoding="utf-8"))
    h = O.hypotheses(_sortie_synthetique({"BTCUSDT": 0.03, "ETHUSDT": 0.0}), attentes, REGLES)
    assert not h["H7"]["BTCUSDT"]["confirmee"] and h["H7"]["BTCUSDT"]["moyenne_difference"] > 0     # moins bien que HAR-J
    assert not h["H7"]["ETHUSDT"]["confirmee"] and h["H7"]["ETHUSDT"]["p_valeur_holm_2_actifs"] >= 0.05  # aucun écart net
    assert not h["prevision_har_j"]["BTCUSDT"]["dans_l_intervalle"]


def test_attentes_contiennent_h7_et_h1_reste_principale():
    import tomllib
    attentes = tomllib.loads(O.CHEMIN_ATTENTES.read_text(encoding="utf-8"))
    assert attentes["H1"]["type"] == "principale" and attentes["H7"]["type"] == "secondaire"
    assert (attentes["prevision_har_j"]["gain_min"], attentes["prevision_har_j"]["gain_max"]) == (0.0, 0.09)


# --- La garde reste fermée hors de src/ouvrir_test.py ---------------------------------------------

def test_garde_fermee_hors_du_script():
    with pytest.raises(G.ErreurTestAveugle, match="Ouverture refusée"):
        with G._ouverture_officielle():
            pass
    with pytest.raises(G.ErreurTestAveugle, match="aveugle"):
        G.refuser_si_test([D("2025-01-01")], "moyenne")


def test_temoin_fonction_du_meme_nom_ailleurs_refusee():
    def _chaine_sur_le_test_ouvert():
        with G._ouverture_officielle():
            return "ouvert"
    with pytest.raises(G.ErreurTestAveugle, match="Ouverture refusée"):
        _chaine_sur_le_test_ouvert()
    with pytest.raises(G.ErreurTestAveugle):
        G.refuser_si_test([D("2025-06-01")], "moyenne")


def test_la_porte_s_ouvre_seulement_dans_la_fonction_prevue_puis_se_referme(monkeypatch):
    """Témoin positif, sans aucune donnée : la chaîne est remplacée par un faux calcul sur des dates de 2025."""
    def fausse_chaine(regles, decoupage):
        G.refuser_si_test([D("2025-03-01")], "faux calcul")        # passerait seulement si la porte est ouverte
        return {"ok": True}
    monkeypatch.setattr(O, "chaine", fausse_chaine)
    assert O._chaine_sur_le_test_ouvert(REGLES) == {"ok": True}
    with pytest.raises(G.ErreurTestAveugle):                         # refermée après le bloc
        G.refuser_si_test([D("2025-03-01")], "moyenne")


def test_seul_ouvrir_test_utilise_la_porte():
    utilisateurs = sorted(f.name for f in (RACINE / "src").glob("*.py") if "_ouverture_officielle" in f.read_text(encoding="utf-8"))
    assert utilisateurs == ["garde.py", "ouvrir_test.py"]


def test_sans_option_explicite_rien_ne_s_ouvre(capsys):
    assert O.main([]) == 2 and O.main(["--ouvrir-maintenant"]) == 2
    assert "Usage" in capsys.readouterr().out
    assert not (RACINE / REGLES["test_final"]["resultats"]).exists()
