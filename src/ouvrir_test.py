"""Ouverture du test final : le SEUL chemin qui lève la garde du test aveugle.

Règles : config/regles.toml, section test_final ; config/attentes_test.toml ; docs/REGLES.md, section 17 ;
docs/ATTENTES_TEST.md. Écrites et commitées avant l'ouverture.

Deux modes, exactement la même chaîne de calcul :
- `--verification` : sur 2024 (pli 5), avec les modèles du pli 5 ; la garde reste FERMÉE (2024 est dans le
  développement) ; résultats comparés aux chiffres déjà publiés pour 2024 ; écrit rapports/verification_test_2024.json.
- `--ouvrir` : sur le test final, avec les modèles du découpage du test final ; écrit rapports/test_final.json en
  création exclusive. À ne lancer qu'une seule fois, après l'accord explicite de l'auteur.

Avant tout calcul, dans les deux modes : dépôt propre, commit local égal à origin/main (et au dépôt distant),
fichiers des attentes dans le commit poussé, empreintes de tous les modèles et normalisations vérifiées.
Données coupées à la fin de la période évaluée. Aucun réentraînement (sauf XGBoost du pli 5 en vérification,
dont les modèles n'avaient pas été enregistrés : ré-entraîné à l'identique et contrôlé à 1e-9).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import sys
import tomllib
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
import har_j as HJ  # noqa: E402
import regles as R  # noqa: E402
import reprise as P  # noqa: E402
import strategie as S  # noqa: E402
import variables as V  # noqa: E402

LONGUEUR = 30
CHEMIN_ATTENTES = C.RACINE / "config" / "attentes_test.toml"
FICHIERS_ATTENTES = ["config/attentes_test.toml", "docs/ATTENTES_TEST.md"]
MODELES = ["Persistance", "HAR-RV", "HAR-J", "GARCH(1,1)", "XGBoost"] + list(T.MODELES)
REGLES_MODELES = ["XGBoost"] + list(T.MODELES)
COMPARES_A_HAR = ["GARCH(1,1)", "XGBoost"] + list(T.MODELES)          # famille de Holm descriptive (7)


class ErreurOuverture(Exception):
    pass


# --- Préconditions ------------------------------------------------------------------------------

def _git(racine: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=racine, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise ErreurOuverture(f"git {' '.join(args)} a échoué : {r.stderr.strip()}")
    return r.stdout.strip()


def verifier_depot(racine: Path, distant: bool = True) -> str:
    """Dépôt propre, commit local = origin/main (et = dépôt distant si `distant`), attentes dans le commit poussé."""
    if _git(racine, "status", "--porcelain"):
        raise ErreurOuverture("Refusé : le dépôt n'est pas propre (git status). Commitez et poussez d'abord.")
    local, origine = _git(racine, "rev-parse", "HEAD"), _git(racine, "rev-parse", "origin/main")
    if local != origine:
        raise ErreurOuverture(f"Refusé : le commit local ({local[:7]}) diffère de origin/main ({origine[:7]}).")
    if distant:
        ligne = _git(racine, "ls-remote", "origin", "refs/heads/main")
        if not ligne or ligne.split()[0] != local:
            raise ErreurOuverture("Refusé : le commit local n'est pas celui du dépôt distant (git ls-remote).")
    suivis = set(_git(racine, "ls-tree", "-r", "--name-only", "HEAD", "--", *FICHIERS_ATTENTES).splitlines())
    manquants = [f for f in FICHIERS_ATTENTES if f not in suivis]
    if manquants:
        raise ErreurOuverture(f"Refusé : fichiers des attentes absents du commit poussé : {manquants}.")
    return local


def _sha256(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def verifier_fichiers(attendus: dict[Path, str]) -> int:
    """Refuse si un fichier manque ou si son empreinte diffère de celle du manifeste."""
    problemes = [f"{p.name} : absent" for p in attendus if not p.exists()]
    problemes += [f"{p.name} : empreinte différente" for p, h in attendus.items() if p.exists() and _sha256(p) != h]
    if problemes:
        raise ErreurOuverture("Refusé : modèles non conformes à leurs manifestes : " + " ; ".join(problemes[:10]))
    return len(attendus)


def empreintes_attendues(regles: dict, decoupage: dict) -> dict[Path, str]:
    """Tous les fichiers de modèles et de normalisation du découpage, avec leur empreinte publiée."""
    nom = decoupage["nom"].replace(" ", "_")
    actifs = regles["donnees"]["actifs"]
    dl = json.loads(K.CHEMIN_MANIFESTE.read_text(encoding="utf-8"))
    poids = {K.DOSSIER_DL / p: h for p, h in dl["poids"].items() if p.split("/")[-1].startswith(f"{nom}_graine_")}
    normes = {K.DOSSIER_DL / p: h for p, h in dl["normalisations"].items() if p.split("/")[-1] == f"{nom}.json"}
    if len(poids) != len(actifs) * len(T.MODELES) * len(regles["modeles"]["graines_deep_learning"]) or len(normes) != len(actifs):
        raise ErreurOuverture(f"Manifeste incomplet pour {decoupage['nom']} : {len(poids)} poids, {len(normes)} normalisations.")
    sortie = {**poids, **normes}
    if decoupage["nom"] == "test final":
        for manifeste, attendus in ((B.CHEMIN_MANIFESTE_MODELES, 4), (HJ.CHEMIN_MANIFESTE, 1)):
            m = json.loads(manifeste.read_text(encoding="utf-8"))["modeles"]
            if sorted(m) != sorted(actifs) or any(len(f) != attendus for f in m.values()):
                raise ErreurOuverture(f"Manifeste incomplet : {manifeste.name}.")
            sortie.update({B.DOSSIER_MODELES / a / f: h for a, fichiers in m.items() for f, h in fichiers.items()})
    return sortie


def ecrire_exclusif(chemin: Path, texte: str) -> None:
    """Création exclusive : refus si le fichier existe déjà."""
    try:
        with open(chemin, "x", encoding="utf-8", newline="\n") as f:
            f.write(texte)
    except FileExistsError as e:
        raise ErreurOuverture(f"Refusé : {chemin.name} existe déjà ; le test final ne s'ouvre qu'une fois.") from e


# --- Modèles d'un découpage ---------------------------------------------------------------------

class Modeles:
    """Charge les modèles d'un découpage et prévoit (log RV ou variance) sur des exemples."""

    def __init__(self, actif: str, decoupage: dict, regles: dict, exemples: pd.DataFrame, journalier_reseaux: pd.DataFrame,
                 journalier: pd.DataFrame):
        self.actif, self.d, self.regles = actif, decoupage, regles
        self.exemples, self.jr, self.jb = exemples, journalier_reseaux, journalier
        self.cle = T._cle_donnees(regles)
        self.final = decoupage["nom"] == "test final"
        self.unite_b = K._unite(B.DOSSIER_REPRISE, f"{B.VERSION}|{actif}|baselines|{decoupage['nom']}|{self.cle}")
        self.unite_hj = K._unite(HJ.DOSSIER_REPRISE, HJ.identifiant(actif, decoupage, self.cle))
        self.choix = json.loads((K.DOSSIER_DL / "reglage.json").read_text(encoding="utf-8"))[actif]
        if self.final:
            hg = json.loads((B.DOSSIER_MODELES / actif / "har_garch.json").read_text(encoding="utf-8"))
            self.har, self.garch = np.array(hg["har_coefficients"]), hg["garch"]
            self.har_j = np.array(json.loads((B.DOSSIER_MODELES / actif / "har_j.json").read_text(encoding="utf-8"))["coefficients"])
            import xgboost as xgb
            self.xgb = []
            for g in regles["modeles"]["graines_deep_learning"]:
                m = xgb.XGBRegressor()
                m.load_model(str(B.DOSSIER_MODELES / actif / f"xgboost_graine_{g}.json"))
                self.xgb.append(m)
        else:
            self.har, self.garch = np.array(self.unite_b["har_coefficients"]), self.unite_b["garch"]
            self.har_j = np.array(self.unite_hj["coefficients"])
            self.xgb = self._xgboost_reentraine()
        self.norm = json.loads((K.DOSSIER_DL / "normalisation" / actif / f"{decoupage['nom'].replace(' ', '_')}.json").read_text(encoding="utf-8"))
        self.tableau = T.tableau_normalise(self.jr, self.norm)
        self._reseaux, self._tft = {}, {}

    def _xgboost_reentraine(self) -> list:
        identifiant = f"{B.VERSION}|{self.actif}|baselines|{self.d['nom']}|{self.cle}"
        graines = [P.graine_unite(f"{identifiant}|graine {g}") for g in self.regles["modeles"]["graines_deep_learning"]]
        comb = json.loads(B.CHEMIN_JSON.read_text(encoding="utf-8"))["actifs"][self.actif]["xgboost_reglage"]["combinaison_retenue"]
        m = B.masques(self.exemples, self.d)
        aj, val = self.exemples[m["ajustement"]], self.exemples[m["validation"]]
        return [B.entrainer_xgboost(B.entrees(aj, self.regles), aj["cible"].to_numpy(), B.entrees(val, self.regles), val["cible"].to_numpy(),
                                    comb, g, self.regles) for g in graines]

    def _reseau(self, modele: str, g: int):
        import torch
        import reseaux
        if (modele, g) not in self._reseaux:
            r = reseaux.construire_reseau(modele, self.choix[modele]["combinaison"], self.tableau.shape[1], LONGUEUR)
            r.load_state_dict(torch.load(K.DOSSIER_DL / "poids" / self.actif / modele / f"{self.d['nom'].replace(' ', '_')}_graine_{g}.pt",
                                         weights_only=True))
            self._reseaux[(modele, g)] = r.eval()
        return self._reseaux[(modele, g)]

    def _tft_et_reference(self, g: int):
        import torch
        from pytorch_forecasting import TemporalFusionTransformer
        import reseaux
        if g not in self._tft:
            c = self.choix["TFT"]["combinaison"]
            table = T.table_tft(self.jr, self.norm)
            aj = self.exemples[B.masques(self.exemples, self.d)["ajustement"]]
            jeu_aj = T.jeu_tft(table, list(aj["date_cible"]), LONGUEUR)
            tft = TemporalFusionTransformer.from_dataset(
                jeu_aj, hidden_size=c["hidden_size"], attention_head_size=c["tetes_attention"],
                hidden_continuous_size=c["hidden_continuous_size"], dropout=c["dropout"], loss=reseaux.perte_mse_tft(),
                learning_rate=c["taux_apprentissage"], optimizer="adamw", weight_decay=c["weight_decay"], output_size=1)
            tft.load_state_dict(torch.load(K.DOSSIER_DL / "poids" / self.actif / "TFT" / f"{self.d['nom'].replace(' ', '_')}_graine_{g}.pt",
                                           weights_only=True))
            self._tft[g] = (tft.eval(), table, jeu_aj)
        return self._tft[g]

    def prevoir_log(self, modele: str, ex: pd.DataFrame) -> list[np.ndarray]:
        """Prévisions en log(RV) : une série par graine pour les modèles réglés, une seule sinon."""
        if modele == "Persistance":
            return [B.prevoir_persistance(ex)]
        if modele == "HAR-RV":
            return [B.prevoir_har(ex, self.har, self.regles)]
        if modele == "HAR-J":
            return [HJ.prevoir(ex, self.har_j, self.regles)]
        if modele == "XGBoost":
            x = B.entrees(ex, self.regles)
            return [m.predict(x).astype("float64") for m in self.xgb]
        mu, sigma = self.norm["cible_moyenne"], self.norm["cible_ecart_type"]
        sortie = []
        for g in self.regles["modeles"]["graines_deep_learning"]:
            if modele == "TFT":
                tft, table, jeu_aj = self._tft_et_reference(g)
                jeu = T.jeu_tft(table, list(ex["date_cible"]), LONGUEUR, reference=jeu_aj)
                prev, jours = T.prevoir_tft(tft, jeu)
                if jours != [(j - dt.date(1970, 1, 1)).days for j in ex["date_cible"]]:
                    raise ErreurOuverture(f"{self.actif} TFT : ordre des échantillons inattendu.")
            else:
                prev = T.prevoir_torch(self._reseau(modele, g), T.sequences(self.tableau, self.jr.index, list(ex["date_origine"]), LONGUEUR))
            sortie.append(prev * sigma + mu)
        return sortie

    def reference_validation(self, modele: str) -> list[np.ndarray]:
        """Prévisions de validation enregistrées pendant le calcul d'origine (contrôle de reproduction)."""
        v = self.unite_b["validation"]
        if modele == "Persistance":
            return [np.array(v["persistance_log"])]
        if modele == "HAR-RV":
            return [np.array(v["har_log"])]
        if modele == "HAR-J":
            return [np.array(self.unite_hj["validation"]["prevision_log"])]
        if modele == "XGBoost":
            return [np.array(p) for p in v["xgboost_log_par_graine"]]
        return [np.array(K._unite(K.DOSSIER_DL / "unites", T.id_pli(self.actif, modele, self.d["nom"], g, self.cle))["validation"]["prevision_log"])
                for g in self.regles["modeles"]["graines_deep_learning"]]


