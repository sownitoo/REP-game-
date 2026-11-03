"""Régulations (§4.15) : pression et niveau PZR, niveau GV 3 éléments, ΔP des APP, VDA,
contournement, puits, ASG. (Les grappes sont pilotées dans sim/core_model/coeur.py.)

Elles calculent les demandes « auto » des actionneurs ; un actionneur en manuel
ou sous ordre automatique ne les suit pas.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from sim.components.base import Composant
from sim.components.pid import EtatPI, RegulateurPI
from sim.config import RegulationsCfg
from sim.units import POURCENT, RHO_REF_KG_M3, interp_table, kg_s_vers_m3h

if TYPE_CHECKING:
    from sim.plant import Centrale


class ConsigneReglable(Composant):
    """Consigne d'une régulation, modifiable par le joueur (repère REG_xxx)."""

    type_ui = "regulation"

    def __init__(self, id: str, systeme: str, valeur: float, mini: float, maxi: float, unite: str) -> None:
        super().__init__(id, systeme)
        self.valeur = valeur
        self.mini, self.maxi, self.unite = mini, maxi, unite

    def commandes(self) -> list[str]:
        return ["consigne"]

    def executer(self, action: str, valeur: float | None) -> None:
        if action == "consigne" and valeur is not None:
            self.valeur = valeur

    def exporter_etat(self) -> dict[str, Any]:
        return {"valeur": self.valeur}

    def importer_etat(self, donnees: dict[str, Any]) -> None:
        self.valeur = donnees["valeur"]

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        d.update(consigne=self.valeur, unite=self.unite, mini=self.mini, maxi=self.maxi)
        return d


@dataclass
class EtatRegulations:
    chaufferettes_tor: bool       # groupes tout-ou-rien enclenchés (hystérésis)
    porv_auto: bool               # ouverture automatique des PORV (hystérésis)


