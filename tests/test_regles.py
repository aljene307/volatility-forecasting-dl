"""Tests des règles du projet (config/regles.toml et docs/REGLES.md)."""

import copy
import datetime as dt
import math
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

import regles as R  # noqa: E402

TEXTE_TOML = R.CHEMIN_REGLES.read_text(encoding="utf-8")
D = dt.date.fromisoformat


def _toml_modifie(tmp_path, ancien: str, nouveau: str) -> Path:
    """Copie du vrai fichier de règles avec une seule ligne modifiée."""
    assert TEXTE_TOML.count(ancien) == 1, f"Ligne introuvable ou ambiguë : {ancien}"
    chemin = tmp_path / "regles_modifiees.toml"
    chemin.write_text(TEXTE_TOML.replace(ancien, nouveau), encoding="utf-8")
    return chemin


# --- Le vrai fichier ---------------------------------------------------------

def test_le_fichier_se_charge_et_est_coherent():
    regles = R.charger_regles()
    assert regles["donnees"]["actifs"] == ["BTCUSDT", "ETHUSDT"]
    assert regles["decoupage"]["embargo_jours"] == 0


def test_prechauffage_et_premiere_cible():
    regles = R.charger_regles()
    pre = regles["decoupage"]["prechauffage"]
    assert (pre["debut"], pre["fin"]) == (D("2018-01-01"), D("2018-03-31"))
    assert (pre["fin"] - pre["debut"]).days + 1 == 90
    assert regles["decoupage"]["premiere_cible"] == D("2018-04-01")
    assert regles["donnees"]["debut"].year == 2018, "Aucune donnée de 2017."


def test_cinq_plis_annuels_en_dates_de_cible():
    """Exception du 2026-11-16 : 5 plis de 12 mois, mêmes jours évalués que les 10 plis de 6 mois."""
    plis = R.plis_walk_forward(R.charger_regles())
    assert len(plis) == 5
    assert plis[0] == (D("2020-01-01"), D("2020-12-31"))
    assert plis[-1] == (D("2024-01-01"), D("2024-12-31"))
    assert sum((fin - debut).days + 1 for debut, fin in plis) == (D("2024-12-31") - D("2020-01-01")).days + 1
    for (_, fin), (debut_suivant, _) in zip(plis, plis[1:]):
        assert debut_suivant == fin + R.UN_JOUR, "Les plis doivent se suivre sans trou ni recouvrement."


def test_separation_stricte_pour_chaque_pli_et_la_validation_interne():
    """Dernière cible d'apprentissage < première cible évaluée, pour les 5 plis et le test final."""
    liste = R.decoupages(R.charger_regles())
    assert len(liste) == 6
    for d in liste:
        assert d["ajustement"][1] < d["validation"][0], d["nom"]
        assert d["apprentissage"][1] < d["evaluation"][0], d["nom"]
        assert d["apprentissage"][0] == D("2018-04-01"), d["nom"]
    pli1 = liste[0]
    assert pli1["ajustement"] == (D("2018-04-01"), D("2019-06-30"))
    assert pli1["validation"] == (D("2019-07-01"), D("2019-12-31"))
    final = liste[-1]
    assert final["apprentissage"][1] == D("2024-12-31")
    assert final["evaluation"] == (D("2025-01-01"), D("2026-10-31"))
    assert R.problemes_separation(liste, 0) == []


def test_chaque_date_du_toml_est_dans_regles_md():
    texte_md = (RACINE / "docs" / "REGLES.md").read_text(encoding="utf-8")
    dates = R.toutes_les_dates(R.charger_regles())
    assert len(dates) >= 18, "Trop peu de dates lues : le parcours du TOML est suspect."
    absentes = [f"{cle} = {d.isoformat()}" for cle, d in dates.items() if d.isoformat() not in texte_md]
    assert not absentes, "Dates absentes de docs/REGLES.md : " + ", ".join(absentes)


