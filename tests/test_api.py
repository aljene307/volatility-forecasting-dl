"""Tests de l'API, par un client HTTP de test (règles : section api de config/regles.toml, section 18 des règles)."""

import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "src"))

from api import app as A  # noqa: E402
import regles as R  # noqa: E402

REGLES = R.charger_regles()
CLIENT = TestClient(A.creer_app())
EXEMPLE = json.loads((RACINE / "api" / "exemple_synthetique.json").read_text(encoding="utf-8"))


def _requete():
    return json.loads(json.dumps(EXEMPLE["requete"]))


def _erreurs(reponse):
    assert reponse.status_code == 422
    return {e["champ"]: e["message"] for e in reponse.json()["erreurs"]}


def test_health():
    r = CLIENT.get("/health")
    assert r.status_code == 200
    c = r.json()
    assert c["statut"] == "ok" and c["manifeste_verifie"] and c["fichiers_verifies"] == 7
    assert c["modeles"] == REGLES["api"]["modeles_servis"]
    if sys.platform == "win32" or Path("/proc/self/status").exists():
        assert c["memoire_mo"] > 0 and c["source_memoire"] != "indisponible"


def test_exemple_synthetique_indique_comme_tel_et_prevision_coherente():
    assert "SYNTHÉTIQUE" in EXEMPLE["avertissement"]
    r = CLIENT.post("/prevoir", json=_requete())
    assert r.status_code == 200
    c = r.json()
    s = REGLES["strategie"]
    assert c["volatilite_journaliere"] == pytest.approx(math.sqrt(math.exp(2 * c["prevision_log_rv"] + 2 * c["s2"])), rel=1e-12)
    assert c["volatilite_annualisee"] == pytest.approx(c["volatilite_journaliere"] * math.sqrt(365), rel=1e-12)
    assert c["exposition"] == pytest.approx(R.exposition(REGLES, c["vol_cible_annuelle"], c["volatilite_journaliere"]), abs=1e-12)
    assert c["var_1_jour_95"] == pytest.approx(R.var_un_jour(REGLES, c["volatilite_journaliere"]), rel=1e-12)
    assert s["exposition_min"] <= c["exposition"] <= s["exposition_max"]
    assert "Binance Vision" in c["licence"]


def test_erreur_29_jours():
    q = _requete()
    q["jours"] = q["jours"][:29]
    assert _erreurs(CLIENT.post("/prevoir", json=q)) == {"jours": "il faut exactement 30 jours (reçu 29)"}


def test_erreur_valeur_manquante():
    q = _requete()
    del q["jours"][5]["rv_7"]
    assert _erreurs(CLIENT.post("/prevoir", json=q))["jours[5].rv_7"] == "valeur manquante"


def test_erreur_actif_inconnu():
    q = _requete()
    q["actif"] = "SOLUSDT"
    assert _erreurs(CLIENT.post("/prevoir", json=q)) == {"actif": "actif inconnu : valeurs permises BTCUSDT et ETHUSDT"}


def test_erreur_nombre_negatif_impossible():
    q = _requete()
    q["jours"][0]["rv_1"] = -0.01
    assert _erreurs(CLIENT.post("/prevoir", json=q))["jours[0].rv_1"].startswith("doit être strictement supérieur à 0")


def test_erreurs_rsi_jour_de_semaine_et_coherence_des_logs():
    q = _requete()
    q["jours"][3]["rsi_14"] = 120
    q["jour_semaine_dernier_jour"] = 7
    q["jours"][4]["log_rv_7"] += 0.5
    e = _erreurs(CLIENT.post("/prevoir", json=q))
    assert e["jours[3].rsi_14"].startswith("doit être inférieur ou égal à 100")
    assert e["jour_semaine_dernier_jour"].startswith("doit être inférieur ou égal à 6")
    assert e["jours[4]"].startswith("log_rv_7 doit être égal à log(rv_7)")


