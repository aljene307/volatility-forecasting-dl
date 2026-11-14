"""Outils communs aux scripts de données : chemins, mois couverts, JSON déterministe, mémoire."""

from __future__ import annotations

import ctypes
import datetime as dt
import json
import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_DATA = RACINE / "data"
DOSSIER_BRUT = DOSSIER_DATA / "raw"
DOSSIER_REJETS = DOSSIER_BRUT / "_rejets"
DOSSIER_TRAITE = DOSSIER_DATA / "processed"
MANIFESTE_BRUT = DOSSIER_DATA / "manifeste_brut.json"
MANIFESTE_TRAITE = DOSSIER_DATA / "manifeste_traite.json"
DOSSIER_RAPPORTS = RACINE / "rapports"


def proteger_sortie() -> None:
    """Sous Windows, un caractère non affichable devient "?" au lieu de faire planter le script."""
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(errors="replace")


def mois_couverts(debut: dt.date, fin: dt.date) -> list[tuple[int, int]]:
    """Liste des (année, mois) du mois de `debut` au mois de `fin`, inclus."""
    mois = []
    annee, m = debut.year, debut.month
    while (annee, m) <= (fin.year, fin.month):
        mois.append((annee, m))
        annee, m = (annee + 1, 1) if m == 12 else (annee, m + 1)
    return mois


def nom_fichier_klines(actif: str, intervalle: str, annee: int, mois: int) -> str:
    return f"{actif}-{intervalle}-{annee:04d}-{mois:02d}.zip"


def texte_json(objet) -> str:
    """JSON déterministe : clés triées, indentation fixe, UTF-8 lisible, fin de ligne finale."""
    return json.dumps(objet, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def ecrire_texte(chemin: Path, texte: str) -> None:
    """Écrit en UTF-8 sans BOM, fins de ligne LF, via un fichier temporaire renommé à la fin."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_name(chemin.name + ".part")
    with open(temporaire, "w", encoding="utf-8", newline="\n") as f:
        f.write(texte)
    os.replace(temporaire, chemin)


def chemin_relatif(chemin: Path) -> str:
    """Chemin relatif à la racine du projet, avec des barres obliques (jamais de chemin absolu)."""
    return chemin.resolve().relative_to(RACINE).as_posix()


def memoire_max_mo() -> float:
    """Mémoire maximale (pic de l'ensemble de travail) du processus Python courant, en Mo.

    Mesurée de l'intérieur : c'est le vrai interpréteur, pas le lanceur de .venv.
    """
    if sys.platform == "win32":
        class Compteurs(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        compteurs = Compteurs()
        compteurs.cb = ctypes.sizeof(Compteurs)
        noyau, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
        noyau.GetCurrentProcess.restype = ctypes.c_void_p  # sinon le handle 64 bits est tronqué
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Compteurs), ctypes.c_ulong]
        psapi.GetProcessMemoryInfo.restype = ctypes.c_int
        if not psapi.GetProcessMemoryInfo(noyau.GetCurrentProcess(), ctypes.byref(compteurs), compteurs.cb):
            raise OSError("GetProcessMemoryInfo a échoué")
        return compteurs.PeakWorkingSetSize / 2**20
    import resource  # Linux : ru_maxrss est en kilo-octets
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def nombre_fr(x: float, decimales: int = 0) -> str:
    """Format français : espace pour les milliers, virgule pour les décimales."""
    texte = f"{x:,.{decimales}f}"
    return texte.replace(",", " ").replace(".", ",")
