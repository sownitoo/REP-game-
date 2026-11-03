"""Tests d'acceptation V0 (A1-A11, A13) — cf. docs/PROPOSITION_V0.md §6, rejoués sur la centrale V1.

Spec §10, V0 : « Équilibre stable à 100 % ; fermer une ARE fait baisser le niveau GV
et tasser/gonfler correctement ».
"""

from __future__ import annotations

import json
import time

import pytest

from sim.plant import Centrale
from sim.scenarios.chargement import centrale_depuis_etat
from tests.conftest import serie

GV = ["GV1", "GV2", "GV3", "GV4"]


# ============================================================================ A1-A3
@pytest.fixture(scope="module")
def heure_a_100pct() -> tuple[Centrale, list[dict[str, float]], float]:
    c = centrale_depuis_etat("rp100")
    m0 = c.masse_eau_totale_kg()
    mesures = ["GV1.p_bar", "turbine.p_elec_mw", "coeur.p_thermique_mw", "primaire.q_pompes_mw", "turbine.p_meca_mw",
               "condenseur.q_mer_mw", "logique.au", "pzr.p_bar", "pzr.niveau_pct", "primaire.tmoy_c",
               "coeur.puissance_pct", "rcv.charge_kg_s", "rcv.decharge_kg_s"] \
        + [f"{g}.niveau_pct" for g in GV] + [f"{g}.p_bar" for g in GV]
    releves = serie(c, 3600.0, 60.0, *mesures)
    return c, releves, m0


@pytest.mark.lent
def test_a1_equilibre_100pct(heure_a_100pct) -> None:
    c, releves, _ = heure_a_100pct
    trente_min = [r for r in releves if r["t_s"] <= 1800.0 + 1.0]
    p0 = trente_min[0]["turbine.p_elec_mw"]
    for r in trente_min:
        for g in GV:
            assert r[f"{g}.p_bar"] == pytest.approx(63.0, abs=0.5)
            assert r[f"{g}.niveau_pct"] == pytest.approx(50.0, abs=2.0)
        assert abs(r["turbine.p_elec_mw"] - p0) / p0 < 0.005
        assert r["logique.au"] == 0.0
    assert c.alarmes.liste() == []


@pytest.mark.lent
def test_a2_bilan_energie(heure_a_100pct) -> None:
    _, releves, _ = heure_a_100pct
    r = releves[-1]
    entree = r["coeur.p_thermique_mw"] + r["primaire.q_pompes_mw"]
    sortie = r["turbine.p_meca_mw"] + r["condenseur.q_mer_mw"]
    assert abs(entree - sortie) / entree < 0.01


@pytest.mark.lent
def test_a3_conservation_masse(heure_a_100pct) -> None:
    c, _, m0 = heure_a_100pct
    assert c.mesures["vapeur.vda_qm_kg_s"] == 0.0 and c.mesures["vapeur.soupapes_qm_kg_s"] == 0.0
    derive_pct_h = abs(c.masse_eau_totale_kg() - m0) / m0 * 100.0   # sur 1 h simulée
    assert derive_pct_h < 0.1


# ============================================================================ A4
def test_a4_fermeture_are_gv1(rp100: Centrale) -> None:
    c = rp100
    for v in ("ARE1_GD", "ARE1_PD"):
        assert c.commande(v, "manu").ok
        assert c.commande(v, "position", 0.0).ok
    n0 = c.mesures["GV1.niveau_vrai_pct"]
    vap0 = c.mesures["GV1.qm_vapeur_kg_s"]
    debut = serie(c, 5.0, 0.1, "GV1.niveau_vrai_pct")
    assert max(r["GV1.niveau_vrai_pct"] for r in debut) > n0 + 0.1, "pas de gonflement initial"
    t_au = None
    for r in serie(c, 60.0, 0.1, "GV1.niveau_vrai_pct", "logique.au", "GV1.qm_vapeur_kg_s"):
        if r["logique.au"] and t_au is None:
            t_au = r["t_s"]
            assert r["GV1.niveau_vrai_pct"] < n0 - 20.0
        if t_au is None and r["t_s"] > 5.0:
            # plus d'eau froide à réchauffer : toute la chaleur du GV1 part en vapeur
            assert r["GV1.qm_vapeur_kg_s"] > vap0
    assert t_au is not None and 10.0 <= t_au <= 60.0, f"AU à {t_au} s"
    # V1 : « débit d'eau insuffisant » (écart vapeur/eau + niveau < 25,5 %) précède le niveau très bas
    assert set(c.logique.etat.au_causes) & {"niveau très bas GV1", "débit d'eau insuffisant GV1"}