@pytest.mark.parametrize("y, s2", [(math.log(0.02), 0.0), (-4.0, 0.25), (-3.2, 0.6)])
def test_volatilite_prevue_est_racine_de_exp_2y_plus_2s2(y, s2):
    attendu = math.sqrt(math.exp(2 * y + 2 * s2))
    assert math.isclose(R.variance_prevue_depuis_log(y, s2), math.exp(2 * y + 2 * s2), rel_tol=1e-9)
    assert math.isclose(R.volatilite_prevue_depuis_log(y, s2), attendu, rel_tol=1e-9)


def test_temoin_ancienne_formule_de_rv_ecartee():
    """Témoin : avec s2 > 0, l'ancienne formule exp(y + s2/2) donne une autre valeur ; elle n'est plus utilisée."""
    y, s2 = -4.0, 0.25
    assert not math.isclose(R.volatilite_prevue_depuis_log(y, s2), math.exp(y + s2 / 2), rel_tol=1e-6)
    assert R.volatilite_prevue_depuis_log(y, s2) > math.exp(y + s2 / 2), "sigma est au-dessus de la moyenne de RV."
    assert not hasattr(R, "retour_depuis_log")


def test_sensibilite_sans_correction_revient_a_exp_y():
    assert math.isclose(R.volatilite_prevue_depuis_log(-4.0, 0.0), math.exp(-4.0), rel_tol=1e-9)


@pytest.mark.parametrize("appel", [
    lambda: R.variance_prevue_depuis_log(-4.0, -0.1),
    lambda: R.volatilite_prevue(0.0),
    lambda: R.volatilite_prevue(-1e-6),
])
def test_temoin_valeurs_interdites_rejetees(appel):
    with pytest.raises(R.ErreurRegles):
        appel()


def test_regles_communes_de_la_volatilite_prevue():
    regles = R.charger_regles()
    assert regles["cible"]["retour_log"]["s2_mesuree_sur"] == "validation_interne"
    assert regles["cible"]["volatilite_prevue"]["usages"] == ["RMSE", "MAE", "strategie", "VaR"]
    assert regles["decoupage"]["walk_forward"]["ajustement_commun"] is True


@pytest.mark.parametrize("bougies, ecart, attendu", [
    (288, 5, True), (287, 5, True), (274, 60, True),
    (273, 5, False), (288, 65, False), (274, 61, False),
])
def test_jour_valide(bougies, ecart, attendu):
    assert R.jour_valide(R.charger_regles(), bougies, ecart) is attendu


def test_premier_jour_des_donnees():
    regles = R.charger_regles()
    rdt = regles["donnees"]["rendements"]
    assert rdt["premier_jour_donnees"] == D("2018-01-01") and rdt["premier_jour_rendements"] == 287
    assert R.jour_valide(regles, rdt["premier_jour_rendements"], 5)
    assert rdt["premier_jour_donnees"] < regles["decoupage"]["premiere_cible"], "Jamais une cible."


@pytest.mark.parametrize("taux, attendu", [
    ({"BTCUSDT": 0.01, "ETHUSDT": 0.05}, False),
    ({"BTCUSDT": 0.01, "ETHUSDT": 0.051}, True),
    ({"BTCUSDT": 0.06, "ETHUSDT": 0.00}, True),
])
def test_secours_pour_les_deux_actifs_si_un_seul_depasse(taux, attendu):
    assert R.secours_active(R.charger_regles(), taux) is attendu


def test_temoin_secours_refuse_un_actif_manquant():
    with pytest.raises(R.ErreurRegles):
        R.secours_active(R.charger_regles(), {"BTCUSDT": 0.01})


