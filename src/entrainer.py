"""Entraînement du deep learning : LSTM, GRU, CNN-LSTM, Transformer (codé à la main) et TFT.

Règles : config/regles.toml (sections entrainement, modeles, evaluation) et docs/REGLES.md (sections 11 et 12).
- Un modèle par actif. Séquences de 30 jours se terminant à J (variables de la série remplacée, jour de la
  semaine en one-hot) ; TFT : encodeur de 30 jours, horizon 1, jour de la semaine de la CIBLE en catégorie connue.
- Normalisation des entrées et de la cible apprise sur la fenêtre d'ajustement de chaque découpage,
  enregistrée en JSON dans sorties/.
- AdamW, MSE sur log(RV) normalisé, patience 20, 200 époques au plus (meilleurs poids gardés), 2 fils,
  mode déterministe de torch, graine dérivée de l'identifiant de chaque unité.
- Phase « reglage » : les mêmes N combinaisons valides pour BTC et ETH (graine 42), sur le premier découpage ;
  choix = plus petite MSE en unités de log(RV) sur la validation interne.
- Phase « plis » : la combinaison retenue, 3 graines × 6 découpages (5 plis et le modèle du test final).
  Aucune prévision sur le test final : la garde du test aveugle le refuse.
- Reprise après interruption, refus sur batterie, seuil de mémoire, mise en veille empêchée.
- Journal d'avancement dans sorties/ ; règle de suivi : si le temps réel cumulé dépasse l'estimation de plus
  de 50 %, arrêt propre après l'unité en cours.

Usage :
    .venv\\Scripts\\python src/entrainer.py reglage
    .venv\\Scripts\\python src/entrainer.py plis
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import baselines as B  # noqa: E402
import commun as C  # noqa: E402
import garde as G  # noqa: E402
import regles as R  # noqa: E402
import reprise as P  # noqa: E402
import variables as V  # noqa: E402

VERSION = "deep-1"
MODELES = ["LSTM", "GRU", "CNN-LSTM", "Transformer", "TFT"]
ESPACES = {"LSTM": "lstm", "GRU": "gru", "CNN-LSTM": "cnn_lstm", "Transformer": "transformer", "TFT": "tft"}
CLES_INUTILES = {"meme_espace_que", "contrainte", "dropout_lot_taux_weight_decay"}


class ArretSuivi(RuntimeError):
    """Le temps réel cumulé dépasse l'estimation de plus de 50 % : arrêt propre, décision à écrire."""


class ErreurEntrainement(RuntimeError):
    pass


# --- Configuration de torch ----------------------------------------------------------------------

def configurer_torch(regles: dict) -> None:
    fils = regles["projet"]["fils_calcul"]
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ.setdefault(var, str(fils))
    import torch
    torch.set_num_threads(fils)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass                                   # déjà fixé dans ce processus
    torch.use_deterministic_algorithms(True)


# --- Espaces et combinaisons --------------------------------------------------------------------

def espace_resolu(regles: dict, modele: str) -> dict:
    """Espace d'un modèle, avec les réglages repris du LSTM là où les règles le disent."""
    espaces = regles["entrainement"]["espaces"]
    e = dict(espaces[ESPACES[modele]])
    lstm = espaces["lstm"]
    if e.get("meme_espace_que") == "lstm":
        e = {**lstm, **e}
    if e.get("dropout_lot_taux_weight_decay") == "comme_lstm":
        e.update({k: lstm[k] for k in ("dropout", "taux_apprentissage", "lot", "weight_decay")})
    return {k: v for k, v in e.items() if k not in CLES_INUTILES}


def valide(modele: str, c: dict) -> bool:
    if modele == "TFT":
        return c["hidden_continuous_size"] <= c["hidden_size"]
    if modele == "Transformer":
        return c["d_model"] % c["tetes"] == 0
    return True