# ============================================================================ A5-A7
@pytest.mark.lent
def test_a5_echelon_moins_10pct(rp100: Centrale) -> None:
    c = rp100
    assert c.commande("TURBINE", "consigne_mw", 0.9 * c.cfg.turbine.p_elec_nom_mw).ok
    r = serie(c, 300.0, 1.0, *[f"{g}.niveau_pct" for g in GV], "logique.au", "vapeur.soupapes_ouvertes")
    assert min(x["GV1.niveau_pct"] for x in r[:30]) < 49.0, "pas de tassement"
    for g in GV:
        assert r[-1][f"{g}.niveau_pct"] == pytest.approx(50.0, abs=2.0)
    assert all(x["logique.au"] == 0.0 and x["vapeur.soupapes_ouvertes"] == 0.0 for x in r)


@pytest.mark.lent
def test_a6_echelon_plus_10pct(rp100: Centrale) -> None:
    c = rp100
    p_nom = c.cfg.turbine.p_elec_nom_mw
    c.commande("TURBINE", "consigne_mw", 0.9 * p_nom)
    c.avancer(1200.0)
    n0 = c.mesures["GV1.niveau_pct"]
    assert c.commande("TURBINE", "consigne_mw", p_nom).ok
    r = serie(c, 300.0, 1.0, *[f"{g}.niveau_pct" for g in GV], "logique.au")
    assert max(x["GV1.niveau_pct"] for x in r[:30]) > n0 + 1.0, "pas de gonflement"
    for g in GV:
        assert r[-1][f"{g}.niveau_pct"] == pytest.approx(50.0, abs=2.0)
    assert all(x["logique.au"] == 0.0 for x in r)


def test_a7_ouverture_are_eau_froide(rp100: Centrale) -> None:
    c = rp100
    gd = c.vannes["ARE1_GD"]
    c.commande("ARE1_GD", "manu")
    assert c.commande("ARE1_GD", "position", 100.0 * (gd.etat.position + 0.15)).ok
    n0 = c.mesures["GV1.niveau_vrai_pct"]
    r = serie(c, 30.0, 0.1, "GV1.niveau_vrai_pct")
    assert min(x["GV1.niveau_vrai_pct"] for x in r[:20]) < n0 - 0.05, "pas de tassement initial"
    assert r[-1]["GV1.niveau_vrai_pct"] > n0 + 1.0


# ============================================================================ A8
@pytest.mark.lent
def test_a8_declenchement_turbine(rp100: Centrale) -> None:
    c = rp100
    assert c.commande("TURBINE", "declencher").ok
    r = serie(c, 600.0, 0.1, "logique.au", "gctc.ouverture_pct", "vapeur.soupapes_ouvertes",
              *[f"{g}.p_bar" for g in GV], *[f"{g}.niveau_pct" for g in GV])
    t_au = next(x["t_s"] for x in r if x["logique.au"])
    assert t_au < 1.0
    assert max(x["gctc.ouverture_pct"] for x in r) > 10.0
    assert all(x["vapeur.soupapes_ouvertes"] == 0.0 for x in r)
    assert c.logique.etat.isolement_are_au
    assert c.vannes["ARE1_GD"].etat.position == 0.0
    for g in GV:
        # contournement en mode Tmoy (C-8) : Tmoy ≈ T à vide + offset → P GV ≈ Psat(292–293 °C)
        assert 75.0 <= r[-1][f"{g}.p_bar"] <= 78.5
        assert 30.0 <= r[-1][f"{g}.niveau_pct"] <= 60.0


