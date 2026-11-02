"""Vapeur principale (VVP) : 4 lignes GV → collecteur, VIV (+ by-pass), VDA, soupapes.

Collecteur quasi statique : Σ débits des lignes = turbine + contournement.
Ligne : ṁ = C·y·√(ρ·ΔP), clapet anti-retour, limiteur de débit (venturi).
Couplage GV ↔ ligne traité en implicite : la pression du GV en fin de pas
dépend du débit soutiré (P_GV − s·ṁ·dt), d'où ṁ² + a·ṁ − c = 0 en forme fermée.
C'est ce qui rend le calcul stable même quand les GV s'équilibrent entre eux.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from sim.components.base import Composant
from sim.components.relief import Soupape
from sim.components.valve import Vanne
from sim.config import CollecteurNumCfg, VapeurCfg
from sim.systems.gv import GenerateurVapeur
from sim.thermo.tables import TableEau


@dataclass
class EtatVapeur:
    p_collecteur_bar: float
    h_collecteur_kj_kg: float
    qm_lignes_kg_s: list[float]
    qm_vda_kg_s: list[float]
    qm_soupapes_kg_s: list[float]


class Vapeur:
    """Lignes vapeur et collecteur."""

    def __init__(self, cfg: VapeurCfg, boucles: list[int], composants: dict[str, Composant],
                 table: TableEau, num: CollecteurNumCfg) -> None:
        self.cfg = cfg
        self.table = table
        self.num = num
        self.viv: list[Vanne] = [composants[f"VIV{b}"] for b in boucles]          # type: ignore[misc]
        self.viv_bp: list[Vanne] = [composants[f"VIV{b}_BP"] for b in boucles]    # type: ignore[misc]
        self.vda: list[Vanne] = [composants[f"VDA{b}"] for b in boucles]          # type: ignore[misc]
        s = cfg.soupapes
        self.soupapes: list[list[Soupape]] = [
            [Soupape(f"SOUP{b}_{n}", "VVP", tarage, s.capacite_kg_s, s.fermeture_pct)
             for n, tarage in enumerate(s.tarages_bar, start=1)]
            for b in boucles]
        lg = cfg.ligne
        self.c_ligne = lg.qm_nom_kg_s / math.sqrt(table.rho_v_kg_m3(lg.p_nom_bar) * lg.dp_nom_bar)
        nb = len(boucles)
        self.etat = EtatVapeur(p_collecteur_bar=lg.p_nom_bar - lg.dp_nom_bar,
                               h_collecteur_kj_kg=table.hg_kj_kg(lg.p_nom_bar),
                               qm_lignes_kg_s=[0.0] * nb, qm_vda_kg_s=[0.0] * nb,
                               qm_soupapes_kg_s=[0.0] * nb)

    def ouverture_ligne(self, i: int) -> float:
        """Ouverture équivalente de la ligne : VIV + by-pass."""
        return min(1.0, self.viv[i].etat.position
                   + self.cfg.ligne.fraction_bypass_viv * self.viv_bp[i].etat.position)

    # ------------------------------------------------------------------ collecteur
    def resoudre(self, dt: float, gvs: list[GenerateurVapeur], k_sortie_kg_s_bar: float,
                 p_bas_bar: float) -> None:
        """Pression du collecteur et débits des lignes (k_sortie : turbine + GCT-c, ṁ = k·P)."""
        lg = self.cfg.ligne
        coef = []   # (P_GV, C²ρ, a) par ligne
        for i, gv in enumerate(gvs):
            c = self.c_ligne * self.ouverture_ligne(i)
            rho = gv.vol.sat.rho_v_kg_m3
            sens = gv.vol.sensibilite_bar_par_kg_vapeur(lg.qm_nom_kg_s * dt)
            coef.append((gv.p_bar, c * c * rho, c * c * rho * sens * dt))

        def debits(p_h: float) -> tuple[list[float], float, float]:
            """Débits des lignes, résidu f = Σṁ − k·P, dérivée df/dP."""
            q, df = [], -k_sortie_kg_s_bar
            for p_gv, c2rho, a in coef:
                cc = c2rho * (p_gv - p_h)
                if cc <= 0.0:
                    q.append(0.0)
                    continue
                racine = math.sqrt(a * a + 4.0 * cc)
                qm = 0.5 * (racine - a)
                if qm >= lg.limiteur_kg_s:
                    q.append(lg.limiteur_kg_s)
                else:
                    q.append(qm)
                    df -= c2rho / racine
            return q, sum(q) - k_sortie_kg_s_bar * p_h, df

        lo = p_bas_bar
        hi = max([p for p, c2, _ in coef if c2 > 0.0], default=lo)
        if hi <= lo:
            p_h = lo
        else:
            _, f_lo, _ = debits(lo)
            _, f_hi, _ = debits(hi)
            if f_lo <= 0.0:
                p_h = lo
            elif f_hi >= 0.0:
                p_h = hi
            else:
                p_h = min(max(self.etat.p_collecteur_bar, lo), hi)
                for _ in range(self.num.iterations_max):
                    _, f, df = debits(p_h)
                    if abs(f) < self.num.tolerance_kg_s:
                        break
                    if f > 0.0:
                        lo = p_h
                    else:
                        hi = p_h
                    nouveau = p_h - f / df if df < 0.0 else 0.5 * (lo + hi)
                    p_h = nouveau if lo < nouveau < hi else 0.5 * (lo + hi)
        q, _, _ = debits(p_h)
        self.etat.p_collecteur_bar = p_h
        self.etat.qm_lignes_kg_s = q
        total = sum(q)
        self.etat.h_collecteur_kj_kg = (sum(qi * gv.vol.sat.hg_kj_kg for qi, gv in zip(q, gvs)) / total
                                        if total > 0.0 else self.table.hg_kj_kg(p_h))

    # ------------------------------------------------------------------ décharges
    def decharges(self, gvs: list[GenerateurVapeur]) -> list[str]:
        """Débits VDA et soupapes ; renvoie les repères des soupapes qui viennent de s'ouvrir."""
        ouvertures = []
        for i, gv in enumerate(gvs):
            self.etat.qm_vda_kg_s[i] = self.vda[i].debit_vapeur_kg_s(gv.p_bar)
            total = 0.0
            for s in self.soupapes[i]:
                if s.mettre_a_jour(gv.p_bar):
                    ouvertures.append(s.id)
                total += s.debit_kg_s(gv.p_bar)
            self.etat.qm_soupapes_kg_s[i] = total
        return ouvertures

    def qm_decharge_kg_s(self, i: int) -> float:
        return self.etat.qm_vda_kg_s[i] + self.etat.qm_soupapes_kg_s[i]

    def nb_soupapes_ouvertes(self) -> int:
        return sum(s.etat.ouverte for ligne in self.soupapes for s in ligne)

    def etats_ui(self) -> dict[str, Any]:
        return {s.id: s.etat_ui() for ligne in self.soupapes for s in ligne}
