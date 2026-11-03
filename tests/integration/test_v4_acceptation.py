"""Tests d'acceptation V4 : RIS + EAS + enceinte + brèches + signaux de sauvegarde.

Spec §10, V4 : « S7 à S11 jouables ».
"""

from __future__ import annotations

import pytest

from sim.plant import Centrale
from sim.scenarios.chargement import centrale_scenario
from tests.conftest import serie

SEUIL_DEBIT_M3H = 1.0


def premier(r: list[dict[str, float]], cle: str, seuil: float) -> float:
    """Premier instant où la mesure dépasse le seuil (inf si jamais)."""
    return next((x["t_s"] for x in r if x[cle] > seuil), float("inf"))


def test_e1_situation_normale(rp100: Centrale) -> None:
    c = rp100
    c.avancer(10.0)
    m = c.mesures
    assert abs(m["enceinte.p_rel_bar"]) < 0.01 and m["prt.disque_rompu"] == 0.0
    assert m["ris.qm_kg_s"] == 0.0 and m["ris.q_eas_m3h"] == 0.0 and m["breche.primaire_kg_s"] == 0.0
    assert m["primaire.sature"] == 0.0 and m["primaire.vide_m3"] == 0.0 and m["cuve.niveau_pct"] == 100.0
    assert not c.logique.etat.is_actif and not c.logique.etat.isolement_vapeur
    assert c.alarmes.liste() == []


@pytest.mark.lent
def test_e2_s7_petite_breche_injection_et_ordre() -> None:
    c = centrale_scenario("s7_petite_breche_primaire")
    r = serie(c, 900.0, 5.0, "ris.q_hp_m3h", "ris.q_mp_m3h", "pzr.p_bar", "enceinte.p_rel_bar",
              "enceinte.puisard_m3", "cuve.niveau_pct")
    lg = c.logique.etat
    assert lg.au and lg.is_actif and any("PZR" in x for x in lg.is_causes)
    t_hp, t_mp = premier(r, "ris.q_hp_m3h", SEUIL_DEBIT_M3H), premier(r, "ris.q_mp_m3h", SEUIL_DEBIT_M3H)
    assert t_hp < t_mp < float("inf"), "HP (charge par la BIT) d'abord, MP seulement sous 106 bar"
    p_mp = next(x["pzr.p_bar"] for x in r if x["t_s"] == t_mp)
    assert p_mp < c.cfg.ris.mp.dp0_bar + 1.0
    fin = r[-60:]                                             # 5 dernières minutes : plateau
    assert all(60.0 < x["pzr.p_bar"] < 100.0 for x in fin), "pression stabilisée par l'injection et les GV"
    assert min(x["cuve.niveau_pct"] for x in r) > 90.0, "le cœur reste noyé"
    assert r[-1]["enceinte.puisard_m3"] > 20.0 and r[-1]["enceinte.p_rel_bar"] > 0.1
    assert not c.pzr.etat.hors_domaine


def test_e3_recirculation(rp100: Centrale) -> None:
    c = rp100
    assert c.commande("RPR", "declencher_is").ok
    c.avancer(30.0)
    assert all(p.etat.en_marche for p in c.ris.pompes_bp), "pompes RRA démarrées en BP par l'IS (PTR pleine)"
    c.rcv.etat.ptr_m3 = 0.47 * c.cfg.rcv.ptr.volume_m3
    c.avancer(2.0)
    assert all(not p.etat.en_marche for p in c.ris.pompes_bp), "PTR < 48 % : arrêt des pompes RRA"
    assert any("PTR à 48 %" in e.texte for e in c.journal.evenements)
    rep = c.commande("RIS_PUISARD1", "ouvrir")
    assert not rep.ok, "puisards vides : ouverture interdite"
    c.enceinte.etat.puisard_m3 = 400.0
    for v in ("RIS_PUISARD1", "RIS_PUISARD2"):
        assert c.commande(v, "ouvrir").ok
    c.avancer(60.0)
    assert c.ris.recirculation
    assert c.commande("RRA_P1", "demarrer").ok, "recirculation : les pompes RRA aspirent aux puisards"
    c.avancer(10.0)
    assert c.ris.pompes_bp[0].etat.en_marche


@pytest.mark.lent
def test_e4_s8_porv_bloquee_tmi_et_prt() -> None:
    c = centrale_scenario("s8_porv_bloquee")
    r = serie(c, 700.0, 5.0, "pzr.niveau_pct", "primaire.sature", "cuve.niveau_pct", "prt.p_bar", "prt.disque_rompu")
    assert c.logique.etat.is_actif
    t_sat = premier(r, "primaire.sature", 0.5)
    assert t_sat < 400.0, "la PORV ouverte amène le primaire à saturation"
    n_sat = next(x["pzr.niveau_pct"] for x in r if x["t_s"] == t_sat)
    n_min = min(x["pzr.niveau_pct"] for x in r if x["t_s"] < t_sat)
    assert n_sat > n_min + 10.0, "TMI : le niveau PZR remonte pendant que le primaire bout"
    assert min(x["cuve.niveau_pct"] for x in r) < 100.0
    assert r[-1]["prt.disque_rompu"] == 1.0, "la PRT monte à 8 bar et son disque crève"
    assert any("Disque de rupture" in e.texte for e in c.journal.evenements)
    assert c.commande("PZR_ISOL1", "fermer").ok
    c.avancer(30.0)
    assert c.mesures["pzr.porv_qm_kg_s"] < 0.1 or c.vannes["PZR_PORV2"].etat.position > 0.0


