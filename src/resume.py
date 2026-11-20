"""Résumé « Ce qu'on a trouvé » (français et anglais) et liste des limites, générés depuis rapports/test_final.json (aucun chiffre tapé à la main).

Une seule source pour l'application (page d'accueil), le README (blocs générés) et la synthèse PDF : les deux langues
sont écrites par la MÊME fonction, à partir des MÊMES valeurs.
"""

from __future__ import annotations

ACTIFS = ["BTCUSDT", "ETHUSDT"]
NOMS = {"BTCUSDT": "BTC", "ETHUSDT": "ETH"}


def nombre(x: float, decimales: int = 3) -> str:
    """Nombre au format français : virgule décimale, espace fine insécable pour les milliers, vrai signe moins."""
    if x is None:
        return "—"
    texte = f"{x:,.{decimales}f}".replace(",", " ").replace(".", ",").replace(" ", " ")
    if texte.startswith("-") and not any(c in "123456789" for c in texte):
        texte = texte[1:]                                    # « −0,0 » : une valeur arrondie à zéro n'a pas de signe
    return texte.replace("-", "−")


def pourcent(x: float, decimales: int = 1) -> str:
    return nombre(100 * x, decimales) + " %"          # espace insécable : « 32,2 % » n'est jamais coupé


def p_valeur(p: float) -> str:
    return nombre(p, 4) if p >= 0.0001 else "< 0,0001"


def valeurs_trouvailles(test_final: dict) -> dict:
    """Valeurs du résumé, lues dans le contenu de rapports/test_final.json."""
    v = {"periode": test_final["periode"], "actifs": {}}
    for a in ACTIFS:
        r = test_final["actifs"][a]
        retenu = r["modele_retenu"]
        q = {m: r["modeles"][m]["qlike"] for m in ("HAR-RV", "HAR-J", retenu)}
        v["actifs"][a] = {"retenu": retenu, "gain_har_rv": r["gain_sur_har_rv"][retenu], "gain_har_j": r["gain_sur_har_j"][retenu],
                          "part_jour_semaine": (q["HAR-RV"] - q["HAR-J"]) / (q["HAR-RV"] - q[retenu]),
                          "h1": test_final["hypotheses"]["H1"][a]["confirmee"],
                          "sharpe": r["strategie"]["difference_sharpe_retenu_moins_har"]}
    return v


def phrases_trouvailles(v: dict, langue: str = "fr") -> list[str]:
    """Les trois phrases du résumé, en français ou en anglais, générées depuis les MÊMES valeurs."""
    fr = langue == "fr"
    pc = (lambda x, d=1: pourcent(x, d)) if fr else (lambda x, d=1: f"{100 * x:.{d}f}%")
    nb = (lambda x: nombre(x, 2)) if fr else (lambda x: f"{x:.2f}")
    A = v["actifs"]
    noms = {a: f"{NOMS[a]}, {A[a]['retenu']}" for a in ACTIFS}
    tous_h1 = all(A[a]["h1"] for a in ACTIFS)
    if fr:
        p1 = (f"Sur le test final ({v['periode'][0]} au {v['periode'][1]}), le modèle retenu fait mieux que HAR-RV de "
              + " et de ".join(f"{pc(A[a]['gain_har_rv'])} ({noms[a]})" for a in ACTIFS) + " en QLIKE"
              + (", de façon significative (H1 confirmée pour les deux actifs)." if tous_h1 else "."))
        p2 = ("Mais une grande part vient du jour de la semaine : face à HAR-J (HAR-RV + jour de la semaine), le gain n'est plus que de "
              + " et de ".join(f"{pc(A[a]['gain_har_j'])} ({NOMS[a]})" for a in ACTIFS) + " ; ce seul ajout comble "
              + " et ".join(f"{pc(A[a]['part_jour_semaine'], 0)} ({NOMS[a]})" for a in ACTIFS)
              + " de l'écart entre HAR-RV et le modèle retenu.")
    else:
        p1 = (f"On the final test ({v['periode'][0]} to {v['periode'][1]}), the selected model beats HAR-RV by "
              + " and ".join(f"{pc(A[a]['gain_har_rv'])} ({noms[a]})" for a in ACTIFS) + " in QLIKE"
              + (", significantly (H1 confirmed for both assets)." if tous_h1 else "."))
        p2 = ("But a large part comes from the day of the week: against HAR-J (HAR-RV + day of the week), the gain shrinks to "
              + " and ".join(f"{pc(A[a]['gain_har_j'])} ({NOMS[a]})" for a in ACTIFS) + "; this single addition closes "
              + " and ".join(f"{pc(A[a]['part_jour_semaine'], 0)} ({NOMS[a]})" for a in ACTIFS)
              + " of the gap between HAR-RV and the selected model.")
    nette = [a for a in ACTIFS if A[a]["sharpe"]["bas"] > 0]
    if fr:
        detail = " ; ".join(f"{NOMS[a]} : {nb(A[a]['sharpe']['valeur'])} [{nb(A[a]['sharpe']['bas'])} ; {nb(A[a]['sharpe']['haut'])}]"
                            for a in ACTIFS)
        p3 = (("La stratégie de pilotage par la volatilité n'en profite pas" if not nette else
               "La stratégie de pilotage par la volatilité en profite pour " + " et ".join(NOMS[a] for a in nette))
              + f" : différence de Sharpe avec HAR-RV et intervalle à 95 % ({detail}).")
    else:
        detail = "; ".join(f"{NOMS[a]}: {nb(A[a]['sharpe']['valeur'])} [{nb(A[a]['sharpe']['bas'])}, {nb(A[a]['sharpe']['haut'])}]"
                           for a in ACTIFS)
        p3 = (("The volatility-targeting strategy does not benefit" if not nette else
               "The volatility-targeting strategy benefits for " + " and ".join(NOMS[a] for a in nette))
              + f": Sharpe ratio difference with HAR-RV and 95% interval ({detail}).")
    return [p1, p2, p3]