def combinaisons(regles: dict, modele: str, n: int | None = None) -> tuple[list[dict], int]:
    """Les N combinaisons valides du modèle (les mêmes pour les deux actifs : graine de la recherche)."""
    n = regles["modeles"]["budget_reglage"] if n is None else n
    return B.tirer_dans_espace(espace_resolu(regles, modele), n, regles["entrainement"]["recherche"]["graine"],
                               lambda c: valide(modele, c))


# --- Données, normalisation, séquences ------------------------------------------------------

def donnees_reseaux(bougies: pd.DataFrame, regles: dict, debut: dt.date | None = None, fin: dt.date | None = None):
    """(exemples, journalier) : exemples de src/variables.py et variables de TOUS les jours (série remplacée)."""
    exemples, lignes, _ = V.calculer_actif(bougies, regles, debut, fin)
    base, _ = V.appliquer_secours(lignes)
    journalier = V.calculer_variables(base, regles)
    return exemples, journalier


def apprendre_normalisation(journalier: pd.DataFrame, exemples: pd.DataFrame, decoupage: dict, regles: dict) -> dict:
    """Moyennes et écarts-types appris sur la fenêtre d'ajustement seulement : entrées sur les jours d'origine
    jusqu'à la dernière origine d'ajustement, cible sur les exemples d'ajustement."""
    colonnes = regles["entrainement"]["variables_continues"]
    derniere_origine = decoupage["ajustement"][1] - dt.timedelta(days=1)
    jours = journalier[[j <= derniere_origine for j in journalier.index]][colonnes].dropna()
    cibles = exemples.loc[B.masques(exemples, decoupage)["ajustement"], "cible"]
    return {"decoupage": decoupage["nom"], "colonnes": colonnes,
            "moyennes": [float(x) for x in jours.mean()], "ecarts_types": [float(x) for x in jours.std(ddof=0)],
            "cible_moyenne": float(cibles.mean()), "cible_ecart_type": float(cibles.std(ddof=0)),
            "jours_utilises": [str(jours.index[0]), str(jours.index[-1])], "exemples_cible": int(len(cibles))}


def tableau_normalise(journalier: pd.DataFrame, norm: dict) -> np.ndarray:
    """Une ligne par jour : variables continues normalisées, puis le jour de la semaine en one-hot (7 colonnes)."""
    x = (journalier[norm["colonnes"]].to_numpy(dtype="float64") - np.array(norm["moyennes"])) / np.array(norm["ecarts_types"])
    jours = np.eye(7)[journalier["jour_semaine"].to_numpy(dtype="int64")]
    return np.concatenate([x, jours], axis=1).astype("float32")


def sequences(tableau: np.ndarray, index_jours: pd.Index, origines, longueur: int) -> np.ndarray:
    """Séquences de `longueur` jours se terminant à chaque origine J (jours J-longueur+1 à J, jamais après J)."""
    position = {j: i for i, j in enumerate(index_jours)}
    p = np.array([position[j] for j in origines])
    if (p < longueur - 1).any():
        raise ErreurEntrainement("Une séquence commencerait avant le début des données.")
    seq = tableau[p[:, None] + np.arange(-longueur + 1, 1)[None, :]]
    if not np.isfinite(seq).all():
        raise ErreurEntrainement("Une séquence contient une valeur manquante.")
    return seq


def parties(exemples: pd.DataFrame, decoupage: dict, avec_evaluation: bool) -> dict[str, pd.DataFrame]:
    m = B.masques(exemples, decoupage)
    sortie = {"ajustement": exemples[m["ajustement"]], "validation": exemples[m["validation"]]}
    if avec_evaluation:
        G.refuser_si_test(exemples.loc[m["evaluation"], "date_cible"], f"prévisions de {decoupage['nom']}")
        sortie["evaluation"] = exemples[m["evaluation"]]
    return sortie


# --- Entraînement des réseaux torch ---------------------------------------------------------

