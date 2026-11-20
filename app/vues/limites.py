"""Limites : liste honnête, chaque chiffre lu dans les JSON."""

import streamlit as st

import outils_app as K
import resume as RES


def afficher() -> None:
    st.title("Limites")
    points = RES.points_limites(K.json_rapport("test_final.json"), K.attentes(), K.json_rapport("comparaison_modeles.json"),
                                K.json_rapport("explicabilite.json"), K.regles())
    st.markdown("\n".join(f"- {p}" for p in points))
    K.pied()
