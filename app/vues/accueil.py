"""Accueil : ce qu'on a trouvé, comment c'est prouvé, et les verdicts du test final (lus dans rapports/test_final.json)."""

import pandas as pd
import streamlit as st

import outils_app as K

ENONCES = {"H1": "Retenu < HAR-RV (principale)", "H2": "HAR-RV < persistance", "H3": "GARCH > HAR-RV", "H4": "VaR de HAR-RV valide (Kupiec)",
           "H5": "Stratégie moins risquée que l'achat simple", "H6": "Gain sur HAR-J < gain sur HAR-RV", "H7": "Retenu < HAR-J (secondaire)"}


def afficher() -> None:
    t, a = K.json_rapport("test_final.json"), K.attentes()
    st.title("Prévision de la volatilité des cryptomonnaies par deep learning")
    st.markdown("Prévoir la volatilité du lendemain du bitcoin et de l'ether à partir de bougies de 5 minutes, en comparant des réseaux "
                "de neurones (LSTM, GRU, CNN-LSTM, Transformer, TFT) à des modèles classiques (HAR-RV, GARCH, XGBoost).")
    valeurs = K.valeurs_trouvailles()
    st.subheader("Ce qu'on a trouvé")
    st.success("\n\n".join(K.phrases_trouvailles(valeurs, "fr")))
    st.markdown(f"**Comment c'est prouvé** : les règles ont été publiées sur GitHub avant chaque calcul ; le test "
                f"{t['periode'][0][:4]}-{t['periode'][1][:4]} n'a été ouvert qu'une seule fois ; les hypothèses et les gains attendus "
                f"avaient été déclarés à l'avance ([attentes du test]({K.DEPOT}/blob/main/docs/ATTENTES_TEST.md)).")
    with st.expander("In English"):
        st.markdown("Forecasting next-day volatility of bitcoin and ether from 5-minute candles, comparing neural networks with classical "
                    "models.\n\n" + "\n\n".join(K.phrases_trouvailles(valeurs, "en")))
    st.subheader("Verdicts du test final")
    st.caption(f"Test ouvert le {t['ouvert_le'][:10]} (code du commit {t['commit_du_code'][:7]}), dates de cible du "
               f"{t['periode'][0]} au {t['periode'][1]}.")
    lignes = [{"Hypothèse": f"{h} : {e}", **{f"{K.NOMS[x]} ({t['actifs'][x]['modele_retenu']})":
                                              "confirmée" if t["hypotheses"][h][x]["confirmee"] else "non confirmée" for x in K.ACTIFS}}
              for h, e in ENONCES.items()]
    st.table(pd.DataFrame(lignes).set_index("Hypothèse"))
    pr, pj = a["prevision"], a["prevision_har_j"]
    st.table(pd.DataFrame([
        {"Prévision écrite avant l'ouverture": f"Gain sur HAR-RV : {K.pourcent(pr['gain_min'], 0)} à {K.pourcent(pr['gain_max'], 0)}",
         **{K.NOMS[x]: K.pourcent(t["hypotheses"]["prevision"][x]["gain"]) for x in K.ACTIFS}},
        {"Prévision écrite avant l'ouverture": f"Gain sur HAR-J : {K.pourcent(pj['gain_min'], 0)} à {K.pourcent(pj['gain_max'], 0)}",
         **{K.NOMS[x]: K.pourcent(t["hypotheses"]["prevision_har_j"][x]["gain"]) for x in K.ACTIFS}}]).set_index("Prévision écrite avant l'ouverture"))
    au_dessus = [K.NOMS[x] for x in K.ACTIFS if t["hypotheses"]["prevision"][x]["gain"] > pr["gain_max"]]
    if au_dessus:
        st.info("Le gain observé dépasse la prévision écrite avant l'ouverture pour " + " et ".join(au_dessus)
                + " : la prévision était trop prudente.")
    K.pied()
