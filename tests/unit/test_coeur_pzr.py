"""U12-U13 : cœur (cinétique, résiduelle, grappes) et pressuriseur."""

from __future__ import annotations

import pytest

from sim.components.base import Sources
from sim.core_model.coeur import Coeur
from sim.plant import Centrale

DT = 0.1
T_FROID_C = 290.0     # eau la plus chaude du primaire (loin de la saturation)


def coeur_nominal(cfg) -> Coeur:
    return Coeur(cfg.coeur)


def test_u12_saut_prompt(cfg) -> None:
    """−500 pcm (bore) : la puissance chute d'un coup à β/(β − ρ) puis décroît lentement."""
    c = coeur_nominal(cfg)
    c.etat.bore_ppm += 500.0 / -cfg.coeur.alpha_bore_pcm_ppm
    c.avancer(DT, cfg.coeur.t_mod_ref_c)
    beta = cfg.coeur.beta_pcm
    assert c.etat.n == pytest.approx(beta / (beta + 500.0), rel=0.01)


def test_u12_reactivite_nulle_au_nominal(cfg) -> None:
    c = coeur_nominal(cfg)
    assert c.reactivite_pcm(cfg.coeur.t_mod_ref_c) == pytest.approx(0.0, abs=1e-9)
    for _ in range(100):
        c.avancer(DT, cfg.coeur.t_mod_ref_c)
    assert c.etat.n == pytest.approx(1.0, abs=1e-6)
    assert c.puissance_thermique_kw == pytest.approx(cfg.coeur.p_nom_mw * 1e3, rel=1e-3)


@pytest.mark.parametrize("t_s, attendu_pct", [(100.0, 2.28), (1000.0, 1.36), (3600.0, 1.01)])
def test_u12_puissance_residuelle(cfg, t_s: float, attendu_pct: float) -> None:
    """Après chute des grappes : puissance ≈ Way-Wigner (spec : ~1 % à 1 h). Avant ~100 s s'y ajoutent
    les neutrons retardés et la chaleur stockée dans le combustible."""
    c = coeur_nominal(cfg)
    c.chute_grappes()
    for _ in range(round(t_s / DT)):
        c.bouger_grappes(DT, 0.0, False, False)
        c.avancer(DT, cfg.coeur.t_mod_ref_c)
    pct = 100.0 * c.puissance_thermique_kw / (cfg.coeur.p_nom_mw * 1e3)
    assert pct == pytest.approx(attendu_pct, rel=0.1)


def test_u12_chute_grappes(cfg) -> None:
    c = coeur_nominal(cfg)
    c.chute_grappes()
    for _ in range(round(cfg.coeur.grappes.temps_chute_s / DT) + 1):
        c.bouger_grappes(DT, 0.0, False, False)
    assert c.etat.z_pas == 0.0 and c.etat.g_pas == 0.0 and c.etat.arret_insere == 1.0
    g = cfg.coeur.grappes
    rho = c.rho_grappes_pcm()
    assert rho == pytest.approx(g.regulation_pcm + g.compensation_pcm + g.arret_pcm - c.rho_grappes_nom)


def test_u12_retrait_bloque(cfg) -> None:
    c = coeur_nominal(cfg)
    c.etat.auto = False
    c.etat.consigne_manu_pas = cfg.coeur.grappes.pas_max
    z0 = c.etat.z_pas
    c.bouger_grappes(DT, 0.0, retrait_interdit=True, retrait_auto_interdit=False)
    assert c.etat.z_pas == z0


def test_u13_pzr_chaufferettes_et_aspersion(rp100: Centrale) -> None:
    pz, tab = rp100.pzr, rp100.table
    m0, p0 = pz.vol.etat.m_kg, pz.p_bar
    pz.chauffe_tor.etat.auto = False
    pz.chauffe_tor.etat.demande_manu = 1.0
    for _ in range(600):
        pz.avancer(DT, 0.0, 0.0, 0.0, 0.0, lambda _: Sources(), T_FROID_C)
    assert pz.p_bar > p0 + 0.5                       # chauffe → la pression monte
    assert pz.vol.etat.m_kg == pytest.approx(m0)     # pas de débit : masse conservée
    p1 = pz.p_bar
    pz.chauffe_tor.etat.demande_manu = 0.0
    h_froide = tab.h_primaire_kj_kg(290.0)
    for _ in range(100):
        pz.avancer(DT, -40.0, 0.0, 40.0, h_froide, lambda _: Sources(), T_FROID_C)   # aspersion pleine (~2 × 95 m³/h), même débit ressorti
    assert pz.p_bar < p1 - 0.5                       # aspersion → la pression baisse
