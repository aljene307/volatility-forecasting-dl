"""Rapport généré des résultats du test final, à partir de rapports/test_final.json SEUL (agrégats publiés).

Aucun calcul de modèle, aucune donnée lue : le fichier de résultats est lu tel qu'il a été écrit une seule fois par
src/ouvrir_test.py --ouvrir. Sorties : docs/RESULTATS_TEST.md (généré) et le bloc « Résultats du test final » du README.
Chaque phrase de la lecture est conditionnée par les valeurs du JSON et suit les verdicts.
"""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import commun as C  # noqa: E402
import regles as R  # noqa: E402

CHEMIN_TEST = C.DOSSIER_RAPPORTS / "test_final.json"
CHEMIN_ATTENTES = C.RACINE / "config" / "attentes_test.toml"
CHEMIN_COMPARAISON = C.DOSSIER_RAPPORTS / "comparaison_modeles.json"
CHEMIN_MD = C.RACINE / "docs" / "RESULTATS_TEST.md"
DEBUT_BLOC = "<!-- début du bloc généré par src/resultats_test.py : test final -->"
FIN_BLOC = "<!-- fin du bloc généré par src/resultats_test.py : test final -->"
ACHAT = "Achat simple"
ORDRE = ["Persistance", "HAR-RV", "HAR-J", "GARCH(1,1)", "XGBoost", "LSTM", "GRU", "CNN-LSTM", "Transformer", "TFT"]
ENONCES = {"H1": "QLIKE(modèle retenu) < QLIKE(HAR-RV) (principale)", "H2": "QLIKE(HAR-RV) < QLIKE(persistance)",
           "H3": "QLIKE(GARCH(1,1)) > QLIKE(HAR-RV)", "H4": "VaR de HAR-RV non rejetée par Kupiec",
           "H5": "stratégie du modèle retenu : volatilité et drawdown plus faibles que l'achat simple",
           "H6": "gain du modèle retenu sur HAR-J < gain sur HAR-RV (descriptive)",
           "H7": "QLIKE(modèle retenu) < QLIKE(HAR-J) (secondaire, ajoutée le 2026-11-19)"}


def _n(x: float, d: int = 3) -> str:
    return C.nombre_fr(x, d).replace("-", "−")


def _pc(x: float, d: int = 1) -> str:
    return _n(100 * x, d) + " %"


def _p(p: float) -> str:
    return _n(p, 4) if p >= 0.0001 else "< 0,0001"


def _oui(b: bool) -> str:
    return "confirmée" if b else "non confirmée"


def _liste(noms: list[str]) -> str:
    return noms[0] if len(noms) == 1 else ", ".join(noms[:-1]) + " et " + noms[-1]


def _nom(actif: str) -> str:
    return actif.replace("USDT", "")


def _position(gain: float, bas: float, haut: float) -> str:
    if gain > haut:
        return "au-dessus de l'intervalle prévu"
    if gain < bas:
        return "au-dessous de l'intervalle prévu"
    return "dans l'intervalle prévu"


