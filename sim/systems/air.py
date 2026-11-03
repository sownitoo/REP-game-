"""Air comprimé de régulation (SAR, §4.13) : un collecteur alimenté par 2 compresseurs.

dP/dt = chute · (consommation + fuite − production)    (en bar/min, débits relatifs à la consommation normale)
Les compresseurs régulent la pression (production limitée à leur capacité). Sous p_min, les vannes
pneumatiques n'ont plus d'air : elles vont en position de repli après leur réserve locale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.components.base import Composant
from sim.components.pump import Pompe
from sim.config import AirComprimeCfg
from sim.units import S_PAR_MIN

GAIN_REGULATION = 2.0           # production supplémentaire par bar sous la consigne (régulation des compresseurs)


@dataclass
class EtatAir:
    p_bar: float
    fuite: float = 0.0               # fuite (relative à la consommation normale)


class AirComprime(Composant):
    """Collecteur d'air (repère SAR) ; commande : isoler une fuite."""

    type_ui = "air"

    def __init__(self, cfg: AirComprimeCfg, compresseurs: list[Pompe]) -> None:
        super().__init__("SAR", "SAR")
        self.cfg = cfg
        self.compresseurs = compresseurs
        self.etat = EtatAir(p_bar=cfg.p_nom_bar)

    @property
    def disponible(self) -> bool:
        return self.etat.p_bar >= self.cfg.p_min_bar

    def avancer(self, dt: float) -> None:
        c, e = self.cfg, self.etat
        capacite = sum(p.etat.vitesse for p in self.compresseurs) * c.capacite_compresseur
        besoin = 1.0 + e.fuite + GAIN_REGULATION * (c.p_nom_bar - e.p_bar)
        production = min(capacite, max(0.0, besoin))
        e.p_bar += c.chute_bar_min / S_PAR_MIN * dt * (production - 1.0 - e.fuite)
        e.p_bar = min(max(e.p_bar, 0.0), c.p_nom_bar)

    def commandes(self) -> list[str]:
        return ["isoler_fuite"]

    def executer(self, action: str, valeur: float | None) -> None:
        if action == "isoler_fuite":
            self.etat.fuite = 0.0

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        d.update(p_bar=self.etat.p_bar, fuite=self.etat.fuite, disponible=self.disponible)
        return d
