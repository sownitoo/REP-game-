"""Tutos guidés et catalogue d'explications des automatismes.

- `explications.yaml` : pour chaque automatisme (repéré par un motif sur le texte du journal) : ce qui se
  passe, pourquoi, ce que ça entraîne, les équipements à montrer, l'onglet et les mesures à suivre.
  Sert aux tutos ET au mode libre « commenté » (pause + explication sur chaque automatisme).
- `t*.yaml` : un tuto = un état de départ + des étapes. Une étape est une lecture (texte, onglet,
  équipements en surbrillance, mesures), une action à faire (commande, avec « le faire pour moi »),
  ou une observation (la simulation tourne et s'arrête sur chaque automatisme attendu).
Validation stricte : une clé inconnue est une erreur.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from sim.config import lire_yaml_ou_json
from sim.plant import Centrale
from sim.scenarios.chargement import centrale_depuis_etat, centrale_scenario

DOSSIER_TUTOS = Path(__file__).resolve().parent


def _construire(cls: type, d: dict[str, Any], ou: str) -> Any:
    noms = {f.name for f in fields(cls)}
    inconnues = set(d) - noms
    if inconnues:
        raise ValueError(f"{ou} : clé(s) inconnue(s) {sorted(inconnues)}")
    return cls(**d)


@dataclass
class Explication:
    id: str
    motif: str                      # expression régulière sur le texte du journal
    titre: str
    pourquoi: str
    effet: str
    voir: list[str] = field(default_factory=list)       # repères d'équipements (ou « bloc:clé » de la vue d'ensemble)
    onglet: str = ""
    mesures: list[list[Any]] = field(default_factory=list)   # [mesure, libellé, unité, décimales]


@dataclass
class Catalogue:
    reprise_mode_commente_s: float
    explications: list[Explication]

    def motifs(self, ids: list[str] | None = None) -> dict[str, re.Pattern[str]]:
        choix = [e for e in self.explications if ids is None or e.id in ids]
        return {e.id: re.compile(e.motif) for e in choix}

    def par_id(self) -> dict[str, Explication]:
        return {e.id: e for e in self.explications}


@dataclass
class Action:
    cible: str
    action: str
    libelle: str
    valeur: float | None = None


@dataclass
class Observation:
    attendus: list[str]             # ids du catalogue, dans l'ordre où on s'attend à les voir
    duree_s: float                  # temps simulé de l'observation
    acceleration: int = 1


@dataclass
class Etape:
    titre: str
    texte: str
    onglet: str = ""
    voir: list[str] = field(default_factory=list)
    mesures: list[list[Any]] = field(default_factory=list)
    action: Action | None = None
    observer: Observation | None = None

    @property
    def genre(self) -> str:
        return "action" if self.action else "observation" if self.observer else "lecture"


@dataclass
class Tuto:
    id: str
    titre: str
    resume: str
    niveau: str
    duree_min: int
    etat_initial: str = ""          # état sauvegardé (config/etats) …
    scenario: str = ""              # … ou scénario (avec ses pannes programmées)
    etapes: list[Etape] = field(default_factory=list)

    def vers_ui(self) -> dict[str, Any]:
        d = asdict(self)
        for e, src in zip(d["etapes"], self.etapes):
            e["genre"] = src.genre
        return d


def lire_catalogue() -> Catalogue:
    d = lire_yaml_ou_json(DOSSIER_TUTOS / "explications.yaml")
    explications = [_construire(Explication, e, f"explication {e.get('id')}") for e in d.pop("explications")]
    cat = _construire(Catalogue, {**d, "explications": explications}, "explications.yaml")
    ids = [e.id for e in explications]
    if len(ids) != len(set(ids)):
        raise ValueError("explications.yaml : identifiants en double")
    return cat


def lire_tuto(chemin: Path) -> Tuto:
    d = lire_yaml_ou_json(chemin)
    etapes = []
    for k, e in enumerate(d.pop("etapes")):
        ou = f"{chemin.name}, étape {k + 1}"
        if e.get("action") is not None:
            e["action"] = _construire(Action, e["action"], ou)
        if e.get("observer") is not None:
            e["observer"] = _construire(Observation, e["observer"], ou)
        etapes.append(_construire(Etape, e, ou))
    t = _construire(Tuto, {**d, "etapes": etapes}, chemin.name)
    if bool(t.etat_initial) == bool(t.scenario):
        raise ValueError(f"{chemin.name} : donner etat_initial OU scenario")
    return t


def lister_tutos() -> list[Tuto]:
    fichiers = sorted(DOSSIER_TUTOS.glob("t*.yaml")) or sorted(DOSSIER_TUTOS.glob("t*.json"))
    return [lire_tuto(p) for p in fichiers]


def centrale_tuto(t: Tuto) -> Centrale:
    return centrale_scenario(t.scenario) if t.scenario else centrale_depuis_etat(t.etat_initial)
