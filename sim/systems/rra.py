"""Refroidissement à l'arrêt (RRA, §4.3) : 2 trains pompe + échangeur refroidi par le RRI.

Hydraulique : chaque train est une branche du réseau primaire (aspiration branche chaude,
ramenée au plénum → pompe → [échangeur ∥ by-pass] → branches froides, ramenées à la descente) ;
le débit est donc calculé avec celui des boucles. Verrou : aspiration ouvrable si P < 30 bar,
refermée automatiquement si P > 41 bar.
Échangeur (contre-courant, ε-NTU) : seule la fraction du débit qui passe par l'échangeur
(Kv échangeur / Kv total) est refroidie par le RRI.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from sim.components.pump import Pompe
from sim.components.valve import Vanne
from sim.config import RraCfg
from sim.units import KW_PAR_MW, S_PAR_H

ECART_CR_UNITAIRE = 1e-9          # Cr ≈ 1 : formule limite de l'efficacité


def efficacite_contre_courant(ua: float, c_chaud: float, c_froid: float) -> float:
    """Efficacité d'un échangeur à contre-courant (débits calorifiques en kW/°C)."""
    c_min, c_max = min(c_chaud, c_froid), max(c_chaud, c_froid)
    if c_min <= 0.0:
        return 0.0
    ntu, cr = ua / c_min, c_min / c_max
    if abs(1.0 - cr) < ECART_CR_UNITAIRE:
        return ntu / (1.0 + ntu)
    x = math.exp(-ntu * (1.0 - cr))
    return (1.0 - x) / (1.0 - cr * x)


@dataclass
class EtatRra:
    w_kg_s: list[float] = field(default_factory=list)      # débit de chaque train
    q_kw: list[float] = field(default_factory=list)        # chaleur extraite par chaque échangeur
    t_sortie_c: list[float] = field(default_factory=list)


class RRA:
    def __init__(self, cfg: RraCfg, composants: dict) -> None:
        self.cfg = cfg
        t = cfg.trains
        self.pompes: list[Pompe] = [composants[f"RRA_P{k}"] for k in t]
        self.aspiration: list[list[Vanne]] = [[composants[f"RRA_ASP{k}A"], composants[f"RRA_ASP{k}B"]] for k in t]
        self.echangeur: list[Vanne] = [composants[f"RRA_HX{k}"] for k in t]
        self.bypass: list[Vanne] = [composants[f"RRA_BP{k}"] for k in t]
        n = len(t)
        self.etat = EtatRra(w_kg_s=[0.0] * n, q_kw=[0.0] * n, t_sortie_c=[0.0] * n)

    def aspiration_ouverte(self, i: int) -> bool:
        return all(v.etat.position > 0.0 for v in self.aspiration[i])

    def vannes_aspiration(self) -> list[Vanne]:
        return [v for paire in self.aspiration for v in paire]

    def en_service(self) -> bool:
        return any(self.aspiration_ouverte(i) and p.etat.en_marche for i, p in enumerate(self.pompes))

    def fraction_echangeur(self, i: int) -> float:
        kv_hx = self.echangeur[i].kv()
        kv_bp = self.bypass[i].kv()
        return kv_hx / (kv_hx + kv_bp) if kv_hx + kv_bp > 0.0 else 0.0

    def calculer(self, w_kg_s: list[float], t_entree_c: float, t_rri_c: float, rri_ok: bool, cp_kj_kgk: float,
                 rho_rri_kg_m3: float) -> None:
        """Chaleur extraite par chaque train (débits donnés par le réseau primaire)."""
        e, c = self.etat, self.cfg
        c_rri = c.debit_rri_m3h * rho_rri_kg_m3 / S_PAR_H * cp_kj_kgk if rri_ok else 0.0
        for i, w in enumerate(w_kg_s):
            w = max(0.0, w)
            e.w_kg_s[i] = w
            c_chaud = self.fraction_echangeur(i) * w * cp_kj_kgk
            eff = efficacite_contre_courant(c.ua_echangeur_mw_c * KW_PAR_MW, c_chaud, c_rri)
            e.q_kw[i] = eff * min(c_chaud, c_rri) * max(0.0, t_entree_c - t_rri_c)
            e.t_sortie_c[i] = t_entree_c - e.q_kw[i] / (w * cp_kj_kgk) if w > 0.0 else t_entree_c

    def chaleur_pompes_kw(self) -> float:
        return sum(p.etat.vitesse for p in self.pompes) * self.cfg.chaleur_pompe_mw * KW_PAR_MW

    @property
    def q_total_kw(self) -> float:
        return sum(self.etat.q_kw)
