"""Vannes : tout-ou-rien (Valve), régulée (ControlValve), clapet (CheckValve), perte de charge fixe (Resistance).

- MOV (motorisée) : reste en place si perte de tension.
- AOV (pneumatique) : va en position de repli si perte d'air, après épuisement de la réserve locale.
- Un « ordre » automatique (logique de protection) prime sur la demande opérateur et la régulation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.components.base import Composant, Sources
from sim.config import ClapetCfg, ResistanceCfg, VanneCfg
from sim.units import POURCENT, RHO_REF_KG_M3, S_PAR_MIN

POSITIONS_REPLI = {"fermee": 0.0, "ouverte": 1.0}


@dataclass
class EtatVanne:
    position: float                # 0 = fermée … 1 = ouverte
    auto: bool                     # suit la régulation (vannes régulées)
    demande_auto: float            # sortie de la régulation
    demande_manu: float            # demande opérateur
    ordre: float | None            # ordre automatique (prioritaire), None si aucun
    ordre_raison: str
    air_restant_s: float           # réserve d'air locale restante


class Vanne(Composant):
    """Vanne tout-ou-rien ou régulée, motorisée ou pneumatique."""

    type_ui = "vanne"
    anti_retour = False

    def __init__(self, id: str, cfg: VanneCfg, position_initiale: float) -> None:
        super().__init__(id, cfg.systeme, cfg.alim, cfg.air)
        self.cfg = cfg
        self.regulee = cfg.type == "ControlValve"
        self.reserve_air_s = (cfg.reserve_air_min or 0.0) * S_PAR_MIN
        self.etat = EtatVanne(position=position_initiale, auto=self.regulee,
                              demande_auto=position_initiale, demande_manu=position_initiale,
                              ordre=None, ordre_raison="", air_restant_s=self.reserve_air_s)

    # --- commandes ---
    def commandes(self) -> list[str]:
        return ["auto", "manu", "position"] if self.regulee else ["ouvrir", "fermer"]

    def demander(self, position: float) -> None:
        """Demande opérateur (0..1)."""
        self.etat.demande_manu = min(max(position, 0.0), 1.0)

    def fixer_ordre(self, ordre: float | None, raison: str = "") -> None:
        """Ordre automatique de la logique (None = pas d'ordre)."""
        self.etat.ordre = ordre
        self.etat.ordre_raison = raison if ordre is not None else ""
        if ordre is not None and not self.regulee:
            # un ordre sur une vanne TOR est « mémorisé » : elle reste dans cette position
            self.etat.demande_manu = ordre

    def demande_effective(self) -> float:
        if self.etat.ordre is not None:
            return self.etat.ordre
        if self.regulee and self.etat.auto:
            return self.etat.demande_auto
        return self.etat.demande_manu

    # --- dynamique ---
    def avancer(self, dt: float, sources: Sources) -> None:
        cible = self.demande_effective()
        if self.cfg.actionneur == "AOV" and self.alim and not sources.electricite_ok:
            # électrovanne de pilotage hors tension : position de repli immédiate
            cible = POSITIONS_REPLI.get(self.cfg.position_repli or "", self.etat.position)
        elif self.cfg.actionneur == "AOV":
            if sources.air_ok:
                self.etat.air_restant_s = self.reserve_air_s
            else:
                self.etat.air_restant_s = max(0.0, self.etat.air_restant_s - dt)
                if self.etat.air_restant_s <= 0.0:
                    cible = POSITIONS_REPLI.get(self.cfg.position_repli or "", self.etat.position)
        elif self.cfg.actionneur == "MOV" and not sources.electricite_ok:
            return  # vanne motorisée sans tension : reste en place
        pas = dt / self.cfg.temps_course_s
        ecart = cible - self.etat.position
        self.etat.position += max(-pas, min(pas, ecart))

    # --- hydraulique ---
    def kv(self) -> float:
        """Kv actuel (caractéristique linéaire)."""
        return (self.cfg.kv_max or 0.0) * self.etat.position

    def debit_vapeur_kg_s(self, p_amont_bar: float) -> float:
        """Débit critique de vapeur (vanne vers l'atmosphère ou le condenseur)."""
        if self.cfg.capacite_kg_s is None or self.cfg.p_ref_bar is None:
            return 0.0
        return self.cfg.capacite_kg_s * self.etat.position * p_amont_bar / self.cfg.p_ref_bar

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        d.update(position_pct=POURCENT * self.etat.position, regulee=self.regulee, auto=self.etat.auto,
                 ordre=self.etat.ordre, ordre_raison=self.etat.ordre_raison,
                 actionneur=self.cfg.actionneur,
                 air_restant_min=self.etat.air_restant_s / S_PAR_MIN if self.cfg.actionneur == "AOV" else None,
                 demande_pct=POURCENT * self.demande_effective())
        return d


class Clapet(Composant):
    """Clapet anti-retour : laisse passer dans le sens de la branche uniquement."""

    type_ui = "clapet"
    anti_retour = True

    def __init__(self, id: str, cfg: ClapetCfg) -> None:
        super().__init__(id, cfg.systeme)
        self.cfg = cfg
        self.ouvert = False   # résultat du calcul hydraulique (affichage)

    def kv(self) -> float:
        return self.cfg.kv_max

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        d["ouvert"] = self.ouvert
        return d


class Resistance(Composant):
    """Perte de charge fixe (échangeur, tuyauterie) définie par un point nominal."""

    type_ui = "echangeur"
    anti_retour = False

    def __init__(self, id: str, cfg: ResistanceCfg) -> None:
        super().__init__(id, cfg.systeme)
        self.cfg = cfg
        # ΔP = d·(Q/Kv)²  ⇒  Kv = Q_nom·√(d_nom/ΔP_nom)
        self._kv = cfg.q_nom_m3h * (cfg.rho_nom_kg_m3 / RHO_REF_KG_M3 / cfg.dp_nom_bar) ** 0.5

    def kv(self) -> float:
        return self._kv
