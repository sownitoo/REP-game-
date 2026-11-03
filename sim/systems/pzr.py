"""Pressuriseur (§4.1) : volume diphasique à saturation qui fixe la pression du primaire.

- Chaufferettes : groupe proportionnel + groupes tout-ou-rien (coupés si niveau < 17 %).
- Aspersion : 2 vannes alimentées par les branches froides B2/B3 (débit ∝ vitesse des
  pompes primaires) + débit permanent.
- 2 PORV (pneumatiques, réserve d'air) derrière leur vanne d'isolement, 3 soupapes.
- Expansion : entrée d'eau de la branche chaude B2 ou sortie d'eau saturée.
Modèle à 1 zone (équilibre liquide/vapeur), l'option 2 zones de la spec n'est pas faite.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sim.components.base import Composant, Sources
from sim.components.relief import Soupape
from sim.components.sensor import Capteur
from sim.components.valve import Vanne
from sim.components.volume2phase import Volume2Phase
from sim.config import FlashCfg, PressuriseurCfg
from sim.thermo.tables import TableEau
from sim.units import KW_PAR_MW, POURCENT, S_PAR_H, interp_table


@dataclass
class EtatChaufferettes:
    auto: bool
    demande_auto: float          # 0..1
    demande_manu: float          # 0..1
    coupe: str                   # raison de coupure automatique ("" = aucune)
    puissance_kw: float


class GroupeChaufferettes(Composant):
    """Groupe de chaufferettes (proportionnel ou tout-ou-rien)."""

    type_ui = "chaufferettes"

    def __init__(self, id: str, puissance_kw: float, proportionnel: bool, alim: str | None) -> None:
        super().__init__(id, "RCP", alim)
        self.puissance_max_kw = puissance_kw
        self.proportionnel = proportionnel
        self.etat = EtatChaufferettes(auto=True, demande_auto=0.0, demande_manu=0.0, coupe="", puissance_kw=0.0)

    def commandes(self) -> list[str]:
        return ["auto", "manu", "puissance"]

    def executer(self, action: str, valeur: float | None) -> None:
        e = self.etat
        if action == "auto":
            e.auto = True
        elif action == "manu":
            e.auto = False
            e.demande_manu = e.puissance_kw / self.puissance_max_kw
        elif action == "puissance" and valeur is not None:
            frac = valeur / POURCENT
            e.demande_manu = frac if self.proportionnel else float(frac > 0.0)

    def avancer(self, sources: Sources) -> None:
        e = self.etat
        demande = e.demande_auto if e.auto else e.demande_manu
        if e.coupe or not sources.electricite_ok:
            demande = 0.0
        e.puissance_kw = self.puissance_max_kw * min(max(demande, 0.0), 1.0)

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        d.update(auto=self.etat.auto, puissance_kw=self.etat.puissance_kw, coupe=self.etat.coupe,
                 proportionnel=self.proportionnel, puissance_pct=POURCENT * self.etat.puissance_kw / self.puissance_max_kw)
        return d


@dataclass
class EtatPressuriseur:
    qm_aspersion_kg_s: float
    qm_porv_kg_s: float
    qm_soupapes_kg_s: float
    q_chauffe_kw: float


class Pressuriseur(Composant):
    """Pressuriseur (repère PZR)."""

    type_ui = "pzr"

    def __init__(self, cfg: PressuriseurCfg, composants: dict[str, Composant],
                 table: TableEau, flash: FlashCfg, boucles_aspersion: list[int]) -> None:
        super().__init__("PZR", "RCP")
        self.cfg = cfg
        self.table = table
        self.vol = Volume2Phase(cfg.volume_m3, table, flash)
        self.chauffe_prop = GroupeChaufferettes("PZR_CHAUF_P", cfg.chaufferettes.proportionnelles_kw, True, "LGA")
        self.chauffe_tor = GroupeChaufferettes("PZR_CHAUF_T", cfg.chaufferettes.tor_kw, False, "LHB")   # groupe de secours (HYPOTHESE)
        self.aspersion: list[Vanne] = [composants[f"PZR_ASP{b}"] for b in boucles_aspersion]   # type: ignore[misc]
        self.porv: list[Vanne] = [composants["PZR_PORV1"], composants["PZR_PORV2"]]          # type: ignore[list-item]
        self.isol: list[Vanne] = [composants["PZR_ISOL1"], composants["PZR_ISOL2"]]          # type: ignore[list-item]
        s = cfg.soupapes
        self.soupapes = [Soupape(f"PZR_SOUP{n}", "RCP", tarage, s.capacite_kg_s, s.fermeture_pct)
                         for n, tarage in enumerate(s.tarages_bar, start=1)]
        self.capteur_p = Capteur("PZR_P", "RCP", cfg.voies_pression, cfg.retard_mesure_s, 0.0,
                                 cfg.gamme_pression_bar, 0.0)
        self.capteur_niveau = Capteur("PZR_NIV", "RCP", cfg.voies_niveau, cfg.retard_mesure_s, 0.0, POURCENT, 0.0)
        self.etat = EtatPressuriseur(qm_aspersion_kg_s=0.0, qm_porv_kg_s=0.0, qm_soupapes_kg_s=0.0, q_chauffe_kw=0.0)

    def initialiser(self, p_bar: float, niveau_pct: float) -> None:
        s = self.table.sat(p_bar)
        self.vol.initialiser(p_bar, niveau_pct / POURCENT * self.cfg.volume_m3 / s.vf_m3_kg)
        self.capteur_p.initialiser(p_bar)
        self.capteur_niveau.initialiser(self.niveau_pct)

    # ------------------------------------------------------------------ grandeurs
    @property
    def p_bar(self) -> float:
        return self.vol.p_bar

    @property
    def niveau_pct(self) -> float:
        return POURCENT * self.vol.v_liq_m3 / self.cfg.volume_m3

    def niveau_programme_pct(self, tmoy_c: float) -> float:
        return interp_table(self.cfg.programme_niveau_pct, tmoy_c)

    def debit_aspersion_kg_s(self, vitesses_pompes: list[float], rho_kg_m3: float) -> float:
        """Aspersion : débit ∝ ouverture × vitesse de la pompe de la boucle d'origine, + débit permanent."""
        a = self.cfg.aspersion
        debit_m3h = sum(v.etat.position * a.debit_vanne_m3h * s for v, s in zip(self.aspersion, vitesses_pompes))
        debit_m3h += a.debit_permanent_m3h * max(vitesses_pompes, default=0.0)
        return debit_m3h * rho_kg_m3 / S_PAR_H

    def debit_porv_kg_s(self) -> float:
        c = self.cfg.porv
        return sum(c.capacite_kg_s * min(p.etat.position, i.etat.position) * self.p_bar / c.p_ref_bar
                   for p, i in zip(self.porv, self.isol))

    # ------------------------------------------------------------------ dynamique
    def avancer(self, dt: float, qm_expansion_kg_s: float, h_branche_chaude_kj_kg: float,
                qm_aspersion_kg_s: float, h_aspersion_kj_kg: float,
                sources: Callable[[Composant], Sources]) -> list[str]:
        """Bilans du pressuriseur ; renvoie les soupapes qui viennent de s'ouvrir."""
        e, s = self.etat, self.vol.sat
        for ch in (self.chauffe_prop, self.chauffe_tor):
            ch.avancer(sources(ch))
        e.q_chauffe_kw = self.chauffe_prop.etat.puissance_kw + self.chauffe_tor.etat.puissance_kw
        e.qm_aspersion_kg_s = qm_aspersion_kg_s
        e.qm_porv_kg_s = self.debit_porv_kg_s()
        ouvertures = [sp.id for sp in self.soupapes if sp.mettre_a_jour(self.p_bar)]
        e.qm_soupapes_kg_s = sum(sp.debit_kg_s(self.p_bar) for sp in self.soupapes)
        qm_vapeur = e.qm_porv_kg_s + e.qm_soupapes_kg_s
        entree_kg_s = qm_aspersion_kg_s
        entree_kw = qm_aspersion_kg_s * h_aspersion_kj_kg + e.q_chauffe_kw
        sortie_kg_s = qm_vapeur
        sortie_kw = qm_vapeur * s.hg_kj_kg + self.cfg.pertes_thermiques_kw
        if qm_expansion_kg_s >= 0.0:
            entree_kg_s += qm_expansion_kg_s
            entree_kw += qm_expansion_kg_s * h_branche_chaude_kj_kg
        else:
            sortie_kg_s -= qm_expansion_kg_s
            sortie_kw -= qm_expansion_kg_s * s.hf_kj_kg
        self.vol.integrer(dt, entree_kg_s, entree_kw, sortie_kg_s, sortie_kw)
        self.capteur_p.mesurer(dt, self.p_bar)
        self.capteur_niveau.mesurer(dt, self.niveau_pct)
        return ouvertures

    def nb_soupapes_ouvertes(self) -> int:
        return sum(sp.etat.ouverte for sp in self.soupapes)

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        d.update(p_bar=self.p_bar, niveau_pct=self.niveau_pct, chauffe_mw=self.etat.q_chauffe_kw / KW_PAR_MW,
                 aspersion_kg_s=self.etat.qm_aspersion_kg_s, porv_kg_s=self.etat.qm_porv_kg_s,
                 voies_pression=self.capteur_p.etat.valeurs, voies_niveau=self.capteur_niveau.etat.valeurs)
        return d
