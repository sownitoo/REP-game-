"""Alimentation de secours des GV (ASG, §4.9) : 2 motopompes + 1 turbopompe, aspiration CST.

Réseau liquide décrit dans plant.yaml (reseaux.asg). La turbopompe n'a pas besoin
d'électricité : elle tourne si sa vanne de prise vapeur est ouverte et qu'un GV
d'alimentation a assez de pression ; sa vapeur part à l'atmosphère.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.components.base import Composant
from sim.components.pump import Pompe
from sim.components.valve import Vanne
from sim.config import AsgCfg, NumeriqueCfg, ReseauCfg
from sim.core.network import construire_reseau
from sim.systems.gv import GenerateurVapeur
from sim.thermo.tables import TableEau


@dataclass
class EtatASG:
    qm_gv_kg_s: list[float]
    qm_vapeur_tps_kg_s: float
    p_bar: dict[str, float]


class ASG:
    """Réseau ASG et turbopompe."""

    def __init__(self, cfg: AsgCfg, reseau_cfg: ReseauCfg, composants: dict[str, Composant],
                 num: NumeriqueCfg, table: TableEau, boucles: list[int], t_eau_c: float, p_initiale_bar: float) -> None:
        self.cfg = cfg
        self.table = table
        self.boucles = boucles
        self.t_eau_c = t_eau_c
        self.motopompes: list[Pompe] = [composants["ASG_MP1"], composants["ASG_MP2"]]   # type: ignore[list-item]
        self.turbopompe: Pompe = composants["ASG_TP"]                                  # type: ignore[assignment]
        self.vanne_vapeur: Vanne = composants["ASG_TP_VAP"]                            # type: ignore[assignment]
        self.vannes: list[Vanne] = [composants[f"ASG{b}"] for b in boucles]            # type: ignore[misc]
        self.reseau = construire_reseau("asg", reseau_cfg, composants, num.reseau,
                                        table.rho_liq_kg_m3(t_eau_c), p_initiale_bar)
        self.etat = EtatASG(qm_gv_kg_s=[0.0] * len(boucles), qm_vapeur_tps_kg_s=0.0,
                            p_bar=dict(self.reseau.etat.p_bar))

    @property
    def h_eau_kj_kg(self) -> float:
        return self.table.h_liq_kj_kg(self.t_eau_c)

    def pompes(self) -> list[Pompe]:
        return self.motopompes + [self.turbopompe]

    def vapeur_disponible(self, gvs: list[GenerateurVapeur]) -> bool:
        p_max = max(gvs[self.boucles.index(b)].p_bar for b in self.cfg.prises_vapeur_tps)
        return p_max >= self.cfg.p_vapeur_min_bar

    def piloter_turbopompe(self, gvs: list[GenerateurVapeur]) -> None:
        """Vitesse de consigne de la turbopompe = ouverture de la prise vapeur si la pression suffit."""
        vapeur = self.vapeur_disponible(gvs)
        self.turbopompe.etat.consigne_auto = self.vanne_vapeur.etat.position if vapeur else 0.0

    def resoudre(self, p_cst_bar: float, gvs: list[GenerateurVapeur]) -> None:
        r = self.reseau
        r.fixer_frontiere("CST", p_cst_bar)
        for gv in gvs:
            r.fixer_frontiere(gv.id, gv.p_bar)
        rho = self.table.rho_liq_kg_m3(self.t_eau_c)
        for b in r.branches:
            b.rho_kg_m3 = rho
        r.resoudre()
        self.etat.qm_gv_kg_s = [r.branche[f"L_ASG{b}"].qm_kg_s for b in self.boucles]
        self.etat.qm_vapeur_tps_kg_s = self.cfg.vapeur_tps_kg_s * self.turbopompe.etat.vitesse
        self.etat.p_bar = dict(r.etat.p_bar)

    def vapeur_tps_par_gv_kg_s(self, b: int) -> float:
        """Vapeur prélevée sur le GV b par la turbopompe (répartie entre les GV d'alimentation)."""
        prises = self.cfg.prises_vapeur_tps
        return self.etat.qm_vapeur_tps_kg_s / len(prises) if b in prises else 0.0

    def qm_total_kg_s(self) -> float:
        return sum(max(0.0, q) for q in self.etat.qm_gv_kg_s)

    def exporter_etat(self) -> dict[str, Any]:
        return {"qm_gv_kg_s": list(self.etat.qm_gv_kg_s), "qm_vapeur_tps_kg_s": self.etat.qm_vapeur_tps_kg_s,
                "p_bar": dict(self.reseau.etat.p_bar)}

    def importer_etat(self, d: dict[str, Any]) -> None:
        self.etat = EtatASG(**d)
        self.reseau.etat.p_bar = dict(d["p_bar"])
