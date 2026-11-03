"""Assemblage de la centrale et boucle de calcul d'un pas de temps (§2.3).

Ordre d'un pas :
  1. commandes joueur (appliquées dès réception, entre deux pas)
  2. pannes programmées, électricité (tableaux, diesels, batteries), air comprimé
  3. logique : capteurs → permissifs → AU → IS / isolement vapeur / phase B → automatismes
  4. régulations → demandes des actionneurs, puis mouvement des actionneurs et des grappes
  5. hydraulique : primaire (+ RRA), collecteur vapeur, eau alimentaire, ASG
  6. thermique : cœur, RRA, accumulateurs, brèches, RIS / EAS, RCV/REA (bore), primaire, pressuriseur
     (+ vide primaire), PRT, enceinte, GV, turbine, condenseur, bâches, réchauffeurs, RRI/SEC
  7. mesures, alarmes, historique
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from sim.components.base import Composant, Condition, Sources
from sim.components.pump import Pompe
from sim.components.valve import Clapet, Resistance, Vanne
from sim.config import (CentraleCfg, ClapetCfg, PompeCfg, ResistanceCfg, VanneCfg, charger_config)
from sim.core.events import PRIORITE_HAUTE, PRIORITE_INFO, GestionAlarmes, Journal
from sim.core.history import Historique
from sim.core_model.coeur import PCM, Coeur
from sim.logic import interlocks
from sim.logic.protection import Logique
from sim.logic.regulations import Regulations
from sim.electrical.reseau import Diesel, Electricite, TableauSecouru
from sim.scenarios import pannes
from sim.scenarios.formateur import Formateur
from sim.systems.accumulateurs import Accumulateurs
from sim.systems.air import AirComprime
from sim.systems.asg import ASG
from sim.systems.breches import Breches
from sim.systems.enceinte import PRT, Enceinte
from sim.systems.condenseur import Condenseur
from sim.systems.gct import Contournement
from sim.systems.gv import GenerateurVapeur
from sim.systems.joints import DEBIT_INJECTION_MIN_M3H, JointsPP
from sim.systems.poste_eau import PosteEau
from sim.systems.pzr import Pressuriseur
from sim.systems.rcp import COEUR, DESCENTE, PLENUM, CircuitPrimaire, bc, bf, gvp
from sim.systems.rcv import RCV, Rea
from sim.systems.rra import RRA
from sim.systems.ris import RIS
from sim.systems.rri import RRI
from sim.systems.turbine import Turbine
from sim.systems.vvp import Vapeur
from sim.thermo.tables import obtenir_table
from sim.units import KG_PAR_T, KW_PAR_MW, POURCENT, S_PAR_H, interp_table

VERSION_SAUVEGARDE = 5
PUISARD_REFERENCE_M3 = 2000.0     # échelle d'affichage du niveau des puisards
P_ASPIRATION_RIS_BAR = 1.0        # aspiration des pompes d'injection (PTR / puisards ~ pression atmosphérique)
ENERGIE_FISSION_J = 3.2e-11       # ~200 MeV récupérés par fission
W_PAR_KW = 1.0e3
PERIODE_INFINIE_S = 1.0e9         # réacteur critique : période infinie (affichée « ∞ »)
CONSTANTE_VITESSE_S = 300.0       # filtrage de la vitesse de refroidissement instantanée
PAS_ECHANTILLON_S = 60.0          # fenêtre glissante d'une heure : 60 échantillons d'une minute
NB_ECHANTILLONS = 60


@dataclass
class EtatSuivi:
    """Vitesse de refroidissement : « instantanée » (dérivée filtrée, pour la régulation RRA) et sur
    une heure glissante (baisse de Tmoy sur la dernière heure, pour la limite d'exploitation)."""

    tmoy_prec_c: float = 0.0
    vitesse_instantanee_c_h: float = 0.0
    vitesse_refroidissement_c_h: float = 0.0
    echantillons_c: list[float] = field(default_factory=list)   # Tmoy toutes les PAS_ECHANTILLON_S
    temps_echantillon_s: float = 0.0


class Suivi:
    def __init__(self, tmoy_c: float) -> None:
        self.etat = EtatSuivi(tmoy_prec_c=tmoy_c, echantillons_c=[tmoy_c] * NB_ECHANTILLONS)

    def avancer(self, dt: float, tmoy_c: float) -> None:
        e = self.etat
        brute = (e.tmoy_prec_c - tmoy_c) / dt * S_PAR_H if dt > 0.0 else 0.0
        e.vitesse_instantanee_c_h += (brute - e.vitesse_instantanee_c_h) * min(1.0, dt / CONSTANTE_VITESSE_S)
        e.tmoy_prec_c = tmoy_c
        e.temps_echantillon_s += dt
        if e.temps_echantillon_s >= PAS_ECHANTILLON_S:
            e.temps_echantillon_s = 0.0
            e.echantillons_c = e.echantillons_c[1:] + [tmoy_c]
        if not e.echantillons_c:                     # sauvegarde sans historique
            e.echantillons_c = [tmoy_c] * NB_ECHANTILLONS
        e.vitesse_refroidissement_c_h = max(0.0, max(e.echantillons_c) - tmoy_c)

    def initialiser(self, tmoy_c: float) -> None:
        self.etat = EtatSuivi(tmoy_prec_c=tmoy_c, echantillons_c=[tmoy_c] * NB_ECHANTILLONS)


@dataclass
class Reponse:
    """Réponse à une commande joueur."""

    ok: bool
    raisons: list[str]


class Centrale:
    """Centrale V4 : primaire 4 boucles + PZR (primaire saturé / plein d'eau) + cœur, RCV/REA, RRA, RRI/SEC,
    accumulateurs, secondaire, ASG, électricité (réseau, tableaux, diesels, séquenceurs, batteries), air comprimé,
    joints des pompes primaires, RIS (HP / MP / BP, recirculation), EAS, enceinte, PRT, brèches."""

    def __init__(self, cfg: CentraleCfg | None = None) -> None:
        self.cfg = cfg = cfg or charger_config()
        n = cfg.numerique
        self.table = obtenir_table(n.table_p_min_bar, n.table_p_max_bar, n.table_nb_points, n.table_t_pas_c,
                                   n.table_p_liquide_bar)
        self.boucles = cfg.generateurs_vapeur.boucles
        self.dt_s = cfg.simulation.dt_s
        self.t_s = 0.0
        self.inhiber_protections = False    # utilisé seulement pour stabiliser l'état initial
        self.journal = Journal(cfg.simulation.journal_max)
        self.alarmes = GestionAlarmes(cfg.alarmes, n.alarmes_hysteresis_pct, n.alarmes_temporisation_s)
        self.historique = Historique(cfg.simulation.historique_duree_s, cfg.simulation.historique_pas_s,
                                     cfg.simulation.dt_s)
        self.mesures: dict[str, float] = {}
        self._qm_turbine = 0.0
        self._qm_gct = 0.0

        # --- composants génériques ---
        self.composants: dict[str, Composant] = {}
        for rep, cc in cfg.composants.items():
            if isinstance(cc, PompeCfg):
                self.composants[rep] = Pompe(rep, cc)
            elif isinstance(cc, VanneCfg):
                self.composants[rep] = Vanne(rep, cc, 0.0)
            elif isinstance(cc, ClapetCfg):
                self.composants[rep] = Clapet(rep, cc)
            elif isinstance(cc, ResistanceCfg):
                self.composants[rep] = Resistance(rep, cc)
        self.pompes = {k: v for k, v in self.composants.items() if isinstance(v, Pompe)}
        self.vannes = {k: v for k, v in self.composants.items() if isinstance(v, Vanne)}
        self.apps = [p for p in self.pompes.values() if p.cfg.systeme == "APP" and p.cfg.vitesse_variable]
        self.cexs = [p for p in self.pompes.values() if p.cfg.systeme == "CEX"]
        self.crfs = [p for p in self.pompes.values() if p.cfg.systeme == "CRF"]

        # --- systèmes ---
        nom = cfg.point_nominal
        p_atm = cfg.simulation.p_atm_bar
        self.coeur = Coeur(cfg.coeur)
        self.primaire = CircuitPrimaire(cfg.primaire, cfg.reseaux["primaire"], self.composants, n, self.table,
                                        self.boucles, nom.tmoy_c)
        self.pzr = Pressuriseur(cfg.pressuriseur, self.composants, self.table, n.flash, cfg.primaire.boucles_aspersion)
        self.gvs = [GenerateurVapeur(b, cfg.generateurs_vapeur, self.table, n.flash) for b in self.boucles]
        self.vapeur = Vapeur(cfg.vapeur, self.boucles, self.composants, self.table, n.collecteur)
        self.turbine = Turbine(cfg.turbine, self.table)
        self.gct = Contournement(cfg.gct_c, self.composants, POURCENT)
        self.condenseur = Condenseur(cfg.condenseur, cfg.puits, cfg.cst, self.crfs, self.table, cfg.condenseur.t_mer_c)
        debit_purges_nom = cfg.turbine.fraction_soutirage * cfg.turbine.debit_nom_kg_s
        self.poste_eau = PosteEau(cfg.poste_eau, cfg.reseaux["eau_alimentaire"], self.composants, n,
                                  self.table, debit_purges_nom, cfg.condenseur.t_mer_c, p_atm)
        self.asg = ASG(cfg.asg, cfg.reseaux["asg"], self.composants, n, self.table, self.boucles, cfg.cst.t_c, p_atm)
        self.rea = Rea(cfg.rea)
        self.rcv = RCV(cfg.rcv, self.rea, self.composants, cfg.coeur.bore_ppm, self.table.rho_liq_kg_m3(cfg.rcv.t_vct_c))
        self.rra = RRA(cfg.rra, self.composants)
        self.rri = RRI(cfg.rri, cfg.sec, self.composants)
        self.accus = Accumulateurs(cfg.accumulateurs, self.composants, self.boucles,
                                   self.table.rho_liq_kg_m3(cfg.accumulateurs.t_c))
        self.suivi = Suivi(nom.tmoy_c)
        self.elec = Electricite(cfg.electricite, self.pompes)
        self.air = AirComprime(cfg.air_comprime, [self.pompes["SAR_C1"], self.pompes["SAR_C2"]])
        self.joints = JointsPP(cfg.joints_pp, len(self.boucles))
        self.pannes: list[dict[str, Any]] = []
        self.ris = RIS(cfg.ris, cfg.enceinte, self.composants, self.rra.pompes)
        self.enceinte = Enceinte(cfg.enceinte, self.table)
        self.prt = PRT(cfg.prt, self.table)
        self.breches = Breches(cfg.breches, len(self.boucles))
        self.formateur = Formateur(self)
        self.logique = Logique(self)
        self.regulations = Regulations(cfg.regulations, self)

        # --- objets manœuvrables par le joueur ---
        r = self.regulations
        self.commandables: dict[str, Composant] = {
            **self.pompes, **self.vannes,
            self.turbine.id: self.turbine, self.coeur.id: self.coeur, self.logique.id: self.logique,
            self.gct.id: self.gct, r.reg_vda.id: r.reg_vda, r.reg_puits.id: r.reg_puits,
            r.reg_p_pzr.id: r.reg_p_pzr, self.pzr.chauffe_prop.id: self.pzr.chauffe_prop,
            self.pzr.chauffe_tor.id: self.pzr.chauffe_tor, self.rea.id: self.rea,
            self.elec.id: self.elec, self.air.id: self.air, **self.elec.diesels, **self.elec.tableaux,
            self.formateur.id: self.formateur,
        }
        self.initialiser_100pct()

    # ================================================================== utilitaires
    def gv(self, b: int) -> GenerateurVapeur:
        return self.gvs[self.boucles.index(b)]

    def sources(self, composant: Composant) -> Sources:
        """Électricité (tableau d'alimentation) et air comprimé disponibles pour ce composant."""
        alim, air = composant.alim, composant.air
        return Sources(electricite_ok=self.elec.sous_tension(alim) if alim else True,
                       air_ok=self.air.disponible if air else True)

    def qm_charge_kg_s(self) -> float:
        """Charge RCV + part des joints qui entre au primaire."""
        return self.rcv.qm_entree_primaire_kg_s()

    def qm_decharge_kg_s(self) -> float:
        """Décharge normale + décharge RRA → RCV."""
        return self.rcv.qm_sortie_primaire_kg_s()

    def tref_c(self) -> float:
        """Température de référence (programme Tmoy en fonction de la charge turbine)."""
        return interp_table(self.cfg.coeur.grappes.regulation_tmoy.tref_programme_c, self.turbine.charge_pct)

    def voies_flux_pct(self) -> list[float]:
        """Chaînes de puissance (4 voies identiques en V1 : pas de panne de capteur)."""
        return [self.coeur.puissance_pct] * int(self.cfg.logique.au.votes.flux.split("/")[1])

    # ================================================================== initialisation
    def _temperatures_nominales(self) -> tuple[float, float, float]:
        """(T branche froide, T branche chaude, T sortie GV) telles que Tmoy = nominale au point 100 %."""
        cfg, tab = self.cfg, self.table
        nb = len(self.boucles)
        q_coeur = cfg.coeur.p_nom_mw * KW_PAR_MW / nb
        q_pompe = cfg.primaire.chaleur_pompe_mw * KW_PAR_MW
        w = sum(self.primaire.etat.w_boucles_kg_s) / nb
        bas, haut = tab.t_min_c, cfg.point_nominal.tmoy_c
        t_bf = t_bc = t_gv = haut
        for _ in range(cfg.numerique.flash.iterations_max):
            t_bf = 0.5 * (bas + haut)
            t_bc = tab.t_primaire_c(tab.h_primaire_kj_kg(t_bf) + q_coeur / w)
            t_gv = tab.t_primaire_c(tab.h_primaire_kj_kg(t_bc) - (q_coeur + q_pompe) / w)
            if 0.5 * (t_bc + t_bf) > cfg.point_nominal.tmoy_c:
                haut = t_bf
            else:
                bas = t_bf
        return t_bf, t_bc, t_gv

    def initialiser_100pct(self) -> None:
        """État approché du point nominal 100 % (à stabiliser ensuite, cf. sim.tools.etat_initial)."""
        cfg, nom = self.cfg, self.cfg.point_nominal
        self.t_s = 0.0
        # primaire : pompes en marche, débits, températures nominales
        for p in self.primaire.pompes + self.primaire.huile:
            p.demarrer()
            p.etat.vitesse = 1.0
        self.primaire.etat.huile_s = [cfg.primaire.soulevement_huile_s] * len(self.boucles)
        self.primaire.reseau.fixer_frontiere("PLENUM", nom.p_primaire_bar)
        t = self.primaire.etat.t_c
        for _ in range(cfg.numerique.iterations_initialisation):     # débits ↔ températures
            self.primaire.resoudre_hydraulique()
            t_bf, t_bc, t_gv = self._temperatures_nominales()
            t.update({DESCENTE: t_bf, COEUR: t_bc, "PLENUM": t_bc})
            for b in self.boucles:
                t.update({bc(b): t_bc, gvp(b): t_gv, bf(b): t_bf})
        self.primaire.etat.masse_liquide_kg = self.primaire.masse_liquide_kg()
        self.pzr.initialiser(nom.p_primaire_bar, nom.niveau_pzr_pct)
        # vannes ouvertes en exploitation normale : isolements PORV, RCV (aspiration VCT, charge, joints,
        # décharge par l'orifice n°1), accumulateurs
        ouvertes = ["PZR_ISOL1", "PZR_ISOL2", "RCV_ASP_VCT", "RCV_ISOL_CHARGE", "RCV_JOINTS", "RCV_LCV459",
                    "RCV_LCV460", "RCV_ORIF1", "RCV_ISOL_ENC"] + [v.id for v in self.accus.isolement]
        for rep in ouvertes:
            v = self.vannes[rep]
            v.etat.position = v.etat.demande_manu = 1.0
        for p in (self.rcv.pompes[0], self.rri.pompes[0], self.rri.pompes_sec[0], self.air.compresseurs[0]):
            p.demarrer()
            p.etat.vitesse = 1.0
        rc = cfg.rcv
        q_charge = rc.orifices_m3h[0] - rc.joints.entree_primaire_m3h       # charge = décharge − joints
        charge = self.rcv.fcv121
        charge.etat.position = charge.etat.demande_auto = q_charge / rc.charge_max_m3h
        self.rcv.calculer(0.0, nom.p_primaire_bar, self.primaire.t(bf(cfg.primaire.boucle_decharge)), False, True,
                          self.masse_primaire_kg(), [], self.table.cp_primaire_kj_kgk(rc.t_vct_c))
        for rep in ("RCV_JOINTS", "RCV_HCV128"):          # vannes manuelles (HCV)
            self.vannes[rep].etat.auto = False
        q_ch = self.rcv.kg_s(q_charge)
        self.regulations.pi_niveau_pzr.initialiser(q_ch, q_ch)
        ri, cp_froid = cfg.rri, self.table.cp_primaire_kj_kgk(rc.t_vct_c)
        nb_pp = len(self.primaire.pompes)
        q_rri = self.rcv.etat.q_echangeur_kw + (ri.chaleur_fixe_mw + nb_pp * ri.chaleur_par_pompe_primaire_mw) * KW_PAR_MW
        self.rri.equilibrer(q_rri, cfg.condenseur.t_mer_c, cp_froid, self.table.rho_liq_kg_m3(ri.t_initiale_c))
        for pi in self.regulations.pi_asg:
            pi.initialiser(0.0)
        # GV
        h_alim = self.table.h_liq_kj_kg(nom.t_alim_c)
        qm_gv = nom.qm_vapeur_kg_s / len(self.gvs)
        for gv in self.gvs:
            gv.initialiser(nom.p_gv_bar, nom.niveau_gv_pct, qm_gv, h_alim)
        self.vapeur.etat.p_collecteur_bar = nom.p_collecteur_bar
        # pompes du secondaire en service
        for p in self.crfs + self.cexs + self.apps + [self.pompes[r] for r in cfg.poste_eau.reprise.pompes]:
            p.demarrer()
            p.etat.vitesse = p.consigne_vitesse()
        for a in self.apps:
            a.etat.consigne_auto = a.etat.vitesse = 1.0
        for b in self.boucles:
            for rep in (f"ARE{b}_ISOL", f"VIV{b}"):
                v = self.vannes[rep]
                v.etat.position = v.etat.demande_manu = 1.0
        # turbine couplée au nominal
        t_, tc = self.turbine.etat, cfg.turbine
        t_.declenchee, t_.cause, t_.couplee = False, "", True
        t_.positions_arret = [1.0] * tc.vannes_arret
        t_.y_reglage = t_.demande_reglage = tc.ouverture_nom
        t_.vitesse_tr_min = t_.consigne_vitesse_tr_min = t_.consigne_vitesse_eff_tr_min = tc.vitesse_nom_tr_min
        t_.consigne_mw = t_.consigne_eff_mw = tc.p_elec_nom_mw
        # condenseur : température d'équilibre estimée (chaleur = cœur − puissance mécanique)
        cd = cfg.condenseur
        q_cond_kw = (nom.p_coeur_mw - tc.p_elec_nom_mw / tc.rendement_alternateur) * KW_PAR_MW
        mcp = self.condenseur.qm_crf_kg_s() * cd.cp_eau_mer_kj_kgk
        eff = 1.0 - math.exp(-cd.ua_mw_c * KW_PAR_MW / mcp)
        self.condenseur.etat.t_c = cd.t_mer_c + q_cond_kw / (eff * mcp)
        self.condenseur.integrer(0.0, q_cond_kw)
        self.turbine.calculer_puissance(0.0, nom.qm_vapeur_kg_s, nom.p_collecteur_bar, self.condenseur.etat.p_bar)
        r = cfg.poste_eau.rechauffeurs
        self.poste_eau.etat.t_abp_c = interp_table(r.abp_sortie_c, POURCENT)
        self.poste_eau.etat.t_ahp_c = interp_table(r.ahp_sortie_c, POURCENT)
        # allers-retours régulations ↔ hydraulique pour placer vannes et pompes (dt = 0 : pas d'intégration)
        self.regulations.pi_dp_app.initialiser(self.apps[0].etat.vitesse)
        for _ in range(cfg.numerique.iterations_initialisation):
            self._resoudre_hydraulique()
            self.regulations.calculer(0.0)
            for v in self.vannes.values():
                v.etat.position = v.demande_effective()
            for a in self.apps:
                a.etat.vitesse = a.consigne_vitesse()
        self._resoudre_hydraulique()
        self.logique.etat.c9 = True
        self.logique.initialiser_filtres()
        self.suivi.initialiser(self.primaire.tmoy_c)
        self.coeur.etat.desequilibre_retard_pct = self.coeur.puissance_pct - self.turbine.charge_pct
        self._mesurer()

    # ================================================================== pas de temps
    def pas(self) -> None:
        dt = self.dt_s
        if self.pzr.etat.hors_domaine:
            return          # cœur découvert ou primaire plein d'eau : hors du domaine du modèle, simulation figée
        # 1-2. pannes programmées, électricité, air comprimé
        pannes.avancer(self)
        self.elec.avancer(dt, self, self.logique.etat.is_actif)
        self.air.avancer(dt)
        # 3. logique
        self.logique.evaluer(dt)
        # 4. régulations puis actionneurs
        self.regulations.calculer(dt)
        self.turbine.reguler(dt, self.vapeur.etat.p_collecteur_bar)
        self.asg.piloter_turbopompe(self.gvs)
        lg = self.logique.etat
        if self.breches.etat.porv_bloquee:                  # panne mécanique : la PORV reste ouverte
            self.vannes[self.breches.etat.porv_bloquee].fixer_ordre(1.0, "bloquée ouverte (panne mécanique)")
        self.coeur.bouger_grappes(dt, self.coeur.vitesse_auto_pas_min(dt, self.primaire.tmoy_c, self.turbine.charge_pct),
                                  retrait_interdit=lg.c2 or lg.c3 or lg.c4, retrait_auto_interdit=lg.c5 or lg.c11)
        for c in list(self.pompes.values()) + list(self.vannes.values()):
            c.avancer(dt, self.sources(c))
        self.primaire.avancer_huile(dt)
        # 5. hydraulique
        self._resoudre_hydraulique()
        # 6. thermique
        self._bilans_thermiques(dt)
        # 7. mesures
        self.t_s += dt
        self._mesurer()
        self.alarmes.evaluer(self.t_s, self.mesures, self.journal)
        self.historique.enregistrer(self.t_s, self.mesures)

    def avancer(self, duree_s: float) -> None:
        """Avance de `duree_s` secondes simulées."""
        for _ in range(round(duree_s / self.dt_s)):
            self.pas()

    def _resoudre_hydraulique(self) -> None:
        cd = self.condenseur
        self.primaire.reseau.fixer_frontiere("PLENUM", self.pzr.p_bar)
        self.primaire.resoudre_hydraulique()
        k_turbine = self.turbine.k_kg_s_bar()
        k_gct = self.gct.k_kg_s_bar()
        self.vapeur.resoudre(self.dt_s, self.gvs, k_turbine + k_gct, cd.etat.p_bar)
        p_h = self.vapeur.etat.p_collecteur_bar
        self._qm_turbine = k_turbine * p_h
        self._qm_gct = k_gct * p_h
        for s in self.vapeur.decharges(self.gvs):
            self.journal.ajouter(self.t_s, "automatisme", f"Ouverture soupape {s}", PRIORITE_HAUTE)
        p_cst = cd.p_fond_cst_bar(self.cfg.simulation.p_atm_bar)
        frontieres = {"PUITS": cd.p_aspiration_cex_bar(), "CONDENSEUR": cd.etat.p_bar, "CST": p_cst}
        frontieres.update({gv.id: gv.p_bar for gv in self.gvs})
        purges = self.cfg.turbine.fraction_soutirage * self._qm_turbine
        self.poste_eau.resoudre(frontieres, cd.etat.t_c, self.cfg.cst.t_c, purges)
        self.asg.resoudre(p_cst, self.gvs)

    def _bilans_thermiques(self, dt: float) -> None:
        pe, cd, tab, pc, cfg = self.poste_eau, self.condenseur, self.table, self.cfg.primaire, self.cfg
        pr = self.primaire
        # cœur (bore venant du RCV)
        self.coeur.etat.bore_ppm = self.rcv.etat.bore_primaire_ppm
        self.coeur.avancer(dt, pr.t_moderateur_c)
        # RRA, accumulateurs, RCV/REA
        rri_ok = self.rri.disponible()
        cp_froid = tab.cp_primaire_kj_kgk(cfg.rcv.t_vct_c)
        rho_froid = tab.rho_liq_kg_m3(self.rri.etat.t_c)
        self.rra.calculer(pr.etat.w_rra_kg_s, pr.t(PLENUM), self.rri.etat.t_c, rri_ok, cp_froid, rho_froid)
        p_prim = self.pzr.p_bar
        self.accus.avancer(dt, p_prim)
        qm_acc = self.accus.qm_total_kg_s
        # V4 : brèches, injection de sécurité MP / BP et aspersion (aspiration PTR ou puisards)
        enc, br, ris = self.enceinte, self.breches, self.ris
        t_breche = pr.t(bf(br.etat.primaire_boucle))
        br.calculer(p_prim, enc.etat.p_bar, tab.rho_primaire_kg_m3(t_breche), tab.psat_bar(t_breche),
                    [gv.p_bar for gv in self.gvs], [gv.tsat_c for gv in self.gvs],
                    br.fraction_vapeur(self.pzr.etat.v_vide_m3, self.volume_decouvrement_m3), tab.tsat_c(p_prim))
        qm_breche_liquide = br.etat.qm_primaire_kg_s - br.etat.qm_primaire_vapeur_kg_s
        gv_breche = self.gvs[br.etat.vapeur_gv - 1]           # un GV vidé par la brèche vapeur ne crache plus rien
        br.etat.qm_vapeur_kg_s = min(br.etat.qm_vapeur_kg_s, gv_breche.masse_disponible_kg(enc.etat.p_bar) / dt)
        injection_bp = self.logique.etat.is_actif and not any(self.rra.aspiration_ouverte(i)
                                                              for i in range(len(self.rra.pompes)))
        ris.calculer(p_prim, P_ASPIRATION_RIS_BAR, injection_bp)
        demande = ris.q_injection_m3h + ris.etat.q_eas_m3h
        if ris.recirculation:
            dispo = enc.prelever_puisard(dt, demande)
            t_inj, bore_inj = min(enc.etat.t_puisard_c, cfg.ris.t_puisard_max_injection_c), cfg.rcv.ptr.bore_ppm
        else:
            dispo = min(demande, self.rcv.etat.ptr_m3 * S_PAR_H / dt)
            self.rcv.etat.ptr_m3 = max(0.0, self.rcv.etat.ptr_m3 - dispo * dt / S_PAR_H)
            t_inj, bore_inj = cfg.rcv.ptr.t_c, cfg.rcv.ptr.bore_ppm
        facteur = dispo / demande if demande > 0.0 else 0.0
        qm_ris = ris.q_injection_m3h * facteur * tab.rho_liq_kg_m3(t_inj) / S_PAR_H
        q_aspersion = ris.etat.q_eas_m3h * facteur
        self.rcv.calculer(dt, p_prim, pr.t(bf(pc.boucle_decharge)), self.rra.en_service(), rri_ok,
                          self.masse_primaire_kg(), [(qm_acc, cfg.accumulateurs.bore_ppm), (qm_ris, bore_inj)], cp_froid)
        # apports au primaire : charge (sortie régénérateur) + joints (froids) en B1, accumulateurs à la descente
        rc, e_rcv = cfg.rcv, self.rcv.etat
        qm_charge = self.rcv.kg_s(e_rcv.q_charge_m3h)
        qm_joints = self.qm_charge_kg_s() - qm_charge
        apports = [(bf(pc.boucle_charge), qm_charge, tab.h_primaire_kj_kg(e_rcv.t_charge_c)),
                   (bf(pc.boucle_charge), qm_joints, tab.h_primaire_kj_kg(rc.t_vct_c)),
                   (DESCENTE, qm_acc, tab.h_primaire_kj_kg(cfg.accumulateurs.t_c)),
                   (DESCENTE, qm_ris, tab.h_primaire_kj_kg(t_inj))]
        boucles_asp = pc.boucles_aspersion
        t_asp = sum(pr.t(bf(b)) for b in boucles_asp) / len(boucles_asp)
        vitesses = [pr.pompes[self.boucles.index(b)].etat.vitesse for b in boucles_asp]
        qm_asp = self.pzr.debit_aspersion_kg_s(vitesses, tab.rho_primaire_kg_m3(t_asp))
        q_rra_net = self.rra.q_total_kw - self.rra.chaleur_pompes_kw()
        # joints des pompes primaires : fuite si ni injection aux joints ni RRI
        injection_joints = self.rcv.nb_pompes() > 0 and e_rcv.q_joints_m3h > DEBIT_INJECTION_MIN_M3H
        rri_pp = rri_ok and not self.logique.etat.phase_b       # la phase B isole le RRI des pompes primaires
        self.joints.avancer(dt, injection_joints, rri_pp, p_prim)
        qm_joints_fuite = self.joints.fuite_totale_m3h * tab.rho_primaire_kg_m3(pr.t(DESCENTE)) / S_PAR_H
        sorties = self.qm_decharge_kg_s() + qm_joints_fuite + qm_breche_liquide + br.etat.qm_rtgv_kg_s
        pr.avancer(dt, self.coeur.puissance_thermique_kw, self.gvs, apports, sorties,
                   qm_asp, self.pzr.vol.sat.hf_kj_kg, q_rra_net, self.pzr.etat.q_vide_kw)
        # RRI / SEC : échangeurs RRA, décharge RCV, pompes primaires, autres utilisateurs
        ri = cfg.rri
        nb_pp = sum(p.etat.en_marche for p in pr.pompes)
        q_rri = (self.rra.q_total_kw + e_rcv.q_echangeur_kw
                 + (ri.chaleur_fixe_mw + nb_pp * ri.chaleur_par_pompe_primaire_mw) * KW_PAR_MW)
        self.rri.avancer(dt, q_rri, cfg.condenseur.t_mer_c, cp_froid, rho_froid)
        self.suivi.avancer(dt, pr.tmoy_c)
        h_bc_exp = tab.h_primaire_kj_kg(self.primaire.t(bc(pc.boucle_expansion)))
        for s in self.pzr.avancer(dt, self.primaire.etat.qm_expansion_kg_s, h_bc_exp, qm_asp,
                                  tab.h_primaire_kj_kg(t_asp), self.sources, pr.t_chaud_c,
                                  br.etat.qm_primaire_vapeur_kg_s):
            self.journal.ajouter(self.t_s, "automatisme", f"Ouverture soupape {s}", PRIORITE_HAUTE)
        self._verifier_domaine()
        # décharge du PZR → PRT → (disque rompu) enceinte ; brèches → enceinte ; aspersion
        disque = self.prt.etat.disque_rompu
        vers_enceinte = self.prt.avancer(dt, self.pzr.etat.qm_porv_kg_s + self.pzr.etat.qm_soupapes_kg_s,
                                         self.pzr.h_decharge_kj_kg, enc.etat.p_bar)
        if self.prt.etat.disque_rompu and not disque:
            self.journal.ajouter(self.t_s, "automatisme", "Disque de rupture de la PRT rompu : décharge dans l'enceinte",
                                 PRIORITE_HAUTE)
        j = br.etat.vapeur_gv - 1
        vers_enceinte += [(qm_joints_fuite, tab.h_primaire_kj_kg(pr.t(DESCENTE))),
                          (qm_breche_liquide, tab.h_primaire_kj_kg(pr.t(bf(br.etat.primaire_boucle)))),
                          (br.etat.qm_primaire_vapeur_kg_s, tab.hg_kj_kg(self.pzr.p_bar)),
                          (br.etat.qm_vapeur_kg_s, tab.hg_kj_kg(self.gvs[j].p_bar))]
        enc.avancer(dt, vers_enceinte, q_aspersion, t_inj)
        # GV : eau alimentaire ARE + ASG
        h_are, h_asg = pe.h_alim_kj_kg, self.asg.h_eau_kj_kg
        for i, gv in enumerate(self.gvs):
            qm_are = pe.qm(f"L_ARE{gv.b}")
            qm_asg = max(0.0, self.asg.etat.qm_gv_kg_s[i])
            qm_alim = qm_are + qm_asg
            h_alim = (qm_are * h_are + qm_asg * h_asg) / qm_alim if qm_alim > 0.0 else h_are
            if gv.b == br.etat.rtgv_gv and br.etat.qm_rtgv_kg_s > 0.0:      # RTGV : eau primaire dans le GV
                h_prim = tab.h_primaire_kj_kg(pr.t(gvp(gv.b)))
                h_alim = (qm_alim * h_alim + br.etat.qm_rtgv_kg_s * h_prim) / (qm_alim + br.etat.qm_rtgv_kg_s)
                qm_alim += br.etat.qm_rtgv_kg_s
            decharge = self.vapeur.qm_decharge_kg_s(i) + self.asg.vapeur_tps_par_gv_kg_s(gv.b)
            if gv.b == br.etat.vapeur_gv:
                decharge += br.etat.qm_vapeur_kg_s
            gv.avancer(dt, self.primaire.etat.q_gv_kw[i], qm_alim, h_alim, self.vapeur.etat.qm_lignes_kg_s[i], decharge)
        br.avancer_activite(dt, [gv.vol.m_liq_kg for gv in self.gvs])
        # turbine
        p_h = self.vapeur.etat.p_collecteur_bar
        self.turbine.calculer_puissance(dt, self._qm_turbine, p_h, cd.etat.p_bar)
        # condenseur : énergie restante après travail et réchauffage de l'eau alimentaire
        h_col, h_puits = self.vapeur.etat.h_collecteur_kj_kg, cd.h_puits_kj_kg
        qm_are_total = sum(pe.qm(f"L_ARE{b}") for b in self.boucles)
        q_rechauffeurs = qm_are_total * (h_are - h_puits)
        qm_vapeur = self._qm_turbine + self._qm_gct
        q_cond = (qm_vapeur * (h_col - h_puits) - self.turbine.etat.p_meca_mw * KW_PAR_MW - q_rechauffeurs)
        cd.integrer(dt, max(0.0, q_cond))
        # puits : condensat turbine + purges non reprises + contournement + recirculation + appoint − CEX
        purges_condenseur = pe.etat.qm_purges_kg_s - pe.etat.qm_reprise_kg_s
        entree = (self._qm_turbine * (1.0 - self.cfg.turbine.fraction_soutirage) + purges_condenseur
                  + self._qm_gct + pe.qm("L_RECIRC") + pe.qm("L_APPOINT"))
        sortie = pe.qm("L_CEX1") + pe.qm("L_CEX2")
        cd.puits.integrer(dt, entree - sortie)
        cd.cst.integrer(dt, pe.qm("L_REJET") - pe.qm("L_APPOINT") - sum(self.asg.etat.qm_gv_kg_s))
        pe.avancer_rechauffeurs(dt, self.turbine.charge_pct, cd.etat.t_c)

    def _verifier_domaine(self) -> None:
        """Garde-fou du modèle : cœur découvert (accident grave, pas modélisé)."""
        pz = self.pzr
        raison = ""
        if pz.etat.v_vide_m3 > self.volume_decouvrement_m3:
            raison = "cœur découvert (vide primaire au-dessus du cœur) : accident grave, hors du domaine du simulateur"
        if raison and not pz.etat.hors_domaine:
            pz.etat.hors_domaine = raison
            self.journal.ajouter(self.t_s, "automatisme", f"SIMULATION FIGÉE : {raison} — recharger un état ou un "
                                 "scénario", PRIORITE_HAUTE)

    @property
    def volume_decouvrement_m3(self) -> float:
        """Vide primaire au-delà duquel le haut du cœur est dénoyé (tout sauf cœur et descente)."""
        v = self.cfg.primaire.volumes_m3
        return self.primaire.volume_total_m3 - v.coeur - v.descente

    # ================================================================== mesures
    def masse_eau_totale_kg(self) -> float:
        """Secondaire : GV + puits + CST (circuit fermé hors décharges à l'atmosphère)."""
        return (sum(gv.vol.etat.m_kg for gv in self.gvs) + self.condenseur.puits.etat.m_kg
                + self.condenseur.cst.etat.m_kg)

    def masse_primaire_kg(self) -> float:
        """Primaire : nœuds liquides (moins le vide) + pressuriseur."""
        return (self.primaire.masse_liquide_kg() + self.pzr.vol.etat.m_kg + self.pzr.etat.m_comprime_kg
                - self.pzr.etat.v_vide_m3 / self.pzr.vol.sat.vf_m3_kg)

    def _mesurer(self) -> None:
        m: dict[str, float] = {}
        pe, cd, t, lg = self.poste_eau, self.condenseur, self.turbine.etat, self.logique.etat
        pr, co, pz = self.primaire, self.coeur, self.pzr
        # cœur et primaire
        m["coeur.puissance_pct"] = co.puissance_pct
        m["coeur.p_thermique_mw"] = co.puissance_thermique_kw / KW_PAR_MW
        m["coeur.rho_pcm"] = co.etat.rho_pcm
        m["coeur.t_comb_c"] = co.etat.t_comb_c
        m["grappes.position_pas"] = co.etat.z_pas
        m["grappes.arret_insere_pct"] = POURCENT * co.etat.arret_insere
        m["grappes.g_pas"] = co.etat.g_pas
        rho = co.etat.rho_pcm * PCM
        cc = self.cfg.coeur
        m["coeur.k_eff"] = 1.0 / (1.0 - rho)
        m["coeur.periode_s"] = ((cc.beta_pcm * PCM - rho) / (cc.lambda_s * rho)
                                if abs(rho) > PCM else PERIODE_INFINIE_S)
        m["coeur.fissions_par_s"] = co.puissance_fission_kw * W_PAR_KW / ENERGIE_FISSION_J
        m["coeur.n_relatif"] = co.etat.n
        tmoy, tref = pr.tmoy_c, self.tref_c()
        m["primaire.tmoy_c"] = tmoy
        m["primaire.tref_c"] = tref
        m["primaire.ecart_tref_abs_c"] = abs(tmoy - tref)
        m["primaire.q_pompes_mw"] = pr.etat.q_pompes_kw / KW_PAR_MW
        m["primaire.debit_min_pct"] = min(pr.debit_pct(i) for i in range(len(self.boucles)))
        for i, b in enumerate(self.boucles):
            m[f"B{b}.t_bc_c"] = pr.t(bc(b))
            m[f"B{b}.t_bf_c"] = pr.t(bf(b))
            m[f"B{b}.dt_c"] = pr.dt_boucle_c(i)
            m[f"B{b}.debit_pct"] = pr.debit_pct(i)
        m["cuve.t_entree_c"] = pr.t(DESCENTE)
        m["cuve.t_sortie_c"] = pr.t(COEUR)
        m["cuve.marge_saturation_c"] = self.table.tsat_c(pz.p_bar) - pr.t(COEUR)
        m["pzr.p_bar"] = pz.p_bar
        m["pzr.niveau_pct"] = pz.niveau_pct
        m["pzr.niveau_programme_pct"] = pz.niveau_programme_pct(tmoy)
        m["pzr.ecart_niveau_pct"] = pz.niveau_pct - pz.niveau_programme_pct(tmoy)
        m["pzr.chauffe_kw"] = pz.etat.q_chauffe_kw
        m["pzr.aspersion_kg_s"] = pz.etat.qm_aspersion_kg_s
        m["pzr.porv_qm_kg_s"] = pz.etat.qm_porv_kg_s
        m["pzr.soupapes_ouvertes"] = float(pz.nb_soupapes_ouvertes())
        m["pzr.expansion_kg_s"] = pr.etat.qm_expansion_kg_s
        m["rcv.charge_kg_s"] = self.qm_charge_kg_s()
        m["rcv.decharge_kg_s"] = self.qm_decharge_kg_s()
        rv, rea = self.rcv.etat, self.rea.etat
        m["rcv.charge_m3h"] = rv.q_charge_m3h
        m["rcv.joints_m3h"] = rv.q_joints_m3h
        m["rcv.decharge_m3h"] = rv.q_decharge_m3h + rv.q_rra_m3h
        m["rcv.dispo_m3h"] = rv.q_dispo_m3h
        m["rcv.deviation_m3h"] = rv.q_deviation_m3h
        m["rcv.t_charge_c"] = rv.t_charge_c
        m["rcv.vct_niveau_pct"] = self.rcv.niveau_vct_pct
        m["rcv.vct_bore_ppm"] = rv.vct_bore_ppm
        m["rcv.ptr_m3"] = rv.ptr_m3
        m["rcv.pompes_charge"] = float(self.rcv.nb_pompes())
        m["rcv.bore_charge_ppm"] = rv.bore_charge_ppm
        m["rcv.echangeur_mw"] = rv.q_echangeur_kw / KW_PAR_MW
        m["rea.acide_m3"] = rea.acide_m3
        m["rea.eau_m3"] = rea.eau_m3
        m["rea.q_acide_m3h"] = rea.q_acide_m3h + rv.q_urgence_m3h
        m["rea.q_eau_m3h"] = rea.q_eau_m3h
        m["rea.volume_restant_m3"] = rea.volume_restant_m3
        m["rea.q_total_m3h"] = rea.q_acide_m3h + rea.q_eau_m3h
        m["rea.q_urgence_m3h"] = rv.q_urgence_m3h
        m["rea.acide_pct"] = POURCENT * rea.acide_m3 / self.cfg.rea.volume_acide_m3
        m["rea.eau_pct"] = POURCENT * rea.eau_m3 / self.cfg.rea.volume_eau_m3
        m["rcv.ptr_pct"] = POURCENT * rv.ptr_m3 / self.cfg.rcv.ptr.volume_m3
        m["primaire.bore_ppm"] = rv.bore_primaire_ppm
        et = self.cfg.logique.etats
        m["coeur.marge_arret_chaud_pcm"] = co.marge_arret_pcm(pr.t_moderateur_c, rv.bore_primaire_ppm, et.grappe_coincee_pcm)
        m["coeur.marge_arret_froid_pcm"] = co.marge_arret_pcm(et.t_froid_c, rv.bore_primaire_ppm, et.grappe_coincee_pcm)
        m["coeur.bore_arret_froid_ppm"] = co.bore_requis_ppm(et.t_froid_c, et.marge_arret_pcm, et.grappe_coincee_pcm)
        m["coeur.rho_grappes_pcm"] = co.rho_grappes_pcm()
        m["coeur.rho_moderateur_pcm"] = co.rho_moderateur_pcm(pr.t_moderateur_c)
        m["coeur.rho_doppler_pcm"] = co.rho_doppler_pcm(co.etat.t_comb_c)
        m["coeur.rho_bore_pcm"] = co.rho_bore_pcm(rv.bore_primaire_ppm)
        m["primaire.vitesse_refroidissement_c_h"] = self.suivi.etat.vitesse_refroidissement_c_h
        m["primaire.vitesse_instantanee_c_h"] = self.suivi.etat.vitesse_instantanee_c_h
        m["primaire.t_max_c"] = max(pr.etat.t_c.values())
        # RRA, RRI/SEC, accumulateurs
        rho_plenum = self.table.rho_primaire_kg_m3(pr.t(PLENUM))
        for i, k in enumerate(self.cfg.rra.trains):
            m[f"RRA{k}.debit_m3h"] = self.rra.etat.w_kg_s[i] * S_PAR_H / rho_plenum
            m[f"RRA{k}.q_mw"] = self.rra.etat.q_kw[i] / KW_PAR_MW
            m[f"RRA{k}.t_sortie_c"] = self.rra.etat.t_sortie_c[i]
        m["rra.q_mw"] = self.rra.q_total_kw / KW_PAR_MW
        m["rri.t_c"] = self.rri.etat.t_c
        m["rri.q_mw"] = self.rri.etat.q_utilisateurs_kw / KW_PAR_MW
        m["sec.q_mw"] = self.rri.etat.q_sec_kw / KW_PAR_MW
        m["rri.perte_pp"] = float(lg.perte_rri)
        for i, b in enumerate(self.boucles):
            m[f"ACC{b}.p_bar"] = self.accus.p_bar(i)
            m[f"ACC{b}.volume_m3"] = self.accus.etat.v_eau_m3[i]
            m[f"ACC{b}.niveau_pct"] = POURCENT * self.accus.etat.v_eau_m3[i] / self.cfg.accumulateurs.volume_m3
        m["accu.qm_kg_s"] = self.accus.qm_total_kg_s
        # électricité, air, joints
        el = self.elec
        m["elec.reseau_ok"] = float(el.etat.reseau_ok)
        for k in self.cfg.electricite.tableaux_normaux + self.cfg.electricite.tableaux_secourus:
            m[f"elec.{k}.tension_pct"] = el.tension_pct(k)
        for d in el.diesels.values():
            m[f"elec.{d.id}.en_service"] = float(d.en_service)
            m[f"elec.{d.id}.charge_kw"] = d.etat.charge_kw
        for lb in self.cfg.electricite.batteries:
            m[f"elec.{lb}.charge_pct"] = el.etat.batteries_pct[lb]
            m[f"elec.{lb}.decharge"] = float(el.batterie_en_decharge(lb))
        m["air.p_bar"] = self.air.etat.p_bar
        m["air.p_pct"] = POURCENT * self.air.etat.p_bar / self.cfg.air_comprime.p_nom_bar
        m["elec.reseau_pct"] = POURCENT * float(el.etat.reseau_ok)
        m["elec.ta_pct"] = POURCENT * float(el.etat.source_normale == "TA" or el.etat.reseau_ok)
        m["elec.ts_pct"] = POURCENT * float(el.etat.source_normale == "TS")
        m["elec.alternateur_pct"] = POURCENT * float(self.turbine.etat.couplee)
        for d in el.diesels.values():
            m[f"elec.{d.id}.tension_pct"] = POURCENT * float(d.etat.etat in ("pret", "couple"))
        m["joints.fuite_m3h"] = self.joints.fuite_totale_m3h
        m["joints.volume_m3"] = self.joints.etat.volume_fuite_m3
        m["primaire.hors_domaine"] = float(bool(pz.etat.hors_domaine))
        m["primaire.vide_m3"] = pz.etat.v_vide_m3
        m["primaire.sature"] = float(pz.etat.sature)
        m["primaire.en_eau"] = float(pz.en_eau)
        m["cuve.niveau_pct"] = POURCENT * max(0.0, 1.0 - pz.etat.v_vide_m3 / self.volume_decouvrement_m3)
        # V4 : enceinte, PRT, RIS, brèches
        en, pt, ri, bre = self.enceinte.etat, self.prt.etat, self.ris.etat, self.breches.etat
        m["enceinte.p_bar"] = en.p_bar
        m["enceinte.p_rel_bar"] = self.enceinte.p_rel_bar
        m["enceinte.t_c"] = en.t_c
        m["enceinte.puisard_m3"] = en.puisard_m3
        m["enceinte.t_puisard_c"] = en.t_puisard_c
        m["enceinte.puisard_pct"] = POURCENT * min(1.0, en.puisard_m3 / PUISARD_REFERENCE_M3)
        m["prt.p_bar"] = pt.p_bar
        m["prt.t_c"] = pt.t_c
        m["prt.disque_rompu"] = float(pt.disque_rompu)
        m["ris.q_hp_m3h"] = self.rcv.etat.q_bit_m3h
        m["ris.q_mp_m3h"] = ri.q_mp_m3h
        m["ris.q_bp_m3h"] = ri.q_bp_m3h
        m["ris.q_eas_m3h"] = ri.q_eas_m3h
        m["ris.qm_kg_s"] = self.rcv.kg_s(self.rcv.etat.q_bit_m3h + ri.q_mp_m3h + ri.q_bp_m3h)
        m["ris.recirculation"] = float(ri.recirculation)
        m["breche.primaire_kg_s"] = bre.qm_primaire_kg_s
        m["breche.rtgv_kg_s"] = bre.qm_rtgv_kg_s
        m["breche.vapeur_kg_s"] = bre.qm_vapeur_kg_s
        for i, b in enumerate(self.boucles):
            m[f"GV{b}.activite"] = bre.activite_gv[i]
        m["gv.activite_max"] = max(bre.activite_gv)
        m["logique.isolement_vapeur"] = float(lg.isolement_vapeur)
        m["logique.phase_b"] = float(lg.phase_b)
        m_ot, m_op = self.logique.marges_dt_pct()
        m["otdt.marge_pct"] = m_ot
        m["opdt.marge_pct"] = m_op
        # GV
        for i, gv in enumerate(self.gvs):
            k = gv.id
            m[f"{k}.niveau_pct"] = gv.capteur.mediane
            m[f"{k}.niveau_vrai_pct"] = gv.niveau_pct
            m[f"{k}.p_bar"] = gv.p_bar
            m[f"{k}.qm_vapeur_kg_s"] = gv.etat.qm_ligne_kg_s
            m[f"{k}.qm_alim_kg_s"] = gv.etat.qm_alim_kg_s
            m[f"{k}.qm_asg_kg_s"] = self.asg.etat.qm_gv_kg_s[i]
            m[f"{k}.q_mw"] = gv.etat.q_kw / KW_PAR_MW
            m[f"{k}.m_eau_t"] = gv.vol.m_liq_kg / KG_PAR_T
            m[f"{k}.qm_decharge_kg_s"] = self.vapeur.qm_decharge_kg_s(i)
        # vapeur, turbine, condenseur, poste d'eau
        m["collecteur.p_bar"] = self.vapeur.etat.p_collecteur_bar
        m["turbine.p_elec_mw"] = t.p_elec_mw
        m["turbine.p_meca_mw"] = t.p_meca_mw
        m["turbine.qm_kg_s"] = t.qm_kg_s
        m["turbine.charge_pct"] = self.turbine.charge_pct
        m["turbine.vitesse_tr_min"] = t.vitesse_tr_min
        m["turbine.ouverture_pct"] = POURCENT * t.y_reglage
        m["gctc.qm_kg_s"] = self._qm_gct
        m["gctc.ouverture_pct"] = self.gct.ouverture_pct()
        m["vapeur.vda_qm_kg_s"] = sum(self.vapeur.etat.qm_vda_kg_s)
        m["vapeur.soupapes_qm_kg_s"] = sum(self.vapeur.etat.qm_soupapes_kg_s)
        m["vapeur.soupapes_ouvertes"] = float(self.vapeur.nb_soupapes_ouvertes())
        m["vapeur.vda_ouvertes"] = float(sum(v.etat.position > 0.0 for v in self.vapeur.vda))
        m["condenseur.p_bar"] = cd.etat.p_bar
        m["condenseur.t_c"] = cd.etat.t_c
        m["condenseur.q_mw"] = cd.etat.q_entree_kw / KW_PAR_MW
        m["condenseur.q_mer_mw"] = cd.etat.q_mer_kw / KW_PAR_MW
        m["puits.niveau_pct"] = cd.niveau_puits_pct()
        m["cst.volume_m3"] = cd.volume_cst_m3()
        m["cst.niveau_pct"] = POURCENT * cd.volume_cst_m3() / self.cfg.cst.volume_m3
        m["alim.qm_kg_s"] = sum(pe.qm(f"L_ARE{b}") for b in self.boucles)
        m["alim.t_c"] = pe.etat.t_ahp_c
        m["abp.t_c"] = pe.etat.t_abp_c
        m["alim.dp_bar"] = pe.p("N_ARE") - self.vapeur.etat.p_collecteur_bar
        m["cex.q_m3h"] = pe.debit_cex_m3h(cd.rho_puits_kg_m3)
        m["reprise.qm_kg_s"] = pe.etat.qm_reprise_kg_s
        m["asg.qm_kg_s"] = self.asg.qm_total_kg_s()
        m["asg.p_refoulement_bar"] = self.asg.reseau.p("N_ASG")
        for noeud in pe.reseau.noeuds:
            m[f"{noeud}.p_bar"] = pe.p(noeud)
        for p in self.pompes.values():
            m[f"{p.id}.vitesse_pct"] = POURCENT * p.etat.vitesse
        m["crf.debit_m3s"] = cd.qm_crf_kg_s() / self.cfg.condenseur.rho_eau_mer_kg_m3
        m["bilan.masse_eau_t"] = self.masse_eau_totale_kg() / KG_PAR_T
        m["bilan.masse_primaire_t"] = self.masse_primaire_kg() / KG_PAR_T
        # logique
        m["logique.au"] = float(lg.au)
        m["logique.p7"] = float(lg.p7)
        m["logique.p10"] = float(lg.p10)
        m["logique.p12"] = float(lg.p12)
        m["logique.p14"] = float(lg.p14)
        m["logique.c9"] = float(lg.c9)
        m["logique.c3_c4"] = float(lg.c3 or lg.c4)
        m["logique.turbine_declenchee"] = float(t.declenchee)
        m["logique.isolement_are"] = float(lg.isolement_are_au or lg.isolement_are_complet)
        m["logique.app_declenchee"] = float(lg.app_declenchee)
        m["logique.cex_declenchee"] = float(lg.cex_declenchee)
        m["logique.is"] = float(lg.is_actif)
        m["logique.p11"] = float(lg.p11)
        m["logique.rra_isole_auto"] = float(lg.rra_isole_auto)
        self.mesures = m

    # ================================================================== commandes joueur
    def conditions(self, cible: str, action: str, valeur: float | None = None) -> list[Condition]:
        return interlocks.conditions(self, self.commandables[cible], action, valeur)

    def commande(self, cible: str, action: str, valeur: float | None = None) -> Reponse:
        """Exécute une commande joueur si toutes ses conditions sont remplies, sinon dit pourquoi."""
        obj = self.commandables.get(cible)
        if obj is None:
            return Reponse(False, [f"Équipement inconnu : {cible}"])
        if action not in obj.commandes():
            return Reponse(False, [f"Action « {action} » impossible sur {cible}"])
        refus = [c.texte for c in self.conditions(cible, action, valeur) if not c.ok]
        texte = f"{cible} : {action}" + (f" = {valeur:g}" if valeur is not None else "")
        if refus:
            self.journal.ajouter(self.t_s, "action", f"REFUS {texte} — {'; '.join(refus)}", PRIORITE_INFO)
            return Reponse(False, refus)
        self._executer(obj, action, valeur)
        self.journal.ajouter(self.t_s, "action", texte, PRIORITE_INFO)
        return Reponse(True, [])

    def _executer(self, obj: Composant, action: str, valeur: float | None) -> None:
        if isinstance(obj, Pompe):
            if action == "demarrer":
                obj.demarrer()
            elif action == "arreter":
                obj.arreter()
            elif action in ("auto", "manu"):
                obj.etat.auto = action == "auto"
                obj.etat.consigne_manu = obj.etat.vitesse
            elif action == "vitesse" and valeur is not None:
                obj.etat.consigne_manu = valeur / POURCENT
        elif isinstance(obj, Vanne):
            if action in ("ouvrir", "fermer"):
                obj.demander(1.0 if action == "ouvrir" else 0.0)
            elif action in ("auto", "manu"):
                obj.etat.auto = action == "auto"
                obj.etat.demande_manu = obj.etat.position
            elif action == "position" and valeur is not None:
                obj.demander(valeur / POURCENT)
        elif isinstance(obj, Diesel):
            self._executer_diesel(obj, action)
        elif isinstance(obj, TableauSecouru):
            obj.etat.arrivee_fermee = action == "fermer_arrivee"
        else:
            obj.executer(action, valeur)  # type: ignore[attr-defined]

    def _executer_diesel(self, d: Diesel, action: str) -> None:
        if action == "demarrer":
            d.demarrer()
        elif action == "arreter":
            d.arreter("arrêt manuel")
        elif action == "coupler":
            self.elec.coupler(self, self.elec.tableaux[d.tableau])
        elif action == "decoupler":
            d.etat.etat = "pret"
        elif action == "rearmer":
            d.etat.refus, d.etat.etat, d.etat.cause = False, "arret", ""

    def liste_commandes(self, cible: str) -> list[dict[str, Any]]:
        """Pour le panneau équipement : chaque action avec ses conditions ✓/✗ (sans valeur)."""
        obj = self.commandables[cible]
        sortie = []
        for action in obj.commandes():
            conds = [c for c in self.conditions(cible, action, None) if not c.texte.startswith("Valeur entre")]
            sortie.append({"action": action, "possible": all(c.ok for c in conds),
                           "conditions": [{"texte": c.texte, "ok": c.ok} for c in conds]})
        return sortie

    # ================================================================== sauvegarde
    def objets_etat(self) -> dict[str, Any]:
        """Tous les objets dont l'état est sauvegardé."""
        objets: dict[str, Any] = dict(self.composants)
        objets.update({gv.id: gv for gv in self.gvs})
        objets.update({f"{gv.id}.volume": gv.vol for gv in self.gvs})
        objets.update({gv.capteur.id: gv.capteur for gv in self.gvs})
        objets.update({s.id: s for ligne in self.vapeur.soupapes for s in ligne})
        objets.update({s.id: s for s in self.pzr.soupapes})
        pz, r = self.pzr, self.regulations
        objets.update({
            "GRAPPES": self.coeur, "PRIMAIRE": self.primaire, "PZR": pz, "PZR.volume": pz.vol,
            pz.capteur_p.id: pz.capteur_p, pz.capteur_niveau.id: pz.capteur_niveau,
            pz.chauffe_prop.id: pz.chauffe_prop, pz.chauffe_tor.id: pz.chauffe_tor, "ASG": self.asg,
            "TURBINE": self.turbine, "CONDENSEUR": self.condenseur, "REG_GCTC": self.gct,
            "RCV": self.rcv, "REA": self.rea, "RRA": self.rra, "RRI": self.rri, "ACCUS": self.accus,
            "SUIVI": self.suivi, "ELEC": self.elec, "SAR": self.air, "JOINTS": self.joints,
            "ENCEINTE": self.enceinte, "PRT": self.prt, "BRECHES": self.breches, "RIS": self.ris,
            r.reg_vda.id: r.reg_vda, r.reg_puits.id: r.reg_puits, r.reg_p_pzr.id: r.reg_p_pzr,
        })
        return objets

    def exporter(self) -> dict[str, Any]:
        """État complet sérialisable en JSON."""
        objets = {}
        for k, o in self.objets_etat().items():
            if hasattr(o, "exporter_etat"):
                objets[k] = o.exporter_etat()
            elif getattr(o, "etat", None) is not None:
                objets[k] = vars(o.etat).copy()
        return {
            "version": VERSION_SAUVEGARDE,
            "t_s": self.t_s,
            "objets": objets,
            "vapeur": vars(self.vapeur.etat).copy(),
            "poste_eau": self.poste_eau.exporter_etat(),
            "regulations": self.regulations.exporter_etat(),
            "logique": self.logique.exporter_etat(),
            "journal": self.journal.exporter(),
            "alarmes": self.alarmes.exporter(),
            "pannes": [dict(p) for p in self.pannes],
        }

    def importer(self, d: dict[str, Any]) -> None:
        """Recharge un état exporté (même configuration)."""
        if d.get("version") != VERSION_SAUVEGARDE:
            raise ValueError("Sauvegarde d'une version incompatible")
        self.t_s = d["t_s"]
        for k, o in self.objets_etat().items():
            donnees = d["objets"][k]
            if hasattr(o, "importer_etat"):
                o.importer_etat(donnees)
            elif getattr(o, "etat", None) is not None:
                o.etat = type(o.etat)(**donnees)
        self.vapeur.etat = type(self.vapeur.etat)(**d["vapeur"])
        self.poste_eau.importer_etat(d["poste_eau"])
        self.regulations.importer_etat(d["regulations"])
        self.logique.etat = type(self.logique.etat)(**d["logique"])
        self.journal.importer(d["journal"])
        self.alarmes.importer(d["alarmes"])
        self.pannes = [dict(p) for p in d.get("pannes", [])]
        for vol in [gv.vol for gv in self.gvs] + [self.pzr.vol]:
            vol.mettre_a_jour()
        p_h = self.vapeur.etat.p_collecteur_bar
        self._qm_turbine = self.turbine.k_kg_s_bar() * p_h
        self._qm_gct = self.gct.k_kg_s_bar() * p_h
        self.historique.vider()
        self._mesurer()
