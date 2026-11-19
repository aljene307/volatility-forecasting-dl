"""Explicabilité sur le développement (2020 à 2024) : SHAP, attention, règle de fidélité. Le test final reste fermé.

Règles : config/regles.toml, sections explicabilite et explicabilite.precisions ; docs/REGLES.md, sections 10 et 16
(écrites et commitées avant tout calcul).

- SHAP : XGBoost (TreeExplainer, exact) ; LSTM et modèle retenu de chaque actif (GradientExplainer, 1000 tirages,
  fond de 100 séquences de la fenêtre d'ajustement). Contributions en unités de log(RV). Additivité vérifiée ;
  au-delà de la tolérance, arrêt avant toute écriture de résultat.
- Les modèles expliqués sont exactement ceux qui ont été évalués : réseaux rechargés depuis leurs poids, XGBoost
  ré-entraîné à l'identique ; prévisions comparées à celles des unités (tolérance 1e-9).
- Attention : Transformer (ligne du jour J, moyenne sur les têtes et les couches), crises contre autres jours ;
  TFT (importance des variables de l'encodeur et attention par retard).
- Fidélité : sur la validation interne de chaque pli, permuter la meilleure variable SHAP doit dégrader le QLIKE plus
  que permuter la moins bonne (20 répétitions, graine 42).

Calcul par unités avec reprise (sorties/explicabilite/, ignoré par Git). Sorties commitées : rapports/explicabilite.json,
docs/EXPLICABILITE.md (généré), figures 7 à 9. Aucune valeur journalière n'est commitée.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import baselines as B  # noqa: E402
import commun as C  # noqa: E402
import comparer as K  # noqa: E402
import entrainer as T  # noqa: E402
import evaluation as EV  # noqa: E402
import garde as G  # noqa: E402
import regles as R  # noqa: E402
import reprise as P  # noqa: E402
import variables as V  # noqa: E402

VERSION = "explicabilite-1"
DOSSIER = C.RACINE / "sorties" / "explicabilite"
CHEMIN_JSON = C.DOSSIER_RAPPORTS / "explicabilite.json"
CHEMIN_MD = C.RACINE / "docs" / "EXPLICABILITE.md"
LONGUEUR = 30
NOMS_VARIABLES = {
    "rv_1": "RV du jour", "rv_7": "RV moyenne 7 j", "rv_30": "RV moyenne 30 j", "log_rv_1": "log RV du jour",
    "log_rv_7": "log RV moyenne 7 j", "log_rv_30": "log RV moyenne 30 j", "parkinson": "Parkinson", "garman_klass": "Garman-Klass",
    "log_rendement": "log-rendement", "log_volume": "log-volume", "rsi_14": "RSI 14 j", "macd_histogramme_relatif": "MACD relatif",
    "bollinger_largeur_relative": "largeur de Bollinger", "jour_semaine": "jour de la semaine", "y": "y (log RV du jour, TFT)"}


class ErreurExplicabilite(Exception):
    pass


def variables(regles: dict) -> list[str]:
    return list(regles["entrainement"]["variables_continues"]) + ["jour_semaine"]


def colonnes_variable(regles: dict) -> dict[str, list[int]]:
    """Colonnes de chaque variable dans les entrées des réseaux : une par variable continue, 7 pour le jour de la semaine."""
    n = len(regles["entrainement"]["variables_continues"])
    sortie = {v: [k] for k, v in enumerate(regles["entrainement"]["variables_continues"])}
    sortie["jour_semaine"] = list(range(n, n + 7))
    return sortie


# --- SHAP des réseaux ---------------------------------------------------------------------------

def _enveloppe(reseau):
    import torch

    class Enveloppe(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.reseau = reseau

        def forward(self, z):
            return self.reseau(z).unsqueeze(-1)

    return Enveloppe().eval()


def shap_reseau(reseau, x: np.ndarray, fond: np.ndarray, tirages: int, graine: int) -> dict:
    """Contributions SHAP (GradientExplainer) d'un réseau torch, dans l'unité de sa sortie ; additivité mesurée."""
    import shap
    import torch
    e = _enveloppe(reseau)
    xt, ft = torch.from_numpy(np.asarray(x, dtype="float32")), torch.from_numpy(np.asarray(fond, dtype="float32"))
    with torch.no_grad():
        prevision = e(xt).squeeze(-1).numpy().astype("float64")
        base = float(e(ft).mean())
    np.random.seed(graine)
    phi = np.asarray(shap.GradientExplainer(e, ft, batch_size=1000).shap_values(xt, nsamples=tirages, rseed=graine), dtype="float64")
    phi = phi.reshape(x.shape)
    return {"phi": phi, "base": base, "prevision": prevision, **additivite(prevision, base, phi)}


def additivite(prevision: np.ndarray, base: float, phi: np.ndarray) -> dict:
    """Écart entre la prévision et (valeur de base + somme des contributions) : erreur relative moyenne et écart maximal."""
    residu = np.asarray(prevision) - base - phi.reshape(len(phi), -1).sum(axis=1)
    return {"additivite_erreur_relative": float(np.mean(np.abs(residu)) / float(np.mean(np.abs(np.asarray(prevision) - base)))),
            "additivite_residu_max": float(np.max(np.abs(residu)))}


def importance_par_element(phi: np.ndarray, regles: dict) -> np.ndarray:
    """(30 retards × variables) : moyenne des |φ| sur les jours ; jour de la semaine = somme de ses 7 colonnes.
    Ligne k = retard k + 1 (retard 1 = jour J, dernier jour de la séquence)."""
    moyenne = np.abs(phi).mean(axis=0)[::-1]              # retard 1 en premier
    cols = colonnes_variable(regles)
    return np.stack([moyenne[:, c].sum(axis=1) for c in cols.values()], axis=1)


# --- Fidélité ------------------------------------------------------------------------------------

def degradation_permutation(predire, x: np.ndarray, colonnes: list[int], cible: np.ndarray, s2: float,
                            permutations: list[np.ndarray]) -> dict:
    """QLIKE moyen avec la variable permutée entre les jours, moins QLIKE sans permutation (moyenne des répétitions).
    `predire(x)` renvoie une prévision en log(RV) ; x est (jours, retards, colonnes) ou (jours, colonnes)."""
    def qlike(px):
        return float(B.pertes(cible, EV.variance_depuis_log(predire(px), s2))["qlike"].mean())

    reference = qlike(x)
    valeurs = []
    for p in permutations:
        xp = x.copy()
        xp[..., colonnes] = x[p][..., colonnes]
        valeurs.append(qlike(xp) - reference)
    return {"qlike_reference": reference, "degradation_moyenne": float(np.mean(valeurs)), "degradation_ecart_type": float(np.std(valeurs, ddof=1))}


def fidelite(predire, x: np.ndarray, cible: np.ndarray, s2: float, importance: dict[str, float], colonnes: dict[str, list[int]],
             repetitions: int, graine: int) -> dict:
    """Règle de fidélité : la meilleure variable SHAP doit dégrader le QLIKE plus que la moins bonne (permutations appariées)."""
    classement = sorted(importance, key=importance.get, reverse=True)
    rng = np.random.default_rng(graine)
    permutations = [rng.permutation(len(x)) for _ in range(repetitions)]
    meilleure, moins_bonne = classement[0], classement[-1]
    dm = degradation_permutation(predire, x, colonnes[meilleure], cible, s2, permutations)
    db = degradation_permutation(predire, x, colonnes[moins_bonne], cible, s2, permutations)
    return {"meilleure": meilleure, "moins_bonne": moins_bonne, "degradation_meilleure": dm["degradation_moyenne"],
            "degradation_moins_bonne": db["degradation_moyenne"], "ecart_type_meilleure": dm["degradation_ecart_type"],
            "ecart_type_moins_bonne": db["degradation_ecart_type"], "qlike_reference": dm["qlike_reference"],
            "fidele": dm["degradation_moyenne"] > db["degradation_moyenne"]}


# --- Contexte d'un actif ---------------------------------------------------------------------------

class Contexte:
    """Données, choix et unités déjà calculées d'un actif (développement)."""

    def __init__(self, actif: str, regles: dict):
        self.actif, self.regles = actif, regles
        self.cle = T._cle_donnees(regles)
        self.exemples, self.journalier = T.donnees_reseaux(V.lire_bougies(C.DOSSIER_TRAITE / f"{actif}_5m.parquet"), regles)
        self.choix = json.loads((K.DOSSIER_DL / "reglage.json").read_text(encoding="utf-8"))[actif]
        self.calcul = K.calcul_baselines(actif, regles, self.cle)
        self.plis = R.decoupages(regles)[:-1]
        self.xgb = json.loads(B.CHEMIN_JSON.read_text(encoding="utf-8"))["actifs"][actif]["xgboost_reglage"]["combinaison_retenue"]
        self._norm, self._tableau = {}, {}

    def norm(self, d: dict) -> dict:
        if d["nom"] not in self._norm:
            chemin = K.DOSSIER_DL / "normalisation" / self.actif / f"{d['nom'].replace(' ', '_')}.json"
            self._norm[d["nom"]] = json.loads(chemin.read_text(encoding="utf-8"))
        return self._norm[d["nom"]]

    def tableau(self, d: dict) -> np.ndarray:
        if d["nom"] not in self._tableau:
            self._tableau[d["nom"]] = T.tableau_normalise(self.journalier, self.norm(d))
        return self._tableau[d["nom"]]

    def parties(self, d: dict) -> dict:
        return T.parties(self.exemples, d, avec_evaluation=True)          # garde du test aveugle comprise

    def x(self, d: dict, partie: str) -> np.ndarray:
        return T.sequences(self.tableau(d), self.journalier.index, list(self.parties(d)[partie]["date_origine"]), LONGUEUR)

    def unite_dl(self, modele: str, d: dict, g: int) -> dict:
        return K._unite(K.DOSSIER_DL / "unites", T.id_pli(self.actif, modele, d["nom"], g, self.cle))

    def reseau(self, modele: str, d: dict, g: int):
        """Réseau torch rechargé depuis ses poids ; contrôle : prévisions d'évaluation identiques à celles de l'unité."""
        import torch
        import reseaux
        u = self.unite_dl(modele, d, g)
        r = reseaux.construire_reseau(modele, self.choix[modele]["combinaison"], self.tableau(d).shape[1], LONGUEUR)
        r.load_state_dict(torch.load(K.DOSSIER_DL / u["poids"], weights_only=True))
        r.eval()
        n = self.norm(d)
        prev = T.prevoir_torch(r, self.x(d, "evaluation")) * n["cible_ecart_type"] + n["cible_moyenne"]
        ecart = float(np.max(np.abs(prev - np.array(u["evaluation"]["prevision_log"]))))
        if ecart > self.regles["explicabilite"]["precisions"]["reproduction_tolerance"]:
            raise ErreurExplicabilite(f"{self.actif} {modele} {d['nom']} graine {g} : réseau rechargé différent ({ecart}).")
        return r, ecart

    def xgboost(self, d: dict) -> tuple[list, float]:
        """Les 3 XGBoost du pli, ré-entraînés avec les mêmes graines ; contrôle : prévisions identiques à celles de l'unité."""
        identifiant = f"{B.VERSION}|{self.actif}|baselines|{d['nom']}|{self.cle}"
        graines = [P.graine_unite(f"{identifiant}|graine {g}") for g in self.regles["modeles"]["graines_deep_learning"]]
        m = B.masques(self.exemples, d)
        aj, val = self.exemples[m["ajustement"]], self.exemples[m["validation"]]
        ev = self.parties(d)["evaluation"]
        modeles = [B.entrainer_xgboost(B.entrees(aj, self.regles), aj["cible"].to_numpy(), B.entrees(val, self.regles),
                                       val["cible"].to_numpy(), self.xgb, g, self.regles) for g in graines]
        sortie = next(b["sortie"] for b in self.calcul["decoupages"] if b["decoupage"]["nom"] == d["nom"])
        ecart = max(float(np.max(np.abs(mx.predict(B.entrees(ev, self.regles)).astype("float64") - np.array(p))))
                    for mx, p in zip(modeles, sortie["evaluation"]["xgboost_log_par_graine"]))
        if ecart > self.regles["explicabilite"]["precisions"]["reproduction_tolerance"]:
            raise ErreurExplicabilite(f"{self.actif} XGBoost {d['nom']} : modèle ré-entraîné différent ({ecart}).")
        return modeles, ecart

    def tft(self, d: dict, g: int):
        """TFT reconstruit et rechargé depuis ses poids ; contrôle de reproduction ; renvoie aussi son jeu d'évaluation."""
        import torch
        from pytorch_forecasting import TemporalFusionTransformer
        import reseaux
        u = self.unite_dl("TFT", d, g)
        c = self.choix["TFT"]["combinaison"]
        table = T.table_tft(self.journalier, self.norm(d))
        p = self.parties(d)
        jeu_aj = T.jeu_tft(table, list(p["ajustement"]["date_cible"]), LONGUEUR)
        jeu_ev = T.jeu_tft(table, list(p["evaluation"]["date_cible"]), LONGUEUR, reference=jeu_aj)
        tft = TemporalFusionTransformer.from_dataset(
            jeu_aj, hidden_size=c["hidden_size"], attention_head_size=c["tetes_attention"],
            hidden_continuous_size=c["hidden_continuous_size"], dropout=c["dropout"], loss=reseaux.perte_mse_tft(),
            learning_rate=c["taux_apprentissage"], optimizer="adamw", weight_decay=c["weight_decay"], output_size=1)
        tft.load_state_dict(torch.load(K.DOSSIER_DL / u["poids"], weights_only=True))
        tft.eval()
        prev, jours = T.prevoir_tft(tft, jeu_ev)
        if jours != [(j - dt.date(1970, 1, 1)).days for j in p["evaluation"]["date_cible"]]:
            raise ErreurExplicabilite(f"{self.actif} TFT {d['nom']} : ordre des échantillons inattendu.")
        n = self.norm(d)
        ecart = float(np.max(np.abs(prev * n["cible_ecart_type"] + n["cible_moyenne"] - np.array(u["evaluation"]["prevision_log"]))))
        if ecart > self.regles["explicabilite"]["precisions"]["reproduction_tolerance"]:
            raise ErreurExplicabilite(f"{self.actif} TFT {d['nom']} graine {g} : TFT rechargé différent ({ecart}).")
        return tft, jeu_ev, ecart


