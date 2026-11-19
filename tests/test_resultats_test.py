"""Le rapport du test final et le bloc du README sont exactement générés depuis rapports/test_final.json."""

import copy
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

import resultats_test as RT  # noqa: E402


def test_rapport_et_bloc_readme_identiques_au_json():
    t, attentes, dev = RT.charger()
    assert RT.CHEMIN_MD.read_text(encoding="utf-8") == RT.rapport_markdown(t, attentes, dev)
    assert RT.bloc_readme(t, attentes) in (RACINE / "README.md").read_text(encoding="utf-8")


def test_verdicts_affiches_sont_ceux_du_json_et_temoin():
    t, attentes, _ = RT.charger()
    bloc = RT.bloc_readme(t, attentes)
    for k in ("H1", "H2", "H3", "H4", "H5", "H6", "H7"):
        ligne = next(x for x in bloc.splitlines() if x.startswith(f"| {k} :"))
        assert ligne.count("non confirmée") == sum(not v["confirmee"] for v in t["hypotheses"][k].values())
    faux = copy.deepcopy(t)
    a = next(iter(faux["hypotheses"]["H1"]))
    faux["hypotheses"]["H1"][a]["confirmee"] = not faux["hypotheses"]["H1"][a]["confirmee"]
    assert RT.bloc_readme(faux, attentes) != bloc                    # témoin : un verdict changé change le bloc
