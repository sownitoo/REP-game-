"""Enceinte de confinement (§9.5) et bâche de décharge du pressuriseur (PRT).

Enceinte : un volume d'air + vapeur (gaz parfaits), des parois (béton + acier) qui absorbent la chaleur,
un puisard qui recueille l'eau. Ce qui entre (brèche, vapeur, PRT) se détend : une partie se vaporise
(titre x = (h − h_f) / h_fg à la pression de l'enceinte), le reste tombe au puisard. Si la vapeur dépasse
la saturation, l'excédent condense (brouillard → puisard) en rendant sa chaleur latente à l'atmosphère.
L'aspersion (EAS) refroidit l'atmosphère, ce qui fait condenser la vapeur et baisser la pression.

PRT : ~38 m³ d'eau sous azote. La vapeur des PORV et des soupapes du PZR y condense (barboteur) ;
P = P_azote (comprimé par l'eau, chauffé) + Psat(T eau). Au-delà de 8 bar, le disque de rupture cède :
la décharge part alors directement dans l'enceinte.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.config import EnceinteCfg, PrtCfg
from sim.thermo.tables import TableEau
from sim.units import KJ_PAR_MJ, S_PAR_H

R_AIR_KJ_KGK = 0.287
R_VAP_KJ_KGK = 0.4615
CV_AIR_KJ_KGK = 0.718
CV_VAP_KJ_KGK = 1.40
U_VAP_0_KJ_KG = 2375.0           # énergie interne de la vapeur à 0 °C (gaz parfait)
CP_EAU_KJ_KGK = 4.18
RHO_EAU_KG_M3 = 990.0
T_ABS = 273.15
KPA_PAR_BAR = 100.0
ITERATIONS_CONDENSATION = 40
VOLUME_GAZ_MIN = 0.05            # fraction minimale du volume de la PRT laissée au gaz


@dataclass
class EtatEnceinte:
    t_c: float
    m_vapeur_kg: float
    t_parois_c: float
    puisard_m3: float = 0.0
    t_puisard_c: float = 0.0
    m_air_kg: float = 0.0
    p_bar: float = 0.0


class Enceinte:
    def __init__(self, cfg: EnceinteCfg, table: TableEau) -> None:
        self.cfg = cfg
        self.table = table
        t = cfg.t_initiale_c
        pv = cfg.humidite * table.psat_bar(t)
        tk = t + T_ABS
        m_air = (cfg.p_initiale_bar - pv) * KPA_PAR_BAR * cfg.volume_m3 / (R_AIR_KJ_KGK * tk)
        m_v = pv * KPA_PAR_BAR * cfg.volume_m3 / (R_VAP_KJ_KGK * tk)
        self.etat = EtatEnceinte(t_c=t, m_vapeur_kg=m_v, t_parois_c=t, t_puisard_c=t, m_air_kg=m_air,
                                 p_bar=cfg.p_initiale_bar)

    # ------------------------------------------------------------------ thermodynamique
    def _energie(self, t_c: float, m_v: float) -> float:
        return self.etat.m_air_kg * CV_AIR_KJ_KGK * t_c + m_v * (U_VAP_0_KJ_KG + CV_VAP_KJ_KGK * t_c)

    def _temperature(self, e_kj: float, m_v: float) -> float:
        return (e_kj - U_VAP_0_KJ_KG * m_v) / (self.etat.m_air_kg * CV_AIR_KJ_KGK + CV_VAP_KJ_KGK * m_v)

    def _p_vap_bar(self, t_c: float, m_v: float) -> float:
        return m_v * R_VAP_KJ_KGK * (t_c + T_ABS) / self.cfg.volume_m3 / KPA_PAR_BAR

    def _p_bar(self, t_c: float, m_v: float) -> float:
        return (self.etat.m_air_kg * R_AIR_KJ_KGK * (t_c + T_ABS) / self.cfg.volume_m3 / KPA_PAR_BAR
                + self._p_vap_bar(t_c, m_v))

    @property
    def p_rel_bar(self) -> float:
        return self.etat.p_bar - self.cfg.p_initiale_bar

    def _vers_puisard(self, m_kg: float, t_c: float) -> None:
        e = self.etat
        v = m_kg / RHO_EAU_KG_M3
        if v <= 0.0:
            return
        total = e.puisard_m3 + v
        e.t_puisard_c = (e.puisard_m3 * e.t_puisard_c + v * t_c) / total
        e.puisard_m3 = total

    # ------------------------------------------------------------------ pas de calcul
    def avancer(self, dt: float, apports: list[tuple[float, float]], aspersion_m3h: float, t_aspersion_c: float) -> None:
        """apports : (débit kg/s, enthalpie kJ/kg) entrant dans l'enceinte."""
        c, e, tab = self.cfg, self.etat, self.table
        m_v = e.m_vapeur_kg
        energie = self._energie(e.t_c, m_v)
        tsat = tab.tsat_c(e.p_bar)
        hf, hg = tab.h_liq_kj_kg(tsat), tab.hg_kj_kg(e.p_bar)
        for qm, h in apports:
            if qm <= 0.0:
                continue
            x = min(1.0, max(0.0, (h - hf) / (hg - hf)))
            m_v += x * qm * dt
            energie += x * qm * dt * hg
            self._vers_puisard((1.0 - x) * qm * dt, tsat)
        t = self._temperature(energie, m_v)
        # parois
        q_parois = c.ha_parois_kw_c * (t - e.t_parois_c)
        energie -= q_parois * dt
        e.t_parois_c += q_parois * dt / (c.capacite_parois_mj_c * KJ_PAR_MJ)
        # aspersion
        if aspersion_m3h > 0.0:
            m_asp = aspersion_m3h * RHO_EAU_KG_M3 / S_PAR_H * dt
            t_sortie = t_aspersion_c + c.efficacite_aspersion * (t - t_aspersion_c)
            energie -= m_asp * CP_EAU_KJ_KGK * (t_sortie - t_aspersion_c)
            self._vers_puisard(m_asp, t_sortie)
        t = self._temperature(energie, m_v)
        # condensation de la vapeur en excès (bisection sur la masse condensée)
        if self._p_vap_bar(t, m_v) > tab.psat_bar(t):
            bas, haut = 0.0, m_v
            for _ in range(ITERATIONS_CONDENSATION):
                dm = 0.5 * (bas + haut)
                t_essai = self._temperature(energie - dm * CP_EAU_KJ_KGK * t, m_v - dm)
                if self._p_vap_bar(t_essai, m_v - dm) > tab.psat_bar(t_essai):
                    bas = dm
                else:
                    haut = dm
            dm = haut
            energie -= dm * CP_EAU_KJ_KGK * t
            m_v -= dm
            t = self._temperature(energie, m_v)
            self._vers_puisard(dm, t)
        e.t_c, e.m_vapeur_kg = t, m_v
        e.p_bar = self._p_bar(t, m_v)

    def prelever_puisard(self, dt: float, q_m3h: float) -> float:
        """Aspiration de recirculation ; renvoie le débit réellement disponible (m³/h)."""
        e = self.etat
        q = min(q_m3h, e.puisard_m3 * S_PAR_H / dt) if dt > 0.0 else 0.0
        e.puisard_m3 = max(0.0, e.puisard_m3 - q * dt / S_PAR_H)
        return q


