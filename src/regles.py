"""Chargement et contrôle des règles du projet (config/regles.toml).

Utilise uniquement la bibliothèque standard (tomllib, Python 3.11 et plus).

Convention de date : un exemple (variables arrêtées à la clôture de J, cible RV de J+1)
appartient à la période qui contient sa CIBLE J+1. Toutes les bornes de période et de pli
sont des dates de cible.

Usage :
    .venv\\Scripts\\python src/regles.py                 # résumé lisible des règles
    .venv\\Scripts\\python src/regles.py --entrainement  # refuse si une valeur reste à fixer
"""

from __future__ import annotations

import datetime as dt
import math
import sys
import tomllib
from pathlib import Path
from statistics import NormalDist

RACINE = Path(__file__).resolve().parent.parent
CHEMIN_REGLES = RACINE / "config" / "regles.toml"
A_FIXER = "a_fixer_apres_mesure"
UN_JOUR = dt.timedelta(days=1)


class ErreurRegles(ValueError):
    """Règle absente, incohérente ou pas encore fixée."""


# --------------------------------------------------------------------------
# Chargement
# --------------------------------------------------------------------------

def charger_regles(chemin: Path | str | None = None, verifier: bool = True) -> dict:
    """Lit le fichier TOML et, par défaut, vérifie sa cohérence."""
    chemin = Path(chemin) if chemin is not None else CHEMIN_REGLES
    with open(chemin, "rb") as f:
        regles = tomllib.load(f)
    if verifier:
        verifier_coherence(regles)
    return regles


def _valeur(regles: dict, cle: str):
    """Lit une valeur par son chemin pointé, par exemple "decoupage.dev_debut"."""
    noeud = regles
    for partie in cle.split("."):
        if not isinstance(noeud, dict) or partie not in noeud:
            raise ErreurRegles(f"Règle absente : {cle}")
        noeud = noeud[partie]
    return noeud


def _date(regles: dict, cle: str) -> dt.date:
    valeur = _valeur(regles, cle)
    if not isinstance(valeur, dt.date) or isinstance(valeur, dt.datetime):
        raise ErreurRegles(f"{cle} doit être une date AAAA-MM-JJ, reçu : {valeur!r}")
    return valeur


# --------------------------------------------------------------------------
# Dates et découpage (toutes les dates sont des dates de cible)
# --------------------------------------------------------------------------