def entrainer_torch(modele: str, combinaison: dict, xa, ya, xv, yv, graine: int, regles: dict, epoques_max: int | None = None):
    """AdamW, MSE, arrêt anticipé sur la validation interne ; renvoie le réseau avec ses meilleurs poids."""
    import torch
    import reseaux
    ent = regles["entrainement"]
    epoques_max = epoques_max or ent["epoques_max"]
    torch.manual_seed(graine)
    reseau = reseaux.construire_reseau(modele, combinaison, xa.shape[2], xa.shape[1])
    opt = torch.optim.AdamW(reseau.parameters(), lr=combinaison["taux_apprentissage"], weight_decay=combinaison["weight_decay"])
    generateur = torch.Generator().manual_seed(graine)
    xa, ya, xv, yv = (torch.from_numpy(np.asarray(a, dtype="float32")) for a in (xa, ya, xv, yv))
    meilleure, meilleurs_poids, sans_progres, temps = float("inf"), None, 0, []
    for epoque in range(epoques_max):
        debut = time.perf_counter()
        reseau.train()
        for idx in torch.randperm(len(xa), generator=generateur).split(combinaison["lot"]):
            opt.zero_grad()
            torch.nn.functional.mse_loss(reseau(xa[idx]), ya[idx]).backward()
            opt.step()
        reseau.eval()
        with torch.no_grad():
            perte_val = float(torch.nn.functional.mse_loss(reseau(xv), yv))
        temps.append(time.perf_counter() - debut)
        if perte_val < meilleure:
            meilleure, meilleurs_poids, sans_progres, meilleure_epoque = perte_val, copy.deepcopy(reseau.state_dict()), 0, epoque + 1
        else:
            sans_progres += 1
            if sans_progres >= ent["patience_epoques"]:
                break
    reseau.load_state_dict(meilleurs_poids)
    reseau.eval()
    return reseau, {"epoques": len(temps), "meilleure_epoque": meilleure_epoque, "temps_epoques_s": temps}


def prevoir_torch(reseau, x) -> np.ndarray:
    import torch
    with torch.no_grad():
        return reseau(torch.from_numpy(np.asarray(x, dtype="float32"))).numpy().astype("float64")


# --- TFT -------------------------------------------------------------------------------------

def table_tft(journalier: pd.DataFrame, norm: dict) -> pd.DataFrame:
    """Une ligne par jour : variables normalisées (inconnues dans le futur), y = log RV du jour normalisé
    (série remplacée : égale à la vraie valeur les jours valides), jour de la semaine (connu d'avance)."""
    colonnes = norm["colonnes"]
    t = pd.DataFrame((journalier[colonnes].to_numpy(dtype="float64") - np.array(norm["moyennes"])) / np.array(norm["ecarts_types"]),
                     columns=colonnes, index=journalier.index)
    t["y"] = (journalier["log_rv_1"].to_numpy(dtype="float64") - norm["cible_moyenne"]) / norm["cible_ecart_type"]
    t["jour_semaine"] = journalier["jour_semaine"].astype(str).to_numpy()
    t["groupe"] = "actif"
    t = t.dropna()
    t["time_idx"] = [(j - dt.date(1970, 1, 1)).days for j in t.index]
    return t.reset_index(drop=True)


