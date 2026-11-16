"""Tests de la reprise après interruption, du seuil de mémoire et de l'interdiction de lire les vraies données."""

import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

import commun as C  # noqa: E402
import regles as R  # noqa: E402
import reprise as P  # noqa: E402

UNITES = [f"TEST|LSTM|pli {p}|combinaison {c}|graine {g}" for p in (1, 2) for c in (0, 1) for g in (0, 1)]
SECTEUR = {"secteur": True, "batterie_pourcent": 80, "mode": None}
BATTERIE = {"secteur": False, "batterie_pourcent": 22, "mode": None}


def executer(unites, calcul, dossier, graine=P.graine_unite, alimentation=lambda: SECTEUR):
    """Exécution avec une alimentation simulée (les tests ne dépendent pas de l'état réel du PC)."""
    return P.executer(unites, calcul, dossier, graine, alimentation)


def petit_calcul(identifiant: str, graine: int) -> list[float]:
    """Petit réseau entraîné 20 pas sur des données aléatoires tirées avec la graine de l'unité."""
    import torch
    torch.use_deterministic_algorithms(True)
    g = torch.Generator().manual_seed(graine)
    x, y = torch.randn(64, 5, generator=g), torch.randn(64, generator=g)
    torch.manual_seed(graine)
    modele = torch.nn.Sequential(torch.nn.Linear(5, 8), torch.nn.Tanh(), torch.nn.Linear(8, 1))
    opt = torch.optim.Adam(modele.parameters(), lr=1e-2)
    for _ in range(20):
        opt.zero_grad()
        torch.nn.functional.mse_loss(modele(x).squeeze(-1), y).backward()
        opt.step()
    return [float(v) for v in torch.cat([p.detach().flatten() for p in modele.parameters()])]


class Coupure(Exception):
    """Interruption volontaire (comme une coupure de courant)."""


def calcul_interrompu_apres(k: int):
    compte = {"n": 0}

    def calcul(identifiant, graine):
        if compte["n"] == k:
            raise Coupure()
        compte["n"] += 1
        return petit_calcul(identifiant, graine)
    return calcul


def contenus(dossier: Path) -> dict[str, bytes]:
    return {f.name: f.read_bytes() for f in sorted(dossier.glob("*.json"))}


def _interrompu_puis_relance(dossier: Path, graine=P.graine_unite) -> dict:
    with pytest.raises(Coupure):
        executer(UNITES, calcul_interrompu_apres(3), dossier, graine)
    assert len(contenus(dossier)) == 3
    return executer(UNITES, petit_calcul, dossier, graine)


def test_calcul_interrompu_puis_relance_identique(tmp_path):
    sans = executer(UNITES, petit_calcul, tmp_path / "sans")
    avec = _interrompu_puis_relance(tmp_path / "avec")
    assert sans == {"calculees": 8, "sautees": 0}
    assert avec == {"calculees": 5, "sautees": 3}, "Les unités terminées doivent être sautées."
    assert contenus(tmp_path / "sans") == contenus(tmp_path / "avec")


def test_ordre_d_execution_sans_effet(tmp_path):
    executer(UNITES, petit_calcul, tmp_path / "a")
    executer(list(reversed(UNITES)), petit_calcul, tmp_path / "b")
    assert contenus(tmp_path / "a") == contenus(tmp_path / "b")


def test_temoin_graine_tiree_de_l_ordre_d_execution_detectee(tmp_path):
    """Une graine tirée de l'ordre d'exécution (compteur) donne des fichiers différents après une coupure."""
    def graine_par_ordre():
        compte = {"n": 0}

        def graine(_identifiant):
            compte["n"] += 1
            return compte["n"]
        return graine

    executer(UNITES, petit_calcul, tmp_path / "sans", graine_par_ordre())
    with pytest.raises(Coupure):
        executer(UNITES, calcul_interrompu_apres(3), tmp_path / "avec", graine_par_ordre())
    executer(UNITES, petit_calcul, tmp_path / "avec", graine_par_ordre())
    assert contenus(tmp_path / "sans") != contenus(tmp_path / "avec")


def test_unite_abimee_ou_fichier_temporaire_recalcules(tmp_path):
    executer(UNITES, petit_calcul, tmp_path / "ref")
    dossier = tmp_path / "abime"
    executer(UNITES, petit_calcul, dossier)
    premier = dossier / P.nom_fichier(UNITES[0])
    premier.write_bytes(premier.read_bytes()[:-40])                   # fichier tronqué
    (dossier / (P.nom_fichier(UNITES[1]) + ".part")).write_text("{")   # reste d'une écriture coupée
    assert executer(UNITES, petit_calcul, dossier) == {"calculees": 1, "sautees": 7}
    assert contenus(tmp_path / "ref") == contenus(dossier)


