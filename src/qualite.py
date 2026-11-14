"""Contrôles de qualité des bougies converties.

Produit rapports/qualite_donnees.json et docs/QUALITE_DONNEES.md (générés, rien à la main).

Test aveugle : pour la période du test final, seuls des COMPTAGES sont produits (bougies,
trous, jours valides, nombre d'incohérences). Aucune statistique de prix, de rendement, de
volume ou de volatilité n'est calculée pour l'affichage, ni pour le test ni pour le développement.

Règle d'attribution d'un trou (exception datée du 2026-11-14, docs/CHOIX.md) : un écart entre deux
bougies consécutives est compté pour chaque jour qui contient une partie des bougies manquantes,
et pour le jour de la bougie qui suit le trou (son premier rendement enjambe le trou).

Usage : .venv\\Scripts\\python src/qualite.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))

import commun as C  # noqa: E402
import regles as R  # noqa: E402

PAS_MIN = 5
MINUTES_PAR_JOUR = 1440
CHEMIN_JSON = C.DOSSIER_RAPPORTS / "qualite_donnees.json"
CHEMIN_MD = C.RACINE / "docs" / "QUALITE_DONNEES.md"
EPOQUE = pd.Timestamp("1970-01-01", tz="UTC")


def minutes_et_alignement(dates: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """Dates UTC -> (minutes depuis 1970, arrondies vers le bas ; vrai si la bougie est sur la grille de 5 min).

    Une bougie « désalignée » (qui ne commence pas à hh:00, hh:05, …) est comptée à part et traitée
    comme manquante pour la validité des jours (exception datée du 2026-11-14, docs/CHOIX.md).
    """
    us = ((dates - EPOQUE) // pd.Timedelta(microseconds=1)).to_numpy(dtype="int64")
    return us // 60_000_000, (us % (PAS_MIN * 60_000_000)) == 0


def jour_vers_date(indice_jour: int) -> dt.date:
    return dt.date(1970, 1, 1) + dt.timedelta(days=int(indice_jour))


def date_vers_jour(jour: dt.date) -> int:
    return (jour - dt.date(1970, 1, 1)).days


def trous(minutes: np.ndarray) -> pd.DataFrame:
    """Trous entre bougies consécutives (minutes triées et uniques)."""
    ecarts = np.diff(minutes)
    i = np.nonzero(ecarts > PAS_MIN)[0]
    return pd.DataFrame({
        "avant": minutes[i], "apres": minutes[i + 1], "ecart_min": ecarts[i],
        "bougies_manquantes": ecarts[i] // PAS_MIN - 1,
    })


def bilan_jours(minutes: np.ndarray, debut: dt.date, fin: dt.date, regles: dict) -> pd.DataFrame:
    """Une ligne par jour UTC de `debut` à `fin` : bougies, rendements, plus grand écart, validité."""
    j0, j1 = date_vers_jour(debut), date_vers_jour(fin)
    nb_jours = j1 - j0 + 1
    jours = minutes // MINUTES_PAR_JOUR
    dans = (jours >= j0) & (jours <= j1)
    bougies = np.bincount(jours[dans] - j0, minlength=nb_jours)

    # Rendements : bougies - 1, plus 1 si une clôture existe avant la première bougie du jour
    premiere_globale = minutes.min() if minutes.size else None
    a_veille = np.zeros(nb_jours, dtype=bool)
    if minutes.size:
        premiers = pd.Series(minutes[dans]).groupby(jours[dans] - j0).min()
        a_veille[premiers.index.to_numpy()] = premiers.to_numpy() > premiere_globale
    rendements = np.where(bougies > 0, bougies - 1 + a_veille, 0)

    # Plus grand écart touchant chaque jour
    ecart_max = np.full(nb_jours, PAS_MIN, dtype="int64")
    for avant, apres, ecart in trous(minutes)[["avant", "apres", "ecart_min"]].itertuples(index=False):
        premier_jour = (avant + PAS_MIN) // MINUTES_PAR_JOUR - j0
        dernier_jour = apres // MINUTES_PAR_JOUR - j0
        a, b = max(premier_jour, 0), min(dernier_jour, nb_jours - 1)
        if a <= b:
            ecart_max[a:b + 1] = np.maximum(ecart_max[a:b + 1], ecart)

    valide = [R.jour_valide(regles, int(n), int(e)) for n, e in zip(rendements, ecart_max)]
    jv = regles["donnees"]["jour_valide"]
    return pd.DataFrame({
        "jour": [jour_vers_date(j0 + k) for k in range(nb_jours)],
        "bougies": bougies, "rendements": rendements, "ecart_max_min": ecart_max, "valide": valide,
        "trop_peu": rendements < jv["bougies_min"], "ecart_trop_long": ecart_max > jv["ecart_max_minutes"],
    })


def taux_exclusion(jours: pd.DataFrame, regles: dict) -> dict:
    """Exemples (dates de cible) de la période de mesure du seuil, exclus par leur fenêtre d'entrée."""
    ex = regles["donnees"]["exclusions"]
    fenetre = ex["fenetre_entree_jours"]
    invalides = set(jours.loc[~jours["valide"], "jour"])
    cibles = pd.date_range(ex["seuil_mesure_debut"], ex["seuil_mesure_fin"], freq="D").date
    exclus_fenetre = exclus_cible = exclus_total = 0
    for cible in cibles:
        par_fenetre = any((cible - dt.timedelta(days=k)) in invalides for k in range(1, fenetre + 1))
        par_cible = cible in invalides
        exclus_fenetre += par_fenetre
        exclus_cible += par_cible
        exclus_total += par_fenetre or par_cible
    n = len(cibles)
    return {"exemples": n, "exclus_par_fenetre": exclus_fenetre, "exclus_par_cible_invalide": exclus_cible,
            "exclus_au_total": exclus_total, "taux_fenetre": exclus_fenetre / n, "taux_total": exclus_total / n}