# ============================================================================ A9
@pytest.mark.lent
def test_a9_perte_des_crf(rp100: Centrale) -> None:
    c = rp100
    assert c.commande("CRF1", "arreter").ok and c.commande("CRF2", "arreter").ok
    c.avancer(1.0)
    assert not c.logique.etat.c9
    r = serie(c, 600.0, 1.0, "logique.au", "logique.turbine_declenchee", "gctc.ouverture_pct",
              "vapeur.vda_qm_kg_s", "condenseur.p_bar")
    assert any(x["logique.turbine_declenchee"] for x in r)
    assert any("vide condenseur" in e.texte for e in c.journal.evenements)
    assert c.logique.etat.au
    assert all(x["gctc.ouverture_pct"] == 0.0 for x in r), "GCT-c doit rester fermé sans C-9"
    assert max(x["vapeur.vda_qm_kg_s"] for x in r) > 0.0, "les VDA doivent prendre le relais"


# ============================================================================ A10
def test_a10_gctc_interdit_sans_c9(rp100: Centrale) -> None:
    c = rp100
    c.commande("CRF1", "arreter")
    c.commande("CRF2", "arreter")
    c.avancer(1.0)
    c.commande("GCTC_G1", "manu")
    rep = c.commande("GCTC_G1", "position", 50.0)
    assert not rep.ok and any("C-9" in t for t in rep.raisons)


def test_a10_app_interdite_sans_aspiration(rp100: Centrale) -> None:
    c = rp100
    for p in ("APP1", "APP2", "CEX1", "CEX2", "REP1", "REP2"):
        c.commande(p, "arreter")
    c.avancer(30.0)
    rep = c.commande("APP1", "demarrer")
    assert not rep.ok and any("aspiration" in t for t in rep.raisons)


def test_a10_couplage_hors_synchronisme(rp100: Centrale) -> None:
    c = rp100
    c.commande("TURBINE", "declencher")
    c.avancer(5.0)
    rep = c.commande("TURBINE", "coupler")
    assert not rep.ok and any("réarmée" in t for t in rep.raisons) and any("synchronisme" in t for t in rep.raisons)


def test_a10_rearmement_turbine_avec_p14(rp100: Centrale) -> None:
    c = rp100
    c.commande("ARE1_GD", "manu")
    c.commande("ARE1_GD", "position", 100.0)
    for _ in range(600):
        c.avancer(0.1)
        if c.logique.etat.p14:
            break
    assert c.logique.etat.p14 and c.turbine.etat.declenchee
    rep = c.commande("TURBINE", "rearmer")
    assert not rep.ok and any("P-14" in t for t in rep.raisons)
    assert c.logique.etat.isolement_are_complet


# ============================================================================ A11
def test_a11_sauvegarde_chargement_deterministe(rp100: Centrale) -> None:
    c = rp100
    c.commande("TURBINE", "consigne_mw", 1000.0)
    c.avancer(30.0)
    sauvegarde = json.loads(json.dumps(c.exporter()))     # passage par JSON comme dans l'interface
    c.avancer(60.0)
    attendu = dict(c.mesures)
    c2 = Centrale()
    c2.importer(sauvegarde)
    c2.avancer(60.0)
    assert c2.t_s == pytest.approx(c.t_s)
    for k, v in attendu.items():
        assert c2.mesures[k] == pytest.approx(v, rel=1e-9, abs=1e-9), k


# ============================================================================ A13
def test_a13_performance(rp100: Centrale) -> None:
    n = 3000
    t0 = time.perf_counter()
    for _ in range(n):
        rp100.pas()
    pas_par_s = n / (time.perf_counter() - t0)
    assert pas_par_s >= 600.0, f"{pas_par_s:.0f} pas/s : ×60 non tenu en temps réel"
