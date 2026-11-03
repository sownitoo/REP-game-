"""Assemblage de la centrale et boucle de calcul d'un pas de temps (§2.3).

Ordre d'un pas :
  1. commandes joueur (appliquées dès réception, entre deux pas)
  2. électricité (stub, tout est sous tension — V3)
  3. logique : capteurs → permissifs → AU → automatismes
  4. régulations → demandes des actionneurs, puis mouvement des actionneurs et des grappes
  5. hydraulique : primaire (+ RRA), collecteur vapeur, eau alimentaire, ASG
  6. thermique : cœur, RRA, accumulateurs, RCV/REA (bore), primaire, pressuriseur, GV, turbine,
     condenseur, bâches, réchauffeurs, RRI/SEC
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
from sim.systems.accumulateurs import Accumulateurs
from sim.systems.asg import ASG
from sim.systems.condenseur import Condenseur
from sim.systems.gct import Contournement
from sim.systems.gv import GenerateurVapeur
from sim.systems.poste_eau import PosteEau
from sim.systems.pzr import Pressuriseur
from sim.systems.rcp import COEUR, DESCENTE, PLENUM, CircuitPrimaire, bc, bf, gvp
from sim.systems.rcv import RCV, Rea
from sim.systems.rra import RRA
from sim.systems.rri import RRI
from sim.systems.turbine import Turbine
from sim.systems.vvp import Vapeur
from sim.thermo.tables import obtenir_table
from sim.units import KG_PAR_T, KW_PAR_MW, POURCENT, S_PAR_H, interp_table

VERSION_SAUVEGARDE = 3
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
    """Centrale V2 : primaire 4 boucles + PZR + cœur, RCV/REA, RRA, RRI/SEC, accumulateurs, secondaire, ASG."""

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
        }
        self.initialiser_100pct()

    # ================================================================== utilitaires
    def gv(self, b: int) -> GenerateurVapeur:
        return self.gvs[self.boucles.index(b)]

    def sources(self, composant: Composant) -> Sources:
        """Électricité et air disponibles pour ce composant (V1 : toujours disponibles, cf. V3)."""
        return Sources()

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
        for p in (self.rcv.pompes[0], self.rri.pompes[0], self.rri.pompes_sec[0]):
            p.demarrer()
            p.etat.vitesse = 1.0
        rc = cfg.rcv
        q_charge = rc.orifices_m3h[0] - rc.joints.entree_primaire_m3h       # charge = décharge − joints
        charge = self.rcv.fcv121
        charge.etat.position = charge.etat.demande_auto = q_charge / rc.charge_max_m3h
        self.rcv.calculer(0.0, nom.p_primaire_bar, self.primaire.t(bf(cfg.primaire.boucle_decharge)), False, True,
                          self.masse_primaire_kg(), 0.0, cfg.accumulateurs.bore_ppm, self.table.cp_primaire_kj_kgk(rc.t_vct_c))
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
        # 3. logique
        self.logique.evaluer(dt)
        # 4. régulations puis actionneurs
        self.regulations.calculer(dt)
        self.turbine.reguler(dt, self.vapeur.etat.p_collecteur_bar)
        self.asg.piloter_turbopompe(self.gvs)
        lg = self.logique.etat
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
        self.rcv.calculer(dt, p_prim, pr.t(bf(pc.boucle_decharge)), self.rra.en_service(), rri_ok,
                          self.masse_primaire_kg(), qm_acc, cfg.accumulateurs.bore_ppm, cp_froid)
        # apports au primaire : charge (sortie régénérateur) + joints (froids) en B1, accumulateurs à la descente
        rc, e_rcv = cfg.rcv, self.rcv.etat
        qm_charge = self.rcv.kg_s(e_rcv.q_charge_m3h)
        qm_joints = self.qm_charge_kg_s() - qm_charge
        apports = [(bf(pc.boucle_charge), qm_charge, tab.h_primaire_kj_kg(e_rcv.t_charge_c)),
                   (bf(pc.boucle_charge), qm_joints, tab.h_primaire_kj_kg(rc.t_vct_c)),
                   (DESCENTE, qm_acc, tab.h_primaire_kj_kg(cfg.accumulateurs.t_c))]
        boucles_asp = pc.boucles_aspersion
        t_asp = sum(pr.t(bf(b)) for b in boucles_asp) / len(boucles_asp)
        vitesses = [pr.pompes[self.boucles.index(b)].etat.vitesse for b in boucles_asp]
        qm_asp = self.pzr.debit_aspersion_kg_s(vitesses, tab.rho_primaire_kg_m3(t_asp))
        q_rra_net = self.rra.q_total_kw - self.rra.chaleur_pompes_kw()
        pr.avancer(dt, self.coeur.puissance_thermique_kw, self.gvs, apports, self.qm_decharge_kg_s(), qm_asp,
                   self.pzr.vol.sat.hf_kj_kg, q_rra_net)
        # RRI / SEC : échangeurs RRA, décharge RCV, pompes primaires, autres utilisateurs
        ri = cfg.rri
        nb_pp = sum(p.etat.en_marche for p in pr.pompes)
        q_rri = (self.rra.q_total_kw + e_rcv.q_echangeur_kw
                 + (ri.chaleur_fixe_mw + nb_pp * ri.chaleur_par_pompe_primaire_mw) * KW_PAR_MW)
        self.rri.avancer(dt, q_rri, cfg.condenseur.t_mer_c, cp_froid, rho_froid)
        self.suivi.avancer(dt, pr.tmoy_c)
        h_bc_exp = tab.h_primaire_kj_kg(self.primaire.t(bc(pc.boucle_expansion)))
        for s in self.pzr.avancer(dt, self.primaire.etat.qm_expansion_kg_s, h_bc_exp, qm_asp,
                                  tab.h_primaire_kj_kg(t_asp), self.sources(self.pzr)):
            self.journal.ajouter(self.t_s, "automatisme", f"Ouverture soupape {s}", PRIORITE_HAUTE)
        # GV : eau alimentaire ARE + ASG
        h_are, h_asg = pe.h_alim_kj_kg, self.asg.h_eau_kj_kg
        for i, gv in enumerate(self.gvs):
            qm_are = pe.qm(f"L_ARE{gv.b}")
            qm_asg = max(0.0, self.asg.etat.qm_gv_kg_s[i])
            qm_alim = qm_are + qm_asg
            h_alim = (qm_are * h_are + qm_asg * h_asg) / qm_alim if qm_alim > 0.0 else h_are
            decharge = self.vapeur.qm_decharge_kg_s(i) + self.asg.vapeur_tps_par_gv_kg_s(gv.b)
            gv.avancer(dt, self.primaire.etat.q_gv_kw[i], qm_alim, h_alim, self.vapeur.etat.qm_lignes_kg_s[i], decharge)
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

    # ================================================================== mesures
    def masse_eau_totale_kg(self) -> float:
        """Secondaire : GV + puits + CST (circuit fermé hors décharges à l'atmosphère)."""
        return (sum(gv.vol.etat.m_kg for gv in self.gvs) + self.condenseur.puits.etat.m_kg
                + self.condenseur.cst.etat.m_kg)

    def masse_primaire_kg(self) -> float:
        """Primaire : nœuds liquides + pressuriseur."""
        return self.primaire.masse_liquide_kg() + self.pzr.vol.etat.m_kg

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
        else:
            obj.executer(action, valeur)  # type: ignore[attr-defined]

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
            "SUIVI": self.suivi,
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
        for vol in [gv.vol for gv in self.gvs] + [self.pzr.vol]:
            vol.mettre_a_jour()
        p_h = self.vapeur.etat.p_collecteur_bar
        self._qm_turbine = self.turbine.k_kg_s_bar() * p_h
        self._qm_gct = self.gct.k_kg_s_bar() * p_h
        self.historique.vider()
        self._mesurer()
