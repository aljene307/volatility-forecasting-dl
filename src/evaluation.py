"""Fonctions d'évaluation (règles : config/regles.toml, sections evaluation et cible ; docs/REGLES.md, section 12).

- QLIKE de Patton sur la variance : RV²/h − ln(RV²/h) − 1 (0 si et seulement si h = RV²).
- RMSE et MAE sur RV, avec σ̂ = racine(variance prévue).
- Diebold-Mariano : d = perte(modèle) − perte(référence), variance de long terme de Newey-West (noyau de
  Bartlett, retards floor(4·(T/100)^(2/9))), correction de Harvey-Leybourne-Newbold, loi de Student à T − 1
  degrés de liberté, test bilatéral.
- Bootstrap par blocs mobiles de la moyenne (1000 tirages, blocs de 20 jours, graine 42), intervalle par percentiles.

Ces fonctions ne regardent aucune date : l'appelant passe d'abord par la garde du test aveugle.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))

import regles as R  # noqa: E402


def variance_depuis_log(y, s2: float) -> np.ndarray:
    """Variance prévue pour un modèle en log : exp(2y + 2·s²) (toujours strictement positive)."""
    if s2 < 0:
        raise ValueError(f"s² doit être positif ou nul, reçu {s2}")
    return np.exp(2 * np.asarray(y, dtype="float64") + 2 * s2)


def qlike(rv, h) -> np.ndarray:
    """Perte QLIKE de Patton, jour par jour : RV²/h − ln(RV²/h) − 1."""
    rv, h = np.asarray(rv, dtype="float64"), np.asarray(h, dtype="float64")
    if not (h > 0).all():
        raise ValueError("QLIKE demande des variances prévues strictement positives.")
    rapport = rv ** 2 / h
    return rapport - np.log(rapport) - 1


def rmse(rv, sigma) -> float:
    return float(np.sqrt(np.mean((np.asarray(rv) - np.asarray(sigma)) ** 2)))


def mae(rv, sigma) -> float:
    return float(np.mean(np.abs(np.asarray(rv) - np.asarray(sigma))))


def variance_long_terme(d: np.ndarray, retards: int) -> float:
    """Variance de long terme de Newey-West (noyau de Bartlett) d'une série d."""
    e = d - d.mean()
    t = len(e)
    gamma = [float(e @ e) / t] + [float(e[k:] @ e[:-k]) / t for k in range(1, retards + 1)]
    return gamma[0] + 2 * sum((1 - k / (retards + 1)) * gamma[k] for k in range(1, retards + 1))


def diebold_mariano(perte_modele, perte_reference, retards: int | None = None) -> dict:
    """Test de Diebold-Mariano, horizon 1, avec la correction de Harvey-Leybourne-Newbold.

    Moyenne de d négative : le modèle a une perte plus faible que la référence.
    """
    d = np.asarray(perte_modele, dtype="float64") - np.asarray(perte_reference, dtype="float64")
    t = len(d)
    retards = R.retards_hac(t) if retards is None else retards
    lrv = variance_long_terme(d, retards)
    if not lrv > 0:
        raise ValueError(f"Variance de long terme non positive ({lrv}) : test impossible.")
    stat_dm = d.mean() / math.sqrt(lrv / t)
    h = 1
    stat = stat_dm * math.sqrt((t + 1 - 2 * h + h * (h - 1) / t) / t)
    p = 2 * stats.t.sf(abs(stat), df=t - 1)
    return {"moyenne_difference": float(d.mean()), "statistique": float(stat), "p_valeur": float(p), "jours": t,
            "retards_hac": retards, "sens": "modèle meilleur" if d.mean() < 0 else "référence meilleure"}


