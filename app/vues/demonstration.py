"""Démonstration : envoi de l'exemple SYNTHÉTIQUE, ou d'un fichier CSV de l'utilisateur, à l'API ; aucune donnée Binance."""

import io
import json
import math

import pandas as pd
import requests
import streamlit as st

import outils_app as K

DELAI_S = 90
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


@st.cache_data
def exemple() -> dict:
    return json.loads((K.RACINE / "api" / "exemple_synthetique.json").read_text(encoding="utf-8"))


def variables() -> list[str]:
    return list(K.regles()["entrainement"]["variables_continues"])


def lire_csv(contenu: bytes) -> tuple[list[dict] | None, list[str]]:
    """Lit et valide un CSV : une ligne d'en-tête avec les 13 variables, puis 30 lignes (du plus ancien au plus récent).
    Séparateur « , » avec point décimal, ou « ; » avec virgule décimale. Renvoie (jours, erreurs)."""
    attendu = variables()
    longueur = K.regles()["variables"]["fenetre_sequence_jours"]
    for sep, dec in ((",", "."), (";", ",")):
        try:
            t = pd.read_csv(io.BytesIO(contenu), sep=sep, decimal=dec, float_precision="round_trip")   # nombres relus au bit près
        except Exception:
            continue
        if set(t.columns) == set(attendu):
            break
    else:
        return None, [f"En-tête attendu : les colonnes {', '.join(attendu)} (séparateur « , » ou « ; »)."]
    erreurs = []
    if len(t) != longueur:
        erreurs.append(f"Il faut exactement {longueur} lignes de données (reçu {len(t)}).")
    for c in attendu:
        valeurs = pd.to_numeric(t[c], errors="coerce")
        mauvaises = [i + 1 for i, v in enumerate(valeurs) if not (isinstance(v, float) and math.isfinite(v))]
        if mauvaises:
            erreurs.append(f"Colonne {c} : valeur manquante ou non numérique aux lignes {', '.join(map(str, mauvaises[:10]))}.")
    if erreurs:
        return None, erreurs
    return [{c: float(t[c].iloc[i]) for c in attendu} for i in range(len(t))], []


def envoyer(adresse: str, requete: dict, delai: float = DELAI_S) -> tuple[str, object]:
    """('ok', réponse), ('invalide', erreurs 422) ou ('panne', message clair)."""
    try:
        r = requests.post(f"{adresse}/prevoir", json=requete, timeout=delai)
    except requests.exceptions.Timeout:
        return "panne", f"L'API n'a pas répondu dans le délai de {delai:.0f} s ({adresse}). Réessayez dans une minute."
    except requests.exceptions.RequestException:
        return "panne", (f"L'API ne répond pas à l'adresse {adresse}. Elle est peut-être arrêtée ou en train de démarrer : "
                         "réessayez dans une minute.")
    if r.status_code == 422:
        return "invalide", r.json().get("erreurs", [])
    if r.status_code != 200:
        return "panne", f"L'API a répondu avec le code {r.status_code} ({adresse})."
    return "ok", r.json()


def _afficher_resultat(statut: str, contenu) -> None:
    if statut == "panne":
        st.error(contenu)
    elif statut == "invalide":
        st.error("L'API a refusé les données :")
        st.table(pd.DataFrame(contenu).rename(columns={"champ": "Champ", "message": "Message"}))
    else:
        c = contenu
        st.success(f"Prévision de {c['modele']} pour {K.NOMS[c['actif']]}.")
        a, b, d, e = st.columns(4)
        a.metric("Volatilité prévue (journalière)", K.pourcent(c["volatilite_journaliere"], 2))
        b.metric("Volatilité prévue (annualisée)", K.pourcent(c["volatilite_annualisee"], 1))
        d.metric("Exposition de la stratégie", K.pourcent(c["exposition"], 0))
        e.metric("VaR à 1 jour à 95 %", K.pourcent(c["var_1_jour_95"], 2))
        st.caption(c["explication"])


def afficher() -> None:
    st.title("Démonstration")
    adresse = K.adresse_api()
    st.markdown(f"Adresse de l'API : `{adresse}`. Les données viennent de vous : l'application et l'API ne téléchargent et ne "
                "diffusent **aucune** donnée Binance.")
    actif = st.selectbox("Actif", K.ACTIFS, format_func=lambda a: K.NOMS[a], key="actif_demo")
    jour = st.selectbox("Jour de la semaine du dernier jour fourni", range(7), format_func=lambda k: JOURS[k], index=2, key="jour_demo")
    st.subheader("Exemple de démonstration")
    st.warning(exemple()["avertissement"])
    if st.button("Envoyer l'exemple synthétique", key="envoyer_exemple"):
        requete = dict(exemple()["requete"], actif=actif, jour_semaine_dernier_jour=jour)
        with st.spinner("L'API se réveille, cela peut prendre environ une minute…"):
            st.session_state["demo"] = envoyer(adresse, requete)
    st.subheader("Vos propres données (fichier CSV)")
    longueur = K.regles()["variables"]["fenetre_sequence_jours"]
    st.markdown(f"Format : une ligne d'en-tête avec les colonnes `{'`, `'.join(variables())}`, puis exactement {longueur} lignes, une par "
                "jour consécutif, du plus ancien au plus récent. Séparateur « , » avec point décimal, ou « ; » avec virgule décimale. "
                "Les variables sont celles du projet, non normalisées, arrêtées à la clôture de chaque jour (voir le README).")
    modele_csv = pd.DataFrame(exemple()["requete"]["jours"])[variables()].to_csv(index=False).encode("utf-8")
    st.download_button("Télécharger un modèle de fichier (valeurs SYNTHÉTIQUES)", modele_csv, file_name="modele_synthetique.csv",
                       mime="text/csv", key="modele_csv")
    fichier = st.file_uploader("Fichier CSV", type=["csv"], key="fichier_csv")
    if fichier is not None and st.button("Envoyer mon fichier", key="envoyer_csv"):
        jours, erreurs = lire_csv(fichier.getvalue())
        if erreurs:
            st.session_state["demo"] = ("invalide", [{"champ": "fichier", "message": e} for e in erreurs])
        else:
            with st.spinner("L'API se réveille, cela peut prendre environ une minute…"):
                st.session_state["demo"] = envoyer(adresse, {"actif": actif, "jour_semaine_dernier_jour": jour, "jours": jours})
    if "demo" in st.session_state:
        _afficher_resultat(*st.session_state["demo"])
    K.pied()