def test_modele_du_test_final_ecrit_dans_le_toml():
    regles = R.charger_regles()
    tf = regles["decoupage"]["modele_test_final"]
    assert (tf["ajustement_debut"], tf["ajustement_fin"]) == (D("2018-04-01"), D("2024-06-30"))
    assert (tf["validation_debut"], tf["validation_fin"]) == (D("2024-07-01"), D("2024-12-31"))
    final = R.decoupages(regles)[-1]
    assert final["ajustement"] == (tf["ajustement_debut"], tf["ajustement_fin"])
    assert final["validation"] == (tf["validation_debut"], tf["validation_fin"])


def test_validation_interne_est_la_fin_du_pli_precedent():
    """Plis annuels : la validation interne du pli k (6 mois) est la seconde moitié de la période évaluée
    du pli k-1 : du passé, pas une fuite."""
    liste = R.decoupages(R.charger_regles())
    for precedent, courant in zip(liste[:-2], liste[1:-1]):
        assert courant["validation"][1] == precedent["evaluation"][1], courant["nom"]
        assert precedent["evaluation"][0] < courant["validation"][0], courant["nom"]
        assert courant["validation"][1] < courant["evaluation"][0], courant["nom"]
        assert courant["validation"][0] == R.ajouter_mois(courant["evaluation"][0], -6), courant["nom"]


def test_reglage_une_fois_sur_le_premier_decoupage():
    """Exception du 2026-11-16 : hyperparamètres réglés une fois, avec l'information disponible fin 2019."""
    regles = R.charger_regles()
    rech = regles["entrainement"]["recherche"]
    pli1 = R.decoupages(regles)[0]
    assert (rech["reglage_ajustement_debut"], rech["reglage_ajustement_fin"]) == pli1["ajustement"]
    assert (rech["reglage_validation_debut"], rech["reglage_validation_fin"]) == pli1["validation"]
    assert rech["reglage_validation_fin"] == D("2019-12-31") < pli1["evaluation"][0]
    assert regles["modeles"]["graines_deep_learning"] == [0, 1, 2]


def _exposition_sans_annualisation(regles, vol_cible_annuelle, sigma_journaliere):
    """Implémentation volontairement fausse (oubli de racine(365)), utilisée comme témoin."""
    s = regles["strategie"]
    return min(max(vol_cible_annuelle / sigma_journaliere, s["exposition_min"]), s["exposition_max"])


@pytest.mark.parametrize("facteur_sigma, attendu", [(1.0, 1.0), (2.0, 0.5), (4.0, 0.25), (0.5, 1.0)])
def test_exposition_annualise_sigma_journaliere(facteur_sigma, attendu):
    """sigma journalière = facteur × (vol cible / racine(365)) : exposition = 1 / facteur, bornée à 1."""
    regles = R.charger_regles()
    vol_cible = 0.60
    sigma = facteur_sigma * vol_cible / math.sqrt(365)
    assert math.isclose(R.exposition(regles, vol_cible, sigma), attendu, rel_tol=1e-9)


def test_temoin_exposition_sans_annualisation_detectee():
    """Témoin : oublier racine(365) donne une exposition toujours bloquée à 1 ; le test ci-dessus l'aurait vu."""
    regles = R.charger_regles()
    vol_cible, sigma = 0.60, 2.0 * 0.60 / math.sqrt(365)
    assert math.isclose(R.exposition(regles, vol_cible, sigma), 0.5, rel_tol=1e-9)
    assert _exposition_sans_annualisation(regles, vol_cible, sigma) == 1.0


def test_exposition_bornee_et_sigma_nulle_refusee():
    regles = R.charger_regles()
    assert R.exposition(regles, 0.60, 1e-9) == 1.0
    assert R.exposition(regles, 0.60, 10.0) > 0
    with pytest.raises(R.ErreurRegles):
        R.exposition(regles, 0.60, 0.0)


def test_var_un_jour_sigma_journaliere():
    regles = R.charger_regles()
    assert math.isclose(R.var_un_jour(regles, 0.03), 1.6448536269514722 * 0.03, rel_tol=1e-9)


