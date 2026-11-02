"""Chargement des scénarios (YAML) et des états sauvegardés."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from sim.config import RACINE
from sim.core.events import PRIORITE_INFO
from sim.plant import Centrale

DOSSIER_ETATS = RACINE / "config" / "etats"
DOSSIER_SCENARIOS = Path(__file__).resolve().parent


@dataclass
class Scenario:
    id: str
    titre: str
    etat_initial: str
    description: str = ""
    duree_s: float | None = None
    pannes: list[dict[str, Any]] = field(default_factory=list)


def lire_etat(nom: str) -> dict[str, Any]:
    return json.loads((DOSSIER_ETATS / f"{nom}.json").read_text(encoding="utf-8"))


def centrale_depuis_etat(nom: str = "rp100") -> Centrale:
    """Nouvelle centrale placée dans l'état sauvegardé `nom`."""
    c = Centrale()
    c.importer(lire_etat(nom))
    return c


def lire_scenario(id_scenario: str) -> Scenario:
    with open(DOSSIER_SCENARIOS / f"{id_scenario}.yaml", encoding="utf-8") as f:
        return Scenario(**yaml.safe_load(f))


def lister_scenarios() -> list[Scenario]:
    return [lire_scenario(p.stem) for p in sorted(DOSSIER_SCENARIOS.glob("*.yaml"))]


def centrale_scenario(id_scenario: str) -> Centrale:
    sc = lire_scenario(id_scenario)
    c = centrale_depuis_etat(sc.etat_initial)
    c.journal.ajouter(c.t_s, "info", f"Scénario {sc.id} : {sc.titre}", PRIORITE_INFO)
    return c
