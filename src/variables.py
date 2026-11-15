"""Volatilité réalisée, variables et cible, à partir des bougies de 5 minutes converties.

Toutes les règles sont lues dans config/regles.toml (sections donnees, decoupage, variables,
strategie). Les jours valides et les trous viennent de src/qualite.py : une seule source de vérité.

- Jour UTC [00:00 ; 24:00[ ; ligne journalière : ouverture de la première bougie, plus haut,
  plus bas, clôture de la dernière bougie, volume en USDT (somme de volume_cotation).
- RV du jour = racine de la somme des carrés des log-rendements entre clôtures consécutives
  disponibles ; le premier rendement du jour part de la dernière clôture de la veille.
- Variables arrêtées à la clôture de J (passé strict) ; cible = log(RV de J+1).
- Règle de secours (déclenchée à l'étape des données) : en ENTRÉE, la ligne journalière entière
  d'un jour non valide est remplacée par celle du dernier jour valide ; les variables sont
  ensuite calculées sur cette série. La cible n'est jamais remplacée : une cible non valide est exclue.
- Test aveugle : les variables du test final sont calculées et écrites, jamais affichées.
  Ce script n'affiche que des comptages.

Sorties : data/processed/variables.parquet (jamais commité), data/manifeste_variables.json et
rapports/volatilite_cible.json (une valeur agrégée par actif, calculée sur 2018-2019).

Usage : .venv\\Scripts\\python src/variables.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import math
import os
import sys
import time
from collections.abc import Callable, Iterable
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))

import commun as C  # noqa: E402
import convertir as CV  # noqa: E402
import garde as G  # noqa: E402
import qualite as Q  # noqa: E402
import regles as R  # noqa: E402

COLONNES_BOUGIES = ["date_ouverture", "ouverture", "plus_haut", "plus_bas", "cloture", "volume_cotation"]
COLONNES_LIGNE = ["ouverture", "plus_haut", "plus_bas", "cloture", "volume", "rv"]
CHEMIN_VOL_CIBLE = C.DOSSIER_RAPPORTS / "volatilite_cible.json"
UN_JOUR = dt.timedelta(days=1)


class ErreurVariables(ValueError):
    pass


# --- Formules (vérifiées à la main dans tests/test_variables.py) -----------------------

def parkinson(haut, bas):
    """ln(H/L)² / (4 ln 2)."""
    return np.log(haut / bas) ** 2 / (4 * math.log(2))


def garman_klass(ouverture, haut, bas, cloture):
    """0,5 ln(H/L)² − (2 ln 2 − 1) ln(C/O)²."""
    return 0.5 * np.log(haut / bas) ** 2 - (2 * math.log(2) - 1) * np.log(cloture / ouverture) ** 2


def rsi_wilder(clotures: pd.Series, n: int) -> pd.Series:
    """RSI de Wilder : moyennes des hausses et des baisses lissées avec alpha = 1/n.

    La première moyenne est la moyenne simple des n premières variations ; le RSI existe à partir
    de la (n+1)-ième clôture. Si la moyenne des baisses est nulle, le RSI vaut 100.
    """
    c = clotures.to_numpy(dtype="float64")
    resultat = np.full(len(c), np.nan)
    variations = np.diff(c)
    if len(variations) < n:
        return pd.Series(resultat, index=clotures.index)
    hausses, baisses = np.clip(variations, 0, None), np.clip(-variations, 0, None)

    def valeur(mh: float, mb: float) -> float:
        return 100.0 if mb == 0 else 100.0 - 100.0 / (1.0 + mh / mb)

    mh, mb = hausses[:n].mean(), baisses[:n].mean()
    resultat[n] = valeur(mh, mb)
    for i in range(n, len(variations)):
        mh = (mh * (n - 1) + hausses[i]) / n
        mb = (mb * (n - 1) + baisses[i]) / n
        resultat[i + 1] = valeur(mh, mb)
    return pd.Series(resultat, index=clotures.index)


def macd_histogramme(clotures: pd.Series, rapide: int, lente: int, signal: int) -> pd.Series:
    """Histogramme MACD = (EMA rapide − EMA lente) − signal ; moyennes démarrées à la première clôture."""
    ligne = (clotures.ewm(span=rapide, adjust=False).mean() - clotures.ewm(span=lente, adjust=False).mean())
    return ligne - ligne.ewm(span=signal, adjust=False).mean()


def bollinger_largeur(clotures: pd.Series, n: int, ecarts_types: float) -> pd.Series:
    """(bande haute − bande basse) / moyenne mobile, écart-type de population (ddof = 0)."""
    moyenne = clotures.rolling(n, min_periods=n).mean()
    ecart = clotures.rolling(n, min_periods=n).std(ddof=0)
    return 2 * ecarts_types * ecart / moyenne


# --- Lignes journalières, RV et validité ---------------------------------------------

def lire_bougies(chemin: Path) -> pd.DataFrame:
    return pq.read_table(chemin, columns=COLONNES_BOUGIES).to_pandas()


def _minutes_alignees(bougies: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """Bougies sur la grille de 5 minutes (les désalignées sont manquantes) et leurs minutes."""
    minutes, aligne = Q.minutes_et_alignement(bougies["date_ouverture"])
    b, m = bougies.loc[aligne], minutes[aligne]
    if m.size and (np.diff(m) <= 0).any():
        raise ErreurVariables("Bougies en double ou hors d'ordre : la conversion aurait dû l'empêcher.")
    return b, m


def lignes_journalieres(bougies: pd.DataFrame, regles: dict, debut: dt.date, fin: dt.date) -> pd.DataFrame:
    """Une ligne par jour UTC de `debut` à `fin` : ouverture, haut, bas, clôture, volume, RV, validité.

    Les jours sans bougie ont des valeurs manquantes (ils sont non valides).
    """
    b, m = _minutes_alignees(bougies)
    clotures = b["cloture"].to_numpy(dtype="float64")
    carres = np.full(len(clotures), np.nan)
    carres[1:] = np.log(clotures[1:] / clotures[:-1]) ** 2   # rendement entre clôtures consécutives disponibles
    jour = m // Q.MINUTES_PAR_JOUR
    j0, j1 = Q.date_vers_jour(debut), Q.date_vers_jour(fin)
    dans = (jour >= j0) & (jour <= j1)
    t = pd.DataFrame({"jour": jour[dans], "o": b["ouverture"].to_numpy()[dans], "h": b["plus_haut"].to_numpy()[dans],
                      "l": b["plus_bas"].to_numpy()[dans], "c": clotures[dans],
                      "v": b["volume_cotation"].to_numpy()[dans], "r2": carres[dans]})
    g = t.groupby("jour", sort=True)
    agregat = pd.DataFrame({"ouverture": g["o"].first(), "plus_haut": g["h"].max(), "plus_bas": g["l"].min(),
                            "cloture": g["c"].last(), "volume": g["v"].sum(),
                            "rv": np.sqrt(g["r2"].sum(min_count=1))})
    agregat = agregat.reindex(range(j0, j1 + 1))
    bilan = Q.bilan_jours(m, debut, fin, regles)            # une seule source de vérité pour la validité
    agregat.index = pd.Index([Q.jour_vers_date(j) for j in agregat.index], name="jour")
    bilan = bilan.set_index("jour")
    agregat["rendements"] = bilan["rendements"].to_numpy()
    agregat["valide"] = bilan["valide"].to_numpy()
    return agregat


def controle_validite_passe(bougies: pd.DataFrame, lignes: pd.DataFrame, regles: dict) -> int:
    """Vérifie que la validité de chaque jour, utilisée en entrée, n'utilise jamais l'avenir.

    Seul un trou qui passe minuit peut faire dépendre la validité de J de ce qui suit J. Pour chaque
    jour J touché par un tel trou, on recalcule la validité de J avec les bougies connues à la clôture
    de J seulement (et une bougie fictive à minuit : au mieux, la suivante arrive à 00:00).
    Lève ErreurVariables si le résultat diffère. Renvoie le nombre de jours contrôlés.
    """
    _, m = _minutes_alignees(bougies)
    debut, fin = lignes.index[0], lignes.index[-1]
    j0, j1 = Q.date_vers_jour(debut), Q.date_vers_jour(fin)
    controles = 0
    for avant, apres in Q.trous(m)[["avant", "apres"]].itertuples(index=False):
        premier = (avant + Q.PAS_MIN) // Q.MINUTES_PAR_JOUR
        dernier = apres // Q.MINUTES_PAR_JOUR
        for j in range(max(premier, j0), min(dernier - 1, j1) + 1):
            minuit = (j + 1) * Q.MINUTES_PAR_JOUR
            connues = np.append(m[m < minuit], minuit)
            jour = Q.jour_vers_date(j)
            passe = bool(Q.bilan_jours(connues, jour, jour, regles)["valide"].iloc[0])
            if passe != bool(lignes.loc[jour, "valide"]):
                raise ErreurVariables(
                    f"La validité du {jour} utilise l'avenir : {'valide' if passe else 'non valide'} avec les "
                    f"bougies connues à sa clôture, {'valide' if lignes.loc[jour, 'valide'] else 'non valide'} "
                    "avec le trou complet. Règle à préciser avant de continuer.")
            controles += 1
    return controles


def appliquer_secours(lignes: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Ligne entière d'un jour non valide = celle du dernier jour valide (passé seulement)."""
    if not bool(lignes["valide"].iloc[0]):
        raise ErreurVariables(f"Le premier jour ({lignes.index[0]}) n'est pas valide : aucune valeur passée à reprendre.")
    remplace = ~lignes["valide"].astype(bool)
    base = lignes[COLONNES_LIGNE].copy()
    base.loc[remplace, :] = np.nan
    return base.ffill(), remplace


