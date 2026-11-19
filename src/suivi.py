"""Suivi de l'entraînement, en LECTURE SEULE : affiche en français le journal écrit par src/entrainer.py.

Usage : .venv\\Scripts\\python src/suivi.py            (dossier par défaut : sorties/deep_learning)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import commun as C  # noqa: E402


def duree(secondes: float | None) -> str:
    if secondes is None:
        return "-"
    h, reste = divmod(int(round(secondes)), 3600)
    return f"{h} h {reste // 60:02d} min" if h else f"{reste // 60} min {reste % 60:02d} s"


def texte_suivi(journal: dict) -> str:
    n = C.nombre_fr
    lignes = [f"Phase : {journal['phase']} | statut : {journal['statut']} | dernière mise à jour : {journal['mise_a_jour']}",
              f"Unités terminées : {journal['unites_terminees']} sur {journal['unites_total']} "
              f"(restantes : {journal['unites_total'] - journal['unites_terminees']})",
              f"Temps réel cumulé : {duree(journal['cumul_reel_s'])} | estimé pour ces unités : {duree(journal['cumul_estime_s'])}"
              + (f" | rapport réel / estimé : {n(journal['rapport_reel_sur_estime'], 2)} (arrêt au-delà de 1,50)"
                 if journal["rapport_reel_sur_estime"] is not None else ""),
              f"Temps restant estimé : {duree(journal['restant_estime_s'])}", "",
              f"{'Modèle':<12} {'Terminées':>10} {'Réel/époque':>12} {'Estimé/époque':>14} {'Temps réel':>12}"]
    for m, s in journal["par_modele"].items():
        reel = f"{n(s['temps_par_epoque_reel_s'], 2)} s" if s["temps_par_epoque_reel_s"] is not None else "-"
        lignes.append(f"{m:<12} {s['terminees']:>4} / {s['total']:<4} {reel:>12} {n(s['temps_par_epoque_estime_s'], 2) + ' s':>14} "
                      f"{duree(s['temps_reel_s']):>12}")
    return "\n".join(lignes)


def main(arguments: list[str]) -> int:
    C.proteger_sortie()
    dossier = C.RACINE / (arguments[0] if arguments else "sorties/deep_learning")
    chemin = dossier / "journal.json"
    if not chemin.exists():
        print(f"Aucun journal dans {C.chemin_relatif(dossier) if dossier.exists() else dossier.name} : l'entraînement n'a pas encore commencé.")
        return 0
    print(texte_suivi(json.loads(chemin.read_text(encoding="utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
