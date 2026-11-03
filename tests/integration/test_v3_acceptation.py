"""Tests d'acceptation V3 : électricité, diesels, séquenceurs, batteries, air comprimé, joints des PP.

Spec §10, V3 : « S5, S6, S12 jouables ».
"""

from __future__ import annotations

import pytest

from sim.plant import Centrale
from sim.scenarios.chargement import centrale_scenario
from tests.conftest import serie

TABLEAUX = ["LGA", "LGB", "LHA", "LHB"]


def test_d1_situation_normale(rp100: Centrale) -> None:
    c = rp100
    c.avancer(10.0)
    m = c.mesures
    assert all(m[f"elec.{k}.tension_pct"] == 100.0 for k in TABLEAUX)
    assert m["elec.DIESEL_A.en_service"] == 0.0 and m["elec.DIESEL_B.en_service"] == 0.0
    assert m["elec.LBA.charge_pct"] == 100.0 and m["air.p_bar"] == pytest.approx(7.0)
    assert c.elec.etat.source_normale == "TS"
    assert c.alarmes.liste() == []


@pytest.mark.lent
def test_d2_s5_perte_alimentations_externes() -> None:
    c = centrale_scenario("s5_perte_alimentations_externes")
    c.avancer(30.5)                                          # panne programmée à t = 30 s
    assert c.elec.etat.reseau_ok is False
    r = serie(c, 15.0, 0.5, "logique.au", "elec.LHA.tension_pct", "elec.LHB.tension_pct")
    assert c.logique.etat.au and any("sous-tension" in x or "turbine" in x for x in c.logique.etat.au_causes)
    t_lh = next(x["t_s"] for x in r if x["elec.LHA.tension_pct"] == 100.0 and x["elec.LHB.tension_pct"] == 100.0)
    assert t_lh - 30.0 <= 13.0, "diesels couplés en ~10 s (+ 1 s de détection)"
    c.avancer(30.0)
    for rep in ("RCV_PC1", "RRI_P1", "SEC_P1", "ASG_MP1", "SAR_C1", "RCV_PC2", "RRI_P2", "SEC_P2", "ASG_MP2"):
        assert c.pompes[rep].etat.en_marche, f"{rep} relancée par le séquenceur"
    assert all(not p.etat.en_marche for p in c.primaire.pompes)
    r = serie(c, 3600.0, 60.0, "B1.debit_pct", "cuve.marge_saturation_c", "elec.DIESEL_A.charge_kw", "air.p_bar")
    assert 2.0 < r[-1]["B1.debit_pct"] < 10.0, "circulation naturelle"
    assert min(x["cuve.marge_saturation_c"] for x in r) > 20.0
    assert max(x["elec.DIESEL_A.charge_kw"] for x in r) < c.cfg.electricite.diesel.puissance_kw
    assert min(x["air.p_bar"] for x in r) > c.cfg.air_comprime.p_min_bar


@pytest.mark.lent
def test_d3_s6_perte_totale_puis_diesel_repare() -> None:
    c = centrale_scenario("s6_perte_totale_sources")
    r = serie(c, 2700.0, 60.0, "elec.LBB.charge_pct", "elec.LBA.charge_pct", "joints.fuite_m3h", "asg.qm_kg_s")
    assert c.elec.diesels["DIESEL_A"].etat.etat == "echec"
    assert r[-1]["elec.LBB.charge_pct"] == 0.0, "batterie B vide au bout de 30 min"
    assert 55.0 < r[-1]["elec.LBA.charge_pct"] < 70.0, "batterie A : 2 h d'autonomie"
    assert r[-1]["joints.fuite_m3h"] > 10.0, "les joints des 4 pompes primaires fuient"
    assert c.asg.turbopompe.etat.en_marche, "turbopompe ASG tenue par la batterie A"
    c.avancer(60.0)                                         # réparation à 45 min
    assert c.commande("DIESEL_A", "rearmer").ok
    assert c.commande("DIESEL_A", "demarrer").ok
    c.avancer(45.0)
    assert c.elec.diesels["DIESEL_A"].etat.etat == "couple"
    assert c.mesures["elec.LHA.tension_pct"] == 100.0
    assert c.pompes["RCV_PC1"].etat.en_marche
    fuite = c.mesures["joints.fuite_m3h"]
    r = serie(c, 1800.0, 60.0, "joints.fuite_m3h", "elec.LBA.charge_pct", "pzr.niveau_pct")
    assert max(x["joints.fuite_m3h"] for x in r) <= fuite + 1.0, "injection aux joints rétablie : plus de dégradation"
    assert r[-1]["elec.LBA.charge_pct"] > r[0]["elec.LBA.charge_pct"], "batterie A rechargée"
    assert not c.joints.etat.hors_domaine


def test_d4_s12_perte_air() -> None:
    c = centrale_scenario("s12_perte_air_comprime")
    serie(c, 300.0, 10.0, "air.p_bar")
    v = c.vannes
    assert c.mesures["air.p_bar"] < c.cfg.air_comprime.p_min_bar
    assert v["ARE1_GD"].etat.position == 0.0, "ARE en repli fermé"
    assert v["PZR_ASP2"].etat.position == 0.0, "aspersion en repli fermé"
    assert v["RCV_CHARGE"].etat.position == 1.0, "FCV-121 en repli ouvert"
    assert v["RCV_LCV459"].etat.position == 0.0, "décharge en repli fermé"
    assert v["VIV1"].etat.position == 1.0, "VIV tenues par leur réserve (15 min)"
    assert c.logique.etat.au
    assert c.commande("SAR", "isoler_fuite").ok
    assert c.commande("SAR_C2", "demarrer").ok
    c.avancer(600.0)
    assert c.mesures["air.p_bar"] > c.cfg.air_comprime.p_min_bar


def test_d5_verrous_electriques(rp100: Centrale) -> None:
    c = rp100

    def refus(cible: str, action: str, motif: str) -> None:
        rep = c.commande(cible, action)
        assert not rep.ok and any(motif in t for t in rep.raisons), (cible, action, rep.raisons)

    refus("DIESEL_A", "coupler", "Diesel à vitesse et tension")
    assert c.commande("DIESEL_A", "demarrer").ok
    c.avancer(15.0)
    refus("DIESEL_A", "coupler", "hors tension")          # tableau LHA alimenté par LGA
    refus("LHA", "fermer_arrivee", "Arrivée ouverte")
    assert c.commande("RESEAU", "perte_reseau").ok
    c.avancer(20.0)
    assert c.elec.diesels["DIESEL_A"].etat.etat == "couple"
    refus("DIESEL_A", "arreter", "Diesel découplé")
    refus("LHA", "fermer_arrivee", "sous tension")         # LGA mort
    refus("PP1", "demarrer", "Tableau LGA sous tension")
    assert c.commande("RESEAU", "retour_reseau").ok
    c.avancer(2.0)
    assert c.commande("LHA", "fermer_arrivee").ok         # transfert sur le réseau : le diesel se découple
    c.avancer(2.0)
    assert c.elec.tableaux["LHA"].etat.source == "LGA"
    assert c.commande("DIESEL_A", "arreter").ok