def test_temoin_refus_de_demarrer_sur_batterie(tmp_path):
    with pytest.raises(C.ErreurAlimentation, match=r"sur batterie \(batterie à 22 %\)"):
        executer(UNITES, petit_calcul, tmp_path / "b", alimentation=lambda: BATTERIE)
    assert contenus(tmp_path / "b") == {}


def test_passage_sur_batterie_arret_propre_puis_reprise_identique(tmp_path):
    """Secteur pour le démarrage et les 3 premières unités, puis batterie : arrêt propre après la 3e unité."""
    etats = iter([SECTEUR] * 4 + [BATTERIE] * 100)
    with pytest.raises(C.ErreurAlimentation, match="arrêt propre après 3 unité"):
        executer(UNITES, petit_calcul, tmp_path / "avec", alimentation=lambda: next(etats))
    assert len(contenus(tmp_path / "avec")) == 3
    assert not list((tmp_path / "avec").glob("*.part")), "Aucune unité à moitié écrite."
    assert executer(UNITES, petit_calcul, tmp_path / "avec") == {"calculees": 5, "sautees": 3}
    executer(UNITES, petit_calcul, tmp_path / "sans")
    assert contenus(tmp_path / "sans") == contenus(tmp_path / "avec")


def test_secteur_ou_etat_inconnu_acceptes():
    assert C.verifier_secteur(SECTEUR) == SECTEUR
    inconnu = {"secteur": None, "batterie_pourcent": None, "mode": None}
    assert C.verifier_secteur(inconnu) == inconnu


def test_etat_alimentation_lu():
    etat = C.etat_alimentation()
    assert set(etat) == {"secteur", "batterie_pourcent", "mode"}


def test_graine_derivee_de_l_identifiant():
    assert P.graine_unite("BTCUSDT|LSTM|pli 1|combinaison 0|graine 0") == P.graine_unite("BTCUSDT|LSTM|pli 1|combinaison 0|graine 0")
    assert P.graine_unite("a") != P.graine_unite("b")
    assert 0 <= P.graine_unite("x") < 2**31


@pytest.mark.skipif(sys.platform != "win32", reason="mise en veille de Windows")
def test_mise_en_veille_retablie_meme_en_cas_d_erreur(monkeypatch):
    import ctypes
    appels = []
    monkeypatch.setattr(ctypes.windll.kernel32, "SetThreadExecutionState", lambda drapeaux: appels.append(drapeaux) or 1)
    with pytest.raises(Coupure):
        with P.sans_mise_en_veille():
            raise Coupure()
    assert appels == [P.ES_CONTINUOUS | P.ES_SYSTEM_REQUIRED, P.ES_CONTINUOUS]


# --- Seuil de mémoire libre -------------------------------------------------------------

def test_memoire_libre_mesuree():
    assert 0 < C.memoire_libre_go() < 1024


def test_temoin_script_lourd_refuse_sous_le_seuil():
    regles = R.charger_regles()
    regles["projet"]["seuil_memoire_libre_go"] = 2.0
    with pytest.raises(C.ErreurMemoire, match="Démarrage refusé : 1,50 Go de mémoire libre"):
        C.verifier_memoire_libre(regles, libre_go=1.5)
    assert C.verifier_memoire_libre(regles, libre_go=2.5) == 2.5


def test_seuil_pas_encore_fixe_refuse():
    regles = R.charger_regles()
    regles["projet"]["seuil_memoire_libre_go"] = R.A_FIXER
    with pytest.raises(C.ErreurMemoire, match="pas encore fixé"):
        C.verifier_memoire_libre(regles, libre_go=100.0)


# --- Aucune vraie donnée lue pendant les mesures -------------------------------------------

def _python(code: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8", cwd=str(RACINE))


PREAMBULE = "import sys; sys.path.insert(0, 'src'); import mesures; mesures.interdire_donnees()\n"


@pytest.mark.parametrize("lecture", [
    "open('data/manifeste_traite.json').read()",
    "import pandas; pandas.read_parquet('data/processed/variables.parquet')",
    "import pyarrow.parquet as pq; pq.read_table('data/processed/variables.parquet')",
    "import os; os.listdir('data')",
])
def test_lecture_des_donnees_refusee_pendant_les_mesures(lecture):
    sortie = _python(PREAMBULE + lecture)
    assert sortie.returncode != 0 and "PermissionError" in sortie.stderr, sortie.stderr[-500:]


def test_lecture_hors_de_data_permise_pendant_les_mesures():
    sortie = _python(PREAMBULE + "print(len(open('config/regles.toml', encoding='utf-8').read()) > 0)")
    assert sortie.returncode == 0 and sortie.stdout.strip() == "True", sortie.stderr[-500:]


def test_temoin_sans_interdiction_la_lecture_reussit():
    """Sans le crochet, la même lecture réussit : le refus vient bien du crochet."""
    sortie = _python("print(len(open('data/manifeste_traite.json', encoding='utf-8').read()) > 0)")
    assert sortie.returncode == 0 and sortie.stdout.strip() == "True", sortie.stderr[-500:]
