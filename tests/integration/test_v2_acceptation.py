"""Tests d'acceptation V2 : RCV + REA + RRA + RRI + SEC + accumulateurs + états standards.

Spec §10, V2 : « Scénario S2 (RP → AN/RRA) faisable de bout en bout ».
"""

from __future__ import annotations

import pytest

from sim.logic import etats
from sim.plant import Centrale
from tests.conftest import serie


# ============================================================================ C1
@pytest.mark.lent
def test_c1_rcv_rri_stables_a_100pct(rp100: Centrale) -> None:
    c = rp100
    r = serie(c, 3600.0, 60.0, "primaire.bore_ppm", "rcv.vct_niveau_pct", "rri.t_c", "rcv.charge_m3h", "pzr.niveau_pct")
    assert all(x["primaire.bore_ppm"] == pytest.approx(1000.0, abs=1.0) for x in r)
    assert all(30.0 < x["rcv.vct_niveau_pct"] < 70.0 for x in r)
    assert max(x["rri.t_c"] for x in r) - min(x["rri.t_c"] for x in r) < 1.0
    assert r[-1]["rcv.charge_m3h"] == pytest.approx(12.5, abs=1.0)        # 17 − 4,5 (joints)
    assert c.alarmes.liste() == []
    assert etats.code_etat(c) == "RP"


# ============================================================================ C2
def test_c2_borication_puis_dilution(rp100: Centrale) -> None:
    c = rp100
    c0 = c.mesures["primaire.bore_ppm"]
    assert c.commande("REA", "borication", 2.0).ok          # acide à l'aspiration des pompes de charge
    c.avancer(1800.0)
    c1 = c.mesures["primaire.bore_ppm"]
    assert c1 > c0 + 20.0, "la borication fait monter le bore du primaire"
    assert c.rea.etat.mode == "auto", "retour en automatique quand le volume est injecté"
    assert c.mesures["coeur.rho_bore_pcm"] < 0.0
    assert c.commande("REA", "dilution", 4.0).ok            # eau à la VCT : effet retardé par la VCT
    c.avancer(3600.0)
    assert c.mesures["primaire.bore_ppm"] < c1 - 5.0


# ============================================================================ C3
def test_c3_verrous_v2(rp100: Centrale) -> None:
    c = rp100

    def refus(cible: str, action: str, motif: str) -> None:
        rep = c.commande(cible, action)
        assert not rep.ok and any(motif in t for t in rep.raisons), (cible, action, rep.raisons)

    refus("RRA_ASP1A", "ouvrir", "Pression primaire < 30 bar")
    refus("ACC1_ISOL", "fermer", "P-11")
    refus("RPR", "bloquer_is", "P-11")
    refus("RRA_P1", "demarrer", "Aspiration du train ouverte")
    assert c.commande("RCV_LCV459", "fermer").ok
    c.avancer(10.0)
    refus("RCV_LCV459", "ouvrir", "Aucune vanne d'orifice ouverte")
    assert c.commande("PP1", "arreter").ok
    assert c.commande("RRI_P1", "arreter").ok
    c.avancer(5.0)
    refus("PP1", "demarrer", "RRI en service")


# ============================================================================ C4
def test_c4_vct_appoint_auto_puis_ptr(rp100: Centrale) -> None:
    c = rp100
    assert c.commande("RCV_ORIF1", "fermer").ok           # plus de décharge, charge maxi : la VCT se vide
    assert c.commande("RCV_CHARGE", "manu").ok
    assert c.commande("RCV_CHARGE", "position", 100.0).ok
    r = serie(c, 1200.0, 10.0, "rcv.vct_niveau_pct", "rea.q_eau_m3h")
    assert max(x["rea.q_eau_m3h"] for x in r) > 0.0, "appoint automatique REA sur niveau VCT bas"
    assert any("basculée sur la PTR" in e.texte for e in c.journal.evenements), "bascule au niveau très bas"
    # retour manuel : l'aspiration reste sur la PTR une fois la VCT remontée
    assert c.rcv.asp_ptr.etat.position == 1.0 and c.rcv.asp_vct.etat.position == 0.0
    assert c.mesures["rcv.bore_charge_ppm"] == pytest.approx(c.cfg.rcv.ptr.bore_ppm, abs=1.0)


# ============================================================================ C5
def test_c5_accumulateurs() -> None:
    c = Centrale()
    acc = c.accus
    acc.avancer(1.0, 155.0)
    assert acc.qm_total_kg_s == 0.0
    acc.avancer(1.0, 30.0)
    assert acc.qm_total_kg_s > 0.0, "sous 42 bar, les accumulateurs non isolés injectent"
    for v in acc.isolement:
        v.etat.position = 0.0
    acc.avancer(1.0, 30.0)
    assert acc.qm_total_kg_s == 0.0