# --- La chaîne de calcul --------------------------------------------------------------------------

def _resume(pertes: dict, regles: dict) -> dict:
    return B.resume_pertes(pertes, regles)


def bougies_coupees(actif: str, fin: dt.date) -> pd.DataFrame:
    """Bougies jusqu'à la fin du jour `fin` : aucune bougie postérieure n'entre dans le calcul."""
    b = V.lire_bougies(C.DOSSIER_TRAITE / f"{actif}_5m.parquet")
    return b[(b["date_ouverture"] < pd.Timestamp(fin + dt.timedelta(days=1), tz="UTC")).to_numpy()].reset_index(drop=True)


def controle_modeles_test_final(regles: dict) -> dict:
    """AVANT toute ouverture : les modèles du test final, chargés depuis leurs fichiers, redonnent leurs prévisions de
    validation interne (2024-07-01 à 2024-12-31, développement) ; données coupées à la fin de cette validation."""
    final = R.decoupages(regles)[-1]
    tol = regles["test_final"]["verification_tolerance"]
    sortie = {}
    for actif in regles["donnees"]["actifs"]:
        bougies = bougies_coupees(actif, final["validation"][1])
        exemples, jr = T.donnees_reseaux(bougies, regles)
        _, jb = B.donnees_actif(bougies, regles)
        mod = Modeles(actif, final, regles, exemples, jr, jb)
        val = exemples[B.masques(exemples, final)["validation"]]
        sortie[actif] = {}
        for modele in MODELES:
            if modele == "GARCH(1,1)":
                continue
            ecart = max(float(np.max(np.abs(a - b))) for a, b in zip(mod.prevoir_log(modele, val), mod.reference_validation(modele)))
            if ecart > tol:
                raise ErreurOuverture(f"Modèle du test final {actif} {modele} : prévisions de validation différentes ({ecart}).")
            sortie[actif][modele] = ecart
    return sortie


