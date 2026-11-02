"""Condenseur + circulation (CRF) + puits + bâche de stockage (CST).

Condenseur = nœud thermique : C·dT/dt = Q_entrée − ε·ṁ_CRF·cp·(T − T_mer),
ε = 1 − exp(−UA/(ṁ·cp)) ; P_cond = Psat(T) + P_incondensables.
La vapeur entrante est condensée sans stockage : sa masse va directement au puits.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from sim.components.base import Composant
from sim.components.pump import Pompe
from sim.components.tank import Bache
from sim.config import CondenseurCfg, CstCfg, PuitsCfg
from sim.thermo.tables import TableEau
from sim.units import KJ_PAR_MJ, KW_PAR_MW, POURCENT, S_PAR_H


@dataclass
class EtatCondenseur:
    t_c: float
    p_bar: float
    q_entree_kw: float
    q_mer_kw: float


class Condenseur(Composant):
    """Condenseur et ses bâches (repère CONDENSEUR)."""

    type_ui = "condenseur"

    def __init__(self, cfg: CondenseurCfg, puits: PuitsCfg, cst: CstCfg, crf: list[Pompe],
                 table: TableEau, t_initiale_c: float) -> None:
        super().__init__("CONDENSEUR", "CVI")
        self.cfg = cfg
        self.cfg_puits = puits
        self.cfg_cst = cst
        self.crf = crf
        self.table = table
        self.c_kj_c = cfg.capacite_thermique_mj_c * KJ_PAR_MJ
        rho_puits = table.rho_liq_kg_m3(t_initiale_c)
        self.puits = Bache("PUITS", puits.volume_m3, puits.hauteur_m,
                           puits.niveau_initial_pct / POURCENT * puits.volume_m3 * rho_puits)
        self.cst = Bache("CST", cst.volume_m3, cst.hauteur_m,
                         cst.volume_initial_m3 * table.rho_liq_kg_m3(cst.t_c))
        self.etat = EtatCondenseur(t_c=t_initiale_c, p_bar=self._p_bar(t_initiale_c), q_entree_kw=0.0,
                                   q_mer_kw=0.0)

    def _p_bar(self, t_c: float) -> float:
        return self.table.psat_bar(t_c) + self.cfg.p_incondensables_bar

    # --- grandeurs ---
    @property
    def rho_puits_kg_m3(self) -> float:
        return self.table.rho_liq_kg_m3(self.etat.t_c)

    @property
    def rho_cst_kg_m3(self) -> float:
        return self.table.rho_liq_kg_m3(self.cfg_cst.t_c)

    @property
    def h_puits_kj_kg(self) -> float:
        return self.table.h_liq_kj_kg(self.etat.t_c)

    def niveau_puits_pct(self) -> float:
        return self.puits.niveau_pct(self.rho_puits_kg_m3)

    def p_aspiration_cex_bar(self) -> float:
        return self.puits.p_fond_bar(self.etat.p_bar, self.rho_puits_kg_m3, self.cfg_puits.hauteur_aspiration_m)

    def p_fond_cst_bar(self, p_atm_bar: float) -> float:
        return self.cst.p_fond_bar(p_atm_bar, self.rho_cst_kg_m3, 0.0)

    def volume_cst_m3(self) -> float:
        return self.cst.volume_eau_m3(self.rho_cst_kg_m3)

    def qm_crf_kg_s(self) -> float:
        return sum(p.debit_libre_m3h() for p in self.crf) * self.cfg.rho_eau_mer_kg_m3 / S_PAR_H

    def nb_crf_en_marche(self) -> int:
        return sum(p.etat.en_marche for p in self.crf)

    # --- dynamique ---
    def integrer(self, dt: float, q_entree_kw: float) -> None:
        cfg, e = self.cfg, self.etat
        qm = self.qm_crf_kg_s()
        if qm > 0.0:
            mcp = qm * cfg.cp_eau_mer_kj_kgk
            efficacite = 1.0 - math.exp(-cfg.ua_mw_c * KW_PAR_MW / mcp)
            q_mer = efficacite * mcp * (e.t_c - cfg.t_mer_c)
        else:
            q_mer = 0.0
        e.q_entree_kw, e.q_mer_kw = q_entree_kw, q_mer
        e.t_c = min(max(e.t_c + dt * (q_entree_kw - q_mer) / self.c_kj_c, cfg.t_mer_c), cfg.t_max_c)
        e.p_bar = self._p_bar(e.t_c)

    def exporter_etat(self) -> dict[str, Any]:
        d = super().exporter_etat()
        d["_puits_m_kg"] = self.puits.etat.m_kg
        d["_cst_m_kg"] = self.cst.etat.m_kg
        return d

    def importer_etat(self, donnees: dict[str, Any]) -> None:
        donnees = dict(donnees)
        self.puits.etat.m_kg = donnees.pop("_puits_m_kg")
        self.cst.etat.m_kg = donnees.pop("_cst_m_kg")
        super().importer_etat(donnees)

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        d.update(p_bar=self.etat.p_bar, t_c=self.etat.t_c, niveau_puits_pct=self.niveau_puits_pct(),
                 volume_cst_m3=self.volume_cst_m3())
        return d
