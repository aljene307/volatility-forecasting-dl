"""Données et méthode : parcours des données, règles écrites avant le calcul, walk-forward, contrôles de fuite, licence."""

import pandas as pd
import streamlit as st

import outils_app as K

# Commits qui ont fixé des règles AVANT les calculs correspondants (identifiants de commits, pas des résultats)
COMMITS_REGLES = [
    ("31b9dae", "Règles initiales, avant tout téléchargement de données"),
    ("d348928", "Règles des variables, avant leur calcul"),
    ("ca008d1", "Règles de l'entraînement, avant tout entraînement"),
    ("a370ebb", "Exceptions datées : plis annuels, réglage unique, budget"),
    ("2e2ac52", "Évaluation et baselines, avant leur calcul"),
    ("6682d32", "Ajustement de Holm, avant de lire les résultats du deep learning"),
    ("e158870", "Explicabilité, avant tout calcul"),
    ("96b896d", "Attentes du test final et HAR-J, avant l'ouverture"),
    ("0359186", "Hypothèse H7, avant l'ouverture"),
    ("dd55c85", "API, avant son code"),
]

SCHEMA = """
digraph {
  rankdir=TB; node [shape=box, style="rounded,filled", fillcolor="#F3F4F6", fontname="Helvetica", fontsize=16];
  b [label="Bougies de 5 minutes\\n(Binance Vision)"]; q [label="Contrôle de qualité\\n(jours valides)"];
  v [label="Variables du jour J\\n(passé seulement)"]; c [label="Cible : log RV de J+1"];
  w [label="Walk-forward\\n(ajustement, validation, évaluation)"]; m [label="Modèles\\n(baselines, réseaux)"];
  e [label="Évaluation\\n(QLIKE, Diebold-Mariano, Holm)"]; s [label="Stratégie et VaR"]; t [label="Test final\\n(ouvert une fois)"];
  b -> q -> v -> w; q -> c -> w; w -> m -> e -> s; e -> t;
}
"""


def afficher() -> None:
    st.title("Données et méthode")
    st.subheader("Parcours des données")
    st.graphviz_chart(SCHEMA)
    st.markdown("Chaque variable du jour J est calculée avec les seules données disponibles à la clôture de J ; la cible est la "
                "volatilité réalisée du lendemain, calculée avec les bougies de 5 minutes de J+1.")
    st.subheader("Règles écrites avant le calcul")
    st.markdown("Les règles sont écrites et commitées AVANT chaque calcul ; une précision ajoutée après coup est datée et dite "
                "honnêtement dans le journal des choix. Exemples de commits de règles :")
    st.markdown("\n".join(f"- {K.lien_commit(c)} : {texte}" for c, texte in COMMITS_REGLES))
    st.subheader("Walk-forward")
    import regles as R
    lignes = [{"Découpage": d["nom"], "Ajustement": f"{d['ajustement'][0]} → {d['ajustement'][1]}",
               "Validation interne": f"{d['validation'][0]} → {d['validation'][1]}",
               "Période évaluée": f"{d['evaluation'][0]} → {d['evaluation'][1]}"} for d in R.decoupages(K.regles())]
    st.table(pd.DataFrame(lignes).set_index("Découpage"))
    st.caption("Chaque modèle est ajusté sur le passé, réglé sur la validation interne, puis évalué sur l'année suivante ; "
               "les transformations sont apprises sur la fenêtre d'ajustement de chaque découpage.")
    st.subheader("Contrôles de fuite")
    cf = K.json_rapport("controles_fuite.json")
    lignes = []
    for a in K.ACTIFS:
        am = cf["actifs"][a]["avenir_modifie"]
        ecarts = sum(x["ecarts"] for x in am["modeles"].values())
        comparees = sum(x["previsions_comparees"] for x in am["modeles"].values())
        g = cf["actifs"][a]["cible_melangee"]["gain_sur_har_rv"]["moyenne_des_plis"]
        lignes.append({"Actif": K.NOMS[a], "Avenir modifié (tous les réseaux) : écarts / prévisions comparées":
                       f"{K.nombre(ecarts, 0)} / {K.nombre(comparees, 0)}",
                       "Jour J du test de l'avenir modifié": am["jour_j"], "LSTM à cible mélangée : gain sur HAR-RV": K.pourcent(g)})
    st.table(pd.DataFrame(lignes).set_index("Actif"))
    st.markdown("- **Avenir modifié** : toutes les données après le jour J sont modifiées ; aucune prévision faite avant J ne doit "
                "changer (0 écart exigé, au bit près).\n"
                "- **Cible mélangée** : un réseau entraîné sur des cibles permutées au hasard ne peut rien apprendre ; il doit faire "
                "nettement moins bien que HAR-RV. Sinon, l'information viendrait d'ailleurs : fuite probable.")
    st.subheader("Licence")
    st.markdown("Les données sont fournies par Binance (data.binance.vision) sous la licence CC BY-NC-SA 4.0 et les conditions « Vision "
                "Dataset Terms », dans un cadre éducatif et non commercial. Aucune donnée brute ni aucune série journalière dérivée n'est "
                "publiée : seulement des résultats agrégés, des figures et des modèles, sous la même licence.")
    K.pied()