# --- Unités de calcul ----------------------------------------------------------------------------

def calcul_shap_reseau(ctx: Contexte, modele: str, d: dict, g: int) -> dict:
    xp = ctx.regles["explicabilite"]["precisions"]
    r, ecart = ctx.reseau(modele, d, g)
    xa = ctx.x(d, "ajustement")
    fond = xa[np.sort(np.random.default_rng(xp["shap_graine"]).choice(len(xa), xp["shap_fond_reseaux"], replace=False))]
    s = shap_reseau(r, ctx.x(d, "evaluation"), fond, xp["shap_tirages_reseaux"], xp["shap_graine"])
    if s["additivite_erreur_relative"] > xp["additivite_tolerance_reseaux"]:
        raise ErreurExplicabilite(f"ARRÊT : additivité de SHAP non vérifiée pour {ctx.actif} {modele} {d['nom']} graine {g} "
                                  f"({s['additivite_erreur_relative']:.4f} > {xp['additivite_tolerance_reseaux']}).")
    sigma = ctx.norm(d)["cible_ecart_type"]
    return {"importance": (importance_par_element(s["phi"], ctx.regles) * sigma).tolist(),
            "additivite_erreur_relative": s["additivite_erreur_relative"], "additivite_residu_max_log": s["additivite_residu_max"] * sigma,
            "reproduction_ecart": ecart, "jours": int(len(s["prevision"]))}


