"""Électricité (§4.12) : réseau 400 kV, 6,6 kV normaux (LG), secourus (LH), diesels, 125 V continu (LB).

Sources des tableaux normaux LGA / LGB :
  alternateur couplé → transformateur de soutirage (TS) ; sinon réseau → transformateurs auxiliaires (TA)
  (basculement rapide automatique) ; sinon hors tension.
Tableaux secourus LHA / LHB : arrivée normale depuis LGA / LGB, ou diesel A / B.
  Sous-tension (< 62 % pendant 1 s) → délestage (toutes les pompes du tableau s'arrêtent), ouverture de
  l'arrivée normale, démarrage du diesel ; diesel à vitesse et tension (10 s) + tableau hors tension +
  arrivée ouverte → couplage, puis séquenceur (arrêt, ou accident si IS).
Batteries 125 V LBA / LBB : chargées depuis LHA / LHB ; sans chargeur, autonomie 2 h (A) / 30 min (B).
  Sans 125 V : contrôle-commande perdu (turbopompe ASG, électrovannes des VDA et des PORV).
Le réseau peut être perdu / rétabli par un scénario (ou par le formateur : repère RESEAU).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sim.components.base import Composant
from sim.components.pump import Pompe
from sim.config import DieselCfg, ElectriciteCfg
from sim.core.events import PRIORITE_HAUTE, PRIORITE_MOYENNE
from sim.units import POURCENT

if TYPE_CHECKING:
    from sim.plant import Centrale

TENSION_NOMINALE = POURCENT


# =============================================================================== diesel
@dataclass
class EtatDiesel:
    etat: str = "arret"               # arret | demarrage | pret | couple | echec
    t_demarrage_s: float = 0.0
    refus: bool = False                # panne : ne démarre pas
    reparation_t_s: float | None = None   # panne réparée à partir de cet instant (réarmement possible)
    charge_kw: float = 0.0
    surcharge_s: float = 0.0
    cause: str = ""


class Diesel(Composant):
    """Groupe électrogène de secours (repère DIESEL_A / DIESEL_B)."""

    type_ui = "diesel"

    def __init__(self, id: str, tableau: str, cfg: DieselCfg) -> None:
        super().__init__(id, tableau)
        self.cfg = cfg
        self.tableau = tableau
        self.etat = EtatDiesel()

    @property
    def en_service(self) -> bool:
        return self.etat.etat in ("demarrage", "pret", "couple")

    def demarrer(self) -> bool:
        e = self.etat
        if e.etat not in ("arret", "echec"):
            return True
        if e.refus:
            e.etat, e.cause = "echec", "refus de démarrage"
            return False
        e.etat, e.t_demarrage_s, e.cause = "demarrage", 0.0, ""
        return True

    def arreter(self, cause: str = "") -> None:
        self.etat.etat, self.etat.cause, self.etat.charge_kw = "arret", cause, 0.0

    def avancer(self, dt: float) -> None:
        e = self.etat
        if e.etat == "demarrage":
            e.t_demarrage_s += dt
            if e.t_demarrage_s >= self.cfg.temps_demarrage_s:
                e.etat = "pret"

    def commandes(self) -> list[str]:
        return ["demarrer", "arreter", "coupler", "decoupler", "rearmer"]

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        e = self.etat
        d.update(etat=e.etat, charge_kw=e.charge_kw, puissance_kw=self.cfg.puissance_kw, refus=e.refus,
                 cause=e.cause, en_service=self.en_service)
        return d


# =============================================================================== tableau secouru
@dataclass
class EtatTableau:
    tension_pct: float = TENSION_NOMINALE
    source: str = ""
    arrivee_fermee: bool = True        # disjoncteur d'arrivée depuis le tableau normal
    sous_tension_s: float = 0.0
    deleste: bool = False
    sequenceur_t_s: float | None = None    # temps depuis le couplage du diesel (séquenceur en cours)
    sequenceur_accident: bool = False
    etape: int = 0


class TableauSecouru(Composant):
    """Tableau 6,6 kV secouru (repère LHA / LHB)."""

    type_ui = "tableau"

    def __init__(self, id: str, normal: str, diesel: Diesel) -> None:
        super().__init__(id, "ELEC")
        self.normal = normal
        self.diesel = diesel
        self.etat = EtatTableau(source=normal)

    @property
    def sous_tension(self) -> bool:
        return self.etat.tension_pct >= TENSION_NOMINALE

    def commandes(self) -> list[str]:
        return ["ouvrir_arrivee", "fermer_arrivee"]

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        e = self.etat
        d.update(tension_pct=e.tension_pct, source=e.source, arrivee_fermee=e.arrivee_fermee,
                 sequenceur=e.sequenceur_t_s is not None, deleste=e.deleste)
        return d


# =============================================================================== ensemble
@dataclass
class EtatElectricite:
    reseau_ok: bool = True
    source_normale: str = "TS"                        # TS (soutirage) | TA (auxiliaires) | "" (hors tension)
    tensions_pct: dict[str, float] = field(default_factory=dict)   # tableaux normaux et batteries
    batteries_pct: dict[str, float] = field(default_factory=dict)
    cc_perdu: dict[str, bool] = field(default_factory=dict)


class Electricite(Composant):
    """Distribution électrique (repère RESEAU pour les commandes « formateur »)."""

    type_ui = "reseau"

    def __init__(self, cfg: ElectriciteCfg, pompes: dict[str, Pompe]) -> None:
        super().__init__("RESEAU", "ELEC")
        self.cfg = cfg
        self.pompes = pompes
        self.diesels: dict[str, Diesel] = {}
        self.tableaux: dict[str, TableauSecouru] = {}
        for lh, lg in zip(cfg.tableaux_secourus, cfg.tableaux_normaux):
            d = Diesel(f"DIESEL_{lh[-1]}", lh, cfg.diesel)
            self.diesels[d.id] = d
            self.tableaux[lh] = TableauSecouru(lh, lg, d)
        self.batterie_de = dict(zip(cfg.batteries, cfg.tableaux_secourus))
        self.etat = EtatElectricite(
            tensions_pct={k: TENSION_NOMINALE for k in cfg.tableaux_normaux + cfg.batteries},
            batteries_pct={k: POURCENT for k in cfg.batteries}, cc_perdu={k: False for k in cfg.batteries})

    # ------------------------------------------------------------------ disponibilité
    def tension_pct(self, tableau: str) -> float:
        if tableau in self.tableaux:
            return self.tableaux[tableau].etat.tension_pct
        return self.etat.tensions_pct.get(tableau, TENSION_NOMINALE)

    def sous_tension(self, tableau: str) -> bool:
        return self.tension_pct(tableau) >= TENSION_NOMINALE

    def charge_kw(self, tableau: str) -> float:
        """Charges en service sur un tableau secouru (pompes + charges fixes)."""
        total = self.cfg.charges_fixes_kw
        for p in self.pompes.values():
            if p.alim == tableau and p.etat.en_marche and p.cfg.puissance_kw:
                total += p.cfg.puissance_kw * p.etat.vitesse
        return total

    # ------------------------------------------------------------------ pas de calcul
    def avancer(self, dt: float, c: Centrale, injection_securite: bool) -> None:
        e, cfg = self.etat, self.cfg
        journal, t = c.journal, c.t_s
        # perte du réseau : la turbine se découple et déclenche (pas d'îlotage)
        if not e.reseau_ok and c.turbine.etat.couplee:
            c.turbine.declencher("perte du réseau 400 kV")
            journal.ajouter(t, "automatisme", "Perte du réseau : déclenchement turbine", PRIORITE_HAUTE)
        tu = c.turbine.etat
        alternateur = tu.couplee and not tu.declenchee
        source = "TS" if alternateur else ("TA" if e.reseau_ok else "")
        if source != e.source_normale:
            texte = {"TA": "Basculement rapide des tableaux normaux sur les transformateurs auxiliaires",
                     "TS": "Tableaux normaux sur le transformateur de soutirage",
                     "": "Tableaux 6,6 kV normaux hors tension"}[source]
            journal.ajouter(t, "automatisme", texte, PRIORITE_HAUTE if not source else PRIORITE_MOYENNE)
            e.source_normale = source
        for lg in cfg.tableaux_normaux:
            e.tensions_pct[lg] = TENSION_NOMINALE if source else 0.0
        for lh, tb in self.tableaux.items():
            self._tableau_secouru(dt, c, tb, injection_securite)
        self._batteries(dt, c)

    def _tableau_secouru(self, dt: float, c: Centrale, tb: TableauSecouru, injection_securite: bool) -> None:
        cfg, e, d = self.cfg, tb.etat, tb.diesel
        journal, t = c.journal, c.t_s
        d.avancer(dt)
        if injection_securite and d.etat.etat == "arret":
            d.demarrer()
        normal_ok = e.arrivee_fermee and self.etat.tensions_pct[tb.normal] >= TENSION_NOMINALE
        if normal_ok:
            e.tension_pct, e.source = TENSION_NOMINALE, tb.normal
            if d.etat.etat == "couple":                # transfert sur l'arrivée normale : le diesel se découple
                d.etat.etat = "pret"
        elif d.etat.etat == "couple":
            e.tension_pct, e.source = TENSION_NOMINALE, d.id
        else:
            e.tension_pct, e.source = 0.0, ""
        # sous-tension : délestage, ouverture de l'arrivée, démarrage du diesel
        if e.tension_pct < cfg.sous_tension_pct:
            e.sous_tension_s += dt
            if e.sous_tension_s >= cfg.sous_tension_delai_s and not e.deleste:
                e.deleste = True
                e.arrivee_fermee = False
                e.sequenceur_t_s = None
                for p in self.pompes.values():
                    if p.alim == tb.id and p.etat.en_marche:
                        p.declencher(f"délestage {tb.id}")
                ok = d.demarrer()
                journal.ajouter(t, "automatisme", f"Sous-tension {tb.id} : délestage, démarrage {d.id}"
                                + ("" if ok else " — ÉCHEC du démarrage"), PRIORITE_HAUTE)
        else:
            e.sous_tension_s = 0.0
            e.deleste = False
        # couplage automatique du diesel sur le tableau mort
        if d.etat.etat == "pret" and e.tension_pct <= 0.0 and not e.arrivee_fermee:
            self.coupler(c, tb)
        # séquenceur
        if e.sequenceur_t_s is not None:
            e.sequenceur_t_s += dt
            etapes = cfg.sequenceur_accident if e.sequenceur_accident else cfg.sequenceur_arret
            while e.etape < len(etapes) and e.sequenceur_t_s >= etapes[e.etape].t_s:
                rep = etapes[e.etape].pompes.get(tb.id)
                p = self.pompes.get(rep) if rep else None
                if p is not None and not p.etat.en_marche:
                    p.demarrer()
                    journal.ajouter(t, "automatisme", f"Séquenceur {tb.id} : démarrage {p.id}", PRIORITE_MOYENNE)
                e.etape += 1
            if e.etape >= len(etapes):
                e.sequenceur_t_s = None
        # charge et surcharge du diesel
        if d.etat.etat == "couple":
            d.etat.charge_kw = self.charge_kw(tb.id)
            limite = d.cfg.puissance_kw * d.cfg.surcharge_pct / POURCENT
            d.etat.surcharge_s = d.etat.surcharge_s + dt if d.etat.charge_kw > limite else 0.0
            if d.etat.surcharge_s > d.cfg.surcharge_delai_s:
                d.arreter("surcharge")
                journal.ajouter(t, "automatisme", f"{d.id} déclenché sur surcharge", PRIORITE_HAUTE)
        else:
            d.etat.charge_kw = 0.0

    def coupler(self, c: Centrale, tb: TableauSecouru) -> None:
        d, e = tb.diesel, tb.etat
        d.etat.etat = "couple"
        e.tension_pct, e.source = TENSION_NOMINALE, d.id
        e.sequenceur_t_s, e.etape = 0.0, 0
        e.sequenceur_accident = c.logique.etat.is_actif
        nom = "accident" if e.sequenceur_accident else "arrêt"
        c.journal.ajouter(c.t_s, "automatisme", f"{d.id} couplé sur {tb.id} : séquenceur {nom}", PRIORITE_HAUTE)

    def _batteries(self, dt: float, c: Centrale) -> None:
        e, cfg = self.etat, self.cfg
        for lb, lh in self.batterie_de.items():
            if self.tableaux[lh].sous_tension:
                e.batteries_pct[lb] = min(POURCENT, e.batteries_pct[lb] + POURCENT * dt / cfg.batterie_recharge_s)
            else:
                e.batteries_pct[lb] = max(0.0, e.batteries_pct[lb] - POURCENT * dt / cfg.batterie_autonomie_s[lb])
            e.tensions_pct[lb] = TENSION_NOMINALE if e.batteries_pct[lb] > 0.0 else 0.0
            perdu = e.tensions_pct[lb] <= 0.0
            if perdu and not e.cc_perdu[lb]:
                c.journal.ajouter(c.t_s, "automatisme", f"Batterie {lb} épuisée : contrôle-commande perdu",
                                  PRIORITE_HAUTE)
            e.cc_perdu[lb] = perdu
            if perdu:
                for rep in cfg.commande_cc.get(lb, []):
                    p = self.pompes.get(rep)
                    if p is not None and p.etat.en_marche:
                        p.declencher(f"perte du 125 V {lb}")

    def batterie_en_decharge(self, lb: str) -> bool:
        return not self.tableaux[self.batterie_de[lb]].sous_tension

    # ------------------------------------------------------------------ commandes « formateur » (RESEAU)
    def commandes(self) -> list[str]:
        return ["perte_reseau", "retour_reseau"]

    def executer(self, action: str, valeur: float | None) -> None:
        self.etat.reseau_ok = action == "retour_reseau"

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        e = self.etat
        d.update(reseau_ok=e.reseau_ok, source_normale=e.source_normale, batteries_pct=dict(e.batteries_pct))
        return d

    # ------------------------------------------------------------------ sauvegarde
    def exporter_etat(self) -> dict[str, Any]:
        return {"general": vars(self.etat).copy(),
                "diesels": {k: vars(d.etat).copy() for k, d in self.diesels.items()},
                "tableaux": {k: vars(tb.etat).copy() for k, tb in self.tableaux.items()}}

    def importer_etat(self, d: dict[str, Any]) -> None:
        self.etat = EtatElectricite(**d["general"])
        for k, v in d["diesels"].items():
            self.diesels[k].etat = EtatDiesel(**v)
        for k, v in d["tableaux"].items():
            self.tableaux[k].etat = EtatTableau(**v)
