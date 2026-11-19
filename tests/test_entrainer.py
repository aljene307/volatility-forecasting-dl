"""Tests de l'entraînement du deep learning (données synthétiques, 2 époques, témoins)."""

import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

import entrainer as E  # noqa: E402
import regles as R  # noqa: E402
import reprise as P  # noqa: E402

REGLES = R.charger_regles()
E.configurer_torch(REGLES)
D = dt.date.fromisoformat
UTC = "UTC"
DEBUT, FIN = D("2018-01-01"), D("2020-12-31")
PLI1 = R.decoupages(REGLES)[0]
SECTEUR = {"secteur": True, "batterie_pourcent": 80, "mode": None}

COMMUN = {"dropout": 0.1, "taux_apprentissage": 1e-3, "lot": 64, "weight_decay": 1e-5}
PETITES = {
    "LSTM": {"taille_cachee": 8, "couches": 1, **COMMUN},
    "GRU": {"taille_cachee": 8, "couches": 2, **COMMUN},
    "CNN-LSTM": {"filtres": 8, "noyau": 3, "taille_cachee": 8, "couches": 1, **COMMUN},
    "Transformer": {"d_model": 16, "tetes": 2, "couches": 1, "dimension_feed_forward": 32, **COMMUN},
    "TFT": {"hidden_size": 8, "tetes_attention": 1, "hidden_continuous_size": 8, **COMMUN},
}