# --- Limites : mêmes phrases dans l'application (page Limites) et dans la synthèse PDF ---------------------------

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
    return [f"{k} = {nombre(combinaison[k], 1) if isinstance(combinaison[k], float) else combinaison[k]}"
            for k, v in espace.items() if len(v) >= 3 and k in combinaison and combinaison[k] == max(v)]


def points_limites(t: dict, a: dict, dev: dict, ex: dict, regles: dict) -> list[str]:
    """Liste des limites (Markdown, gras avec **), chaque chiffre lu dans les JSON ; partagée par l'application et la synthèse."""
    h = t["hypotheses"]
    points = [f"**Une seule période de test** (du {t['periode'][0]} au {t['periode'][1]}), sans aucune crise définie : le test ne dit rien "
              "d'une nouvelle crise."]
    reseaux = ("LSTM", "GRU", "CNN-LSTM", "Transformer", "TFT")
    covid = {x: [m for m in reseaux if dev["actifs"][x]["modeles"][m]["crises"]["covid"]["qlike"]
                 > dev["actifs"][x]["modeles"]["HAR-RV"]["crises"]["covid"]["qlike"]] for x in ACTIFS}
    if any(covid.values()):
        points.append("**Covid** : pendant cette crise, " + " ; ".join(f"{len(p)} réseaux sur {len(reseaux)} ({NOMS[x]})"
                                                                         for x, p in covid.items() if p)
                      + " ont un QLIKE plus élevé que HAR-RV (descriptif) : les réseaux ne sont pas toujours meilleurs quand le marché "
                        "change brutalement.")
    for x in ACTIFS:
        p = h["H7"][x]["p_valeur_holm_2_actifs"]
        if h["H7"][x]["confirmee"] and p > a["H7"]["seuil"] / 2:
            points.append(f"**H7 de justesse ({NOMS[x]})** : le modèle retenu bat HAR-J avec une p-valeur ajustée de {p_valeur(p)}, pour un "
                          f"seuil de {nombre(a['H7']['seuil'], 2)}.")
    trop = [NOMS[x] for x in ACTIFS if h["prevision"][x]["gain"] > a["prevision"]["gain_max"]]
    if trop:
        points.append(f"**Prévisions chiffrées trop prudentes** ({' et '.join(trop)}) : les gains observés sur le test dépassent les intervalles "
                      "écrits avant l'ouverture ; notre jugement a priori était mal calibré.")
    sans_gain = {x: t["actifs"][x]["strategie"]["difference_sharpe_retenu_moins_har"] for x in ACTIFS
                 if t["actifs"][x]["strategie"]["difference_sharpe_retenu_moins_har"]["bas"] <= 0}   # pas d'amélioration nette du Sharpe
    if sans_gain:
        points.append("**Stratégie peu améliorée** : sur le test, la différence de Sharpe entre le modèle retenu et HAR-RV vaut "
                      + " ; ".join(f"{nombre(ds['valeur'], 2)} [{nombre(ds['bas'], 2)} ; {nombre(ds['haut'], 2)}] ({NOMS[x]})"
                                   for x, ds in sans_gain.items())
                      + " : une meilleure prévision ne donne pas une meilleure stratégie.")
    ecarts = []
    for x in ACTIFS:
        for m, c in dev["actifs"][x]["reglage"].items():
            s = sorted(c["scores"])
            ecarts.append((s[1] - s[0], NOMS[x], m, s[0], s[1]))
    e = min(ecarts)
    points.append(f"**Une seule graine par combinaison au réglage** : le choix est en partie dû au hasard ; plus petit écart entre la 1re et la "
                  f"2e combinaison : {e[2]} sur {e[1]}, {nombre(e[3], 4)} contre {nombre(e[4], 4)} en MSE de validation.")
    bords, total, frequence = 0, 0, {}
    for x in ACTIFS:
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
    x = ACTIFS[0]
    fx = ex["actifs"][x]["fidelite"]["XGBoost"]
    points.append(f"**SHAP ne suffit pas toujours** : XGBoost n'est fidèle que sur {fx['plis_fideles']} plis sur {fx['plis']} ({NOMS[x]}) ; "
                  f"l'attention est presque uniforme (au plus {pourcent(max(ex['actifs'][x]['attention_transformer']['tous']))} par retard).")
    points.append("**Part du jour de la semaine** : une partie de l'avantage des réseaux vient du jour de la semaine (HAR-J), une information "
                  "simple qu'un modèle linéaire peut aussi utiliser.")
    return points