def _sans_series(sortie: dict) -> dict:
    """Retire les séries journalières (clés commençant par « _ ») : seuls les agrégats sont publiés."""
    for res in sortie["actifs"].values():
        for cle in [k for k in res if k.startswith("_")]:
            res.pop(cle)
        for cle in [k for k in res["strategie"] if k.startswith("_")]:
            res["strategie"].pop(cle)
    return sortie


def chaine(regles: dict, decoupage: dict, garder_series: bool = False) -> dict:
    """Tout le calcul d'une période évaluée : prévisions, métriques, tests, stratégie, VaR. La garde s'applique."""
    tol = regles["test_final"]["verification_tolerance"]
    attentes = tomllib.loads(CHEMIN_ATTENTES.read_text(encoding="utf-8"))
    vol_cible = json.loads(V.CHEMIN_VOL_CIBLE.read_text(encoding="utf-8"))["actifs"]
    debut, fin = decoupage["evaluation"]
    sortie = {"decoupage": decoupage["nom"], "periode": [str(debut), str(fin)], "actifs": {}}
    for actif in regles["donnees"]["actifs"]:
        retenu = attentes["modele_retenu"][actif]
        bougies = bougies_coupees(actif, fin)
        exemples, jr = T.donnees_reseaux(bougies, regles)
        _, jb = B.donnees_actif(bougies, regles)
        mod = Modeles(actif, decoupage, regles, exemples, jr, jb)
        m = B.masques(exemples, decoupage)
        val, ev = exemples[m["validation"]], exemples[m["evaluation"]]
        G.refuser_si_test(ev["date_cible"], f"prévisions sur {decoupage['nom']}")
        # Validation : contrôle de reproduction et s²
        s2, reproduction = {}, {}
        cible_val = val["cible"].to_numpy()
        prev_ev = {}
        for modele in MODELES:
            if modele == "GARCH(1,1)":
                continue
            pv = mod.prevoir_log(modele, val)
            reproduction[modele] = max(float(np.max(np.abs(a - b))) for a, b in zip(pv, mod.reference_validation(modele)))
            if reproduction[modele] > tol:
                raise ErreurOuverture(f"{actif} {modele} : prévisions de validation différentes du calcul d'origine ({reproduction[modele]}).")
            s2[modele] = {"moyenne": B.s2_et_biais(cible_val, np.mean(pv, axis=0))[0], "graines": [B.s2_et_biais(cible_val, p)[0] for p in pv]}
            prev_ev[modele] = mod.prevoir_log(modele, ev)
        # Table des variances prévues sur la période évaluée
        table = pd.DataFrame({"date_cible": list(ev["date_cible"]), "pli": decoupage["nom"], "cible": ev["cible"].to_numpy()})
        for modele in MODELES:
            if modele == "GARCH(1,1)":
                table[modele] = B.prevoir_garch(jb, list(ev["date_origine"]), mod.garch)
                continue
            table[modele] = EV.variance_depuis_log(np.mean(prev_ev[modele], axis=0), s2[modele]["moyenne"])
            if modele in REGLES_MODELES:
                for k, p in enumerate(prev_ev[modele]):
                    table[f"{modele} graine {k}"] = EV.variance_depuis_log(p, s2[modele]["graines"][k])
        res = {"modele_retenu": retenu, "jours": int(len(table)), "reproduction_validation": reproduction,
               "jours_en_crise": int(sum(any(c["debut"] <= j <= c["fin"] for c in regles["crises"].values()) for j in table["date_cible"])),
               "modeles": {}}
        cible = table["cible"].to_numpy()
        pertes = {mm: B.pertes(cible, table[mm].to_numpy()) for mm in MODELES}
        for mm in MODELES:
            res["modeles"][mm] = _resume(pertes[mm], regles)
            if mm in REGLES_MODELES:
                pg = [B.resume_pertes(B.pertes(cible, table[f"{mm} graine {k}"].to_numpy())) for k in range(len(prev_ev[mm]))]
                res["modeles"][mm]["par_graine"] = {x: {"valeurs": [g[x] for g in pg], "moyenne": float(np.mean([g[x] for g in pg])),
                                                        "ecart_type": float(np.std([g[x] for g in pg], ddof=1))} for x in ("qlike", "rmse", "mae")}
        q = {mm: res["modeles"][mm]["qlike"] for mm in MODELES}
        res["gain_sur_har_rv"] = {mm: (q["HAR-RV"] - q[mm]) / q["HAR-RV"] for mm in MODELES}
        res["gain_sur_har_j"] = {mm: (q["HAR-J"] - q[mm]) / q["HAR-J"] for mm in MODELES}
        ref = pertes["HAR-RV"]["qlike"]
        dm = {mm: EV.diebold_mariano(pertes[mm]["qlike"], ref) for mm in COMPARES_A_HAR}
        holm7 = EV.holm({mm: t["p_valeur"] for mm, t in dm.items()})
        for mm, t in dm.items():
            t["p_valeur_holm_7_descriptif"] = holm7[mm]
        res["diebold_mariano"] = dm
        res["diebold_mariano_contre_har_j"] = {retenu: EV.diebold_mariano(pertes[retenu]["qlike"], pertes["HAR-J"]["qlike"])}   # H7
        res["diebold_mariano_descriptif"] = {"HAR-RV contre persistance": EV.diebold_mariano(ref, pertes["Persistance"]["qlike"]),
                                             "HAR-J contre HAR-RV": EV.diebold_mariano(pertes["HAR-J"]["qlike"], ref)}
        res["strategie"], res["var"] = strategie(table, jb, decoupage, regles, vol_cible[actif]["valeur_annualisee"], retenu)
        if garder_series:
            res["_table"] = table[["date_cible", "cible", "HAR-RV", "HAR-J", retenu]].copy()
        sortie["actifs"][actif] = res
    sortie["hypotheses"] = hypotheses(sortie, attentes, regles)
    return sortie


