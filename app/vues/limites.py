"""Limites : liste honnête, chaque chiffre lu dans les JSON."""

import streamlit as st

import outils_app as K


def _bord(regles: dict, modele: str, combinaison: dict) -> list[str]:
    """Hyperparamètres retenus égaux à la plus grande valeur d'une liste d'au moins trois choix."""
    e = regles["entrainement"]["espaces"]
    cle = {"LSTM": "lstm", "GRU": "gru", "CNN-LSTM": "cnn_lstm", "Transformer": "transformer", "TFT": "tft"}[modele]
    propres = {k: v for k, v in e[cle].items() if isinstance(v, list)}
    lstm = {k: v for k, v in e["lstm"].items() if isinstance(v, list)}
    if e[cle].get("meme_espace_que") == "lstm":                      # GRU et CNN-LSTM : tout l'espace du LSTM
        espace = {**lstm, **propres}
    elif e[cle].get("dropout_lot_taux_weight_decay") == "comme_lstm":  # Transformer et TFT : seulement ces réglages du LSTM
        espace = {**{k: v for k, v in lstm.items() if k in ("dropout", "lot")}, **propres}
    else:
        espace = propres
    return [f"{k} = {K.nombre(combinaison[k], 1) if isinstance(combinaison[k], float) else combinaison[k]}"
            for k, v in espace.items() if len(v) >= 3 and k in combinaison and combinaison[k] == max(v)]


def afficher() -> None:
    st.title("Limites")
    t, a, dev = K.json_rapport("test_final.json"), K.attentes(), K.json_rapport("comparaison_modeles.json")
    ex, regles = K.json_rapport("explicabilite.json"), K.regles()
    h = t["hypotheses"]
    points = [f"**Une seule période de test** (du {t['periode'][0]} au {t['periode'][1]}), sans aucune crise définie : le test ne dit rien "
              "d'une nouvelle crise."]
    reseaux = ("LSTM", "GRU", "CNN-LSTM", "Transformer", "TFT")
    covid = {x: [m for m in reseaux if dev["actifs"][x]["modeles"][m]["crises"]["covid"]["qlike"]
                 > dev["actifs"][x]["modeles"]["HAR-RV"]["crises"]["covid"]["qlike"]] for x in K.ACTIFS}
    if any(covid.values()):
        points.append("**Covid** : pendant cette crise, " + " ; ".join(f"{len(p)} réseaux sur {len(reseaux)} ({K.NOMS[x]})"
                                                                         for x, p in covid.items() if p)
                      + " ont un QLIKE plus élevé que HAR-RV (descriptif) : les réseaux ne sont pas toujours meilleurs quand le marché "
                        "change brutalement.")
    for x in K.ACTIFS:
        p = h["H7"][x]["p_valeur_holm_2_actifs"]
        if h["H7"][x]["confirmee"] and p > a["H7"]["seuil"] / 2:
            points.append(f"**H7 de justesse ({K.NOMS[x]})** : le modèle retenu bat HAR-J avec une p-valeur ajustée de {K.p_valeur(p)}, pour un "
                          f"seuil de {K.nombre(a['H7']['seuil'], 2)}.")
    trop = [K.NOMS[x] for x in K.ACTIFS if h["prevision"][x]["gain"] > a["prevision"]["gain_max"]]
    if trop:
        points.append(f"**Prévisions chiffrées trop prudentes** ({' et '.join(trop)}) : les gains observés sur le test dépassent les intervalles "
                      "écrits avant l'ouverture ; notre jugement a priori était mal calibré.")
    sans_gain = {x: t["actifs"][x]["strategie"]["difference_sharpe_retenu_moins_har"] for x in K.ACTIFS
                 if t["actifs"][x]["strategie"]["difference_sharpe_retenu_moins_har"]["bas"] <= 0}   # pas d'amélioration nette du Sharpe
    if sans_gain:
        points.append("**Stratégie peu améliorée** : sur le test, la différence de Sharpe entre le modèle retenu et HAR-RV vaut "
                      + " ; ".join(f"{K.nombre(ds['valeur'], 2)} [{K.nombre(ds['bas'], 2)} ; {K.nombre(ds['haut'], 2)}] ({K.NOMS[x]})"
                                   for x, ds in sans_gain.items())
                      + " : une meilleure prévision ne donne pas une meilleure stratégie.")
    ecarts = []
    for x in K.ACTIFS:
        for m, c in dev["actifs"][x]["reglage"].items():
            s = sorted(c["scores"])
            ecarts.append((s[1] - s[0], K.NOMS[x], m, s[0], s[1]))
    e = min(ecarts)
    points.append(f"**Une seule graine par combinaison au réglage** : le choix est en partie dû au hasard ; plus petit écart entre la 1re et la "
                  f"2e combinaison : {e[2]} sur {e[1]}, {K.nombre(e[3], 4)} contre {K.nombre(e[4], 4)} en MSE de validation.")
    bords, total, frequence = 0, 0, {}
    for x in K.ACTIFS:
        for m, c in dev["actifs"][x]["reglage"].items():
            total += 1
            b = _bord(regles, m, c["combinaison"])
            bords += bool(b)
            for reglage in b:
                frequence[reglage] = frequence.get(reglage, 0) + 1
    if bords:
        courant = max(frequence, key=frequence.get)
        points.append(f"**Combinaisons au bord des espaces de recherche** : {bords} combinaisons retenues sur {total} ont au moins un réglage "
                      f"à la plus grande valeur permise (le plus fréquent : {courant}, {frequence[courant]} fois). Des espaces plus larges "
                      "auraient pu aider ; ils n'ont pas été modifiés.")
    points.append("**TFT sans intervalles de quantiles** : il est entraîné en erreur quadratique comme les autres modèles, pour une comparaison "
                  "équitable.")
    x = K.ACTIFS[0]
    fx = ex["actifs"][x]["fidelite"]["XGBoost"]
    points.append(f"**SHAP ne suffit pas toujours** : XGBoost n'est fidèle que sur {fx['plis_fideles']} plis sur {fx['plis']} ({K.NOMS[x]}) ; "
                  f"l'attention est presque uniforme (au plus {K.pourcent(max(ex['actifs'][x]['attention_transformer']['tous']))} par retard).")
    points.append("**Part du jour de la semaine** : une partie de l'avantage des réseaux vient du jour de la semaine (HAR-J), une information "
                  "simple qu'un modèle linéaire peut aussi utiliser.")
    st.markdown("\n".join(f"- {p}" for p in points))
    K.pied()