def rapport_markdown(t: dict, attentes: dict, dev: dict) -> str:
    h, pr, pj = t["hypotheses"], attentes["prevision"], attentes["prevision_har_j"]
    lignes = ["# Résultats du test final", "",
              "Fichier généré par `src/resultats_test.py` à partir de `rapports/test_final.json` : ne pas le modifier à la main.", "",
              f"- Test ouvert une seule fois le {t['ouvert_le'][:10]} par `src/ouvrir_test.py --ouvrir`, avec le code du commit "
              f"`{t['commit_du_code'][:7]}` ; {t['empreintes_verifiees']} empreintes de modèles et de normalisations vérifiées avant toute prévision.",
              f"- Période du test (dates de cible) : du {t['periode'][0]} au {t['periode'][1]}, {C.nombre_fr(next(iter(t['actifs'].values()))['jours'])} "
              "jours par actif. Aucune crise n'est définie sur cette période : rien n'est rapporté par crise.",
              "- Modèles du découpage du test final, sans réentraînement ; attentes écrites et poussées avant l'ouverture : "
              "[`docs/ATTENTES_TEST.md`](ATTENTES_TEST.md). Tous les résultats sont publiés tels quels.", "",
              "## Verdicts des hypothèses", "", "| Hypothèse | Énoncé | " + " | ".join(_nom(a) for a in t["actifs"]) + " |",
              "|---|---|" + "---|" * len(t["actifs"])]
    for k in ("H1", "H2", "H3", "H4", "H5", "H6", "H7"):
        lignes.append(f"| {k} | {ENONCES[k]} | " + " | ".join(_oui(h[k][a]["confirmee"]) for a in t["actifs"]) + " |")
    lignes += ["", "| Test (Holm sur les 2 actifs) | Actif | Modèle retenu | Différence moyenne d | Statistique | p-valeur brute | p-valeur ajustée |",
               "|---|---|---|---:|---:|---:|---:|"]
    for k, ref in (("H1", "HAR-RV"), ("H7", "HAR-J")):
        for a, x in h[k].items():
            lignes.append(f"| {k} (contre {ref}) | {_nom(a)} | {x['modele_retenu']} | {_n(x['moyenne_difference'], 4)} | {_n(x['statistique'], 2)} | "
                          f"{_p(x['p_valeur'])} | {_p(x['p_valeur_holm_2_actifs'])} |")
    lignes += ["", "## Comparaison avec les prévisions chiffrées écrites avant l'ouverture", "",
               "| Prévision | Intervalle prévu | " + " | ".join(_nom(a) for a in t["actifs"]) + " |", "|---|---|" + "---|" * len(t["actifs"]),
               f"| Gain du modèle retenu sur HAR-RV | {_pc(pr['gain_min'], 0)} à {_pc(pr['gain_max'], 0)} | "
               + " | ".join(f"{_pc(h['prevision'][a]['gain'])} ({_position(h['prevision'][a]['gain'], pr['gain_min'], pr['gain_max'])})" for a in t["actifs"]) + " |",
               f"| Gain du modèle retenu sur HAR-J | {_pc(pj['gain_min'], 0)} à {_pc(pj['gain_max'], 0)} | "
               + " | ".join(f"{_pc(h['prevision_har_j'][a]['gain'])} ({_position(h['prevision_har_j'][a]['gain'], pj['gain_min'], pj['gain_max'])})" for a in t["actifs"]) + " |",
               "", f"Textes écrits avant l'ouverture : « {pr['texte']} » ; « {pj['texte']} ».", ""]
    for actif, r in t["actifs"].items():
        retenu = r["modele_retenu"]
        lignes += [f"## {actif}", "", f"Modèle retenu : **{retenu}**.", "", "### Tous les modèles", "",
                   "| Modèle | QLIKE [IC 95 %] | Gain sur HAR-RV | Gain sur HAR-J | RMSE [IC 95 %] | MAE [IC 95 %] |", "|---|---|---:|---:|---|---|"]
        for m in ORDRE:
            x = r["modeles"][m]
            role = {"Persistance": " (descriptive)", "HAR-J": " (descriptif)", retenu: " (retenu)"}.get(m, "")
            lignes.append(f"| {m}{role} | {_n(x['qlike'])} [{_n(x['qlike_intervalle']['bas'])} ; {_n(x['qlike_intervalle']['haut'])}] | "
                          f"{_pc(r['gain_sur_har_rv'][m])} | {_pc(r['gain_sur_har_j'][m])} | {_n(x['rmse'], 4)} [{_n(x['rmse_intervalle']['bas'], 4)} ; "
                          f"{_n(x['rmse_intervalle']['haut'], 4)}] | {_n(x['mae'], 4)} [{_n(x['mae_intervalle']['bas'], 4)} ; {_n(x['mae_intervalle']['haut'], 4)}] |")
        lignes += ["", "Modèles réglés : prévision = moyenne des log des 3 graines. QLIKE moyen de chaque graine seule (avec son propre s²) :", "",
                   "| Modèle | QLIKE moyen des graines (écart-type) |", "|---|---|"]
        for m in ORDRE:
            if "par_graine" in r["modeles"][m]:
                g = r["modeles"][m]["par_graine"]["qlike"]
                lignes.append(f"| {m} | {_n(g['moyenne'])} ({_n(g['ecart_type'], 4)}) |")
        lignes += ["", "### Diebold-Mariano contre HAR-RV (QLIKE)", "",
                   "Le test principal est H1 (modèle retenu, Holm sur les 2 actifs, ci-dessus). Les 7 comparaisons ci-dessous sont descriptives "
                   "(Holm sur 7).", "", "| Modèle | Différence moyenne | Statistique (HLN) | p-valeur brute | p-valeur ajustée (Holm sur 7) |",
                   "|---|---:|---:|---:|---:|"]
        for m, x in r["diebold_mariano"].items():
            lignes.append(f"| {m} | {_n(x['moyenne_difference'], 4)} | {_n(x['statistique'], 2)} | {_p(x['p_valeur'])} | {_p(x['p_valeur_holm_7_descriptif'])} |")
        lignes += ["", "| Comparaison descriptive | Différence moyenne | p-valeur brute |", "|---|---:|---:|"]
        for nom, x in r["diebold_mariano_descriptif"].items():
            lignes.append(f"| {nom} | {_n(x['moyenne_difference'], 4)} | {_p(x['p_valeur'])} |")
        s = r["strategie"]
        lignes += ["", "### Stratégie de volatility targeting (frais de 0,10 %)", "",
                   "| Stratégie | Rendement annualisé | Volatilité (÷ cible) | Sharpe [IC 95 %] | Sortino | Drawdown max | Rotation annuelle | Frais par an |",
                   "|---|---:|---:|---|---:|---:|---:|---:|"]
        for m in [ACHAT, "HAR-RV", retenu] + [x for x in ORDRE if x in s and x not in ("HAR-RV", retenu)]:
            x = s[m]
            lignes.append(f"| {m} | {_pc(x['rendement_annualise'])} | {_pc(x['volatilite_annualisee'])} ({_n(x['volatilite_sur_cible'], 2)}) | "
                          f"{_n(x['sharpe'], 2)} [{_n(x['sharpe_intervalle']['bas'], 2)} ; {_n(x['sharpe_intervalle']['haut'], 2)}] | {_n(x['sortino'], 2)} | "
                          f"{_pc(x['drawdown_max'])} | {_n(x['rotation_annuelle'], 1)} | {_pc(x['frais_annuels_en_rendement'], 2)} |")
        ds = s["difference_sharpe_retenu_moins_har"]
        lignes += ["", f"Différence de Sharpe {retenu} − HAR-RV (descriptif) : {_n(ds['valeur'], 3)} [{_n(ds['bas'], 3)} ; {_n(ds['haut'], 3)}].", "",
                   "### VaR à 1 jour à 95 % et test de Kupiec", "",
                   f"Jours exclus (jour non valide ou lendemain) : {r['var']['jours_exclus_non_valides']}.", "",
                   "| Modèle | Jours | Dépassements | Taux (attendu 5 %) | p-valeur | Rejet à 5 % |", "|---|---:|---:|---:|---:|---|"]
        for m in [x for x in ORDRE if x in r["var"]["modeles"]]:
            k = r["var"]["modeles"][m]
            lignes.append(f"| {m} | {C.nombre_fr(k['jours'])} | {k['depassements']} | {_pc(k['taux'], 2)} | {_p(k['p_valeur'])} | "
                          f"{'oui' if k['p_valeur'] < 0.05 else 'non'} |")
        lignes += ["", f"Figures : `figures/figure_10_test_previsions_{actif}.png`, `figures/figure_11_test_strategie_{actif}.png`.", ""]
    lignes += lecture(t, attentes, dev)
    return "\n".join(lignes) + "\n"


