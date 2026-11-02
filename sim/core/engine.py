"""Horloge de simulation : temps réel accéléré (×1, ×10, ×60, ×600) avec budget de calcul.

À chaque tick réel, on calcule autant de pas que l'accélération le demande, dans la
limite du budget ; l'accélération réellement tenue est mesurée et affichée.
"""

from __future__ import annotations

import time

from sim.config import SimulationCfg
from sim.plant import Centrale
from sim.units import POURCENT


class Simulateur:
    """Fait avancer une centrale en temps réel accéléré."""

    def __init__(self, centrale: Centrale, cfg: SimulationCfg) -> None:
        self.centrale = centrale
        self.cfg = cfg
        self.acceleration = cfg.accelerations[0]
        self.pause = False
        self.acceleration_reelle = 0.0
        self.scenario = ""

    def remplacer(self, centrale: Centrale, scenario: str) -> None:
        self.centrale = centrale
        self.scenario = scenario

    def tick(self, duree_reelle_s: float) -> int:
        """Avance la simulation pour `duree_reelle_s` de temps réel ; renvoie le nombre de pas."""
        if self.pause:
            self.acceleration_reelle = 0.0
            return 0
        c = self.centrale
        n_voulu = round(duree_reelle_s * self.acceleration / c.dt_s)
        budget_s = duree_reelle_s * self.cfg.budget_calcul_pct / POURCENT
        debut = time.perf_counter()
        n = 0
        while n < n_voulu and time.perf_counter() - debut < budget_s:
            c.pas()
            n += 1
        self.acceleration_reelle = n * c.dt_s / duree_reelle_s
        return n
