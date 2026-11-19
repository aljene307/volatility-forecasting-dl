"""Export ONNX des modèles servis par l'API (règles : config/regles.toml, section api ; docs/REGLES.md, section 18).

- Modèles retenus (Transformer pour BTC, CNN-LSTM pour ETH), 3 graines du découpage du test final ; empreintes des
  poids vérifiées (rapports/modeles_deep_learning.json) avant l'export ; ancien exportateur de torch (dynamo=False).
- Contrôle : onnxruntime redonne les sorties de torch sur des entrées aléatoires.
- Paramètres (api/modeles/parametres.json) : normalisation du découpage du test final, s² mesuré sur sa validation
  interne pour la prévision moyenne des 3 graines, volatilité cible, bornes d'exposition, quantile de la VaR.
- Exemple de démonstration SYNTHÉTIQUE (api/exemple_synthetique.json), sans aucune donnée Binance.
- Manifeste des empreintes (api/modeles/manifeste.json), vérifié par l'API à son démarrage.

Fichiers ONNX et paramètres : œuvres dérivées sous CC BY-NC-SA 4.0 ; Données : Binance Vision.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path
from statistics import NormalDist

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import baselines as B  # noqa: E402
import commun as C  # noqa: E402
import comparer as K  # noqa: E402
import entrainer as T  # noqa: E402
import regles as R  # noqa: E402
import variables as V  # noqa: E402

DOSSIER_API = C.RACINE / "api"
DOSSIER_MODELES = DOSSIER_API / "modeles"
LICENCE = "CC BY-NC-SA 4.0 (œuvre dérivée) ; Données : Binance Vision"
LONGUEUR = 30


def _sha256(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def exporter_reseau(reseau, chemin: Path, n_entrees: int) -> float:
    """Export ONNX (ancien exportateur), puis écart maximal onnxruntime / torch sur des entrées aléatoires."""
    import onnxruntime as ort
    import torch
    exemple = torch.zeros(1, LONGUEUR, n_entrees)
    torch.onnx.export(reseau, (exemple,), str(chemin), input_names=["entree"], output_names=["sortie"],
                      dynamic_axes={"entree": {0: "lot"}, "sortie": {0: "lot"}}, opset_version=17, dynamo=False)
    x = np.random.default_rng(0).normal(size=(64, LONGUEUR, n_entrees)).astype("float32")
    with torch.no_grad():
        attendu = reseau(torch.from_numpy(x)).numpy()
    obtenu = ort.InferenceSession(str(chemin), providers=["CPUExecutionProvider"]).run(None, {"entree": x})[0]
    return float(np.max(np.abs(obtenu - attendu)))


def exemple_synthetique(variables: list[str], graine: int = 7) -> dict:
    """Requête de démonstration SYNTHÉTIQUE : valeurs tirées au hasard, cohérentes entre elles, sans aucune donnée Binance."""
    rng = np.random.default_rng(graine)
    rv = 0.02 * np.exp(np.cumsum(rng.normal(0, 0.15, LONGUEUR + 29)))
    jours = []
    for i in range(29, 29 + LONGUEUR):
        r1, r7, r30 = rv[i], rv[i - 6:i + 1].mean(), rv[i - 29:i + 1].mean()
        valeurs = {"rv_1": r1, "rv_7": r7, "rv_30": r30, "log_rv_1": math.log(r1), "log_rv_7": math.log(r7), "log_rv_30": math.log(r30),
                   "parkinson": float((r1 * rng.uniform(0.8, 1.2)) ** 2), "garman_klass": float((r1 * rng.uniform(0.8, 1.2)) ** 2),
                   "log_rendement": float(rng.normal(0, r1)), "log_volume": float(rng.normal(21.0, 0.3)),
                   "rsi_14": float(rng.uniform(30, 70)), "macd_histogramme_relatif": float(rng.normal(0, 0.003)),
                   "bollinger_largeur_relative": float(rng.uniform(0.05, 0.3))}
        jours.append({v: float(valeurs[v]) for v in variables})
    return {"avertissement": "EXEMPLE SYNTHÉTIQUE : valeurs tirées au hasard pour la démonstration, sans aucune donnée de marché.",
            "requete": {"actif": "BTCUSDT", "jour_semaine_dernier_jour": 2, "jours": jours}}


def executer(regles: dict) -> dict:
    import torch
    import reseaux
    T.configurer_torch(regles)
    api = regles["api"]
    cle = T._cle_donnees(regles)
    final = R.decoupages(regles)[-1]
    nom_decoupage = final["nom"].replace(" ", "_")
    graines = regles["modeles"]["graines_deep_learning"]
    manifeste_dl = json.loads(K.CHEMIN_MANIFESTE.read_text(encoding="utf-8"))
    choix = json.loads((K.DOSSIER_DL / "reglage.json").read_text(encoding="utf-8"))
    vol_cible = json.loads(V.CHEMIN_VOL_CIBLE.read_text(encoding="utf-8"))["actifs"]
    s = regles["strategie"]
    variables = list(regles["entrainement"]["variables_continues"])
    DOSSIER_MODELES.mkdir(parents=True, exist_ok=True)
    parametres = {"licence": LICENCE, "description": "Paramètres des modèles servis par l'API (découpage du test final).",
                  "variables": variables, "longueur_sequence": LONGUEUR, "jour_semaine": "one-hot de 7 colonnes après les variables, lundi = 0",
                  "annualisation_jours": s["annualisation_jours"], "exposition_min": s["exposition_min"],
                  "exposition_max": s["exposition_max"], "var_niveau": s["var_niveau"],
                  "var_quantile": NormalDist().inv_cdf(s["var_niveau"]), "actifs": {}}
    ecarts = {}
    for actif, modele in api["modeles_servis"].items():
        norm = json.loads((K.DOSSIER_DL / "normalisation" / actif / f"{nom_decoupage}.json").read_text(encoding="utf-8"))
        if norm["colonnes"] != variables:
            raise ValueError(f"{actif} : colonnes de normalisation inattendues.")
        fichiers = []
        for g in graines:
            relatif = f"poids/{actif}/{modele}/{nom_decoupage}_graine_{g}.pt"
            if _sha256(K.DOSSIER_DL / relatif) != manifeste_dl["poids"][relatif]:
                raise ValueError(f"Empreinte différente : {relatif}")
            r = reseaux.construire_reseau(modele, choix[actif][modele]["combinaison"], len(variables) + 7, LONGUEUR)
            r.load_state_dict(torch.load(K.DOSSIER_DL / relatif, weights_only=True))
            r.eval()
            nom = f"{actif}_{modele}_graine_{g}.onnx"
            ecarts[nom] = exporter_reseau(r, DOSSIER_MODELES / nom, len(variables) + 7)
            fichiers.append(nom)
        # s² : validation interne du découpage du test final, prévision moyenne des 3 graines (comme dans le projet)
        unite_b = K._unite(B.DOSSIER_REPRISE, f"{B.VERSION}|{actif}|baselines|{final['nom']}|{cle}")
        val = [K._unite(K.DOSSIER_DL / "unites", T.id_pli(actif, modele, final["nom"], g, cle))["validation"] for g in graines]
        if any(v["date_cible"] != unite_b["validation"]["date_cible"] for v in val):
            raise ValueError(f"{actif} : dates de validation incohérentes.")
        s2, _ = B.s2_et_biais(np.array(unite_b["validation"]["cible"]), np.mean([v["prevision_log"] for v in val], axis=0))
        parametres["actifs"][actif] = {
            "modele": modele, "fichiers_onnx": fichiers, "s2": s2, "vol_cible_annuelle": vol_cible[actif]["valeur_annualisee"],
            "normalisation": {k: norm[k] for k in ("moyennes", "ecarts_types", "cible_moyenne", "cible_ecart_type")},
            "validation_interne": [str(final["validation"][0]), str(final["validation"][1])]}
    C.ecrire_texte(DOSSIER_MODELES / "parametres.json", C.texte_json(parametres))
    C.ecrire_texte(DOSSIER_API / "exemple_synthetique.json", C.texte_json(exemple_synthetique(variables)))
    fichiers = sorted(p for p in DOSSIER_MODELES.iterdir() if p.suffix in (".onnx", ".json") and p.name != "manifeste.json")
    C.ecrire_texte(DOSSIER_MODELES / "manifeste.json", C.texte_json({
        "description": "Empreintes SHA-256 des fichiers servis par l'API, vérifiées à son démarrage.", "licence": LICENCE,
        "fichiers": {p.name: _sha256(p) for p in fichiers}}))
    return {"ecarts_onnxruntime_torch": ecarts, "taille_octets": sum(p.stat().st_size for p in DOSSIER_MODELES.iterdir())}


def main() -> int:
    C.proteger_sortie()
    resultat = executer(R.charger_regles())
    for nom, e in resultat["ecarts_onnxruntime_torch"].items():
        print(f"{nom} : écart maximal onnxruntime / torch (sortie normalisée) {e:.2e}")
    print(f"Taille du dossier api/modeles : {resultat['taille_octets'] / 1024:.1f} Ko")
    return 0


if __name__ == "__main__":
    sys.exit(main())