def strategie(table: pd.DataFrame, jb: pd.DataFrame, decoupage: dict, regles: dict, vol_cible: float, retenu: str) -> tuple[dict, dict]:
    debut, fin = decoupage["evaluation"]
    jours = [debut + dt.timedelta(days=k) for k in range((fin - debut).days + 1)]
    G.refuser_si_test(jours, f"stratégie sur {decoupage['nom']}")
    veilles = [debut - dt.timedelta(days=1)] + jours
    j = jb.loc[veilles]
    if j["rendement"].loc[jours].isna().any():
        raise ErreurOuverture("Rendement manquant sur la période évaluée.")
    valide = j["valide"].astype(bool)
    r = np.expm1(j["rendement"].loc[jours].to_numpy())
    t = table.set_index("date_cible")
    modeles = K.SELECTIONNABLES + ["Persistance"]
    expo = {S.ACHAT: np.ones(len(jours))}
    sigma = {}
    for mm in modeles:
        sig = np.sqrt(t[mm]).reindex(veilles)
        sigma[mm] = sig.loc[jours].to_numpy()
        par_origine = pd.Series([sig[o + dt.timedelta(days=1)] for o in veilles[:-1]], index=veilles[:-1])
        expo[mm] = S.exposition_appliquee(S.decisions(par_origine, valide, vol_cible, regles), jours, regles["strategie"]["decalage_execution_jours"])
    sims = {mm: S.simuler(e, r, regles["strategie"]["frais"], regles) for mm, e in expo.items()}
    res = {mm: S.mesures(sims[mm], expo[mm], vol_cible, regles) for mm in sims}
    a = regles["strategie"]["annualisation_jours"]
    res["difference_sharpe_retenu_moins_har"] = EV.bootstrap_statistique(
        [sims[retenu]["rendement"], sims["HAR-RV"]["rendement"]], lambda u, v: S.sharpe(u, a) - S.sharpe(v, a), regles)
    res["_expositions"] = {mm: expo[mm].tolist() for mm in ("HAR-RV", retenu)}
    res["_valeurs"] = {mm: sims[mm]["valeur"].tolist() for mm in (S.ACHAT, "HAR-RV", retenu)}       # pour les figures
    res["_jours"] = [str(x) for x in jours]
    v = valide.to_numpy()
    un_jour = v[1:] & v[:-1]
    var = {"jours_exclus_non_valides": int((~un_jour).sum()),
           "modeles": {mm: S.var_kupiec(sigma[mm], r, un_jour & np.isfinite(sigma[mm]), regles) for mm in modeles}}
    return res, var


