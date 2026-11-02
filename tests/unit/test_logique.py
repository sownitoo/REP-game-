"""U9-U11 : votes, permissifs, verrous (raisons), configuration."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

from sim.config import RACINE, ErreurConfig, charger_config
from sim.logic.permissives import calculer_permissifs
from sim.logic.voting import vote


# ----------------------------------------------------------------------------- U9
def test_u9_votes() -> None:
    assert vote("2/3", [True, True, False])
    assert not vote("2/3", [True, False, False])
    assert vote("1/2", [False, True])
    assert vote("2/4", [False, True, False, True])
    with pytest.raises(ValueError):
        vote("2/3", [True, True])


def test_u9_c9_hysteresis(rp100) -> None:
    c, e = rp100, rp100.logique.etat
    lg = c.cfg.logique.c9
    calculer_permissifs(c, e)
    assert e.c9
    c.condenseur.etat.p_bar = (lg.p_cond_max_bar + lg.p_cond_perte_bar) / 2   # entre les deux seuils
    calculer_permissifs(c, e)
    assert e.c9                                                               # reste présent
    c.condenseur.etat.p_bar = lg.p_cond_perte_bar * 1.01
    calculer_permissifs(c, e)
    assert not e.c9                                                           # perdu
    c.condenseur.etat.p_bar = (lg.p_cond_max_bar + lg.p_cond_perte_bar) / 2
    calculer_permissifs(c, e)
    assert not e.c9                                                           # pas de retour avant 0,17 bar


def test_u9_p14_vote_2_sur_3(rp100) -> None:
    c, e = rp100, rp100.logique.etat
    capteur = c.gvs[0].capteur
    capteur.etat.valeurs = [80.0, 50.0, 50.0]          # une seule voie : pas de P-14
    calculer_permissifs(c, e)
    assert not e.p14
    capteur.etat.valeurs = [80.0, 80.0, 50.0]
    calculer_permissifs(c, e)
    assert e.p14 and e.p14_gv[0]


# ----------------------------------------------------------------------------- U10
def _toutes_les_commandes_refusees_ont_une_raison(c) -> None:
    for cible in c.commandables:
        for ligne in c.liste_commandes(cible):
            if not ligne["possible"]:
                assert any(not cond["ok"] and cond["texte"] for cond in ligne["conditions"]), (cible, ligne)


def test_u10_refus_toujours_motive(rp100) -> None:
    _toutes_les_commandes_refusees_ont_une_raison(rp100)
    rp100.commande("TURBINE", "declencher")
    rp100.avancer(5.0)
    _toutes_les_commandes_refusees_ont_une_raison(rp100)


def test_u10_reponse_contient_les_raisons(rp100) -> None:
    r = rp100.commande("TURBINE", "coupler")
    assert not r.ok and any("découplé" in t for t in r.raisons)
    r = rp100.commande("ARE1_GD", "position", 150.0)
    assert not r.ok and any("manuel" in t for t in r.raisons) and any("Valeur" in t for t in r.raisons)
    assert not rp100.commande("INCONNU", "ouvrir").ok


# ----------------------------------------------------------------------------- U11
def test_u11_config_valide() -> None:
    cfg = charger_config()
    assert len(cfg.composants) > 40
    assert {"ARE1_GD", "ARE4_GD", "VIV3", "APP2", "GCTC_G4"} <= set(cfg.composants)


def test_u11_cle_inconnue_refusee(tmp_path: Path) -> None:
    brut = yaml.safe_load((RACINE / "config" / "plant.yaml").read_text(encoding="utf-8"))
    brut["turbine"]["cle_fantaisie"] = 1.0
    fichier = tmp_path / "plant.yaml"
    fichier.write_text(yaml.safe_dump(brut, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ErreurConfig, match="cle_fantaisie"):
        charger_config(fichier)


LITTERAUX_AUTORISES = {0, 1, 2, 4, 0.5}   # constantes mathématiques (moyenne, carré, formule quadratique)


def test_u11_aucune_valeur_en_dur_dans_sim() -> None:
    """Toutes les valeurs numériques doivent venir de plant.yaml (ou être des constantes nommées)."""
    fautes = []
    for fichier in sorted((RACINE / "sim").rglob("*.py")):
        if fichier.name == "units.py":
            continue
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        nommees = {id(n.value) for n in arbre.body if isinstance(n, ast.Assign)
                   and all(isinstance(t, ast.Name) and t.id.isupper() for t in n.targets)}
        for n in ast.walk(arbre):
            if (isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
                    and not isinstance(n.value, bool) and n.value not in LITTERAUX_AUTORISES
                    and id(n) not in nommees):
                fautes.append(f"{fichier.relative_to(RACINE)}:{n.lineno} → {n.value}")
    assert not fautes, "Valeurs en dur :\n" + "\n".join(fautes)
