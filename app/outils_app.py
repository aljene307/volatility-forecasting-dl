"""Outils communs de l'application : lectures en cache des fichiers précalculés, format français, couleurs, licence.

Aucun calcul lourd et aucun chiffre tapé à la main : tout est lu dans les JSON du dépôt (rapports/, config/).
Aucune série journalière dérivée n'est affichée en tableau téléchargeable (licence des données).
"""

from __future__ import annotations

import json
import os
import sys
import tomllib
from pathlib import Path

import streamlit as st

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

MENTION = "Données : Binance Vision, CC BY-NC-SA 4.0"
DEPOT = "https://github.com/aljene307/volatility-forecasting-dl"
API_PAR_DEFAUT = "http://127.0.0.1:8000"
COULEURS = {"BTCUSDT": "#D97706", "ETHUSDT": "#2563EB", "retenu": "#7C3AED", "gris": "#999999", "HAR-J": "#16A34A"}
NOMS = {"BTCUSDT": "BTC", "ETHUSDT": "ETH"}
ACTIFS = ["BTCUSDT", "ETHUSDT"]


@st.cache_data
def json_rapport(nom: str) -> dict:
    return json.loads((RACINE / "rapports" / nom).read_text(encoding="utf-8"))


@st.cache_data
def attentes() -> dict:
    return tomllib.loads((RACINE / "config" / "attentes_test.toml").read_text(encoding="utf-8"))


@st.cache_data
def regles() -> dict:
    import regles as R
    return R.charger_regles()


def figure(nom: str) -> Path:
    return RACINE / "figures" / nom


def nombre(x: float, decimales: int = 3) -> str:
    """Nombre au format français : virgule décimale, espace fine insécable pour les milliers, vrai signe moins."""
    if x is None:
        return "—"
    texte = f"{x:,.{decimales}f}".replace(",", " ").replace(".", ",").replace(" ", " ")
    if texte.startswith("-") and not any(c in "123456789" for c in texte):
        texte = texte[1:]                                    # « −0,0 » : une valeur arrondie à zéro n'a pas de signe
    return texte.replace("-", "−")


def pourcent(x: float, decimales: int = 1) -> str:
    return nombre(100 * x, decimales) + " %"          # espace insécable : « 32,2 % » n'est jamais coupé


def p_valeur(p: float) -> str:
    return nombre(p, 4) if p >= 0.0001 else "< 0,0001"


def adresse_api() -> str:
    """Adresse de l'API : st.secrets["API_URL"], sinon la variable d'environnement API_URL, sinon la valeur par défaut.
    L'application fonctionne sans aucun fichier de secrets."""
    try:
        valeur = st.secrets.get("API_URL")
    except Exception:                       # aucun fichier de secrets : c'est permis
        valeur = None
    return (valeur or os.environ.get("API_URL") or API_PAR_DEFAUT).rstrip("/")


def adresse_locale(adresse: str) -> bool:
    return any(h in adresse for h in ("127.0.0.1", "localhost", "0.0.0.0"))


# --- Résumé « Ce qu'on a trouvé » : mêmes valeurs pour le français et l'anglais ------------------------------

def valeurs_trouvailles() -> dict:
    """Valeurs du résumé, lues dans rapports/test_final.json (aucun chiffre tapé à la main)."""
    t = json_rapport("test_final.json")
    v = {"periode": t["periode"], "actifs": {}}
    for a in ACTIFS:
        r = t["actifs"][a]
        retenu = r["modele_retenu"]
        q = {m: r["modeles"][m]["qlike"] for m in ("HAR-RV", "HAR-J", retenu)}
        v["actifs"][a] = {"retenu": retenu, "gain_har_rv": r["gain_sur_har_rv"][retenu], "gain_har_j": r["gain_sur_har_j"][retenu],
                          "part_jour_semaine": (q["HAR-RV"] - q["HAR-J"]) / (q["HAR-RV"] - q[retenu]),
                          "h1": t["hypotheses"]["H1"][a]["confirmee"],
                          "sharpe": r["strategie"]["difference_sharpe_retenu_moins_har"]}
    return v


