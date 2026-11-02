"""U6 : solveur de réseau hydraulique."""

from __future__ import annotations

import math

import pytest

from sim.core.network import Branche, Reseau
from sim.units import S_PAR_H

RHO = 1000.0


class PompeTest:
    def __init__(self, dp0_bar: float, k: float) -> None:
        self.dp0, self.k = dp0_bar, k

    def hydraulique(self, rho_kg_m3: float) -> tuple[float, float]:
        return self.dp0, self.k


class VanneTest:
    def __init__(self, kv: float, anti_retour: bool = False) -> None:
        self._kv, self.anti_retour = kv, anti_retour

    def kv(self) -> float:
        return self._kv


def reseau_deux_pompes(cfg, kv_aval: float) -> Reseau:
    p1, p2 = PompeTest(10.0, 1e-6), PompeTest(10.0, 1e-6)
    branches = [
        Branche("P1", "A", "N", [p1, VanneTest(1e6, anti_retour=True)], RHO),
        Branche("P2", "A", "N", [p2, VanneTest(1e6, anti_retour=True)], RHO),
        Branche("R", "N", "B", [VanneTest(kv_aval)], RHO),
    ]
    r = Reseau("test", ["A", "B"], ["N"], branches, [], cfg.numerique.reseau, 1.0)
    r.fixer_frontiere("A", 1.0)
    r.fixer_frontiere("B", 1.0)
    return r


def test_u6_deux_pompes_en_parallele(cfg) -> None:
    kv = 3000.0
    r = reseau_deux_pompes(cfg, kv)
    r.resoudre()
    # solution analytique : 2·√((ΔP0 − x)/k') = Kv·√x  avec k' = k + d/Kv_clapet²
    k_eff = 1e-6 + 1.0 / 1e6 ** 2
    x = 4 * 10.0 / k_eff / (kv ** 2 + 4 / k_eff)
    q_total_m3h = kv * math.sqrt(x)
    assert r.p("N") == pytest.approx(1.0 + x, rel=1e-4)
    assert r.branche["R"].qm_kg_s == pytest.approx(q_total_m3h * RHO / S_PAR_H, rel=1e-3)
    bilan = r.branche["P1"].qm_kg_s + r.branche["P2"].qm_kg_s - r.branche["R"].qm_kg_s
    assert abs(bilan) < 1e-5


def test_u6_refoulement_ferme_converge(cfg) -> None:
    """Pompe en butée (vanne aval fermée) : le nœud monte à la pression à débit nul, débit ≈ 0."""
    r = reseau_deux_pompes(cfg, 0.0)
    r.resoudre()
    assert r.etat.residu_kg_s < cfg.numerique.reseau.tolerance_kg_s
    assert r.p("N") == pytest.approx(11.0, abs=0.05)
    assert abs(r.branche["P1"].qm_kg_s) < 1e-3


def test_u6_clapet_bloque_le_retour(cfg) -> None:
    """Pompe arrêtée en parallèle d'une pompe en marche : son clapet empêche le retour."""
    r = reseau_deux_pompes(cfg, 3000.0)
    r.branche["P2"].elements[0].dp0 = 0.0
    r.resoudre()
    assert r.branche["P2"].qm_kg_s <= 1e-3
    assert r.branche["P1"].qm_kg_s > 1.0


def test_u6_reseau_centrale_bilan_aux_noeuds(rp100) -> None:
    pe = rp100.poste_eau
    q = pe.etat.qm_branches_kg_s
    inj = pe.etat.qm_reprise_kg_s
    assert abs(q["L_CEX1"] + q["L_CEX2"] - q["L_RECIRC"] - q["L_REJET"] - q["L_ABP"]) < 1e-3
    assert abs(q["L_ABP"] + inj - q["L_APP1"] - q["L_APP2"] - q["L_APD"]) < 1e-3
    assert abs(q["L_AHP"] - sum(q[f"L_ARE{b}"] for b in rp100.boucles)) < 1e-3
