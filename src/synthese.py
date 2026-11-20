"""Synthèse PDF du projet (docs/synthese.pdf), générée depuis les JSON de rapports/, les règles et les figures.

Aucun chiffre tapé à la main : chaque nombre est lu dans un fichier de résultats ou dans config/regles.toml.
Résumé et limites : les MÊMES fonctions que l'application (src/resume.py).

Reproductible : même script et mêmes fichiers d'entrée = même PDF, octet pour octet.
- mode « invariant » de reportlab : identifiant de fichier fixe, aucun commentaire variable ;
- date du document fixée (SOURCE_DATE_EPOCH) à la date d'ouverture du test final, lue dans rapports/test_final.json ;
- police Vera, fournie avec reportlab (aucune police du système, aucun fichier de police dans le dépôt).

Lancement : .venv\\Scripts\\python src\\synthese.py
"""

from __future__ import annotations

import calendar
import datetime as dt
import html
import json
import os
import re
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import commun as C  # noqa: E402
import regles as R  # noqa: E402
import resume as RES  # noqa: E402

CHEMIN_PDF = C.RACINE / "docs" / "synthese.pdf"
DEPOT = "https://github.com/aljene307/volatility-forecasting-dl"
API = "https://volatilite-api.onrender.com"
ORDRE = ["Persistance", "HAR-RV", "HAR-J", "GARCH(1,1)", "XGBoost", "LSTM", "GRU", "CNN-LSTM", "Transformer", "TFT"]
ACHAT = "Achat simple"
ENONCES = {"H1": "QLIKE du modèle retenu < QLIKE de HAR-RV (principale)", "H2": "QLIKE de HAR-RV < QLIKE de la persistance",
           "H3": "QLIKE de GARCH(1,1) > QLIKE de HAR-RV", "H4": "VaR de HAR-RV non rejetée par le test de Kupiec",
           "H5": "stratégie du modèle retenu : volatilité et drawdown plus faibles que l'achat simple",
           "H6": "gain sur HAR-J < gain sur HAR-RV (descriptive)", "H7": "QLIKE du modèle retenu < QLIKE de HAR-J (secondaire)"}


def lire(nom: str) -> dict:
    return json.loads((C.DOSSIER_RAPPORTS / nom).read_text(encoding="utf-8"))


def texte(s: str) -> str:
    """Texte pour un paragraphe reportlab : caractères spéciaux échappés, **gras** converti, espace fine remplacée
    (la police Vera n'a pas le caractère U+202F ; l'espace insécable ordinaire garde le nombre sur une ligne)."""
    s = html.escape(s.replace(" ", " "), quote=False)
    s = re.sub(r"`([^`]+)`", r"<font face='Courier'>\1</font>", s)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)


def date_fr(iso: str) -> str:
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    d = dt.date.fromisoformat(iso[:10])
    return f"{'1er' if d.day == 1 else d.day} {mois[d.month - 1]} {d.year}"


