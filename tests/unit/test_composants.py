"""U3-U5, U7, U8 : pompe, vannes, soupape, volume diphasique, régulateur PI."""

from __future__ import annotations

import pytest

from sim.components.base import Sources
from sim.components.pid import RegulateurPI
from sim.components.pump import Pompe
from sim.components.relief import Soupape
from sim.components.valve import Vanne
from sim.components.volume2phase import Volume2Phase
from sim.config import PompeCfg, VanneCfg
from sim.units import hauteur_vers_bar

DT = 0.1


# ----------------------------------------------------------------------------- U3 pompe
def test_u3_courbe_pompe(cfg) -> None:
    p = Pompe("CEX1", cfg.composants["CEX1"])
    c = p.cfg
    p.etat.vitesse = 1.0
    dp0, k = p.hydraulique(1000.0)
    assert dp0 == pytest.approx(hauteur_vers_bar(c.h0_m, 1000.0))
    # le point nominal est sur la courbe : ΔP0 − k·Q_nom² = ρ·g·H_nom
    assert dp0 - k * c.q_nom_m3h ** 2 == pytest.approx(hauteur_vers_bar(c.h_nom_m, 1000.0))
    # similitude : ΔP0 ∝ s²
    p.etat.vitesse = 0.5
    assert p.hydraulique(1000.0)[0] == pytest.approx(dp0 / 4)


def test_u3_demarrage_et_ralentissement(cfg) -> None:
    p = Pompe("CEX1", cfg.composants["CEX1"])
    p.demarrer()
    for _ in range(round(p.cfg.temps_demarrage_s / DT) + 1):
        p.avancer(DT, Sources())
    assert p.etat.vitesse == pytest.approx(1.0)
    p.arreter()
    p.avancer(DT, Sources())
    assert 0.0 < p.etat.vitesse < 1.0          # ralentissement progressif, pas d'arrêt instantané


def test_u3_perte_de_tension_declenche(cfg) -> None:
    p = Pompe("CEX1", cfg.composants["CEX1"])
    p.demarrer()
    p.avancer(DT, Sources(electricite_ok=False))
    assert not p.etat.en_marche and "tension" in p.etat.defaut


# ----------------------------------------------------------------------------- U4 vannes
def test_u4_mov_temps_de_course(cfg) -> None:
    v = Vanne("ARE1_ISOL", cfg.composants["ARE1_ISOL"], 0.0)
    v.demander(1.0)
    n = round(v.cfg.temps_course_s / DT)
    for _ in range(n - 1):
        v.avancer(DT, Sources())
    assert v.etat.position < 1.0
    v.avancer(DT, Sources())
    v.avancer(DT, Sources())
    assert v.etat.position == pytest.approx(1.0)


def test_u4_mov_reste_en_place_sans_tension(cfg) -> None:
    v = Vanne("ARE1_ISOL", cfg.composants["ARE1_ISOL"], 0.4)
    v.demander(1.0)
    v.avancer(DT, Sources(electricite_ok=False))
    assert v.etat.position == pytest.approx(0.4)


def test_u4_aov_repli_apres_reserve(cfg) -> None:
    v = Vanne("VIV1", cfg.composants["VIV1"], 1.0)       # repli fermée, réserve 15 min
    reserve_s = v.cfg.reserve_air_min * 60
    for _ in range(round(reserve_s / DT) - 10):
        v.avancer(DT, Sources(air_ok=False))
    assert v.etat.position == pytest.approx(1.0)          # tient tant que la réserve dure
    for _ in range(round(v.cfg.temps_course_s / DT) + 20):
        v.avancer(DT, Sources(air_ok=False))
    assert v.etat.position == pytest.approx(0.0)


def test_u4_ordre_automatique_prioritaire(cfg) -> None:
    v = Vanne("ARE1_GD", cfg.composants["ARE1_GD"], 0.5)
    v.etat.demande_auto = 0.8
    v.fixer_ordre(0.0, "test")
    for _ in range(100):
        v.avancer(DT, Sources())
    assert v.etat.position == pytest.approx(0.0)
    v.fixer_ordre(None)
    for _ in range(100):
        v.avancer(DT, Sources())
    assert v.etat.position == pytest.approx(0.8)


# ----------------------------------------------------------------------------- U5 soupape
def test_u5_soupape_hysteresis() -> None:
    s = Soupape("S", "VVP", tarage_bar=82.0, capacite_kg_s=100.0, fermeture_pct=4.0)
    assert not s.mettre_a_jour(81.9) and s.debit_kg_s(81.9) == 0.0
    assert s.mettre_a_jour(82.0) and s.etat.ouverte
    assert s.debit_kg_s(82.0) == pytest.approx(100.0)
    s.mettre_a_jour(80.0)                                  # 80 > 82 × 0,96 = 78,72 : reste ouverte
    assert s.etat.ouverte
    s.mettre_a_jour(78.7)
    assert not s.etat.ouverte and s.etat.sollicitations == 1


# ----------------------------------------------------------------------------- U7 volume diphasique
def test_u7_volume_ferme_chauffe(table, cfg) -> None:
    v = Volume2Phase(165.0, table, cfg.numerique.flash)
    v.initialiser(63.0, 42000.0)
    m0, u0 = v.etat.m_kg, v.etat.u_kj
    q_kw = 10000.0
    for _ in range(600):
        v.integrer(DT, 0.0, q_kw, 0.0, 0.0)
    assert v.etat.m_kg == pytest.approx(m0, rel=1e-12)                # masse conservée
    assert v.etat.u_kj == pytest.approx(u0 + q_kw * 60.0, rel=1e-12)  # énergie conservée
    assert v.p_bar > 63.0
    assert v.sat.t_c == pytest.approx(table.tsat_c(v.p_bar), abs=1e-6)  # toujours à saturation


# ----------------------------------------------------------------------------- U8 PI
def test_u8_pi_sans_a_coup() -> None:
    pi = RegulateurPI("PI", kp=0.5, ti_s=10.0, sortie_min=0.0, sortie_max=1.0, sortie_initiale=0.3)
    pi.etat.auto = False
    pi.etat.sortie_manu = 0.6
    assert pi.calculer(0.2, DT) == pytest.approx(0.6)
    pi.etat.auto = True
    assert pi.calculer(0.2, DT) == pytest.approx(0.6, abs=0.01)       # retour en auto sans à-coup


def test_u8_pi_anti_emballement() -> None:
    pi = RegulateurPI("PI", kp=1.0, ti_s=1.0, sortie_min=0.0, sortie_max=1.0, sortie_initiale=0.5)
    for _ in range(1000):
        pi.calculer(10.0, DT)                                         # saturation haute prolongée
    assert pi.etat.sortie == 1.0
    for _ in range(3):
        pi.calculer(-0.5, DT)
    assert pi.etat.sortie < 1.0                                       # décroche tout de suite