# --- Variables, cible et exemples -----------------------------------------------------

def calculer_variables(base: pd.DataFrame, regles: dict) -> pd.DataFrame:
    """Variables arrêtées à la clôture de chaque jour J (index), à partir de la série remplacée."""
    v = regles["variables"]
    o, h, b, c, vol, rv = (base[k] for k in COLONNES_LIGNE)
    sortie = pd.DataFrame(index=base.index)
    for n in v["rv_moyennes_jours"]:
        sortie[f"rv_{n}"] = rv.rolling(n, min_periods=n).mean()
    for n in v["rv_moyennes_jours"]:
        sortie[f"log_rv_{n}"] = np.log(sortie[f"rv_{n}"])
    sortie["parkinson"] = parkinson(h, b)
    sortie["garman_klass"] = garman_klass(o, h, b, c)
    sortie["log_rendement"] = np.log(c / c.shift(1))
    sortie["log_volume"] = np.log(vol)
    sortie[f"rsi_{v['rsi_jours']}"] = rsi_wilder(c, v["rsi_jours"])
    rapide, lente, signal = v["macd"]
    sortie["macd_histogramme_relatif"] = macd_histogramme(c, rapide, lente, signal) / c
    sortie["bollinger_largeur_relative"] = bollinger_largeur(c, v["bollinger_jours"], v["bollinger_ecarts_types"])
    sortie["jour_semaine"] = np.array([j.weekday() for j in base.index], dtype="int64")
    return sortie


