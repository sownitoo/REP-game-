"""Capteur multi-voies : retard du 1er ordre par voie, panne = valeur figée."""

from __future__ import annotations

from dataclasses import dataclass, field

from sim.components.base import Composant


@dataclass
class EtatCapteur:
    valeurs: list[float]
    pannes: list[bool] = field(default_factory=list)


class Capteur(Composant):
    """Mesure redondante (n voies) d'une grandeur, bornée à sa gamme."""

    type_ui = "capteur"

    def __init__(self, id: str, systeme: str, voies: int, retard_s: float,
                 gamme_min: float, gamme_max: float, valeur_initiale: float) -> None:
        super().__init__(id, systeme)
        self.retard_s = retard_s
        self.gamme = (gamme_min, gamme_max)
        v = self._borner(valeur_initiale)
        self.etat = EtatCapteur(valeurs=[v] * voies, pannes=[False] * voies)

    def _borner(self, x: float) -> float:
        return min(max(x, self.gamme[0]), self.gamme[1])

    def mesurer(self, dt: float, valeur_vraie: float) -> None:
        cible = self._borner(valeur_vraie)
        a = min(1.0, dt / self.retard_s)
        for i, v in enumerate(self.etat.valeurs):
            if not self.etat.pannes[i]:
                self.etat.valeurs[i] = v + a * (cible - v)

    def initialiser(self, valeur: float) -> None:
        self.etat.valeurs = [self._borner(valeur)] * len(self.etat.valeurs)

    @property
    def mediane(self) -> float:
        """Valeur retenue pour la régulation : médiane des voies."""
        v = sorted(self.etat.valeurs)
        return v[len(v) // 2]

    def depasse(self, seuil: float, au_dessus: bool) -> list[bool]:
        """Voie par voie : seuil franchi ?"""
        return [(v > seuil) if au_dessus else (v < seuil) for v in self.etat.valeurs]