def calcul_xgboost(ctx: Contexte, d: dict) -> dict:
    import shap
    xp = ctx.regles["explicabilite"]["precisions"]
    modeles, ecart = ctx.xgboost(d)
    x = B.entrees(ctx.parties(d)["evaluation"], ctx.regles)
    importances, residus = [], []
    for mx in modeles:
        ex = shap.TreeExplainer(mx)
        phi = np.asarray(ex.shap_values(x), dtype="float64")
        residus.append(float(np.max(np.abs(phi.sum(axis=1) + float(np.ravel(ex.expected_value)[0]) - mx.predict(x, output_margin=True)))))
        importances.append(np.abs(phi).mean(axis=0))
    if max(residus) > xp["additivite_tolerance_xgboost"]:
        raise ErreurExplicabilite(f"ARRÊT : additivité de SHAP non vérifiée pour {ctx.actif} XGBoost {d['nom']} ({max(residus)}).")
    return {"importance_par_graine": [i.tolist() for i in importances], "additivite_residu_max": max(residus),
            "reproduction_ecart": ecart, "jours": int(len(x))}


def calcul_attention_transformer(ctx: Contexte, d: dict, g: int) -> dict:
    import torch
    r, ecart = ctx.reseau("Transformer", d, g)
    with torch.no_grad():
        r(torch.from_numpy(ctx.x(d, "evaluation")))
    lignes = [c.attention.derniers_poids[:, :, -1, :].mean(dim=1).numpy().astype("float64") for c in r.couches]
    attention = np.mean(lignes, axis=0)[:, ::-1]               # (jours, 30) ; retard 1 en premier
    return {"dates_cible": [str(j) for j in ctx.parties(d)["evaluation"]["date_cible"]], "attention": attention.tolist(),
            "reproduction_ecart": ecart}


