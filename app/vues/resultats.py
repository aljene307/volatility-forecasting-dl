"""Résultats : test final puis développement ; QLIKE avec IC, Diebold-Mariano brutes et Holm ; sélecteur d'actif."""

import altair as alt
import pandas as pd
import streamlit as st

import outils_app as K

ORDRE = ["Persistance", "HAR-RV", "HAR-J", "GARCH(1,1)", "XGBoost", "LSTM", "GRU", "CNN-LSTM", "Transformer", "TFT"]
FORMAT_FR = "replace(format(datum.value, '.2f'), '.', ',')"      # axes au format français


def _graphique(tableau: pd.DataFrame, actif: str, retenu: str, titre: str):
    """Point (QLIKE) et intervalle à 95 % pour chaque modèle, dans l'ordre des modèles ; les 10 étiquettes sont affichées."""
    couleurs = [K.COULEURS["retenu"] if m == retenu else K.COULEURS[actif] if m == "HAR-RV" else
                K.COULEURS["HAR-J"] if m == "HAR-J" else K.COULEURS["gris"] for m in tableau["Modèle"]]
    marge = 0.05 * (tableau["haut"].max() - tableau["bas"].min())
    echelle_x = alt.Scale(domain=[tableau["bas"].min() - marge, tableau["haut"].max() + marge], zero=False, nice=False)
    axe_y = alt.Axis(labelOverlap=False, labelLimit=200, labelFontSize=13, labelExpr=f"datum.value == '{retenu}' ? datum.value + ' (retenu)' : datum.value")
    base = alt.Chart(tableau).encode(y=alt.Y("Modèle:N", sort=list(tableau["Modèle"]), title=None, axis=axe_y))
    couleur = alt.Color("Modèle:N", scale=alt.Scale(domain=list(tableau["Modèle"]), range=couleurs), legend=None)
    barres = base.mark_rule(strokeWidth=2).encode(x=alt.X("bas:Q", scale=echelle_x, title="QLIKE (plus bas = meilleur)",
                                                          axis=alt.Axis(labelExpr=FORMAT_FR)), x2="haut:Q", color=couleur)
    points = base.mark_point(filled=True, size=90).encode(x=alt.X("QLIKE:Q", scale=echelle_x), color=couleur)
    return (barres + points).properties(title=titre, height=36 * len(tableau))


def _lignes(modeles: dict, cle_reunis: bool) -> list[dict]:
    return [{"Modèle": m, "QLIKE": (modeles[m]["reunis"] if cle_reunis else modeles[m])["qlike"],
             "bas": (modeles[m]["reunis"] if cle_reunis else modeles[m])["qlike_intervalle"]["bas"],
             "haut": (modeles[m]["reunis"] if cle_reunis else modeles[m])["qlike_intervalle"]["haut"]} for m in ORDRE]


def _ic(x: dict) -> str:
    return f"{K.nombre(x['QLIKE'])} [{K.nombre(x['bas'])} ; {K.nombre(x['haut'])}]"


def afficher() -> None:
    st.title("Résultats")
    actif = st.selectbox("Actif", K.ACTIFS, format_func=lambda a: K.NOMS[a], key="actif_resultats")
    dev = K.json_rapport("comparaison_modeles.json")["actifs"][actif]
    test = K.json_rapport("test_final.json")["actifs"][actif]
    h = K.json_rapport("test_final.json")["hypotheses"]
    retenu = dev["classement"]["modele_retenu"]
    st.markdown(f"Modèle retenu par la règle de sélection (QLIKE moyen par pli sur le développement) : **{retenu}**.")
    onglet_test, onglet_dev = st.tabs(["Test final", f"Développement ({len(dev['modeles']['HAR-RV']['par_pli'])} plis réunis)"])
    with onglet_test:
        lignes = _lignes(test["modeles"], False)
        st.altair_chart(_graphique(pd.DataFrame(lignes), actif, retenu, "QLIKE et intervalle de confiance à 95 % (test final)"),
                        width="stretch")
        st.table(pd.DataFrame([{"Modèle": x["Modèle"], "QLIKE [IC 95 %]": _ic(x), "Gain sur HAR-RV": K.pourcent(test["gain_sur_har_rv"][x["Modèle"]]),
                                "Gain sur HAR-J": K.pourcent(test["gain_sur_har_j"][x["Modèle"]])} for x in lignes]).set_index("Modèle"))
        st.markdown(f"**Tests principaux** (Holm sur les deux actifs) : H1 contre HAR-RV, p-valeur ajustée "
                    f"{K.p_valeur(h['H1'][actif]['p_valeur_holm_2_actifs'])} ; H7 contre HAR-J, p-valeur ajustée "
                    f"{K.p_valeur(h['H7'][actif]['p_valeur_holm_2_actifs'])}.")
        n = len(test["diebold_mariano"])
        st.markdown(f"**Diebold-Mariano contre HAR-RV** (descriptif, Holm sur les {n} comparaisons) :")
        st.table(pd.DataFrame([{"Modèle": m, "Différence moyenne": K.nombre(t["moyenne_difference"], 4), "p-valeur brute": K.p_valeur(t["p_valeur"]),
                                f"p-valeur ajustée (Holm sur {n})": K.p_valeur(t["p_valeur_holm_7_descriptif"])}
                               for m, t in ((m, test["diebold_mariano"][m]) for m in ORDRE if m in test["diebold_mariano"])]).set_index("Modèle"))
        st.image(str(K.figure(f"figure_10_test_previsions_{actif}.png")), width="stretch")
    with onglet_dev:
        lignes = _lignes(dev["modeles"], True)
        st.altair_chart(_graphique(pd.DataFrame(lignes), actif, retenu, "QLIKE et intervalle de confiance à 95 % (développement)"),
                        width="stretch")
        st.table(pd.DataFrame([{"Modèle": x["Modèle"], "QLIKE [IC 95 %]": _ic(x),
                                "QLIKE moyen par pli": K.nombre(dev["modeles"][x["Modèle"]]["qlike_moyenne_des_plis"])} for x in lignes]).set_index("Modèle"))
        st.markdown(f"**Diebold-Mariano contre HAR-RV** (famille de Holm : les {len(dev['diebold_mariano'])} comparaisons) :")
        st.table(pd.DataFrame([{"Modèle": m, "Différence moyenne": K.nombre(t["moyenne_difference"], 4), "p-valeur brute": K.p_valeur(t["p_valeur"]),
                                "p-valeur ajustée (Holm)": K.p_valeur(t["p_valeur_holm"]), "Significatif (ajustée)": "oui" if t["significatif_holm"] else "non"}
                               for m, t in ((m, dev["diebold_mariano"][m]) for m in ORDRE if m in dev["diebold_mariano"])]).set_index("Modèle"))
        st.image(str(K.figure(f"figure_5_deep_learning_{actif}.png")), width="stretch")
    K.pied()
