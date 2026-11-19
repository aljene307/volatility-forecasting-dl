"""Tests de l'application Streamlit (streamlit.testing AppTest) : pages, nombres lus dans les JSON, secrets, API en panne."""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "app"))

import outils_app as K  # noqa: E402
from vues import demonstration as D  # noqa: E402

MODULES = ["accueil", "methode", "exploration", "resultats", "strategie", "explicabilite", "demonstration", "limites"]


def _page(module: str, racine: str) -> None:
    import importlib
    import sys
    sys.path.insert(0, racine + "/app")
    importlib.import_module("vues." + module).afficher()


def _textes(at) -> str:
    """Tout le texte affiché : markdown, légendes, alertes, métriques et cellules des tableaux."""
    morceaux = [e.value for e in at.markdown] + [e.value for e in at.caption] + [e.value for e in at.info]
    morceaux += [e.value for e in at.error] + [e.value for e in at.success] + [e.value for e in at.warning]
    morceaux += [str(m.value) for m in at.metric]
    for t in at.table:
        df = t.value
        morceaux += [str(v) for v in df.to_numpy().ravel()] + [str(v) for v in df.index]
    return "\n".join(morceaux)


@pytest.mark.parametrize("module", MODULES)
def test_chaque_page_s_affiche_sans_exception(module):
    at = AppTest.from_function(_page, args=(module, str(RACINE)), default_timeout=120).run()
    assert not at.exception, at.exception
    assert K.MENTION in _textes(at)                               # mention de la licence sur chaque page


def test_application_complete_demarre_sans_fichier_de_secrets():
    assert not (RACINE / "app" / ".streamlit" / "secrets.toml").exists() and not (RACINE / ".streamlit" / "secrets.toml").exists()
    at = AppTest.from_file(str(RACINE / "app" / "streamlit_app.py"), default_timeout=120).run()
    assert not at.exception, at.exception
    assert K.adresse_api() == K.API_PAR_DEFAUT or K.adresse_api()     # sans secrets : valeur par défaut ou variable d'environnement


def test_nombres_affiches_egaux_au_json_et_temoin():
    t = json.loads((RACINE / "rapports" / "test_final.json").read_text(encoding="utf-8"))
    at = AppTest.from_function(_page, args=("accueil", str(RACINE)), default_timeout=120).run()
    texte = _textes(at)
    for a in K.ACTIFS:
        gain = t["hypotheses"]["prevision"][a]["gain"]
        assert K.pourcent(gain) in texte
        assert K.pourcent(gain + 0.01) not in texte                   # témoin : une valeur fausse n'est pas affichée
    at = AppTest.from_function(_page, args=("resultats", str(RACINE)), default_timeout=120).run()
    texte = _textes(at)
    q = t["actifs"]["BTCUSDT"]["modeles"]["Transformer"]
    assert f"{K.nombre(q['qlike'])} [{K.nombre(q['qlike_intervalle']['bas'])} ; {K.nombre(q['qlike_intervalle']['haut'])}]" in texte


def test_demonstration_message_clair_si_l_api_ne_repond_pas(monkeypatch):
    monkeypatch.setenv("API_URL", "http://127.0.0.1:9")              # aucune API sur ce port : API simulée en panne
    at = AppTest.from_function(_page, args=("demonstration", str(RACINE)), default_timeout=120).run()
    at.button(key="envoyer_exemple").click().run()
    assert not at.exception
    assert any("ne répond pas" in e.value for e in at.error)


def test_format_francais():
    assert K.nombre(1234.5678, 2) == "1 234,57" and K.nombre(-0.0866, 4) == "−0,0866" and K.pourcent(0.322) == "32,2 %"


def test_lecture_du_csv_valide_et_refus_clairs():
    jours = D.exemple()["requete"]["jours"]
    df = pd.DataFrame(jours)[D.variables()]
    lus, erreurs = D.lire_csv(df.to_csv(index=False).encode("utf-8"))
    assert erreurs == [] and lus == [{c: float(j[c]) for c in D.variables()} for j in jours]
    lus2, erreurs2 = D.lire_csv(df.to_csv(index=False, sep=";", decimal=",").encode("utf-8"))
    assert erreurs2 == [] and lus2 == lus
    _, e = D.lire_csv(df.iloc[:29].to_csv(index=False).encode("utf-8"))
    assert e == ["Il faut exactement 30 lignes de données (reçu 29)."]
    _, e = D.lire_csv(df.drop(columns=["rv_7"]).to_csv(index=False).encode("utf-8"))
    assert e and e[0].startswith("En-tête attendu")
    sale = df.copy().astype(object)
    sale.loc[4, "rsi_14"] = "abc"
    _, e = D.lire_csv(sale.to_csv(index=False).encode("utf-8"))
    assert e == ["Colonne rsi_14 : valeur manquante ou non numérique aux lignes 5."]