def calcul_tft(ctx: Contexte, d: dict, g: int) -> dict:
    import torch
    tft, jeu, ecart = ctx.tft(d, g)
    variables_enc, attention = [], []
    with torch.no_grad():
        for x, _ in jeu.to_dataloader(train=False, batch_size=256, num_workers=0):
            i = tft.interpret_output(tft(x), reduction="none")
            variables_enc.append(i["encoder_variables"].numpy())
            attention.append(i["attention"].numpy())
    return {"variables": list(tft.encoder_variables), "importance": np.concatenate(variables_enc).mean(axis=0).tolist(),
            "attention_par_retard": np.concatenate(attention).mean(axis=0)[::-1].tolist(), "reproduction_ecart": ecart}


def unites_actif(ctx: Contexte, retenu: str) -> list[tuple[str, callable]]:
    graines = ctx.regles["modeles"]["graines_deep_learning"]
    u = []
    for d in ctx.plis:
        u.append((f"{VERSION}|{ctx.actif}|XGBoost|shap|{d['nom']}|{ctx.cle}", lambda d=d: calcul_xgboost(ctx, d)))
        for g in graines:
            u.append((f"{VERSION}|{ctx.actif}|Transformer|attention|{d['nom']}|graine {g}|{ctx.cle}",
                      lambda d=d, g=g: calcul_attention_transformer(ctx, d, g)))
            u.append((f"{VERSION}|{ctx.actif}|TFT|interpretation|{d['nom']}|graine {g}|{ctx.cle}", lambda d=d, g=g: calcul_tft(ctx, d, g)))
    for modele in dict.fromkeys(["LSTM", retenu]):
        for d in ctx.plis:
            for g in graines:
                u.append((f"{VERSION}|{ctx.actif}|{modele}|shap|{d['nom']}|graine {g}|{ctx.cle}",
                          lambda m=modele, d=d, g=g: calcul_shap_reseau(ctx, m, d, g)))
    return u


# --- Agrégation ----------------------------------------------------------------------------------

def _lire(identifiant: str) -> dict:
    u = P.lire_unite(DOSSIER, identifiant)
    if u is None:
        raise ErreurExplicabilite(f"Unité absente : {identifiant}")
    return u


def _parts(valeurs: dict) -> dict:
    total = sum(valeurs.values())
    return {k: v / total for k, v in valeurs.items()}


