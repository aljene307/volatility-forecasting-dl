"""Exploration : les figures déjà produites, chacune avec une phrase d'explication."""

import streamlit as st

import outils_app as K

FIGURES = [
    ("figure_1_rv_annualisee.png", "Volatilité réalisée annualisée sur le développement : elle varie beaucoup et monte par pics, "
                                   "surtout pendant les crises."),
    ("figure_2_autocorrelation_log_rv.png", "Autocorrélation du log de la RV : la volatilité d'aujourd'hui dit beaucoup de celle des "
                                            "jours suivants, et cette mémoire décroît lentement — c'est ce qu'exploite HAR-RV. Les pics qui reviennent "
                                            "chaque semaine montrent l'effet du jour de la semaine, que HAR-J ajoute à HAR-RV."),
    ("figure_3_histogrammes_rv.png", "Histogrammes de la RV : la distribution est très asymétrique ; son logarithme est beaucoup plus "
                                     "proche d'une courbe en cloche, d'où la cible en log."),
]


def afficher() -> None:
    st.title("Exploration (développement seulement)")
    for nom, phrase in FIGURES:
        st.image(str(K.figure(nom)), width="stretch")
        st.markdown(phrase)
    K.pied()