@dataclass
class EtatPrt:
    m_eau_kg: float
    t_c: float
    disque_rompu: bool = False
    p_bar: float = 0.0


class PRT:
    def __init__(self, cfg: PrtCfg, table: TableEau) -> None:
        self.cfg = cfg
        self.table = table
        self.etat = EtatPrt(m_eau_kg=cfg.volume_eau_m3 * RHO_EAU_KG_M3, t_c=cfg.t_initiale_c)
        self.etat.p_bar = self._pression()

    def _pression(self) -> float:
        c, e = self.cfg, self.etat
        v_gaz0 = c.volume_m3 - c.volume_eau_m3
        v_gaz = max(VOLUME_GAZ_MIN * c.volume_m3, c.volume_m3 - e.m_eau_kg / RHO_EAU_KG_M3)
        p_azote = c.p_azote_bar * (v_gaz0 / v_gaz) * (e.t_c + T_ABS) / (c.t_initiale_c + T_ABS)
        return p_azote + self.table.psat_bar(e.t_c)

    def avancer(self, dt: float, qm_kg_s: float, h_kj_kg: float, p_enceinte_bar: float) -> list[tuple[float, float]]:
        """Reçoit la décharge du PZR ; renvoie ce qui part dans l'enceinte (débit, enthalpie)."""
        e = self.etat
        if e.disque_rompu:
            e.p_bar = p_enceinte_bar
            return [(qm_kg_s, h_kj_kg)]
        if qm_kg_s > 0.0:
            m = qm_kg_s * dt
            energie = e.m_eau_kg * CP_EAU_KJ_KGK * e.t_c + m * h_kj_kg
            e.m_eau_kg += m
            e.t_c = energie / (e.m_eau_kg * CP_EAU_KJ_KGK)
        e.p_bar = self._pression()
        if e.p_bar >= self.cfg.p_disque_bar:
            e.disque_rompu = True
        return []
