"""Poste d'eau : CEX → ABP → (reprise des purges) → APP / APD → AHP → ARE → GV.

Le réseau liquide est décrit dans plant.yaml (reseaux.eau_alimentaire) et
résolu par le solveur générique. Ce module fixe les pressions aux frontières,
les masses volumiques par zone de température et l'injection des purges.
Réchauffeurs : température de sortie = table(charge) avec une inertie du 1er ordre
(leur stockage d'énergie n'est pas suivi : bilan exact à l'équilibre seulement).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.components.base import Composant
from sim.components.pump import Pompe
from sim.components.valve import Clapet
from sim.config import NumeriqueCfg, PosteEauCfg, ReseauCfg
from sim.core.network import construire_reseau
from sim.thermo.tables import TableEau
from sim.units import POURCENT, interp_table, kg_s_vers_m3h, m3h_vers_kg_s

# zone de température de l'eau selon le nœud amont de chaque branche
ZONE_CONDENSAT = ("PUITS", "CONDENSEUR", "N_CEX")
ZONE_BP = ("N_ABP", "N_APP")
ZONE_HP = ("N_ARE",)


@dataclass
class EtatPosteEau:
    t_abp_c: float
    t_ahp_c: float
    qm_purges_kg_s: float          # purges produites par les soutirages
    qm_reprise_kg_s: float         # reprises par les pompes de reprise
    qm_branches_kg_s: dict[str, float]


class PosteEau:
    """Réseau d'eau alimentaire."""

    def __init__(self, cfg: PosteEauCfg, reseau_cfg: ReseauCfg, composants: dict[str, Composant],
                 num: NumeriqueCfg, table: TableEau, debit_purges_nom_kg_s: float,
                 t_initiale_c: float, p_initiale_bar: float) -> None:
        self.cfg = cfg
        self.table = table
        self.composants = composants
        self.reprise: list[Pompe] = [composants[r] for r in cfg.reprise.pompes]  # type: ignore[misc]
        self.capacite_pompe_reprise_kg_s = cfg.reprise.capacite_pompe_pct / POURCENT * debit_purges_nom_kg_s
        self.reseau = construire_reseau("eau_alimentaire", reseau_cfg, composants, num.reseau,
                                        table.rho_liq_kg_m3(t_initiale_c), p_initiale_bar)
        branches = self.reseau.branches
        self.clapets = [(br, el) for br in branches for el in br.elements if isinstance(el, Clapet)]
        self.etat = EtatPosteEau(t_abp_c=t_initiale_c, t_ahp_c=t_initiale_c, qm_purges_kg_s=0.0,
                                 qm_reprise_kg_s=0.0, qm_branches_kg_s={b.id: 0.0 for b in branches})

    # --- grandeurs ---
    def qm(self, branche: str) -> float:
        return self.etat.qm_branches_kg_s[branche]

    @property
    def h_alim_kj_kg(self) -> float:
        return self.table.h_liq_kj_kg(self.etat.t_ahp_c)

    def p(self, noeud: str) -> float:
        return self.reseau.p(noeud)

    def debit_cex_m3h(self, rho_kg_m3: float) -> float:
        return kg_s_vers_m3h(sum(max(0.0, self.qm(b)) for b in ("L_CEX1", "L_CEX2")), rho_kg_m3)

    # --- calcul ---
    def resoudre(self, frontieres_bar: dict[str, float], t_condensat_c: float, t_cst_c: float,
                 qm_purges_kg_s: float) -> None:
        """Résout le réseau (débits de toutes les branches)."""
        for nom, p in frontieres_bar.items():
            self.reseau.fixer_frontiere(nom, p)
        capacite = sum(p.etat.vitesse for p in self.reprise) * self.capacite_pompe_reprise_kg_s
        rep = self.cfg.reprise
        self.etat.qm_purges_kg_s = qm_purges_kg_s
        self.reseau.fixer_injection("N_ABP", min(qm_purges_kg_s, capacite), rep.p_plein_debit_bar, rep.p_arret_bar)
        rho = {
            "condensat": self.table.rho_liq_kg_m3(t_condensat_c),
            "cst": self.table.rho_liq_kg_m3(t_cst_c),
            "bp": self.table.rho_liq_kg_m3(self.etat.t_abp_c),
            "hp": self.table.rho_liq_kg_m3(self.etat.t_ahp_c),
        }
        for b in self.reseau.branches:
            zone = ("bp" if b.de in ZONE_BP else "hp" if b.de in ZONE_HP
                    else "cst" if b.de == "CST" else "condensat")
            b.rho_kg_m3 = rho[zone]
        self.reseau.resoudre()
        self.etat.qm_reprise_kg_s = self.reseau.injections["N_ABP"].qm_kg_s
        for b in self.reseau.branches:
            self.etat.qm_branches_kg_s[b.id] = b.qm_kg_s
        for br, clapet in self.clapets:
            clapet.ouvert = br.qm_kg_s > m3h_vers_kg_s(clapet.cfg.kv_max, br.rho_kg_m3) * self.reseau.num.zone_lineaire_bar

    def avancer_rechauffeurs(self, dt: float, charge_pct: float, t_condensat_c: float) -> None:
        r = self.cfg.rechauffeurs
        cible_bp = max(t_condensat_c, interp_table(r.abp_sortie_c, charge_pct))
        cible_hp = max(cible_bp, interp_table(r.ahp_sortie_c, charge_pct))
        a = min(1.0, dt / r.tau_s)
        self.etat.t_abp_c += a * (cible_bp - self.etat.t_abp_c)
        self.etat.t_ahp_c += a * (cible_hp - self.etat.t_ahp_c)

    def exporter_etat(self) -> dict[str, Any]:
        return {"poste": vars(self.etat).copy(), "reseau": {"p_bar": dict(self.reseau.etat.p_bar)}}

    def importer_etat(self, donnees: dict[str, Any]) -> None:
        self.etat = EtatPosteEau(**donnees["poste"])
        self.reseau.etat.p_bar = dict(donnees["reseau"]["p_bar"])
        for b in self.reseau.branches:
            b.qm_kg_s = self.etat.qm_branches_kg_s[b.id]