def test_refus_de_demarrer_si_un_fichier_est_altere(tmp_path):
    copie = tmp_path / "modeles"
    shutil.copytree(RACINE / "api" / "modeles", copie)
    A.creer_app(copie)                                                  # témoin : la copie intacte démarre
    onnx = next(copie.glob("*.onnx"))
    octets = bytearray(onnx.read_bytes())
    octets[-1] ^= 1
    onnx.write_bytes(bytes(octets))
    with pytest.raises(A.ErreurDemarrage, match="empreinte différente"):
        A.creer_app(copie)


def test_api_sans_torch_ni_pandas():
    code = ("import sys; sys.path.insert(0, r'%s'); import api.app; "
            "print(sorted(m for m in ('torch', 'pandas') if m in sys.modules))") % RACINE
    sortie = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip()
    assert sortie == "[]"


# --- Test clé : validation interne du test final (2024-H2, développement) --------------------------------

@pytest.mark.skipif(not (RACINE / "data" / "processed" / "BTCUSDT_5m.parquet").exists(), reason="données locales absentes")
@pytest.mark.parametrize("actif", ["BTCUSDT", "ETHUSDT"])
def test_api_redonne_torch_et_onnxruntime_sur_la_validation_2024(actif):
    import onnxruntime as ort
    import baselines as B
    import comparer as K
    import entrainer as T
    import ouvrir_test as O
    api = REGLES["api"]
    modele = api["modeles_servis"][actif]
    final = R.decoupages(REGLES)[-1]
    exemples, journalier = T.donnees_reseaux(O.bougies_coupees(actif, final["validation"][1]), REGLES)
    val = exemples[B.masques(exemples, final)["validation"]]
    cle = T._cle_donnees(REGLES)
    torch_par_graine = np.array([K._unite(K.DOSSIER_DL / "unites", T.id_pli(actif, modele, final["nom"], g, cle))["validation"]["prevision_log"]
                                 for g in REGLES["modeles"]["graines_deep_learning"]])
    norm = json.loads((K.DOSSIER_DL / "normalisation" / actif / "test_final.json").read_text(encoding="utf-8"))
    x_direct = T.sequences(T.tableau_normalise(journalier, norm), journalier.index, list(val["date_origine"]), 30)
    p = json.loads((RACINE / "api" / "modeles" / "parametres.json").read_text(encoding="utf-8"))["actifs"][actif]
    sessions = [ort.InferenceSession(str(RACINE / "api" / "modeles" / f), providers=["CPUExecutionProvider"]) for f in p["fichiers_onnx"]]
    direct = np.mean([s.run(None, {"entree": x_direct})[0].astype("float64") * norm["cible_ecart_type"] + norm["cible_moyenne"]
                      for s in sessions], axis=0)
    variables = REGLES["entrainement"]["variables_continues"]
    position = {j: i for i, j in enumerate(journalier.index)}
    ecart_torch, ecart_ort = 0.0, 0.0
    for k, origine in enumerate(val["date_origine"]):
        i = position[origine]
        bloc = journalier.iloc[i - 29:i + 1]
        requete = {"actif": actif, "jour_semaine_dernier_jour": int(journalier["jour_semaine"].iloc[i]),
                   "jours": [{v: float(bloc[v].iloc[t]) for v in variables} for t in range(30)]}
        r = CLIENT.post("/prevoir", json=requete)
        assert r.status_code == 200, r.text
        c = r.json()
        ecart_torch = max(ecart_torch, float(np.max(np.abs(np.array(c["prevision_log_rv_par_graine"]) - torch_par_graine[:, k]))))
        ecart_ort = max(ecart_ort, abs(c["prevision_log_rv"] - float(direct[k])))
    print(f"{actif} : {len(val)} jours ; écart maximal API / torch {ecart_torch:.2e} ; API / onnxruntime {ecart_ort:.2e}")
    assert ecart_torch <= api["tolerance_torch_log"]
    assert ecart_ort <= api["tolerance_onnxruntime"]