def hypotheses(sortie: dict, attentes: dict, regles: dict) -> dict:
    """Verdicts H1 à H6 et prévision chiffrée, selon les règles écrites dans config/attentes_test.toml."""
    actifs = sortie["actifs"]
    dm ={a: r["diebold_mariano"][r["modele_retenu"]] for a, r in actifs.items()}
    holm = EV.holm({a: t["p_valeur"] for a, t in dm.items()})
    seuil = attentes["H1"]["seuil"]
    h1 = {a: {"modele_retenu": actifs[a]["modele_retenu"], "moyenne_difference": dm[a]["moyenne_difference"], "statistique": dm[a]["statistique"],
              "p_valeur": dm[a]["p_valeur"], "p_valeur_holm_2_actifs": holm[a],
              "confirmee": dm[a]["moyenne_difference"] < 0 and holm[a] < seuil} for a in actifs}
    h2 = {a: {"qlike_har_rv": r["modeles"]["HAR-RV"]["qlike"], "qlike_persistance": r["modeles"]["Persistance"]["qlike"],
              "confirmee": r["modeles"]["HAR-RV"]["qlike"] < r["modeles"]["Persistance"]["qlike"]} for a, r in actifs.items()}
    h3 = {a: {"qlike_garch": r["modeles"]["GARCH(1,1)"]["qlike"], "qlike_har_rv": r["modeles"]["HAR-RV"]["qlike"],
              "confirmee": r["modeles"]["GARCH(1,1)"]["qlike"] > r["modeles"]["HAR-RV"]["qlike"]} for a, r in actifs.items()}
    h4 = {a: {"p_valeur_kupiec": r["var"]["modeles"]["HAR-RV"]["p_valeur"], "taux": r["var"]["modeles"]["HAR-RV"]["taux"],
              "confirmee": r["var"]["modeles"]["HAR-RV"]["p_valeur"] > attentes["H4"]["seuil"]} for a, r in actifs.items()}
    h5 = {}
    for a, r in actifs.items():
        s, achat = r["strategie"][r["modele_retenu"]], r["strategie"][S.ACHAT]
        h5[a] = {"volatilite_retenu": s["volatilite_annualisee"], "volatilite_achat": achat["volatilite_annualisee"],
                 "drawdown_retenu": s["drawdown_max"], "drawdown_achat": achat["drawdown_max"],
                 "confirmee": s["volatilite_annualisee"] < achat["volatilite_annualisee"] and s["drawdown_max"] > achat["drawdown_max"]}
    h6 = {a: {"gain_sur_har_j": r["gain_sur_har_j"][r["modele_retenu"]], "gain_sur_har_rv": r["gain_sur_har_rv"][r["modele_retenu"]],
              "confirmee": r["gain_sur_har_j"][r["modele_retenu"]] < r["gain_sur_har_rv"][r["modele_retenu"]]} for a, r in actifs.items()}
    pr = attentes["prevision"]
    prevision = {a: {"gain": r["gain_sur_har_rv"][r["modele_retenu"]],
                     "dans_l_intervalle": pr["gain_min"] <= r["gain_sur_har_rv"][r["modele_retenu"]] <= pr["gain_max"]} for a, r in actifs.items()}
    # H7 (secondaire, ajoutée le 2026-11-19) : modèle retenu contre HAR-J, Holm sur les 2 actifs
    dm7 = {a: r["diebold_mariano_contre_har_j"][r["modele_retenu"]] for a, r in actifs.items()}
    holm7 = EV.holm({a: t["p_valeur"] for a, t in dm7.items()})
    h7 = {a: {"modele_retenu": actifs[a]["modele_retenu"], "moyenne_difference": dm7[a]["moyenne_difference"],
              "statistique": dm7[a]["statistique"], "p_valeur": dm7[a]["p_valeur"], "p_valeur_holm_2_actifs": holm7[a],
              "confirmee": dm7[a]["moyenne_difference"] < 0 and holm7[a] < attentes["H7"]["seuil"]} for a in actifs}
    pj = attentes["prevision_har_j"]
    prevision_har_j = {a: {"gain": r["gain_sur_har_j"][r["modele_retenu"]],
                           "dans_l_intervalle": pj["gain_min"] <= r["gain_sur_har_j"][r["modele_retenu"]] <= pj["gain_max"]}
                       for a, r in actifs.items()}
    return {"H1": h1, "H2": h2, "H3": h3, "H4": h4, "H5": h5, "H6": h6, "H7": h7, "prevision": prevision,
            "prevision_har_j": prevision_har_j}


