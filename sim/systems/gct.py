"""Contournement condenseur (GCT-c) : 4 groupes de vannes, mode pression (V0).

Demande d = (P_collecteur − consigne) / bande ∈ [0, 1], groupes ouverts l'un après l'autre.
Le mode « Tmoy » (C-7 / C-8) et P-12 arrivent en V1.
"""

from __future__ import annotations

from typing import Any

from sim.components.base import Composant
from sim.components.valve import Vanne
from sim.config import GctCfg
from sim.units import POURCENT


class Contournement(Composant):
    """Régulation du contournement (repère REG_GCTC) et ses groupes de vannes GCTC_Gx."""

    type_ui = "regulation"

    def __init__(self, cfg: GctCfg, composants: dict[str, Composant]) -> None:
        super().__init__("REG_GCTC", "GCT")
        self.cfg = cfg
        self.groupes: list[Vanne] = [composants[f"GCTC_G{i}"]  # type: ignore[misc]
                                     for i in range(1, cfg.groupes + 1)]
        self.consigne_bar = cfg.regulation.consigne_bar

    def commandes(self) -> list[str]:
        return ["consigne"]

    def executer(self, action: str, valeur: float | None) -> None:
        if action == "consigne" and valeur is not None:
            self.consigne_bar = valeur

    def calculer(self, p_collecteur_bar: float) -> None:
        d = (p_collecteur_bar - self.consigne_bar) / self.cfg.regulation.bande_bar
        d = min(max(d, 0.0), 1.0)
        n = len(self.groupes)
        for i, v in enumerate(self.groupes):
            v.etat.demande_auto = min(max(n * d - i, 0.0), 1.0)

    def k_kg_s_bar(self) -> float:
        """ṁ = k · P_collecteur (débit critique)."""
        return sum(v.debit_vapeur_kg_s(1.0) for v in self.groupes)

    def ouverture_pct(self) -> float:
        return POURCENT * sum(v.etat.position for v in self.groupes) / len(self.groupes)

    def exporter_etat(self) -> dict[str, Any]:
        return {"consigne_bar": self.consigne_bar}

    def importer_etat(self, donnees: dict[str, Any]) -> None:
        self.consigne_bar = donnees["consigne_bar"]

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        d.update(consigne_bar=self.consigne_bar, ouverture_pct=self.ouverture_pct())
        return d
