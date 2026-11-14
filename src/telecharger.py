"""Téléchargement des bougies mensuelles de Binance spot, avec vérification SHA-256.

Les actifs, l'intervalle et les dates sont lus dans config/regles.toml.
Pour chaque mois : le zip et son fichier .CHECKSUM publié par Binance. Le zip est écrit
dans un fichier .part, renommé seulement si son SHA-256 est correct ; sinon il est déplacé
dans data/raw/_rejets/ et signalé. Relancer le script est sans risque : un fichier présent
et correct n'est pas retéléchargé (aucune requête réseau).

Usage : .venv\\Scripts\\python src/telecharger.py
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import commun as C  # noqa: E402
import regles as R  # noqa: E402

DELAI_ATTENTE_S = 60          # timeout de chaque requête
NOUVELLES_TENTATIVES = 3      # au maximum, après le premier essai
PAUSE_ENTRE_FICHIERS_S = 0.3  # politesse envers le serveur

Recuperateur = Callable[[str], bytes]


class ErreurTelechargement(RuntimeError):
    pass


def recuperer_http(url: str) -> bytes:
    # identification par défaut de urllib (Python-urllib/3.11)
    with urllib.request.urlopen(url, timeout=DELAI_ATTENTE_S) as reponse:
        return reponse.read()


def avec_tentatives(recuperer: Recuperateur, url: str, attente_s: float = 2.0) -> bytes:
    """Un essai, puis au plus NOUVELLES_TENTATIVES, avec une attente qui double à chaque fois."""
    derniere_erreur = None
    for essai in range(1 + NOUVELLES_TENTATIVES):
        try:
            return recuperer(url)
        except urllib.error.HTTPError as erreur:
            if erreur.code == 404:
                raise ErreurTelechargement(f"Fichier absent du serveur (404) : {url}") from None
            derniere_erreur = erreur
        except (urllib.error.URLError, TimeoutError, OSError) as erreur:
            derniere_erreur = erreur
        if essai < NOUVELLES_TENTATIVES:
            time.sleep(attente_s * 2 ** essai)
    raise ErreurTelechargement(f"Échec après {1 + NOUVELLES_TENTATIVES} essais : {url} ({derniere_erreur})")


def sha256_fichier(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def lire_checksum(texte: str, nom_attendu: str) -> str:
    """Le fichier .CHECKSUM contient « <sha256>  <nom du fichier> »."""
    morceaux = texte.split()
    if len(morceaux) != 2 or len(morceaux[0]) != 64 or morceaux[1] != nom_attendu:
        raise ErreurTelechargement(f"Fichier CHECKSUM illisible pour {nom_attendu} : {texte[:120]!r}")
    empreinte = morceaux[0].lower()
    int(empreinte, 16)  # lève une erreur si ce n'est pas de l'hexadécimal
    return empreinte


def deplacer_vers_rejets(source: Path, nom: str, rejets: Path) -> Path:
    """Déplace (sans supprimer) un fichier refusé ; ajoute un numéro si le nom existe déjà."""
    rejets.mkdir(parents=True, exist_ok=True)
    cible = rejets / nom
    numero = 1
    while cible.exists():
        cible = rejets / f"{nom}.{numero}"
        numero += 1
    shutil.move(str(source), str(cible))
    return cible


def traiter_fichier(nom: str, url_zip: str, dossier: Path, recuperer: Recuperateur) -> tuple[str, int]:
    """Renvoie (statut, nombre de requêtes réseau). Statuts : deja_present, telecharge, rejete."""
    rejets = dossier / "_rejets"
    zip_final = dossier / nom
    checksum_final = dossier / f"{nom}.CHECKSUM"
    requetes = 0

    # 1. Empreinte attendue : fichier .CHECKSUM local, sinon téléchargé
    if not checksum_final.exists():
        texte = avec_tentatives(recuperer, url_zip + ".CHECKSUM").decode("ascii", errors="replace")
        requetes += 1
        lire_checksum(texte, nom)  # vérifie le format avant d'enregistrer
        C.ecrire_texte(checksum_final, texte if texte.endswith("\n") else texte + "\n")
    attendu = lire_checksum(checksum_final.read_text(encoding="ascii"), nom)

    # 2. Fichier déjà présent : on le garde s'il est correct, sinon on le met de côté
    if zip_final.exists():
        if sha256_fichier(zip_final) == attendu:
            return "deja_present", requetes
        cible = deplacer_vers_rejets(zip_final, nom, rejets)
        print(f"  ATTENTION : {nom} présent mais empreinte fausse, déplacé dans _rejets ({cible.name})")

    # 3. Téléchargement dans un .part, vérifié, puis renommé
    partiel = dossier / f"{nom}.part"
    partiel.write_bytes(avec_tentatives(recuperer, url_zip))
    requetes += 1
    obtenu = sha256_fichier(partiel)
    if obtenu != attendu:
        cible = deplacer_vers_rejets(partiel, nom, rejets)
        print(f"  REJET : {nom} empreinte {obtenu[:12]}… au lieu de {attendu[:12]}… ; déplacé dans _rejets ({cible.name})")
        return "rejete", requetes
    os.replace(partiel, zip_final)
    return "telecharge", requetes


def fichiers_prevus(regles: dict) -> list[tuple[str, str]]:
    """(nom du zip, adresse) pour chaque actif et chaque mois des règles."""
    d = regles["donnees"]
    base = d["url_source"].rstrip("/") + "/data/spot/monthly/klines"
    prevus = []
    for actif in d["actifs"]:
        for annee, mois in C.mois_couverts(d["debut"], d["fin"]):
            nom = C.nom_fichier_klines(actif, d["intervalle"], annee, mois)
            prevus.append((nom, f"{base}/{actif}/{d['intervalle']}/{nom}"))
    return prevus


def manifeste(dossier: Path, noms: list[str], source: str) -> dict:
    """Manifeste trié et déterministe : nom, taille, SHA-256 (ni date, ni chemin absolu)."""
    entrees = []
    for nom in sorted(noms):
        chemin = dossier / nom
        if chemin.exists():
            entrees.append({"fichier": nom, "taille_octets": chemin.stat().st_size, "sha256": sha256_fichier(chemin)})
    return {"source": source, "nombre_fichiers": len(entrees), "fichiers": entrees}


def executer(regles: dict, dossier: Path, chemin_manifeste: Path, recuperer: Recuperateur = recuperer_http,
             prevus: list[tuple[str, str]] | None = None, pause_s: float = PAUSE_ENTRE_FICHIERS_S) -> dict:
    """Télécharge ce qui manque, écrit le manifeste et renvoie un bilan chiffré."""
    dossier.mkdir(parents=True, exist_ok=True)
    prevus = fichiers_prevus(regles) if prevus is None else prevus
    bilan = {"prevus": len(prevus), "deja_present": 0, "telecharge": 0, "rejete": 0, "echec": 0, "requetes": 0}
    problemes = []
    for i, (nom, url) in enumerate(prevus, start=1):
        try:
            statut, requetes = traiter_fichier(nom, url, dossier, recuperer)
        except ErreurTelechargement as erreur:
            statut, requetes = "echec", 0
            problemes.append(str(erreur))
            print(f"  ÉCHEC : {erreur}")
        bilan[statut] += 1
        bilan["requetes"] += requetes
        if statut != "deja_present":
            print(f"[{i:3d}/{len(prevus)}] {nom} : {statut}")
        if requetes and pause_s:
            time.sleep(pause_s)
    contenu = manifeste(dossier, [nom for nom, _ in prevus], regles["donnees"]["url_source"])
    C.ecrire_texte(chemin_manifeste, C.texte_json(contenu))
    bilan["problemes"] = problemes
    return bilan


def main() -> int:
    C.proteger_sortie()
    debut = time.perf_counter()
    regles = R.charger_regles()
    bilan = executer(regles, C.DOSSIER_BRUT, C.MANIFESTE_BRUT)
    duree = time.perf_counter() - debut
    print(f"Prévus {bilan['prevus']} | déjà présents {bilan['deja_present']} | téléchargés {bilan['telecharge']} | "
          f"rejetés {bilan['rejete']} | échecs {bilan['echec']} | requêtes réseau {bilan['requetes']}")
    print(f"Manifeste : {C.chemin_relatif(C.MANIFESTE_BRUT)}")
    print(f"Durée : {C.nombre_fr(duree, 1)} s | mémoire maximale du processus : {C.nombre_fr(C.memoire_max_mo(), 1)} Mo")
    return 0 if bilan["rejete"] == 0 and bilan["echec"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
