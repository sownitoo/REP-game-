"""Régulateur PI avec anticipation, bornes et anti-emballement.

En mode manuel, l'intégrale suit la sortie manuelle : le retour en automatique
se fait sans à-coup.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EtatPI:
    integrale: float
    auto: bool
    sortie_manu: float
    sortie: float


class RegulateurPI:
    """sortie = anticipation + kp·e + I ; dI/dt = kp·e/ti ; bornée à [sortie_min, sortie_max]."""

    def __init__(self, id: str, kp: float, ti_s: float, sortie_min: float, sortie_max: float,
                 sortie_initiale: float) -> None:
        self.id = id
        self.kp = kp
        self.ti_s = ti_s
        self.sortie_min = sortie_min
        self.sortie_max = sortie_max
        self.etat = EtatPI(integrale=sortie_initiale, auto=True, sortie_manu=sortie_initiale,
                           sortie=sortie_initiale)

    def _borner(self, x: float) -> float:
        return min(max(x, self.sortie_min), self.sortie_max)

    def calculer(self, erreur: float, dt: float, anticipation: float = 0.0) -> float:
        e = self.etat
        if not e.auto:
            e.sortie = self._borner(e.sortie_manu)
            e.integrale = e.sortie - anticipation - self.kp * erreur
            return e.sortie
        integrale = e.integrale + self.kp * erreur * dt / self.ti_s
        brute = anticipation + self.kp * erreur + integrale
        sortie = self._borner(brute)
        # anti-emballement : on n'intègre pas si cela pousse plus loin dans la saturation
        if brute == sortie or (brute > sortie) != (erreur > 0):
            e.integrale = integrale
        e.sortie = sortie
        e.sortie_manu = sortie
        return sortie

    def initialiser(self, sortie: float, anticipation: float = 0.0) -> None:
        """Place le régulateur à l'équilibre sur `sortie` (erreur nulle)."""
        self.etat.integrale = sortie - anticipation
        self.etat.sortie = sortie
        self.etat.sortie_manu = sortie
