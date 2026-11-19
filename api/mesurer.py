"""Mesure de l'API en fonctionnement : mémoire du processus (lue par /health) et temps de réponse de /prevoir.

Lance uvicorn dans un processus séparé, envoie l'exemple SYNTHÉTIQUE, puis arrête le serveur.
Usage (depuis la racine du projet) : .venv\\Scripts\\python api\\mesurer.py
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

import httpx

RACINE = Path(__file__).resolve().parent.parent
PORT = 8765
REQUETES = 300


def main() -> int:
    serveur = subprocess.Popen([sys.executable, "-m", "uvicorn", "api.app:app", "--port", str(PORT), "--log-level", "warning"],
                               cwd=RACINE)
    url = f"http://127.0.0.1:{PORT}"
    try:
        debut = time.perf_counter()
        while True:
            try:
                if httpx.get(f"{url}/health", timeout=1).status_code == 200:
                    break
            except httpx.TransportError:
                pass
            if time.perf_counter() - debut > 60:
                raise RuntimeError("L'API n'a pas démarré en 60 s.")
            time.sleep(0.2)
        demarrage = time.perf_counter() - debut
        memoire_depart = httpx.get(f"{url}/health").json()
        requete = json.loads((RACINE / "api" / "exemple_synthetique.json").read_text(encoding="utf-8"))["requete"]
        temps = []
        with httpx.Client(base_url=url) as client:
            for i in range(REQUETES):
                requete["actif"] = "BTCUSDT" if i % 2 == 0 else "ETHUSDT"
                t = time.perf_counter()
                r = client.post("/prevoir", json=requete)
                temps.append(time.perf_counter() - t)
                r.raise_for_status()
        memoire_fin = httpx.get(f"{url}/health").json()
        q = statistics.quantiles(temps, n=100)
        print(f"Démarrage : {demarrage:.1f} s")
        print(f"Mémoire du processus au démarrage : {memoire_depart['memoire_mo']} Mo ; après {REQUETES} requêtes : "
              f"{memoire_fin['memoire_mo']} Mo ({memoire_fin['source_memoire']}) ; limite visée : 512 Mo")
        print(f"Temps de réponse de /prevoir (client local, {REQUETES} requêtes) : médiane {1000 * statistics.median(temps):.1f} ms, "
              f"95e centile {1000 * q[94]:.1f} ms, maximum {1000 * max(temps):.1f} ms")
    finally:
        serveur.terminate()
        serveur.wait(timeout=10)
    return 0


if __name__ == "__main__":
    sys.exit(main())
