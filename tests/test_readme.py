"""Chaque lien relatif du README doit pointer vers un fichier suivi par Git."""

import re
import subprocess
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
LIEN = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")


def liens_relatifs(texte: str) -> list[str]:
    return [l for l in LIEN.findall(texte) if not re.match(r"^[a-z][a-z0-9+.-]*:", l, re.I)]


def fichiers_suivis() -> set[str]:
    sortie = subprocess.run(["git", "ls-files"], cwd=RACINE, capture_output=True, text=True, check=True)
    return set(sortie.stdout.splitlines())


def liens_casses(texte: str, suivis: set[str]) -> list[str]:
    return [l for l in liens_relatifs(texte) if l.removeprefix("./") not in suivis]


def test_liens_du_readme_vers_des_fichiers_suivis():
    texte = (RACINE / "README.md").read_text(encoding="utf-8")
    liens = liens_relatifs(texte)
    assert liens, "Le README devrait contenir au moins un lien relatif."
    assert liens_casses(texte, fichiers_suivis()) == []


def test_temoin_lien_casse_detecte():
    texte = "Voir [les règles](docs/REGLES.md), [absent](docs/INEXISTANT.md) et [site](https://exemple.org)."
    assert liens_relatifs(texte) == ["docs/REGLES.md", "docs/INEXISTANT.md"]
    assert liens_casses(texte, fichiers_suivis()) == ["docs/INEXISTANT.md"]