def jeu_tft(table: pd.DataFrame, cibles: list[dt.date], longueur: int, reference=None):
    """Échantillons dont le jour prédit est dans `cibles` ; encodeur = les `longueur` jours avant la cible."""
    from pytorch_forecasting import TimeSeriesDataSet
    from pytorch_forecasting.data.encoders import NaNLabelEncoder, TorchNormalizer
    idx = {(j - dt.date(1970, 1, 1)).days for j in cibles}
    derniere = max(idx)
    morceau = table[table["time_idx"] <= derniere]
    if reference is None:
        colonnes = [c for c in table.columns if c not in ("y", "jour_semaine", "groupe", "time_idx")]
        jeu = TimeSeriesDataSet(
            morceau, time_idx="time_idx", target="y", group_ids=["groupe"], max_encoder_length=longueur,
            min_encoder_length=longueur, max_prediction_length=1, min_prediction_length=1,
            time_varying_known_categoricals=["jour_semaine"], time_varying_known_reals=[],
            time_varying_unknown_reals=["y"] + colonnes, static_categoricals=[], static_reals=[],
            target_normalizer=TorchNormalizer(method="identity", center=False), scalers={k: None for k in colonnes},
            categorical_encoders={"jour_semaine": NaNLabelEncoder(add_nan=False), "groupe": NaNLabelEncoder(add_nan=False)},
            add_relative_time_idx=False, add_target_scales=False, add_encoder_length=False, allow_missing_timesteps=False)
    else:
        jeu = TimeSeriesDataSet.from_dataset(reference, morceau, min_prediction_idx=min(idx), stop_randomization=True)
    return jeu.filter(lambda x: x.time_idx_first_prediction.isin(idx))


def entrainer_tft(combinaison: dict, jeu_aj, jeu_val, graine: int, regles: dict, epoques_max: int | None = None):
    import warnings
    warnings.filterwarnings("ignore")
    import logging
    logging.getLogger("lightning.pytorch").setLevel(logging.ERROR)
    import lightning.pytorch as pl
    import torch
    from lightning.pytorch.callbacks import EarlyStopping
    from pytorch_forecasting import TemporalFusionTransformer
    import reseaux
    ent = regles["entrainement"]
    pl.seed_everything(graine, workers=True, verbose=False)
    tft = TemporalFusionTransformer.from_dataset(
        jeu_aj, hidden_size=combinaison["hidden_size"], attention_head_size=combinaison["tetes_attention"],
        hidden_continuous_size=combinaison["hidden_continuous_size"], dropout=combinaison["dropout"],
        loss=reseaux.perte_mse_tft(), learning_rate=combinaison["taux_apprentissage"], optimizer="adamw",
        weight_decay=combinaison["weight_decay"], output_size=1)
    suivi = {"meilleure": float("inf"), "poids": None, "epoque": 0, "temps": [], "debut": None}

    class Meilleurs(pl.Callback):
        def on_train_epoch_start(self, trainer, module):
            suivi["debut"] = time.perf_counter()

        def on_validation_epoch_end(self, trainer, module):
            if trainer.sanity_checking:
                return
            perte = float(trainer.callback_metrics["val_loss"])
            suivi["temps"].append(time.perf_counter() - suivi["debut"])
            if perte < suivi["meilleure"]:
                suivi.update(meilleure=perte, poids=copy.deepcopy(module.state_dict()), epoque=trainer.current_epoch + 1)

    entraineur = pl.Trainer(max_epochs=epoques_max or ent["epoques_max"], accelerator="cpu", deterministic=True, logger=False,
                            enable_checkpointing=False, enable_progress_bar=False, enable_model_summary=False,
                            num_sanity_val_steps=0,
                            callbacks=[EarlyStopping(monitor="val_loss", patience=ent["patience_epoques"], mode="min"), Meilleurs()])
    entraineur.fit(tft, train_dataloaders=jeu_aj.to_dataloader(train=True, batch_size=combinaison["lot"], num_workers=0),
                   val_dataloaders=jeu_val.to_dataloader(train=False, batch_size=combinaison["lot"], num_workers=0))
    tft.load_state_dict(suivi["poids"])
    tft.eval()
    torch.set_grad_enabled(True)
    return tft, {"epoques": len(suivi["temps"]), "meilleure_epoque": suivi["epoque"], "temps_epoques_s": suivi["temps"]}


def prevoir_tft(tft, jeu) -> tuple[np.ndarray, list[int]]:
    """Prévisions (normalisées) et jour prédit (time_idx) de chaque échantillon, dans l'ordre du jeu."""
    import torch
    chargeur = jeu.to_dataloader(train=False, batch_size=256, num_workers=0)
    with torch.no_grad():
        prev = torch.cat([tft(x)["prediction"].reshape(-1) for x, _ in chargeur]).numpy().astype("float64")
    jours = jeu.decoded_index["time_idx_first_prediction"].to_list()
    return prev, jours