def test_temoin_var_avec_sigma_annualisee_detectee():
    """Témoin : passer une sigma annualisée multiplierait la VaR par racine(365), environ 19."""
    regles = R.charger_regles()
    juste = R.var_un_jour(regles, 0.03)
    fausse = R.var_un_jour(regles, 0.03 * math.sqrt(365))
    assert not math.isclose(juste, fausse, rel_tol=1e-3)
    assert math.isclose(fausse / juste, math.sqrt(365), rel_tol=1e-9)


@pytest.mark.parametrize("nombre_jours", [1827, 669])
def test_retards_hac_des_tests_principaux(nombre_jours):
    """5 plis réunis (1827 jours au plus, les mêmes qu'avec 10 plis) et test final (669 jours au plus)."""
    assert R.retards_hac(nombre_jours) == math.floor(4 * (nombre_jours / 100) ** (2 / 9))


@pytest.mark.parametrize("nombre_jours, attendu", [(100, 4), (182, 4), (1000, 6), (1826, 7)])
def test_retards_hac_newey_west(nombre_jours, attendu):
    assert R.retards_hac(nombre_jours) == attendu


VALEURS_MESUREES = ("projet.fils_calcul", "projet.seuil_memoire_libre_go", "modeles.budget_reglage")


def test_entrainement_accepte_avec_les_valeurs_mesurees():
    regles = R.charger_regles()
    assert R.valeurs_a_fixer(regles) == []
    R.verifier_pret_pour_entrainement(regles)
    assert R.main(["--entrainement"]) == 0


@pytest.mark.parametrize("cle", VALEURS_MESUREES)
def test_temoin_entrainement_refuse_si_une_valeur_redevient_a_fixer(cle):
    regles = R.charger_regles()
    section, nom = cle.split(".")
    regles[section][nom] = R.A_FIXER
    with pytest.raises(R.ErreurRegles, match=cle.replace(".", r"\.")):
        R.verifier_pret_pour_entrainement(regles)


def test_valeurs_du_toml_egales_au_rapport_de_mesures():
    """Les trois valeurs fixées sont celles calculées dans rapports/mesures_entrainement.json (aucune saisie à la main)."""
    import json
    rapport = json.loads((RACINE / "rapports" / "mesures_entrainement.json").read_text(encoding="utf-8"))
    regles = R.charger_regles()
    assert regles["projet"]["fils_calcul"] == rapport["fils_choisi"]
    assert regles["projet"]["seuil_memoire_libre_go"] == rapport["memoire"]["seuil_go"]
    assert regles["modeles"]["budget_reglage"] == rapport["budget"]["n"]
    assert rapport["budget"]["n_suffisant"] and rapport["memoire"]["seuil_acceptable"]
    assert rapport["alimentation_debut"]["secteur"] is True and rapport["alimentation_fin"]["secteur"] is True
    assert all(v["reproductible"] for v in rapport["fils"][str(rapport["fils_choisi"])].values())


# --- Témoins : des découpages et des fichiers volontairement faux doivent être rejetés

@pytest.mark.parametrize("periode, extrait", [
    ("apprentissage", "apprentissage (fin 2020-01-01) et évaluation"),
    ("ajustement", "ajustement (fin 2019-07-01) et validation interne"),
])
def test_temoin_chevauchement_rejete(periode, extrait):
    liste = copy.deepcopy(R.decoupages(R.charger_regles()))
    pli1 = liste[0]
    if periode == "apprentissage":
        pli1["apprentissage"] = (pli1["apprentissage"][0], pli1["evaluation"][0])
        pli1["validation"] = (pli1["validation"][0], pli1["evaluation"][0])
    else:
        pli1["ajustement"] = (pli1["ajustement"][0], pli1["validation"][0])
    problemes = R.problemes_separation(liste, 0)
    assert any(extrait in p for p in problemes), problemes