def contenu(t: dict, attentes: dict, dev: dict, ex: dict, regles: dict, qualite: dict, exploration: dict) -> list:
    """Liste des éléments du document (titres, paragraphes, tableaux, figures)."""
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Image, KeepTogether, ListFlowable, ListItem, PageBreak, Paragraph, Spacer, Table, TableStyle

    n, pc, pv = RES.nombre, RES.pourcent, RES.p_valeur
    corps = ParagraphStyle("corps", fontName="Vera", fontSize=9.5, leading=13.2, spaceAfter=5, alignment=4)
    petit = ParagraphStyle("petit", parent=corps, fontSize=8, leading=10.5, alignment=0, spaceAfter=2)
    cellule = ParagraphStyle("cellule", parent=petit, fontSize=7.8, leading=9.6, spaceAfter=0)
    legende = ParagraphStyle("legende", parent=petit, fontName="VeraIt", textColor=colors.HexColor("#444444"), alignment=1, spaceAfter=8)
    titre = ParagraphStyle("titre", fontName="VeraBd", fontSize=17, leading=21, spaceAfter=4)
    sous_titre = ParagraphStyle("sous_titre", fontName="Vera", fontSize=9.5, leading=12, textColor=colors.HexColor("#444444"), spaceAfter=10)
    h1 = ParagraphStyle("h1", fontName="VeraBd", fontSize=12, leading=15, spaceBefore=8, spaceAfter=4, textColor=colors.HexColor("#1F3A5F"))
    puce = ParagraphStyle("puce", parent=corps, alignment=0, spaceAfter=3)
    encadre = ParagraphStyle("encadre", parent=corps, backColor=colors.HexColor("#EEF3F8"), borderPadding=(6, 6, 6, 6), spaceBefore=4,
                             spaceAfter=10, alignment=0)
    largeur = 17 * cm

    def p(s: str, style=corps):
        return Paragraph(texte(s), style)

    def puces(items: list[str]):
        return ListFlowable([ListItem(p(x, puce), leftIndent=10, value="•") for x in items], bulletType="bullet", start="•", leftIndent=10,
                            bulletFontName="Vera", bulletFontSize=8)

    def figure(nom: str, texte_legende: str, part: float = 1.0):
        chemin = C.RACINE / "figures" / nom
        w, h = ImageReader(str(chemin)).getSize()
        lw = largeur * part
        return KeepTogether([Image(str(chemin), width=lw, height=lw * h / w), p(texte_legende, legende)])

    def tableau(lignes: list[list[str]], largeurs: list[float], gras: set[int] = frozenset()):
        cellules = [[Paragraph(texte(c), cellule) for c in ligne] for ligne in lignes]
        tab = Table(cellules, colWidths=[x * cm for x in largeurs], repeatRows=1)
        style = [("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#B8C2CC")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE5EE")),
                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
        style += [("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F1ECFB")) for i in gras]
        tab.setStyle(TableStyle(style))
        return tab

    actifs = list(t["actifs"])
    nom = {a: RES.NOMS[a] for a in actifs}
    retenu = {a: t["actifs"][a]["modele_retenu"] for a in actifs}
    h = t["hypotheses"]
    per_dev, per_test = qualite["periodes"]["developpement"], t["periode"]
    plis = dev["plis"]
    boot = regles["evaluation"]["bootstrap"]
    graines = regles["modeles"]["graines_deep_learning"]
    fenetres = regles["modeles"]["har_rv"]["fenetres_jours"]
    st = regles["strategie"]
    cible = lire("volatilite_cible.json")["actifs"]
    v = RES.valeurs_trouvailles(t)
    e = []

    # --- Page 1 : résumé, question, données, méthode ---------------------------------------------------------------
    e += [p("Prévoir la volatilité de BTC et d'ETH", titre),
          p(f"Synthèse du projet volatility-forecasting-dl — Mohamed Aljene (ENSI, II3-IF) — projet éducatif, non commercial. "
            f"Document généré par `src/synthese.py` depuis les fichiers de résultats du dépôt.", sous_titre),
          Paragraph("<b>Ce qu'on a trouvé.</b> " + " ".join(texte(x) for x in RES.phrases_trouvailles(v, "fr")), encadre),
          p("1. La question", h1),
          p("La volatilité mesure l'ampleur des variations d'un prix : c'est la « météo » du risque. On cherche à prévoir, chaque soir, la "
            "volatilité réalisée du lendemain (RV de J+1) de deux cryptomonnaies, à partir de ce qu'on sait à la clôture de J. On compare des "
            "modèles économétriques classiques à des réseaux de neurones, avec des règles écrites et publiées avant chaque calcul."),
          p("2. Les données", h1),
          p(f"Bougies de {regles['cible']['intervalle_rendements'].replace('m', ' minutes')} de BTCUSDT et ETHUSDT (Binance spot), "
            f"téléchargées sur Binance Vision. Jour défini en UTC ; marché ouvert {regles['cible']['annualisation_jours']} jours par an. "
            f"Développement (apprentissage et validation) : du {date_fr(per_dev[0])} au {date_fr(per_dev[1])}, "
            f"{n(exploration['actifs'][actifs[0]]['jours'], 0)} jours par actif. Test final : du {date_fr(per_test[0])} au "
            f"{date_fr(per_test[1])}, {n(t['actifs'][actifs[0]]['jours'], 0)} jours par actif, ouvert une seule fois le "
            f"{date_fr(t['ouvert_le'])}. Les données sont sous licence CC BY-NC-SA 4.0 : elles ne sont pas dans le dépôt, qui contient "
            "seulement leurs empreintes SHA-256 pour vérifier un téléchargement."),
          p("3. La méthode", h1),
          puces([f"**Cible** : RV = racine de la somme des carrés des log-rendements de 5 minutes du jour ; les modèles prévoient log(RV), "
                 "puis la variance prévue est corrigée par exp(2y + 2s²), avec s² mesuré sur une validation interne.",
                 f"**Découpage** : chronologique strict, walk-forward en {len(plis)} plis d'un an (du {date_fr(plis[0][0])} au "
                 f"{date_fr(plis[-1][1])}) ; chaque transformation est apprise sur l'apprentissage du pli seulement.",
                 f"**Modèles** : persistance, HAR-RV (fenêtres de {', '.join(map(str, fenetres[:-1]))} et {fenetres[-1]} jours), HAR-J "
                 "(HAR-RV + jour de la semaine), GARCH(1,1), XGBoost et cinq réseaux : LSTM, GRU, CNN-LSTM, Transformer, TFT. "
                 f"Chaque réseau est entraîné avec {len(graines)} graines ; sa prévision est la moyenne des log des graines.",
                 "**Choix du modèle** : " + regles["evaluation"]["selection"]["critere"] + ", sur le développement seulement.",
                 f"**Évaluation** : QLIKE (perte de référence pour la variance), test de Diebold-Mariano avec erreurs HAC et ajustement de "
                 f"Holm, intervalles par bootstrap par blocs mobiles ({boot['taille_bloc_jours']} jours, {n(boot['tirages'], 0)} tirages, "
                 f"graine {boot['graine']})."]),
          PageBreak()]

    # --- Page 2 : résultats du test final ------------------------------------------------------------------------
    e += [p("4. Résultats du test final", h1),
          p(f"Les attentes chiffrées ont été écrites et publiées avant l'ouverture du test. Les modèles ne sont ni réentraînés ni choisis à "
            f"nouveau : on applique ceux du développement. Modèles retenus : {retenu[actifs[0]]} pour {nom[actifs[0]]}, "
            f"{retenu[actifs[1]]} pour {nom[actifs[1]]}. Un gain positif signifie un QLIKE plus faible (meilleur) que la référence.")]
    lignes = [["Modèle"] + [x for a in actifs for x in (f"QLIKE {nom[a]} [IC 95 %]", f"Gain sur HAR-RV ({nom[a]})")]]
    gras = set()
    for i, m in enumerate(ORDRE, start=1):
        if m in retenu.values():
            gras.add(i)
        cases = [m + "".join(f" (retenu {nom[a]})" for a in actifs if retenu[a] == m)]
        for a in actifs:
            x = t["actifs"][a]["modeles"][m]
            cases += [f"{n(x['qlike'])} [{n(x['qlike_intervalle']['bas'])} ; {n(x['qlike_intervalle']['haut'])}]",
                      pc(t["actifs"][a]["gain_sur_har_rv"][m])]
        lignes.append(cases)
    e += [tableau(lignes, [4.2, 3.7, 2.5, 3.7, 2.5], gras), Spacer(1, 6),
          p("Tableau 1 — QLIKE de chaque modèle sur le test final (plus petit = meilleur) et gain relatif sur HAR-RV.", legende)]
    lignes = [["Hypothèse", "Énoncé"] + [f"{nom[a]} ({retenu[a]})" for a in actifs]]
    for k in ("H1", "H2", "H3", "H4", "H5", "H6", "H7"):
        cases = [k, ENONCES[k]]
        for a in actifs:
            x = h[k][a]
            verdict = "confirmée" if x["confirmee"] else "non confirmée"
            if "p_valeur_holm_2_actifs" in x:
                verdict += f" (p ajustée {pv(x['p_valeur_holm_2_actifs'])})"
            cases.append(verdict)
        lignes.append(cases)
    pr, pj = attentes["prevision"], attentes["prevision_har_j"]
    e += [tableau(lignes, [2.1, 7.1, 3.9, 3.9]), Spacer(1, 6),
          p("Tableau 2 — Verdicts des hypothèses écrites avant l'ouverture (Holm sur les 2 actifs pour H1 et H7).", legende),
          p("Les gains observés sont tous au-dessus des intervalles écrits avant l'ouverture : " +
            " ; ".join(f"{nom[a]} : {pc(h['prevision'][a]['gain'])} sur HAR-RV (prévu {pc(pr['gain_min'], 0)} à {pc(pr['gain_max'], 0)}) et "
                       f"{pc(h['prevision_har_j'][a]['gain'])} sur HAR-J (prévu {pc(pj['gain_min'], 0)} à {pc(pj['gain_max'], 0)})"
                       for a in actifs) + ". Ils sont publiés tels quels : notre jugement a priori était trop prudent."
            if all(h["prevision"][a]["gain"] > pr["gain_max"] and h["prevision_har_j"][a]["gain"] > pj["gain_max"] for a in actifs) else
            "Comparaison avec les intervalles écrits avant l'ouverture : " +
            " ; ".join(f"{nom[a]} : {pc(h['prevision'][a]['gain'])} sur HAR-RV (prévu {pc(pr['gain_min'], 0)} à {pc(pr['gain_max'], 0)})"
                       for a in actifs) + "."),
          PageBreak()]

    # --- Page 3 : prévisions et HAR-J ----------------------------------------------------------------------------
    e += [figure(f"figure_10_test_previsions_{a}.png", f"Figure {1 + i} — Test final, {nom[a]} : volatilité réalisée et prévisions "
                 f"de HAR-RV et du modèle retenu ({retenu[a]}).", 0.92) for i, a in enumerate(actifs)]
    e += [p("5. Le rôle du jour de la semaine (HAR-J)", h1),
          p(RES.phrases_trouvailles(v, "fr")[1]),
          p("HAR-J est un simple modèle linéaire : HAR-RV avec un indicateur pour chaque jour de la semaine de la cible. Il a été ajouté "
            "avant l'ouverture du test, parce que l'analyse d'explicabilité montrait que les réseaux utilisaient beaucoup cette information. "
            "Le modèle retenu reste meilleur que HAR-J sur le test : " +
            " ; ".join(f"{nom[a]} : gain de {pc(t['actifs'][a]['gain_sur_har_j'][retenu[a]])}, p-valeur ajustée "
                       f"{pv(h['H7'][a]['p_valeur_holm_2_actifs'])}" for a in actifs)
            + f" (seuil {n(attentes['H7']['seuil'], 2)})."),
          PageBreak()]

    # --- Page 4 : stratégie ---------------------------------------------------------------------------------------
    e += [p("6. Une stratégie de pilotage par la volatilité", h1),
          p(f"Chaque soir, on décide la part investie : exposition = volatilité cible / volatilité prévue, bornée entre "
            f"{n(st['exposition_min'], 0)} et {n(st['exposition_max'], 0)} (ni vente à découvert ni emprunt). La décision prise à la "
            f"clôture de J s'applique à partir de J+{st['decalage_execution_jours']}, avec des frais de {pc(st['frais'], 2)} de la valeur "
            "échangée. Volatilité cible (médiane de la RV annualisée sur l'apprentissage) : "
            + " ; ".join(f"{pc(cible[a]['valeur_annualisee'])} pour {nom[a]}" for a in actifs) + ". Aucun réglage n'a été fait sur le test.")]
    lignes = [["Actif", "Stratégie", "Rendement annualisé", "Volatilité", "Sharpe [IC 95 %]", "Drawdown max"]]
    for a in actifs:
        s = t["actifs"][a]["strategie"]
        for m in (ACHAT, "HAR-RV", retenu[a]):
            x = s[m]
            lignes.append([nom[a], m + (" (retenu)" if m == retenu[a] else ""), pc(x["rendement_annualise"]), pc(x["volatilite_annualisee"]),
                           f"{n(x['sharpe'], 2)} [{n(x['sharpe_intervalle']['bas'], 2)} ; {n(x['sharpe_intervalle']['haut'], 2)}]",
                           pc(x["drawdown_max"])])
    e += [tableau(lignes, [1.4, 3.8, 2.9, 2.4, 3.6, 2.9]), Spacer(1, 6),
          p("Tableau 3 — Stratégies sur le test final, frais inclus.", legende),
          p(RES.phrases_trouvailles(v, "fr")[2] + " " + (
              "La stratégie du modèle retenu réduit la volatilité et le drawdown par rapport à l'achat simple (H5 confirmée pour "
              + " et ".join(nom[a] for a in actifs) + ")" if all(h["H5"][a]["confirmee"] for a in actifs) else
              "H5 : " + " ; ".join(f"{'confirmée' if h['H5'][a]['confirmee'] else 'non confirmée'} pour {nom[a]}" for a in actifs))
            + (" ; mais un QLIKE plus faible ne donne pas ici une meilleure stratégie que HAR-RV."
               if all(t["actifs"][a]["strategie"]["difference_sharpe_retenu_moins_har"]["bas"] <= 0 for a in actifs) else ".")),
          figure(f"figure_11_test_strategie_{actifs[0]}.png", f"Figure 3 — Test final, {nom[actifs[0]]} : valeur des stratégies, frais "
                 "inclus.", 0.85),
          PageBreak()]

    # --- Page 5 : limites et liens --------------------------------------------------------------------------------
    limites = RES.points_limites(t, attentes, dev, ex, regles)
    e += [p("7. Limites", h1), puces(limites), Spacer(1, 6),
          p("8. Reproduire et vérifier", h1),
          puces([f"Code, règles, journal des décisions et résultats : {DEPOT} (`docs/CHOIX.md`, `docs/RESULTATS_TEST.md`).",
                 f"API de prévision (FastAPI, modèles ONNX) : {API} (documentation interactive : {API}/docs). Le service gratuit "
                 "s'endort sans requête : la première réponse peut prendre du temps.",
                 "Reproduction rapide (documents et tests, sans données) et reproduction complète (téléchargement, entraînement) : "
                 "voir le README du dépôt.",
                 "Licences : code sous licence MIT (`LICENSE`) ; données Binance Vision et fichiers dérivés (figures, résultats, cette "
                 "synthèse, modèles) sous CC BY-NC-SA 4.0 (`LICENSE-DONNEES.md`)."]),
          Spacer(1, 8),
          p(f"Données : Binance Vision, CC BY-NC-SA 4.0 — projet volatility-forecasting-dl, Mohamed Aljene. Résultats lus dans "
            f"`rapports/test_final.json` (code du commit {t['commit_du_code'][:7]}).", petit)]
    return e