def bougies_synthetiques(graine=0) -> pd.DataFrame:
    dates = pd.date_range(pd.Timestamp(DEBUT, tz=UTC), pd.Timestamp(FIN + dt.timedelta(days=1), tz=UTC),
                          freq="5min", inclusive="left").astype("datetime64[us, UTC]")
    rng = np.random.default_rng(graine)
    n = len(dates)
    vol = np.repeat(np.exp(np.cumsum(rng.normal(0, 0.15, n // 288)) * 0.3) * 0.002, 288)[:n]
    cloture = 100 * np.exp(np.cumsum(rng.normal(0, 1, n) * vol))
    ouverture = np.r_[100.0, cloture[:-1]]
    return pd.DataFrame({
        "date_ouverture": dates, "ouverture": ouverture,
        "plus_haut": np.maximum(ouverture, cloture) * (1 + np.abs(rng.normal(0, 0.0005, n))),
        "plus_bas": np.minimum(ouverture, cloture) * (1 - np.abs(rng.normal(0, 0.0005, n))),
        "cloture": cloture, "volume_cotation": rng.uniform(1e5, 1e6, n)})


BOUGIES = bougies_synthetiques()
DONNEES = E.donnees_reseaux(BOUGIES, REGLES, DEBUT, FIN)
J = D("2020-03-15")


def modifier_apres(b: pd.DataFrame, j: dt.date) -> pd.DataFrame:
    """Toutes les bougies après la fin de J : prix et volumes × 10 avec un bruit (comme à l'étape 4)."""
    b = b.copy()
    apres = (b["date_ouverture"] >= pd.Timestamp(j + dt.timedelta(days=1), tz=UTC)).to_numpy()
    f = 10 * (1 + np.random.default_rng(5).uniform(-0.5, 0.5, int(apres.sum())))
    for k in ("ouverture", "plus_haut", "plus_bas", "cloture", "volume_cotation"):
        b.loc[apres, k] = b.loc[apres, k].to_numpy() * f
    return b


def unite(modele: str, donnees=DONNEES, graine: int = 7):
    return E.entrainer_unite(modele, PETITES[modele], *donnees, PLI1, graine, REGLES, avec_evaluation=True, epoques_max=2)


def ecarts_passe(reference: dict, nouveau: dict, j: dt.date) -> bool:
    """Vrai si une prévision d'une origine <= J a changé (comparaison au bit près)."""
    garder = np.array([D(x) - dt.timedelta(days=1) <= j for x in reference["evaluation"]["date_cible"]])
    a = np.array(reference["evaluation"]["prevision_log"])[garder]
    b = np.array(nouveau["evaluation"]["prevision_log"])[: garder.sum()]
    return not np.array_equal(a.view("<i8"), b.view("<i8"))


DONNEES_MODIFIEES = E.donnees_reseaux(modifier_apres(BOUGIES, J), REGLES, DEBUT, FIN)


@pytest.mark.parametrize("modele", E.MODELES)
def test_avenir_modifie_aucune_prevision_passee_ne_change(modele):
    reference, _, _ = unite(modele)
    nouveau, _, _ = unite(modele, DONNEES_MODIFIEES)
    assert not ecarts_passe(reference, nouveau, J)


def test_temoin_sequence_qui_inclut_j_plus_1_detectee(monkeypatch):
    def sequences_tricheuses(tableau, index_jours, origines, longueur):
        position = {j: i for i, j in enumerate(index_jours)}
        p = np.array([position[j] for j in origines]) + 1          # la séquence finit à J+1 : triche
        return tableau[p[:, None] + np.arange(-longueur + 1, 1)[None, :]]

    monkeypatch.setattr(E, "sequences", sequences_tricheuses)
    reference, _, _ = unite("LSTM")
    nouveau, _, _ = unite("LSTM", DONNEES_MODIFIEES)
    assert ecarts_passe(reference, nouveau, J)


@pytest.mark.parametrize("modele", ["LSTM", "Transformer", "TFT"])
def test_meme_unite_deux_fois_identique(modele):
    a, ra, _ = unite(modele)
    b, rb, _ = unite(modele)
    assert a["evaluation"]["prevision_log"] == b["evaluation"]["prevision_log"]
    assert a["validation"]["prevision_log"] == b["validation"]["prevision_log"]
    for (ka, va), (kb, vb) in zip(ra.state_dict().items(), rb.state_dict().items()):
        assert ka == kb and np.array_equal(va.numpy(), vb.numpy()), ka


def test_sequence_finit_a_j_et_normalisation_sur_l_ajustement():
    exemples, journalier = DONNEES
    norm = E.apprendre_normalisation(journalier, exemples, PLI1, REGLES)
    assert D(norm["jours_utilises"][1]) == PLI1["ajustement"][1] - dt.timedelta(days=1)
    tableau = E.tableau_normalise(journalier, norm)
    seq = E.sequences(tableau, journalier.index, [J], 30)
    position = list(journalier.index).index(J)
    assert np.array_equal(seq[0, -1], tableau[position]) and np.array_equal(seq[0, 0], tableau[position - 29])
    assert seq.shape == (1, 30, len(REGLES["entrainement"]["variables_continues"]) + 7)


def test_tft_recoit_le_jour_de_la_semaine_de_la_cible_et_rien_d_autre_du_futur():
    exemples, journalier = DONNEES
    norm = E.apprendre_normalisation(journalier, exemples, PLI1, REGLES)
    table = E.table_tft(journalier, norm)
    cible = D("2019-03-14")
    jeu = E.jeu_tft(table, [cible], 30)
    assert jeu.time_varying_known_categoricals == ["jour_semaine"] and jeu.time_varying_known_reals == []
    x, _ = next(iter(jeu.to_dataloader(train=False, batch_size=1, num_workers=0)))
    code = int(x["decoder_cat"][0, 0, jeu.categoricals.index("jour_semaine")])
    codes = jeu._categorical_encoders["jour_semaine"].classes_         # encodeur ajusté : libellé -> code
    assert {v: k for k, v in codes.items()}[code] == str(cible.weekday())
    assert int(x["decoder_time_idx"][0, 0]) == (cible - dt.date(1970, 1, 1)).days
    assert int(x["encoder_lengths"][0]) == 30 and int(x["decoder_lengths"][0]) == 1
    import reseaux
    from pytorch_forecasting import TemporalFusionTransformer
    tft = TemporalFusionTransformer.from_dataset(jeu, hidden_size=8, attention_head_size=1, hidden_continuous_size=8,
                                                 loss=reseaux.perte_mse_tft(), output_size=1)
    assert tft.decoder_variables == ["jour_semaine"]


# --- Reprise et règle de suivi ------------------------------------------------------------------

def _calcul_lstm(identifiant: str, graine: int) -> dict:
    resultat, _, _ = E.entrainer_unite("LSTM", PETITES["LSTM"], *DONNEES, PLI1, graine, REGLES, avec_evaluation=False, epoques_max=1)
    resultat.pop("duree_s")
    resultat.pop("temps_epoques_s")
    return resultat


class Coupure(Exception):
    pass


def test_reprise_interrompue_puis_relancee_identique(tmp_path):
    unites = [f"TEST|LSTM|pli 1|graine {g}" for g in range(3)]
    P.executer(unites, _calcul_lstm, tmp_path / "sans", alimentation=lambda: SECTEUR)
    compte = {"n": 0}

    def coupe(identifiant, graine):
        if compte["n"] == 1:
            raise Coupure()
        compte["n"] += 1
        return _calcul_lstm(identifiant, graine)

    with pytest.raises(Coupure):
        P.executer(unites, coupe, tmp_path / "avec", alimentation=lambda: SECTEUR)
    assert P.executer(unites, _calcul_lstm, tmp_path / "avec", alimentation=lambda: SECTEUR) == {"calculees": 2, "sautees": 1}
    lire = lambda d: {f.name: f.read_bytes() for f in sorted(d.glob("*.json"))}  # noqa: E731
    assert lire(tmp_path / "sans") == lire(tmp_path / "avec")


def test_regle_de_suivi_seuil_de_50_pourcent():
    E.verifier_suivi(150.0, 100.0, REGLES)                     # exactement +50 % : on continue
    with pytest.raises(E.ArretSuivi, match="règle de suivi"):
        E.verifier_suivi(150.1, 100.0, REGLES)


def test_regle_de_suivi_arrete_apres_l_unite_en_cours(tmp_path, monkeypatch):
    """Temps simulé : chaque unité dure 3 fois l'estimation ; l'arrêt arrive avant la 2e unité, la 1re est gardée."""
    estimation = E.estimation_par_unite(REGLES)
    unites = [(f"TEST|LSTM|pli 1|graine {g}", "LSTM") for g in range(3)]
    calcul = lambda identifiant, graine: {"duree_s": 3 * estimation["LSTM"], "epoques": 100}  # noqa: E731
    opt = E.Options(REGLES, tmp_path)
    vrai = P.executer
    monkeypatch.setattr(P, "executer", lambda u, c, d: vrai(u, c, d, alimentation=lambda: SECTEUR))
    with pytest.raises(E.ArretSuivi):
        E._executer("plis", unites, calcul, opt, REGLES)
    journal = (tmp_path / "journal.json").read_text(encoding="utf-8")
    assert '"unites_terminees": 1' in journal and "règle de suivi" in journal


def test_suivi_affiche_l_avancement_en_francais(tmp_path):
    import suivi
    estimation = E.estimation_par_unite(REGLES)
    unites = [("TEST|LSTM|a", "LSTM"), ("TEST|TFT|b", "TFT")]
    P.ecrire_unite(tmp_path / "unites", "TEST|LSTM|a", 1, {"duree_s": 120.0, "epoques": 40})
    E.ecrire_journal(tmp_path, "plis", unites, tmp_path / "unites", estimation, 0.0, "en cours")
    texte = suivi.texte_suivi(__import__("json").loads((tmp_path / "journal.json").read_text(encoding="utf-8")))
    assert "Unités terminées : 1 sur 2" in texte and "LSTM" in texte and "3,00 s" in texte


def test_combinaisons_identiques_pour_les_deux_actifs_et_valides():
    for modele in E.MODELES:
        a, ecartes = E.combinaisons(REGLES, modele)
        assert a == E.combinaisons(REGLES, modele)[0] and len(a) == REGLES["modeles"]["budget_reglage"]
        assert all(E.valide(modele, c) for c in a)
    tft, ecartes_tft = E.combinaisons(REGLES, "TFT")
    assert all(c["hidden_continuous_size"] <= c["hidden_size"] for c in tft)