def agreger_actif(ctx: Contexte, retenu: str) -> dict:
    regles, cle, a = ctx.regles, ctx.cle, ctx.actif
    noms = variables(regles)
    graines = regles["modeles"]["graines_deep_learning"]
    xp = regles["explicabilite"]["precisions"]
    sortie = {"modele_retenu": retenu, "shap": {}, "fidelite": {}}
    # XGBoost
    par_pli = {}
    for d in ctx.plis:
        u = _lire(f"{VERSION}|{a}|XGBoost|shap|{d['nom']}|{cle}")
        par_pli[d["nom"]] = {"importance": dict(zip(noms, np.mean(u["importance_par_graine"], axis=0).tolist())),
                             "additivite_residu_max": u["additivite_residu_max"], "reproduction_ecart": u["reproduction_ecart"]}
    sortie["shap"]["XGBoost"] = _resume_shap(par_pli, noms, None)
    # Réseaux expliqués par SHAP
    for modele in dict.fromkeys(["LSTM", retenu]):
        par_pli = {}
        for d in ctx.plis:
            us = [_lire(f"{VERSION}|{a}|{modele}|shap|{d['nom']}|graine {g}|{cle}") for g in graines]
            imp = np.mean([u["importance"] for u in us], axis=0)                 # (30 retards, variables)
            par_pli[d["nom"]] = {"importance": dict(zip(noms, imp.sum(axis=0).tolist())), "par_retard": imp.sum(axis=1).tolist(),
                                 "additivite_erreur_relative_max": max(u["additivite_erreur_relative"] for u in us),
                                 "reproduction_ecart": max(u["reproduction_ecart"] for u in us)}
        sortie["shap"][modele] = _resume_shap(par_pli, noms, True)
    # Fidélité, sur la validation interne de chaque pli
    cols = colonnes_variable(regles)
    for modele in ["XGBoost"] + list(dict.fromkeys(["LSTM", retenu])):
        res = {}
        for d in ctx.plis:
            p = ctx.parties(d)
            cible = p["validation"]["cible"].to_numpy()
            importance = sortie["shap"][modele]["par_pli"][d["nom"]]["importance"]
            if modele == "XGBoost":
                modeles, _ = ctx.xgboost(d)
                x = B.entrees(p["validation"], regles)
                predire = lambda z, ms=modeles: np.mean([m.predict(z).astype("float64") for m in ms], axis=0)  # noqa: E731
                colonnes = {v: [k] for k, v in enumerate(noms)}
            else:
                reseaux_ = [ctx.reseau(modele, d, g)[0] for g in graines]
                n = ctx.norm(d)
                x = ctx.x(d, "validation")
                predire = lambda z, rs=reseaux_, n=n: np.mean(  # noqa: E731
                    [T.prevoir_torch(r, z) * n["cible_ecart_type"] + n["cible_moyenne"] for r in rs], axis=0)
                colonnes = cols
            s2, _ = B.s2_et_biais(cible, predire(x))
            res[d["nom"]] = fidelite(predire, x, cible, s2, importance, colonnes, xp["fidelite_repetitions"], xp["fidelite_graine"])
        sortie["fidelite"][modele] = {"par_pli": res, "plis_fideles": sum(r["fidele"] for r in res.values()), "plis": len(res)}
    # Attention du Transformer : crises contre autres jours
    par_jour = {}
    for d in ctx.plis:
        us = [_lire(f"{VERSION}|{a}|Transformer|attention|{d['nom']}|graine {g}|{cle}") for g in graines]
        att = np.mean([u["attention"] for u in us], axis=0)
        for j, ligne in zip(us[0]["dates_cible"], att):
            par_jour[dt.date.fromisoformat(j)] = ligne
    G.refuser_si_test(list(par_jour), "attention du Transformer")
    crise = np.array([any(c["debut"] <= j <= c["fin"] for c in regles["crises"].values()) for j in par_jour])
    matrice = np.array(list(par_jour.values()))
    sortie["attention_transformer"] = {
        "jours_crises": int(crise.sum()), "jours_autres": int((~crise).sum()),
        "crises": matrice[crise].mean(axis=0).tolist(), "autres": matrice[~crise].mean(axis=0).tolist(),
        "tous": matrice.mean(axis=0).tolist(),
        "reproduction_ecart": max(_lire(f"{VERSION}|{a}|Transformer|attention|{d['nom']}|graine {g}|{cle}")["reproduction_ecart"]
                                  for d in ctx.plis for g in graines)}
    # TFT
    us = [_lire(f"{VERSION}|{a}|TFT|interpretation|{d['nom']}|graine {g}|{cle}") for d in ctx.plis for g in graines]
    sortie["tft"] = {"importance": _parts(dict(zip(us[0]["variables"], np.mean([u["importance"] for u in us], axis=0).tolist()))),
                     "attention_par_retard": np.mean([u["attention_par_retard"] for u in us], axis=0).tolist(),
                     "reproduction_ecart": max(u["reproduction_ecart"] for u in us)}
    return sortie


def _resume_shap(par_pli: dict, noms: list[str], avec_retards) -> dict:
    moyenne = {v: float(np.mean([p["importance"][v] for p in par_pli.values()])) for v in noms}
    sortie = {"importance": moyenne, "parts": _parts(moyenne), "classement": sorted(moyenne, key=moyenne.get, reverse=True),
              "par_pli": par_pli}
    if avec_retards:
        retards = np.mean([p["par_retard"] for p in par_pli.values()], axis=0)
        sortie["par_retard"] = retards.tolist()
        sortie["parts_par_retard"] = (retards / retards.sum()).tolist()
    return sortie


# --- Figures --------------------------------------------------------------------------------------

def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def figure_importance(actif: str, res: dict, chemin: Path) -> None:
    import exploration as X
    plt = _plt()
    modeles = list(res["shap"]) + ["TFT"]
    fig, axes = plt.subplots(1, len(modeles), figsize=(4.2 * len(modeles), 5.2), sharex=False)
    for ax, m in zip(axes, modeles):
        parts = res["tft"]["importance"] if m == "TFT" else res["shap"][m]["parts"]
        ordre = sorted(parts, key=parts.get)
        ax.barh([NOMS_VARIABLES.get(v, v) for v in ordre], [parts[v] for v in ordre], color=X.COULEURS[actif])
        ax.xaxis.set_major_formatter(X.FORMAT_POURCENT)
        titre = f"{m} (SHAP)" if m != "TFT" else "TFT (sélection des variables)"
        ax.set_title(titre + (" — retenu" if m == res["modele_retenu"] else ""), fontsize=10)
        ax.grid(axis="x", alpha=0.3)
        ax.tick_params(axis="y", labelsize=8)
    fig.suptitle(f"{X.NOMS[actif]} : part de chaque variable dans l'importance (moyenne des graines et des 5 plis)")
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    X._finir(fig, chemin)


def figure_retards(actif: str, res: dict, chemin: Path) -> None:
    import exploration as X
    plt = _plt()
    fig, ax = plt.subplots(figsize=(10, 4.8))
    retards = np.arange(1, LONGUEUR + 1)
    couleurs = ["#2563EB", "#7C3AED", "#16A34A"]
    for c, m in zip(couleurs, [m for m in res["shap"] if m != "XGBoost"]):
        ax.plot(retards, res["shap"][m]["parts_par_retard"], marker="o", markersize=3, color=c, label=f"{m} : SHAP")
    ax.plot(retards, res["tft"]["attention_par_retard"], marker="s", markersize=3, color="#D97706", linestyle="--", label="TFT : attention")
    ax.plot(retards, res["attention_transformer"]["tous"], marker="^", markersize=3, color="#999999", linestyle=":",
            label="Transformer : attention")
    ax.yaxis.set_major_formatter(X.FORMAT_POURCENT)
    ax.set_xlabel("Retard (1 = jour J, veille de la cible)")
    ax.set_ylabel("Part du total")
    ax.set_title(f"{X.NOMS[actif]} : importance par retard (SHAP) et attention par retard")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    X._finir(fig, chemin)


