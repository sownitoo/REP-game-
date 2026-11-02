"""Assemblage de la centrale V0 et boucle de calcul d'un pas de temps (§2.3).

Ordre d'un pas :
  1. commandes joueur (appliquées dès réception, entre deux pas)
  2. électricité (V0 : stub, tout est sous tension)
  3. logique : capteurs → permissifs → AU → automatismes
  4. régulations → demandes des actionneurs, puis mouvement des actionneurs
  5. hydraulique : collecteur vapeur, réseau d'eau alimentaire
  6. thermique : GV, turbine, condenseur, bâches, réchauffeurs
  7. source de chaleur (cœur en V1)
  8. mesures, alarmes, historique
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from sim.components.base import Composant, Condition, Sources
from sim.components.pump import Pompe
from sim.components.valve import Clapet, Resistance, Vanne
from sim.config import (CentraleCfg, ClapetCfg, PompeCfg, ResistanceCfg, VanneCfg, charger_config)
from sim.core.events import PRIORITE_HAUTE, PRIORITE_INFO, GestionAlarmes, Journal
from sim.core.history import Historique
from sim.logic import interlocks
from sim.logic.protection import Logique
from sim.logic.regulations import Regulations
from sim.systems.condenseur import Condenseur
from sim.systems.gct import Contournement
from sim.systems.gv import GenerateurVapeur
from sim.systems.poste_eau import PosteEau
from sim.systems.source_v0 import SourceV0
from sim.systems.turbine import Turbine
from sim.systems.vvp import Vapeur
from sim.thermo.tables import obtenir_table
from sim.units import KG_PAR_T, KW_PAR_MW, POURCENT, interp_table

VERSION_SAUVEGARDE = 1


@dataclass
class Reponse:
    """Réponse à une commande joueur."""

    ok: bool
    raisons: list[str]


class Centrale:
    """Centrale V0 : boucle secondaire chauffée par une source imposée."""

    def __init__(self, cfg: CentraleCfg | None = None) -> None:
        self.cfg = cfg = cfg or charger_config()
        n = cfg.numerique
        self.table = obtenir_table(n.table_p_min_bar, n.table_p_max_bar, n.table_nb_points, n.table_t_pas_c)
        self.boucles = cfg.generateurs_vapeur.boucles
        self.dt_s = cfg.simulation.dt_s
        self.t_s = 0.0
        self.inhiber_protections = False    # utilisé seulement pour stabiliser l'état initial
        self.journal = Journal(cfg.simulation.journal_max)
        self.alarmes = GestionAlarmes(cfg.alarmes, n.alarmes_hysteresis_pct)
        self.historique = Historique(cfg.simulation.historique_duree_s, cfg.simulation.historique_pas_s,
                                     cfg.simulation.dt_s)
        self.mesures: dict[str, float] = {}

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
        self.apps = [p for k, p in self.pompes.items() if p.cfg.systeme == "APP" and p.cfg.vitesse_variable]
        self.cexs = [p for p in self.pompes.values() if p.cfg.systeme == "CEX"]
        self.crfs = [p for p in self.pompes.values() if p.cfg.systeme == "CRF"]

        # --- systèmes ---
        nom = cfg.point_nominal
        self.source = SourceV0(cfg.source_v0, cfg.coeur, nom, self.dt_s)
        self.gvs = [GenerateurVapeur(b, cfg.generateurs_vapeur, self.table, n.flash) for b in self.boucles]
        self.vapeur = Vapeur(cfg.vapeur, self.boucles, self.composants, self.table, n.collecteur)
        self.turbine = Turbine(cfg.turbine, self.table)
        self.gct = Contournement(cfg.gct_c, self.composants)
        self.condenseur = Condenseur(cfg.condenseur, cfg.puits, cfg.cst, self.crfs, self.table,
                                     cfg.condenseur.t_mer_c)
        debit_purges_nom = cfg.turbine.fraction_soutirage * cfg.turbine.debit_nom_kg_s
        self.poste_eau = PosteEau(cfg.poste_eau, cfg.reseaux["eau_alimentaire"], self.composants, n,
                                  self.table, debit_purges_nom, cfg.condenseur.t_mer_c,
                                  cfg.simulation.p_atm_bar)
        self.logique = Logique(self)
        self.regulations = Regulations(cfg.regulations, self)

        # --- objets manœuvrables par le joueur ---
        self.commandables: dict[str, Composant] = {
            **self.pompes, **self.vannes,
            self.turbine.id: self.turbine, self.source.id: self.source, self.logique.id: self.logique,
            self.gct.id: self.gct, self.regulations.reg_vda.id: self.regulations.reg_vda,
            self.regulations.reg_puits.id: self.regulations.reg_puits,
        }
        self.initialiser_100pct()

    # ================================================================== utilitaires
    def gv(self, b: int) -> GenerateurVapeur:
        return self.gvs[self.boucles.index(b)]

    def sources(self, composant: Composant) -> Sources:
        """Électricité et air disponibles pour ce composant (V0 : toujours disponibles)."""
        return Sources()

    # ================================================================== initialisation
    def initialiser_100pct(self) -> None:
        """État approché du point nominal 100 % (à stabiliser ensuite, cf. sim.tools.etat_initial)."""
        cfg, nom = self.cfg, self.cfg.point_nominal
        self.t_s = 0.0
        h_alim = self.table.h_liq_kj_kg(nom.t_alim_c)
        qm_gv = nom.qm_vapeur_kg_s / len(self.gvs)
        for gv in self.gvs:
            gv.initialiser(nom.p_gv_bar, nom.niveau_gv_pct, qm_gv, h_alim)
        self.source.etat.tmoy_c = nom.tmoy_c
        self.source.etat.p_kw = nom.p_source_mw * KW_PAR_MW
        self.vapeur.etat.p_collecteur_bar = nom.p_collecteur_bar
        # pompes en service
        for p in self.crfs + self.cexs + self.apps + [self.pompes[r] for r in cfg.poste_eau.reprise.pompes]:
            p.demarrer()
            p.etat.vitesse = p.consigne_vitesse()
        for a in self.apps:
            a.etat.consigne_auto = a.etat.vitesse = 1.0
        # vannes
        for b in self.boucles:
            for rep in (f"ARE{b}_ISOL", f"VIV{b}"):
                v = self.vannes[rep]
                v.etat.position = v.etat.demande_manu = 1.0
        # turbine couplée au nominal
        t, tc = self.turbine.etat, cfg.turbine
        t.declenchee, t.cause, t.couplee = False, "", True
        t.positions_arret = [1.0] * tc.vannes_arret
        t.y_reglage = t.demande_reglage = tc.ouverture_nom
        t.vitesse_tr_min = t.consigne_vitesse_tr_min = t.consigne_vitesse_eff_tr_min = tc.vitesse_nom_tr_min
        t.consigne_mw = t.consigne_eff_mw = tc.p_elec_nom_mw
        # condenseur : température d'équilibre estimée (chaleur = source − puissance mécanique)
        cd = cfg.condenseur
        q_cond_kw = (nom.p_source_mw - tc.p_elec_nom_mw / tc.rendement_alternateur) * KW_PAR_MW
        mcp = self.condenseur.qm_crf_kg_s() * cd.cp_eau_mer_kj_kgk
        eff = 1.0 - math.exp(-cd.ua_mw_c * KW_PAR_MW / mcp)
        self.condenseur.etat.t_c = cd.t_mer_c + q_cond_kw / (eff * mcp)
        self.condenseur.integrer(0.0, q_cond_kw)
        self.turbine.calculer_puissance(0.0, nom.qm_vapeur_kg_s, nom.p_collecteur_bar, self.condenseur.etat.p_bar)
        # réchauffeurs au nominal
        r = cfg.poste_eau.rechauffeurs
        self.poste_eau.etat.t_abp_c = interp_table(r.abp_sortie_c, POURCENT)
        self.poste_eau.etat.t_ahp_c = interp_table(r.ahp_sortie_c, POURCENT)
        # quelques allers-retours régulations ↔ hydraulique pour placer vannes et pompes
        # (dt = 0 : les régulateurs n'intègrent pas pendant ce calage)
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
        self._mesurer()

    # ================================================================== pas de temps
    def pas(self) -> None:
        dt = self.dt_s
        # 3. logique
        self.logique.evaluer(dt)
        # 4. régulations puis actionneurs
        self.regulations.calculer(dt)
        self.turbine.reguler(dt, self.vapeur.etat.p_collecteur_bar)
        for c in list(self.pompes.values()) + list(self.vannes.values()):
            c.avancer(dt, self.sources(c))
        # 5. hydraulique
        self._resoudre_hydraulique()
        # 6. thermique
        self._bilans_thermiques(dt)
        # 8. mesures
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
        k_turbine = self.turbine.k_kg_s_bar()
        k_gct = self.gct.k_kg_s_bar()
        self.vapeur.resoudre(self.dt_s, self.gvs, k_turbine + k_gct, cd.etat.p_bar)
        p_h = self.vapeur.etat.p_collecteur_bar
        self._qm_turbine = k_turbine * p_h
        self._qm_gct = k_gct * p_h
        for s in self.vapeur.decharges(self.gvs):
            self.journal.ajouter(self.t_s, "automatisme", f"Ouverture soupape {s}", PRIORITE_HAUTE)
        frontieres = {"PUITS": cd.p_aspiration_cex_bar(), "CONDENSEUR": cd.etat.p_bar,
                      "CST": cd.p_fond_cst_bar(self.cfg.simulation.p_atm_bar)}
        frontieres.update({gv.id: gv.p_bar for gv in self.gvs})
        purges = self.cfg.turbine.fraction_soutirage * self._qm_turbine
        self.poste_eau.resoudre(frontieres, cd.etat.t_c, self.cfg.cst.t_c, purges)

    def _bilans_thermiques(self, dt: float) -> None:
        pe, cd, src = self.poste_eau, self.condenseur, self.source
        h_alim = pe.h_alim_kj_kg
        q_total = 0.0
        for i, gv in enumerate(self.gvs):
            q = src.chaleur_gv_kw(gv.ua_kw_c(), gv.tsat_c)
            q_total += q
            gv.avancer(dt, q, pe.qm(f"L_ARE{gv.b}"), h_alim, self.vapeur.etat.qm_lignes_kg_s[i],
                       self.vapeur.qm_decharge_kg_s(i))
        # turbine
        p_h = self.vapeur.etat.p_collecteur_bar
        self.turbine.calculer_puissance(dt, self._qm_turbine, p_h, cd.etat.p_bar)
        # condenseur : énergie restante après travail et réchauffage de l'eau alimentaire
        h_col, h_puits = self.vapeur.etat.h_collecteur_kj_kg, cd.h_puits_kj_kg
        qm_alim = sum(pe.qm(f"L_ARE{b}") for b in self.boucles)
        q_rechauffeurs = qm_alim * (h_alim - h_puits)
        qm_vapeur = self._qm_turbine + self._qm_gct
        q_cond = (qm_vapeur * (h_col - h_puits) - self.turbine.etat.p_meca_mw * KW_PAR_MW - q_rechauffeurs)
        cd.integrer(dt, max(0.0, q_cond))
        # puits : condensat turbine + purges non reprises + contournement + recirculation + appoint − CEX
        purges_condenseur = pe.etat.qm_purges_kg_s - pe.etat.qm_reprise_kg_s
        entree = (self._qm_turbine * (1.0 - self.cfg.turbine.fraction_soutirage) + purges_condenseur
                  + self._qm_gct + pe.qm("L_RECIRC") + pe.qm("L_APPOINT"))
        sortie = pe.qm("L_CEX1") + pe.qm("L_CEX2")
        cd.puits.integrer(dt, entree - sortie)
        cd.cst.integrer(dt, pe.qm("L_REJET") - pe.qm("L_APPOINT"))
        pe.avancer_rechauffeurs(dt, self.turbine.charge_pct, cd.etat.t_c)
        # 7. source
        src.avancer(dt, q_total, self.turbine.charge_pct)

    # ================================================================== mesures
    def masse_eau_totale_kg(self) -> float:
        """GV + puits + CST (circuit fermé hors décharges à l'atmosphère)."""
        return sum(gv.vol.etat.m_kg for gv in self.gvs) + self.condenseur.puits.etat.m_kg + self.condenseur.cst.etat.m_kg

    def _mesurer(self) -> None:
        m: dict[str, float] = {}
        pe, cd, t, src, lg = self.poste_eau, self.condenseur, self.turbine.etat, self.source.etat, self.logique.etat
        for i, gv in enumerate(self.gvs):
            k = gv.id
            m[f"{k}.niveau_pct"] = gv.capteur.mediane
            m[f"{k}.niveau_vrai_pct"] = gv.niveau_pct
            m[f"{k}.p_bar"] = gv.p_bar
            m[f"{k}.qm_vapeur_kg_s"] = gv.etat.qm_ligne_kg_s
            m[f"{k}.qm_alim_kg_s"] = gv.etat.qm_alim_kg_s
            m[f"{k}.q_mw"] = gv.etat.q_kw / KW_PAR_MW
            m[f"{k}.m_eau_t"] = gv.vol.m_liq_kg / KG_PAR_T
            m[f"{k}.qm_decharge_kg_s"] = self.vapeur.qm_decharge_kg_s(i)
        m["source.p_mw"] = src.p_kw / KW_PAR_MW
        m["source.puissance_pct"] = self.source.puissance_pct
        m["source.tmoy_c"] = src.tmoy_c
        m["source.tref_c"] = src.tref_c
        m["source.ecart_tref_abs_c"] = abs(src.tmoy_c - src.tref_c)
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
        for noeud in pe.reseau.noeuds:
            m[f"{noeud}.p_bar"] = pe.p(noeud)
        for p in self.pompes.values():
            m[f"{p.id}.vitesse_pct"] = POURCENT * p.etat.vitesse
        m["crf.debit_m3s"] = cd.qm_crf_kg_s() / self.cfg.condenseur.rho_eau_mer_kg_m3
        m["bilan.masse_eau_t"] = self.masse_eau_totale_kg() / KG_PAR_T
        m["logique.au"] = float(lg.au)
        m["logique.p7"] = float(lg.p7)
        m["logique.p14"] = float(lg.p14)
        m["logique.c9"] = float(lg.c9)
        m["logique.turbine_declenchee"] = float(t.declenchee)
        m["logique.isolement_are"] = float(lg.isolement_are_au or lg.isolement_are_complet)
        m["logique.app_declenchee"] = float(lg.app_declenchee)
        m["logique.cex_declenchee"] = float(lg.cex_declenchee)
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
        objets.update({"SOURCE": self.source, "TURBINE": self.turbine, "CONDENSEUR": self.condenseur,
                       "REG_GCTC": self.gct, "REG_VDA": self.regulations.reg_vda,
                       "REG_PUITS": self.regulations.reg_puits})
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
        for gv in self.gvs:
            gv.vol.mettre_a_jour()
        p_h = self.vapeur.etat.p_collecteur_bar
        self._qm_turbine = self.turbine.k_kg_s_bar() * p_h
        self._qm_gct = self.gct.k_kg_s_bar() * p_h
        self.historique.vider()
        self._mesurer()
