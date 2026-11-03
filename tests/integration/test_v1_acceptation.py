"""Tests d'acceptation V1 (B1-B9).

Spec §10, V1 : « Primaire 4 boucles + pressuriseur + cœur boîte noire + régulations P/niveau PZR —
stable à 100 % ; échelon de charge −10 % encaissé sans AU ». Plus l'ASG (proposition validée).
"""

from __future__ import annotations

import pytest

from sim.plant import Centrale
from tests.conftest import serie

GV = ["GV1", "GV2", "GV3", "GV4"]
BOUCLES = ["B1", "B2", "B3", "B4"]


# ============================================================================ B1
@pytest.mark.lent
def test_b1_primaire_stable_100pct(rp100: Centrale) -> None:
    c = rp100
    m0 = c.masse_primaire_kg()
    r = serie(c, 3600.0, 60.0, "pzr.p_bar", "pzr.niveau_pct", "primaire.tmoy_c", "coeur.puissance_pct",
              "rcv.charge_kg_s", "rcv.decharge_kg_s", "logique.au")
    for x in r:
        assert x["pzr.p_bar"] == pytest.approx(155.0, abs=0.5)
        assert x["pzr.niveau_pct"] == pytest.approx(60.0, abs=2.0)
        assert x["primaire.tmoy_c"] == pytest.approx(307.0, abs=0.8)
        assert x["coeur.puissance_pct"] == pytest.approx(100.0, abs=1.0)
        assert x["logique.au"] == 0.0
    assert c.alarmes.liste() == []
    # B9 : masse du primaire (charge = décharge à l'équilibre) — dérive < 0,01 %/h
    assert abs(c.masse_primaire_kg() - m0) / m0 < 1e-4


# ============================================================================ B2
@pytest.mark.lent
def test_b2_echelon_moins_10pct_sans_au(rp100: Centrale) -> None:
    c = rp100
    assert c.commande("TURBINE", "consigne_mw", 0.9 * c.cfg.turbine.p_elec_nom_mw).ok
    r = serie(c, 900.0, 1.0, "logique.au", "pzr.p_bar", "pzr.porv_qm_kg_s", "pzr.soupapes_ouvertes",
              "coeur.puissance_pct", "vapeur.soupapes_ouvertes")
    assert all(x["logique.au"] == 0.0 for x in r), "l'échelon −10 % doit être encaissé sans AU"
    assert all(x["pzr.porv_qm_kg_s"] == 0.0 and x["pzr.soupapes_ouvertes"] == 0.0 for x in r)
    assert all(x["vapeur.soupapes_ouvertes"] == 0.0 for x in r)
    assert 150.0 < min(x["pzr.p_bar"] for x in r) and max(x["pzr.p_bar"] for x in r) < 160.0
    assert min(x["coeur.puissance_pct"] for x in r) > 80.0
    m = c.mesures
    assert m["coeur.puissance_pct"] == pytest.approx(90.0, abs=3.0)
    assert abs(m["primaire.tmoy_c"] - m["primaire.tref_c"]) < 1.0


# ============================================================================ B3
@pytest.mark.lent
def test_b3_declenchement_turbine_primaire(rp100: Centrale) -> None:
    c = rp100
    c.commande("TURBINE", "declencher")
    r = serie(c, 600.0, 1.0, "pzr.p_bar", "pzr.niveau_pct", "primaire.tmoy_c", "gctc.ouverture_pct",
              "pzr.porv_qm_kg_s", "cuve.marge_saturation_c", *[f"{g}.niveau_pct" for g in GV])
    assert c.logique.etat.au and c.gct.etat.c8
    assert max(x["gctc.ouverture_pct"] for x in r) > 50.0          # régulateur « déclenchement turbine »
    p_min = min(x["pzr.p_bar"] for x in r)
    assert p_min > c.cfg.logique.au.p_pzr_basse_bar                  # pas de seuil IS (125,6 bar, V4) atteint
    assert min(x["pzr.niveau_pct"] for x in r) > c.cfg.pressuriseur.niveau_bas_pct
    assert all(x["pzr.porv_qm_kg_s"] == 0.0 for x in r)
    assert max(x[f"{g}.niveau_pct"] for x in r for g in GV) < 69.0   # pas de P-14
    assert 289.0 <= r[-1]["primaire.tmoy_c"] <= 295.0
    assert min(x["cuve.marge_saturation_c"] for x in r) > 15.0


