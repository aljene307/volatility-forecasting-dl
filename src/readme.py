"""Blocs générés du README : résumé (français), « In English », limites et durées de la reproduction complète.

Aucun chiffre tapé à la main : tout est lu dans rapports/ et config/, par les MÊMES fonctions que l'application et la
synthèse PDF (src/resume.py). Les deux autres blocs du README sont écrits par src/resultats_test.py (test final) et
src/comparer.py (HAR-J).

Lancement : .venv\\Scripts\\python src\\readme.py      (vérification seule : --verifier, code 1 si le README n'est pas à jour)
"""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import commun as C  # noqa: E402
import regles as R  # noqa: E402
import resume as RES  # noqa: E402

CHEMIN_README = C.RACINE / "README.md"


def marqueurs(nom: str) -> tuple[str, str]:
    return (f"<!-- début du bloc généré par src/readme.py : {nom} -->", f"<!-- fin du bloc généré par src/readme.py : {nom} -->")


def lire(nom: str) -> dict:
    return json.loads((C.DOSSIER_RAPPORTS / nom).read_text(encoding="utf-8"))


def duree(secondes: float) -> str:
    minutes = round(secondes / 60)
    return f"{minutes // 60} h {minutes % 60:02d} min" if minutes >= 60 else f"{minutes} min"


def blocs() -> dict[str, str]:
    t = lire("test_final.json")
    attentes = tomllib.loads((C.RACINE / "config" / "attentes_test.toml").read_text(encoding="utf-8"))
    dev, ex = lire("comparaison_modeles.json"), lire("explicabilite.json")
    mesures = lire("mesures_entrainement.json")
    v = RES.valeurs_trouvailles(t)
    plis = dev["temps_phase_plis"]
    return {
        "résumé": " ".join(RES.phrases_trouvailles(v, "fr")),
        "In English": "### In English\n\n" + " ".join(RES.phrases_trouvailles(v, "en"))
                      + " Educational, non-commercial project; data: Binance Vision, CC BY-NC-SA 4.0.",
        "limites": "\n".join(f"- {p}" for p in RES.points_limites(t, attentes, dev, ex, R.charger_regles())),
        "durées": (f"- Durée réelle de la phase des plis du deep learning ({len(plis['par_modele'])} réseaux, {len(dev['actifs'])} actifs) : "
                   f"{duree(plis['reel_s'])} "
                   f"(`rapports/comparaison_modeles.json`, clé `temps_phase_plis`).\n"
                   f"- Pic de mémoire mesuré à l'entraînement : {RES.nombre(mesures['memoire']['pic_max_go'], 2)} Go "
                   f"(`rapports/mesures_entrainement.json`).\n"
                   "- Les autres durées (téléchargement, réglage, explicabilité) sont dans le [journal des choix](docs/CHOIX.md) : "
                   "une reprise après interruption rendrait fausse une durée écrite dans un fichier de résultats."),
    }


def remplacer(texte: str, nom: str, contenu: str) -> str:
    debut, fin = marqueurs(nom)
    if texte.count(debut) != 1 or texte.count(fin) != 1:
        raise ValueError(f"README : marqueurs du bloc « {nom} » absents ou en double.")
    avant, reste = texte.split(debut)
    _, apres = reste.split(fin)
    return avant + debut + "\n" + contenu + "\n" + fin + apres


def readme_a_jour(texte: str) -> str:
    for nom, contenu in blocs().items():
        texte = remplacer(texte, nom, contenu)
    return texte


def main(arguments: list[str]) -> int:
    C.proteger_sortie()
    texte = CHEMIN_README.read_text(encoding="utf-8")
    nouveau = readme_a_jour(texte)
    if "--verifier" in arguments:
        print("README à jour." if nouveau == texte else "README PAS à jour : relancer src/readme.py.")
        return 0 if nouveau == texte else 1
    C.ecrire_texte(CHEMIN_README, nouveau)
    print("Blocs du README générés : " + ", ".join(blocs()) + ".")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
