"""Volume diphasique à l'équilibre de saturation (GV côté secondaire ; plus tard PZR, RDP).

Variables d'état conservées : masse totale m et énergie interne totale U.
La pression et le titre se déduisent de (v = V/m, u = U/m) par un « flash » sur
les tables de saturation : la conservation de la masse et de l'énergie est exacte.
Pas de vapeur surchauffée : un volume asséché (titre > 1, GV vidé par une brèche) est ramené à de la
vapeur saturée sèche de même volume massique (la surchauffe est perdue).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from sim.config import FlashCfg
from sim.thermo.tables import Saturation, TableEau


@dataclass
class EtatVolume2Phase:
    m_kg: float
    u_kj: float
    p_bar: float      # dernière pression calculée (sert aussi de point de départ du flash)


class Volume2Phase:
    """Volume rigide eau + vapeur à saturation."""

    def __init__(self, v_m3: float, table: TableEau, flash: FlashCfg) -> None:
        self.v_m3 = v_m3
        self.table = table
        self.flash = flash
        self.etat = EtatVolume2Phase(m_kg=0.0, u_kj=0.0, p_bar=table.p_min_bar)
        self.x = 0.0
        self.sat: Saturation = table.sat(table.p_min_bar)

    def initialiser(self, p_bar: float, m_liq_kg: float) -> None:
        """État saturé à p_bar contenant m_liq_kg de liquide (le reste du volume en vapeur)."""
        s = self.table.sat(p_bar)
        v_vap = self.v_m3 - m_liq_kg * s.vf_m3_kg
        m_vap = v_vap / s.vg_m3_kg
        self.etat = EtatVolume2Phase(m_kg=m_liq_kg + m_vap,
                                     u_kj=m_liq_kg * s.uf_kj_kg + m_vap * s.ug_kj_kg, p_bar=p_bar)
        self.mettre_a_jour()

    def _flash(self, m_kg: float, u_kj: float) -> tuple[float, float]:
        return self.table.flash_vu(self.v_m3 / m_kg, u_kj / m_kg, self.etat.p_bar,
                                   self.flash.tolerance_lnp, self.flash.pas_derivee_lnp,
                                   self.flash.iterations_max)

    def mettre_a_jour(self) -> None:
        """Recalcule P et le titre à partir de (m, U)."""
        p, x = self._flash(self.etat.m_kg, self.etat.u_kj)
        if x > 1.0:                                   # asséché : vapeur saturée sèche à v = vg(P)
            p = self._p_vapeur_seche(self.v_m3 / self.etat.m_kg)
            self.etat.u_kj = self.etat.m_kg * self.table.sat(p).ug_kj_kg
            x = 1.0
        self.etat.p_bar = p
        self.x = min(max(x, 0.0), 1.0)
        self.sat = self.table.sat(p)

    def _p_vapeur_seche(self, v_m3_kg: float) -> float:
        """Pression où le volume massique de la vapeur saturée vaut v (bissection sur ln P)."""
        tab = self.table
        lo, hi = math.log(tab.p_min_bar), math.log(tab.p_max_bar)
        for _ in range(self.flash.iterations_max):
            mi = 0.5 * (lo + hi)
            if tab.sat(math.exp(mi)).vg_m3_kg > v_m3_kg:
                lo = mi
            else:
                hi = mi
        return math.exp(0.5 * (lo + hi))

    # --- grandeurs dérivées ---
    @property
    def p_bar(self) -> float:
        return self.etat.p_bar

    @property
    def m_liq_kg(self) -> float:
        return self.etat.m_kg * (1.0 - self.x)

    @property
    def v_liq_m3(self) -> float:
        return self.m_liq_kg * self.sat.vf_m3_kg

    # --- bilans ---
    def integrer(self, dt: float, qm_entree_kg_s: float, puissance_entree_kw: float,
                 qm_sortie_kg_s: float, puissance_sortie_kw: float) -> None:
        """Bilans masse et énergie (puissances = débits × enthalpies + chaleur)."""
        self.etat.m_kg += dt * (qm_entree_kg_s - qm_sortie_kg_s)
        self.etat.u_kj += dt * (puissance_entree_kw - puissance_sortie_kw)
        self.mettre_a_jour()

    def sensibilite_bar_par_kg_vapeur(self, dm_kg: float) -> float:
        """Baisse de pression (bar) par kg de vapeur saturée soutiré (> 0)."""
        p, _ = self._flash(self.etat.m_kg - dm_kg, self.etat.u_kj - dm_kg * self.sat.hg_kj_kg)
        return max(0.0, (self.etat.p_bar - p) / dm_kg)
