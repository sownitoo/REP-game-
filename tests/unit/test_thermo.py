"""U1-U2 : tables eau/vapeur et flash (v, u) → P."""

from __future__ import annotations

import math

import CoolProp.CoolProp as CP
import pytest
from CoolProp import AbstractState

from sim.thermo.tables import TableEau

PRESSIONS_BAR = [0.02, 0.05, 0.14, 0.5, 1.0, 5.0, 20.0, 45.0, 63.0, 76.6, 100.0, 155.0, 200.0]


@pytest.mark.parametrize("p_bar", PRESSIONS_BAR)
def test_u1_tables_vs_coolprop(table: TableEau, p_bar: float) -> None:
    ref = AbstractState("IF97", "Water")
    s = table.sat(p_bar)
    ref.update(CP.PQ_INPUTS, p_bar * 1e5, 0.0)
    assert s.t_c == pytest.approx(ref.T() - 273.15, rel=5e-4)
    assert s.hf_kj_kg == pytest.approx(ref.hmass() / 1e3, rel=5e-4)
    assert s.rho_l_kg_m3 == pytest.approx(ref.rhomass(), rel=5e-4)
    ref.update(CP.PQ_INPUTS, p_bar * 1e5, 1.0)
    assert s.hg_kj_kg == pytest.approx(ref.hmass() / 1e3, rel=5e-4)
    assert s.rho_v_kg_m3 == pytest.approx(ref.rhomass(), rel=5e-4)


def test_u1_point_nominal_gv(table: TableEau) -> None:
    """63 bar → Tsat 278,8 °C ; Psat(292 °C) = 76,6 bar (valeurs de la proposition V0)."""
    assert table.tsat_c(63.0) == pytest.approx(278.8, abs=0.05)
    assert table.psat_bar(292.0) == pytest.approx(76.6, abs=0.05)


@pytest.mark.parametrize("p_bar", [0.1, 1.0, 10.0, 63.0, 150.0])
@pytest.mark.parametrize("titre", [0.02, 0.3, 0.9])
def test_u2_flash_aller_retour(table: TableEau, cfg, p_bar: float, titre: float) -> None:
    s = table.sat(p_bar)
    v = s.vf_m3_kg + titre * (s.vg_m3_kg - s.vf_m3_kg)
    u = s.uf_kj_kg + titre * (s.ug_kj_kg - s.uf_kj_kg)
    f = cfg.numerique.flash
    for depart in (p_bar * 0.5, p_bar * 1.7):
        p, x = table.flash_vu(v, u, depart, f.tolerance_lnp, f.pas_derivee_lnp, f.iterations_max)
        assert p == pytest.approx(p_bar, abs=0.01)
        assert x == pytest.approx(titre, abs=1e-4)


def test_u2_liquide_inverse(table: TableEau) -> None:
    for t in (20.0, 52.5, 180.0, 224.0, 300.0):
        assert table.t_liq_c(table.h_liq_kj_kg(t)) == pytest.approx(t, abs=0.01)
    assert not math.isnan(table.dhf_dp_kj_kg_bar(63.0))