def construire_exemples(lignes: pd.DataFrame, variables: pd.DataFrame, remplace: pd.Series, regles: dict) -> pd.DataFrame:
    """Un exemple par origine J : variables de J, cible = log(RV de J+1) ; cibles non valides exclues."""
    c = regles["decoupage"]
    fenetre = regles["donnees"]["exclusions"]["fenetre_entree_jours"]
    ex = variables.copy()
    ex.insert(0, "date_origine", list(variables.index))
    ex.insert(1, "date_cible", [j + UN_JOUR for j in variables.index])
    rv_suivant = lignes["rv"].shift(-1)                 # RV de J+1, jamais remplacée
    valide_suivant = lignes["valide"].shift(-1, fill_value=False).astype(bool)
    ex.insert(2, "cible", np.log(rv_suivant).to_numpy())
    ex["jour_remplace"] = remplace.astype("int64").to_numpy()
    ex["fenetre_avec_jour_remplace"] = remplace.astype("int64").rolling(fenetre, min_periods=1).max().astype("int64").to_numpy()
    garde = (ex["date_cible"] >= c["premiere_cible"]) & (ex["date_cible"] <= lignes.index[-1]) & valide_suivant.to_numpy()
    return ex.loc[garde].reset_index(drop=True)


def _dans(dates: pd.Series, debut: dt.date, fin: dt.date) -> pd.Series:
    return (dates >= debut) & (dates <= fin)