def figure_attention(rapport: dict, chemin: Path) -> None:
    import exploration as X
    plt = _plt()
    actifs = list(rapport["actifs"])
    fig, axes = plt.subplots(1, len(actifs), figsize=(6 * len(actifs), 4.6), sharey=True)
    retards = np.arange(1, LONGUEUR + 1)
    for ax, a in zip(axes, actifs):
        at = rapport["actifs"][a]["attention_transformer"]
        ax.plot(retards, at["crises"], color="#DC2626", marker="o", markersize=3,
                label=f"Jours de crise ({C.nombre_fr(at['jours_crises'])} jours)")
        ax.plot(retards, at["autres"], color="#2563EB", marker="o", markersize=3,
                label=f"Autres jours ({C.nombre_fr(at['jours_autres'])} jours)")
        ax.yaxis.set_major_formatter(X.FORMAT_POURCENT)
        ax.set_xlabel("Retard (1 = jour J, veille de la cible)")
        ax.set_title(f"{X.NOMS[a]} : attention du Transformer par retard")
        ax.grid(alpha=0.3)
        ax.legend()
    axes[0].set_ylabel("Poids d'attention moyen")
    fig.text(0.01, 0.005, "L'attention montre où le modèle regarde, pas nécessairement pourquoi il décide.", fontsize=8, color="#555555")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    X._finir(fig, chemin)


# --- Rapport Markdown généré ----------------------------------------------------------------------

def _n(x: float, d: int = 3) -> str:
    return C.nombre_fr(x, d).replace("-", "−")


def _pc(x: float, d: int = 1) -> str:
    return _n(100 * x, d) + " %"


def _liste(noms: list[str]) -> str:
    return noms[0] if len(noms) == 1 else ", ".join(noms[:-1]) + " et " + noms[-1]


def _v(v: str) -> str:
    return NOMS_VARIABLES.get(v, v)


def rapport_markdown(rapport: dict, regles: dict) -> str:
    xp = regles["explicabilite"]["precisions"]
    lignes = ["# Explicabilité (développement, 2020 à 2024)", "",
              "Fichier généré par `src/explicabilite.py` à partir de `rapports/explicabilite.json` : ne pas le modifier à la main.", "",
              "- SHAP : XGBoost (TreeExplainer, exact) ; LSTM et modèle retenu de chaque actif (GradientExplainer, "
              f"{C.nombre_fr(xp['shap_tirages_reseaux'])} tirages, fond de {xp['shap_fond_reseaux']} séquences de la fenêtre d'ajustement). "
              "Contributions en unités de log(RV) ; importance = moyenne des valeurs absolues sur les jours évalués, puis somme ; "
              "moyenne des 3 graines, puis des 5 plis. Retard 1 = jour J, veille de la cible.",
              "- Les modèles expliqués sont exactement ceux qui ont été évalués (réseaux rechargés, XGBoost ré-entraîné ; contrôle à 1e-9).",
              "- Fidélité : sur la validation interne de chaque pli, la meilleure et la moins bonne variable SHAP sont permutées "
              f"({xp['fidelite_repetitions']} répétitions, graine {xp['fidelite_graine']}) ; fidèle si la meilleure dégrade plus le QLIKE.",
              "- **Limite : l'attention montre où le modèle regarde, pas nécessairement pourquoi il décide.**", ""]
    for actif, res in rapport["actifs"].items():
        lignes += [f"## {actif}", "", f"Modèle retenu : **{res['modele_retenu']}**.", "", "### Les 5 variables les plus importantes", "",
                   "| Modèle | 1 | 2 | 3 | 4 | 5 |", "|---|---|---|---|---|---|"]
        for m, s in res["shap"].items():
            lignes.append(f"| {m} (SHAP) | " + " | ".join(f"{_v(v)} ({_pc(s['parts'][v])})" for v in s["classement"][:5]) + " |")
        t = res["tft"]["importance"]
        lignes.append("| TFT (sélection des variables) | " + " | ".join(f"{_v(v)} ({_pc(t[v])})" for v in sorted(t, key=t.get, reverse=True)[:5]) + " |")
        lignes += ["", "### Importance par retard (part du total)", "", "| Modèle | Retard 1 | Retard 2 | Retard 3 | Retards 1 à 5 | Retards 6 à 30 |",
                   "|---|---:|---:|---:|---:|---:|"]
        series = {f"{m} (SHAP)": s["parts_par_retard"] for m, s in res["shap"].items() if m != "XGBoost"}
        series["TFT (attention)"] = res["tft"]["attention_par_retard"]
        series["Transformer (attention)"] = res["attention_transformer"]["tous"]
        for nom, p in series.items():
            lignes.append(f"| {nom} | {_pc(p[0])} | {_pc(p[1])} | {_pc(p[2])} | {_pc(sum(p[:5]))} | {_pc(sum(p[5:]))} |")
        at = res["attention_transformer"]
        lignes += ["", "### Attention du Transformer : jours de crise contre autres jours", "",
                   f"Jours de crise : {C.nombre_fr(at['jours_crises'])} ; autres jours : {C.nombre_fr(at['jours_autres'])}.", "",
                   "| Jours | Retard 1 | Retard 2 | Retard 3 | Retards 1 à 5 | Retards 6 à 30 |", "|---|---:|---:|---:|---:|---:|"]
        for nom, p in (("Crises", at["crises"]), ("Autres", at["autres"])):
            lignes.append(f"| {nom} | {_pc(p[0])} | {_pc(p[1])} | {_pc(p[2])} | {_pc(sum(p[:5]))} | {_pc(sum(p[5:]))} |")
        lignes += ["", "### Fidélité par pli", "",
                   "| Modèle | Pli | Meilleure variable | Dégradation | Moins bonne variable | Dégradation | Fidèle |", "|---|---|---|---:|---|---:|---|"]
        for m, f in res["fidelite"].items():
            for pli, r in f["par_pli"].items():
                lignes.append(f"| {m} | {pli} | {_v(r['meilleure'])} | {_n(r['degradation_meilleure'], 4)} | {_v(r['moins_bonne'])} | "
                              f"{_n(r['degradation_moins_bonne'], 4)} | {'oui' if r['fidele'] else 'non'} |")
        lignes += ["", "Dégradation : QLIKE moyen sur la validation interne avec la variable permutée, moins QLIKE sans permutation.", "",
                   "### Contrôles", "", "| Modèle | Reproduction (écart maximal) | Additivité |", "|---|---:|---|"]
        for m, s in res["shap"].items():
            pp = s["par_pli"].values()
            if m == "XGBoost":
                add = f"écart maximal {_n(max(p['additivite_residu_max'] for p in pp), 7)} (tolérance {_n(xp['additivite_tolerance_xgboost'], 4)})"
            else:
                add = (f"erreur relative maximale {_pc(max(p['additivite_erreur_relative_max'] for p in pp), 2)} "
                       f"(tolérance {_pc(xp['additivite_tolerance_reseaux'], 0)})")
            lignes.append(f"| {m} | {_n(max(p['reproduction_ecart'] for p in pp), 12)} | {add} |")
        lignes.append(f"| Transformer (attention) | {_n(at['reproduction_ecart'], 12)} | — |")
        lignes.append(f"| TFT | {_n(res['tft']['reproduction_ecart'], 12)} | — |")
        lignes += ["", f"Figures : `figures/figure_7_importance_variables_{actif}.png`, `figures/figure_8_importance_retards_{actif}.png`.", ""]
    lignes += ["Figure de l'attention du Transformer : `figures/figure_9_attention_transformer.png`.", ""]
    lignes += lecture_des_resultats(rapport)
    return "\n".join(lignes) + "\n"


