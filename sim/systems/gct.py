"""Contournement condenseur (GCT-c, §4.6) : 4 groupes de vannes, modes « Tmoy » et « pression ».

- Mode pression : d = (P_collecteur − consigne) / bande.
- Mode Tmoy : armé par C-7 (baisse de charge > 10 % en échelon, ou 5 %/min) ou C-8
  (turbine déclenchée). Régulateur « perte de charge » : d = (Tmoy − Tref − bande morte) / bande ;
  régulateur « déclenchement turbine » : d = (Tmoy − T à vide) / bande.
Les groupes s'ouvrent l'un après l'autre. C-9 et P-12 sont appliqués par la logique (ordres).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from sim.components.base import Composant
from sim.components.valve import Vanne
from sim.config import GctCfg
from sim.units import POURCENT

MODE_TMOY = "tmoy"
MODE_PRESSION = "pression"


@dataclass
class EtatContournement:
    mode: str
    consigne_bar: float
    charge_retard_pct: float     # charge turbine filtrée (détection C-7)
    c7: bool                     # armé par une baisse de charge (mémorisé)
    c8: bool                     # armé par le déclenchement turbine
    demande: float


class Contournement(Composant):
    """Régulation du contournement (repère REG_GCTC) et ses groupes de vannes GCTC_Gx."""

    type_ui = "regulation"

    def __init__(self, cfg: GctCfg, composants: dict[str, Composant], charge_initiale_pct: float) -> None:
        super().__init__("REG_GCTC", "GCT")
        self.cfg = cfg
        self.groupes: list[Vanne] = [composants[f"GCTC_G{i}"]  # type: ignore[misc]
                                     for i in range(1, cfg.groupes + 1)]
        self.etat = EtatContournement(mode=cfg.mode_initial, consigne_bar=cfg.regulation.consigne_bar,
                                      charge_retard_pct=charge_initiale_pct, c7=False, c8=False, demande=0.0)

    # ------------------------------------------------------------------ commandes
    def commandes(self) -> list[str]:
        return ["mode_tmoy", "mode_pression", "consigne", "rearmer_c7"]

    def executer(self, action: str, valeur: float | None) -> None:
        e = self.etat
        if action == "mode_tmoy":
            e.mode = MODE_TMOY
        elif action == "mode_pression":
            e.mode = MODE_PRESSION
        elif action == "consigne" and valeur is not None:
            e.consigne_bar = valeur
        elif action == "rearmer_c7":
            e.c7 = False

    # ------------------------------------------------------------------ armements
    def mettre_a_jour_armements(self, dt: float, charge_pct: float, turbine_declenchee: bool) -> None:
        e, c7 = self.etat, self.cfg.c7
        e.charge_retard_pct += (charge_pct - e.charge_retard_pct) * min(1.0, dt / c7.constante_s)
        if e.charge_retard_pct - charge_pct > c7.echelon_pct:
            e.c7 = True
        e.c8 = turbine_declenchee

    # ------------------------------------------------------------------ régulation
    def calculer(self, p_collecteur_bar: float, tmoy_c: float, tref_c: float) -> None:
        e, cfg = self.etat, self.cfg
        if e.mode == MODE_PRESSION:
            d = (p_collecteur_bar - e.consigne_bar) / cfg.regulation.bande_bar
        elif e.c8:
            d = (tmoy_c - cfg.tmoy.t_vide_c) / cfg.tmoy.bande_declenchement_c
        elif e.c7:
            d = (tmoy_c - tref_c - cfg.tmoy.bande_morte_c) / cfg.tmoy.bande_perte_charge_c
        else:
            d = 0.0
        e.demande = min(max(d, 0.0), 1.0)
        n = len(self.groupes)
        for i, v in enumerate(self.groupes):
            v.etat.demande_auto = min(max(n * e.demande - i, 0.0), 1.0)

    def k_kg_s_bar(self) -> float:
        """ṁ = k · P_collecteur (débit critique)."""
        return sum(v.debit_vapeur_kg_s(1.0) for v in self.groupes)

    def ouverture_pct(self) -> float:
        return POURCENT * sum(v.etat.position for v in self.groupes) / len(self.groupes)

    def exporter_etat(self) -> dict[str, Any]:
        return asdict(self.etat)

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        d.update(asdict(self.etat))
        d["ouverture_pct"] = self.ouverture_pct()
        return d
