"""Synthèse PDF : reproductible octet pour octet, à jour, 3 à 5 pages, date fixée, aucun chemin du poste."""

import base64
import io
import json
import re
import sys
import zlib
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

pytest.importorskip("reportlab")

import synthese as S  # noqa: E402


@pytest.fixture(scope="module")
def deux_generations(tmp_path_factory):
    d = tmp_path_factory.mktemp("synthese")
    return S.generer(d / "a.pdf").read_bytes(), S.generer(d / "b.pdf").read_bytes()


def test_meme_script_meme_pdf(deux_generations):
    a, b = deux_generations
    assert a == b


def test_pdf_commite_a_jour(deux_generations):
    assert (RACINE / "docs" / "synthese.pdf").read_bytes() == deux_generations[0], \
        "docs/synthese.pdf n'est pas à jour : relancer src/synthese.py"


def test_trois_a_cinq_pages(deux_generations):
    pages = len(re.findall(rb"/Type /Page[^s]", deux_generations[0]))
    assert 3 <= pages <= 5


def test_date_fixee_a_l_ouverture_du_test(deux_generations):
    ouvert = json.loads((RACINE / "rapports" / "test_final.json").read_text(encoding="utf-8"))["ouvert_le"][:10].replace("-", "")
    dates = re.findall(rb"/(?:CreationDate|ModDate) \(D:(\d{8})", deux_generations[0])
    assert dates and all(x.decode() == ouvert for x in dates)


# Motifs composés par morceaux, pour que ce fichier ne contienne pas lui-même les mots recherchés.
_DOSSIER, _DONNEES, _NUMERO = "Us" + "ers", "App" + "Data", str(21000 + 655)
MOTIFS_CHEMIN = [m.encode() for m in (rf"(?i)C:[\\/]+{_DOSSIER}", rf"(?i){_DONNEES}", rf"(?<![0-9]){_NUMERO}(?![0-9])")]


def textes_du_pdf(octets: bytes) -> list[bytes]:
    """Le fichier brut et chaque flux décodé (ASCII85 puis Flate), sauf les images (pixels : des octets au hasard).
    L'en-tête d'un flux est cherché dans SON objet seulement (jamais au-delà d'un « endobj »)."""
    textes = [octets]
    for m in re.finditer(rb"\d+ 0 obj\s*<<((?:(?!endobj).)*?)>>\s*stream\r?\n(.*?)endstream", octets, re.S):
        entete, flux = m.groups()
        if re.search(rb"/Subtype\s*/Image", entete):
            continue
        if b"/ASCII85Decode" in entete:
            flux = base64.a85decode(flux.strip().removesuffix(b"~>"))
        textes.append(zlib.decompress(flux) if b"/FlateDecode" in entete else flux)
    return textes


def chemins_trouves(octets: bytes) -> list[bytes]:
    return [m for t in textes_du_pdf(octets) for m in MOTIFS_CHEMIN if re.search(m, t)]


def test_aucun_chemin_du_poste(deux_generations):
    """Fichier brut et flux décodés : métadonnées et texte en police standard (Courier). Le texte en police TrueType (Vera)
    est écrit en numéros de glyphes : il est vérifié avant la mise en page (test suivant)."""
    assert len(textes_du_pdf(deux_generations[0])) > 5          # les pages et les métadonnées sont bien lues
    assert chemins_trouves(deux_generations[0]) == []


def textes_des_paragraphes(monkeypatch) -> list[str]:
    """Texte de chaque paragraphe donné à reportlab (cellules des tableaux comprises), relevé pendant contenu()."""
    import reportlab.platypus as P
    releves = []

    class ParagrapheReleve(P.Paragraph):
        def __init__(self, text, *args, **kwargs):
            releves.append(text)
            super().__init__(text, *args, **kwargs)

    monkeypatch.setattr(P, "Paragraph", ParagrapheReleve)
    S.enregistrer_polices()
    S.contenu(*S.entrees())
    return releves


def test_aucun_chemin_dans_le_texte_du_document(monkeypatch):
    textes = textes_des_paragraphes(monkeypatch)
    assert len(textes) > 50 and any("QLIKE" in x for x in textes)
    assert [x for x in textes if chemins_trouves(x.encode())] == []


def test_temoin_chemin_dans_un_paragraphe(monkeypatch):
    plante = "C" + ":\\" + _DOSSIER + "\\x"
    monkeypatch.setattr(S.RES, "phrases_trouvailles", lambda v, langue="fr": [plante, plante, plante])
    assert any(chemins_trouves(x.encode()) for x in textes_des_paragraphes(monkeypatch))


@pytest.mark.parametrize("ascii85", [0, 1])
def test_temoin_chemin_dans_le_texte_compresse(ascii85, monkeypatch):
    """Un PDF dont le TEXTE (compressé) contient un chemin du poste est bien détecté, avec ou sans codage ASCII85.
    Le témoin a aussi une image : son flux est ignoré sans masquer le texte de la page."""
    from reportlab import rl_config
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    monkeypatch.setattr(rl_config, "useA85", ascii85)
    tampon = io.BytesIO()
    c = canvas.Canvas(tampon, invariant=1, pageCompression=1)
    c.drawImage(ImageReader(str(RACINE / "figures" / "figure_1_rv_annualisee.png")), 72, 300, width=200, height=130)
    c.drawString(72, 720, "C" + ":\\" + _DOSSIER + "\\" + _NUMERO + "\\" + _DONNEES)
    c.save()
    octets = tampon.getvalue()
    assert _DONNEES.encode() not in octets                     # invisible sans décodage
    assert len(chemins_trouves(octets)) == 3