class Regulations:
    """Ensemble des régulations automatiques."""

    def __init__(self, cfg: RegulationsCfg, c: Centrale) -> None:
        self.cfg = cfg
        self.c = c
        n = cfg.niveau_gv
        self.pi_niveau = [RegulateurPI(f"PI_NIV_GV{b}", n.kp_debit_pct_par_pct, n.ti_s,
                                       -n.integrale_max_pct, n.integrale_max_pct, 0.0) for b in c.boucles]
        self.pi_debit = [RegulateurPI(f"PI_DEB_GV{b}", n.trim_kp, n.trim_ti_s, 0.0, 1.0, 0.0)
                         for b in c.boucles]
        app = c.apps[0].cfg
        self.pi_dp_app = RegulateurPI("PI_DP_APP", cfg.dp_app.kp_par_bar, cfg.dp_app.ti_s,
                                      app.vitesse_min or 0.0, app.vitesse_max or 1.0, app.vitesse_min or 0.0)
        self.pi_puits = RegulateurPI("PI_PUITS", cfg.puits.kp_par_pct, cfg.puits.ti_s, -1.0, 1.0, 0.0)
        self.reg_vda = ConsigneReglable("REG_VDA", "VVP", cfg.vda.consigne_bar, 0.0,
                                        max(c.cfg.vapeur.soupapes.tarages_bar), "bar")
        self.reg_puits = ConsigneReglable("REG_PUITS", "CEX", cfg.puits.consigne_pct, 0.0, POURCENT, "%")
        pp = cfg.pression_pzr
        self.reg_p_pzr = ConsigneReglable("REG_P_PZR", "RCP", pp.consigne_bar, 0.0,
                                          c.cfg.logique.au.p_pzr_haute_bar, "bar")
        self.pi_p_pzr = RegulateurPI("PI_P_PZR", 1.0, pp.ti_s, -pp.aspersion_pleine_bar, pp.aspersion_pleine_bar, 0.0)
        self.qm_charge_max_kg_s = c.debit_rcv_kg_s(c.cfg.rcv_v1.charge_max_m3h)
        self.pi_niveau_pzr = RegulateurPI("PI_NIV_PZR", cfg.niveau_pzr.kp_kg_s_par_pct, cfg.niveau_pzr.ti_s,
                                          0.0, self.qm_charge_max_kg_s, 0.0)
        na = cfg.niveau_asg
        self.pi_asg = [RegulateurPI(f"PI_ASG{b}", na.kp_par_pct, na.ti_s, 0.0, 1.0, 1.0) for b in c.boucles]
        self.etat = EtatRegulations(chaufferettes_tor=False, porv_auto=False)

    def tous_les_pi(self) -> list[RegulateurPI]:
        return (self.pi_niveau + self.pi_debit + self.pi_asg
                + [self.pi_dp_app, self.pi_puits, self.pi_p_pzr, self.pi_niveau_pzr])

    # ------------------------------------------------------------------ calcul
    def calculer(self, dt: float) -> None:
        c = self.c
        charge = c.turbine.charge_pct
        self._niveau_gv(dt, charge)
        self._dp_app(dt, charge)
        for i, gv in enumerate(c.gvs):
            d = (gv.p_bar - self.reg_vda.valeur) / self.cfg.vda.bande_bar
            c.vapeur.vda[i].etat.demande_auto = min(max(d, 0.0), 1.0)
        c.gct.calculer(c.vapeur.etat.p_collecteur_bar, c.primaire.tmoy_c, c.tref_c())
        u = self.pi_puits.calculer(self.reg_puits.valeur - c.condenseur.niveau_puits_pct(), dt)
        c.vannes["PUITS_APPOINT"].etat.demande_auto = max(u, 0.0)
        c.vannes["PUITS_REJET"].etat.demande_auto = max(-u, 0.0)
        self._pression_pzr(dt)
        self._niveau_pzr(dt)
        self._asg(dt)

    def _pression_pzr(self, dt: float) -> None:
        """Régulateur maître PI (sortie en bar équivalents) → chaufferettes, aspersion, PORV."""
        c, pp, e = self.c, self.cfg.pression_pzr, self.etat
        p = c.pzr.capteur_p.mediane
        u = self.pi_p_pzr.calculer(p - self.reg_p_pzr.valeur, dt)
        prop = (pp.proportionnelles_nulles_bar - u) / (pp.proportionnelles_nulles_bar - pp.proportionnelles_pleines_bar)
        c.pzr.chauffe_prop.etat.demande_auto = min(max(prop, 0.0), 1.0)
        if u < pp.tor_marche_bar:
            e.chaufferettes_tor = True
        elif u > pp.tor_arret_bar:
            e.chaufferettes_tor = False
        c.pzr.chauffe_tor.etat.demande_auto = float(e.chaufferettes_tor)
        asp = (u - pp.aspersion_debut_bar) / (pp.aspersion_pleine_bar - pp.aspersion_debut_bar)
        for v in c.pzr.aspersion:
            v.etat.demande_auto = min(max(asp, 0.0), 1.0)
        if p > pp.porv_ouverture_bar:
            e.porv_auto = True
        elif p < pp.porv_fermeture_bar:
            e.porv_auto = False
        for v in c.pzr.porv:
            v.etat.demande_auto = float(e.porv_auto)

    def _niveau_pzr(self, dt: float) -> None:
        """Débit de charge = débit de décharge (anticipation) + PI sur l'écart au programme de niveau."""
        c = self.c
        consigne = c.pzr.niveau_programme_pct(c.primaire.tmoy_c)
        qm = self.pi_niveau_pzr.calculer(consigne - c.pzr.capteur_niveau.mediane, dt,
                                         anticipation=c.qm_decharge_kg_s())
        c.vannes["RCV_CHARGE"].etat.demande_auto = qm / self.qm_charge_max_kg_s

    def _asg(self, dt: float) -> None:
        """Vannes ASG : PI sur le niveau GV (consigne sous celle de l'ARE)."""
        c, na = self.c, self.cfg.niveau_asg
        for i, gv in enumerate(c.gvs):
            c.asg.vannes[i].etat.demande_auto = self.pi_asg[i].calculer(na.consigne_pct - gv.capteur.mediane, dt)

    def _niveau_gv(self, dt: float, charge: float) -> None:
        """3 éléments : le niveau corrige un débit de consigne = débit vapeur ± correction ;
        les vannes PD puis GD (en cascade) sont positionnées par anticipation (Kv requis) + PI de débit."""
        c, n = self.c, self.cfg.niveau_gv
        p_are = c.poste_eau.p("N_ARE")
        rho = c.poste_eau.table.rho_liq_kg_m3(c.poste_eau.etat.t_ahp_c)
        for i, gv in enumerate(c.gvs):
            qm_nom = gv.cfg.debit_vapeur_nom_kg_s
            consigne = interp_table(gv.cfg.programme_niveau_pct, charge)
            correction_pct = self.pi_niveau[i].calculer(consigne - gv.capteur.mediane, dt)
            qm_consigne = gv.etat.qm_ligne_kg_s + qm_nom * correction_pct / POURCENT
            qm_consigne = min(max(qm_consigne, 0.0), qm_nom * n.debit_max_pct / POURCENT)
            gd, pd = c.vannes[f"ARE{gv.b}_GD"], c.vannes[f"ARE{gv.b}_PD"]
            kv_gd, kv_pd = gd.cfg.kv_max or 0.0, pd.cfg.kv_max or 0.0
            dp = max(p_are - gv.p_bar, n.dp_min_bar)
            kv_requis = kg_s_vers_m3h(qm_consigne, rho) * math.sqrt(rho / RHO_REF_KG_M3 / dp)
            anticipation = kv_requis / (kv_gd + kv_pd)
            erreur = (qm_consigne - gv.etat.qm_alim_kg_s) / qm_nom
            d = self.pi_debit[i].calculer(erreur, dt, anticipation)
            d1 = kv_pd / (kv_gd + kv_pd)
            pd.etat.demande_auto = min(max(d / d1, 0.0), 1.0)
            gd.etat.demande_auto = min(max((d - d1) / (1.0 - d1), 0.0), 1.0)

    def _dp_app(self, dt: float, charge: float) -> None:
        """Vitesse des APP : ΔP (refoulement ARE − collecteur vapeur) = programme(charge)."""
        c = self.c
        consigne = interp_table(self.cfg.dp_app.consigne_bar, charge)
        dp = c.poste_eau.p("N_ARE") - c.vapeur.etat.p_collecteur_bar
        if any(a.etat.en_marche for a in c.apps):
            vitesse = self.pi_dp_app.calculer(consigne - dp, dt)
        else:
            vitesse = self.pi_dp_app.sortie_min
            self.pi_dp_app.initialiser(vitesse)
        for a in c.apps:
            a.etat.consigne_auto = vitesse

    # ------------------------------------------------------------------ sauvegarde
    def exporter_etat(self) -> dict[str, Any]:
        d: dict[str, Any] = {pi.id: asdict(pi.etat) for pi in self.tous_les_pi()}
        d["_etat"] = asdict(self.etat)
        return d

    def importer_etat(self, donnees: dict[str, Any]) -> None:
        for pi in self.tous_les_pi():
            pi.etat = EtatPI(**donnees[pi.id])
        self.etat = EtatRegulations(**donnees["_etat"])