def entrees() -> tuple:
    """Fichiers lus par la synthèse, dans l'ordre des paramètres de contenu()."""
    attentes = tomllib.loads((C.RACINE / "config" / "attentes_test.toml").read_text(encoding="utf-8"))
    return (lire("test_final.json"), attentes, lire("comparaison_modeles.json"), lire("explicabilite.json"), R.charger_regles(),
            lire("qualite_donnees.json"), lire("exploration.json"))


def enregistrer_polices() -> None:
    import reportlab
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    polices = Path(reportlab.__file__).parent / "fonts"
    for nom, fichier in (("Vera", "Vera.ttf"), ("VeraBd", "VeraBd.ttf"), ("VeraIt", "VeraIt.ttf"), ("VeraBI", "VeraBI.ttf")):
        pdfmetrics.registerFont(TTFont(nom, str(polices / fichier)))
    pdfmetrics.registerFontFamily("Vera", normal="Vera", bold="VeraBd", italic="VeraIt", boldItalic="VeraBI")


def generer(chemin: Path = CHEMIN_PDF) -> Path:
    import reportlab
    from reportlab import rl_config
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate

    e = entrees()
    t = e[0]
    enregistrer_polices()

    ouverture = dt.datetime.fromisoformat(t["ouvert_le"]).replace(tzinfo=dt.timezone.utc)
    os.environ["SOURCE_DATE_EPOCH"] = str(calendar.timegm(ouverture.date().timetuple()))   # date fixe : jour d'ouverture du test

    def pied_de_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Vera", 7.5)
        canvas.drawString(2 * cm, 1.2 * cm, "Données : Binance Vision, CC BY-NC-SA 4.0 — volatility-forecasting-dl")
        canvas.drawRightString(19 * cm, 1.2 * cm, f"page {doc.page}")
        canvas.restoreState()

    rl_config.useA85 = 0      # flux compressés en binaire, sans codage ASCII85 : fichier plus petit d'environ un quart
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_suffix(".pdf.tmp")
    doc = SimpleDocTemplate(str(temporaire), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.7 * cm, bottomMargin=1.8 * cm,
                            title="Prévoir la volatilité de BTC et d'ETH — synthèse", author="Mohamed Aljene",
                            subject="Prévision de la volatilité réalisée journalière (BTCUSDT, ETHUSDT)", creator="src/synthese.py",
                            producer="reportlab " + reportlab.Version, invariant=1, lang="fr-FR")
    doc.build(contenu(*e), onFirstPage=pied_de_page, onLaterPages=pied_de_page)
    os.replace(temporaire, chemin)
    return chemin


def main() -> int:
    C.proteger_sortie()
    chemin = generer()
    import hashlib
    print(f"{C.chemin_relatif(chemin)} généré ({C.nombre_fr(chemin.stat().st_size / 1024, 0)} Ko), SHA-256 "
          f"{hashlib.sha256(chemin.read_bytes()).hexdigest()}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