def ajouter_mois(jour: dt.date, mois: int) -> dt.date:
    """Ajoute (ou retire) un nombre de mois à une date qui est un premier du mois."""
    if jour.day != 1:
        raise ErreurRegles(f"Date attendue au 1er du mois, reçu : {jour}")
    total = jour.year * 12 + (jour.month - 1) + mois
    return dt.date(total // 12, total % 12 + 1, 1)


def plis_walk_forward(regles: dict) -> list[tuple[dt.date, dt.date]]:
    """Périodes évaluées (première et dernière date de cible), de plis_debut à plis_fin."""
    wf = "decoupage.walk_forward"
    debut = _date(regles, f"{wf}.plis_debut")
    fin = _date(regles, f"{wf}.plis_fin")
    duree = _valeur(regles, f"{wf}.duree_pli_mois")
    plis = []
    courant = debut
    while courant <= fin:
        suivant = ajouter_mois(courant, duree)
        plis.append((courant, suivant - UN_JOUR))
        courant = suivant
    return plis


def _decoupe(regles: dict, nom: str, eval_debut: dt.date, eval_fin: dt.date) -> dict:
    """Apprentissage, ajustement, validation interne et évaluation pour une période évaluée."""
    embargo = dt.timedelta(days=_valeur(regles, "decoupage.embargo_jours"))
    premiere = _date(regles, "decoupage.premiere_cible")
    mois_val = _valeur(regles, "decoupage.walk_forward.validation_interne_mois")
    app_fin = eval_debut - UN_JOUR - embargo
    val_debut = ajouter_mois(eval_debut, -mois_val)
    return {
        "nom": nom,
        "apprentissage": (premiere, app_fin),           # ajustement + validation interne
        "ajustement": (premiere, val_debut - UN_JOUR - embargo),
        "validation": (val_debut, app_fin),
        "evaluation": (eval_debut, eval_fin),
    }


def decoupages(regles: dict) -> list[dict]:
    """Les 10 plis walk-forward, puis le découpage du test final."""
    liste = [_decoupe(regles, f"pli {i}", debut, fin)
             for i, (debut, fin) in enumerate(plis_walk_forward(regles), start=1)]
    liste.append(_decoupe(regles, "test final",
                          _date(regles, "decoupage.test_debut"), _date(regles, "decoupage.test_fin")))
    return liste


def problemes_separation(liste: list[dict], embargo_jours: int) -> list[str]:
    """Vérifie qu'aucune cible d'apprentissage ne touche une cible évaluée.

    Pour chaque découpage : dernière cible d'ajustement < première cible de validation,
    et dernière cible d'apprentissage < première cible évaluée, avec au moins
    `embargo_jours` jours d'écart en plus.
    """
    ecart_min = dt.timedelta(days=1 + embargo_jours)
    problemes = []
    for d in liste:
        a_debut, a_fin = d["apprentissage"]
        j_debut, j_fin = d["ajustement"]
        v_debut, v_fin = d["validation"]
        e_debut, e_fin = d["evaluation"]
        for etiquette, (debut, fin) in (("apprentissage", d["apprentissage"]), ("ajustement", d["ajustement"]),
                                        ("validation", d["validation"]), ("évaluation", d["evaluation"])):
            if debut > fin:
                problemes.append(f"{d['nom']} : période {etiquette} vide ({debut} -> {fin}).")
        if v_debut - j_fin < ecart_min:
            problemes.append(f"{d['nom']} : chevauchement entre ajustement (fin {j_fin}) et validation interne (début {v_debut}).")
        if e_debut - a_fin < ecart_min:
            problemes.append(f"{d['nom']} : chevauchement entre apprentissage (fin {a_fin}) et évaluation (début {e_debut}).")
        if not (a_debut == j_debut and v_fin == a_fin):
            problemes.append(f"{d['nom']} : la validation interne doit être la fin de l'apprentissage.")
    return problemes


def toutes_les_dates(regles: dict, prefixe: str = "") -> dict[str, dt.date]:
    """Toutes les dates du fichier, indexées par leur chemin pointé."""
    dates = {}
    for cle, valeur in regles.items():
        chemin = f"{prefixe}{cle}"
        if isinstance(valeur, dict):
            dates.update(toutes_les_dates(valeur, chemin + "."))
        elif isinstance(valeur, dt.date):
            dates[chemin] = valeur
    return dates


# --------------------------------------------------------------------------
# Formules fixées par les règles
# --------------------------------------------------------------------------

def variance_prevue_depuis_log(y: float, s2: float) -> float:
    """Prévision de log(RV) -> variance prévue (utilisée pour QLIKE).

    Si log(RV) suit une loi normale de moyenne y et de variance s2 : E[RV²] = exp(2y + 2·s2) > 0.
    s2 est la variance des résidus en log mesurée sur la validation interne.
    """
    if s2 < 0:
        raise ErreurRegles(f"La variance des résidus doit être positive, reçu : {s2}")
    return math.exp(2 * y + 2 * s2)


def volatilite_prevue(variance: float) -> float:
    """La seule volatilité prévue du projet : sigma = racine(variance prévue).

    Sert pour RMSE, MAE, la stratégie et la VaR, pour tous les modèles
    (variance depuis le log, ou variance GARCH mise à l'échelle).
    """
    if not variance > 0:
        raise ErreurRegles(f"La variance prévue doit être strictement positive, reçu : {variance}")
    return math.sqrt(variance)


def volatilite_prevue_depuis_log(y: float, s2: float) -> float:
    """sigma = racine(exp(2y + 2·s2)) pour un modèle qui prévoit log(RV)."""
    return volatilite_prevue(variance_prevue_depuis_log(y, s2))


def exposition(regles: dict, vol_cible_annuelle: float, sigma_journaliere: float) -> float:
    """Exposition = vol_cible_annuelle / (sigma_journaliere × racine(365)), bornée entre min et max.

    sigma est journalière : on l'annualise avant de la comparer à la volatilité cible annuelle.
    """
    s = regles["strategie"]
    if not sigma_journaliere > 0:
        raise ErreurRegles(f"La volatilité prévue doit être strictement positive, reçu : {sigma_journaliere}")
    brute = vol_cible_annuelle / (sigma_journaliere * math.sqrt(s["annualisation_jours"]))
    return min(max(brute, s["exposition_min"]), s["exposition_max"])


def var_un_jour(regles: dict, sigma_journaliere: float) -> float:
    """VaR à 1 jour (perte positive) : quantile de la loi normale × sigma journalière, sans annualisation."""
    if not sigma_journaliere > 0:
        raise ErreurRegles(f"La volatilité prévue doit être strictement positive, reçu : {sigma_journaliere}")
    return NormalDist().inv_cdf(regles["strategie"]["var_niveau"]) * sigma_journaliere


def jour_valide(regles: dict, nombre_bougies: int, plus_grand_ecart_minutes: float) -> bool:
    """Un jour est valide s'il a assez de bougies (un rendement manquant compte comme une
    bougie manquante) et si aucun écart entre deux bougies consécutives ne dépasse le maximum."""
    jv = regles["donnees"]["jour_valide"]
    return nombre_bougies >= jv["bougies_min"] and plus_grand_ecart_minutes <= jv["ecart_max_minutes"]


def secours_active(regles: dict, taux_exclusion_par_actif: dict[str, float]) -> bool:
    """Taux d'exclusion mesurés une fois par actif sur le développement.

    Si un seul actif dépasse le seuil, la règle de secours s'applique aux deux actifs, partout.
    """
    actifs = set(regles["donnees"]["actifs"])
    if set(taux_exclusion_par_actif) != actifs:
        raise ErreurRegles(f"Un taux d'exclusion par actif est attendu pour {sorted(actifs)}, "
                           f"reçu {sorted(taux_exclusion_par_actif)}.")
    seuil = regles["donnees"]["exclusions"]["seuil_secours"]
    return any(taux > seuil for taux in taux_exclusion_par_actif.values())


def retards_hac(nombre_jours: int) -> int:
    """Nombre de retards HAC de Newey-West : floor(4·(T/100)^(2/9))."""
    if nombre_jours < 1:
        raise ErreurRegles(f"Nombre de jours évalués invalide : {nombre_jours}")
    return math.floor(4 * (nombre_jours / 100) ** (2 / 9))


# --------------------------------------------------------------------------
# Contrôles
# --------------------------------------------------------------------------

def verifier_coherence(regles: dict) -> None:
    """Lève ErreurRegles avec la liste de tous les problèmes trouvés."""
    problemes: list[str] = []

    def exiger(condition: bool, message: str) -> None:
        if not condition:
            problemes.append(message)

    wf = "decoupage.walk_forward"
    try:
        d_debut = _date(regles, "donnees.debut")
        d_fin = _date(regles, "donnees.fin")
        dev_debut = _date(regles, "decoupage.dev_debut")
        premiere = _date(regles, "decoupage.premiere_cible")
        dev_fin = _date(regles, "decoupage.dev_fin")
        test_debut = _date(regles, "decoupage.test_debut")
        test_fin = _date(regles, "decoupage.test_fin")
        pre_debut = _date(regles, "decoupage.prechauffage.debut")
        pre_fin = _date(regles, "decoupage.prechauffage.fin")
        pre_jours = _valeur(regles, "decoupage.prechauffage.jours")
        app_debut = _date(regles, f"{wf}.premier_apprentissage_debut")
        app_fin = _date(regles, f"{wf}.premier_apprentissage_fin")
        plis_debut = _date(regles, f"{wf}.plis_debut")
        plis_fin = _date(regles, f"{wf}.plis_fin")
        vc_debut = _date(regles, "strategie.vol_cible_debut")
        vc_fin = _date(regles, "strategie.vol_cible_fin")
        expo_min = _valeur(regles, "strategie.exposition_min")
        expo_max = _valeur(regles, "strategie.exposition_max")
        embargo = _valeur(regles, "decoupage.embargo_jours")
        convention = _valeur(regles, "decoupage.convention_date")
        crises = _valeur(regles, "crises")
        jv = _valeur(regles, "donnees.jour_valide")
        seuil_secours = _valeur(regles, "donnees.exclusions.seuil_secours")
        seuil_debut = _date(regles, "donnees.exclusions.seuil_mesure_debut")
        seuil_fin = _date(regles, "donnees.exclusions.seuil_mesure_fin")
        premier_jour = _date(regles, "donnees.rendements.premier_jour_donnees")
        premier_jour_rdt = _valeur(regles, "donnees.rendements.premier_jour_rendements")
        s2_sur = _valeur(regles, "cible.retour_log.s2_mesuree_sur")
        tf = "decoupage.modele_test_final"
        tf_dates = {k: _date(regles, f"{tf}.{k}")
                    for k in ("ajustement_debut", "ajustement_fin", "validation_debut", "validation_fin")}
    except ErreurRegles as erreur:
        raise ErreurRegles(f"Règles incomplètes : {erreur}") from None

    exiger(convention == "cible", f"Convention de date attendue « cible », reçu : {convention!r}.")
    exiger(isinstance(embargo, int) and embargo >= 0, f"L'embargo doit être un entier positif ou nul, reçu : {embargo!r}.")

    # Ordre des grandes périodes (dates de cible)
    exiger(d_debut <= dev_debut, f"Le développement ({dev_debut}) commence avant les données ({d_debut}).")
    exiger(dev_debut <= dev_fin, f"Développement : début {dev_debut} après fin {dev_fin}.")
    exiger(test_debut <= test_fin, f"Test final : début {test_debut} après fin {test_fin}.")
    exiger(dev_fin < test_debut, f"Le test final ({test_debut}) doit commencer après la fin du développement ({dev_fin}), sans chevauchement.")
    exiger(test_fin <= d_fin, f"La dernière cible du test ({test_fin}) est après la fin des données ({d_fin}).")

    # Préchauffage : uniquement pour les variables, aucune cible
    exiger(pre_debut == d_debut == dev_debut, f"Le préchauffage doit commencer avec les données ({d_debut}), reçu {pre_debut}.")
    exiger((pre_fin - pre_debut).days + 1 == pre_jours,
           f"Préchauffage {pre_debut} -> {pre_fin} : {(pre_fin - pre_debut).days + 1} jours, annoncé {pre_jours}.")
    exiger(premiere == pre_fin + UN_JOUR, f"La première cible ({premiere}) doit suivre le préchauffage (fin {pre_fin}).")

    # Walk-forward
    exiger(app_debut == premiere, f"Le premier apprentissage ({app_debut}) doit commencer à la première cible ({premiere}).")
    exiger(app_debut <= app_fin, f"Premier apprentissage incohérent : {app_debut} -> {app_fin}.")
    exiger(app_fin < plis_debut, f"Les plis ({plis_debut}) doivent commencer après le premier apprentissage ({app_fin}).")
    exiger(plis_debut <= plis_fin <= dev_fin, f"Les plis ({plis_debut} -> {plis_fin}) doivent rester dans le développement (fin {dev_fin}).")
    if not problemes:
        try:
            plis = plis_walk_forward(regles)
            attendu = _valeur(regles, f"{wf}.nombre_plis")
            exiger(len(plis) == attendu, f"Nombre de plis calculé {len(plis)}, annoncé {attendu}.")
            exiger(plis[-1][1] == plis_fin, f"Le dernier pli finit le {plis[-1][1]}, et non le {plis_fin}.")
            liste = decoupages(regles)
            problemes.extend(problemes_separation(liste, embargo))
            final = liste[-1]
            calcule = {"ajustement_debut": final["ajustement"][0], "ajustement_fin": final["ajustement"][1],
                       "validation_debut": final["validation"][0], "validation_fin": final["validation"][1]}
            for cle, valeur in tf_dates.items():
                exiger(valeur == calcule[cle],
                       f"Modèle du test final : {cle} = {valeur} dans le fichier, {calcule[cle]} d'après la règle des plis.")
        except ErreurRegles as erreur:
            problemes.append(str(erreur))

    # Crises : analysées sur les prévisions hors échantillon des plis
    exiger(isinstance(crises, dict) and len(crises) > 0, "Aucune période de crise définie.")
    for nom in (crises if isinstance(crises, dict) else {}):
        try:
            c_debut = _date(regles, f"crises.{nom}.debut")
            c_fin = _date(regles, f"crises.{nom}.fin")
        except ErreurRegles as erreur:
            problemes.append(str(erreur))
            continue
        exiger(c_debut <= c_fin, f"Crise {nom} : début {c_debut} après fin {c_fin}.")
        exiger(plis_debut <= c_debut and c_fin <= plis_fin,
               f"Crise {nom} ({c_debut} -> {c_fin}) hors des plis walk-forward ({plis_debut} -> {plis_fin}).")

    # Volatilité cible : données du premier apprentissage seulement
    exiger(d_debut <= vc_debut <= vc_fin <= app_fin,
           f"La volatilité cible ({vc_debut} -> {vc_fin}) doit être calculée dans le premier apprentissage.")

    # Exposition
    nombres = (int, float)
    if all(isinstance(x, nombres) and not isinstance(x, bool) for x in (expo_min, expo_max)):
        exiger(0 <= expo_min <= expo_max <= 1,
               f"Il faut 0 <= exposition_min ({expo_min}) <= exposition_max ({expo_max}) <= 1.")
    else:
        problemes.append("exposition_min et exposition_max doivent être des nombres.")

    # Jours valides et exclusions
    attendu_min = math.ceil(round(jv["bougies_par_jour"] * jv["part_min_bougies"], 9))  # round() évite 273,60000000000002
    exiger(jv["bougies_min"] == attendu_min,
           f"bougies_min = {jv['bougies_min']}, attendu {attendu_min} ({jv['part_min_bougies']:.0%} de {jv['bougies_par_jour']}).")
    exiger(5 <= jv["ecart_max_minutes"] <= 24 * 60, f"ecart_max_minutes hors limites : {jv['ecart_max_minutes']}.")
    exiger(0 < seuil_secours < 1, f"seuil_secours doit être entre 0 et 1, reçu : {seuil_secours}.")
    exiger((seuil_debut, seuil_fin) == (premiere, dev_fin),
           f"Le taux d'exclusion se mesure sur tout le développement ({premiere} -> {dev_fin}), "
           f"jamais sur le test final ; reçu {seuil_debut} -> {seuil_fin}.")

    # Premier jour des données : pas de veille, donc un rendement de moins
    exiger(premier_jour == d_debut, f"premier_jour_donnees ({premier_jour}) doit être le début des données ({d_debut}).")
    exiger(pre_debut <= premier_jour <= pre_fin and premier_jour < premiere,
           f"Le premier jour ({premier_jour}) doit être dans le préchauffage et ne jamais être une cible.")
    exiger(premier_jour_rdt == jv["bougies_par_jour"] - 1,
           f"premier_jour_rendements = {premier_jour_rdt}, attendu {jv['bougies_par_jour'] - 1}.")
    exiger(premier_jour_rdt >= jv["bougies_min"], "Le premier jour, avec un rendement de moins, doit rester valide.")

    # Correction du logarithme : s² toujours mesuré sur des jours non appris
    exiger(s2_sur == "validation_interne", f"s² doit être mesuré sur la validation interne, reçu : {s2_sur!r}.")

    # Exceptions du 2026-11-14 : GARCH sur l'ajustement seul, sigma journalière
    garch = regles.get("modeles", {}).get("garch", {})
    for cle in ("parametres_appris_sur", "facteur_appris_sur"):
        exiger(garch.get(cle) == "ajustement_du_pli",
               f"GARCH : {cle} doit être « ajustement_du_pli » (sans la validation interne), reçu : {garch.get(cle)!r}.")
    strat = regles.get("strategie", {})
    exiger(regles.get("cible", {}).get("volatilite_prevue", {}).get("echelle") == "journaliere",
           "La volatilité prévue doit être journalière.")
    exiger(strat.get("annualisation_jours") == _valeur(regles, "cible.annualisation_jours"),
           "La stratégie doit annualiser avec le même nombre de jours que la cible (365).")
    exiger(strat.get("var_horizon_jours") == 1 and strat.get("var_volatilite") == "sigma_journaliere",
           "La VaR à 1 jour utilise sigma journalière, sans annualisation.")

    # Précisions du 2026-11-15, écrites avant le calcul des variables
    var = regles.get("variables", {})
    prec, secours = var.get("precisions", {}), var.get("secours", {})
    exiger(prec.get("date_ecriture") == dt.date(2026, 11, 15),
           f"variables.precisions.date_ecriture doit être 2026-11-15, reçu : {prec.get('date_ecriture')!r}.")
    exiger(prec.get("jour_volume") == "somme_volume_cotation", "Le volume du jour doit être en USDT (volume_cotation).")
    exiger(prec.get("macd_variable") == "histogramme_divise_par_cloture",
           "L'histogramme MACD doit être divisé par la clôture.")
    exiger(prec.get("bougies_desalignees") == "manquantes",
           "Les bougies désalignées doivent rester manquantes, comme au contrôle de qualité.")
    exiger(secours.get("remplacement") == "ligne_journaliere_entiere"
           and secours.get("validite_en_entree") == "passe_seulement",
           "Secours : la ligne journalière entière est remplacée, avec une validité qui n'utilise que le passé.")
    exiger(regles.get("test_aveugle", {}).get("garde") == "refus_sans_option",
           "La garde du test aveugle ne doit avoir aucune option de contournement.")
    expl = regles.get("exploration", {})
    exiger(expl.get("periode") == "developpement_seulement", "L'exploration porte sur le développement seulement.")
    retards = expl.get("acf_retards_rapportes", [])
    exiger(bool(retards) and max(retards) <= expl.get("acf_retards_max", 0),
           f"Retards d'autocorrélation rapportés {retards} au-delà du maximum {expl.get('acf_retards_max')}.")

    # Précisions du 2026-11-16 : règles d'entraînement, écrites avant tout entraînement
    ent = regles.get("entrainement", {})
    exiger(ent.get("date_ecriture") == dt.date(2026, 11, 16),
           f"entrainement.date_ecriture doit être 2026-11-16, reçu : {ent.get('date_ecriture')!r}.")
    exiger(ent.get("un_modele_par_actif") is True, "Un modèle par actif, pour tous les modèles.")
    exiger(ent.get("perte") == "mse_log_rv" and ent.get("tft_perte") == "mse",
           "La perte d'entraînement est l'erreur quadratique sur log(RV), TFT compris.")
    exiger(isinstance(ent.get("patience_epoques"), int) and isinstance(ent.get("epoques_max"), int)
           and 0 < ent.get("patience_epoques", 0) < ent.get("epoques_max", 0),
           "Il faut 0 < patience_epoques < epoques_max.")
    exiger(not set(ent.get("reperes_non_entrees", [])) & set(ent.get("variables_continues", [])),
           "Un repère de comptage ne doit jamais être une entrée.")
    rech = ent.get("recherche", {})
    exiger(sorted(rech.get("modeles_regles", [])) == sorted(m for m in regles.get("modeles", {}).get("liste", [])
                                                             if m not in ("HAR-RV", "GARCH(1,1)")),
           "Tous les modèles réglés (XGBoost et deep learning) ont le même nombre N de combinaisons.")
    espaces = ent.get("espaces", {})
    for nom_espace, espace in espaces.items():
        for cle, valeur in espace.items():
            if isinstance(valeur, list):
                exiger(len(valeur) > 0, f"Espace {nom_espace}.{cle} vide.")
            elif isinstance(valeur, dict) and valeur.get("loi") == "log_uniforme":
                exiger(0 < valeur.get("min", 0) < valeur.get("max", 0),
                       f"Espace {nom_espace}.{cle} : il faut 0 < min < max pour une loi log-uniforme.")
    tr = espaces.get("transformer", {})
    exiger(all(d % t == 0 for d in tr.get("d_model", []) for t in tr.get("tetes", [])),
           "Transformer : chaque d_model doit être divisible par chaque nombre de têtes.")
    tft = espaces.get("tft", {})
    exiger(all(h % t == 0 for h in tft.get("hidden_size", []) for t in tft.get("tetes_attention", [])),
           "TFT : chaque hidden_size doit être divisible par chaque nombre de têtes.")
    exiger(tft.get("contrainte") == "hidden_continuous_size <= hidden_size",
           "TFT : la contrainte hidden_continuous_size <= hidden_size doit être écrite.")
    mes = ent.get("mesures", {})
    exiger(mes.get("donnees") == "aleatoires_meme_forme", "Les mesures se font sur des données aléatoires seulement.")
    exiger(mes.get("n_minimum", 0) >= 1 and mes.get("marge_memoire", 0) >= 1 and mes.get("budget_heures_deep_learning", 0) > 0,
           "Mesures : n_minimum >= 1, marge_memoire >= 1 et budget en heures > 0.")
    exiger(ent.get("reprise", {}).get("graine_unite") == "hachage_de_l_identifiant",
           "Reprise : la graine d'une unité vient de son identifiant, jamais de l'ordre d'exécution.")

    # Exceptions du 2026-11-16 (avant tout entraînement réel)
    exiger(ent.get("exceptions_date") == dt.date(2026, 11, 16), "entrainement.exceptions_date doit être 2026-11-16.")
    exiger(ent.get("optimiseur") == "adamw", "Optimiseur AdamW pour tous les modèles de deep learning.")
    exiger(ent.get("alimentation") == "secteur_obligatoire" and ent.get("arret_sur_batterie") == "apres_unite_en_cours",
           "Alimentation : refus de démarrer sur batterie, arrêt propre après l'unité en cours.")
    exiger(_valeur(regles, "evaluation.diebold_mariano.test_principal") == "plis_reunis",
           "Diebold-Mariano : un seul test principal, sur les plis réunis.")
    if not problemes:
        pli1 = decoupages(regles)[0]
        reglage = ((rech.get("reglage_ajustement_debut"), rech.get("reglage_ajustement_fin")),
                   (rech.get("reglage_validation_debut"), rech.get("reglage_validation_fin")))
        exiger(rech.get("reglage") == "une_fois_par_actif_et_modele" and reglage == (pli1["ajustement"], pli1["validation"]),
               f"Réglage des hyperparamètres : une seule fois, sur le premier découpage {pli1['ajustement']} / "
               f"{pli1['validation']} ; reçu {reglage}.")
        exiger(reglage[1][1] < pli1["evaluation"][0], "Le réglage ne doit utiliser que l'information disponible avant les plis.")
    exiger(mes.get("repetitions", 0) >= 3 and mes.get("statistique") == "mediane",
           "Mesures : au moins 3 répétitions, médiane retenue.")

    # Précisions du 2026-11-16, écrites avant le calcul des baselines
    ev = regles.get("evaluation", {})
    pe = ev.get("precisions", {})
    exiger(pe.get("date_precisions") == dt.date(2026, 11, 16), "evaluation.precisions.date_precisions doit être 2026-11-16.")
    exiger(pe.get("qlike_forme") == "RV2/h - ln(RV2/h) - 1", "QLIKE : forme de Patton, nulle quand la prévision est exacte.")
    exiger(pe.get("prevision_modele_regle") == "moyenne_des_log_des_graines"
           and pe.get("s2_prevision_moyenne") == "validation_interne",
           "Modèle réglé : prévision = moyenne des log des graines, s² mesuré pour elle sur la validation interne.")
    exiger(pe.get("sorties_journalieres") == "sorties/", "Les prévisions journalières vont dans sorties/ (ignoré par Git).")
    pers = regles.get("modeles", {}).get("persistance", {})
    exiger(pers.get("dans_selection") is False and pers.get("dans_diebold_mariano_principal") is False,
           "La persistance est descriptive : hors de la sélection et des tests de Diebold-Mariano principaux.")
    gp = regles.get("modeles", {}).get("garch_precisions", {})
    exiger(gp.get("backcast") == "calcule_sur_l_ajustement_puis_fixe"
           and gp.get("mise_a_jour") == "parametres_fixes_serie_coupee_a_l_origine",
           "GARCH : variance de départ calculée sur l'ajustement puis fixée ; paramètres figés, série coupée à l'origine.")
    dm = ev.get("diebold_mariano", {})
    exiger(dm.get("difference") == "QLIKE(modele) - QLIKE(HAR-RV)" and dm.get("bilateral") is True,
           "Diebold-Mariano : différence QLIKE(modèle) − QLIKE(HAR-RV), test bilatéral.")
    exiger(ev.get("bootstrap", {}).get("blocs") == "mobiles", "Bootstrap par blocs mobiles.")

    if problemes:
        raise ErreurRegles("Règles incohérentes :\n- " + "\n- ".join(problemes))


def valeurs_a_fixer(regles: dict, prefixe: str = "") -> list[str]:
    """Chemins des valeurs encore égales à "a_fixer_apres_mesure"."""
    trouvees = []
    for cle, valeur in regles.items():
        chemin = f"{prefixe}{cle}"
        if isinstance(valeur, dict):
            trouvees.extend(valeurs_a_fixer(valeur, chemin + "."))
        elif valeur == A_FIXER:
            trouvees.append(chemin)
    return trouvees


def verifier_pret_pour_entrainement(regles: dict) -> None:
    """Refuse l'entraînement tant qu'une valeur reste à fixer après mesure."""
    restantes = valeurs_a_fixer(regles)
    if restantes:
        raise ErreurRegles(
            "Entraînement refusé : ces valeurs doivent d'abord être fixées par une mesure, "
            "puis écrites dans config/regles.toml et docs/CHOIX.md : " + ", ".join(restantes)
        )


# --------------------------------------------------------------------------
# Résumé lisible
# --------------------------------------------------------------------------

def _pourcent(x: float) -> str:
    """Format français : 0.001 -> "0,10 %"."""
    return f"{x * 100:.2f}".replace(".", ",") + " %"


def resume(regles: dict) -> str:
    d, c = regles["donnees"], regles["decoupage"]
    wf, pre = c["walk_forward"], c["prechauffage"]
    s, e = regles["strategie"], regles["evaluation"]
    lignes = ["Règles du projet volatility-forecasting-dl",
              "(toutes les bornes de découpage sont des dates de CIBLE, c'est-à-dire J+1)", ""]

    def ligne(etiquette: str, texte: str) -> None:
        lignes.append(f"{etiquette:<15}: {texte}")

    ligne("Données", f"{d['source']}, bougies {d['intervalle']}, {', '.join(d['actifs'])}, fuseau {d['fuseau']}")
    ligne("", f"du {d['debut']} au {d['fin']} ; jour valide si >= {d['jour_valide']['bougies_min']} bougies "
              f"sur {d['jour_valide']['bougies_par_jour']} et aucun écart > {d['jour_valide']['ecart_max_minutes']} min")
    ligne("Préchauffage", f"{pre['debut']} -> {pre['fin']} ({pre['jours']} jours, variables seulement)")
    ligne("Première cible", str(c["premiere_cible"]))
    ligne("Développement", f"cibles du {c['premiere_cible']} au {c['dev_fin']}")
    ligne("Test final", f"cibles du {c['test_debut']} au {c['test_fin']} (ouvert {c['test_ouvertures_max']} fois)")
    ligne("Walk-forward", f"{wf['nombre_plis']} plis de {wf['duree_pli_mois']} mois, fenêtre {wf['fenetre']}, "
                          f"validation interne {wf['validation_interne_mois']} mois, embargo {c['embargo_jours']} jour")
    for dec in decoupages(regles):
        (a0, a1), (j0, j1), (v0, v1), (e0, e1) = dec["apprentissage"], dec["ajustement"], dec["validation"], dec["evaluation"]
        ligne("", f"{dec['nom']:<10} ajustement {j0} -> {j1} | validation {v0} -> {v1} | évaluation {e0} -> {e1}")
    ligne("Crises", " ; ".join(f"{nom} {p['debut']} -> {p['fin']}" for nom, p in regles["crises"].items()))
    rl, vp = regles["cible"]["retour_log"], regles["cible"]["volatilite_prevue"]
    ligne("Cible", f"RV de J+{regles['cible']['horizon_jours']}, modélisée en {regles['cible']['transformation_modele']}")
    ligne("", f"variance prévue {rl['variance']} (s2 sur la {rl['s2_mesuree_sur'].replace('_', ' ')}) ; "
              f"volatilité prévue {vp['formule']} pour {', '.join(vp['usages'])}")
    ligne("Modèles", ", ".join(regles["modeles"]["liste"]))
    ligne("Évaluation", f"{e['metrique_principale']} sur la {e['qlike_sur']}, Diebold-Mariano contre "
                        f"{e['diebold_mariano']['reference']} (retards {e['diebold_mariano']['retards_hac']}, "
                        f"{e['diebold_mariano']['correction']}), bootstrap {e['bootstrap']['tirages']} tirages")
    ligne("", f"Diebold-Mariano : un test sur les {wf['nombre_plis']} plis réunis, un test sur le test final ; "
              "par pli et par crise : descriptif seulement")
    ligne("Stratégie", f"exposition = {s['exposition']}, bornée entre {s['exposition_min']:g} et {s['exposition_max']:g}")
    ligne("", f"VaR {s['var_horizon_jours']} jour à {_pourcent(s['var_niveau']).replace(',00', '')} "
              f"avec sigma journalière, loi {s['var_loi']} ; GARCH appris sur "
              f"{regles['modeles']['garch']['parametres_appris_sur'].replace('_', ' ')}")
    ligne("", f"frais "
                       f"{_pourcent(s['frais'])} (sensibilité {', '.join(_pourcent(x) for x in s['frais_sensibilite'])})")
    ligne("Graine", str(regles["projet"]["graine"]))
    restantes = valeurs_a_fixer(regles)
    ligne("À fixer", ", ".join(restantes) if restantes else "aucune")
    return "\n".join(lignes)


def main(arguments: list[str]) -> int:
    # Protège l'affichage sous Windows : un caractère non affichable devient "?" au lieu de planter.
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(errors="replace")
    try:
        regles = charger_regles()
        print(resume(regles))
        if "--entrainement" in arguments:
            verifier_pret_pour_entrainement(regles)
            print("Prêt pour l'entraînement.")
    except ErreurRegles as erreur:
        print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
