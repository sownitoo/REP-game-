"""Joints des pompes primaires (§4.1) : sans injection aux joints ET sans barrière thermique (RRI),
ils se dégradent : petite fuite (~5 m³/h par pompe) après ~13 min, joints détruits (68 m³/h) une
heure plus tard. Débit ∝ √(P / P_ref). L'eau part dans l'enceinte (comptée, sans effet en V3).
Garde-fou : si le pressuriseur se vide ou se remplit (primaire diphasique ou PZR plein : pas modélisés
avant la V4), la simulation est figée et une alarme le signale.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from sim.config import JointsPpCfg
from sim.units import S_PAR_H

NIVEAU_PZR_MIN_PCT = 2.0         # PZR vide ou plein : hors du domaine de validité du modèle
NIVEAU_PZR_MAX_PCT = 98.0
DEBIT_INJECTION_MIN_M3H = 1.0    # injection aux joints considérée comme présente au-delà


@dataclass
class EtatJoints:
    sans_refroidissement_s: list[float] = field(default_factory=list)
    fuite_m3h: list[float] = field(default_factory=list)
    volume_fuite_m3: float = 0.0
    hors_domaine: bool = False


class JointsPP:
    def __init__(self, cfg: JointsPpCfg, nb_pompes: int) -> None:
        self.cfg = cfg
        self.etat = EtatJoints(sans_refroidissement_s=[0.0] * nb_pompes, fuite_m3h=[0.0] * nb_pompes)

    def avancer(self, dt: float, injection_ok: bool, rri_ok: bool, p_bar: float, niveau_pzr_pct: float) -> None:
        c, e = self.cfg, self.etat
        e.hors_domaine = e.hors_domaine or not NIVEAU_PZR_MIN_PCT <= niveau_pzr_pct <= NIVEAU_PZR_MAX_PCT
        facteur = math.sqrt(max(p_bar, 0.0) / c.p_ref_bar)
        for i in range(len(e.fuite_m3h)):
            if not (injection_ok or rri_ok):
                e.sans_refroidissement_s[i] += dt
            t = e.sans_refroidissement_s[i]
            if t >= c.delai_degradation_s + c.delai_rupture_s:
                base = c.fuite_max_m3h
            elif t >= c.delai_degradation_s:
                base = c.fuite_initiale_m3h
            else:
                base = 0.0
            e.fuite_m3h[i] = 0.0 if e.hors_domaine else base * facteur
        e.volume_fuite_m3 += self.fuite_totale_m3h * dt / S_PAR_H

    @property
    def fuite_totale_m3h(self) -> float:
        return sum(self.etat.fuite_m3h)
