"""Brèches (§9.4) : primaire (LOCA), rupture de tube de GV (RTGV), brèche vapeur, PORV bloquée ouverte.

Liquide (brèche primaire) : débit critique simplifié
    G = Cd · min( √(2ρ(P − P_aval)) , max( √(2ρ(P − max(P_aval, Psat(T)))) , K_sat · P ) )
  (l'eau se vaporise au col : le moteur est P − Psat tant qu'elle est sous-refroidie ; saturée, le débit
  diphasique ≈ K_sat · P, environ 3 fois moins qu'en liquide). RTGV : G = Cd · A · √(2·ρ·ΔP) (tube long).
Vapeur : débit sonique ≈ Cd · A · P / √(R·T)
Quand le vide primaire grandit (joints hydrauliques des branches en U vidés), la brèche crache de plus en plus
de vapeur : débit sonique, mais enthalpie élevée → dépressurisation rapide (grosses brèches).
RTGV : l'eau primaire passe dans le GV (Δp primaire − secondaire) avec son activité : l'eau du GV
devient active (« activité vapeur ») — c'est le signe qui permet d'identifier le GV affecté.
La brèche vapeur est placée entre le GV et sa VIV (dans l'enceinte) : la fermeture de la VIV ne l'isole pas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from sim.config import BrechesCfg
from sim.units import POURCENT

PA_PAR_BAR = 1.0e5
R_VAP_J_KGK = 461.5
T_ABS = 273.15
CM_PAR_M = 100.0


def surface_m2(diametre_cm: float) -> float:
    return math.pi * (diametre_cm / CM_PAR_M) ** 2 / 4


@dataclass
class EtatBreches:
    primaire_m2: float = 0.0
    primaire_boucle: int = 1
    rtgv_m2: float = 0.0
    rtgv_gv: int = 1
    vapeur_m2: float = 0.0
    vapeur_gv: int = 1
    porv_bloquee: str = ""
    qm_primaire_kg_s: float = 0.0
    qm_primaire_vapeur_kg_s: float = 0.0      # part de vapeur (prise dans le vide primaire)
    qm_rtgv_kg_s: float = 0.0
    qm_vapeur_kg_s: float = 0.0
    activite_gv: list[float] = field(default_factory=list)    # activité de l'eau de chaque GV (/ primaire)


class Breches:
    def __init__(self, cfg: BrechesCfg, nb_gv: int) -> None:
        self.cfg = cfg
        self.etat = EtatBreches(activite_gv=[0.0] * nb_gv)

    def debit_liquide_kg_s(self, surface: float, rho: float, dp_bar: float) -> float:
        return self.cfg.cd * surface * math.sqrt(2.0 * rho * max(0.0, dp_bar) * PA_PAR_BAR) if surface > 0.0 else 0.0

    def debit_vapeur_kg_s(self, surface: float, p_bar: float, t_c: float) -> float:
        return self.cfg.cd_vapeur * surface * p_bar * PA_PAR_BAR / math.sqrt(R_VAP_J_KGK * (t_c + T_ABS))

    def debit_critique_kg_s(self, surface: float, rho: float, p_bar: float, p_aval_bar: float, psat_bar: float) -> float:
        if surface <= 0.0 or p_bar <= p_aval_bar:
            return 0.0
        g_aval = math.sqrt(2.0 * rho * (p_bar - p_aval_bar) * PA_PAR_BAR)
        g_flash = math.sqrt(2.0 * rho * max(0.0, p_bar - max(p_aval_bar, psat_bar)) * PA_PAR_BAR)
        return self.cfg.cd * surface * min(g_aval, max(g_flash, self.cfg.g_sature_kg_m2s_bar * p_bar))

    def fraction_vapeur(self, v_vide_m3: float, v_decouvrement_m3: float) -> float:
        c = self.cfg
        debut, fin = c.vide_debut_vapeur_pct / POURCENT, c.vide_tout_vapeur_pct / POURCENT
        return min(1.0, max(0.0, (v_vide_m3 / v_decouvrement_m3 - debut) / (fin - debut)))

    def calculer(self, p_prim_bar: float, p_enceinte_bar: float, rho_prim: float, psat_breche_bar: float,
                 p_gv: list[float], tsat_gv: list[float], fraction_vapeur: float = 0.0, tsat_prim_c: float = 0.0) -> None:
        e = self.etat
        liquide = self.debit_critique_kg_s(e.primaire_m2, rho_prim, p_prim_bar, p_enceinte_bar, psat_breche_bar)
        vapeur = self.debit_vapeur_kg_s(e.primaire_m2, p_prim_bar, tsat_prim_c) if p_prim_bar > p_enceinte_bar else 0.0
        e.qm_primaire_vapeur_kg_s = fraction_vapeur * vapeur
        e.qm_primaire_kg_s = (1.0 - fraction_vapeur) * liquide + e.qm_primaire_vapeur_kg_s
        i = e.rtgv_gv - 1
        e.qm_rtgv_kg_s = self.debit_liquide_kg_s(e.rtgv_m2, rho_prim, p_prim_bar - p_gv[i]) if e.rtgv_m2 > 0.0 else 0.0
        j = e.vapeur_gv - 1
        e.qm_vapeur_kg_s = self.debit_vapeur_kg_s(e.vapeur_m2, p_gv[j], tsat_gv[j]) if e.vapeur_m2 > 0.0 else 0.0

    def avancer_activite(self, dt: float, masses_gv_kg: list[float]) -> None:
        """Activité de l'eau des GV : apport par la RTGV (dilution dans la masse d'eau du GV)."""
        e = self.etat
        if e.qm_rtgv_kg_s <= 0.0:
            return
        i = e.rtgv_gv - 1
        m = max(masses_gv_kg[i], 1.0)
        e.activite_gv[i] += dt * e.qm_rtgv_kg_s * (self.cfg.activite_primaire - e.activite_gv[i]) / m