# ============================================================================ C6
def test_c6_rra_ferme_au_dessus_de_41_bar(rp100: Centrale) -> None:
    c = rp100
    v = c.vannes["RRA_ASP1A"]
    v.etat.position = v.etat.demande_manu = 1.0           # ouverte par erreur (forçage du test)
    c.avancer(70.0)
    assert v.etat.position == 0.0
    assert c.logique.etat.rra_isole_auto
    assert any(a["id"] == "RRA_FERMETURE" for a in c.alarmes.liste())


# ============================================================================ C7
def test_c7_perte_rri(rp100: Centrale) -> None:
    c = rp100
    assert c.commande("RRI_P1", "arreter").ok
    c.avancer(20.0)
    assert c.logique.etat.perte_rri
    assert any(a["id"] == "PERTE_RRI" for a in c.alarmes.liste())
    c.avancer(c.cfg.rri.delai_pompes_primaires_s + 20.0)
    assert all(not p.etat.en_marche for p in c.primaire.pompes), "pompes primaires en défaut sans RRI"
    assert c.logique.etat.au                                # débit primaire bas


# ============================================================================ C8
def test_c8_etats_et_checklist(rp100: Centrale) -> None:
    c = rp100
    assert etats.code_etat(c) == "RP"
    c.commande("RPR", "declencher_au")
    c.avancer(30.0)
    ui = etats.etat_ui(c)
    assert ui["code"] == "AN/GV" and ui["vise"] == "AN/RRA"
    textes = {p["texte"].split(" (")[0]: p["ok"] for p in ui["checklist"]}
    assert textes["Accumulateurs isolés"] is False
    assert textes["RRA en service"] is False


# ============================================================================ S2
@pytest.mark.lent
def test_s2_rp_vers_an_rra_de_bout_en_bout(rp100: Centrale) -> None:
    """Fiche de conduite de S2 jouée pas à pas ; contrôle des limites tout du long."""
    c, tab = rp100, rp100.table

    def ok(cible: str, action: str, valeur: float | None = None) -> None:
        rep = c.commande(cible, action, valeur)
        assert rep.ok, (cible, action, valeur, rep.raisons)

    ok("RPR", "declencher_au")
    c.avancer(600.0)
    assert etats.code_etat(c) == "AN/GV"
    ok("REG_GCTC", "mode_pression")
    ok("REA", "borication", 12.0)
    ok("PP1", "arreter")
    ok("PP4", "arreter")
    t0, tmoy0 = c.t_s, c.primaire.tmoy_c
    is_bloquee = accus_isoles = rra = False
    vitesse_max = marge_sat_min = 1e9
    while etats.code_etat(c) == "AN/GV" and c.t_s < 8 * 3600:
        if not rra:
            t_visee = tmoy0 - 30.0 * (c.t_s - t0) / 3600
            ok("REG_GCTC", "consigne", max(tab.psat_bar(t_visee - 5.0), 1.0))
            ok("REG_P_PZR", "consigne", max(tab.psat_bar(c.primaire.tmoy_c + 45.0), 24.0))
        if not is_bloquee and c.logique.etat.p11:
            ok("RPR", "bloquer_is")
            is_bloquee = True
        if is_bloquee and not accus_isoles and c.pzr.p_bar < 100.0:
            for b in c.boucles:
                ok(f"ACC{b}_ISOL", "fermer")
            accus_isoles = True
        if not rra and c.pzr.p_bar < 29.0 and c.primaire.tmoy_c < 177.0:
            for v in ("RRA_ASP1A", "RRA_ASP1B", "RRA_ASP2A", "RRA_ASP2B"):
                ok(v, "ouvrir")
            c.avancer(70.0)
            for p in ("RRA_P1", "RRA_P2", "RRI_P2", "SEC_P2"):
                ok(p, "demarrer")
            rra = True
        c.avancer(300.0)
        m = c.mesures
        assert m["logique.is"] == 0.0, "pas d'IS pendant la descente"
        assert m["accu.qm_kg_s"] == 0.0, "pas d'injection des accumulateurs"
        vitesse_max = min(vitesse_max, -m["primaire.vitesse_refroidissement_c_h"])
        marge_sat_min = min(marge_sat_min, m["cuve.marge_saturation_c"])
    assert etats.code_etat(c) == "AN/RRA", f"AN/RRA non atteint ({c.t_s / 3600:.1f} h)"
    assert c.t_s < 6 * 3600
    assert -vitesse_max < c.cfg.logique.etats.vitesse_refroidissement_max_c_h
    assert marge_sat_min > 20.0
    m = c.mesures
    assert m["primaire.bore_ppm"] >= m["coeur.bore_arret_froid_ppm"]
    c.avancer(1800.0)
    assert c.mesures["rri.t_c"] < 45.0
    assert c.mesures["primaire.vitesse_refroidissement_c_h"] > 5.0, "le RRA refroidit"
