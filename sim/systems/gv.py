"""Générateur de vapeur côté secondaire + niveau gamme étroite avec gonflement / tassement.

Thermodynamique : Volume2Phase (masse et énergie conservées).
Niveau GE = (V_liquide + k·V_bulles − V_bas) / V_plage, où V_bulles (volume de
vapeur sous le niveau) tend vers τ_séjour · ṁ_vaporisé / ρ_v. Le débit vaporisé
contient :
- la chaleur reçue moins le réchauffage de l'eau alimentaire sous-refroidie ;
- la vaporisation éclair quand la pression baisse (−dP/dt).
D'où, sans fonction de transfert plaquée :
- hausse du débit vapeur → P baisse → gonflement puis baisse du niveau ;
- baisse du débit vapeur → P monte → tassement ;
- plus d'eau froide → moins de bulles → tassement initial.
Le terme bulles n'affecte que la mesure de niveau (bilans exacts).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.components.base import Composant
from sim.components.sensor import Capteur
from sim.components.volume2phase import Volume2Phase
from sim.config import FlashCfg, GVCfg
from sim.thermo.tables import TableEau
from sim.units import KG_PAR_T, KW_PAR_MW, POURCENT


@dataclass
class EtatGV:
    v_bulles_m3: float
    dpdt_bar_s: float
    q_kw: float                   # chaleur reçue du primaire
    qm_alim_kg_s: float
    h_alim_kj_kg: float
    qm_ligne_kg_s: float          # vers le collecteur (mesure venturi)
    qm_decharge_kg_s: float       # VDA + soupapes (atmosphère)
    qm_vaporise_kg_s: float


class GenerateurVapeur(Composant):
    """GV n°b côté secondaire."""

    type_ui = "gv"

    def __init__(self, b: int, cfg: GVCfg, table: TableEau, flash: FlashCfg) -> None:
        super().__init__(f"GV{b}", "GV")
        self.b = b
        self.cfg = cfg
        self.table = table
        self.vol = Volume2Phase(cfg.v_secondaire_m3, table, flash)
        n = cfg.niveau_ge
        self.capteur = Capteur(f"GV{b}_NIV", "GV", n.voies, n.retard_mesure_s, 0.0, POURCENT, 0.0)
        self.etat = EtatGV(v_bulles_m3=0.0, dpdt_bar_s=0.0, q_kw=0.0, qm_alim_kg_s=0.0,
                           h_alim_kj_kg=0.0, qm_ligne_kg_s=0.0, qm_decharge_kg_s=0.0,
                           qm_vaporise_kg_s=0.0)

    # --- initialisation ---
    def initialiser(self, p_bar: float, niveau_pct: float, qm_vapeur_kg_s: float,
                    h_alim_kj_kg: float) -> None:
        """État d'équilibre : pression, niveau, débit vapeur = débit d'eau donnés."""
        s = self.table.sat(p_bar)
        n = self.cfg.niveau_ge
        v_bulles = n.tau_sejour_s * qm_vapeur_kg_s / s.rho_v_kg_m3
        v_mix = n.v_bas_m3 + niveau_pct / POURCENT * n.v_plage_m3
        m_liq = (v_mix - n.k_bulles * v_bulles) / s.vf_m3_kg
        self.vol.initialiser(p_bar, m_liq)
        q_kw = qm_vapeur_kg_s * (s.hg_kj_kg - h_alim_kj_kg)
        self.etat = EtatGV(v_bulles_m3=v_bulles, dpdt_bar_s=0.0, q_kw=q_kw,
                           qm_alim_kg_s=qm_vapeur_kg_s, h_alim_kj_kg=h_alim_kj_kg,
                           qm_ligne_kg_s=qm_vapeur_kg_s, qm_decharge_kg_s=0.0,
                           qm_vaporise_kg_s=qm_vapeur_kg_s)
        self.capteur.initialiser(self.niveau_pct)

    # --- grandeurs ---
    @property
    def p_bar(self) -> float:
        return self.vol.p_bar

    @property
    def tsat_c(self) -> float:
        return self.vol.sat.t_c

    @property
    def niveau_pct(self) -> float:
        n = self.cfg.niveau_ge
        v = self.vol.v_liq_m3 + n.k_bulles * self.etat.v_bulles_m3
        return POURCENT * (v - n.v_bas_m3) / n.v_plage_m3

    def ua_kw_c(self) -> float:
        """UA réduit si les tubes se découvrent (masse d'eau faible)."""
        m_seuil = self.cfg.masse_assechement_t * KG_PAR_T
        return self.cfg.ua_mw_c * KW_PAR_MW * min(1.0, self.vol.m_liq_kg / m_seuil)

    # --- dynamique ---
    def avancer(self, dt: float, q_kw: float, qm_alim_kg_s: float, h_alim_kj_kg: float,
                qm_ligne_kg_s: float, qm_decharge_kg_s: float) -> None:
        e = self.etat
        e.q_kw, e.qm_alim_kg_s, e.h_alim_kj_kg = q_kw, qm_alim_kg_s, h_alim_kj_kg
        e.qm_ligne_kg_s, e.qm_decharge_kg_s = qm_ligne_kg_s, qm_decharge_kg_s
        p_avant = self.vol.p_bar
        hg = self.vol.sat.hg_kj_kg
        qm_sortie = qm_ligne_kg_s + qm_decharge_kg_s
        self.vol.integrer(dt, qm_alim_kg_s, qm_alim_kg_s * h_alim_kj_kg + q_kw, qm_sortie, qm_sortie * hg)

        n = self.cfg.niveau_ge
        s = self.vol.sat
        dpdt = (self.vol.p_bar - p_avant) / dt
        e.dpdt_bar_s += (dpdt - e.dpdt_bar_s) * min(1.0, dt / n.filtre_dpdt_s)
        # débit vaporisé : chaleur − réchauffage de l'eau alimentaire + vaporisation éclair
        m_chauffe = (q_kw - qm_alim_kg_s * (s.hf_kj_kg - h_alim_kj_kg)) / s.hfg_kj_kg
        m_eclair = -self.vol.m_liq_kg * self.table.dhf_dp_kj_kg_bar(s.p_bar) * e.dpdt_bar_s / s.hfg_kj_kg
        e.qm_vaporise_kg_s = max(0.0, m_chauffe + m_eclair)
        v_eq = n.tau_sejour_s * e.qm_vaporise_kg_s / s.rho_v_kg_m3
        e.v_bulles_m3 += (v_eq - e.v_bulles_m3) * min(1.0, dt / n.tau_bulles_s)
        self.capteur.mesurer(dt, self.niveau_pct)

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        d.update(p_bar=self.p_bar, niveau_pct=self.niveau_pct, niveau_voies=self.capteur.etat.valeurs,
                 m_eau_t=self.vol.m_liq_kg / KG_PAR_T)
        return d
