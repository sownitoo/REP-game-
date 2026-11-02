"""Source de chaleur imposée (V0 uniquement) : remplace le primaire et le cœur.

Modèle : un seul nœud primaire de capacité thermique C
    C · dTmoy/dt = P_source − Σ Q_GV,   Q_GV = UA · (Tmoy − Tsat(P_GV))
Pilotage de P_source :
- auto : suit Tref(charge turbine) — fait office de grappes + contre-réactions ;
- manu : consigne joueur ;
- après AU : neutrons retardés (1 groupe) + puissance résiduelle Way-Wigner (§4.16).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from sim.components.base import Composant
from sim.config import CoeurCfg, PointNominalCfg, SourceV0Cfg
from sim.units import KJ_PAR_MJ, KW_PAR_MW, POURCENT, S_PAR_MIN, interp_table


@dataclass
class EtatSourceV0:
    tmoy_c: float
    p_kw: float                   # puissance thermique actuelle
    auto: bool
    consigne_manu_mw: float
    integrale_mw: float
    au: bool                      # grappes chutées
    t_depuis_au_s: float
    p_avant_au_kw: float
    tref_c: float


class SourceV0(Composant):
    """Nœud primaire simplifié + puissance pilotée (repère SOURCE)."""

    type_ui = "source"

    def __init__(self, cfg: SourceV0Cfg, coeur: CoeurCfg, nominal: PointNominalCfg, dt_s: float) -> None:
        super().__init__("SOURCE", "RCP")
        self.cfg = cfg
        self.coeur = coeur
        self.dt_s = dt_s
        self.c_kj_c = cfg.capacite_thermique_mj_c * KJ_PAR_MJ
        # neutrons retardés après AU (1 groupe) : saut prompt puis décroissance
        beta, rho = coeur.beta_pcm, coeur.rho_au_pcm
        self.fraction_prompte = beta / (beta - rho)
        self.tau_retardes_s = (beta - rho) / (coeur.lambda_s * abs(rho))
        p_nom_kw = nominal.p_source_mw * KW_PAR_MW
        self.etat = EtatSourceV0(tmoy_c=nominal.tmoy_c, p_kw=p_nom_kw, auto=cfg.mode_initial == "auto",
                                 consigne_manu_mw=nominal.p_source_mw, integrale_mw=0.0, au=False,
                                 t_depuis_au_s=0.0, p_avant_au_kw=p_nom_kw, tref_c=nominal.tmoy_c)

    @property
    def puissance_pct(self) -> float:
        return POURCENT * self.etat.p_kw / (self.cfg.p_nom_mw * KW_PAR_MW)

    # --- puissance après AU ---
    def fraction_apres_au(self, t_s: float) -> float:
        """P/P0 après AU : neutrons retardés + puissance résiduelle (Way-Wigner)."""
        r = self.coeur.residuelle
        t = max(t_s, self.dt_s)
        residuelle = r.a * (t ** -r.b - (t + r.t_fonctionnement_s) ** -r.b)
        return self.fraction_prompte * math.exp(-t / self.tau_retardes_s) + residuelle

    def chute_grappes(self) -> None:
        if not self.etat.au:
            self.etat.au = True
            self.etat.t_depuis_au_s = 0.0
            self.etat.p_avant_au_kw = self.etat.p_kw

    def rearmer(self) -> None:
        """Après réarmement de l'AU : la source repart en manuel depuis sa puissance actuelle."""
        self.etat.au = False
        self.etat.auto = False
        self.etat.consigne_manu_mw = self.etat.p_kw / KW_PAR_MW

    # --- commandes joueur ---
    def commandes(self) -> list[str]:
        return ["auto", "manu", "consigne_mw"]

    def executer(self, action: str, valeur: float | None) -> None:
        if action == "auto":
            self.etat.auto = True
            self.etat.integrale_mw = 0.0
        elif action == "manu":
            self.etat.auto = False
            self.etat.consigne_manu_mw = self.etat.p_kw / KW_PAR_MW
        elif action == "consigne_mw" and valeur is not None:
            self.etat.consigne_manu_mw = valeur

    # --- dynamique ---
    def chaleur_gv_kw(self, ua_kw_c: float, tsat_gv_c: float) -> float:
        return ua_kw_c * (self.etat.tmoy_c - tsat_gv_c)

    def avancer(self, dt: float, q_gv_total_kw: float, charge_turbine_pct: float) -> None:
        e = self.etat
        cfg = self.cfg
        e.tref_c = interp_table(cfg.tref_programme_c, charge_turbine_pct)
        p_max_mw = cfg.p_nom_mw * cfg.p_max_pct / POURCENT
        if e.au:
            e.t_depuis_au_s += dt
            e.p_kw = e.p_avant_au_kw * self.fraction_apres_au(e.t_depuis_au_s)
        else:
            if e.auto:
                ecart = e.tref_c - e.tmoy_c
                e.integrale_mw += cfg.kp_mw_c * ecart * dt / cfg.ti_s
                e.integrale_mw = max(-cfg.p_nom_mw, min(cfg.p_nom_mw, e.integrale_mw))   # anti-emballement
                anticipation = cfg.p_nom_mw * charge_turbine_pct / POURCENT
                demande_mw = anticipation + cfg.kp_mw_c * ecart + e.integrale_mw
            else:
                demande_mw = e.consigne_manu_mw
            demande_kw = min(max(demande_mw, 0.0), p_max_mw) * KW_PAR_MW
            pas_kw = cfg.vitesse_max_pct_min / POURCENT * cfg.p_nom_mw * KW_PAR_MW * dt / S_PAR_MIN
            e.p_kw += max(-pas_kw, min(pas_kw, demande_kw - e.p_kw))
        e.tmoy_c += dt * (e.p_kw - q_gv_total_kw) / self.c_kj_c

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        d.update(p_mw=self.etat.p_kw / KW_PAR_MW, tmoy_c=self.etat.tmoy_c, tref_c=self.etat.tref_c,
                 auto=self.etat.auto, au=self.etat.au, consigne_mw=self.etat.consigne_manu_mw)
        return d
