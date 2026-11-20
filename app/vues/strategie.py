"""Stratégie : tableaux et figures, et constat sur le lien entre précision et stratégie."""

import pandas as pd
import streamlit as st

import outils_app as K


def _tableau(strategies: dict, noms: list[str]) -> pd.DataFrame:
    return pd.DataFrame([{"Stratégie": m, "Rendement annualisé": K.pourcent(s["rendement_annualise"]),
                          "Volatilité (÷ cible)": f"{K.pourcent(s['volatilite_annualisee'])} ({K.nombre(s['volatilite_sur_cible'], 2)})",
                          "Sharpe [IC 95 %]": f"{K.nombre(s['sharpe'], 2)} [{K.nombre(s['sharpe_intervalle']['bas'], 2)} ; {K.nombre(s['sharpe_intervalle']['haut'], 2)}]",
                          "Drawdown max": K.pourcent(s["drawdown_max"])} for m, s in ((n, strategies[n]) for n in noms)]).set_index("Stratégie")


def _verdict(ds: dict) -> str:
    if ds["haut"] < 0:
        return "moins bon que HAR-RV"
    if ds["bas"] > 0:
        return "meilleur que HAR-RV"
    return "pas de différence nette"


def afficher() -> None:
    st.title("Pilotage par la volatilité (volatility targeting)")
    s = K.regles()["strategie"]
    st.markdown("L'exposition décidée à la clôture d'un jour vaut la volatilité cible divisée par la volatilité prévue (annualisée), "
                f"bornée entre {K.nombre(s['exposition_min'], 0)} et {K.nombre(s['exposition_max'], 0)}, et s'applique au rendement du "
                f"lendemain, frais de {K.pourcent(s['frais'], 2)} compris.")
    actif = st.selectbox("Actif", K.ACTIFS, format_func=lambda a: K.NOMS[a], key="actif_strategie")
    dev = K.json_rapport("strategie.json")["actifs"][actif]
    test = K.json_rapport("test_final.json")["actifs"][actif]
    retenu = dev["modele_retenu"]
    noms = ["Achat simple", "HAR-RV", retenu]
    onglet_dev, onglet_test = st.tabs(["Développement", "Test final"])
    with onglet_dev:
        st.table(_tableau(dev["strategies"], noms))
        st.image(str(K.figure(f"figure_6_strategie_{actif}.png")), width="stretch")
    with onglet_test:
        st.table(_tableau(test["strategie"], noms))
        st.image(str(K.figure(f"figure_11_test_strategie_{actif}.png")), width="stretch")
    st.subheader("Constat : une meilleure prévision ne donne pas forcément une meilleure stratégie")
    lignes = []
    for a in K.ACTIFS:
        d, t = K.json_rapport("strategie.json")["actifs"][a], K.json_rapport("test_final.json")["actifs"][a]
        r = d["modele_retenu"]
        for nom_periode, s, ds in (("développement", d["strategies"], d["difference_sharpe_retenu_moins_har"]),
                                   ("test final", t["strategie"], t["strategie"]["difference_sharpe_retenu_moins_har"])):
            lignes.append({"Actif et période": f"{K.NOMS[a]} ({r}), {nom_periode}",
                           "Différence de Sharpe avec HAR-RV [IC 95 %]": f"{K.nombre(ds['valeur'], 2)} [{K.nombre(ds['bas'], 2)} ; {K.nombre(ds['haut'], 2)}]",
                           "Verdict": _verdict(ds),
                           "Rotation annuelle (retenu / HAR-RV)": f"{K.nombre(s[r]['rotation_annuelle'], 1)} / {K.nombre(s['HAR-RV']['rotation_annuelle'], 1)}",
                           "Frais par an (retenu / HAR-RV)": f"{K.pourcent(s[r]['frais_annuels_en_rendement'], 2)} / "
                                                             f"{K.pourcent(s['HAR-RV']['frais_annuels_en_rendement'], 2)}"})
    st.table(pd.DataFrame(lignes).set_index("Actif et période"))
    st.caption("Explication possible, non démontrée : l'exposition est plafonnée à 1 une grande partie du temps (pas d'emprunt) ; "
               "une prévision plus précise ne change alors l'exposition que les jours agités.")
    K.pied()
