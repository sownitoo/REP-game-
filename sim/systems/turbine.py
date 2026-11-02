"""Turbine (GRE) + alternateur : vannes d'arrêt et de réglage, vitesse, couplage, puissance.

Débit admis (débit critique) : ṁ = K · y_réglage · (ouverture moyenne des vannes d'arrêt) · P_collecteur
Puissance mécanique : P = η_is · Δh_is(P_adm → P_cond) · ṁ · (1 − f_sout · part_travail)
Découplée : ½·J·ω² varie de (P_méca − P_pertes) ; couplée : vitesse imposée par le réseau.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from sim.components.base import Composant
from sim.components.pid import RegulateurPI
from sim.config import TurbineCfg
from sim.thermo.tables import TableEau
from sim.units import KW_PAR_MW, POURCENT, S_PAR_MIN

EXPOSANT_VENTILATION = 3      # loi physique : pertes par ventilation ∝ vitesse³


@dataclass
class EtatTurbine:
    declenchee: bool
    cause: str
    positions_arret: list[float]
    y_reglage: float
    demande_reglage: float
    vitesse_tr_min: float
    couplee: bool
    consigne_mw: float
    consigne_eff_mw: float
    consigne_vitesse_tr_min: float
    consigne_vitesse_eff_tr_min: float
    qm_kg_s: float
    dh_is_kj_kg: float
    p_meca_mw: float
    p_elec_mw: float


class Turbine(Composant):
    """Groupe turbo-alternateur (repère TURBINE)."""

    type_ui = "turbine"

    def __init__(self, cfg: TurbineCfg, table: TableEau) -> None:
        super().__init__("TURBINE", "GRE")
        self.cfg = cfg
        self.table = table
        self.k_kg_s_bar_max = cfg.debit_nom_kg_s / (cfg.ouverture_nom * cfg.p_admission_nom_bar)
        rc, rv = cfg.regulation_charge, cfg.regulation_vitesse
        self.pi_charge = RegulateurPI("PI_CHARGE", rc.kp, rc.ti_s, -1.0, 1.0, 0.0)
        self.pi_vitesse = RegulateurPI("PI_VITESSE", rv.kp, rv.ti_s, 0.0, 1.0, 0.0)
        n = cfg.vitesse_nom_tr_min
        self.etat = EtatTurbine(declenchee=True, cause="arrêt", positions_arret=[0.0] * cfg.vannes_arret,
                                y_reglage=0.0, demande_reglage=0.0, vitesse_tr_min=0.0, couplee=False,
                                consigne_mw=0.0, consigne_eff_mw=0.0, consigne_vitesse_tr_min=n,
                                consigne_vitesse_eff_tr_min=0.0, qm_kg_s=0.0, dh_is_kj_kg=0.0,
                                p_meca_mw=0.0, p_elec_mw=0.0)

    # ------------------------------------------------------------------ grandeurs
    @property
    def charge_pct(self) -> float:
        """Charge turbine = débit admis / débit nominal."""
        return POURCENT * self.etat.qm_kg_s / self.cfg.debit_nom_kg_s

    def arret_ferme(self) -> bool:
        """4/4 vannes d'arrêt fermées."""
        return all(p <= 0.0 for p in self.etat.positions_arret)

    def k_kg_s_bar(self) -> float:
        ouverture_arret = sum(self.etat.positions_arret) / len(self.etat.positions_arret)
        return self.k_kg_s_bar_max * self.etat.y_reglage * ouverture_arret

    def mw_par_kg_s(self) -> float:
        """MW électriques produits par kg/s de vapeur admise (au Δh isentrope actuel)."""
        c = self.cfg
        return (c.rendement_alternateur * c.eta_isentropique * self.etat.dh_is_kj_kg
                * (1.0 - c.fraction_soutirage * c.part_travail_soutirage) / KW_PAR_MW)

    # ------------------------------------------------------------------ commandes
    def commandes(self) -> list[str]:
        return ["declencher", "rearmer", "consigne_vitesse", "coupler", "decoupler", "consigne_mw"]

    def declencher(self, cause: str) -> None:
        if not self.etat.declenchee:
            self.etat.declenchee = True
            self.etat.cause = cause
        self.etat.couplee = False      # protection retour de puissance : le disjoncteur s'ouvre

    def executer(self, action: str, valeur: float | None) -> None:
        e = self.etat
        if action == "declencher":
            self.declencher("manuel")
        elif action == "rearmer":
            e.declenchee = False
            e.cause = ""
            e.consigne_vitesse_eff_tr_min = e.vitesse_tr_min
            e.consigne_vitesse_tr_min = e.vitesse_tr_min
            self.pi_vitesse.initialiser(e.y_reglage)
        elif action == "consigne_vitesse" and valeur is not None:
            e.consigne_vitesse_tr_min = valeur
        elif action == "coupler":
            e.couplee = True
            e.consigne_mw = e.consigne_eff_mw = max(e.p_elec_mw, 0.0)
            self.pi_charge.initialiser(0.0)
        elif action == "decoupler":
            e.couplee = False
            e.consigne_vitesse_eff_tr_min = e.consigne_vitesse_tr_min = self.cfg.vitesse_nom_tr_min
            self.pi_vitesse.initialiser(e.y_reglage)
        elif action == "consigne_mw" and valeur is not None:
            e.consigne_mw = valeur
            echelon = self.cfg.regulation_charge.echelon_max_pct / POURCENT * self.cfg.p_elec_nom_mw
            if abs(valeur - e.consigne_eff_mw) <= echelon:
                e.consigne_eff_mw = valeur

    # ------------------------------------------------------------------ régulation + vannes
    def reguler(self, dt: float, p_collecteur_bar: float) -> None:
        """Calcule la demande des vannes de réglage puis fait bouger les vannes."""
        c, e = self.cfg, self.etat
        if e.declenchee:
            pas = dt / c.temps_fermeture_arret_s
            e.positions_arret = [max(0.0, p - pas) for p in e.positions_arret]
            e.demande_reglage = 0.0
        else:
            pas = dt / c.temps_ouverture_arret_s
            e.positions_arret = [min(1.0, p + pas) for p in e.positions_arret]
            if e.couplee:
                rampe = c.regulation_charge.rampe_pct_min / POURCENT * c.p_elec_nom_mw * dt / S_PAR_MIN
                e.consigne_eff_mw += max(-rampe, min(rampe, e.consigne_mw - e.consigne_eff_mw))
                # anticipation : ouverture qui donnerait la consigne au Δh et à la pression actuels
                debit_max = self.k_kg_s_bar_max * p_collecteur_bar
                mw_kg = self.mw_par_kg_s()
                anticipation = e.consigne_eff_mw / mw_kg / debit_max if mw_kg > 0.0 else 0.0
                erreur = (e.consigne_eff_mw - e.p_elec_mw) / c.p_elec_nom_mw
                correction = self.pi_charge.calculer(erreur, dt)
                e.demande_reglage = min(max(anticipation + correction, 0.0), 1.0)
            else:
                rampe = c.regulation_vitesse.rampe_pct_min / POURCENT * c.vitesse_nom_tr_min * dt / S_PAR_MIN
                e.consigne_vitesse_eff_tr_min += max(-rampe, min(rampe, e.consigne_vitesse_tr_min
                                                                  - e.consigne_vitesse_eff_tr_min))
                erreur = (e.consigne_vitesse_eff_tr_min - e.vitesse_tr_min) / c.vitesse_nom_tr_min
                e.demande_reglage = self.pi_vitesse.calculer(erreur, dt)
        pas = dt / c.temps_course_reglage_s
        e.y_reglage += max(-pas, min(pas, e.demande_reglage - e.y_reglage))

    # ------------------------------------------------------------------ puissance + vitesse
    def calculer_puissance(self, dt: float, qm_kg_s: float, p_adm_bar: float, p_cond_bar: float) -> None:
        c, e = self.cfg, self.etat
        e.qm_kg_s = qm_kg_s
        s_adm = self.table.sat(p_adm_bar)
        e.dh_is_kj_kg = max(0.0, s_adm.hg_kj_kg - self.table.h_isentrope_kj_kg(s_adm.sg_kj_kgk, p_cond_bar))
        e.p_meca_mw = self.mw_par_kg_s() * qm_kg_s / c.rendement_alternateur
        n_nom = c.vitesse_nom_tr_min
        if e.couplee:
            e.vitesse_tr_min = n_nom
            e.p_elec_mw = c.rendement_alternateur * e.p_meca_mw
        else:
            e.p_elec_mw = 0.0
            nu = e.vitesse_tr_min / n_nom
            pertes = c.pertes_ventilation_pct / POURCENT * c.puissance_apparente_mva * nu ** EXPOSANT_VENTILATION
            # d(ν²)/dt = (P_méca − P_pertes) / (H·S)
            nu2 = nu * nu + dt * (e.p_meca_mw - pertes) / (c.constante_inertie_s * c.puissance_apparente_mva)
            e.vitesse_tr_min = n_nom * math.sqrt(max(0.0, nu2))

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        e = self.etat
        d.update(declenchee=e.declenchee, cause=e.cause, couplee=e.couplee,
                 vitesse_tr_min=e.vitesse_tr_min, p_elec_mw=e.p_elec_mw, consigne_mw=e.consigne_mw,
                 consigne_eff_mw=e.consigne_eff_mw, consigne_vitesse_tr_min=e.consigne_vitesse_tr_min,
                 ouverture_reglage_pct=POURCENT * e.y_reglage,
                 ouverture_arret_pct=POURCENT * sum(e.positions_arret) / len(e.positions_arret))
        return d

    def exporter_etat(self) -> dict[str, Any]:
        d = super().exporter_etat()
        d["_pi_charge"] = vars(self.pi_charge.etat).copy()
        d["_pi_vitesse"] = vars(self.pi_vitesse.etat).copy()
        return d

    def importer_etat(self, donnees: dict[str, Any]) -> None:
        donnees = dict(donnees)
        self.pi_charge.etat = type(self.pi_charge.etat)(**donnees.pop("_pi_charge"))
        self.pi_vitesse.etat = type(self.pi_vitesse.etat)(**donnees.pop("_pi_vitesse"))
        super().importer_etat(donnees)
