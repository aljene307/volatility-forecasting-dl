"""Chaque lien relatif et chaque chemin cité entre accents graves dans le README doit pointer
vers un fichier existant et suivi par Git."""

import re
import subprocess
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
LIEN = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")
CODE = re.compile(r"`([^`\n]+)`")
DOSSIERS_DU_PROJET = ("src/", "docs/", "tests/", "data/", "config/", "rapports/")


def liens_relatifs(texte: str) -> list[str]:
    return [l for l in LIEN.findall(texte) if not re.match(r"^[a-z][a-z0-9+.-]*:", l, re.I)]


def chemins_cites(texte: str) -> list[str]:
    """Chemins de fichiers du projet cités entre accents graves (par exemple `src/qualite.py`)."""
    return [c.strip() for c in CODE.findall(texte)
            if c.strip().startswith(DOSSIERS_DU_PROJET) and " " not in c.strip()]


def fichiers_suivis() -> set[str]:
    sortie = subprocess.run(["git", "ls-files"], cwd=RACINE, capture_output=True, text=True, check=True)
    return set(sortie.stdout.splitlines())


def references_cassees(references: list[str], suivis: set[str]) -> list[str]:
    cassees = []
    for ref in references:
        chemin = ref.removeprefix("./")
        if chemin not in suivis or not (RACINE / chemin).is_file():
            cassees.append(ref)
    return cassees


def test_liens_du_readme_vers_des_fichiers_suivis():
    texte = (RACINE / "README.md").read_text(encoding="utf-8")
    liens = liens_relatifs(texte)
    assert liens, "Le README devrait contenir au moins un lien relatif."
    assert references_cassees(liens, fichiers_suivis()) == []


def test_chemins_cites_du_readme_existent_et_sont_suivis():
    texte = (RACINE / "README.md").read_text(encoding="utf-8")
    chemins = chemins_cites(texte)
    assert chemins, "Le README devrait citer au moins un fichier du projet."
    assert references_cassees(chemins, fichiers_suivis()) == []


def test_temoin_lien_casse_detecte():
    texte = "Voir [les règles](docs/REGLES.md), [absent](docs/INEXISTANT.md) et [site](https://exemple.org)."
    assert liens_relatifs(texte) == ["docs/REGLES.md", "docs/INEXISTANT.md"]
    assert references_cassees(liens_relatifs(texte), fichiers_suivis()) == ["docs/INEXISTANT.md"]


def test_temoin_chemin_cite_casse_detecte():
    texte = ("Lancer `src/qualite.py`, puis `src/inexistant.py` ; lire `data/manifeste_brut.json`. "
             "Une commande comme `git status` ou un mot comme `.venv` n'est pas un chemin du projet.")
    assert chemins_cites(texte) == ["src/qualite.py", "src/inexistant.py", "data/manifeste_brut.json"]
    assert references_cassees(chemins_cites(texte), fichiers_suivis()) == ["src/inexistant.py"]