def lecture_des_resultats(rapport: dict) -> list[str]:
    """Phrases d'interprétation, chacune conditionnée par les valeurs du JSON."""
    lignes = ["## Lecture des résultats", "", "Chaque phrase ci-dessous est générée à partir des valeurs de `rapports/explicabilite.json`.", ""]
    for actif, res in rapport["actifs"].items():
        nom = actif.replace("USDT", "")
        tetes = {m: s["classement"][0] for m, s in res["shap"].items()}
        if len(set(tetes.values())) == 1:
            lignes.append(f"- {nom} : les {len(tetes)} modèles expliqués par SHAP placent la même variable en tête : {_v(next(iter(tetes.values())))}.")
        else:
            lignes.append(f"- {nom} : la variable en tête n'est pas la même pour tous les modèles : "
                          + " ; ".join(f"{m} : {_v(v)}" for m, v in tetes.items()) + ".")
        for m, s in res["shap"].items():
            familles = {"volatilité passée": [v for v in s["parts"] if v.startswith(("rv_", "log_rv_")) or v in ("parkinson", "garman_klass")]}
            part = sum(s["parts"][v] for v in familles["volatilité passée"])
            lignes.append(f"- {nom} : pour {m}, les mesures de volatilité passée (RV, Parkinson, Garman-Klass) pèsent {_pc(part)} de "
                          f"l'importance{' : l’essentiel' if part > 0.5 else ''}.")
        for m, s in res["shap"].items():
            if m == "XGBoost":
                continue
            p = s["parts_par_retard"]
            lignes.append(f"- {nom} : pour {m}, les 5 derniers jours portent {_pc(sum(p[:5]))} de l'importance SHAP"
                          + (" : le modèle s'appuie surtout sur le passé récent." if sum(p[:5]) > 0.5 else
                             " : le modèle utilise aussi largement les jours plus anciens.")
                          + f" Le retard le plus important est le retard {int(np.argmax(p)) + 1}.")
        reseaux_jour = [m for m, s in res["shap"].items() if m != "XGBoost" and "jour_semaine" in s["classement"][:2]]
        confirme = [m for m in reseaux_jour if any(r["meilleure"] == "jour_semaine" and r["fidele"]
                                                   for r in res["fidelite"][m]["par_pli"].values())]
        if reseaux_jour:
            lignes.append(f"- {nom} : le jour de la semaine est dans les 2 premières variables de {_liste(reseaux_jour)}. Son importance SHAP "
                          "additionne 7 colonnes (codage en one-hot), ce qui peut la grossir"
                          + (f" ; mais la permutation, qui ne dépend pas de ce codage, confirme son poids pour {_liste(confirme)} "
                             "(meilleure variable d'au moins un pli où le modèle est fidèle)" if confirme else "")
                          + ". HAR-RV n'utilise pas le jour de la semaine : c'est une explication possible, non démontrée, d'une partie "
                            "du gain des réseaux.")
        xg = res["fidelite"]["XGBoost"]["par_pli"]
        ameliore = [p for p, r in xg.items() if r["degradation_meilleure"] < 0]
        if ameliore:
            lignes.append(f"- {nom} : pour XGBoost, permuter la meilleure variable SHAP AMÉLIORE le QLIKE de validation sur {_liste(ameliore)}. "
                          "Explication possible, non démontrée : les mesures de volatilité (RV, Parkinson, Garman-Klass) sont très "
                          "corrélées ; SHAP répartit le mérite entre elles, et la permutation d'une seule crée des combinaisons "
                          "irréalistes que les arbres traitent mal.")
        at = res["attention_transformer"]
        uniforme = 1 / LONGUEUR
        for nom_att, serie in (("du Transformer", at["tous"]), ("du TFT", res["tft"]["attention_par_retard"])):
            if max(serie) < 1.5 * uniforme:
                lignes.append(f"- {nom} : l'attention {nom_att} est presque uniforme : au plus {_pc(max(serie))} par retard, pour "
                              f"{_pc(uniforme)} si tous les retards avaient le même poids ; elle ne distingue presque pas les jours.")
        t = res["tft"]["importance"]
        if "y" in t and "log_rv_1" in t:
            lignes.append(f"- {nom} : le TFT voit deux fois le log de la RV du jour (sa série « y » et la variable log_rv_1) : leurs "
                          f"importances ({_pc(t['y'])} et {_pc(t['log_rv_1'])}) se partagent la même information.")
        rc, ra = sum(at["crises"][:5]), sum(at["autres"][:5])
        lignes.append(f"- {nom} : pendant les crises, l'attention du Transformer sur les 5 derniers jours est "
                      f"{'plus forte' if rc > ra else 'plus faible ou égale'} que les autres jours ({_pc(rc)} contre {_pc(ra)}) "
                      "(descriptif ; l'attention montre où le modèle regarde, pas nécessairement pourquoi il décide).")
        for m, f in res["fidelite"].items():
            non = [p for p, r in f["par_pli"].items() if not r["fidele"]]
            lignes.append(f"- {nom} : {m} est fidèle sur {f['plis_fideles']} plis sur {f['plis']}"
                          + (f" ; pas fidèle sur {_liste(non)} : sur ce{'s' if len(non) > 1 else ''} pli{'s' if len(non) > 1 else ''}, "
                             "le classement SHAP ne correspond pas à l'effet réel de la permutation, et SHAP échoue à expliquer ce modèle."
                             if non else " : le classement SHAP correspond à l'effet réel de la permutation sur chaque pli."))
    return lignes + [""]


