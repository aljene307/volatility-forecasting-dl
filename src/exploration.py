"""Analyse exploratoire, sur le DÉVELOPPEMENT SEULEMENT (dates de cible jusqu'à decoupage.dev_fin).

- Les lignes journalières ne sont calculées que jusqu'à la fin du développement : aucune valeur du
  test final n'est même calculée ici. En plus, chaque statistique et chaque figure passe par la
  garde du test aveugle (src/garde.py).
- Figure 1 : RV annualisée dans le temps, avec les crises ; figure 2 : autocorrélation de log(RV) ;
  figure 3 : histogrammes de RV et de log(RV).
- Test ADF (autolag AIC) sur log(RV) et sur le log du prix de clôture.
- Nombres dans rapports/exploration.json ; docs/EXPLORATION.md est généré à partir de ce JSON.

Usage : .venv\\Scripts\\python src/exploration.py
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from statsmodels.tsa.stattools import acf, adfuller  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

import commun as C  # noqa: E402
import garde as G  # noqa: E402
import regles as R  # noqa: E402
import variables as V  # noqa: E402

COULEURS = {"BTCUSDT": "#D97706", "ETHUSDT": "#2563EB"}   # les mêmes dans toutes les figures
NOMS = {"BTCUSDT": "BTC", "ETHUSDT": "ETH"}
MENTION = "Données : Binance Vision, CC BY-NC-SA 4.0"
DOSSIER_FIGURES = C.RACINE / "figures"
CHEMIN_JSON = C.DOSSIER_RAPPORTS / "exploration.json"
CHEMIN_MD = C.RACINE / "docs" / "EXPLORATION.md"
FIGURES = {"rv": "figure_1_rv_annualisee.png", "acf": "figure_2_autocorrelation_log_rv.png",
           "histogrammes": "figure_3_histogrammes_rv.png"}


def nombre_fr_auto(x: float, decimales: int | None = None) -> str:
    """Nombre au format français ; nombre de décimales automatique si non précisé."""
    if decimales is not None:
        return C.nombre_fr(x, decimales)
    texte = f"{x:g}"
    return texte.replace("-", "−").replace(".", ",")


FORMAT_FR = FuncFormatter(lambda x, _pos: nombre_fr_auto(x))
FORMAT_POURCENT = FuncFormatter(lambda x, _pos: nombre_fr_auto(round(100 * x, 6)) + " %")


# --- Séries du développement -------------------------------------------------------------

def series_developpement(bougies: pd.DataFrame, regles: dict) -> pd.DataFrame:
    """Jours du début des données à la fin du développement : RV et clôture des jours valides."""
    d, c = regles["donnees"], regles["decoupage"]
    lignes = V.lignes_journalieres(bougies, regles, d["debut"], c["dev_fin"])
    G.refuser_si_test(lignes.index, "exploration")
    valide = lignes["valide"].astype(bool)
    return pd.DataFrame({"rv": lignes["rv"].where(valide), "cloture": lignes["cloture"].where(valide),
                         "valide": valide}, index=pd.DatetimeIndex(pd.to_datetime(list(lignes.index)), name="jour"))


def statistiques(serie: pd.DataFrame, regles: dict) -> dict:
    """Autocorrélations, ADF et asymétries, sur des séries du développement seulement."""
    G.refuser_si_test(serie.index, "statistiques exploratoires")
    e = regles["exploration"]
    log_rv = np.log(serie["rv"])
    autocorr = acf(log_rv.to_numpy(), nlags=e["acf_retards_max"], missing="conservative", fft=False)
    resultat = {
        "jours": int(len(serie)), "jours_valides": int(serie["valide"].sum()),
        "jours_non_valides_retires_adf": int((~serie["valide"]).sum()),
        "autocorrelation_log_rv": {str(k): float(autocorr[k]) for k in range(1, e["acf_retards_max"] + 1)},
        "asymetrie_rv": float(serie["rv"].dropna().skew()),
        "asymetrie_log_rv": float(log_rv.dropna().skew()),
        "adf": {},
    }
    series_adf = {"log_rv": log_rv, "log_cloture": np.log(serie["cloture"])}
    for nom in e["adf_series"]:
        stat, p, retards, n, critiques, _ = adfuller(series_adf[nom].dropna().to_numpy(), autolag=e["adf_autolag"],
                                                      result_object=False)
        resultat["adf"][nom] = {"statistique": float(stat), "p_valeur": float(p), "retards": int(retards),
                                "observations": int(n), "valeur_critique_5_pourcent": float(critiques["5%"])}
    return resultat


# --- Figures --------------------------------------------------------------------------

def _finir(fig, chemin: Path) -> None:
    fig.text(0.995, 0.005, MENTION, ha="right", va="bottom", fontsize=8, color="#555555")
    chemin.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(chemin, dpi=110, metadata={"Software": None})
    plt.close(fig)


def figure_rv(series: dict[str, pd.DataFrame], regles: dict, chemin: Path) -> None:
    annualisation = math.sqrt(regles["cible"]["annualisation_jours"])
    fig, axes = plt.subplots(len(series), 1, figsize=(10, 6.5), sharex=True)
    for ax, (actif, s) in zip(np.atleast_1d(axes), series.items()):
        G.refuser_si_test(s.index, "figure 1")
        ax.plot(s.index, s["rv"] * annualisation, color=COULEURS[actif], linewidth=0.7, label=NOMS[actif])
        for nom, p in regles["crises"].items():
            ax.axvspan(pd.Timestamp(p["debut"]), pd.Timestamp(p["fin"]) + pd.Timedelta(days=1), color="#999999", alpha=0.25,
                       label="Crises" if nom == next(iter(regles["crises"])) else None)
        ax.set_ylabel("RV annualisée")
        ax.yaxis.set_major_formatter(FORMAT_POURCENT)
        ax.legend(loc="upper right")
        ax.grid(alpha=0.3)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_xlabel("Date (jours UTC valides)")
    fig.suptitle("Volatilité réalisée annualisée, développement (crises en gris : Covid, Terra-Luna, FTX)")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    _finir(fig, chemin)


def figure_acf(stats: dict[str, dict], regles: dict, chemin: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.8))
    retards = np.arange(1, regles["exploration"]["acf_retards_max"] + 1)
    for actif, s in stats.items():
        valeurs = [s["autocorrelation_log_rv"][str(k)] for k in retards]
        ax.plot(retards, valeurs, marker="o", markersize=3, color=COULEURS[actif], label=NOMS[actif])
    n = min(s["jours_valides"] for s in stats.values())
    ax.axhspan(-1.96 / math.sqrt(n), 1.96 / math.sqrt(n), color="#999999", alpha=0.25, label="Zone « aucune autocorrélation » (95 %)")
    ax.set_xlabel("Retard (jours)")
    ax.set_ylabel("Autocorrélation de log(RV)")
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(FORMAT_FR)
    ax.legend()
    ax.grid(alpha=0.3)
    ax.set_title("Autocorrélation de log(RV) jusqu'à 60 jours, développement : regroupement de volatilité")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    _finir(fig, chemin)


def figure_histogrammes(series: dict[str, pd.DataFrame], chemin: Path) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5))
    for actif, s in series.items():
        G.refuser_si_test(s.index, "figure 3")
        rv = s["rv"].dropna()
        ax1.hist(rv, bins=60, density=True, alpha=0.5, color=COULEURS[actif], label=NOMS[actif])
        ax2.hist(np.log(rv), bins=60, density=True, alpha=0.5, color=COULEURS[actif], label=NOMS[actif])
    ax1.set_title("RV journalière : très asymétrique")
    ax1.set_xlabel("RV journalière")
    ax2.set_title("log(RV) : bien plus symétrique")
    ax2.set_xlabel("log(RV journalière)")
    for ax in (ax1, ax2):
        ax.set_ylabel("Densité")
        ax.xaxis.set_major_formatter(FORMAT_FR)
        ax.yaxis.set_major_formatter(FORMAT_FR)
        ax.legend()
        ax.grid(alpha=0.3)
    fig.suptitle("Pourquoi les modèles travaillent en log : histogrammes, jours valides du développement")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    _finir(fig, chemin)


# --- Rapport -----------------------------------------------------------------------------

def _sha256(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def rapport_markdown(rapport: dict) -> str:
    n = nombre_fr_auto
    e = rapport["exploration"]
    actifs = list(rapport["actifs"])
    lignes = [
        "# Analyse exploratoire",
        "",
        "Fichier généré par `src/exploration.py` à partir de `rapports/exploration.json` : ne pas le modifier à la main.",
        "",
        f"- Période : jours du {rapport['periode'][0]} au {rapport['periode'][1]}, **développement seulement** "
        "(le test final est aveugle : aucune valeur n'en est calculée ici).",
        "- Seuls les jours valides sont utilisés ; les jours non valides sont laissés vides pour l'autocorrélation "
        "et retirés pour le test ADF (limite écrite dans les règles).",
        f"- Figures : `figures/{FIGURES['rv']}`, `figures/{FIGURES['acf']}`, `figures/{FIGURES['histogrammes']}`.",
        "",
        "## Comptages",
        "",
        "| Actif | Jours | Jours valides | Jours non valides (retirés pour l'ADF) |",
        "|---|---:|---:|---:|",
    ]
    for a in actifs:
        s = rapport["actifs"][a]
        lignes.append(f"| {a} | {n(s['jours'], 0)} | {n(s['jours_valides'], 0)} | {n(s['jours_non_valides_retires_adf'], 0)} |")

    lignes += ["", "## Autocorrélation de log(RV)", "",
               "| Actif | " + " | ".join(f"{k} jour{'s' if int(k) > 1 else ''}" for k in e["acf_retards_rapportes"]) + " |",
               "|---|" + "---:|" * len(e["acf_retards_rapportes"])]
    for a in actifs:
        ac = rapport["actifs"][a]["autocorrelation_log_rv"]
        lignes.append(f"| {a} | " + " | ".join(n(ac[str(k)], 2) for k in e["acf_retards_rapportes"]) + " |")
    seuil = rapport["seuil_autocorrelation_95"]
    plus_long = str(max(e["acf_retards_rapportes"]))
    toutes_hautes = all(rapport["actifs"][a]["autocorrelation_log_rv"][plus_long] > seuil for a in actifs)
    lignes += ["", ("Interprétation : l'autocorrélation reste nettement au-dessus de la zone « aucune autocorrélation » "
                    f"(± {n(seuil, 3)}) même à {plus_long} jours. Une journée agitée est suivie de journées agitées : "
                    "c'est le regroupement de volatilité, que les modèles HAR et GARCH exploitent.")
               if toutes_hautes else
               (f"Interprétation : à {plus_long} jours, l'autocorrélation n'est plus nettement au-dessus de la zone "
                f"« aucune autocorrélation » (± {n(seuil, 3)}) pour au moins un actif : la mémoire de la volatilité s'efface.")]
    pic = all(rapport["actifs"][a]["autocorrelation_log_rv"]["7"] > (rapport["actifs"][a]["autocorrelation_log_rv"]["6"]
              + rapport["actifs"][a]["autocorrelation_log_rv"]["8"]) / 2 for a in actifs)
    if pic:
        lignes += ["", "Pic tous les 7 jours (voir la figure 2) : l'autocorrélation au retard 7 dépasse la moyenne des retards 6 "
                   "et 8 pour les deux actifs. La volatilité semble dépendre du jour de la semaine, ce qui "
                   "justifie la variable « jour de la semaine »."]

    lignes += ["", "## Test ADF (racine unitaire, retards choisis par AIC)", "",
               "| Actif | Série | Statistique | Valeur critique à 5 % | p-valeur | Retards | Observations |",
               "|---|---|---:|---:|---:|---:|---:|"]
    libelles = {"log_rv": "log(RV)", "log_cloture": "log(clôture)"}
    for a in actifs:
        for nom, t in rapport["actifs"][a]["adf"].items():
            p = t["p_valeur"]
            lignes.append(f"| {a} | {libelles[nom]} | {n(t['statistique'], 2)} | {n(t['valeur_critique_5_pourcent'], 2)} | "
                          f"{n(p, 4) if p >= 0.0001 else '< 0,0001'} | {n(t['retards'], 0)} | {n(t['observations'], 0)} |")
    lignes.append("")
    for nom in e["adf_series"]:
        rejet = [a for a in actifs if rapport["actifs"][a]["adf"][nom]["p_valeur"] < 0.05]
        if len(rejet) == len(actifs):
            texte = "p-valeur sous 5 % pour les deux actifs : on rejette la racine unitaire, la série revient vers sa moyenne (stationnaire)."
        elif not rejet:
            texte = "p-valeur au-dessus de 5 % pour les deux actifs : on ne peut pas rejeter la racine unitaire, la série dérive (non stationnaire)."
        else:
            texte = f"résultat partagé : racine unitaire rejetée seulement pour {', '.join(rejet)}."
        lignes.append(f"- Interprétation pour {libelles[nom]} : {texte}")
    lignes.append("- Conséquence : on modélise log(RV), et non le prix ; la cible est stable dans le temps, le prix ne l'est pas.")

    lignes += ["", "## Asymétrie", "", "| Actif | Asymétrie de RV | Asymétrie de log(RV) |", "|---|---:|---:|"]
    for a in actifs:
        s = rapport["actifs"][a]
        lignes.append(f"| {a} | {n(s['asymetrie_rv'], 2)} | {n(s['asymetrie_log_rv'], 2)} |")
    plus_sym = all(abs(rapport["actifs"][a]["asymetrie_log_rv"]) < abs(rapport["actifs"][a]["asymetrie_rv"]) for a in actifs)
    lignes += ["", ("Interprétation : la RV a une longue queue à droite (quelques journées extrêmes) ; en log, la "
                    "distribution est bien plus symétrique. C'est pourquoi les modèles prévoient log(RV)."
                    if plus_sym else "Interprétation : le passage au log ne rend pas la distribution plus symétrique pour tous les actifs.")]

    lignes += ["", "## Règle de secours (comptages)", "",
               "| Actif | Jours remplacés : préchauffage | Jours remplacés : développement | Exemples gardés du développement | "
               "… dont la fenêtre de 30 jours contient un jour remplacé |", "|---|---:|---:|---:|---:|"]
    for a in actifs:
        c = rapport["secours"][a]
        lignes.append(f"| {a} | {n(c['jours_remplaces_prechauffage'], 0)} | {n(c['jours_remplaces_developpement'], 0)} | "
                      f"{n(c['exemples_gardes_developpement'], 0)} | {n(c['exemples_fenetre_avec_jour_remplace'], 0)} |")
    lignes += ["", "Limite : le rendement d'un jour remplacé est nul, et celui du lendemain porte sur deux jours."]
    return "\n".join(lignes) + "\n"


def executer(regles: dict, dossier_traite: Path) -> dict:
    d, c = regles["donnees"], regles["decoupage"]
    series = {a: series_developpement(V.lire_bougies(dossier_traite / f"{a}_5m.parquet"), regles) for a in d["actifs"]}
    stats = {a: statistiques(s, regles) for a, s in series.items()}
    manifeste_variables = json.loads((C.RACINE / regles["variables"]["sorties"]["manifeste"]).read_text(encoding="utf-8"))
    secours = {}
    for a in d["actifs"]:
        cp = manifeste_variables["comptages_par_actif"][a]
        secours[a] = {"jours_remplaces_prechauffage": cp["jours_remplaces_par_date_du_jour"]["prechauffage"],
                      "jours_remplaces_developpement": cp["jours_remplaces_par_date_du_jour"]["developpement"],
                      "exemples_gardes_developpement": cp["exemples"]["developpement"]["gardes"],
                      "exemples_fenetre_avec_jour_remplace": cp["exemples"]["developpement"]["fenetre_30_jours_avec_jour_remplace"]}
    n_min = min(s["jours_valides"] for s in stats.values())
    rapport = {
        "periode": [str(d["debut"]), str(c["dev_fin"])],
        "exploration": regles["exploration"],
        "actifs": stats,
        "seuil_autocorrelation_95": 1.96 / math.sqrt(n_min),
        "secours": secours,
        "figures": {k: f"figures/{v}" for k, v in FIGURES.items()},
        "depend_de": {"manifeste_traite_sha256": _sha256(C.MANIFESTE_TRAITE), "regles_sha256": _sha256(R.CHEMIN_REGLES),
                      "manifeste_variables_empreinte_contenu": manifeste_variables["empreinte_contenu_sha256"]},
    }
    figure_rv(series, regles, DOSSIER_FIGURES / FIGURES["rv"])
    figure_acf(stats, regles, DOSSIER_FIGURES / FIGURES["acf"])
    figure_histogrammes(series, DOSSIER_FIGURES / FIGURES["histogrammes"])
    C.ecrire_texte(CHEMIN_JSON, C.texte_json(rapport))
    C.ecrire_texte(CHEMIN_MD, rapport_markdown(rapport))
    return rapport


def main() -> int:
    C.proteger_sortie()
    debut = time.perf_counter()
    regles = R.charger_regles()
    try:
        rapport = executer(regles, C.DOSSIER_TRAITE)
    except G.ErreurTestAveugle as erreur:
        print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1
    print(f"Période : {rapport['periode'][0]} -> {rapport['periode'][1]} (développement seulement)")
    print(f"Rapports : {C.chemin_relatif(CHEMIN_JSON)}, {C.chemin_relatif(CHEMIN_MD)} ; figures dans figures/")
    print(f"Durée : {C.nombre_fr(time.perf_counter() - debut, 1)} s | mémoire maximale du processus : "
          f"{C.nombre_fr(C.memoire_max_mo(), 1)} Mo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