def lecture(t: dict, attentes: dict, dev: dict) -> list[str]:
    """Phrases conditionnées par les valeurs ; aucune ne contredit un verdict."""
    h, pr, pj = t["hypotheses"], attentes["prevision"], attentes["prevision_har_j"]
    seuil = attentes["H1"]["seuil"]
    lignes = ["## Lecture des résultats", "", "Chaque phrase ci-dessous est générée à partir des valeurs de `rapports/test_final.json`.", ""]
    for actif, r in t["actifs"].items():
        nom, retenu = _nom(actif), r["modele_retenu"]
        x1 = h["H1"][actif]
        if x1["confirmee"]:
            lignes.append(f"- {nom} : H1 est confirmée : {retenu} a un QLIKE plus faible que HAR-RV sur le test, et l'écart est significatif "
                          f"après ajustement de Holm (p-valeur ajustée {_p(x1['p_valeur_holm_2_actifs'])}).")
        else:
            lignes.append(f"- {nom} : H1 n'est pas confirmée : on ne peut pas dire que {retenu} fait mieux que HAR-RV sur le test.")
        g, g_dev = h["prevision"][actif]["gain"], dev["actifs"][actif]["gain_relatif_qlike"][retenu]["jours_reunis"]
        lignes.append(f"- {nom} : le gain de {retenu} sur HAR-RV est de {_pc(g)} sur le test, {_position(g, pr['gain_min'], pr['gain_max'])} "
                      f"({_pc(pr['gain_min'], 0)} à {_pc(pr['gain_max'], 0)}) ; il était de {_pc(g_dev)} sur le développement (jours réunis)"
                      + (" : la prévision écrite avant l'ouverture a sous-estimé le gain." if g > pr["gain_max"] else
                         " : la prévision écrite avant l'ouverture a surestimé le gain." if g < pr["gain_min"] else "."))
        x7, g7 = h["H7"][actif], h["prevision_har_j"][actif]["gain"]
        if x7["confirmee"]:
            juste = x7["p_valeur_holm_2_actifs"] > seuil / 2
            lignes.append(f"- {nom} : H7 est confirmée{' de justesse' if juste else ''} : {retenu} fait mieux que HAR-J (p-valeur ajustée "
                          f"{_p(x7['p_valeur_holm_2_actifs'])}, seuil {_n(seuil, 2)}) ; son gain sur HAR-J est de {_pc(g7)}, "
                          f"{_position(g7, pj['gain_min'], pj['gain_max'])} ({_pc(pj['gain_min'], 0)} à {_pc(pj['gain_max'], 0)}), "
                          "alors que la prévision écrite avant l'ouverture le disait « probablement non significatif ».")
        else:
            lignes.append(f"- {nom} : H7 n'est pas confirmée : on ne peut pas dire que {retenu} fait mieux que HAR-J sur le test "
                          f"(gain de {_pc(g7)}).")
        meilleur = min(ORDRE, key=lambda m: r["modeles"][m]["qlike"])
        if meilleur != retenu:
            lignes.append(f"- {nom} : sur le test, le plus petit QLIKE est celui de {meilleur} ({_n(r['modeles'][meilleur]['qlike'])}), pas celui du "
                          f"modèle retenu ({_n(r['modeles'][retenu]['qlike'])}) ; la sélection a été faite sur le développement et ne change pas.")
        else:
            lignes.append(f"- {nom} : sur le test, le modèle retenu ({retenu}) a aussi le plus petit QLIKE de tous les modèles.")
        hj = r["diebold_mariano_descriptif"]["HAR-J contre HAR-RV"]
        lignes.append(f"- {nom} : HAR-J fait {'mieux' if r['gain_sur_har_rv']['HAR-J'] > 0 else 'moins bien'} que HAR-RV sur le test "
                      f"({_pc(r['gain_sur_har_rv']['HAR-J'])} ; p-valeur descriptive {_p(hj['p_valeur'])}) ; H6 est {_oui(h['H6'][actif]['confirmee'])} : "
                      f"le gain de {retenu} est de {_pc(h['H6'][actif]['gain_sur_har_j'])} sur HAR-J contre {_pc(h['H6'][actif]['gain_sur_har_rv'])} sur HAR-RV.")
        lignes.append(f"- {nom} : H2 est {_oui(h['H2'][actif]['confirmee'])} (HAR-RV contre la persistance) et H3 est {_oui(h['H3'][actif]['confirmee'])} "
                      "(GARCH(1,1) contre HAR-RV).")
        s, x5 = r["strategie"], h["H5"][actif]
        ecart_dd = x5["drawdown_retenu"] - x5["drawdown_achat"]
        lignes.append(f"- {nom} : H5 est {_oui(x5['confirmee'])} : la stratégie de {retenu} a une volatilité de {_pc(x5['volatilite_retenu'])} contre "
                      f"{_pc(x5['volatilite_achat'])} pour l'achat simple, et un drawdown maximal de {_pc(x5['drawdown_retenu'])} contre "
                      f"{_pc(x5['drawdown_achat'])}" + (" (réduction de moins de 3 points)." if 0 < ecart_dd < 0.03 else "."))
        negatifs = [m for m in (ACHAT, "HAR-RV", retenu) if s[m]["rendement_annualise"] < 0]
        if negatifs:
            noms = [{ACHAT: "l'achat simple"}.get(m, f"la stratégie de {m}") for m in negatifs]
            lignes.append(f"- {nom} : le rendement annualisé est négatif sur le test pour {_liste(noms)} ; la stratégie réduit le risque "
                          "mais ne transforme pas une baisse du marché en gain.")
        ds = s["difference_sharpe_retenu_moins_har"]
        if ds["haut"] < 0:
            lignes.append(f"- {nom} : le Sharpe de la stratégie de {retenu} est plus bas que celui de la stratégie de HAR-RV, et l'intervalle "
                          "bootstrap de la différence ne contient pas 0 (descriptif)"
                          + (" : un QLIKE plus faible que HAR-RV ne se traduit pas ici par une meilleure stratégie." if x1["confirmee"] else "."))
        elif ds["bas"] > 0:
            lignes.append(f"- {nom} : le Sharpe de la stratégie de {retenu} est plus élevé que celui de HAR-RV, et l'intervalle bootstrap de la "
                          "différence ne contient pas 0 (descriptif).")
        else:
            lignes.append(f"- {nom} : l'intervalle bootstrap de la différence de Sharpe entre {retenu} et HAR-RV contient 0 : on ne peut pas "
                          "dire qu'une stratégie fait mieux que l'autre (descriptif).")
        x4 = h["H4"][actif]
        vm = r["var"]["modeles"]
        peu = [m for m, k in vm.items() if k["p_valeur"] < 0.05 and k["taux"] < k["attendu"]]
        trop = [m for m, k in vm.items() if k["p_valeur"] < 0.05 and k["taux"] > k["attendu"]]
        detail = ("Kupiec ne rejette la VaR d'aucun modèle." if not peu + trop else
                  "Kupiec rejette la VaR de " + " ; ".join(
                      ([f"{_liste(peu)} (trop peu de dépassements : VaR trop prudente)"] if peu else [])
                      + ([f"{_liste(trop)} (trop de dépassements : VaR trop optimiste)"] if trop else [])) + ".")
        lignes.append(f"- {nom} : H4 est {_oui(x4['confirmee'])} (taux de dépassement de HAR-RV {_pc(x4['taux'], 2)}, p-valeur "
                      f"{_p(x4['p_valeur_kupiec'])}) ; " + detail)
    return lignes + [""]


