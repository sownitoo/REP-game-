"""Accumulateurs (partie passive du RIS) : un par boucle, eau borée sous azote.

Le gaz se détend de façon isotherme : P = P0·Vg0 / Vg. Dès que la pression primaire passe sous
celle du gaz, l'eau entre dans la branche froide à travers le clapet : Q = k·√(P_acc − P_primaire),
si la vanne d'isolement est ouverte. En conduite, on les isole sous P-11 avant de descendre à ~42 bar.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from sim.components.valve import Vanne
from sim.config import AccumulateursCfg
from sim.units import S_PAR_H


@dataclass
class EtatAccumulateurs:
    v_eau_m3: list[float] = field(default_factory=list)
    qm_kg_s: list[float] = field(default_factory=list)


class Accumulateurs:
    def __init__(self, cfg: AccumulateursCfg, composants: dict, boucles: list[int], rho_kg_m3: float) -> None:
        self.cfg = cfg
        self.rho = rho_kg_m3
        self.isolement: list[Vanne] = [composants[f"ACC{b}_ISOL"] for b in boucles]
        n = len(boucles)
        self.etat = EtatAccumulateurs(v_eau_m3=[cfg.volume_eau_m3] * n, qm_kg_s=[0.0] * n)

    def p_bar(self, i: int) -> float:
        c = self.cfg
        return c.p_azote_bar * (c.volume_m3 - c.volume_eau_m3) / (c.volume_m3 - self.etat.v_eau_m3[i])

    def isoles(self) -> bool:
        return all(v.etat.position <= 0.0 for v in self.isolement)

    def avancer(self, dt: float, p_primaire_bar: float) -> None:
        e, c = self.etat, self.cfg
        for i, v in enumerate(self.isolement):
            dp = self.p_bar(i) - p_primaire_bar
            q = c.k_m3h_par_racine_bar * math.sqrt(dp) * v.etat.position if dp > 0.0 and e.v_eau_m3[i] > 0.0 else 0.0
            q = min(q, e.v_eau_m3[i] * S_PAR_H / dt)
            e.v_eau_m3[i] -= q * dt / S_PAR_H
            e.qm_kg_s[i] = q * self.rho / S_PAR_H

    @property
    def qm_total_kg_s(self) -> float:
        return sum(self.etat.qm_kg_s)