def phrases_trouvailles(v: dict, langue: str = "fr") -> list[str]:
    """Les trois phrases du résumé, en français ou en anglais, générées depuis les MÊMES valeurs."""
    fr = langue == "fr"
    pc = (lambda x, d=1: pourcent(x, d)) if fr else (lambda x, d=1: f"{100 * x:.{d}f}%")
    nb = (lambda x: nombre(x, 2)) if fr else (lambda x: f"{x:.2f}")
    A = v["actifs"]
    noms = {a: f"{NOMS[a]}, {A[a]['retenu']}" for a in ACTIFS}
    tous_h1 = all(A[a]["h1"] for a in ACTIFS)
    p1 = (f"Sur le test final ({v['periode'][0]} au {v['periode'][1]}), le modèle retenu fait mieux que HAR-RV de "
          + " et de ".join(f"{pc(A[a]['gain_har_rv'])} ({noms[a]})" for a in ACTIFS) + " en QLIKE"
          + (", de façon significative (H1 confirmée pour les deux actifs)." if tous_h1 else ".")) if fr else \
         (f"On the final test ({v['periode'][0]} to {v['periode'][1]}), the selected model beats HAR-RV by "
          + " and ".join(f"{pc(A[a]['gain_har_rv'])} ({noms[a]})" for a in ACTIFS) + " in QLIKE"
          + (", significantly (H1 confirmed for both assets)." if tous_h1 else "."))
    p2 = ("Mais une grande part vient du jour de la semaine : face à HAR-J (HAR-RV + jour de la semaine), le gain n'est plus que de "
          + " et de ".join(f"{pc(A[a]['gain_har_j'])} ({NOMS[a]})" for a in ACTIFS) + " ; ce seul ajout comble "
          + " et ".join(f"{pc(A[a]['part_jour_semaine'], 0)} ({NOMS[a]})" for a in ACTIFS)
          + " de l'écart entre HAR-RV et le modèle retenu.") if fr else \
         ("But a large part comes from the day of the week: against HAR-J (HAR-RV + day of the week), the gain shrinks to "
          + " and ".join(f"{pc(A[a]['gain_har_j'])} ({NOMS[a]})" for a in ACTIFS) + "; this single addition closes "
          + " and ".join(f"{pc(A[a]['part_jour_semaine'], 0)} ({NOMS[a]})" for a in ACTIFS)
          + " of the gap between HAR-RV and the selected model.")
    nette = [a for a in ACTIFS if A[a]["sharpe"]["bas"] > 0]
    detail = " ; ".join(f"{NOMS[a]} : {nb(A[a]['sharpe']['valeur'])} [{nb(A[a]['sharpe']['bas'])} ; {nb(A[a]['sharpe']['haut'])}]"
                        for a in ACTIFS) if fr else \
        "; ".join(f"{NOMS[a]}: {nb(A[a]['sharpe']['valeur'])} [{nb(A[a]['sharpe']['bas'])}, {nb(A[a]['sharpe']['haut'])}]" for a in ACTIFS)
    if fr:
        p3 = (("La stratégie de pilotage par la volatilité n'en profite pas" if not nette else
               "La stratégie de pilotage par la volatilité en profite pour " + " et ".join(NOMS[a] for a in nette))
              + f" : différence de Sharpe avec HAR-RV et intervalle à 95 % ({detail}).")
    else:
        p3 = (("The volatility-targeting strategy does not benefit" if not nette else
               "The volatility-targeting strategy benefits for " + " and ".join(NOMS[a] for a in nette))
              + f": Sharpe ratio difference with HAR-RV and 95% interval ({detail}).")
    return [p1, p2, p3]


def pied() -> None:
    st.divider()
    st.caption(f"{MENTION}. Code sous licence MIT ; résultats, figures et modèles : CC BY-NC-SA 4.0. "
               f"Projet éducatif, non commercial — [dépôt GitHub]({DEPOT}).")


def lien_commit(identifiant: str) -> str:
    return f"[`{identifiant}`]({DEPOT}/commit/{identifiant})"
