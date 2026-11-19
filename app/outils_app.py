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
    return texte.replace("-", "−")


def pourcent(x: float, decimales: int = 1) -> str:
    return nombre(100 * x, decimales) + " %"


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


def pied() -> None:
    st.divider()
    st.caption(f"{MENTION}. Code sous licence MIT ; résultats, figures et modèles : CC BY-NC-SA 4.0. "
               f"Projet éducatif, non commercial — [dépôt GitHub]({DEPOT}).")


def lien_commit(identifiant: str) -> str:
    return f"[`{identifiant}`]({DEPOT}/commit/{identifiant})"
