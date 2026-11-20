"""Vérification de l'API en ligne : /health, puis l'exemple SYNTHÉTIQUE, comparé à la prévision locale.

Usage (depuis la racine du projet) : .venv\\Scripts\\python api\\verifier_en_ligne.py https://adresse-de-l-api
- attend jusqu'à 120 s le réveil du service (offre gratuite : il s'endort après une période sans requête) ;
- affiche l'état et la mémoire du service ;
- envoie l'exemple synthétique pour chaque actif et compare la prévision à celle calculée localement avec les mêmes
  fichiers ONNX (tolérance de 1e-6 en log : onnxruntime sous Linux peut différer très légèrement de Windows).
Aucune donnée Binance n'est envoyée : l'exemple est synthétique.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

DELAI_REVEIL_S = 120
TOLERANCE_LOG = 1e-6


def _requete(url: str, corps: dict | None = None, delai: float = 30) -> tuple[int, dict]:
    donnees = None if corps is None else json.dumps(corps).encode("utf-8")
    entetes = {"Content-Type": "application/json"} if corps is not None else {}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=donnees, headers=entetes), timeout=delai) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, {}


def attendre_reveil(adresse: str, delai: float = DELAI_REVEIL_S) -> dict:
    """Appelle /health jusqu'à obtenir une réponse, au plus `delai` secondes."""
    debut = time.monotonic()
    while True:
        try:
            statut, sante = _requete(f"{adresse}/health", delai=min(30, delai))
            if statut == 200:
                return sante
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        if time.monotonic() - debut > delai:
            raise TimeoutError(f"L'API n'a pas répondu en {delai:.0f} s ({adresse}).")
        print("L'API se réveille…", flush=True)
        time.sleep(5)


def comparer(en_ligne: dict, locale: dict, tolerance: float = TOLERANCE_LOG) -> list[str]:
    """Écarts entre la réponse en ligne et la prévision locale (en log), au-delà de la tolérance."""
    problemes = []
    for cle in ("actif", "modele"):
        if en_ligne.get(cle) != locale[cle]:
            problemes.append(f"{cle} : {en_ligne.get(cle)} au lieu de {locale[cle]}")
    ecarts = [abs(en_ligne["prevision_log_rv"] - locale["prevision_log_rv"])]
    ecarts += [abs(a - b) for a, b in zip(en_ligne["prevision_log_rv_par_graine"], locale["prevision_log_rv_par_graine"])]
    if len(en_ligne["prevision_log_rv_par_graine"]) != len(locale["prevision_log_rv_par_graine"]) or max(ecarts) > tolerance:
        problemes.append(f"écart en log de {max(ecarts):.2e} (tolérance {tolerance:.0e})")
    return problemes


def main(arguments: list[str]) -> int:
    if len(arguments) != 1:
        print("Usage : python api/verifier_en_ligne.py https://adresse-de-l-api")
        return 2
    adresse = arguments[0].rstrip("/")
    from api import app as A
    moteur = A.Moteur(A.DOSSIER_MODELES)
    exemple = json.loads((RACINE / "api" / "exemple_synthetique.json").read_text(encoding="utf-8"))["requete"]
    try:
        sante = attendre_reveil(adresse)
    except TimeoutError as e:
        print(f"ÉCHEC : {e}")
        return 1
    print(f"/health : {sante.get('statut')} ; fichiers vérifiés : {sante.get('fichiers_verifies')} ; mémoire : "
          f"{sante.get('memoire_mo')} Mo ({sante.get('source_memoire')}) ; versions : {sante.get('versions')}")
    reussi = True
    for actif in ("BTCUSDT", "ETHUSDT"):
        requete = dict(exemple, actif=actif)
        debut = time.monotonic()
        statut, reponse = _requete(f"{adresse}/prevoir", requete, delai=60)
        duree = time.monotonic() - debut
        if statut != 200:
            print(f"{actif} : ÉCHEC, code {statut}")
            reussi = False
            continue
        locale = moteur.prevoir(A.Requete(**requete))
        problemes = comparer(reponse, locale)
        ecart = abs(reponse["prevision_log_rv"] - locale["prevision_log_rv"])
        print(f"{actif} : {reponse['modele']} ; prévision en log {reponse['prevision_log_rv']:.10f} (locale {locale['prevision_log_rv']:.10f}, "
              f"écart {ecart:.2e}) ; réponse en {1000 * duree:.0f} ms ; " + ("CONFORME" if not problemes else "NON CONFORME : " + " ; ".join(problemes)))
        reussi = reussi and not problemes
    print("Vérification " + ("CONFORME" if reussi else "NON CONFORME") + ".")
    return 0 if reussi else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
