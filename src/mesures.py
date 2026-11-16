"""Mesures sur données ALÉATOIRES pour fixer fils_calcul, seuil_memoire_libre_go et budget_reglage.

Règles : config/regles.toml, section entrainement.mesures (précisions du 2026-11-16).
- Aucune vraie donnée n'est lue : un crochet d'audit refuse toute ouverture dans data/, et les
  fonctions de lecture de pandas et pyarrow (qui ouvrent les fichiers en C++) sont remplacées par un refus.
- Chaque mesure tourne dans son propre processus Python (fils de calcul fixés avant d'importer torch,
  mémoire maximale propre à la mesure).
- Configuration « médiane » d'un espace : valeur du milieu ; pour un nombre pair de valeurs, la plus
  coûteuse des deux du milieu (plus grande taille, plus petit lot) ; loi log-uniforme : moyenne géométrique.

Sortie : rapports/mesures_entrainement.json (temps, déterminisme, mémoire, calcul de N).

Usage : .venv\\Scripts\\python src/mesures.py
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_DATA = (RACINE / "data").resolve()
sys.path.insert(0, str(RACINE / "src"))

import commun as C  # noqa: E402
import regles as R  # noqa: E402

CHEMIN_RAPPORT = C.DOSSIER_RAPPORTS / "mesures_entrainement.json"
LONGUEUR = 30            # variables.fenetre_sequence_jours
VALIDATION = 184         # 6 mois de cibles de validation interne


# --- Interdiction de lire les vraies données ----------------------------------------------

def interdire_donnees() -> None:
    """Refuse toute ouverture de fichier ou de dossier dans data/ pour le reste du processus."""
    en_cours = False

    def crochet(evenement: str, arguments: tuple) -> None:
        nonlocal en_cours
        if en_cours or evenement not in ("open", "os.listdir", "os.scandir", "glob.glob", "shutil.copyfile") or not arguments:
            return
        chemin = arguments[0]
        if not isinstance(chemin, (str, bytes, os.PathLike)):
            return
        en_cours = True
        try:
            absolu = Path(os.fsdecode(chemin)).resolve()
        except (OSError, ValueError):
            return
        finally:
            en_cours = False
        if absolu == DOSSIER_DATA or DOSSIER_DATA in absolu.parents:
            raise PermissionError(f"Lecture interdite pendant les mesures : {absolu.relative_to(RACINE).as_posix()}")

    sys.addaudithook(crochet)
    import pandas
    import pyarrow.parquet as pq

    def refus(*_args, **_kwargs):
        raise PermissionError("Lecture de fichiers de données interdite pendant les mesures (données aléatoires seulement).")

    for nom in ("read_parquet", "read_csv", "read_json", "read_feather", "read_pickle", "read_table"):
        setattr(pandas, nom, refus)
    for nom in ("read_table", "ParquetFile", "read_schema", "read_metadata", "ParquetDataset"):
        setattr(pq, nom, refus)


# --- Configurations ------------------------------------------------------------------------

def _geo(loi: dict) -> float:
    return math.sqrt(loi["min"] * loi["max"])


def configurations(regles: dict) -> dict:
    """Configurations médianes (temps) et plus grandes (mémoire), lues dans les espaces du TOML."""
    e = regles["entrainement"]["espaces"]
    lstm = e["lstm"]
    commun_lstm = {"dropout": 0.2, "taux_apprentissage": _geo(lstm["taux_apprentissage"]), "lot": min(lstm["lot"]),
                   "weight_decay": _geo(lstm["weight_decay"])}
    rec = {"taille_cachee": 32, "couches": max(lstm["couches"]), **commun_lstm}
    tft = e["tft"]
    tr = e["transformer"]
    return {
        "mediane": {
            "lstm": rec, "gru": rec,
            "cnn_lstm": {"filtres": max(e["cnn_lstm"]["filtres"]), "noyau": max(e["cnn_lstm"]["noyau"]), **rec},
            "transformer": {"d_model": 32, "tetes": max(tr["tetes"]), "couches": max(tr["couches"]),
                            "dimension_feed_forward": max(tr["dimension_feed_forward"]), **commun_lstm},
            "tft": {"hidden_size": 16, "tetes_attention": 2, "hidden_continuous_size": 16, **commun_lstm},
        },
        "plus_grande": {
            "transformer": {"d_model": max(tr["d_model"]), "tetes": max(tr["tetes"]), "couches": max(tr["couches"]),
                            "dimension_feed_forward": max(tr["dimension_feed_forward"]), **commun_lstm, "lot": max(lstm["lot"])},
            "tft": {"hidden_size": max(tft["hidden_size"]), "tetes_attention": max(tft["tetes_attention"]),
                    "hidden_continuous_size": max(tft["hidden_continuous_size"]), **commun_lstm, "lot": max(lstm["lot"])},
        },
    }


# --- Travail d'une mesure (dans un processus séparé) -------------------------------------

def _empreinte_tenseurs(tenseurs) -> str:
    h = hashlib.sha256()
    for t in tenseurs:
        h.update(t.detach().cpu().contiguous().numpy().astype("<f4").tobytes())
    return h.hexdigest()


def _donnees(regles: dict, graine: int):
    import numpy as np
    n = regles["entrainement"]["mesures"]["exemples"]
    k = len(regles["entrainement"]["variables_continues"])
    rng = np.random.default_rng(graine)
    x = rng.normal(size=(n + VALIDATION + LONGUEUR - 1, k)).astype("float32")
    jour = np.arange(len(x)) % 7
    y = rng.normal(size=n + VALIDATION).astype("float32")
    return x, jour, y, n


def _sequences(regles: dict, graine: int):
    import numpy as np
    import torch
    x, jour, y, n = _donnees(regles, graine)
    complet = np.concatenate([x, np.eye(7, dtype="float32")[jour]], axis=1)
    seq = torch.from_numpy(complet).unfold(0, LONGUEUR, 1).transpose(1, 2).contiguous()
    cible = torch.from_numpy(y)
    return seq[:n], cible[:n], seq[n:], cible[n:]


def _reseau(nom: str, config: dict, n_entrees: int):
    import reseaux
    if nom in ("lstm", "gru"):
        return reseaux.ReseauRecurrent(nom, n_entrees, config["taille_cachee"], config["couches"], config["dropout"])
    if nom == "cnn_lstm":
        return reseaux.CnnLstm(n_entrees, config["filtres"], config["noyau"], config["taille_cachee"], config["couches"],
                               config["dropout"])
    return reseaux.TransformerEncodeur(n_entrees, LONGUEUR, config["d_model"], config["tetes"], config["couches"],
                                       config["dimension_feed_forward"], config["dropout"])


def travail_reseau(regles: dict, nom: str, config: dict, epoques: int, graine: int) -> dict:
    import torch
    torch.manual_seed(graine)
    xa, ya, xv, yv = _sequences(regles, graine)
    modele = _reseau(nom, config, xa.shape[2])
    opt = torch.optim.AdamW(modele.parameters(), lr=config["taux_apprentissage"], weight_decay=config["weight_decay"])
    generateur = torch.Generator().manual_seed(graine)
    temps = []
    for _ in range(epoques):
        debut = time.perf_counter()
        modele.train()
        for idx in torch.randperm(len(xa), generator=generateur).split(config["lot"]):
            opt.zero_grad()
            perte = torch.nn.functional.mse_loss(modele(xa[idx]), ya[idx])
            perte.backward()
            opt.step()
        modele.eval()
        with torch.no_grad():
            torch.nn.functional.mse_loss(modele(xv), yv)
        temps.append(time.perf_counter() - debut)
    return {"temps_epoques_s": temps, "empreinte_poids": _empreinte_tenseurs(modele.parameters()),
            "parametres": sum(p.numel() for p in modele.parameters())}


def travail_tft(regles: dict, config: dict, epoques: int, graine: int, allege: bool = True, dossier: str | None = None) -> dict:
    """Entraîne le TFT sur des données aléatoires.

    `allege` : sans barre de progression, journaux, sauvegardes automatiques ni résumé du modèle (réglage du projet).
    Sinon, réglages par défaut de Lightning, dans `dossier` (pour prouver que l'allègement ne change pas les prévisions).
    """
    import warnings
    warnings.filterwarnings("ignore")
    import logging
    logging.getLogger("lightning.pytorch").setLevel(logging.ERROR)
    import numpy as np
    import pandas as pd
    import lightning.pytorch as pl
    import torch
    from pytorch_forecasting import TemporalFusionTransformer, TimeSeriesDataSet
    from pytorch_forecasting.data.encoders import NaNLabelEncoder, TorchNormalizer
    import reseaux

    pl.seed_everything(graine, workers=True, verbose=False)
    x, jour, y, n = _donnees(regles, graine)
    noms = [f"x{i}" for i in range(x.shape[1])]
    df = pd.DataFrame(x, columns=noms)
    df["time_idx"] = np.arange(len(df))
    df["groupe"] = "a"
    df["jour_semaine"] = jour.astype(str)
    df["y"] = np.r_[np.zeros(LONGUEUR - 1, dtype="float32"), y]
    fin_apprentissage = LONGUEUR - 1 + n - 1
    commun = dict(time_idx="time_idx", target="y", group_ids=["groupe"], max_encoder_length=LONGUEUR,
                  min_encoder_length=LONGUEUR, max_prediction_length=1, time_varying_known_categoricals=["jour_semaine"],
                  time_varying_unknown_reals=["y"] + noms, target_normalizer=TorchNormalizer(method="identity", center=False),
                  scalers={k: None for k in noms},
                  categorical_encoders={"jour_semaine": NaNLabelEncoder(add_nan=False), "groupe": NaNLabelEncoder(add_nan=False)},
                  add_relative_time_idx=False, add_target_scales=False, add_encoder_length=False)
    apprentissage = TimeSeriesDataSet(df[df["time_idx"] <= fin_apprentissage], **commun)
    validation = TimeSeriesDataSet.from_dataset(apprentissage, df, min_prediction_idx=fin_apprentissage + 1, stop_randomization=True)
    tft = TemporalFusionTransformer.from_dataset(
        apprentissage, hidden_size=config["hidden_size"], attention_head_size=config["tetes_attention"],
        hidden_continuous_size=config["hidden_continuous_size"], dropout=config["dropout"], loss=reseaux.perte_mse_tft(),
        learning_rate=config["taux_apprentissage"], optimizer="adamw", weight_decay=config["weight_decay"], output_size=1)
    temps, debuts = [], {}

    class Chrono(pl.Callback):
        def on_train_epoch_start(self, trainer, module):
            debuts["e"] = time.perf_counter()

        def on_validation_epoch_end(self, trainer, module):
            if "e" in debuts and not trainer.sanity_checking:
                temps.append(time.perf_counter() - debuts.pop("e"))

    if allege:
        options = dict(logger=False, enable_checkpointing=False, enable_progress_bar=False, enable_model_summary=False,
                       num_sanity_val_steps=0)
    else:
        options = dict(default_root_dir=dossier, num_sanity_val_steps=0)   # journaux, sauvegardes, barre, résumé : par défaut
    entraineur = pl.Trainer(max_epochs=epoques, accelerator="cpu", deterministic=True, callbacks=[Chrono()], **options)
    chargeur_validation = validation.to_dataloader(train=False, batch_size=config["lot"], num_workers=0)
    entraineur.fit(tft, train_dataloaders=apprentissage.to_dataloader(train=True, batch_size=config["lot"], num_workers=0),
                   val_dataloaders=chargeur_validation)
    tft.eval()
    with torch.no_grad():
        previsions = torch.cat([tft(xb)["prediction"].reshape(-1) for xb, _ in chargeur_validation])
    return {"temps_epoques_s": temps, "empreinte_poids": _empreinte_tenseurs(tft.parameters()),
            "empreinte_previsions": _empreinte_tenseurs([previsions]),
            "parametres": sum(p.numel() for p in tft.parameters()), "echantillons": len(apprentissage)}


def travail_xgboost(regles: dict, fils: int, graine: int) -> dict:
    import numpy as np
    import xgboost as xgb
    x, jour, y, n = _donnees(regles, graine)
    tableau = np.concatenate([x[LONGUEUR - 1:], jour[LONGUEUR - 1:, None]], axis=1)
    e = regles["entrainement"]["espaces"]["xgboost"]
    modele = xgb.XGBRegressor(n_estimators=regles["entrainement"]["xgboost_arbres_max"], max_depth=4,
                              learning_rate=_geo(e["learning_rate"]), subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
                              reg_lambda=_geo(e["reg_lambda"]), tree_method="hist", n_jobs=fils, random_state=graine)
    debut = time.perf_counter()
    modele.fit(tableau[:n], y[:n])   # 2000 arbres sans arrêt anticipé : estimation prudente
    temps = time.perf_counter() - debut
    prevision = modele.predict(tableau[n:]).astype("<f4")
    return {"temps_ajustement_s": temps, "empreinte_previsions": hashlib.sha256(prevision.tobytes()).hexdigest()}


def travailleur(demande: dict) -> dict:
    """Exécute une mesure dans ce processus (appelé avec --travail)."""
    interdire_donnees()
    import torch
    fils = demande["fils"]
    torch.set_num_threads(fils)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    regles = R.charger_regles()
    if demande["modele"] == "xgboost":
        resultat = travail_xgboost(regles, fils, demande["graine"])
    elif demande["modele"] == "tft":
        resultat = travail_tft(regles, demande["config"], demande["epoques"], demande["graine"],
                               demande.get("allege", True), demande.get("dossier"))
    else:
        resultat = travail_reseau(regles, demande["modele"], demande["config"], demande["epoques"], demande["graine"])
    resultat["fils_torch"] = torch.get_num_threads()
    resultat["memoire_max_mo"] = C.memoire_max_mo()
    return resultat


# --- Orchestration --------------------------------------------------------------------------

def lancer(demande: dict) -> dict:
    C.verifier_secteur(contexte="avant une mesure")   # sur batterie : arrêt (temps non fiables)
    env = dict(os.environ)
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        env[var] = str(demande["fils"])
    env["PYTHONIOENCODING"] = "utf-8"
    sortie = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--travail", json.dumps(demande)],
                            capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(RACINE))
    lignes = [l for l in sortie.stdout.splitlines() if l.startswith("RESULTAT ")]
    if sortie.returncode != 0 or not lignes:
        raise RuntimeError(f"Mesure en échec ({demande['modele']}, {demande['fils']} fils) :\n{sortie.stderr[-3000:]}")
    resultat = json.loads(lignes[-1][len("RESULTAT "):])
    print(f"  {demande['modele']:<12} {demande['fils']} fils : "
          + (f"{resultat['temps_ajustement_s']:.1f} s" if "temps_ajustement_s" in resultat
             else "époques " + ", ".join(f"{t:.1f}" for t in resultat["temps_epoques_s"]) + " s")
          + f" | {resultat['memoire_max_mo']:.0f} Mo", flush=True)
    return resultat


def arrondi_superieur(valeur: float, pas: float) -> float:
    return math.ceil(round(valeur / pas, 9)) * pas


def calcul_n(temps_epoque: dict[str, float], regles: dict) -> dict:
    """Exception du 2026-11-16 : plus grand entier N tel que
    actifs × Σ modèles (médiane d'une époque × époques estimées) × (N + graines × découpages) <= budget."""
    m = regles["entrainement"]["mesures"]
    decoupages = len(R.decoupages(regles))
    actifs = len(regles["donnees"]["actifs"])
    graines = len(regles["modeles"]["graines_deep_learning"])
    par_entrainement = {k: t * m["epoques_estimees"] for k, t in temps_epoque.items()}
    somme = sum(par_entrainement.values())
    budget_s = m["budget_heures_deep_learning"] * 3600
    n = math.floor(budget_s / (actifs * somme) - graines * decoupages)
    total = lambda nn: actifs * somme * (nn + graines * decoupages)  # noqa: E731
    return {"formule": m["formule_n"], "actifs": actifs, "decoupages": decoupages, "graines": graines,
            "epoques_estimees": m["epoques_estimees"], "temps_entrainement_s": par_entrainement,
            "somme_des_5_modeles_s": somme, "budget_s": budget_s, "n": n,
            "entrainements_par_modele_et_actif": max(n, 0) + graines * decoupages,
            "total_estime_s_pour_n": total(max(n, 0)), "total_estime_h_pour_n": total(max(n, 0)) / 3600,
            "n_suffisant": n >= m["n_minimum"]}


def _statistiques(valeurs: list[float]) -> dict:
    ordre = sorted(valeurs)
    return {"mediane": ordre[len(ordre) // 2] if len(ordre) % 2 else (ordre[len(ordre) // 2 - 1] + ordre[len(ordre) // 2]) / 2,
            "min": ordre[0], "max": ordre[-1], "valeurs": valeurs}


def orchestrer() -> dict:
    regles = R.charger_regles()
    cfg = configurations(regles)
    m = regles["entrainement"]["mesures"]
    candidats = regles["projet"]["fils_calcul_candidats"]
    alimentation = C.verifier_secteur(contexte="début des mesures")
    rapport = {"alimentation_debut": alimentation, "powercfg": _powercfg(), "memoire_libre_debut_go": C.memoire_libre_go(),
               "configurations": cfg, "repetitions": m["repetitions"], "fils": {}}
    print(f"Alimentation : {alimentation} | mémoire libre : {rapport['memoire_libre_debut_go']:.2f} Go", flush=True)
    modeles = ["lstm", "gru", "cnn_lstm", "transformer", "tft"]
    for fils in candidats:
        print(f"Fils de calcul : {fils}", flush=True)
        resultat = {}
        for nom in modeles + ["xgboost"]:
            essais = []
            for _ in range(m["repetitions"]):
                demande = {"modele": nom, "fils": fils, "graine": 0}
                if nom != "xgboost":
                    demande.update(config=cfg["mediane"][nom], epoques=2)
                essais.append(lancer(demande))
            if nom == "xgboost":
                temps, cle = [e["temps_ajustement_s"] for e in essais], "empreinte_previsions"
            else:
                temps, cle = [e["temps_epoques_s"][-1] for e in essais], "empreinte_poids"   # 2e époque : sans le démarrage
            resultat[nom] = {**_statistiques(temps), "reproductible": len({e[cle] for e in essais}) == 1}
        rapport["fils"][str(fils)] = resultat
    reproductibles = [f for f, r in rapport["fils"].items() if all(v["reproductible"] for v in r.values())]
    choisi = min(reproductibles, key=lambda f: sum(rapport["fils"][f][k]["mediane"] for k in modeles)) if reproductibles else None
    rapport["fils_choisi"] = int(choisi) if choisi else None
    fils = int(choisi) if choisi else candidats[0]
    print("Mémoire, plus grandes configurations", flush=True)
    rapport["memoire_libre_avant_memoire_go"] = C.memoire_libre_go()
    pics = {nom: lancer({"modele": nom, "config": cfg["plus_grande"][nom], "fils": fils, "epoques": 1, "graine": 0})["memoire_max_mo"]
            for nom in ("tft", "transformer")}
    pic_go = max(pics.values()) / 1024
    seuil = arrondi_superieur(pic_go * m["marge_memoire"], m["arrondi_memoire_go"])
    rapport["memoire"] = {"pics_mo": pics, "pic_max_go": pic_go, "seuil_go": seuil,
                          "seuil_acceptable": seuil <= m["seuil_memoire_max_go"]}
    rapport["budget"] = calcul_n({k: rapport["fils"][str(fils)][k]["mediane"] for k in modeles}, regles)
    b = rapport["budget"]
    rapport["xgboost_total_estime_s"] = b["actifs"] * b["entrainements_par_modele_et_actif"] * rapport["fils"][str(fils)]["xgboost"]["mediane"]
    rapport["alimentation_fin"] = C.verifier_secteur(contexte="fin des mesures")
    rapport["memoire_libre_fin_go"] = C.memoire_libre_go()
    C.ecrire_texte(CHEMIN_RAPPORT, C.texte_json(rapport))
    return rapport


def _powercfg() -> str:
    """Mode de gestion actif de Windows (powercfg /getactivescheme)."""
    if sys.platform != "win32":
        return ""
    sortie = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, text=True)
    return sortie.stdout.strip()


def main(arguments: list[str]) -> int:
    C.proteger_sortie()
    if arguments[:1] == ["--travail"]:
        print("RESULTAT " + json.dumps(travailleur(json.loads(arguments[1]))), flush=True)
        return 0
    interdire_donnees()
    debut = time.perf_counter()
    try:
        rapport = orchestrer()
    except C.ErreurAlimentation as erreur:
        print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1
    b = rapport["budget"]
    print(f"Fils choisi : {rapport['fils_choisi']} | seuil mémoire : {rapport['memoire']['seuil_go']} Go | N = {b['n']} "
          f"({'suffisant' if b['n_suffisant'] else 'INSUFFISANT'}) | total estimé : {b['total_estime_h_pour_n']:.1f} h")
    print(f"Rapport : {C.chemin_relatif(CHEMIN_RAPPORT)} | durée totale : {C.nombre_fr(time.perf_counter() - debut, 0)} s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