# --- Une unité : entraîner un modèle sur un découpage avec une graine ----------------------------

def entrainer_unite(modele: str, combinaison: dict, exemples: pd.DataFrame, journalier: pd.DataFrame, decoupage: dict,
                    graine: int, regles: dict, avec_evaluation: bool, epoques_max: int | None = None) -> tuple[dict, object, dict]:
    """(résultat sérialisable, réseau entraîné, normalisation). Prévisions dénormalisées en log(RV)."""
    longueur = regles["variables"]["fenetre_sequence_jours"]
    norm = apprendre_normalisation(journalier, exemples, decoupage, regles)
    p = parties(exemples, decoupage, avec_evaluation)
    mu, sigma = norm["cible_moyenne"], norm["cible_ecart_type"]
    debut = time.perf_counter()
    previsions = {}
    if modele == "TFT":
        table = table_tft(journalier, norm)
        jeux = {"ajustement": jeu_tft(table, list(p["ajustement"]["date_cible"]), longueur)}
        for nom in p:
            if nom != "ajustement":
                jeux[nom] = jeu_tft(table, list(p[nom]["date_cible"]), longueur, reference=jeux["ajustement"])
        reseau, infos = entrainer_tft(combinaison, jeux["ajustement"], jeux["validation"], graine, regles, epoques_max)
        for nom in p:
            if nom == "ajustement":
                continue
            prev, jours = prevoir_tft(reseau, jeux[nom])
            attendu = [(j - dt.date(1970, 1, 1)).days for j in p[nom]["date_cible"]]
            if jours != attendu:
                raise ErreurEntrainement(f"TFT : ordre des échantillons inattendu sur {nom}.")
            previsions[nom] = prev * sigma + mu
    else:
        tableau = tableau_normalise(journalier, norm)
        x = {nom: sequences(tableau, journalier.index, list(t["date_origine"]), longueur) for nom, t in p.items()}
        y = {nom: (t["cible"].to_numpy() - mu) / sigma for nom, t in p.items()}
        reseau, infos = entrainer_torch(modele, combinaison, x["ajustement"], y["ajustement"], x["validation"], y["validation"],
                                        graine, regles, epoques_max)
        for nom in p:
            if nom != "ajustement":
                previsions[nom] = prevoir_torch(reseau, x[nom]) * sigma + mu
    cible_val = p["validation"]["cible"].to_numpy()
    resultat = {"modele": modele, "decoupage": decoupage["nom"], "combinaison": combinaison, "graine": graine,
                "duree_s": time.perf_counter() - debut, **infos,
                "mse_log_validation": float(np.mean((cible_val - previsions["validation"]) ** 2))}
    for nom, prev in previsions.items():
        resultat[nom] = {"date_cible": [str(d) for d in p[nom]["date_cible"]], "prevision_log": prev.tolist()}
    return resultat, reseau, norm


# --- Journal d'avancement et règle de suivi -----------------------------------------------------

def estimation_par_unite(regles: dict) -> dict[str, float]:
    """Estimation d'une unité = médiane d'une époque (mesures) × époques estimées (100)."""
    mesures = json.loads((C.DOSSIER_RAPPORTS / "mesures_entrainement.json").read_text(encoding="utf-8"))
    fils = str(mesures["fils_choisi"])
    cles = {"LSTM": "lstm", "GRU": "gru", "CNN-LSTM": "cnn_lstm", "Transformer": "transformer", "TFT": "tft"}
    epoques = regles["entrainement"]["mesures"]["epoques_estimees"]
    return {m: mesures["fils"][fils][cles[m]]["mediane"] * epoques for m in MODELES}


