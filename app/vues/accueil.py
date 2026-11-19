"""Accueil : résumé du projet et verdicts du test final (lus dans rapports/test_final.json)."""

import pandas as pd
import streamlit as st

import outils_app as K

ENONCES = {"H1": "QLIKE du modèle retenu < QLIKE de HAR-RV (principale)", "H2": "QLIKE de HAR-RV < QLIKE de la persistance",
           "H3": "QLIKE de GARCH(1,1) > QLIKE de HAR-RV", "H4": "VaR de HAR-RV non rejetée par le test de Kupiec",
           "H5": "Stratégie du modèle retenu : volatilité et drawdown plus faibles que l'achat simple",
           "H6": "Gain du modèle retenu sur HAR-J < gain sur HAR-RV (descriptive)",
           "H7": "QLIKE du modèle retenu < QLIKE de HAR-J (secondaire)"}


def afficher() -> None:
    t, a = K.json_rapport("test_final.json"), K.attentes()
    st.title("Prévision de la volatilité des cryptomonnaies par deep learning")
    st.markdown(
        "- **But** : prévoir la volatilité réalisée du lendemain du bitcoin et de l'ether, à partir de bougies de 5 minutes.\n"
        "- **Modèles** : LSTM, GRU, CNN-LSTM, Transformer et TFT, comparés à HAR-RV, GARCH(1,1) et XGBoost.\n"
        "- **Méthode** : règles écrites et commitées avant chaque calcul, découpage chronologique strict, contrôles de fuite.\n"
        "- **Test final** : ouvert une seule fois, avec des attentes écrites avant l'ouverture ; tous les résultats sont publiés.\n"
        "- **Usage** : la prévision pilote une stratégie de volatility targeting et une VaR à un jour.")
    st.subheader("Verdicts du test final")
    st.caption(f"Test ouvert le {t['ouvert_le'][:10]} (code du commit {t['commit_du_code'][:7]}), dates de cible du "
               f"{t['periode'][0]} au {t['periode'][1]}.")
    lignes = []
    for h, enonce in ENONCES.items():
        lignes.append({"Hypothèse": h, "Énoncé": enonce,
                       **{f"{K.NOMS[x]} ({t['actifs'][x]['modele_retenu']})": "confirmée" if t["hypotheses"][h][x]["confirmee"] else "non confirmée"
                          for x in K.ACTIFS}})
    st.table(pd.DataFrame(lignes).set_index("Hypothèse"))
    pr, pj = a["prevision"], a["prevision_har_j"]
    st.table(pd.DataFrame([
        {"Prévision écrite avant l'ouverture": f"Gain du modèle retenu sur HAR-RV : {K.pourcent(pr['gain_min'], 0)} à {K.pourcent(pr['gain_max'], 0)}",
         **{K.NOMS[x]: K.pourcent(t["hypotheses"]["prevision"][x]["gain"]) for x in K.ACTIFS}},
        {"Prévision écrite avant l'ouverture": f"Gain du modèle retenu sur HAR-J : {K.pourcent(pj['gain_min'], 0)} à {K.pourcent(pj['gain_max'], 0)}",
         **{K.NOMS[x]: K.pourcent(t["hypotheses"]["prevision_har_j"][x]["gain"]) for x in K.ACTIFS}}]).set_index("Prévision écrite avant l'ouverture"))
    au_dessus = [K.NOMS[x] for x in K.ACTIFS if t["hypotheses"]["prevision"][x]["gain"] > pr["gain_max"]]
    if au_dessus:
        st.info("Le gain observé dépasse la prévision écrite avant l'ouverture pour " + " et ".join(au_dessus)
                + " : la prévision était trop prudente.")
    K.pied()