def holm(p_valeurs: dict[str, float]) -> dict[str, float]:
    """P-valeurs ajustées par la méthode de Holm (section 13 des règles).

    Rangées de la plus petite à la plus grande, la k-ième (k = 1 à m) est multipliée par (m − k + 1) ;
    on garde la plus grande valeur rencontrée jusque-là (ordre conservé), plafonnée à 1.
    """
    m = len(p_valeurs)
    ajustees, maximum = {}, 0.0
    for k, (nom, p) in enumerate(sorted(p_valeurs.items(), key=lambda x: x[1])):
        maximum = max(maximum, min(1.0, (m - k) * p))
        ajustees[nom] = maximum
    return {nom: ajustees[nom] for nom in p_valeurs}


def indices_blocs(n: int, tirages: int, taille_bloc: int, graine: int) -> np.ndarray:
    """Indices des rééchantillonnages par blocs mobiles : (tirages, n), blocs de jours consécutifs à débuts tirés au hasard."""
    if n < taille_bloc:
        raise ValueError(f"Série trop courte ({n}) pour des blocs de {taille_bloc} jours.")
    rng = np.random.default_rng(graine)
    blocs = math.ceil(n / taille_bloc)
    debuts = rng.integers(0, n - taille_bloc + 1, size=(tirages, blocs))
    return (debuts[:, :, None] + np.arange(taille_bloc)).reshape(tirages, -1)[:, :n]


def bootstrap_statistique(series: list, statistique, regles: dict) -> dict:
    """Intervalle (percentiles) d'une statistique de une ou plusieurs séries de même longueur, rééchantillonnées avec
    les MÊMES indices de blocs (ce qui garde le lien jour par jour, par exemple pour une différence de Sharpe)."""
    b = regles["evaluation"]["bootstrap"]
    xs = [np.asarray(s, dtype="float64") for s in series]
    indices = indices_blocs(len(xs[0]), b["tirages"], b["taille_bloc_jours"], b["graine"])
    valeurs = np.array([statistique(*[x[i] for x in xs]) for i in indices])
    alpha = (1 - b["niveau_confiance"]) / 2
    return {"valeur": float(statistique(*xs)), "bas": float(np.quantile(valeurs, alpha)), "haut": float(np.quantile(valeurs, 1 - alpha))}


def kupiec(depassements: int, jours: int, p: float) -> dict:
    """Test de Kupiec (couverture inconditionnelle) : LR = −2 ln[(1−p)^(n−x) p^x / ((1−x/n)^(n−x) (x/n)^x)],
    loi du khi-deux à 1 degré de liberté."""
    x, n = int(depassements), int(jours)
    if not 0 <= x <= n or n == 0:
        raise ValueError(f"Comptages incohérents : {x} dépassements sur {n} jours.")
    taux = x / n

    def log_vraisemblance(q: float) -> float:
        return (n - x) * (math.log(1 - q) if n > x else 0.0) + (x * math.log(q) if x > 0 else 0.0)

    lr = -2 * (log_vraisemblance(p) - log_vraisemblance(taux))
    return {"depassements": x, "jours": n, "taux": taux, "attendu": p, "statistique": float(max(lr, 0.0)),
            "p_valeur": float(stats.chi2.sf(max(lr, 0.0), df=1))}


def bootstrap_moyenne(valeurs, tirages: int, taille_bloc: int, graine: int, niveau: float = 0.95) -> dict:
    """Intervalle de confiance de la moyenne par bootstrap à blocs mobiles (percentiles)."""
    x = np.asarray(valeurs, dtype="float64")
    indices = indices_blocs(len(x), tirages, taille_bloc, graine)
    moyennes = x[indices].mean(axis=1)
    alpha = (1 - niveau) / 2
    return {"moyenne": float(x.mean()), "bas": float(np.quantile(moyennes, alpha)),
            "haut": float(np.quantile(moyennes, 1 - alpha))}


def bootstrap_selon_regles(valeurs, regles: dict) -> dict:
    b = regles["evaluation"]["bootstrap"]
    return bootstrap_moyenne(valeurs, b["tirages"], b["taille_bloc_jours"], b["graine"], b["niveau_confiance"])
