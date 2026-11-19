"""API légère de prévision de la volatilité (règles : config/regles.toml, section api ; docs/REGLES.md, section 18).

- Modèles servis : Transformer (BTCUSDT) et CNN-LSTM (ETHUSDT), 3 graines du découpage du test final, en ONNX.
- L'utilisateur fournit 30 jours consécutifs des 13 variables (non normalisées) et le jour de la semaine du dernier
  jour (lundi = 0). L'API ne télécharge et ne diffuse AUCUNE donnée Binance.
- Prévision = moyenne des log des 3 graines ; σ̂ = racine(exp(2ŷ + 2s²)) ; exposition et VaR selon les règles du projet.
- Au démarrage : empreintes du manifeste vérifiées ; refus de démarrer si un fichier est altéré.
- Sans torch ni pandas.

Modèles et paramètres : œuvres dérivées sous CC BY-NC-SA 4.0 ; Données : Binance Vision.
Lancement local : voir le README (section API).
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Literal

import numpy as np
import onnxruntime as ort
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

DOSSIER_MODELES = Path(__file__).resolve().parent / "modeles"
LONGUEUR = 30
TOLERANCE_LOG = 1e-9            # cohérence demandée entre log_rv_k et log(rv_k)


class ErreurDemarrage(RuntimeError):
    """Un fichier servi ne correspond pas à son empreinte : l'API refuse de démarrer."""


# --- Démarrage : empreintes et modèles ---------------------------------------------------------------

def verifier_manifeste(dossier: Path) -> dict:
    manifeste = json.loads((dossier / "manifeste.json").read_text(encoding="utf-8"))
    problemes = []
    for nom, attendu in manifeste["fichiers"].items():
        chemin = dossier / nom
        if not chemin.exists():
            problemes.append(f"{nom} : absent")
        elif hashlib.sha256(chemin.read_bytes()).hexdigest() != attendu:
            problemes.append(f"{nom} : empreinte différente")
    if problemes:
        raise ErreurDemarrage("Refus de démarrer : fichiers non conformes au manifeste : " + " ; ".join(problemes))
    return manifeste


def memoire_processus_mo() -> tuple[float | None, str]:
    """Mémoire résidente du processus : /proc/self/status (VmRSS) si disponible, sinon WorkingSetSize sous Windows."""
    statut = Path("/proc/self/status")
    if statut.exists():
        for ligne in statut.read_text().splitlines():
            if ligne.startswith("VmRSS:"):
                return int(ligne.split()[1]) / 1024, "/proc/self/status (VmRSS)"
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Compteurs(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]
        noyau = ctypes.WinDLL("kernel32", use_last_error=True)
        noyau.GetCurrentProcess.restype = wintypes.HANDLE
        noyau.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Compteurs), wintypes.DWORD]
        noyau.K32GetProcessMemoryInfo.restype = wintypes.BOOL
        c = Compteurs()
        c.cb = ctypes.sizeof(c)
        if noyau.K32GetProcessMemoryInfo(noyau.GetCurrentProcess(), ctypes.byref(c), c.cb):
            return c.WorkingSetSize / 1024 ** 2, "Windows (WorkingSetSize)"
    return None, "indisponible"


# --- Schémas de la requête et de la réponse --------------------------------------------------------------

class Jour(BaseModel):
    """Les 13 variables d'un jour, arrêtées à sa clôture (non normalisées), comme dans le projet."""
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    rv_1: float = Field(gt=0)
    rv_7: float = Field(gt=0)
    rv_30: float = Field(gt=0)
    log_rv_1: float
    log_rv_7: float
    log_rv_30: float
    parkinson: float = Field(ge=0)
    garman_klass: float
    log_rendement: float
    log_volume: float
    rsi_14: float = Field(ge=0, le=100)
    macd_histogramme_relatif: float
    bollinger_largeur_relative: float = Field(ge=0)

    @model_validator(mode="after")
    def coherence_des_logs(self):
        for n in (1, 7, 30):
            rv, lg = getattr(self, f"rv_{n}"), getattr(self, f"log_rv_{n}")
            if abs(lg - math.log(rv)) > TOLERANCE_LOG:
                raise ValueError(f"log_rv_{n} doit être égal à log(rv_{n}) (reçu {lg}, attendu {math.log(rv)})")
        return self


class Requete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actif: Literal["BTCUSDT", "ETHUSDT"]
    jour_semaine_dernier_jour: int = Field(ge=0, le=6)
    jours: list[Jour] = Field(min_length=LONGUEUR, max_length=LONGUEUR)


# --- Erreurs 422 en français, champ par champ -------------------------------------------------------------

def _champ(loc: tuple) -> str:
    morceaux = [str(x) for x in loc if x != "body"]
    texte = ""
    for m in morceaux:
        texte += f"[{m}]" if m.isdigit() else (f".{m}" if texte else m)
    return texte or "corps"


