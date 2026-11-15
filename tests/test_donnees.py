"""Tests du téléchargement, de la conversion et des contrôles de qualité (sans réseau)."""

import datetime as dt
import hashlib
import io
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

import convertir as CV  # noqa: E402
import qualite as Q  # noqa: E402
import regles as R  # noqa: E402
import telecharger as T  # noqa: E402

REGLES = R.charger_regles()
D = dt.date.fromisoformat


# --- Fabrication de fichiers témoins ----------------------------------------------

def _csv_klines(debut_ms: int, n: int, facteur: int = 1, en_tete: bool = False) -> str:
    """n bougies de 5 minutes à partir de debut_ms ; facteur 1000 pour des microsecondes."""
    lignes = ["open_time,open,high,low,close,volume,close_time,quote_volume,count,"
              "taker_buy_volume,taker_buy_quote_volume,ignore"] if en_tete else []
    for i in range(n):
        ouverture = (debut_ms + i * 300_000) * facteur
        cloture = (debut_ms + (i + 1) * 300_000) * facteur - facteur
        lignes.append(f"{ouverture},10.0,11.0,9.0,10.5,1.0,{cloture},10.0,5,0.5,5.0,0")
    return "\n".join(lignes) + "\n"


def _zip(chemin: Path, nom_csv: str, texte: str) -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(nom_csv, texte)
    chemin.write_bytes(tampon.getvalue())
    return tampon.getvalue()


MS_2018 = 1514764800000  # 2018-01-01 00:00 UTC en millisecondes (13 chiffres)


# --- Unité des horodatages ---------------------------------------------------------

def test_unite_millisecondes():
    assert CV.detecter_unite(np.array([MS_2018, MS_2018 + 300_000])) == "ms"


def test_unite_microsecondes():
    assert CV.detecter_unite(np.array([MS_2018 * 1000, MS_2018 * 1000 + 300_000_000])) == "us"