def verifier_suivi(cumul_reel_s: float, cumul_estime_s: float, regles: dict) -> None:
    """Arrêt si le temps réel cumulé dépasse l'estimation de plus de depassement_suivi_max (50 %)."""
    limite = 1 + regles["entrainement"]["mesures"]["depassement_suivi_max"]
    if cumul_estime_s > 0 and cumul_reel_s > limite * cumul_estime_s:
        raise ArretSuivi(
            f"Arrêt propre (règle de suivi) : {C.nombre_fr(cumul_reel_s / 3600, 2)} h réelles pour "
            f"{C.nombre_fr(cumul_estime_s / 3600, 2)} h estimées sur les unités terminées, soit plus de "
            f"{C.nombre_fr(100 * (limite - 1))} % de dépassement. Les unités terminées sont gardées. Une décision doit être "
            "prise et écrite comme exception datée dans docs/CHOIX.md avant de relancer.")


def etat(unites: list[tuple[str, str]], dossier: Path, estimation: dict[str, float]) -> dict:
    """Avancement : unités (identifiant, modèle) terminées, temps réel et estimé, par modèle."""
    par_modele = {m: {"total": 0, "terminees": 0, "temps_reel_s": 0.0, "temps_estime_s": 0.0, "epoques": 0} for m in MODELES}
    for identifiant, modele in unites:
        r = P.lire_unite(dossier, identifiant)
        s = par_modele[modele]
        s["total"] += 1
        if r is not None:
            s["terminees"] += 1
            s["temps_reel_s"] += r["duree_s"]
            s["temps_estime_s"] += estimation[modele]
            s["epoques"] += r["epoques"]
    for m, s in par_modele.items():
        s["temps_par_epoque_reel_s"] = s["temps_reel_s"] / s["epoques"] if s["epoques"] else None
        s["temps_par_epoque_estime_s"] = estimation[m] / 100
        s["restant_estime_s"] = (s["total"] - s["terminees"]) * estimation[m]
    reel = sum(s["temps_reel_s"] for s in par_modele.values())
    estime = sum(s["temps_estime_s"] for s in par_modele.values())
    return {"unites_total": len(unites), "unites_terminees": sum(s["terminees"] for s in par_modele.values()),
            "cumul_reel_s": reel, "cumul_estime_s": estime, "rapport_reel_sur_estime": reel / estime if estime else None,
            "restant_estime_s": sum(s["restant_estime_s"] for s in par_modele.values()),
            "par_modele": {m: s for m, s in par_modele.items() if s["total"]}}


def ecrire_journal(dossier_sorties: Path, phase: str, unites, dossier_unites: Path, estimation, debut_session: float,
                   statut: str) -> dict:
    journal = {"phase": phase, "statut": statut, "mise_a_jour": dt.datetime.now().isoformat(timespec="seconds"),
               "temps_session_s": time.perf_counter() - debut_session, **etat(unites, dossier_unites, estimation)}
    C.ecrire_texte(dossier_sorties / "journal.json", C.texte_json(journal))
    return journal


# --- Phases ---------------------------------------------------------------------------------------

class Options:
    """Réglages d'exécution ; les valeurs par défaut sont celles des règles. Les autres ne servent qu'à l'essai à blanc."""

    def __init__(self, regles: dict, dossier: Path, modeles=None, actifs=None, combinaisons=None, epoques_max=None,
                 graines=None, decoupages=None):
        self.dossier = dossier
        self.modeles = modeles or MODELES
        self.actifs = actifs or regles["donnees"]["actifs"]
        self.combinaisons = combinaisons or regles["modeles"]["budget_reglage"]
        self.epoques_max = epoques_max
        self.graines = graines or regles["modeles"]["graines_deep_learning"]
        tous = R.decoupages(regles)
        self.decoupages = tous if decoupages is None else tous[:decoupages]


def _cle_donnees(regles: dict) -> str:
    manifeste = json.loads((C.RACINE / regles["variables"]["sorties"]["manifeste"]).read_text(encoding="utf-8"))
    return manifeste["empreinte_contenu_sha256"][:12]