# --- Vérification sur 2024 --------------------------------------------------------------------------

def comparer_a_2024(sortie: dict, regles: dict) -> dict:
    """Compare la chaîne appliquée au pli 5 aux chiffres déjà publiés pour 2024."""
    publie = json.loads(K.CHEMIN_JSON.read_text(encoding="utf-8"))
    tol = regles["test_final"]["verification_tolerance"]
    resultat = {"tolerance": tol, "actifs": {}}
    for actif, r in sortie["actifs"].items():
        p = publie["actifs"][actif]
        metriques = {}
        for mm in MODELES:
            ref = p["modeles"][mm]["par_pli"]["pli 5"]
            metriques[mm] = {k: abs(r["modeles"][mm][k] - ref[k]) for k in ("qlike", "rmse", "mae", "jours")}
        ecart_metriques = max(v for x in metriques.values() for v in x.values())
        # Stratégie : mêmes expositions jour par jour que la stratégie du développement, sur 2024
        res_dev, series = S.calculer_actif(actif, regles, json.loads(V.CHEMIN_VOL_CIBLE.read_text(encoding="utf-8"))["actifs"][actif]["valeur_annualisee"],
                                           r["modele_retenu"], bougies=bougies_coupees(actif, R.decoupages(regles)[-2]["evaluation"][1]))
        annee = [i for i, j in enumerate(series["jours"]) if j.year == 2024]
        ecart_expo = max(float(np.max(np.abs(np.array(r["strategie"]["_expositions"][mm]) - np.array(series["exposition"][mm])[annee])))
                         for mm in ("HAR-RV", r["modele_retenu"]))
        strat = {mm: {"publie_2024": res_dev["strategies"][mm]["par_annee"]["2024"],
                      "verification": {k: r["strategie"][mm][k] for k in ("volatilite_annualisee", "drawdown_max", "sharpe")}}
                 for mm in (S.ACHAT, "HAR-RV", r["modele_retenu"])}
        resultat["actifs"][actif] = {"ecart_max_metriques": ecart_metriques, "metriques": metriques,
                                     "ecart_max_expositions": ecart_expo, "strategie": strat,
                                     "conforme": ecart_metriques <= tol and ecart_expo <= tol}
    resultat["conforme"] = all(x["conforme"] for x in resultat["actifs"].values())
    return resultat


# --- Points d'entrée -----------------------------------------------------------------------------------

def _preparer(regles: dict, decoupage: dict) -> dict:
    C.verifier_secteur(contexte="ouverture du test")
    C.verifier_memoire_libre(regles)
    T.configurer_torch(regles)
    commit = verifier_depot(C.RACINE)
    attendus = empreintes_attendues(regles, R.decoupages(regles)[-1])               # modèles du test final : toujours
    if decoupage["nom"] != "test final":
        attendus.update(empreintes_attendues(regles, decoupage))
    n = verifier_fichiers(attendus)
    attentes = tomllib.loads(CHEMIN_ATTENTES.read_text(encoding="utf-8"))
    comparaison = json.loads(K.CHEMIN_JSON.read_text(encoding="utf-8"))
    for a in regles["donnees"]["actifs"]:
        if attentes["modele_retenu"][a] != comparaison["actifs"][a]["classement"]["modele_retenu"]:
            raise ErreurOuverture(f"{a} : le modèle retenu des attentes diffère de celui de la règle de sélection.")
    return {"commit_du_code": commit, "empreintes_verifiees": n, "attentes_sha256": _sha256(CHEMIN_ATTENTES),
            "regles_sha256": _sha256(R.CHEMIN_REGLES), "modeles_test_final_reproduction_validation": controle_modeles_test_final(regles)}


