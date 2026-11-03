"""Cœur « boîte noire » (§4.16) : une source de chaleur pilotée simplement.

Cinétique 1 groupe de neutrons retardés, en approximation du saut prompt
(stable avec dt = 0,1 s, valable tant que ρ < β) :
    n = (β·G + S) / (β − ρ)          G = précurseurs normalisés (G = n en régime établi)
    dG/dt = λ·(n − G)
Réactivité (pcm, nulle au point nominal) :
    ρ = ρ_grappes + ρ_mod(T_mod) + α_D·(T_comb − T_comb,ref) + α_B·(C_B − C_B,ref)
    avec un coefficient modérateur α(T) = α_nom·(T − T0)/(T_ref − T0), faible à froid :
    ρ_mod = α_nom/(2·(T_ref − T0))·[(T − T0)² − (T_ref − T0)²]
Le bore C_B vient du RCV (V2). Marges d'arrêt : toutes grappes insérées sauf la plus efficace.
Combustible : 1 nœud thermique ; puissance résiduelle : groupes du 1er ordre ajustés sur Way-Wigner.
Grappes : groupe R de régulation (0 à 228 pas, efficacité intégrale en S, auto ou manuel),
groupe G de compensation (manuel, extrait à 100 %), groupes S d'arrêt (tout ou rien) ;
chute de tous les groupes en ~2 s à l'AU.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from sim.components.base import Composant
from sim.config import CoeurCfg
from sim.units import KW_PAR_MW, POURCENT, S_PAR_MIN, interp_table

PCM = 1.0e-5


@dataclass
class EtatCoeur:
    g: float                      # précurseurs normalisés
    n: float                      # puissance neutronique / nominale
    t_comb_c: float
    p_res_kw: list[float] = field(default_factory=list)   # groupes de puissance résiduelle
    z_pas: float = 0.0            # position du groupe de régulation R (0 = inséré)
    g_pas: float = 0.0            # position du groupe de compensation G (0 = inséré)
    consigne_g_pas: float = 0.0
    arret_insere: float = 0.0     # fraction d'insertion des groupes d'arrêt (1 = insérés)
    chute: bool = False           # AU : grappes en chute / maintenues insérées
    auto: bool = True             # régulation de température en automatique
    consigne_manu_pas: float = 0.0
    extraction_arret: bool = False   # extraction des groupes d'arrêt demandée
    bore_ppm: float = 0.0
    rho_pcm: float = 0.0
    q_caloporteur_kw: float = 0.0
    vitesse_pas_min: float = 0.0  # vitesse actuelle des grappes (> 0 = extraction)
    desequilibre_retard_pct: float = 0.0   # (puissance − charge turbine) filtrée : voie « déséquilibre »
    rho_coincee_pcm: float = 0.0  # V4 : grappe la plus efficace restée hors du cœur (antiréactivité perdue)


class Coeur(Composant):
    """Cœur + grappes (repère GRAPPES pour les commandes)."""

    type_ui = "coeur"

    def __init__(self, cfg: CoeurCfg) -> None:
        super().__init__("GRAPPES", "RGL")
        self.cfg = cfg
        self.p_nom_kw = cfg.p_nom_mw * KW_PAR_MW
        self.beta = cfg.beta_pcm * PCM
        r = cfg.residuelle
        self.fraction_residuelle = sum(r.fractions)
        # résistance thermique combustible → caloporteur : (T_comb,nom − T_mod,ref) / P_nom
        self.r_comb_c_kw = (cfg.combustible.t_nom_c - cfg.t_mod_ref_c) / self.p_nom_kw
        self.c_comb_kj_c = cfg.combustible.capacite_mj_c * KW_PAR_MW
        g = cfg.grappes
        self.etat = EtatCoeur(g=1.0, n=1.0, t_comb_c=cfg.combustible.t_nom_c,
                              p_res_kw=[f * self.p_nom_kw for f in r.fractions],
                              z_pas=g.position_nom_pas, consigne_manu_pas=g.position_nom_pas,
                              g_pas=g.pas_max, consigne_g_pas=g.pas_max, bore_ppm=cfg.bore_ppm)
        self.rho_grappes_nom = self._rho_regulation(g.position_nom_pas)

    # ------------------------------------------------------------------ réactivité
    def _rho_groupe(self, z_pas: float, poids_pcm: float) -> float:
        """Efficacité intégrale d'un groupe (pcm, ≤ 0) à la position z (0 = inséré), courbe en S."""
        g = self.cfg.grappes
        x = min(max(z_pas / g.pas_max, 0.0), 1.0)
        f = x - math.sin(2.0 * math.pi * x) / (2.0 * math.pi)
        return poids_pcm * (1.0 - f)

    def _rho_regulation(self, z_pas: float) -> float:
        return self._rho_groupe(z_pas, self.cfg.grappes.regulation_pcm)

    def rho_grappes_pcm(self) -> float:
        e, g = self.etat, self.cfg.grappes
        return (self._rho_regulation(e.z_pas) - self.rho_grappes_nom + self._rho_groupe(e.g_pas, g.compensation_pcm)
                + g.arret_pcm * e.arret_insere + e.rho_coincee_pcm * e.arret_insere)

    def rho_moderateur_pcm(self, t_mod_c: float) -> float:
        c = self.cfg
        t0 = c.t_alpha_mod_nul_c
        return c.alpha_mod_pcm_c / (2.0 * (c.t_mod_ref_c - t0)) * ((t_mod_c - t0) ** 2 - (c.t_mod_ref_c - t0) ** 2)

    def rho_doppler_pcm(self, t_comb_c: float) -> float:
        return self.cfg.alpha_doppler_pcm_c * (t_comb_c - self.cfg.combustible.t_nom_c)

    def rho_bore_pcm(self, bore_ppm: float) -> float:
        return self.cfg.alpha_bore_pcm_ppm * (bore_ppm - self.cfg.bore_ppm)

    def reactivite_pcm(self, t_mod_c: float) -> float:
        e = self.etat
        return (self.rho_grappes_pcm() + self.rho_moderateur_pcm(t_mod_c) + self.rho_doppler_pcm(e.t_comb_c)
                + self.rho_bore_pcm(e.bore_ppm))

    def rho_grappes_inserees_pcm(self) -> float:
        """Toutes les grappes insérées (régulation + arrêt), par rapport à la position nominale."""
        g = self.cfg.grappes
        return self._rho_regulation(0.0) - self.rho_grappes_nom + g.compensation_pcm + g.arret_pcm

    def marge_arret_pcm(self, t_mod_c: float, bore_ppm: float, grappe_coincee_pcm: float) -> float:
        """Antiréactivité disponible à l'arrêt, à la température t_mod (combustible à la même température),
        toutes grappes insérées sauf la plus efficace (> 0 : sous-critique)."""
        rho = (self.rho_grappes_inserees_pcm() + grappe_coincee_pcm + self.rho_moderateur_pcm(t_mod_c)
               + self.rho_doppler_pcm(t_mod_c) + self.rho_bore_pcm(bore_ppm))
        return -rho

    def bore_requis_ppm(self, t_mod_c: float, marge_pcm: float, grappe_coincee_pcm: float) -> float:
        """Concentration de bore qui donne la marge d'arrêt visée à la température t_mod."""
        sans_bore = self.marge_arret_pcm(t_mod_c, self.cfg.bore_ppm, grappe_coincee_pcm)
        return self.cfg.bore_ppm + (marge_pcm - sans_bore) / -self.cfg.alpha_bore_pcm_ppm

    @property
    def puissance_pct(self) -> float:
        """Puissance neutronique (chaînes de puissance), % du nominal."""
        return POURCENT * self.etat.n

    @property
    def puissance_fission_kw(self) -> float:
        """Puissance des fissions (hors puissance résiduelle)."""
        return (1.0 - self.fraction_residuelle) * self.etat.n * self.p_nom_kw

    @property
    def puissance_thermique_kw(self) -> float:
        return self.etat.q_caloporteur_kw

    # ------------------------------------------------------------------ grappes
    def chute_grappes(self) -> None:
        self.etat.chute = True

    def rearmer(self) -> None:
        """Après réarmement de l'AU : les grappes restent insérées, pilotage manuel."""
        e = self.etat
        e.chute = False
        e.auto = False
        e.consigne_manu_pas = e.z_pas
        e.consigne_g_pas = e.g_pas

    def bouger_grappes(self, dt: float, vitesse_auto_pas_min: float, retrait_interdit: bool,
                       retrait_auto_interdit: bool) -> None:
        e, g = self.etat, self.cfg.grappes
        if e.chute:
            pas = g.pas_max * dt / g.temps_chute_s
            e.z_pas = max(0.0, e.z_pas - pas)
            e.g_pas = max(0.0, e.g_pas - pas)
            e.consigne_g_pas = e.g_pas
            e.arret_insere = min(1.0, e.arret_insere + dt / g.temps_chute_s)
            e.extraction_arret = False
            e.vitesse_pas_min = 0.0
            return
        if e.extraction_arret and not retrait_interdit:
            e.arret_insere = max(0.0, e.arret_insere - g.vitesse_arret_pas_min / g.pas_max * dt / S_PAR_MIN)
        if e.auto:
            v = vitesse_auto_pas_min
            if v > 0.0 and (retrait_interdit or retrait_auto_interdit):
                v = 0.0
        else:
            ecart = e.consigne_manu_pas - e.z_pas
            v = math.copysign(min(g.vitesse_manu_pas_min, abs(ecart) / dt * S_PAR_MIN), ecart)
            if v > 0.0 and retrait_interdit:
                v = 0.0
        e.vitesse_pas_min = v
        e.z_pas = min(max(e.z_pas + v * dt / S_PAR_MIN, 0.0), g.pas_max)
        # groupe G : toujours manuel
        ecart_g = e.consigne_g_pas - e.g_pas
        v_g = math.copysign(min(g.vitesse_manu_pas_min, abs(ecart_g) / dt * S_PAR_MIN), ecart_g)
        if v_g > 0.0 and retrait_interdit:
            v_g = 0.0
        e.g_pas = min(max(e.g_pas + v_g * dt / S_PAR_MIN, 0.0), g.pas_max)

    def vitesse_auto_pas_min(self, dt: float, tmoy_c: float, charge_turbine_pct: float) -> float:
        """Programme de vitesse (> 0 : extraction) en fonction de l'écart Tmoy − Tref, corrigé par la voie
        « déséquilibre de puissance » (puissance neutronique − charge turbine, filtrée passe-haut) qui
        anticipe et amortit la boucle grappes ↔ température."""
        r = self.cfg.grappes.regulation_tmoy
        e = self.etat
        desequilibre = self.puissance_pct - charge_turbine_pct
        e.desequilibre_retard_pct += (desequilibre - e.desequilibre_retard_pct) * min(1.0, dt / r.desequilibre_constante_s)
        ecart = (tmoy_c - interp_table(r.tref_programme_c, charge_turbine_pct)
                 + r.desequilibre_gain_c_par_pct * (desequilibre - e.desequilibre_retard_pct))
        a = abs(ecart)
        if a < r.bande_morte_c:
            return 0.0
        frac = min(1.0, (a - r.bande_morte_c) / (r.ecart_plein_c - r.bande_morte_c))
        v = r.vitesse_min_pas_min + frac * (r.vitesse_max_pas_min - r.vitesse_min_pas_min)
        return -v if ecart > 0.0 else v

    # ------------------------------------------------------------------ commandes
    def commandes(self) -> list[str]:
        return ["auto", "manu", "position", "position_g", "extraire_arret"]

    def executer(self, action: str, valeur: float | None) -> None:
        e = self.etat
        if action == "auto":
            e.auto = True
        elif action == "manu":
            e.auto = False
            e.consigne_manu_pas = e.z_pas
        elif action == "position" and valeur is not None:
            e.consigne_manu_pas = valeur
        elif action == "position_g" and valeur is not None:
            e.consigne_g_pas = valeur
        elif action == "extraire_arret":
            e.extraction_arret = True

    # ------------------------------------------------------------------ dynamique
    def avancer(self, dt: float, t_mod_c: float) -> None:
        """Cinétique, combustible et résiduelle ; met à jour la chaleur cédée au caloporteur."""
        c, e = self.cfg, self.etat
        rho = min(self.reactivite_pcm(t_mod_c) * PCM, c.rho_max_fraction_beta * self.beta)
        e.rho_pcm = rho / PCM
        e.n = max(0.0, (self.beta * e.g + c.source_neutrons) / (self.beta - rho))
        e.g += c.lambda_s * (e.n - e.g) * dt
        r = c.residuelle
        for i, (f, tau) in enumerate(zip(r.fractions, r.constantes_s)):
            e.p_res_kw[i] += (f * e.n * self.p_nom_kw - e.p_res_kw[i]) * min(1.0, dt / tau)
        p_fission_kw = (1.0 - self.fraction_residuelle) * e.n * self.p_nom_kw
        e.q_caloporteur_kw = (e.t_comb_c - t_mod_c) / self.r_comb_c_kw
        e.t_comb_c += dt * (p_fission_kw + sum(e.p_res_kw) - e.q_caloporteur_kw) / self.c_comb_kj_c

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        e = self.etat
        d.update(puissance_pct=self.puissance_pct, rho_pcm=e.rho_pcm, position_pas=e.z_pas,
                 arret_insere_pct=POURCENT * e.arret_insere, auto=e.auto, chute=e.chute,
                 t_comb_c=e.t_comb_c, bore_ppm=e.bore_ppm, vitesse_pas_min=e.vitesse_pas_min,
                 consigne_manu_pas=e.consigne_manu_pas, position_g_pas=e.g_pas, consigne_g_pas=e.consigne_g_pas)
        return d
