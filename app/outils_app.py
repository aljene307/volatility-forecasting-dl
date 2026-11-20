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

import resume as RES  # noqa: E402

MENTION = "Données : Binance Vision, CC BY-NC-SA 4.0"
DEPOT = "https://github.com/aljene307/volatility-forecasting-dl"
API_PAR_DEFAUT = "https://volatilite-api.onrender.com"     # API publique (Render) ; remplaçable par st.secrets ou API_URL
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


nombre, pourcent, p_valeur = RES.nombre, RES.pourcent, RES.p_valeur   # format français partagé (src/resume.py)


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


# --- Résumé « Ce qu'on a trouvé » : une seule source (src/resume.py) pour l'application, le README et la synthèse ---

def valeurs_trouvailles() -> dict:
    return RES.valeurs_trouvailles(json_rapport("test_final.json"))


phrases_trouvailles = RES.phrases_trouvailles


def pied() -> None:
    st.divider()
    st.caption(f"{MENTION}. Code sous licence MIT ; résultats, figures et modèles : CC BY-NC-SA 4.0. "
               f"Projet éducatif, non commercial — [dépôt GitHub]({DEPOT}).")


def lien_commit(identifiant: str) -> str:
    return f"[`{identifiant}`]({DEPOT}/commit/{identifiant})"
