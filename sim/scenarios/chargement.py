"""Chargement des scénarios (YAML) et des états sauvegardés."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sim.config import RACINE, lire_yaml_ou_json
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
    objectifs: list[str] = field(default_factory=list)     # fiche de conduite affichée au joueur


def lire_etat(nom: str) -> dict[str, Any]:
    return json.loads((DOSSIER_ETATS / f"{nom}.json").read_text(encoding="utf-8"))


def centrale_depuis_etat(nom: str = "rp100") -> Centrale:
    """Nouvelle centrale placée dans l'état sauvegardé `nom`."""
    c = Centrale()
    c.importer(lire_etat(nom))
    return c


def lire_scenario(id_scenario: str) -> Scenario:
    return Scenario(**lire_yaml_ou_json(DOSSIER_SCENARIOS / f"{id_scenario}.yaml"))


def lister_scenarios() -> list[Scenario]:
    fichiers = sorted(DOSSIER_SCENARIOS.glob("*.yaml")) or sorted(DOSSIER_SCENARIOS.glob("*.json"))
    return [lire_scenario(p.stem) for p in fichiers]


def centrale_scenario(id_scenario: str) -> Centrale:
    sc = lire_scenario(id_scenario)
    c = centrale_depuis_etat(sc.etat_initial)
    c.pannes = [{**p, "t_s": c.t_s + p["t_s"]} for p in sc.pannes]
    c.journal.ajouter(c.t_s, "info", f"Scénario {sc.id} : {sc.titre}", PRIORITE_INFO)
    return c