def comptages_periode(df: pd.DataFrame, minutes_bruts: np.ndarray, aligne: np.ndarray, jours: pd.DataFrame,
                      debut: dt.date, fin: dt.date, detail: bool, regles: dict) -> dict:
    """Comptages sur une période. `detail` ajoute les listes de trous et de jours (développement seulement)."""
    j0, j1 = date_vers_jour(debut), date_vers_jour(fin)
    jour_brut = minutes_bruts // MINUTES_PAR_JOUR
    dans_brut = (jour_brut >= j0) & (jour_brut <= j1)
    sous = df.loc[dans_brut]
    m = np.unique(minutes_bruts[dans_brut & aligne])
    # ordre (dans l'ordre du fichier) : une bougie qui n'est pas strictement après la précédente
    desordre = int(((np.diff(df["date_ouverture"].array.asi8) <= 0) & dans_brut[1:]).sum())
    t = trous(np.unique(minutes_bruts[aligne]))
    t = t[(t["apres"] // MINUTES_PAR_JOUR >= j0) & (t["avant"] // MINUTES_PAR_JOUR <= j1)]
    ecarts = np.diff(m)
    p = jours[(jours["jour"] >= debut) & (jours["jour"] <= fin)]
    jv = regles["donnees"]["jour_valide"]
    par_jour, minimum = jv["bougies_par_jour"], jv["bougies_min"]
    resultat = {
        "jours": int(len(p)),
        "bougies_attendues": int(len(p) * par_jour),
        "bougies_observees": int(len(m)),
        "bougies_desalignees": int((dans_brut & ~aligne).sum()),
        "doublons": int((dans_brut & aligne).sum() - len(m)),
        "hors_ordre": desordre,
        "ecarts_non_multiples_de_5_min": int((ecarts % PAS_MIN != 0).sum()),
        "trous": int(len(t)),
        "trous_de_plus_de_60_min": int((t["ecart_min"] > 60).sum()),
        "bougies_manquantes_dans_les_trous": int(t["bougies_manquantes"].sum()),
        "valeurs_manquantes": int(sous[["ouverture", "plus_haut", "plus_bas", "cloture", "volume"]].isna().sum().sum()),
        "prix_negatifs_ou_nuls": int((sous[["ouverture", "plus_haut", "plus_bas", "cloture"]] <= 0).sum().sum()),
        "incoherences_prix": int(((sous["plus_bas"] > sous[["ouverture", "cloture"]].min(axis=1))
                                  | (sous["plus_haut"] < sous[["ouverture", "cloture"]].max(axis=1))
                                  | (sous["plus_bas"] > sous["plus_haut"])).sum()),
        "volumes_negatifs": int((sous["volume"] < 0).sum()),
        "jours_valides": int(p["valide"].sum()),
        "jours_non_valides": int((~p["valide"]).sum()),
        "jours_non_valides_trop_peu_de_rendements": int(p["trop_peu"].sum()),
        "jours_non_valides_ecart_trop_long": int(p["ecart_trop_long"].sum()),
        "jours_par_nombre_de_bougies": {
            "complet": int((p["bougies"] == par_jour).sum()),
            "entre_minimum_et_complet": int(p["bougies"].between(minimum, par_jour - 1).sum()),
            "sous_le_minimum": int(p["bougies"].between(1, minimum - 1).sum()),
            "aucune": int((p["bougies"] == 0).sum()),
            "plus_que_complet": int((p["bougies"] > par_jour).sum()),
        },
    }
    if detail:
        hors_grille = np.nonzero(dans_brut & ~aligne)[0]
        series, debut_serie = [], None
        for k, i in enumerate(hors_grille):
            if debut_serie is None:
                debut_serie = i
            if k + 1 == len(hors_grille) or hors_grille[k + 1] != i + 1:
                series.append({"premiere": str(df["date_ouverture"].iloc[debut_serie]),
                               "derniere": str(df["date_ouverture"].iloc[i]), "bougies": int(i - debut_serie + 1)})
                debut_serie = None
        resultat["liste_desalignements"] = series
        resultat["liste_trous"] = [
            {"debut": str(EPOQUE + pd.Timedelta(minutes=int(a + PAS_MIN))), "fin": str(EPOQUE + pd.Timedelta(minutes=int(b - PAS_MIN))),
             "duree_min": int(e - PAS_MIN), "bougies_manquantes": int(n)}
            for a, b, e, n in t[["avant", "apres", "ecart_min", "bougies_manquantes"]].itertuples(index=False)]
        resultat["liste_jours_non_valides"] = [
            {"jour": str(r.jour), "bougies": int(r.bougies), "rendements": int(r.rendements), "ecart_max_min": int(r.ecart_max_min)}
            for r in p[~p["valide"]].itertuples(index=False)]
    return resultat


def mois_complet(minutes: np.ndarray, annee: int, mois: int, bougies_par_jour: int) -> dict:
    debut = dt.date(annee, mois, 1)
    fin = (dt.date(annee + (mois == 12), mois % 12 + 1, 1)) - dt.timedelta(days=1)
    j0, j1 = date_vers_jour(debut), date_vers_jour(fin)
    jours = minutes // MINUTES_PAR_JOUR
    m = np.unique(minutes[(jours >= j0) & (jours <= j1)])
    attendues = (j1 - j0 + 1) * bougies_par_jour
    return {"mois": f"{annee:04d}-{mois:02d}", "bougies_attendues": int(attendues), "bougies_observees": int(len(m)),
            "complet": bool(len(m) == attendues)}


def analyser_actif(chemin: Path, regles: dict) -> dict:
    df = pq.read_table(chemin, columns=["date_ouverture", "ouverture", "plus_haut", "plus_bas", "cloture", "volume"]).to_pandas()
    minutes_bruts, aligne = minutes_et_alignement(df["date_ouverture"])
    m = np.unique(minutes_bruts[aligne])
    d, c = regles["donnees"], regles["decoupage"]
    jours = bilan_jours(m, d["debut"], d["fin"], regles)
    premier_jour = jours.iloc[0]
    bpj = d["jour_valide"]["bougies_par_jour"]
    return {
        "developpement": comptages_periode(df, minutes_bruts, aligne, jours, d["debut"], c["dev_fin"], True, regles),
        "test_final_comptages_seulement": comptages_periode(df, minutes_bruts, aligne, jours, c["test_debut"],
                                                            c["test_fin"], False, regles),
        "premier_mois": mois_complet(m, d["debut"].year, d["debut"].month, bpj),
        "dernier_mois": mois_complet(m, d["fin"].year, d["fin"].month, bpj),
        "premier_jour": {"jour": str(premier_jour["jour"]), "bougies": int(premier_jour["bougies"]),
                         "rendements": int(premier_jour["rendements"]), "valide": bool(premier_jour["valide"])},
        "seuil_de_secours": taux_exclusion(jours, regles),
    }


def pourcent_fr(x: float) -> str:
    return C.nombre_fr(100 * x, 2) + " %"


def rapport_markdown(rapport: dict) -> str:
    n = C.nombre_fr
    lignes = [
        "# Qualité des données",
        "",
        "Fichier généré par `src/qualite.py` à partir de `rapports/qualite_donnees.json` : ne pas le modifier à la main.",
        "",
        f"- Empreinte du manifeste des données traitées : `{rapport['manifeste_traite_sha256'][:16]}…`",
        f"- Période de développement : du {rapport['periodes']['developpement'][0]} au {rapport['periodes']['developpement'][1]} "
        "(préchauffage compris).",
        f"- Test final : du {rapport['periodes']['test_final'][0]} au {rapport['periodes']['test_final'][1]}, "
        "**comptages seulement** (test aveugle : aucune statistique de prix, de rendement, de volume ou de volatilité).",
        "",
        "## Seuil de secours (5 %)",
        "",
        f"Mesuré une seule fois, par actif, sur les cibles du {rapport['periodes']['mesure_seuil'][0]} au "
        f"{rapport['periodes']['mesure_seuil'][1]}. Un exemple est exclu si sa fenêtre d'entrée de 30 jours contient un jour non valide.",
        "",
        "| Actif | Exemples | Exclus par la fenêtre | Taux | Exclus au total (fenêtre ou cible) | Taux total |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for actif, r in rapport["actifs"].items():
        s = r["seuil_de_secours"]
        lignes.append(f"| {actif} | {n(s['exemples'])} | {n(s['exclus_par_fenetre'])} | {pourcent_fr(s['taux_fenetre'])} | "
                      f"{n(s['exclus_au_total'])} | {pourcent_fr(s['taux_total'])} |")
    lignes += ["", f"**Règle de secours appliquée : {'oui' if rapport['secours_active'] else 'non'}.**", ""]

    lignes += ["## Comptages par actif", "",
               "| Contrôle | " + " | ".join(f"{a} dév. | {a} test" for a in rapport["actifs"]) + " |",
               "|---|" + "---:|---:|" * len(rapport["actifs"])]
    cles = [("jours", "Jours"), ("bougies_attendues", "Bougies attendues"), ("bougies_observees", "Bougies observées"),
            ("bougies_desalignees", "Bougies désalignées (hors grille de 5 min, comptées comme manquantes)"),
            ("doublons", "Doublons"), ("hors_ordre", "Bougies hors d'ordre"),
            ("ecarts_non_multiples_de_5_min", "Écarts non multiples de 5 min"), ("trous", "Trous"),
            ("trous_de_plus_de_60_min", "Trous de plus de 60 min"), ("bougies_manquantes_dans_les_trous", "Bougies manquantes (trous)"),
            ("valeurs_manquantes", "Valeurs manquantes"), ("prix_negatifs_ou_nuls", "Prix négatifs ou nuls"),
            ("incoherences_prix", "Incohérences de prix (bas/haut)"), ("volumes_negatifs", "Volumes négatifs"),
            ("jours_valides", "Jours valides"), ("jours_non_valides", "Jours non valides"),
            ("jours_non_valides_trop_peu_de_rendements", "… dont moins de 274 rendements"),
            ("jours_non_valides_ecart_trop_long", "… dont un écart de plus de 60 min")]
    for cle, libelle in cles:
        valeurs = []
        for r in rapport["actifs"].values():
            valeurs += [n(r["developpement"][cle]), n(r["test_final_comptages_seulement"][cle])]
        lignes.append(f"| {libelle} | " + " | ".join(valeurs) + " |")

    lignes += ["", "## Début et fin des données", "", "| Actif | Premier mois | Dernier mois | Premier jour |", "|---|---|---|---|"]
    for actif, r in rapport["actifs"].items():
        pm, dm, pj = r["premier_mois"], r["dernier_mois"], r["premier_jour"]
        lignes.append(f"| {actif} | {pm['mois']} : {n(pm['bougies_observees'])} / {n(pm['bougies_attendues'])} "
                      f"({'complet' if pm['complet'] else 'INCOMPLET'}) | {dm['mois']} : {n(dm['bougies_observees'])} / "
                      f"{n(dm['bougies_attendues'])} ({'complet' if dm['complet'] else 'INCOMPLET'}) | {pj['jour']} : "
                      f"{pj['bougies']} bougies, {pj['rendements']} rendements, {'valide' if pj['valide'] else 'NON VALIDE'} |")

    for actif, r in rapport["actifs"].items():
        dev = r["developpement"]
        lignes += ["", f"## {actif} : jours non valides du développement ({n(len(dev['liste_jours_non_valides']))})", ""]
        if dev["liste_jours_non_valides"]:
            lignes += ["| Jour | Bougies | Rendements | Plus grand écart (min) |", "|---|---:|---:|---:|"]
            lignes += [f"| {j['jour']} | {j['bougies']} | {j['rendements']} | {n(j['ecart_max_min'])} |" for j in dev["liste_jours_non_valides"]]
        else:
            lignes.append("Aucun.")
        lignes += ["", f"### {actif} : bougies désalignées du développement", ""]
        if dev["liste_desalignements"]:
            lignes += ["| Première | Dernière | Bougies |", "|---|---|---:|"]
            lignes += [f"| {s['premiere']} | {s['derniere']} | {n(s['bougies'])} |" for s in dev["liste_desalignements"]]
        else:
            lignes.append("Aucune.")
        longs = sorted(dev["liste_trous"], key=lambda t: (-t["duree_min"], t["debut"]))
        lignes += ["", f"### {actif} : trous du développement ({n(len(longs))}, du plus long au plus court)", ""]
        if longs:
            lignes += ["| Début (première bougie manquante) | Fin (dernière bougie manquante) | Durée (min) | Bougies manquantes |",
                       "|---|---|---:|---:|"]
            lignes += [f"| {t['debut']} | {t['fin']} | {n(t['duree_min'])} | {n(t['bougies_manquantes'])} |" for t in longs]
        else:
            lignes.append("Aucun.")
    return "\n".join(lignes) + "\n"


def executer(regles: dict, dossier_traite: Path, chemin_manifeste_traite: Path, chemin_json: Path, chemin_md: Path) -> dict:
    d, c, ex = regles["donnees"], regles["decoupage"], regles["donnees"]["exclusions"]
    rapport = {
        "manifeste_traite_sha256": hashlib.sha256(chemin_manifeste_traite.read_bytes()).hexdigest(),
        "periodes": {"developpement": [str(d["debut"]), str(c["dev_fin"])],
                     "test_final": [str(c["test_debut"]), str(c["test_fin"])],
                     "mesure_seuil": [str(ex["seuil_mesure_debut"]), str(ex["seuil_mesure_fin"])]},
        "actifs": {},
    }
    for actif in d["actifs"]:
        rapport["actifs"][actif] = analyser_actif(dossier_traite / f"{actif}_5m.parquet", regles)
    taux = {a: r["seuil_de_secours"]["taux_fenetre"] for a, r in rapport["actifs"].items()}
    rapport["secours_active"] = R.secours_active(regles, taux)
    C.ecrire_texte(chemin_json, C.texte_json(rapport))
    C.ecrire_texte(chemin_md, rapport_markdown(rapport))
    return rapport


def main() -> int:
    C.proteger_sortie()
    debut = time.perf_counter()
    regles = R.charger_regles()
    rapport = executer(regles, C.DOSSIER_TRAITE, C.MANIFESTE_TRAITE, CHEMIN_JSON, CHEMIN_MD)
    for actif, r in rapport["actifs"].items():
        dev, test = r["developpement"], r["test_final_comptages_seulement"]
        print(f"{actif} | dév. : {dev['jours_non_valides']} jours non valides, {dev['trous']} trous | "
              f"test : {test['jours_non_valides']} jours non valides, {test['trous']} trous | "
              f"taux d'exclusion {pourcent_fr(r['seuil_de_secours']['taux_fenetre'])}")
    print(f"Règle de secours : {'oui' if rapport['secours_active'] else 'non'}")
    print(f"Rapports : {C.chemin_relatif(CHEMIN_JSON)}, {C.chemin_relatif(CHEMIN_MD)}")
    duree = time.perf_counter() - debut
    print(f"Durée : {C.nombre_fr(duree, 1)} s | mémoire maximale du processus : {C.nombre_fr(C.memoire_max_mo(), 1)} Mo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
