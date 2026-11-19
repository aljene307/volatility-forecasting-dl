"""Explicabilité : SHAP, importance par retard, attention, fidélité par pli, et la découverte HAR-J."""

import pandas as pd
import streamlit as st

import outils_app as K

NOMS = {"rv_1": "RV du jour", "rv_7": "RV moyenne 7 j", "rv_30": "RV moyenne 30 j", "log_rv_1": "log RV du jour",
        "log_rv_7": "log RV moyenne 7 j", "log_rv_30": "log RV moyenne 30 j", "parkinson": "Parkinson", "garman_klass": "Garman-Klass",
        "log_rendement": "log-rendement", "log_volume": "log-volume", "rsi_14": "RSI 14 j", "macd_histogramme_relatif": "MACD relatif",
        "bollinger_largeur_relative": "largeur de Bollinger", "jour_semaine": "jour de la semaine", "y": "y (log RV du jour, TFT)"}


def afficher() -> None:
    st.title("Explicabilité (développement)")
    actif = st.selectbox("Actif", K.ACTIFS, format_func=lambda a: K.NOMS[a], key="actif_explicabilite")
    ex = K.json_rapport("explicabilite.json")["actifs"][actif]
    st.subheader("Les variables les plus importantes")
    lignes = []
    for m, s in ex["shap"].items():
        lignes.append({"Modèle": f"{m} (SHAP)", **{f"Rang {k + 1}": f"{NOMS.get(v, v)} ({K.pourcent(s['parts'][v])})"
                                                   for k, v in enumerate(s["classement"][:5])}})
    t = ex["tft"]["importance"]
    lignes.append({"Modèle": "TFT (sélection des variables)", **{f"Rang {k + 1}": f"{NOMS.get(v, v)} ({K.pourcent(t[v])})"
                                                                  for k, v in enumerate(sorted(t, key=t.get, reverse=True)[:5])}})
    st.table(pd.DataFrame(lignes).set_index("Modèle"))
    st.image(str(K.figure(f"figure_7_importance_variables_{actif}.png")), width="stretch")
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
                f"({K.nombre(at['jours_crises'], 0)} jours) contre {K.pourcent(sum(at['autres'][:5]))} les autres jours "
                f"({K.nombre(at['jours_autres'], 0)} jours). Attention presque uniforme : au plus {K.pourcent(max(at['tous']))} par retard, "
                f"pour {K.pourcent(1 / len(at['tous']))} si tous les retards pesaient autant.")
    st.image(str(K.figure("figure_9_attention_transformer.png")), width="stretch")
    st.caption("Limite : l'attention montre où le modèle regarde, pas nécessairement pourquoi il décide.")
    st.subheader("Fidélité de SHAP, pli par pli")
    st.markdown("Sur la validation interne de chaque pli, on permute la variable la mieux classée et la moins bien classée par SHAP : "
                "SHAP est « fidèle » si la première dégrade plus le QLIKE que la seconde.")
    lignes = []
    for m, f in ex["fidelite"].items():
        for pli, r in f["par_pli"].items():
            lignes.append({"Modèle": m, "Pli": pli, "Meilleure variable": NOMS.get(r["meilleure"], r["meilleure"]),
                           "Dégradation": K.nombre(r["degradation_meilleure"], 4), "Moins bonne": NOMS.get(r["moins_bonne"], r["moins_bonne"]),
                           "Dégradation ": K.nombre(r["degradation_moins_bonne"], 4), "Fidèle": "oui" if r["fidele"] else "non"})
    st.table(pd.DataFrame(lignes).set_index(["Modèle", "Pli"]))
    st.markdown(" ; ".join(f"{m} : fidèle sur {f['plis_fideles']} plis sur {f['plis']}" for m, f in ex["fidelite"].items()) + ".")
    st.subheader("La découverte HAR-J")
    dev = K.json_rapport("comparaison_modeles.json")["actifs"][actif]
    test = K.json_rapport("test_final.json")["actifs"][actif]
    r = dev["classement"]["modele_retenu"]
    q = {m: dev["modeles"][m]["qlike_moyenne_des_plis"] for m in ("HAR-RV", "HAR-J", r)}
    part = (q["HAR-RV"] - q["HAR-J"]) / (q["HAR-RV"] - q[r])
    st.markdown(f"Les réseaux s'appuient beaucoup sur le jour de la semaine, que HAR-RV n'utilise pas. HAR-J ajoute ce seul jour à HAR-RV. "
                f"Sur le développement, HAR-J fait {K.pourcent(dev['gain_relatif_qlike']['HAR-J']['moyenne_des_plis'])} de mieux que HAR-RV et "
                f"comble {K.pourcent(part, 0)} de l'écart entre HAR-RV et {r}. Sur le test final, {r} fait "
                f"{K.pourcent(test['gain_sur_har_rv'][r])} de mieux que HAR-RV, mais {K.pourcent(test['gain_sur_har_j'][r])} de mieux que HAR-J.")
    K.pied()