@pytest.mark.parametrize(
    "ancien, nouveau, extrait_attendu",
    [
        ("test_debut = 2025-01-01", "test_debut = 2024-06-01", "test final"),
        ("test_debut = 2025-01-01", "test_debut = 2024-12-31", "sans chevauchement"),
        ("plis_debut = 2020-01-01", "plis_debut = 2019-12-01", "après le premier apprentissage"),
        ("debut = 2022-11-01", "debut = 2025-11-01", "Crise ftx"),
        ("debut = 2020-03-01", "debut = 2019-11-01", "hors des plis"),
        ("exposition_max = 1.0", "exposition_max = 1.5", "exposition_max"),
        ("exposition_min = 0.0", "exposition_min = -0.5", "exposition_min"),
        ("nombre_plis = 5", "nombre_plis = 10", "Nombre de plis"),
        ("duree_pli_mois = 12", "duree_pli_mois = 6", "Nombre de plis"),
        ("reglage_validation_fin = 2019-12-31", "reglage_validation_fin = 2020-06-30", "Réglage des hyperparamètres"),
        ("reglage_ajustement_fin = 2019-06-30", "reglage_ajustement_fin = 2019-09-30", "Réglage des hyperparamètres"),
        ('optimiseur = "adamw"', 'optimiseur = "sgd"', "AdamW"),
        ('alimentation = "secteur_obligatoire"', 'alimentation = "indifferente"', "batterie"),
        ('test_principal = "plis_reunis"', 'test_principal = "10_plis_reunis"', "plis réunis"),
        ("exceptions_date = 2026-11-16", "exceptions_date = 2026-12-01", "exceptions_date"),
        ("date_precisions = 2026-11-16", "date_precisions = 2026-11-30", "date_precisions"),
        ('qlike_forme = "RV2/h - ln(RV2/h) - 1"', 'qlike_forme = "ln(h) + RV2/h"', "Patton"),
        ('prevision_modele_regle = "moyenne_des_log_des_graines"', 'prevision_modele_regle = "meilleure_graine"', "moyenne des log"),
        ("dans_selection = false", "dans_selection = true", "persistance est descriptive"),
        ('backcast = "calcule_sur_l_ajustement_puis_fixe"', 'backcast = "toute_la_serie"', "variance de départ"),
        ("bilateral = true", "bilateral = false", "bilatéral"),
        ('blocs = "mobiles"', 'blocs = "independants"', "blocs mobiles"),
        ('methode = "holm"', 'methode = "aucune"', "Holm"),
        ('significatif_selon = "p_valeur_ajustee"', 'significatif_selon = "p_valeur_brute"', "Holm"),
        ("date_tests_multiples = 2026-11-19", "date_tests_multiples = 2026-12-01", "date_tests_multiples"),
        ("seuil_alerte_gain_qlike = 0.20", "seuil_alerte_gain_qlike = 1.5", "Seuil d'alerte"),
        ('jour_non_valide = "pas_de_decision"', 'jour_non_valide = "decision_normale"', "aucune décision"),
        ('periode = "developpement_5_plis"           # jours évalués', 'periode = "test_final"           # jours évalués',
         "développement seulement"),
        ("additivite_tolerance_reseaux = 0.06", "additivite_tolerance_reseaux = 0.5", "tolérance d'additivité"),
        ("additivite_arret = true", "additivite_arret = false", "tolérance d'additivité"),
        ("fidelite_repetitions = 20", "fidelite_repetitions = 5", "au moins 20 répétitions"),
        ("date_precisions_strategie = 2026-11-19", "date_precisions_strategie = 2026-12-01", "date_precisions_strategie"),
        ("avenir_modifie_ecarts_admis = 0", "avenir_modifie_ecarts_admis = 3", "aucun écart"),
        ("avenir_modifie_jour = 2024-07-01", "avenir_modifie_jour = 2025-03-01", "à l'intérieur de la période évaluée"),
        ('sorties_journalieres = "sorties/"', 'sorties_journalieres = "rapports/"', "sorties/"),
        ("bougies_min = 274", "bougies_min = 273", "bougies_min"),
        ("vol_cible_fin = 2019-12-31", "vol_cible_fin = 2020-06-30", "volatilité cible"),
        ("premiere_cible = 2018-04-01", "premiere_cible = 2018-03-15", "suivre le préchauffage"),
        ("jours = 90", "jours = 91", "Préchauffage"),
        ("embargo_jours = 0", "embargo_jours = -1", "embargo"),
        ('convention_date = "cible"', 'convention_date = "variables"', "Convention de date"),
        ("seuil_secours = 0.05", "seuil_secours = 1.5", "seuil_secours"),
        ("ajustement_fin = 2024-06-30", "ajustement_fin = 2024-09-30", "Modèle du test final"),
        ("validation_debut = 2024-07-01", "validation_debut = 2024-01-01", "Modèle du test final"),
        ("seuil_mesure_fin = 2024-12-31", "seuil_mesure_fin = 2026-10-31", "jamais sur le test final"),
        ('s2_mesuree_sur = "validation_interne"', 's2_mesuree_sur = "apprentissage_du_pli"', "validation interne"),
        ("premier_jour_rendements = 287", "premier_jour_rendements = 288", "premier_jour_rendements"),
        ('facteur_appris_sur = "ajustement_du_pli"', 'facteur_appris_sur = "apprentissage_du_pli"', "GARCH"),
        ('parametres_appris_sur = "ajustement_du_pli"', 'parametres_appris_sur = "apprentissage_du_pli"', "GARCH"),
        ('var_volatilite = "sigma_journaliere"', 'var_volatilite = "sigma_annualisee"', "VaR"),
        ('echelle = "journaliere"', 'echelle = "annuelle"', "journalière"),
        ("date_ecriture = 2026-11-15", "date_ecriture = 2026-12-01", "date_ecriture"),
        ('jour_volume = "somme_volume_cotation"', 'jour_volume = "somme_volume"', "USDT"),
        ('macd_variable = "histogramme_divise_par_cloture"', 'macd_variable = "histogramme"', "MACD"),
        ('garde = "refus_sans_option"', 'garde = "refus_sauf_drapeau"', "contournement"),
        ('validite_en_entree = "passe_seulement"', 'validite_en_entree = "complete"', "Secours"),
        ('periode = "developpement_seulement"', 'periode = "tout"', "développement seulement"),
        ("acf_retards_rapportes = [1, 7, 30]", "acf_retards_rapportes = [1, 7, 90]", "autocorrélation"),
        ("date_ecriture = 2026-11-16", "date_ecriture = 2026-11-20", "entrainement.date_ecriture"),
        ("un_modele_par_actif = true", "un_modele_par_actif = false", "Un modèle par actif"),
        ('tft_perte = "mse"', 'tft_perte = "quantile"', "TFT compris"),
        ("patience_epoques = 20", "patience_epoques = 250", "patience_epoques"),
        ("d_model = [16, 32, 64]", "d_model = [16, 30, 64]", "divisible"),
        ('reperes_non_entrees = ["jour_remplace"', 'reperes_non_entrees = ["rv_1"', "repère"),
        ('modeles_regles = ["XGBoost", "LSTM", "GRU", "CNN-LSTM", "Transformer", "TFT"]',
         'modeles_regles = ["XGBoost", "LSTM"]', "même nombre N"),
        ('graine_unite = "hachage_de_l_identifiant"', 'graine_unite = "ordre_d_execution"', "Reprise"),
        ('donnees = "aleatoires_meme_forme"', 'donnees = "vraies"', "aléatoires"),
    ],
)
def test_temoin_toml_faux_rejete(tmp_path, ancien, nouveau, extrait_attendu):
    chemin = _toml_modifie(tmp_path, ancien, nouveau)
    with pytest.raises(R.ErreurRegles) as erreur:
        R.charger_regles(chemin)
    assert extrait_attendu in str(erreur.value)
