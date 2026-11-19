"""Résultats : développement et test final ; QLIKE avec IC, Diebold-Mariano brutes et Holm ; sélecteur d'actif."""

import altair as alt
import pandas as pd
import streamlit as st

import outils_app as K

ORDRE = ["Persistance", "HAR-RV", "HAR-J", "GARCH(1,1)", "XGBoost", "LSTM", "GRU", "CNN-LSTM", "Transformer", "TFT"]


def _graphique(tableau: pd.DataFrame, actif: str, retenu: str, titre: str):
    couleurs = [K.COULEURS["retenu"] if m == retenu else K.COULEURS[actif] if m == "HAR-RV" else
                K.COULEURS["HAR-J"] if m == "HAR-J" else K.COULEURS["gris"] for m in tableau["Modèle"]]
    base = alt.Chart(tableau).encode(y=alt.Y("Modèle:N", sort=list(tableau["Modèle"]), title=None))
    points = base.mark_point(filled=True, size=70).encode(
        x=alt.X("QLIKE:Q", title="QLIKE (plus bas = meilleur)", axis=alt.Axis(format=",.2f")),
        color=alt.Color("Modèle:N", scale=alt.Scale(domain=list(tableau["Modèle"]), range=couleurs), legend=None))
    barres = base.mark_rule().encode(x="bas:Q", x2="haut:Q", color=alt.Color("Modèle:N", legend=None))
    return (barres + points).properties(title=titre, height=300)


def afficher() -> None:
    st.title("Résultats")
    actif = st.selectbox("Actif", K.ACTIFS, format_func=lambda a: K.NOMS[a], key="actif_resultats")
    dev = K.json_rapport("comparaison_modeles.json")["actifs"][actif]
    test = K.json_rapport("test_final.json")["actifs"][actif]
    retenu = dev["classement"]["modele_retenu"]
    st.markdown(f"Modèle retenu par la règle de sélection (QLIKE moyen par pli sur le développement) : **{retenu}**.")
    onglet_dev, onglet_test = st.tabs([f"Développement ({len(dev['modeles']['HAR-RV']['par_pli'])} plis réunis)", "Test final"])
    with onglet_dev:
        lignes = [{"Modèle": m, "QLIKE": dev["modeles"][m]["reunis"]["qlike"], "bas": dev["modeles"][m]["reunis"]["qlike_intervalle"]["bas"],
                   "haut": dev["modeles"][m]["reunis"]["qlike_intervalle"]["haut"]} for m in ORDRE]
        st.altair_chart(_graphique(pd.DataFrame(lignes), actif, retenu, "QLIKE et intervalle de confiance à 95 % (développement)"),
                        width="stretch")
        st.table(pd.DataFrame([{"Modèle": x["Modèle"], "QLIKE [IC 95 %]": f"{K.nombre(x['QLIKE'])} [{K.nombre(x['bas'])} ; {K.nombre(x['haut'])}]",
                                "QLIKE moyen par pli": K.nombre(dev["modeles"][x["Modèle"]]["qlike_moyenne_des_plis"])} for x in lignes]).set_index("Modèle"))
        st.markdown(f"**Diebold-Mariano contre HAR-RV** (famille de Holm : les {len(dev['diebold_mariano'])} comparaisons) :")
        st.table(pd.DataFrame([{"Modèle": m, "Différence moyenne": K.nombre(t["moyenne_difference"], 4), "p-valeur brute": K.p_valeur(t["p_valeur"]),
                                "p-valeur ajustée (Holm)": K.p_valeur(t["p_valeur_holm"]), "Significatif (ajustée)": "oui" if t["significatif_holm"] else "non"}
                               for m, t in dev["diebold_mariano"].items()]).set_index("Modèle"))
        st.image(str(K.figure(f"figure_5_deep_learning_{actif}.png")), width="stretch")
    with onglet_test:
        lignes = [{"Modèle": m, "QLIKE": test["modeles"][m]["qlike"], "bas": test["modeles"][m]["qlike_intervalle"]["bas"],
                   "haut": test["modeles"][m]["qlike_intervalle"]["haut"]} for m in ORDRE]
        st.altair_chart(_graphique(pd.DataFrame(lignes), actif, retenu, "QLIKE et intervalle de confiance à 95 % (test final)"),
                        width="stretch")
        st.table(pd.DataFrame([{"Modèle": x["Modèle"], "QLIKE [IC 95 %]": f"{K.nombre(x['QLIKE'])} [{K.nombre(x['bas'])} ; {K.nombre(x['haut'])}]",
                                "Gain sur HAR-RV": K.pourcent(test["gain_sur_har_rv"][x["Modèle"]]),
                                "Gain sur HAR-J": K.pourcent(test["gain_sur_har_j"][x["Modèle"]])} for x in lignes]).set_index("Modèle"))
        h = K.json_rapport("test_final.json")["hypotheses"]
        st.markdown(f"**Tests principaux** (Holm sur les deux actifs) : H1 contre HAR-RV, p-valeur ajustée "
                    f"{K.p_valeur(h['H1'][actif]['p_valeur_holm_2_actifs'])} ; H7 contre HAR-J, p-valeur ajustée "
                    f"{K.p_valeur(h['H7'][actif]['p_valeur_holm_2_actifs'])}.")
        n = len(test["diebold_mariano"])
        st.markdown(f"**Diebold-Mariano contre HAR-RV** (descriptif, Holm sur les {n} comparaisons) :")
        st.table(pd.DataFrame([{"Modèle": m, "Différence moyenne": K.nombre(t["moyenne_difference"], 4), "p-valeur brute": K.p_valeur(t["p_valeur"]),
                                f"p-valeur ajustée (Holm sur {n})": K.p_valeur(t["p_valeur_holm_7_descriptif"])}
                               for m, t in test["diebold_mariano"].items()]).set_index("Modèle"))
        st.image(str(K.figure(f"figure_10_test_previsions_{actif}.png")), width="stretch")
    K.pied()
