"""Bâche à surface libre (puits condenseur, bâche de stockage) : masse, niveau, pression au fond."""

from __future__ import annotations

from dataclasses import dataclass

from sim.units import POURCENT, hauteur_vers_bar


@dataclass
class EtatBache:
    m_kg: float


class Bache:
    """Bâche cylindrique verticale (section constante)."""

    def __init__(self, id: str, volume_m3: float, hauteur_m: float, m_initiale_kg: float) -> None:
        self.id = id
        self.volume_m3 = volume_m3
        self.hauteur_m = hauteur_m
        self.etat = EtatBache(m_kg=m_initiale_kg)

    def volume_eau_m3(self, rho_kg_m3: float) -> float:
        return self.etat.m_kg / rho_kg_m3

    def niveau_pct(self, rho_kg_m3: float) -> float:
        return POURCENT * self.volume_eau_m3(rho_kg_m3) / self.volume_m3

    def p_fond_bar(self, p_surface_bar: float, rho_kg_m3: float, hauteur_sous_fond_m: float) -> float:
        """Pression au point d'aspiration situé `hauteur_sous_fond_m` sous le fond."""
        h_eau = self.hauteur_m * self.niveau_pct(rho_kg_m3) / POURCENT
        return p_surface_bar + hauteur_vers_bar(h_eau + hauteur_sous_fond_m, rho_kg_m3)

    def integrer(self, dt: float, qm_net_kg_s: float) -> None:
        self.etat.m_kg = max(0.0, self.etat.m_kg + qm_net_kg_s * dt)
