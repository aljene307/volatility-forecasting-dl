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


def memoire_libre_go() -> float:
    """Mémoire physique libre (disponible) de la machine, en Go."""
    if sys.platform == "win32":
        class Etat(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        etat = Etat()
        etat.dwLength = ctypes.sizeof(Etat)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(etat)):
            raise OSError("GlobalMemoryStatusEx a échoué")
        return etat.ullAvailPhys / 2**30
    with open("/proc/meminfo", encoding="ascii") as f:  # Linux
        for ligne in f:
            if ligne.startswith("MemAvailable:"):
                return int(ligne.split()[1]) / 2**20
    raise OSError("Mémoire libre introuvable")


class ErreurMemoire(RuntimeError):
    """Mémoire libre insuffisante pour démarrer un script lourd."""


def verifier_memoire_libre(regles: dict, libre_go: float | None = None) -> float:
    """Un script lourd refuse de démarrer si la mémoire libre est sous projet.seuil_memoire_libre_go.

    `libre_go` : mémoire libre déjà mesurée (sinon elle est mesurée ici). Renvoie la mémoire libre.
    """
    seuil = regles["projet"]["seuil_memoire_libre_go"]
    if not isinstance(seuil, (int, float)) or isinstance(seuil, bool):
        raise ErreurMemoire(f"Seuil de mémoire libre pas encore fixé ({seuil!r}) : démarrage refusé.")
    libre = memoire_libre_go() if libre_go is None else libre_go
    if libre < seuil:
        raise ErreurMemoire(
            f"Démarrage refusé : {nombre_fr(libre, 2)} Go de mémoire libre, il en faut au moins {nombre_fr(seuil, 1)} Go "
            "(projet.seuil_memoire_libre_go). Fermez des applications (par exemple des onglets de Chrome), puis relancez.")
    return libre


MODES_WINDOWS = {"ded574b5-45a0-4f42-8737-46345c09c238": "Performances optimales",
                 "00000000-0000-0000-0000-000000000000": "Équilibré (recommandé)",
                 "961cc777-2547-4f9d-8174-7d86181b8a7a": "Économie d'énergie"}


def etat_alimentation() -> dict:
    """État de l'alimentation : {"secteur": True/False/None, "batterie_pourcent": int|None, "mode": texte|None}."""
    if sys.platform != "win32":
        return {"secteur": None, "batterie_pourcent": None, "mode": None}

    class Etat(ctypes.Structure):
        _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte), ("BatteryLifePercent", ctypes.c_ubyte),
                    ("SystemStatusFlag", ctypes.c_ubyte), ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]
    etat = Etat()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(etat)):
        raise OSError("GetSystemPowerStatus a échoué")
    mode = None
    try:
        import uuid
        guid = (ctypes.c_ubyte * 16)()
        if ctypes.windll.powrprof.PowerGetEffectiveOverlayScheme(ctypes.byref(guid)) == 0:
            identifiant = str(uuid.UUID(bytes_le=bytes(guid)))
            mode = MODES_WINDOWS.get(identifiant, identifiant)
    except (AttributeError, OSError):
        pass
    return {"secteur": {1: True, 0: False}.get(etat.ACLineStatus),
            "batterie_pourcent": None if etat.BatteryLifePercent == 255 else int(etat.BatteryLifePercent), "mode": mode}


class ErreurAlimentation(RuntimeError):
    """Calcul refusé ou arrêté parce que le PC est sur batterie."""


def verifier_secteur(etat: dict | None = None, contexte: str = "démarrage") -> dict:
    """Refuse de calculer sur batterie (temps fiables, pas de calcul coupé par une batterie vide).

    `etat` : état déjà lu (sinon il est lu ici). Un état inconnu (machine sans batterie) est accepté.
    """
    etat = etat_alimentation() if etat is None else etat
    if etat["secteur"] is False:
        pourcent = "" if etat.get("batterie_pourcent") is None else f" (batterie à {etat['batterie_pourcent']} %)"
        raise ErreurAlimentation(
            f"Calcul refusé ({contexte}) : le PC est sur batterie{pourcent}. Branchez-le sur secteur, puis relancez ; "
            "les unités déjà terminées seront reprises.")
    return etat


def nombre_fr(x: float, decimales: int = 0) -> str:
    """Format français : espace pour les milliers, virgule pour les décimales."""
    texte = f"{x:,.{decimales}f}"
    return texte.replace(",", " ").replace(".", ",")