def comptages(lignes: pd.DataFrame, remplace: pd.Series, exemples: pd.DataFrame, regles: dict) -> dict:
    """Comptages seulement (permis sur le test final) : remplacements, exemples, fenêtres touchées."""
    c = regles["decoupage"]
    jours = pd.Series(list(lignes.index), index=lignes.index)
    periodes_jours = {"prechauffage": (c["prechauffage"]["debut"], c["prechauffage"]["fin"]),
                      "developpement": (c["premiere_cible"], c["dev_fin"]),
                      "test_final": (c["test_debut"], c["test_fin"])}
    periodes_cibles = {"developpement": (c["premiere_cible"], c["dev_fin"]), "test_final": (c["test_debut"], c["test_fin"])}
    resultat = {"jours_remplaces_par_date_du_jour": {
        nom: int(remplace[_dans(jours, a, b)].sum()) for nom, (a, b) in periodes_jours.items()}}
    cibles_possibles = {nom: int(_dans(jours + UN_JOUR, a, b).sum()) for nom, (a, b) in periodes_cibles.items()}
    resultat["exemples"] = {}
    for nom, (a, b) in periodes_cibles.items():
        dedans = _dans(exemples["date_cible"], a, b)
        resultat["exemples"][nom] = {"cibles_possibles": cibles_possibles[nom], "gardes": G.compter(exemples.loc[dedans, "date_cible"]),
                                     "exclus_cible_non_valide": cibles_possibles[nom] - int(dedans.sum())}
    dev = _dans(exemples["date_cible"], *periodes_cibles["developpement"])
    resultat["exemples"]["developpement"]["fenetre_30_jours_avec_jour_remplace"] = int(exemples.loc[dev, "fenetre_avec_jour_remplace"].sum())
    resultat["exemples"]["developpement"]["origine_remplacee"] = int(exemples.loc[dev, "jour_remplace"].sum())
    return resultat


def calculer_actif(bougies: pd.DataFrame, regles: dict, debut: dt.date | None = None, fin: dt.date | None = None,
                   controler: bool = True) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """(exemples, lignes journalières non remplacées, comptages) pour un actif."""
    d = regles["donnees"]
    debut, fin = debut or d["debut"], fin or d["fin"]
    lignes = lignes_journalieres(bougies, regles, debut, fin)
    jours_controles = controle_validite_passe(bougies, lignes, regles) if controler else None
    base, remplace = appliquer_secours(lignes)
    exemples = construire_exemples(lignes, calculer_variables(base, regles), remplace, regles)
    compte = comptages(lignes, remplace, exemples, regles)
    compte["jours_controles_validite_passe"] = jours_controles
    return exemples, lignes, compte


# --- Test de l'avenir modifié ------------------------------------------------------------

COLONNES_MODIFIEES = ["ouverture", "plus_haut", "plus_bas", "cloture", "volume", "volume_cotation",
                      "volume_achat_base", "volume_achat_cotation"]


def _bits(serie: pd.Series) -> np.ndarray:
    valeurs = serie.to_numpy()
    if valeurs.dtype.kind == "f":
        return valeurs.astype("<f8").view("<i8")
    return valeurs


def ecarts_avenir_modifie(bougies: pd.DataFrame, jours: Iterable[dt.date], calcul: Callable[[pd.DataFrame], pd.DataFrame],
                          facteurs: Callable[[int], np.ndarray] | None = None) -> list[str]:
    """Multiplie prix et volumes STRICTEMENT après la fin de chaque jour J, recalcule, et liste les
    variables des exemples d'origine <= J qui ont changé (comparaison au bit près).

    `calcul(bougies)` renvoie les exemples ; la cible (l'avenir, par définition) n'est pas comparée.
    `facteurs(n)` donne les multiplicateurs des n bougies modifiées (10 par défaut).
    """
    reference = calcul(bougies)
    variables = [k for k in reference.columns if k not in ("date_origine", "date_cible", "cible")]
    ecarts = []
    for j in jours:
        fin_j = pd.Timestamp(j + UN_JOUR, tz="UTC")
        modifiees = bougies.copy()
        apres = (modifiees["date_ouverture"] >= fin_j).to_numpy()
        f = np.full(int(apres.sum()), 10.0) if facteurs is None else facteurs(int(apres.sum()))
        for k in COLONNES_MODIFIEES:
            if k in modifiees.columns:
                modifiees.loc[apres, k] = modifiees.loc[apres, k].to_numpy() * f
        nouveau = calcul(modifiees)
        a = reference[reference["date_origine"] <= j].reset_index(drop=True)
        b = nouveau[nouveau["date_origine"] <= j].reset_index(drop=True)
        if len(a) != len(b) or not (a["date_origine"] == b["date_origine"]).all():
            ecarts.append(f"{j} : les exemples d'origine <= J ont changé")
            continue
        for k in variables:
            if not np.array_equal(_bits(a[k]), _bits(b[k])):
                ecarts.append(f"{j} : {k}")
    return ecarts


# --- Volatilité cible et écriture ----------------------------------------------------

def volatilite_cible(lignes: pd.DataFrame, regles: dict) -> dict:
    """Médiane de RV × racine(365) sur les jours VALIDES de la période fixée (données d'apprentissage)."""
    s = regles["strategie"]
    jours = pd.Series(list(lignes.index), index=lignes.index)
    choisis = lignes[_dans(jours, s["vol_cible_debut"], s["vol_cible_fin"]) & lignes["valide"].astype(bool)]
    G.refuser_si_test(choisis.index, "volatilité cible")
    return {"valeur_annualisee": float(np.median(choisis["rv"].to_numpy() * math.sqrt(s["annualisation_jours"]))),
            "jours_valides_utilises": int(len(choisis))}


