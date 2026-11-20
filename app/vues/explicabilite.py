"""Explicabilité : la découverte HAR-J d'abord, puis SHAP, importance par retard, attention, et fidélité par pli."""

import altair as alt
import pandas as pd
import streamlit as st

import outils_app as K

NOMS = {"rv_1": "RV du jour", "rv_7": "RV moyenne 7 j", "rv_30": "RV moyenne 30 j", "log_rv_1": "log RV du jour",
        "log_rv_7": "log RV moyenne 7 j", "log_rv_30": "log RV moyenne 30 j", "parkinson": "Parkinson", "garman_klass": "Garman-Klass",
        "log_rendement": "log-rendement", "log_volume": "log-volume", "rsi_14": "RSI 14 j", "macd_histogramme_relatif": "MACD relatif",
        "bollinger_largeur_relative": "largeur de Bollinger", "jour_semaine": "jour de la semaine", "y": "y (log RV du jour, TFT)"}
POURCENT_FR = "replace(format(datum.value * 100, '.0f'), '.', ',') + ' %'"
POURCENT_FR_1 = "replace(format(datum.value * 100, '.1f'), '.', ',') + ' %'"


def _barres(parts: dict, couleur: str):
    t = pd.DataFrame([{"Variable": NOMS.get(v, v), "Part": p} for v, p in sorted(parts.items(), key=lambda x: -x[1])])
    return alt.Chart(t).mark_bar(color=couleur).encode(
        x=alt.X("Part:Q", title="Part de l'importance", axis=alt.Axis(labelExpr=POURCENT_FR)),
        y=alt.Y("Variable:N", sort=list(t["Variable"]), title=None, axis=alt.Axis(labelOverlap=False, labelLimit=220, labelFontSize=13))
    ).properties(height=28 * len(t))


def _attention(at: dict):
    crise, autres = f"Jours de crise ({K.nombre(at['jours_crises'], 0)})", f"Autres jours ({K.nombre(at['jours_autres'], 0)})"
    t = pd.DataFrame([{"Retard": k + 1, "Poids": v, "Jours": crise} for k, v in enumerate(at["crises"])]
                     + [{"Retard": k + 1, "Poids": v, "Jours": autres} for k, v in enumerate(at["autres"])])
    return alt.Chart(t).mark_line(point=True).encode(
        x=alt.X("Retard:Q", title="Retard (1 = veille de la cible)"),
        y=alt.Y("Poids:Q", title="Poids d'attention moyen", scale=alt.Scale(zero=False), axis=alt.Axis(labelExpr=POURCENT_FR_1)),
        color=alt.Color("Jours:N", scale=alt.Scale(domain=[crise, autres], range=["#DC2626", "#2563EB"]), title=None,
                        legend=alt.Legend(orient="top"))                  # crises en rouge, comme la figure 9
    ).properties(height=320)


def afficher() -> None:
    st.title("Explicabilité (développement)")
    actif = st.selectbox("Actif", K.ACTIFS, format_func=lambda a: K.NOMS[a], key="actif_explicabilite")
    ex = K.json_rapport("explicabilite.json")["actifs"][actif]
    dev = K.json_rapport("comparaison_modeles.json")["actifs"][actif]
    test = K.json_rapport("test_final.json")["actifs"][actif]
    r = dev["classement"]["modele_retenu"]

    st.subheader("La découverte HAR-J")
    q = {m: dev["modeles"][m]["qlike_moyenne_des_plis"] for m in ("HAR-RV", "HAR-J", r)}
    part = (q["HAR-RV"] - q["HAR-J"]) / (q["HAR-RV"] - q[r])
    st.success(f"Les réseaux s'appuient beaucoup sur le jour de la semaine, que HAR-RV n'utilise pas. HAR-J ajoute ce seul jour à HAR-RV. "
               f"Sur le développement, HAR-J fait {K.pourcent(dev['gain_relatif_qlike']['HAR-J']['moyenne_des_plis'])} de mieux que HAR-RV et "
               f"comble {K.pourcent(part, 0)} de l'écart entre HAR-RV et {r}. Sur le test final, {r} fait "
               f"{K.pourcent(test['gain_sur_har_rv'][r])} de mieux que HAR-RV, mais {K.pourcent(test['gain_sur_har_j'][r])} de mieux que HAR-J.")

    st.subheader("Les variables les plus importantes")
    choix = list(ex["shap"]) + ["TFT"]
    modele = st.radio("Modèle", choix, horizontal=True, key="modele_importance",
                      format_func=lambda m: f"{m} (sélection des variables)" if m == "TFT" else f"{m} (SHAP)" + (" — retenu" if m == r else ""))
    parts = ex["tft"]["importance"] if modele == "TFT" else ex["shap"][modele]["parts"]
    st.altair_chart(_barres(parts, K.COULEURS[actif]), width="stretch")

    st.subheader("Importance par retard (retard 1 = veille de la cible)")
    series = {f"{m} (SHAP)": s["parts_par_retard"] for m, s in ex["shap"].items() if "parts_par_retard" in s}
    series["TFT (attention)"] = ex["tft"]["attention_par_retard"]
    series["Transformer (attention)"] = ex["attention_transformer"]["tous"]
    st.table(pd.DataFrame([{"Modèle": n, "Retard 1": K.pourcent(p[0]), "Retard 2": K.pourcent(p[1]), "Retard 3": K.pourcent(p[2]),
                            "Retards 1 à 5": K.pourcent(sum(p[:5]))} for n, p in series.items()]).set_index("Modèle"))
    st.image(str(K.figure(f"figure_8_importance_retards_{actif}.png")), width="stretch")

    st.subheader("Attention du Transformer : jours de crise et autres jours")
    at = ex["attention_transformer"]
    st.markdown(f"Part de l'attention sur les cinq derniers jours : {K.pourcent(sum(at['crises'][:5]))} pendant les crises "
                f"contre {K.pourcent(sum(at['autres'][:5]))} les autres jours. Attention presque uniforme : au plus "
                f"{K.pourcent(max(at['tous']))} par retard, pour {K.pourcent(1 / len(at['tous']))} si tous les retards pesaient autant.")
    st.altair_chart(_attention(at), width="stretch")
    st.caption("Limite : l'attention montre où le modèle regarde, pas nécessairement pourquoi il décide.")

    st.subheader("Fidélité de SHAP")
    st.markdown("Sur la validation interne de chaque pli, on permute la variable la mieux classée et la moins bien classée par SHAP : "
                "SHAP est « fidèle » si la première dégrade plus le QLIKE que la seconde.")
    st.table(pd.DataFrame([{"Modèle": m, "Résultat": f"fidèle sur {f['plis_fideles']} plis sur {f['plis']}"}
                           for m, f in ex["fidelite"].items()]).set_index("Modèle"))
    with st.expander("Détail pli par pli"):
        lignes = []
        for m, f in ex["fidelite"].items():
            for pli, x in f["par_pli"].items():
                lignes.append({"Modèle": m, "Pli": pli, "Meilleure variable": NOMS.get(x["meilleure"], x["meilleure"]),
                               "Dégradation (meilleure)": K.nombre(x["degradation_meilleure"], 4),
                               "Moins bonne variable": NOMS.get(x["moins_bonne"], x["moins_bonne"]),
                               "Dégradation (moins bonne)": K.nombre(x["degradation_moins_bonne"], 4), "Fidèle": "oui" if x["fidele"] else "non"})
        st.table(pd.DataFrame(lignes).set_index(["Modèle", "Pli"]))
    K.pied()
