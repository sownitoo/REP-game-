"""Injection de sécurité (RIS, §4.4) et aspersion enceinte (EAS, §4.5).

- HP : pompes de charge par la ligne BIT (calculée par le RCV), jusqu'à ~185 bar.
- MP : 2 pompes SI, ~97 m³/h à 46 bar, débit nul à 106 bar.
- BP : pompes RRA en injection, débit nul à ~14 bar (aspiration PTR ou puisards, pas la branche chaude).
- Accumulateurs : voir accumulateurs.py (passifs, ~42 bar).
Aspiration : bâche PTR (injection directe), puis puisards de l'enceinte (recirculation) quand l'opérateur
ouvre les vannes RIS_PUISARD. À 48 % de PTR, les pompes RRA s'arrêtent ; à 17 %, l'aspersion s'arrête.
Débit d'une pompe : Q = Qn · √((ΔP0 − ΔP) / (ΔP0 − ΔPn)), ΔP = P primaire − P aspiration.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from sim.components.pump import Pompe
from sim.components.valve import Vanne
from sim.config import EnceinteCfg, PompeChargeCfg, RisCfg

SURDEBIT_MAX = 1.5


def debit_pompe_m3h(c: PompeChargeCfg, vitesse_totale: float, dp_bar: float) -> float:
    x = max(0.0, (c.dp0_bar - dp_bar) / (c.dp0_bar - c.dp_nom_bar))
    return vitesse_totale * c.q_nom_m3h * min(math.sqrt(x), SURDEBIT_MAX)


@dataclass
class EtatRis:
    q_mp_m3h: float = 0.0
    q_bp_m3h: float = 0.0
    q_eas_m3h: float = 0.0
    recirculation: bool = False


class RIS:
    def __init__(self, cfg: RisCfg, cfg_enc: EnceinteCfg, composants: dict, pompes_rra: list[Pompe]) -> None:
        self.cfg = cfg
        self.cfg_enc = cfg_enc
        self.pompes_mp: list[Pompe] = [composants["RIS_PMP1"], composants["RIS_PMP2"]]
        self.pompes_bp = pompes_rra
        self.pompes_eas: list[Pompe] = [composants["EAS_P1"], composants["EAS_P2"]]
        self.bit: Vanne = composants["RIS_BIT"]
        self.puisard: list[Vanne] = [composants["RIS_PUISARD1"], composants["RIS_PUISARD2"]]
        self.etat = EtatRis()

    @property
    def recirculation(self) -> bool:
        return any(v.etat.position > 0.0 for v in self.puisard)

    def calculer(self, p_prim_bar: float, p_aspiration_bar: float, injection_bp: bool) -> None:
        """Débits demandés (m³/h) ; les prélèvements PTR / puisards sont faits par la centrale."""
        e, c = self.etat, self.cfg
        dp = p_prim_bar - p_aspiration_bar
        e.recirculation = self.recirculation
        e.q_mp_m3h = debit_pompe_m3h(c.mp, sum(p.etat.vitesse for p in self.pompes_mp), dp)
        e.q_bp_m3h = debit_pompe_m3h(c.bp, sum(p.etat.vitesse for p in self.pompes_bp), dp) if injection_bp else 0.0
        e.q_eas_m3h = sum(p.etat.vitesse for p in self.pompes_eas) * self.cfg_enc.aspersion_m3h

    @property
    def q_injection_m3h(self) -> float:
        return self.etat.q_mp_m3h + self.etat.q_bp_m3h