@pytest.mark.lent
def test_e5_s9_rtgv_activite_et_isolement() -> None:
    c = centrale_scenario("s9_rtgv")
    r = serie(c, 150.0, 5.0, "GV1.activite", "GV2.activite", "breche.rtgv_kg_s")
    seuil = c.cfg.breches.activite_alarme
    assert premier(r, "GV1.activite", seuil) < 90.0, "l'activité signe le GV affecté"
    assert max(x["GV2.activite"] for x in r) == 0.0
    assert 30.0 < r[-1]["breche.rtgv_kg_s"] < 60.0
    assert any(a["id"] == "ACTIVITE_GV" for a in c.alarmes.liste())
    serie(c, 450.0, 30.0, "pzr.p_bar")
    assert c.logique.etat.is_actif, "IS sur pression PZR basse"
    for rep, action, val in (("VIV1", "fermer", None), ("VIV1_BP", "fermer", None), ("ASG1", "manu", None),
                             ("ASG1", "position", 0.0)):
        assert c.commande(rep, action, val).ok
    c.avancer(30.0)
    assert c.vannes["VIV1"].etat.position == 0.0 and c.vannes["ASG1"].etat.position == 0.0


@pytest.mark.lent
def test_e6_s10_breche_vapeur_isolement_et_reactivite() -> None:
    c = centrale_scenario("s10_breche_vapeur")
    r = serie(c, 120.0, 2.0, "enceinte.p_rel_bar", "coeur.rho_pcm", "primaire.tmoy_c")
    lg = c.logique.etat
    assert lg.is_actif and any("enceinte" in x for x in lg.is_causes), "IS sur pression enceinte haute"
    assert lg.isolement_vapeur, "isolement vapeur (débit vapeur haut + pression vapeur basse)"
    assert all(c.vannes[f"VIV{b}"].etat.position == 0.0 for b in c.boucles)
    rho_min = min(x["coeur.rho_pcm"] for x in r)
    r2 = serie(c, 900.0, 30.0, "coeur.rho_pcm", "primaire.tmoy_c", "enceinte.p_rel_bar")
    assert r2[-1]["primaire.tmoy_c"] < r[0]["primaire.tmoy_c"] - 40.0, "surrefroidissement"
    assert max(x["coeur.rho_pcm"] for x in r2) > rho_min + 2000.0, "retour de réactivité avec le refroidissement"
    assert max(x["enceinte.p_rel_bar"] for x in r + r2) > c.cfg.logique.injection_securite.p_enceinte_haute_bar_rel
    assert c.commande("ASG1", "manu").ok and c.commande("ASG1", "position", 0.0).ok
    serie(c, 300.0, 30.0, "GV1.p_bar")
    assert c.mesures["breche.vapeur_kg_s"] < 5.0, "GV1 vidé et privé d'eau : la brèche se tarit"
    assert 0.5 < c.mesures["GV1.p_bar"] < 10.0 and not c.pzr.etat.hors_domaine


def test_e7_s11_perte_rri_pompes_primaires() -> None:
    c = centrale_scenario("s11_perte_rri")
    c.avancer(30.5)
    assert all(not p.etat.en_marche for p in c.rri.pompes)
    assert not c.commande("RRI_P1", "demarrer").ok, "circuit RRI vidé : pompes impossibles à relancer"
    c.avancer(100.0)
    assert all(p.etat.en_marche for p in c.primaire.pompes), "les PP tiennent ~2 min sans RRI"
    c.avancer(30.0)
    assert all(not p.etat.en_marche and p.etat.defaut for p in c.primaire.pompes), "PP en défaut après 2 min"
    assert c.logique.etat.au


def test_e7b_s11_arret_a_temps() -> None:
    c = centrale_scenario("s11_perte_rri")
    c.avancer(60.0)
    assert c.commande("RPR", "declencher_au").ok
    c.avancer(2.0)
    for p in c.primaire.pompes:
        assert c.commande(p.id, "arreter").ok
    c.avancer(180.0)
    assert all(not p.etat.defaut for p in c.primaire.pompes), "arrêtées à temps : pompes intactes"


def test_e8_pupitre_formateur(rp100: Centrale) -> None:
    c = rp100
    assert c.commande("FORMATEUR", "breche_primaire", 2.0).ok
    c.avancer(5.0)
    assert 15.0 < c.mesures["breche.primaire_kg_s"] < 30.0, "∅ 2 cm : ~20 kg/s à 155 bar"
    assert c.mesures["enceinte.puisard_m3"] > 0.0
    assert c.commande("FORMATEUR", "supprimer_breches").ok
    c.avancer(1.0)
    assert c.mesures["breche.primaire_kg_s"] == 0.0


@pytest.mark.lent
def test_e9_primaire_sature_pression_de_saturation() -> None:
    """Primaire saturé : P = Psat(eau la plus chaude) ; grosse brèche → dépressurisation, accumulateurs, cuve renoyée."""
    c = centrale_scenario("s0_bac_a_sable_100")
    assert c.commande("FORMATEUR", "breche_primaire", 15.0).ok
    r = serie(c, 1500.0, 10.0, "primaire.sature", "pzr.p_bar", "accu.qm_kg_s", "cuve.niveau_pct")
    t_sat = premier(r, "primaire.sature", 0.5)
    assert t_sat < 120.0
    assert c.pzr.etat.sature
    assert c.pzr.p_bar == pytest.approx(c.table.psat_bar(c.primaire.t_chaud_c), abs=0.5)
    assert premier(r, "accu.qm_kg_s", 1.0) < 1500.0, "dépressurisation sous 42 bar : les accumulateurs injectent"
    assert min(x["cuve.niveau_pct"] for x in r) > 15.0 and not c.pzr.etat.hors_domaine