@pytest.mark.parametrize("valeurs", [
    [MS_2018 // 1000],                      # secondes (10 chiffres)
    [MS_2018, MS_2018 * 1000],              # mélange ms et us dans un même fichier
    [MS_2018 * 10],                         # 14 chiffres
])
def test_temoin_unite_ambigue_refusee(valeurs):
    with pytest.raises(CV.ErreurConversion, match="ambiguë"):
        CV.detecter_unite(np.array(valeurs, dtype="int64"))


def test_zip_ms_et_us_donnent_les_memes_dates(tmp_path):
    a, _ = CV.lire_zip(_chemin_zip(tmp_path, "a.zip", _csv_klines(MS_2018, 3)))
    b, info_b = CV.lire_zip(_chemin_zip(tmp_path, "b.zip", _csv_klines(MS_2018, 3, facteur=1000)))
    assert info_b["unite"] == "us"
    assert a["date_ouverture"].equals(b["date_ouverture"])
    assert str(a["date_ouverture"].iloc[0]) == "2018-01-01 00:00:00+00:00"


def test_en_tete_detecte(tmp_path):
    sans, info_sans = CV.lire_zip(_chemin_zip(tmp_path, "s.zip", _csv_klines(MS_2018, 4)))
    avec, info_avec = CV.lire_zip(_chemin_zip(tmp_path, "a.zip", _csv_klines(MS_2018, 4, en_tete=True)))
    assert (info_sans["en_tete"], info_avec["en_tete"]) == (False, True)
    pd.testing.assert_frame_equal(sans, avec)
    assert list(avec.columns) == CV.COLONNES_SORTIE


def test_nombres_lus_exactement_comme_float(tmp_path):
    # Volume réel de Binance (BTCUSDT, 2021-01-02 12:20 UTC) : sans lecture exacte, pandas 3.0
    # le lit à un ulp près. float() de Python arrondit toujours correctement.
    texte_volume = "92242008.04830823"
    csv = _csv_klines(MS_2018, 1).replace(",10.0,5,", f",{texte_volume},5,")
    df, _ = CV.lire_zip(_chemin_zip(tmp_path, "v.zip", csv))
    assert df["volume_cotation"].iloc[0] == float(texte_volume)


def _chemin_zip(dossier: Path, nom: str, texte: str) -> Path:
    chemin = dossier / nom
    _zip(chemin, nom.replace(".zip", ".csv"), texte)
    return chemin


def test_empreinte_de_contenu_independante_du_decoupage(tmp_path):
    df, _ = CV.lire_zip(_chemin_zip(tmp_path, "x.zip", _csv_klines(MS_2018, 50)))
    table = pa.Table.from_pandas(df, schema=CV.SCHEMA, preserve_index=False)
    pq.write_table(table, tmp_path / "un.parquet", row_group_size=50)
    pq.write_table(table, tmp_path / "deux.parquet", row_group_size=7, compression="zstd")
    assert (tmp_path / "un.parquet").read_bytes() != (tmp_path / "deux.parquet").read_bytes()
    assert CV.empreinte_contenu(tmp_path / "un.parquet") == CV.empreinte_contenu(tmp_path / "deux.parquet")


def test_temoin_empreinte_de_contenu_change_si_une_valeur_change(tmp_path):
    df, _ = CV.lire_zip(_chemin_zip(tmp_path, "x.zip", _csv_klines(MS_2018, 10)))
    pq.write_table(pa.Table.from_pandas(df, schema=CV.SCHEMA, preserve_index=False), tmp_path / "a.parquet")
    df.loc[3, "cloture"] = 10.500001
    pq.write_table(pa.Table.from_pandas(df, schema=CV.SCHEMA, preserve_index=False), tmp_path / "b.parquet")
    assert CV.empreinte_contenu(tmp_path / "a.parquet") != CV.empreinte_contenu(tmp_path / "b.parquet")


# --- Téléchargement : empreinte, rejets, relance --------------------------------------

class FauxServeur:
    """Remplace le réseau : sert des fichiers en mémoire et compte les requêtes."""

    def __init__(self, fichiers: dict[str, bytes], checksums_faux: set[str] = frozenset()):
        self.fichiers, self.faux, self.requetes = fichiers, checksums_faux, []

    def __call__(self, url: str) -> bytes:
        self.requetes.append(url)
        nom = url.rsplit("/", 1)[1]
        if nom.endswith(".CHECKSUM"):
            nom_zip = nom[: -len(".CHECKSUM")]
            empreinte = "0" * 64 if nom_zip in self.faux else hashlib.sha256(self.fichiers[nom_zip]).hexdigest()
            return f"{empreinte}  {nom_zip}\n".encode("ascii")
        return self.fichiers[nom]


def _contenus(tmp_path, noms):
    contenus = {}
    for i, nom in enumerate(noms):
        contenus[nom] = _zip(tmp_path / f"source_{i}.zip", nom.replace(".zip", ".csv"), _csv_klines(MS_2018 + i, 5))
    return contenus


def test_temoin_empreinte_fausse_refusee_et_deplacee(tmp_path):
    noms = ["BTCUSDT-5m-2018-01.zip", "BTCUSDT-5m-2018-02.zip"]
    serveur = FauxServeur(_contenus(tmp_path, noms), checksums_faux={noms[1]})
    dossier = tmp_path / "raw"
    bilan = T.executer(REGLES, dossier, tmp_path / "manifeste.json", serveur,
                       prevus=[(n, f"https://exemple.invalid/{n}") for n in noms], pause_s=0)
    assert (bilan["telecharge"], bilan["rejete"]) == (1, 1)
    assert (dossier / noms[0]).exists()
    assert not (dossier / noms[1]).exists(), "Un fichier refusé ne doit pas être à sa place finale."
    assert (dossier / "_rejets" / noms[1]).exists(), "Un fichier refusé est déplacé, pas supprimé."
    assert not list(dossier.glob("*.part")), "Aucun fichier temporaire ne doit rester."


def test_relance_ne_telecharge_rien_et_manifeste_identique(tmp_path):
    noms = ["ETHUSDT-5m-2018-01.zip", "ETHUSDT-5m-2018-02.zip", "ETHUSDT-5m-2018-03.zip"]
    serveur = FauxServeur(_contenus(tmp_path, noms))
    dossier, manifeste = tmp_path / "raw", tmp_path / "manifeste.json"
    prevus = [(n, f"https://exemple.invalid/{n}") for n in noms]
    premier = T.executer(REGLES, dossier, manifeste, serveur, prevus=prevus, pause_s=0)
    octets_1 = manifeste.read_bytes()
    assert premier["telecharge"] == 3 and len(serveur.requetes) == 6
    serveur.requetes.clear()
    second = T.executer(REGLES, dossier, manifeste, serveur, prevus=prevus, pause_s=0)
    assert serveur.requetes == [], "La relance ne doit faire aucune requête réseau."
    assert second["deja_present"] == 3 and second["telecharge"] == 0
    assert manifeste.read_bytes() == octets_1
    texte = octets_1.decode("utf-8")
    assert str(tmp_path) not in texte and "\\" not in texte, "Aucun chemin absolu dans le manifeste."


def test_fichier_local_abime_mis_de_cote_puis_retelecharge(tmp_path):
    noms = ["BTCUSDT-5m-2018-01.zip"]
    contenus = _contenus(tmp_path, noms)
    dossier, prevus = tmp_path / "raw", [(noms[0], f"https://exemple.invalid/{noms[0]}")]
    T.executer(REGLES, dossier, tmp_path / "m.json", FauxServeur(contenus), prevus=prevus, pause_s=0)
    (dossier / noms[0]).write_bytes(b"abime")
    bilan = T.executer(REGLES, dossier, tmp_path / "m.json", FauxServeur(contenus), prevus=prevus, pause_s=0)
    assert bilan["telecharge"] == 1
    assert (dossier / "_rejets" / noms[0]).read_bytes() == b"abime"
    assert (dossier / noms[0]).read_bytes() == contenus[noms[0]]


def test_adresses_lues_dans_les_regles():
    prevus = T.fichiers_prevus(REGLES)
    assert len(prevus) == 212
    assert prevus[0] == ("BTCUSDT-5m-2018-01.zip",
                         "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2018-01.zip")
    assert prevus[-1][0] == "ETHUSDT-5m-2026-10.zip"


# --- Jours valides : trous de plus de 60 minutes et règle des 274 -----------------------

def _minutes(jour: dt.date, retirer: set[int] = frozenset()) -> list[int]:
    base = Q.date_vers_jour(jour) * Q.MINUTES_PAR_JOUR
    return [base + 5 * k for k in range(288) if k not in retirer]


def _bilan(*jours_minutes):
    m = np.array(sorted(x for liste in jours_minutes for x in liste), dtype="int64")
    debut = Q.jour_vers_date(int(m.min() // Q.MINUTES_PAR_JOUR))
    fin = Q.jour_vers_date(int(m.max() // Q.MINUTES_PAR_JOUR))
    return Q.bilan_jours(m, debut, fin, REGLES).set_index("jour")


def test_premier_jour_287_rendements_valide():
    b = _bilan(_minutes(D("2018-01-01")), _minutes(D("2018-01-02")))
    assert b.loc[D("2018-01-01"), "rendements"] == 287 and b.loc[D("2018-01-01"), "valide"]
    assert b.loc[D("2018-01-02"), "rendements"] == 288


def test_trou_de_65_minutes_rend_le_jour_non_valide():
    # 12 bougies consécutives manquantes : écart de 65 min, mais encore 276 bougies
    b = _bilan(_minutes(D("2018-01-01")), _minutes(D("2018-01-02"), retirer=set(range(100, 112))))
    jour = b.loc[D("2018-01-02")]
    assert jour["bougies"] == 276 and jour["ecart_max_min"] == 65 and not jour["valide"]


def test_temoin_trou_de_60_minutes_reste_valide():
    b = _bilan(_minutes(D("2018-01-01")), _minutes(D("2018-01-02"), retirer=set(range(100, 111))))
    assert b.loc[D("2018-01-02"), "ecart_max_min"] == 60 and b.loc[D("2018-01-02"), "valide"]


@pytest.mark.parametrize("manquantes, valide", [(14, True), (15, False)])
def test_regle_des_274(manquantes, valide):
    retirees = set(range(10, 10 + 2 * manquantes, 2))  # bougies isolées : écarts de 10 minutes
    b = _bilan(_minutes(D("2018-01-01")), _minutes(D("2018-01-02"), retirer=retirees))
    assert b.loc[D("2018-01-02"), "rendements"] == 288 - manquantes
    assert bool(b.loc[D("2018-01-02"), "valide"]) is valide


def test_trou_a_cheval_sur_minuit_compte_pour_les_deux_jours():
    # dernières bougies du 2 janvier et premières du 3 manquantes : écart de 2 h à cheval sur minuit
    b = _bilan(_minutes(D("2018-01-01")), _minutes(D("2018-01-02"), retirer=set(range(276, 288))),
               _minutes(D("2018-01-03"), retirer=set(range(0, 12))))
    assert not b.loc[D("2018-01-02"), "valide"] and not b.loc[D("2018-01-03"), "valide"]
    assert b.loc[D("2018-01-01"), "valide"]


def test_jour_sans_bougie_non_valide():
    b = _bilan(_minutes(D("2018-01-01")), _minutes(D("2018-01-03")))
    assert b.loc[D("2018-01-02"), "bougies"] == 0 and not b.loc[D("2018-01-02"), "valide"]


def test_alignement_sur_la_grille_de_5_minutes():
    dates = pd.Series(pd.to_datetime(["2018-02-09 09:55:00", "2018-02-09 09:58:14.789", "2018-02-09 10:00:00"],
                                     utc=True, format="ISO8601"))
    minutes, aligne = Q.minutes_et_alignement(dates)
    assert aligne.tolist() == [True, False, True], "Témoin : la bougie décalée de 3 min 14 s est repérée."
    assert (minutes[1] - minutes[0]) == 3


def test_taux_exclusion_fenetre_de_30_jours():
    jours = pd.DataFrame({"jour": pd.date_range("2018-01-01", "2024-12-31", freq="D").date})
    jours["valide"] = True
    jours.loc[jours["jour"] == D("2020-06-15"), "valide"] = False
    s = Q.taux_exclusion(jours, REGLES)
    assert s["exclus_par_fenetre"] == 30, "Un jour non valide exclut les 30 cibles qui le suivent."
    assert s["exclus_par_cible_invalide"] == 1 and s["exclus_au_total"] == 31
    assert s["exemples"] == (D("2024-12-31") - D("2018-04-01")).days + 1