def verifier(regles: dict) -> dict:
    pli5 = R.decoupages(regles)[-2]
    entete = _preparer(regles, pli5)
    sortie = chaine(regles, pli5)
    sortie["verification"] = comparer_a_2024(sortie, regles)
    _sans_series(sortie)
    rapport = {"mode": "verification sur 2024 (pli 5), PAS le test final", **entete, **sortie}
    C.ecrire_texte(C.RACINE / regles["test_final"]["verification"], C.texte_json(rapport))
    return rapport


def _chaine_sur_le_test_ouvert(regles: dict, garder_series: bool = False) -> dict:
    """La seule fonction autorisée à lever la garde (voir src/garde.py). Aucun modèle n'est modifié : ils sont
    chargés depuis leurs fichiers, vérifiés par empreinte."""
    with G._ouverture_officielle():
        return chaine(regles, R.decoupages(regles)[-1], garder_series)


def ouvrir(regles: dict) -> dict:
    chemin = C.RACINE / regles["test_final"]["resultats"]
    if chemin.exists():
        raise ErreurOuverture(f"Refusé : {chemin.name} existe déjà ; le test final ne s'ouvre qu'une fois.")
    entete = _preparer(regles, R.decoupages(regles)[-1])
    sortie = _sans_series(_chaine_sur_le_test_ouvert(regles))
    rapport = {"mode": "test final", "ouvert_le": dt.datetime.now().isoformat(timespec="seconds"), **entete, **sortie}
    ecrire_exclusif(chemin, C.texte_json(rapport))
    return rapport


# --- Figures du test (après l'ouverture) -----------------------------------------------------------------

def verifier_resultats_publies(racine: Path, chemin_relatif: str) -> dict:
    """Le fichier de résultats doit exister, être suivi par Git dans le commit poussé et ne pas avoir été modifié."""
    chemin = racine / chemin_relatif
    if not chemin.exists():
        raise ErreurOuverture(f"Refusé : {chemin_relatif} n'existe pas (le test n'a pas été ouvert).")
    if chemin_relatif not in _git(racine, "ls-tree", "-r", "--name-only", "HEAD", "--", chemin_relatif).splitlines():
        raise ErreurOuverture(f"Refusé : {chemin_relatif} n'est pas dans le commit poussé ; publiez-le d'abord.")
    if _git(racine, "status", "--porcelain", "--", chemin_relatif):
        raise ErreurOuverture(f"Refusé : {chemin_relatif} a été modifié depuis sa publication.")
    return json.loads(chemin.read_text(encoding="utf-8"))


def ecarts_aux_resultats_publies(recalcule: dict, publie: dict) -> list[str]:
    """Différences (au bit près, après passage par le même JSON) entre les agrégats recalculés et publiés."""
    a = json.loads(C.texte_json({k: recalcule[k] for k in ("decoupage", "periode", "actifs", "hypotheses")}))
    b = {k: publie[k] for k in ("decoupage", "periode", "actifs", "hypotheses")}
    ecarts = []

    def parcourir(x, y, chemin):
        if isinstance(x, dict) and isinstance(y, dict):
            for k in sorted(set(x) | set(y)):
                if k not in x or k not in y:
                    ecarts.append(f"{chemin}/{k} : clé absente")
                else:
                    parcourir(x[k], y[k], f"{chemin}/{k}")
        elif isinstance(x, list) and isinstance(y, list) and len(x) == len(y):
            for i, (u, v) in enumerate(zip(x, y)):
                parcourir(u, v, f"{chemin}[{i}]")
        elif x != y:
            ecarts.append(f"{chemin} : {x} ≠ {y}")

    parcourir(a, b, "")
    return ecarts