def _message(e: dict) -> str:
    t, ctx, entree = e.get("type", ""), e.get("ctx", {}) or {}, e.get("input")
    if t == "missing":
        return "valeur manquante"
    if t in ("too_short", "too_long"):
        return f"il faut exactement {LONGUEUR} jours (reçu {len(entree) if isinstance(entree, list) else '?'})"
    if t == "literal_error":
        return "actif inconnu : valeurs permises BTCUSDT et ETHUSDT"
    if t == "greater_than":
        return f"doit être strictement supérieur à {ctx.get('gt')} (reçu {entree})"
    if t == "greater_than_equal":
        return f"doit être supérieur ou égal à {ctx.get('ge')} (reçu {entree})"
    if t == "less_than_equal":
        return f"doit être inférieur ou égal à {ctx.get('le')} (reçu {entree})"
    if t == "finite_number":
        return "doit être un nombre fini"
    if t in ("float_type", "float_parsing"):
        return "doit être un nombre"
    if t in ("int_type", "int_parsing", "int_from_float"):
        return "doit être un nombre entier"
    if t == "extra_forbidden":
        return "champ inconnu"
    if t in ("list_type",):
        return "doit être une liste"
    if t in ("model_type", "model_attributes_type", "dict_type"):
        return "doit être un objet"
    if t == "json_invalid":
        return "corps JSON invalide"
    if t == "value_error":
        return str(e.get("msg", "")).removeprefix("Value error, ")
    return "valeur invalide"


async def erreurs_en_francais(_requete: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"erreurs": [{"champ": _champ(tuple(e.get("loc", ()))), "message": _message(e)}
                                                              for e in exc.errors()]})


# --- Prévision ------------------------------------------------------------------------------------------------

class Moteur:
    """Modèles ONNX et paramètres d'un dossier vérifié par son manifeste."""

    def __init__(self, dossier: Path):
        self.manifeste = verifier_manifeste(dossier)
        self.p = json.loads((dossier / "parametres.json").read_text(encoding="utf-8"))
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        self.sessions = {a: [ort.InferenceSession(str(dossier / f), sess_options=options, providers=["CPUExecutionProvider"])
                             for f in x["fichiers_onnx"]] for a, x in self.p["actifs"].items()}

    def entree(self, requete: Requete) -> np.ndarray:
        """(1, 30, 20) : variables normalisées (float64), puis le jour de la semaine en one-hot ; converti en float32."""
        n = self.p["actifs"][requete.actif]["normalisation"]
        x = np.array([[getattr(j, v) for v in self.p["variables"]] for j in requete.jours], dtype="float64")
        x = (x - np.array(n["moyennes"])) / np.array(n["ecarts_types"])
        jours = [(requete.jour_semaine_dernier_jour - (LONGUEUR - 1 - i)) % 7 for i in range(LONGUEUR)]
        return np.concatenate([x, np.eye(7)[jours]], axis=1).astype("float32")[None, :, :]

    def prevoir(self, requete: Requete) -> dict:
        a = self.p["actifs"][requete.actif]
        n = a["normalisation"]
        x = self.entree(requete)
        par_graine = [float(s.run(None, {"entree": x})[0].astype("float64")[0]) * n["cible_ecart_type"] + n["cible_moyenne"]
                      for s in self.sessions[requete.actif]]
        y = float(np.mean(par_graine))
        sigma = math.sqrt(math.exp(2 * y + 2 * a["s2"]))
        annualisee = sigma * math.sqrt(self.p["annualisation_jours"])
        exposition = min(max(a["vol_cible_annuelle"] / annualisee, self.p["exposition_min"]), self.p["exposition_max"])
        return {"actif": requete.actif, "modele": a["modele"], "prevision_log_rv": y, "prevision_log_rv_par_graine": par_graine,
                "s2": a["s2"], "volatilite_journaliere": sigma, "volatilite_annualisee": annualisee,
                "vol_cible_annuelle": a["vol_cible_annuelle"], "exposition": exposition,
                "var_1_jour_95": self.p["var_quantile"] * sigma,
                "explication": "Volatilité du lendemain du dernier jour fourni ; exposition = volatilité cible / volatilité prévue "
                               "annualisée, bornée entre 0 et 1 ; VaR à 1 jour à 95 % = quantile normal × volatilité journalière.",
                "licence": self.p["licence"]}


def creer_app(dossier: Path = DOSSIER_MODELES) -> FastAPI:
    """Crée l'API ; lève ErreurDemarrage si un fichier servi ne correspond pas au manifeste."""
    moteur = Moteur(dossier)
    app = FastAPI(title="Prévision de la volatilité (BTC, ETH)", version="1.0",
                  description="Les données sont fournies par l'utilisateur ; aucune donnée Binance n'est téléchargée ni diffusée. "
                              "Modèles : CC BY-NC-SA 4.0, Données : Binance Vision.")
    app.add_exception_handler(RequestValidationError, erreurs_en_francais)

    @app.get("/health")
    def sante() -> dict:
        memoire, source = memoire_processus_mo()
        return {"statut": "ok", "manifeste_verifie": True, "fichiers_verifies": len(moteur.manifeste["fichiers"]),
                "modeles": {a: x["modele"] for a, x in moteur.p["actifs"].items()},
                "versions": {"python": platform.python_version(), **{p: version(p) for p in ("numpy", "onnxruntime", "fastapi", "pydantic")}},
                "memoire_mo": None if memoire is None else round(memoire, 1), "source_memoire": source}

    @app.post("/prevoir")
    def prevoir(requete: Requete) -> dict:
        return moteur.prevoir(requete)

    return app


app = creer_app()