def bloc_readme(t: dict, attentes: dict) -> str:
    h = t["hypotheses"]
    actifs = list(t["actifs"])
    lignes = [DEBUT_BLOC, "## Résultats du test final", "",
              f"Test ouvert une seule fois le {t['ouvert_le'][:10]} (code du commit `{t['commit_du_code'][:7]}`), sur les dates de cible du "
              f"{t['periode'][0]} au {t['periode'][1]}, avec des [attentes écrites avant l'ouverture](docs/ATTENTES_TEST.md). "
              "Détails : [résultats du test final](docs/RESULTATS_TEST.md). Tableau généré depuis `rapports/test_final.json`.", "",
              "| Hypothèse | " + " | ".join(f"{_nom(a)} ({t['actifs'][a]['modele_retenu']})" for a in actifs) + " |", "|---|" + "---|" * len(actifs)]
    for k in ("H1", "H2", "H3", "H4", "H5", "H6", "H7"):
        lignes.append(f"| {k} : {ENONCES[k]} | " + " | ".join(_oui(h[k][a]["confirmee"]) for a in actifs) + " |")
    pr, pj = attentes["prevision"], attentes["prevision_har_j"]
    lignes.append(f"| Gain du modèle retenu sur HAR-RV (prévu : {_pc(pr['gain_min'], 0)} à {_pc(pr['gain_max'], 0)}) | "
                  + " | ".join(_pc(h["prevision"][a]["gain"]) for a in actifs) + " |")
    lignes.append(f"| Gain du modèle retenu sur HAR-J (prévu : {_pc(pj['gain_min'], 0)} à {_pc(pj['gain_max'], 0)}) | "
                  + " | ".join(_pc(h["prevision_har_j"][a]["gain"]) for a in actifs) + " |")
    lignes.append(FIN_BLOC)
    return "\n".join(lignes)


def mettre_a_jour_readme(chemin: Path, bloc: str) -> None:
    texte = chemin.read_text(encoding="utf-8")
    if texte.count(DEBUT_BLOC) != 1 or texte.count(FIN_BLOC) != 1:
        raise ValueError("README : marqueurs du bloc du test final absents ou en double.")
    avant, reste = texte.split(DEBUT_BLOC)
    _, apres = reste.split(FIN_BLOC)
    C.ecrire_texte(chemin, avant + bloc + apres)


def charger() -> tuple[dict, dict, dict]:
    return (json.loads(CHEMIN_TEST.read_text(encoding="utf-8")), tomllib.loads(CHEMIN_ATTENTES.read_text(encoding="utf-8")),
            json.loads(CHEMIN_COMPARAISON.read_text(encoding="utf-8")))


def main() -> int:
    C.proteger_sortie()
    R.charger_regles()
    t, attentes, dev = charger()
    C.ecrire_texte(CHEMIN_MD, rapport_markdown(t, attentes, dev))
    mettre_a_jour_readme(C.RACINE / "README.md", bloc_readme(t, attentes))
    print("docs/RESULTATS_TEST.md et le bloc du README générés depuis rapports/test_final.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