# --- Exécution ---------------------------------------------------------------------------------

def executer(regles: dict) -> dict:
    import torch  # noqa: F401
    C.verifier_secteur(contexte="explicabilité")
    C.verifier_memoire_libre(regles)
    T.configurer_torch(regles)
    comparaison = json.loads(K.CHEMIN_JSON.read_text(encoding="utf-8"))
    rapport = {"version": VERSION, "periode": [str(R.decoupages(regles)[0]["evaluation"][0]), str(R.decoupages(regles)[-2]["evaluation"][1])],
               "depend_de": {"comparaison_modeles_sha256": K._sha256(K.CHEMIN_JSON),
                             "modeles_deep_learning_sha256": K._sha256(K.CHEMIN_MANIFESTE)}, "actifs": {}}
    for actif in regles["donnees"]["actifs"]:
        retenu = comparaison["actifs"][actif]["classement"]["modele_retenu"]
        ctx = Contexte(actif, regles)
        unites = unites_actif(ctx, retenu)
        calculs = dict(unites)
        debut = time.perf_counter()
        etat = {"n": 0}

        def calcul(identifiant: str, _graine: int, calculs=calculs) -> dict:
            t = time.perf_counter()
            r = calculs[identifiant]()
            etat["n"] += 1
            print(f"[{time.strftime('%H:%M:%S')}] {identifiant.split('|')[1]} {' '.join(identifiant.split('|')[2:-1])} : "
                  f"{time.perf_counter() - t:.1f} s", flush=True)
            return r

        bilan = P.executer([u for u, _ in unites], calcul, DOSSIER)
        print(f"{actif} : {bilan} en {C.nombre_fr(time.perf_counter() - debut, 1)} s", flush=True)
        rapport["actifs"][actif] = agreger_actif(ctx, retenu)
    for actif, res in rapport["actifs"].items():
        figure_importance(actif, res, C.RACINE / "figures" / f"figure_7_importance_variables_{actif}.png")
        figure_retards(actif, res, C.RACINE / "figures" / f"figure_8_importance_retards_{actif}.png")
    figure_attention(rapport, C.RACINE / "figures" / "figure_9_attention_transformer.png")
    C.ecrire_texte(CHEMIN_JSON, C.texte_json(rapport))
    C.ecrire_texte(CHEMIN_MD, rapport_markdown(rapport, regles))
    return rapport


def main() -> int:
    C.proteger_sortie()
    regles = R.charger_regles()
    try:
        rapport = executer(regles)
    except (G.ErreurTestAveugle, ErreurExplicabilite, K.ErreurComparaison, C.ErreurAlimentation, C.ErreurMemoire) as erreur:
        print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1
    for actif, res in rapport["actifs"].items():
        print(f"{actif} | " + " | ".join(f"{m} : {', '.join(s['classement'][:3])}" for m, s in res["shap"].items())
              + " | fidélité : " + ", ".join(f"{m} {f['plis_fideles']}/{f['plis']}" for m, f in res["fidelite"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
