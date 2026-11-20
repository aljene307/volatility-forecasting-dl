"""Licences : MIT pour le code, CC BY-NC-SA 4.0 pour les données et les fichiers dérivés ; le README renvoie aux deux."""

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def lire(nom: str) -> str:
    return (RACINE / nom).read_text(encoding="utf-8")


def test_licence_mit_du_code():
    texte = lire("LICENSE")
    assert texte.startswith("MIT License")
    assert "Copyright (c) 2026 Mohamed Aljene" in texte
    assert "CODE seulement" in texte and "LICENSE-DONNEES.md" in texte


def test_licence_des_donnees_et_des_fichiers_derives():
    texte = lire("LICENSE-DONNEES.md")
    assert "ne sont **pas** incluses" in texte
    for derive in ("`figures/`", "`docs/captures/`", "`rapports/`", "`docs/synthese.pdf`", "`api/modeles/`"):
        assert derive in texte, derive
    assert "Données : Binance Vision, CC BY-NC-SA 4.0 — projet volatility-forecasting-dl, Mohamed Aljene" in texte
    for lien in ("https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md",
                 "https://data.binance.vision/terms-of-use.html", "https://creativecommons.org/licenses/by-nc-sa/4.0/deed.fr"):
        assert lien in texte, lien


def test_derives_cites_existent():
    for chemin in ("figures", "docs/captures", "rapports", "docs/synthese.pdf", "api/modeles"):
        assert (RACINE / chemin).exists(), chemin


def test_section_licences_du_readme_renvoie_aux_deux():
    texte = lire("README.md")
    section = re.search(r"^## Licences\n(.*?)(?=^## |^<details>|\Z)", texte, re.S | re.M)
    assert section, "section « Licences » absente du README"
    assert "[LICENSE](LICENSE)" in section.group(1) and "[LICENSE-DONNEES.md](LICENSE-DONNEES.md)" in section.group(1)


def test_temoin_section_sans_lien_detectee():
    texte = "## Licences\n\n- Code : MIT.\n\n## Autre\n"
    section = re.search(r"^## Licences\n(.*?)(?=^## |^<details>|\Z)", texte, re.S | re.M)
    assert "[LICENSE](LICENSE)" not in section.group(1)
