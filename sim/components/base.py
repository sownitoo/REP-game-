"""Base commune des composants : repère, système, alimentations, état sérialisable."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Condition:
    """Condition de manœuvre : texte lisible + résultat."""

    texte: str
    ok: bool


@dataclass
class Sources:
    """Disponibilité des alimentations (électricité, air) vue par un composant.

    En V0 l'électricité et l'air sont des « stubs » : tout est disponible.
    """

    electricite_ok: bool = True
    air_ok: bool = True


class Composant:
    """Composant de base : repère `id`, `systeme`, alimentation électrique `alim`, air `air`."""

    type_ui: str = "composant"

    def __init__(self, id: str, systeme: str, alim: str | None = None, air: str | None = None) -> None:
        self.id = id
        self.systeme = systeme
        self.alim = alim
        self.air = air
        self.etat: Any = None

    # --- sérialisation (sauvegarde / chargement) ---
    def exporter_etat(self) -> dict[str, Any]:
        return asdict(self.etat) if self.etat is not None else {}

    def importer_etat(self, donnees: dict[str, Any]) -> None:
        if self.etat is not None:
            self.etat = type(self.etat)(**donnees)

    # --- interface joueur ---
    def commandes(self) -> list[str]:
        """Actions possibles sur ce composant."""
        return []

    def etat_ui(self) -> dict[str, Any]:
        """Résumé de l'état pour l'interface."""
        return {"type": self.type_ui, "systeme": self.systeme, "alim": self.alim, "air": self.air}