def _figures_test(sortie: dict, regles: dict) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import math
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    import exploration as X
    a = math.sqrt(regles["cible"]["annualisation_jours"])
    ecrits = []
    for actif, res in sortie["actifs"].items():
        retenu, t = res["modele_retenu"], res["_table"]
        dates = pd.to_datetime([str(j) for j in t["date_cible"]])
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.plot(dates, np.exp(t["cible"]) * a, color="#999999", linewidth=0.6, label="RV réalisée")
        ax.plot(dates, np.sqrt(t["HAR-RV"]) * a, color=X.COULEURS[actif], linewidth=1.0, label="Prévision HAR-RV")
        ax.plot(dates, np.sqrt(t["HAR-J"]) * a, color="#16A34A", linewidth=0.9, alpha=0.85, label="Prévision HAR-J")
        ax.plot(dates, np.sqrt(t[retenu]) * a, color="#7C3AED", linewidth=0.9, alpha=0.85, label=f"Prévision {retenu} (modèle retenu)")
        ax.yaxis.set_major_formatter(X.FORMAT_POURCENT)
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 4, 7, 10)))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _p: mdates.num2date(x).strftime("%m/%Y")))
        ax.set_ylabel("Volatilité annualisée")
        ax.set_xlabel("Date de la cible (test final ; aucune crise définie sur cette période)")
        ax.set_title(f"{X.NOMS[actif]} : test final, RV réalisée et prévisions à un jour")
        ax.legend(loc="upper right")
        ax.grid(alpha=0.3)
        fig.tight_layout(rect=(0, 0.03, 1, 1))
        chemin = C.RACINE / "figures" / f"figure_10_test_previsions_{actif}.png"
        X._finir(fig, chemin)
        ecrits.append(chemin.name)
        s = res["strategie"]
        jours = pd.to_datetime(s["_jours"])
        couleurs = {S.ACHAT: "#999999", "HAR-RV": X.COULEURS[actif], retenu: "#7C3AED"}
        fig, (h, b) = plt.subplots(2, 1, figsize=(11, 7), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
        for m, v in s["_valeurs"].items():
            h.plot(jours, v, color=couleurs[m], linewidth=1.0, label=m if m != retenu else f"{m} (modèle retenu)")
        h.set_yscale("log")
        h.yaxis.set_major_formatter(FuncFormatter(lambda x, _p: X.nombre_fr_auto(round(x, 6))))
        h.yaxis.set_minor_formatter(FuncFormatter(lambda x, _p: X.nombre_fr_auto(round(x, 6))))
        h.set_ylabel("Valeur du portefeuille (départ 1, échelle log)")
        h.legend(loc="upper left")
        h.grid(alpha=0.3)
        for m, e in s["_expositions"].items():
            b.plot(jours, e, color=couleurs[m], linewidth=0.7, label=m if m != retenu else f"{m} (modèle retenu)")
        b.set_ylim(-0.02, 1.05)
        b.yaxis.set_major_formatter(X.FORMAT_POURCENT)
        b.set_ylabel("Exposition")
        b.legend(loc="lower left")
        b.grid(alpha=0.3)
        b.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 4, 7, 10)))
        b.xaxis.set_major_formatter(FuncFormatter(lambda x, _p: mdates.num2date(x).strftime("%m/%Y")))
        b.set_xlabel("Date (test final, frais de 0,10 % compris)")
        h.set_title(f"{X.NOMS[actif]} : test final, volatility targeting, achat simple, HAR-RV et {retenu}")
        fig.tight_layout(rect=(0, 0.03, 1, 1))
        chemin = C.RACINE / "figures" / f"figure_11_test_strategie_{actif}.png"
        X._finir(fig, chemin)
        ecrits.append(chemin.name)
    return ecrits


def figures(regles: dict) -> dict:
    """Figures du test : seulement si les résultats publiés sont intacts et si la chaîne recalculée les redonne exactement."""
    C.verifier_secteur(contexte="figures du test")
    T.configurer_torch(regles)
    verifier_depot(C.RACINE)
    publie = verifier_resultats_publies(C.RACINE, regles["test_final"]["resultats"])
    verifier_fichiers(empreintes_attendues(regles, R.decoupages(regles)[-1]))
    sortie = _chaine_sur_le_test_ouvert(regles, garder_series=True)
    series = {a: {"_table": r.pop("_table"), "strategie": {k: r["strategie"][k] for k in ("_jours", "_valeurs", "_expositions")},
                  "modele_retenu": r["modele_retenu"]} for a, r in sortie["actifs"].items()}
    ecarts = ecarts_aux_resultats_publies(_sans_series(sortie), publie)
    if ecarts:
        raise ErreurOuverture(f"Refusé : la chaîne recalculée diffère des résultats publiés ({len(ecarts)} écarts, "
                              f"premier : {ecarts[0]}). Aucune figure n'est produite.")
    return {"ecarts_aux_resultats_publies": 0, "figures": _figures_test({"actifs": series}, regles)}


def main(arguments: list[str]) -> int:
    C.proteger_sortie()
    regles = R.charger_regles()
    if arguments == ["--verification"]:
        action = verifier
    elif arguments == ["--ouvrir"]:
        action = ouvrir
    elif arguments == ["--figures"]:
        action = figures
    else:
        print("Usage : python src/ouvrir_test.py --verification   (même chaîne sur 2024, sans ouvrir le test)\n"
              "        python src/ouvrir_test.py --ouvrir         (ouvre le test final, UNE seule fois)\n"
              "        python src/ouvrir_test.py --figures        (après l'ouverture : figures, si la chaîne redonne les résultats publiés)")
        return 2
    try:
        rapport = action(regles)
    except (ErreurOuverture, G.ErreurTestAveugle, K.ErreurComparaison, C.ErreurAlimentation, C.ErreurMemoire) as erreur:
        print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1
    if action is verifier:
        v = rapport["verification"]
        for a, x in v["actifs"].items():
            print(f"{a} | écart maximal des métriques : {x['ecart_max_metriques']:.3g} | écart maximal des expositions : "
                  f"{x['ecart_max_expositions']:.3g} | conforme : {'oui' if x['conforme'] else 'non'}")
        for a, h in rapport["hypotheses"]["H7"].items():
            print(f"{a} | H7 sur 2024 (vérification seulement, pas le test) : moyenne de d {h['moyenne_difference']:.4f}, p-valeur "
                  f"{h['p_valeur']:.4g}, p-valeur Holm {h['p_valeur_holm_2_actifs']:.4g}, confirmée : {'oui' if h['confirmee'] else 'non'} ; "
                  f"gain sur HAR-J {100 * rapport['hypotheses']['prevision_har_j'][a]['gain']:.1f} %")
        print("Vérification " + ("CONFORME" if v["conforme"] else "NON CONFORME") + " (rapports/verification_test_2024.json).")
        return 0 if v["conforme"] else 1
    if action is figures:
        print(f"Chaîne recalculée identique aux résultats publiés (0 écart) ; figures : {', '.join(rapport['figures'])}.")
        return 0
    print("Test final ouvert ; résultats dans rapports/test_final.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