def id_reglage(actif, modele, k, cle) -> str:
    return f"{VERSION}|{actif}|{modele}|réglage|combinaison {k}|graine 0|{cle}"


def id_pli(actif, modele, decoupage, graine, cle) -> str:
    return f"{VERSION}|{actif}|{modele}|{decoupage}|graine {graine}|{cle}"


def _executer(phase: str, unites: list[tuple[str, str]], calcul, opt: Options, regles: dict) -> dict:
    """Exécute les unités avec la reprise ; vérifie la règle de suivi avant chaque nouvelle unité."""
    dossier_unites = opt.dossier / "unites"
    estimation = estimation_par_unite(regles)
    debut = time.perf_counter()

    def avec_suivi(identifiant: str, graine: int):
        e = ecrire_journal(opt.dossier, phase, unites, dossier_unites, estimation, debut, "en cours")
        verifier_suivi(e["cumul_reel_s"], e["cumul_estime_s"], regles)
        modele = dict(unites)[identifiant]
        print(f"[{dt.datetime.now():%H:%M:%S}] {phase} : unité {e['unites_terminees'] + 1}/{e['unites_total']} ({modele}) "
              f"| réel {C.nombre_fr(e['cumul_reel_s'] / 60, 1)} min / estimé {C.nombre_fr(e['cumul_estime_s'] / 60, 1)} min",
              flush=True)
        return calcul(identifiant, graine)

    try:
        P.executer([u for u, _ in unites], avec_suivi, dossier_unites)
        statut = "terminé"
    except ArretSuivi:
        ecrire_journal(opt.dossier, phase, unites, dossier_unites, estimation, debut, "arrêté : règle de suivi")
        raise
    except C.ErreurAlimentation:
        ecrire_journal(opt.dossier, phase, unites, dossier_unites, estimation, debut, "arrêté : PC sur batterie")
        raise
    except BaseException:
        ecrire_journal(opt.dossier, phase, unites, dossier_unites, estimation, debut, "interrompu")
        raise
    return ecrire_journal(opt.dossier, phase, unites, dossier_unites, estimation, debut, statut)


def phase_reglage(regles: dict, opt: Options) -> dict:
    cle = _cle_donnees(regles)
    pli1 = R.decoupages(regles)[0]
    donnees = {a: donnees_reseaux(V.lire_bougies(C.DOSSIER_TRAITE / f"{a}_5m.parquet"), regles) for a in opt.actifs}
    tirages = {m: combinaisons(regles, m, opt.combinaisons) for m in opt.modeles}
    unites = [(id_reglage(a, m, k, cle), m) for a in opt.actifs for m in opt.modeles for k in range(opt.combinaisons)]

    def calcul(identifiant: str, graine: int) -> dict:
        _, actif, modele, _, comb, *_ = identifiant.split("|")
        k = int(comb.split(" ")[1])
        exemples, journalier = donnees[actif]
        resultat, _, _ = entrainer_unite(modele, tirages[modele][0][k], exemples, journalier, pli1, graine, regles,
                                         avec_evaluation=False, epoques_max=opt.epoques_max)
        resultat.pop("validation", None)
        return resultat

    journal = _executer("reglage", unites, calcul, opt, regles)
    choix = {}
    for a in opt.actifs:
        for m in opt.modeles:
            scores = [P.lire_unite(opt.dossier / "unites", id_reglage(a, m, k, cle))["mse_log_validation"] for k in range(opt.combinaisons)]
            meilleure = int(np.argmin(scores))
            choix.setdefault(a, {})[m] = {"numero": meilleure, "combinaison": tirages[m][0][meilleure], "scores": scores,
                                          "tirages_ecartes": tirages[m][1]}
    C.ecrire_texte(opt.dossier / "reglage.json", C.texte_json(choix))
    return journal


