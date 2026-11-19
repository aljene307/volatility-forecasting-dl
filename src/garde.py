"""Garde du test aveugle : la seule porte par laquelle passe tout affichage, toute statistique et toute figure.

Règle (précision du 2026-11-15, config/regles.toml, section test_aveugle) : tant que le test final
n'a pas été officiellement ouvert, toute valeur dont la date de cible est postérieure ou égale au
début du test final est refusée. Seuls les comptages sont permis (fonction `compter`).

Cette garde n'a AUCUNE option de contournement : pas de paramètre, pas de variable d'environnement,
pas de réglage. Un test (tests/test_variables.py) vérifie cette absence d'option, avec un témoin.

Ouverture (précision du 2026-11-19, section 17 des règles) : la seule porte est `_ouverture_officielle`, qui
ne s'ouvre que si elle est appelée par la fonction `_chaine_sur_le_test_ouvert` du fichier src/ouvrir_test.py,
et seulement pendant ce bloc. Partout ailleurs, la garde reste fermée (tests/test_ouvrir_test.py).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import regles as R  # noqa: E402

_PORTE = {"ouverte": False}
_FICHIER_AUTORISE = Path(__file__).resolve().parent / "ouvrir_test.py"
_FONCTION_AUTORISEE = "_chaine_sur_le_test_ouvert"


class ErreurTestAveugle(RuntimeError):
    """Tentative de statistique, de figure ou d'affichage sur le test final avant son ouverture."""


@contextmanager
def _ouverture_officielle():
    """Lève la garde pendant le bloc, si et seulement si l'appelant est la fonction prévue de src/ouvrir_test.py."""
    appelant = sys._getframe(1)
    while appelant is not None and Path(appelant.f_code.co_filename).name == "contextlib.py":
        appelant = appelant.f_back
    if (appelant is None or Path(appelant.f_code.co_filename).resolve() != _FICHIER_AUTORISE
            or appelant.f_code.co_name != _FONCTION_AUTORISEE):
        raise ErreurTestAveugle("Ouverture refusée : seul src/ouvrir_test.py (fonction _chaine_sur_le_test_ouvert) peut ouvrir le test final.")
    _PORTE["ouverte"] = True
    try:
        yield
    finally:
        _PORTE["ouverte"] = False


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
    if _PORTE["ouverte"]:
        return
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
