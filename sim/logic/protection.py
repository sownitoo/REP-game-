"""Protection réacteur (RPR, §4.14) : arrêt automatique (AU), P-4, mémorisation et réarmement.

Signaux d'AU V1 (votes de la spec) :
- manuel ; flux puissance haut (109 %) ; flux seuil bas (25 %, bloquable au-dessus de P-10) ;
- variation rapide de flux ± 5 % ; ΔT surtempérature ; ΔT surpuissance ;
- pression PZR basse (P-7) / haute ; niveau PZR haut (P-7) ;
- débit primaire bas (1 boucle au-dessus de P-8, 2 boucles au-dessus de P-7) ;
- pompes primaires arrêtées 2/4 (P-7) ; niveau GV très bas ; débit eau insuffisant ;
- déclenchement turbine au-dessus de P-7.
Ordre d'évaluation : permissifs → seuils ΔT → causes d'AU → automatismes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

from sim.components.base import Composant
from sim.core.events import PRIORITE_HAUTE
from sim.logic.automatismes import appliquer_automatismes
from sim.logic.permissives import calculer_permissifs
from sim.logic.voting import vote
from sim.units import POURCENT

if TYPE_CHECKING:
    from sim.plant import Centrale


@dataclass
class EtatLogique:
    au: bool = False
    au_causes: list[str] = field(default_factory=list)   # causes mémorisées à l'apparition de l'AU
    au_t_s: float = 0.0
    au_manuel: bool = False                               # demande manuelle en attente
    p4: bool = False
    p7: bool = False
    p8: bool = False
    p9: bool = False
    p10: bool = True
    p12: bool = False
    p13: bool = False
    p14: bool = False
    p14_gv: list[bool] = field(default_factory=list)
    niveau_tres_bas_gv: list[bool] = field(default_factory=list)
    c2: bool = False
    c3: bool = False
    c4: bool = False
    c5: bool = False
    c7: bool = False
    c8: bool = False
    c9: bool = False
    c11: bool = False
    flux_bas_bloque: bool = True
    causes_au: list[str] = field(default_factory=list)          # causes présentes
    causes_turbine: list[str] = field(default_factory=list)     # causes présentes
    isolement_are_au: bool = False
    isolement_are_complet: bool = False                   # mémorisé (P-14), réarmement opérateur
    tempo_aspiration_app_s: list[float] = field(default_factory=list)
    recirc_cex: bool = True
    app_declenchee: bool = False
    cex_declenchee: bool = False
    app_en_service: bool = True                           # pour détecter la perte des 2 APP
    decharge_isolee: bool = False
    # filtres des protections ΔT et de la variation de flux
    flux_retard_pct: float = 0.0
    otdt_retard_c: list[float] = field(default_factory=list)
    opdt_retard_c: list[float] = field(default_factory=list)
    otdt_seuil_c: list[float] = field(default_factory=list)
    opdt_seuil_c: list[float] = field(default_factory=list)


class Logique(Composant):
    """Protection et automatismes (repère RPR)."""

    type_ui = "logique"

    def __init__(self, c: Centrale) -> None:
        super().__init__("RPR", "RPR")
        self.c = c
        n = len(c.gvs)
        self.etat = EtatLogique(p14_gv=[False] * n, niveau_tres_bas_gv=[False] * n,
                                tempo_aspiration_app_s=[0.0] * len(c.apps),
                                otdt_retard_c=[0.0] * n, opdt_retard_c=[0.0] * n,
                                otdt_seuil_c=[0.0] * n, opdt_seuil_c=[0.0] * n)

    def initialiser_filtres(self) -> None:
        """Place les filtres à l'équilibre (pas de faux signal au démarrage)."""
        e, c = self.etat, self.c
        e.flux_retard_pct = c.coeur.puissance_pct
        e.otdt_retard_c = [c.primaire.tmoy_boucle_c(i) for i in range(len(c.boucles))]
        e.opdt_retard_c = list(e.otdt_retard_c)
        self._seuils_dt(0.0)

    # ------------------------------------------------------------------ ΔT surtempérature / surpuissance
    def _seuils_dt(self, dt: float) -> None:
        """Seuils ΔT par boucle (§4.14) : avance-retard sur Tmoy pour la surtempérature,
        dérivée filtrée de Tmoy (montée seulement) pour la surpuissance."""
        e, c = self.etat, self.c
        ot, op = c.cfg.logique.otdt, c.cfg.logique.opdt
        p = c.pzr.capteur_p.mediane
        for i in range(len(c.boucles)):
            tmoy = c.primaire.tmoy_boucle_c(i)
            if dt > 0.0:
                e.otdt_retard_c[i] += (tmoy - e.otdt_retard_c[i]) * min(1.0, dt / ot.tau2_s)
                e.opdt_retard_c[i] += (tmoy - e.opdt_retard_c[i]) * min(1.0, dt / op.tau3_s)
            # (1 + τ1 s)/(1 + τ2 s) = τ1/τ2 + (1 − τ1/τ2) / (1 + τ2 s)
            r = ot.tau1_s / ot.tau2_s
            t_avance = r * tmoy + (1.0 - r) * e.otdt_retard_c[i]
            e.otdt_seuil_c[i] = ot.dt0_c * (ot.k1 - ot.k2_par_c * (t_avance - ot.t_ref_c)
                                            + ot.k3_par_bar * (p - ot.p_ref_bar))
            montee = max(0.0, tmoy - e.opdt_retard_c[i])
            e.opdt_seuil_c[i] = ot.dt0_c * (op.k4 - op.k5_par_c * montee
                                            - op.k6_par_c * max(0.0, tmoy - op.t_ref_c))

    def marges_dt_pct(self) -> tuple[float, float]:
        """Marge minimale (en % du seuil) vis-à-vis de l'AU ΔT surtempérature et surpuissance."""
        e, c = self.etat, self.c
        dts = [c.primaire.dt_boucle_c(i) for i in range(len(c.boucles))]
        m_ot = min(POURCENT * (s - d) / s for s, d in zip(e.otdt_seuil_c, dts))
        m_op = min(POURCENT * (s - d) / s for s, d in zip(e.opdt_seuil_c, dts))
        return m_ot, m_op

    # ------------------------------------------------------------------ causes d'AU
    def causes_au_presentes(self) -> list[str]:
        e, c = self.etat, self.c
        lg = c.cfg.logique
        au, votes = lg.au, lg.au.votes
        causes: list[str] = []
        flux = c.voies_flux_pct()
        if vote(votes.flux, [x > au.flux_haut_pct for x in flux]):
            causes.append(f"flux puissance > {au.flux_haut_pct:g} %")
        if not e.flux_bas_bloque and vote(votes.flux, [x > au.flux_bas_pct for x in flux]):
            causes.append(f"flux puissance seuil bas > {au.flux_bas_pct:g} %")
        ecart = flux[0] - e.flux_retard_pct
        if vote(votes.flux, [abs(x - e.flux_retard_pct) > au.variation_flux_pct for x in flux]):
            causes.append(f"variation rapide de flux {'positive' if ecart > 0 else 'négative'}")
        dts = [c.primaire.dt_boucle_c(i) for i in range(len(c.boucles))]
        if vote(votes.dt, [d > s for d, s in zip(dts, e.otdt_seuil_c)]):
            causes.append("ΔT surtempérature")
        if vote(votes.dt, [d > s for d, s in zip(dts, e.opdt_seuil_c)]):
            causes.append("ΔT surpuissance")
        voies_p = c.pzr.capteur_p.etat.valeurs
        if vote(votes.p_pzr, [p > au.p_pzr_haute_bar for p in voies_p]):
            causes.append(f"pression PZR haute (> {au.p_pzr_haute_bar:g} bar)")
        if not e.p7:
            if vote(votes.p_pzr, [p < au.p_pzr_basse_bar for p in voies_p]):
                causes.append(f"pression PZR basse (< {au.p_pzr_basse_bar:g} bar)")
            if vote(votes.niveau_pzr, c.pzr.capteur_niveau.depasse(au.niveau_pzr_haut_pct, au_dessus=True)):
                causes.append(f"niveau PZR haut (> {au.niveau_pzr_haut_pct:g} %)")
            arretees = [not p.etat.en_marche for p in c.primaire.pompes]
            if vote(votes.pompes, arretees):
                causes.append("disjoncteurs de pompes primaires ouverts (2/4)")
        voies_debit = int(votes.debit.split("/")[1])     # voies identiques par boucle (pas de panne en V1)
        boucles_bas = [b for i, b in enumerate(c.boucles)
                       if vote(votes.debit, [c.primaire.debit_pct(i) < au.debit_bas_pct] * voies_debit)]
        if (len(boucles_bas) >= 1 and not e.p8) or (len(boucles_bas) >= 2 and not e.p7):
            causes.append("débit primaire bas boucle " + ", ".join(f"B{b}" for b in boucles_bas))
        for i, gv in enumerate(c.gvs):
            if e.niveau_tres_bas_gv[i]:
                causes.append(f"niveau très bas GV{gv.b}")
            ecart_pct = POURCENT * (gv.etat.qm_ligne_kg_s - gv.etat.qm_alim_kg_s) / gv.cfg.debit_vapeur_nom_kg_s
            if ecart_pct > au.ecart_vapeur_eau_pct and vote(
                    c.cfg.generateurs_vapeur.seuils.vote, gv.capteur.depasse(au.niveau_gv_bas_pct, au_dessus=False)):
                causes.append(f"débit d'eau insuffisant GV{gv.b}")
        if c.turbine.arret_ferme() and not e.p7:
            causes.append("déclenchement turbine au-dessus de P-7")
        return causes

    def evaluer(self, dt: float) -> None:
        c, e = self.c, self.etat
        calculer_permissifs(c, e)
        self._seuils_dt(dt)
        cfg_au = c.cfg.logique.au
        e.flux_retard_pct += (c.coeur.puissance_pct - e.flux_retard_pct) * min(1.0, dt / cfg_au.variation_flux_constante_s)
        if c.inhiber_protections:          # stabilisation de l'état initial uniquement
            e.causes_au, e.p14, e.p14_gv = [], False, [False] * len(c.gvs)
            appliquer_automatismes(c, e, dt)
            return
        e.causes_au = self.causes_au_presentes()
        if e.au_manuel:
            e.causes_au = ["manuel"] + e.causes_au
            e.au_manuel = False
        if e.causes_au and not e.au:
            e.au = True
            e.au_causes = list(e.causes_au)
            e.au_t_s = c.t_s
            c.journal.ajouter(c.t_s, "automatisme", f"AU : {', '.join(e.au_causes)}", PRIORITE_HAUTE)
        if e.au:
            c.coeur.chute_grappes()
        e.p4 = e.au
        appliquer_automatismes(c, e, dt)

    # ------------------------------------------------------------------ commandes
    def commandes(self) -> list[str]:
        return ["declencher_au", "rearmer_au", "bloquer_flux_bas", "debloquer_flux_bas", "rearmer_isolement_are"]

    def executer(self, action: str, valeur: float | None) -> None:
        e = self.etat
        if action == "declencher_au":
            e.au_manuel = True
        elif action == "rearmer_au":
            e.au = False
            e.au_causes = []
            e.p4 = False
            self.c.coeur.rearmer()
        elif action == "bloquer_flux_bas":
            e.flux_bas_bloque = True
        elif action == "debloquer_flux_bas":
            e.flux_bas_bloque = False
        elif action == "rearmer_isolement_are":
            e.isolement_are_complet = False

    def exporter_etat(self) -> dict[str, Any]:
        return asdict(self.etat)

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        d.update(asdict(self.etat))
        return d