def phase_plis(regles: dict, opt: Options) -> dict:
    import torch
    cle = _cle_donnees(regles)
    chemin_choix = opt.dossier / "reglage.json"
    if not chemin_choix.exists():
        raise ErreurEntrainement("La phase « reglage » n'est pas terminée : lancez-la d'abord (reglage.json absent).")
    choix = json.loads(chemin_choix.read_text(encoding="utf-8"))
    donnees = {a: donnees_reseaux(V.lire_bougies(C.DOSSIER_TRAITE / f"{a}_5m.parquet"), regles) for a in opt.actifs}
    finale = R.decoupages(regles)[-1]["nom"]
    par_nom = {d["nom"]: d for d in opt.decoupages}
    unites = [(id_pli(a, m, d["nom"], g, cle), m) for a in opt.actifs for m in opt.modeles for d in opt.decoupages for g in opt.graines]

    def calcul(identifiant: str, graine: int) -> dict:
        _, actif, modele, nom_decoupage, _, *_ = identifiant.split("|")
        exemples, journalier = donnees[actif]
        resultat, reseau, norm = entrainer_unite(modele, choix[actif][modele]["combinaison"], exemples, journalier,
                                                 par_nom[nom_decoupage], graine, regles,
                                                 avec_evaluation=nom_decoupage != finale, epoques_max=opt.epoques_max)
        dossier = opt.dossier / "poids" / actif / modele
        dossier.mkdir(parents=True, exist_ok=True)
        base = f"{nom_decoupage.replace(' ', '_')}_graine_{identifiant.split('|graine ')[1].split('|')[0]}"
        chemin_poids = dossier / f"{base}.pt"
        torch.save(reseau.state_dict(), chemin_poids)
        C.ecrire_texte(opt.dossier / "normalisation" / actif / f"{nom_decoupage.replace(' ', '_')}.json", C.texte_json(norm))
        resultat["poids"] = chemin_poids.relative_to(opt.dossier).as_posix()
        resultat["poids_sha256"] = hashlib.sha256(chemin_poids.read_bytes()).hexdigest()
        return resultat

    return _executer("plis", unites, calcul, opt, regles)


def main(arguments: list[str]) -> int:
    C.proteger_sortie()
    analyse = argparse.ArgumentParser(description="Entraînement du deep learning (phases reglage puis plis).")
    analyse.add_argument("phase", choices=["reglage", "plis"])
    analyse.add_argument("--dossier", default="sorties/deep_learning", help="dossier des sorties (ignoré par Git)")
    analyse.add_argument("--modeles", nargs="*", choices=MODELES)
    analyse.add_argument("--actifs", nargs="*")
    analyse.add_argument("--combinaisons", type=int, help="essai à blanc seulement")
    analyse.add_argument("--epoques-max", type=int, help="essai à blanc seulement")
    analyse.add_argument("--graines", type=int, nargs="*", help="essai à blanc seulement")
    analyse.add_argument("--decoupages", type=int, help="essai à blanc seulement : nombre de premiers découpages")
    a = analyse.parse_args(arguments)
    regles = R.charger_regles()
    try:
        R.verifier_pret_pour_entrainement(regles)
        C.verifier_secteur(contexte="démarrage de l'entraînement")
        C.verifier_memoire_libre(regles)
        configurer_torch(regles)
        opt = Options(regles, C.RACINE / a.dossier, a.modeles, a.actifs, a.combinaisons, a.epoques_max, a.graines, a.decoupages)
        journal = (phase_reglage if a.phase == "reglage" else phase_plis)(regles, opt)
    except (ArretSuivi, C.ErreurAlimentation, C.ErreurMemoire, G.ErreurTestAveugle, ErreurEntrainement, R.ErreurRegles) as erreur:
        print(f"ARRÊT : {erreur}", file=sys.stderr)
        return 1
    print(f"Phase « {a.phase} » terminée : {journal['unites_terminees']}/{journal['unites_total']} unités, "
          f"{C.nombre_fr(journal['cumul_reel_s'] / 60, 1)} min réelles pour {C.nombre_fr(journal['cumul_estime_s'] / 60, 1)} min estimées.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
