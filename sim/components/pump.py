"""Pompe centrifuge : courbe H = H0·s² − k·Q², vitesse s = n/n_nom, démarrage et ralentissement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.components.base import Composant, Sources
from sim.config import PompeCfg
from sim.units import POURCENT, hauteur_vers_bar


@dataclass
class EtatPompe:
    en_marche: bool
    vitesse: float                 # fraction de la vitesse nominale
    auto: bool                     # vitesse pilotée par la régulation (pompes à vitesse variable)
    consigne_auto: float           # sortie de la régulation (fraction)
    consigne_manu: float           # consigne opérateur (fraction)
    defaut: str                    # cause du dernier déclenchement ("" = aucun)


class Pompe(Composant):
    """Pompe centrifuge (moteur électrique ou turbine à vapeur)."""

    type_ui = "pompe"

    def __init__(self, id: str, cfg: PompeCfg) -> None:
        super().__init__(id, cfg.systeme, cfg.alim)
        self.cfg = cfg
        if cfg.h0_m is not None and cfg.h_nom_m is not None:
            # H = H0 − k·Q² passe par le point nominal (Q_nom, H_nom)
            self.k_m_m3h2 = (cfg.h0_m - cfg.h_nom_m) / cfg.q_nom_m3h ** 2
        else:
            self.k_m_m3h2 = 0.0
        consigne = cfg.vitesse_max if cfg.vitesse_variable and cfg.vitesse_max else 1.0
        self.etat = EtatPompe(en_marche=False, vitesse=0.0, auto=cfg.vitesse_variable,
                              consigne_auto=consigne, consigne_manu=consigne, defaut="")

    # --- commandes ---
    def demarrer(self) -> None:
        self.etat.en_marche = True
        self.etat.defaut = ""

    def arreter(self) -> None:
        self.etat.en_marche = False

    def declencher(self, cause: str) -> None:
        """Arrêt par une protection : mémorise la cause (affichée en rouge)."""
        if self.etat.en_marche:
            self.etat.en_marche = False
            self.etat.defaut = cause

    def commandes(self) -> list[str]:
        base = ["demarrer", "arreter"]
        if self.cfg.vitesse_variable:
            base += ["auto", "manu", "vitesse"]
        return base

    # --- dynamique ---
    def consigne_vitesse(self) -> float:
        if not self.cfg.vitesse_variable:
            return 1.0
        c = self.etat.consigne_auto if self.etat.auto else self.etat.consigne_manu
        return min(max(c, self.cfg.vitesse_min or 0.0), self.cfg.vitesse_max or 1.0)

    def avancer(self, dt: float, sources: Sources) -> None:
        """Fait évoluer la vitesse (démarrage en rampe, ralentissement exponentiel)."""
        besoin_elec = self.cfg.entrainement is None
        if self.etat.en_marche and besoin_elec and not sources.electricite_ok:
            self.declencher(f"perte de tension {self.alim}")
        cible = self.consigne_vitesse() if self.etat.en_marche else 0.0
        if cible > self.etat.vitesse:
            self.etat.vitesse = min(cible, self.etat.vitesse + dt / self.cfg.temps_demarrage_s)
        else:
            self.etat.vitesse += (cible - self.etat.vitesse) * min(1.0, dt / self.cfg.temps_ralentissement_s)

    # --- hydraulique ---
    def hydraulique(self, rho_kg_m3: float) -> tuple[float, float]:
        """(ΔP à débit nul en bar, coefficient k en bar/(m³/h)²) à la vitesse actuelle."""
        h0 = self.cfg.h0_m or 0.0
        s = self.etat.vitesse
        return hauteur_vers_bar(h0 * s * s, rho_kg_m3), hauteur_vers_bar(self.k_m_m3h2, rho_kg_m3)

    def debit_libre_m3h(self) -> float:
        """Débit d'une pompe sans réseau (CRF, reprise) : proportionnel à la vitesse."""
        return self.cfg.q_nom_m3h * self.etat.vitesse

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        d.update(en_marche=self.etat.en_marche, vitesse_pct=POURCENT * self.etat.vitesse,
                 auto=self.etat.auto, defaut=self.etat.defaut,
                 vitesse_variable=self.cfg.vitesse_variable)
        return d