# ============================================================================ B4
def test_b4_perte_pompe_primaire(rp100: Centrale) -> None:
    c = rp100
    assert c.commande("PP1", "arreter").ok
    serie(c, 5.0, 0.1, "logique.au")
    assert c.logique.etat.au
    assert any("débit primaire bas" in cause and "B1" in cause for cause in c.logique.etat.au_causes)
    r = serie(c, 120.0, 1.0, "B1.debit_pct", "B2.debit_pct")
    assert -25.0 < r[-1]["B1.debit_pct"] < -5.0          # débit inverse limité par l'antidévireur
    assert r[-1]["B2.debit_pct"] > 100.0


# ============================================================================ B5
@pytest.mark.lent
def test_b5_perte_totale_are_asg(rp100: Centrale) -> None:
    c = rp100
    for b in range(1, 5):
        for v in (f"ARE{b}_GD", f"ARE{b}_PD"):
            c.commande(v, "manu")
            c.commande(v, "position", 0.0)
    v0_cst = c.mesures["cst.volume_m3"]
    serie(c, 60.0, 1.0, "logique.au")
    # AU par la première cause atteinte (débit d'eau insuffisant, niveau très bas ou vide condenseur)
    assert c.logique.etat.au
    assert any("Démarrage ASG_TP (niveau GV très bas)" in e.texte for e in c.journal.evenements)
    assert all(p.etat.en_marche for p in c.asg.pompes()), "les 3 pompes ASG doivent démarrer"
    r = serie(c, 1740.0, 60.0, "asg.qm_kg_s", *[f"{g}.niveau_pct" for g in GV])
    assert max(x["asg.qm_kg_s"] for x in r) > 80.0
    assert all(r[-1][f"{g}.niveau_pct"] > 20.0 for g in GV)
    assert c.mesures["cst.volume_m3"] < v0_cst                 # l'ASG puise dans la CST


# ============================================================================ B6
@pytest.mark.lent
def test_b6_circulation_naturelle(rp100: Centrale) -> None:
    c = rp100
    c.commande("TURBINE", "declencher")
    c.avancer(120.0)
    for b in range(1, 5):
        assert c.commande(f"PP{b}", "arreter").ok
    assert c.commande("REG_GCTC", "mode_pression").ok
    r = serie(c, 3600.0, 60.0, *[f"{b}.debit_pct" for b in BOUCLES], "cuve.marge_saturation_c", "pzr.p_bar")
    for b in BOUCLES:
        assert 2.0 < r[-1][f"{b}.debit_pct"] < 10.0, "circulation naturelle établie dans chaque boucle"
    assert min(x["cuve.marge_saturation_c"] for x in r[5:]) > 20.0


# ============================================================================ B7
@pytest.mark.lent
def test_b7_porv_avant_au_pression_haute(rp100: Centrale) -> None:
    c = rp100
    assert c.commande("REG_P_PZR", "consigne", 164.0).ok
    r = serie(c, 2400.0, 1.0, "pzr.p_bar", "pzr.porv_qm_kg_s", "logique.au")
    assert max(x["pzr.porv_qm_kg_s"] for x in r) > 0.0, "les PORV doivent s'ouvrir à 162 bar"
    assert max(x["pzr.p_bar"] for x in r) < c.cfg.logique.au.p_pzr_haute_bar
    assert all(x["logique.au"] == 0.0 for x in r)


# ============================================================================ B8
def test_b8_verrous_v1(rp100: Centrale) -> None:
    c = rp100
    # pompe primaire sans pompe de soulèvement d'huile
    c.commande("PP2", "arreter")
    c.commande("PSH2", "arreter")
    c.avancer(5.0)
    rep = c.commande("PP2", "demarrer")
    assert not rep.ok and any("soulèvement d'huile" in t for t in rep.raisons)
    # AU présent : pas de pilotage des grappes ni de blocage du flux bas sans P-10
    assert c.logique.etat.au
    rep = c.commande("GRAPPES", "extraire_arret")
    assert not rep.ok and any("AU réarmé" in t for t in rep.raisons)
    c.avancer(60.0)
    c.commande("RPR", "debloquer_flux_bas")
    rep = c.commande("RPR", "bloquer_flux_bas")
    assert not rep.ok and any("P-10" in t for t in rep.raisons)
    # RCV : pas d'orifice de décharge sans pompe de charge (ordre de mise en service, §4.2)
    c.commande("RCV_PC1", "arreter")
    c.avancer(20.0)
    assert c.rcv.orifices[0].etat.position == 0.0, "orifices refermés à la perte de la charge"
    rep = c.commande("RCV_ORIF2", "ouvrir")
    assert not rep.ok and any("Pompe de charge en marche" in t for t in rep.raisons)
