"""Réfrigération intermédiaire (RRI) et eau brute secourue (SEC), §4.10.

RRI : boucle fermée = un seul nœud thermique C·dT/dt = Q_utilisateurs − Q_SEC.
Utilisateurs : échangeurs RRA, échangeur de décharge RCV, pompes primaires (barrière thermique,
paliers), autres (constante). Échangeurs RRI/SEC : contre-courant, une voie par paire RRI + SEC.
Sans RRI, les pompes primaires doivent être arrêtées (défaut après un délai).
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.components.pump import Pompe
from sim.config import RriCfg, SecCfg
from sim.systems.rra import efficacite_contre_courant
from sim.units import KJ_PAR_MJ, KW_PAR_MW, S_PAR_H


PANNE_PERMANENTE_S = 1.0e9       # panne sans réparation prévue (valeur finie : l'état reste du JSON valide)

@dataclass
class EtatRri:
    t_c: float
    q_utilisateurs_kw: float = 0.0
    q_sec_kw: float = 0.0
    sans_rri_s: float = 0.0          # durée écoulée sans RRI avec des pompes primaires en marche
    panne_jusqua_s: float = -1.0     # panne (fuite du circuit) : pompes indisponibles jusqu'à cet instant


class RRI:
    def __init__(self, cfg: RriCfg, cfg_sec: SecCfg, composants: dict) -> None:
        self.cfg = cfg
        self.cfg_sec = cfg_sec
        self.pompes: list[Pompe] = [composants["RRI_P1"], composants["RRI_P2"]]
        self.pompes_sec: list[Pompe] = [composants["SEC_P1"], composants["SEC_P2"]]
        self.etat = EtatRri(t_c=cfg.t_initiale_c)

    def disponible(self) -> bool:
        return any(p.etat.en_marche for p in self.pompes)

    def conductance_kw_c(self, cp_kj_kgk: float, rho_kg_m3: float) -> float:
        """ε·C_min des échangeurs RRI/SEC en service (kW/°C)."""
        c = self.cfg
        debit = lambda pompes, q: sum(p.etat.vitesse for p in pompes) * q * rho_kg_m3 / S_PAR_H * cp_kj_kgk  # noqa: E731
        c_rri = debit(self.pompes, c.debit_pompe_m3h)
        c_sec = debit(self.pompes_sec, self.cfg_sec.debit_pompe_m3h)
        voies = min(sum(p.etat.en_marche for p in self.pompes), sum(p.etat.en_marche for p in self.pompes_sec))
        eff = efficacite_contre_courant(voies * c.ua_echangeur_mw_c * KW_PAR_MW, c_rri, c_sec)
        return eff * min(c_rri, c_sec)

    def equilibrer(self, q_utilisateurs_kw: float, t_mer_c: float, cp_kj_kgk: float, rho_kg_m3: float) -> None:
        """Température d'équilibre (état initial)."""
        g = self.conductance_kw_c(cp_kj_kgk, rho_kg_m3)
        if g > 0.0:
            self.etat.t_c = t_mer_c + q_utilisateurs_kw / g

    def avancer(self, dt: float, q_utilisateurs_kw: float, t_mer_c: float, cp_kj_kgk: float, rho_kg_m3: float) -> None:
        c, e = self.cfg, self.etat
        e.q_sec_kw = self.conductance_kw_c(cp_kj_kgk, rho_kg_m3) * max(0.0, e.t_c - t_mer_c)
        e.q_utilisateurs_kw = q_utilisateurs_kw
        e.t_c += dt * (q_utilisateurs_kw - e.q_sec_kw) / (c.capacite_mj_c * KJ_PAR_MJ)
