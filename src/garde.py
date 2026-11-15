"""Garde du test aveugle : la seule porte par laquelle passe tout affichage, toute statistique et toute figure.

Règle (précision du 2026-11-15, config/regles.toml, section test_aveugle) : tant que le test final
n'a pas été officiellement ouvert, toute valeur dont la date de cible est postérieure ou égale au
début du test final est refusée. Seuls les comptages sont permis (fonction `compter`).

Cette garde n'a AUCUNE option de contournement : pas de paramètre, pas de variable d'environnement,
pas de réglage. Le mécanisme d'ouverture du test sera construit à l'étape du test final.
Un test (tests/test_variables.py) vérifie cette absence d'option, avec un témoin.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import regles as R  # noqa: E402


class ErreurTestAveugle(RuntimeError):
    """Tentative de statistique, de figure ou d'affichage sur le test final avant son ouverture."""


def _debut_test() -> dt.date:
    return R.charger_regles()["decoupage"]["test_debut"]


def _en_dates(dates_cible: Iterable) -> list[dt.date]:
    serie = pd.Series(list(dates_cible))
    if serie.empty:
        return []
    return [pd.Timestamp(x).date() for x in serie]


def refuser_si_test(dates_cible: Iterable, usage: str) -> None:
    """Lève ErreurTestAveugle si une date de cible appartient au test final.

    `dates_cible` : les dates de CIBLE des valeurs qui vont servir à `usage`
    (une statistique, une figure, un affichage). `usage` ne sert qu'au message.
    """
    debut = _debut_test()
    dates = _en_dates(dates_cible)
    interdites = [d for d in dates if d >= debut]
    if interdites:
        raise ErreurTestAveugle(
            f"Refusé ({usage}) : {len(interdites)} valeur(s) ont une date de cible dans le test final "
            f"(à partir du {debut}, première : {min(interdites)}). Le test final est aveugle : "
            "seuls les comptages sont permis tant qu'il n'a pas été officiellement ouvert.")


def compter(dates_cible: Iterable) -> int:
    """Comptage : toujours permis, même sur le test final (aucune valeur n'est lue)."""
    return len(_en_dates(dates_cible))
