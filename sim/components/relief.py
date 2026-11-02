"""Soupape de sûreté : ouverture passive au tarage, refermeture après chute de pression (blowdown)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.components.base import Composant
from sim.units import POURCENT


@dataclass
class EtatSoupape:
    ouverte: bool
    sollicitations: int            # nombre d'ouvertures (pénalités / débrief)


class Soupape(Composant):
    """Soupape de sûreté à débit critique (vapeur)."""

    type_ui = "soupape"

    def __init__(self, id: str, systeme: str, tarage_bar: float, capacite_kg_s: float,
                 fermeture_pct: float) -> None:
        super().__init__(id, systeme)
        self.tarage_bar = tarage_bar
        self.capacite_kg_s = capacite_kg_s
        self.p_fermeture_bar = tarage_bar * (1.0 - fermeture_pct / POURCENT)
        self.etat = EtatSoupape(ouverte=False, sollicitations=0)

    def mettre_a_jour(self, p_bar: float) -> bool:
        """Met à jour l'état ; renvoie True si la soupape vient de s'ouvrir."""
        if not self.etat.ouverte and p_bar >= self.tarage_bar:
            self.etat.ouverte = True
            self.etat.sollicitations += 1
            return True
        if self.etat.ouverte and p_bar <= self.p_fermeture_bar:
            self.etat.ouverte = False
        return False

    def debit_kg_s(self, p_bar: float) -> float:
        return self.capacite_kg_s * p_bar / self.tarage_bar if self.etat.ouverte else 0.0

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        d.update(ouverte=self.etat.ouverte, tarage_bar=self.tarage_bar,
                 sollicitations=self.etat.sollicitations)
        return d