def colonnes_sortie(exemples: pd.DataFrame) -> list[str]:
    return ["actif"] + list(exemples.columns)


def ecrire_parquet(exemples: pd.DataFrame, chemin: Path) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(exemples, preserve_index=False)
    partiel = chemin.with_name(chemin.name + ".part")
    pq.write_table(table, partiel)
    os.replace(partiel, chemin)


def _sha256(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def executer(regles: dict, dossier_traite: Path) -> dict:
    sorties = regles["variables"]["sorties"]
    chemin_parquet = C.RACINE / sorties["fichier"]
    chemin_manifeste = C.RACINE / sorties["manifeste"]
    tous, comptes, vol_cible, taux = [], {}, {}, {}
    for actif in regles["donnees"]["actifs"]:
        bougies = lire_bougies(dossier_traite / f"{actif}_5m.parquet")
        exemples, lignes, compte = calculer_actif(bougies, regles)
        taux[actif] = Q.taux_exclusion(pd.DataFrame({"jour": list(lignes.index), "valide": lignes["valide"].to_numpy()}),
                                       regles)["taux_fenetre"]
        exemples.insert(0, "actif", actif)
        tous.append(exemples)
        comptes[actif] = compte
        vol_cible[actif] = volatilite_cible(lignes, regles)
        del bougies
    if not R.secours_active(regles, taux):
        raise ErreurVariables("La règle de secours n'est pas déclenchée : la règle d'exclusion n'est pas codée ici.")
    exemples = pd.concat(tous, ignore_index=True)
    ecrire_parquet(exemples, chemin_parquet)
    colonnes = colonnes_sortie(tous[0].drop(columns="actif"))
    manifeste = {
        "fichier": sorties["fichier"],
        "lignes": int(len(exemples)),
        "colonnes": {k: str(t) for k, t in zip(pq.read_schema(chemin_parquet).names, pq.read_schema(chemin_parquet).types)},
        "empreinte_contenu_sha256": CV.empreinte_contenu(chemin_parquet, colonnes),
        "depend_de": {"manifeste_traite_sha256": _sha256(C.MANIFESTE_TRAITE),
                      "qualite_donnees_sha256": _sha256(Q.CHEMIN_JSON),
                      "regles_sha256": _sha256(R.CHEMIN_REGLES)},
        "secours_active": True,
        "comptages_par_actif": comptes,
    }
    C.ecrire_texte(chemin_manifeste, C.texte_json(manifeste))
    s = regles["strategie"]
    C.ecrire_texte(CHEMIN_VOL_CIBLE, C.texte_json({
        "methode": "médiane de RV × racine(365) sur les jours valides",
        "periode": [str(s["vol_cible_debut"]), str(s["vol_cible_fin"])],
        "actifs": vol_cible,
        "manifeste_variables_empreinte_contenu": manifeste["empreinte_contenu_sha256"],
    }))
    return manifeste


def main() -> int:
    C.proteger_sortie()
    debut = time.perf_counter()
    regles = R.charger_regles()
    try:
        manifeste = executer(regles, C.DOSSIER_TRAITE)
    except (ErreurVariables, G.ErreurTestAveugle) as erreur:
        print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1
    n = C.nombre_fr
    for actif, c in manifeste["comptages_par_actif"].items():
        r, e = c["jours_remplaces_par_date_du_jour"], c["exemples"]
        print(f"{actif} | jours remplacés : préchauffage {n(r['prechauffage'])}, dév. {n(r['developpement'])}, "
              f"test {n(r['test_final'])} | exemples gardés : dév. {n(e['developpement']['gardes'])}, "
              f"test {n(e['test_final']['gardes'])} | dév. avec un jour remplacé dans la fenêtre de 30 jours : "
              f"{n(e['developpement']['fenetre_30_jours_avec_jour_remplace'])} | jours contrôlés (validité passée) : "
              f"{n(c['jours_controles_validite_passe'])}")
    print(f"Sorties : {manifeste['fichier']} ({n(manifeste['lignes'])} lignes), "
          f"{regles['variables']['sorties']['manifeste']}, {C.chemin_relatif(CHEMIN_VOL_CIBLE)}")
    print(f"Durée : {n(time.perf_counter() - debut, 1)} s | mémoire maximale du processus : {n(C.memoire_max_mo(), 1)} Mo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
