"""Reprise après interruption (règles : config/regles.toml, section entrainement.reprise).

- Le calcul est découpé en unités indépendantes, identifiées par un texte, par exemple
  "BTCUSDT|LSTM|pli 3|combinaison 7|graine 2".
- La graine d'une unité est DÉRIVÉE de son identifiant (SHA-256), jamais de l'ordre d'exécution :
  une relance donne exactement les mêmes résultats, dans n'importe quel ordre.
- Chaque unité est écrite dans son propre fichier dès qu'elle est finie (fichier temporaire, puis
  renommage) ; le fichier contient l'empreinte de son résultat, ce qui permet de vérifier qu'il est intact.
- À la relance, les unités terminées et intactes sont sautées.
- Pendant le calcul, la mise en veille de Windows est empêchée, puis rétablie à la fin, même en cas d'erreur.

Ce module donne le principe ; le calcul réel l'utilisera à l'étape d'entraînement.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def graine_unite(identifiant: str) -> int:
    """Graine dérivée de l'identifiant : les 4 premiers octets de son SHA-256 (entier de 0 à 2³¹ − 1)."""
    return int.from_bytes(hashlib.sha256(identifiant.encode("utf-8")).digest()[:4], "big") & 0x7FFFFFFF


def nom_fichier(identifiant: str) -> str:
    """Nom de fichier sûr et unique pour une unité (empreinte de l'identifiant)."""
    return hashlib.sha256(identifiant.encode("utf-8")).hexdigest()[:24] + ".json"


def _empreinte(resultat) -> str:
    return hashlib.sha256(json.dumps(resultat, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def lire_unite(dossier: Path, identifiant: str):
    """Résultat d'une unité terminée et intacte, ou None (absente, abîmée, ou d'une autre unité)."""
    chemin = dossier / nom_fichier(identifiant)
    try:
        contenu = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if contenu.get("identifiant") != identifiant or contenu.get("empreinte") != _empreinte(contenu.get("resultat")):
        return None
    return contenu["resultat"]


def ecrire_unite(dossier: Path, identifiant: str, graine: int, resultat) -> None:
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / nom_fichier(identifiant)
    temporaire = chemin.with_name(chemin.name + ".part")
    texte = json.dumps({"identifiant": identifiant, "graine": graine, "resultat": resultat, "empreinte": _empreinte(resultat)},
                       sort_keys=True, ensure_ascii=False, indent=1) + "\n"
    with open(temporaire, "w", encoding="utf-8", newline="\n") as f:
        f.write(texte)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporaire, chemin)


@contextlib.contextmanager
def sans_mise_en_veille() -> Iterator[None]:
    """Empêche la mise en veille de Windows pendant le bloc, puis rétablit le comportement normal."""
    windows = sys.platform == "win32"
    if windows:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    try:
        yield
    finally:
        if windows:
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)


def executer(unites: list[str], calcul: Callable[[str, int], object], dossier: Path,
             graine: Callable[[str], int] = graine_unite,
             alimentation: Callable[[], dict] | None = None) -> dict:
    """Calcule les unités manquantes ou abîmées, dans l'ordre donné ; renvoie {calculées, sautées}.

    `calcul(identifiant, graine)` renvoie un résultat sérialisable en JSON.
    Avant chaque unité, l'alimentation est vérifiée : sur batterie, le calcul refuse de démarrer, ou s'arrête
    proprement après l'unité en cours (ErreurAlimentation) ; une relance reprend les unités manquantes.
    `graine` et `alimentation` ne servent qu'aux témoins (graine par ordre, état d'alimentation simulé).
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import commun as C
    lire_etat = alimentation or C.etat_alimentation
    calculees = sautees = 0
    C.verifier_secteur(lire_etat(), "démarrage")
    with sans_mise_en_veille():
        for identifiant in unites:
            if lire_unite(dossier, identifiant) is not None:
                sautees += 1
                continue
            C.verifier_secteur(lire_etat(), f"arrêt propre après {calculees} unité(s) calculée(s)")
            g = graine(identifiant)
            ecrire_unite(dossier, identifiant, g, calcul(identifiant, g))
            calculees += 1
    return {"calculees": calculees, "sautees": sautees}
