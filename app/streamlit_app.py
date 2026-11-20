"""Application Streamlit du projet (en français). Lancement local : voir le README, section « Application ».

Aucun calcul lourd : seulement des fichiers précalculés (rapports/, figures/, config/), lus avec st.cache_data.
Aucun chiffre tapé à la main. Données : Binance Vision, CC BY-NC-SA 4.0.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402

import outils_app  # noqa: E402,F401
from vues import accueil, demonstration, explicabilite, exploration, limites, methode, resultats, strategie  # noqa: E402

st.set_page_config(page_title="Volatilité crypto", page_icon="📈", layout="wide")

PAGES = [
    st.Page(accueil.afficher, title="Accueil", default=True),          # page par défaut : adresse « / »
    st.Page(methode.afficher, title="Données et méthode", url_path="methode"),
    st.Page(exploration.afficher, title="Exploration", url_path="exploration"),
    st.Page(resultats.afficher, title="Résultats", url_path="resultats"),
    st.Page(strategie.afficher, title="Stratégie", url_path="strategie"),
    st.Page(explicabilite.afficher, title="Explicabilité", url_path="explicabilite"),
    st.Page(demonstration.afficher, title="Démonstration", url_path="demonstration"),
    st.Page(limites.afficher, title="Limites", url_path="limites"),
]

st.navigation(PAGES).run()
