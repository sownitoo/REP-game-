"""Journal d'événements horodaté et gestion des alarmes (apparition, disparition, acquittement)."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from typing import Any

from sim.config import AlarmeCfg
from sim.units import POURCENT


# priorités des événements / alarmes
PRIORITE_HAUTE = 1
PRIORITE_MOYENNE = 2
PRIORITE_INFO = 3


@dataclass
class Evenement:
    t_s: float
    categorie: str          # action | automatisme | alarme | info
    texte: str
    priorite: int


class Journal:
    """Journal circulaire des événements (alarmes, automatismes, actions joueur)."""

    def __init__(self, taille_max: int) -> None:
        self.evenements: deque[Evenement] = deque(maxlen=taille_max)

    def ajouter(self, t_s: float, categorie: str, texte: str, priorite: int) -> None:
        self.evenements.append(Evenement(t_s, categorie, texte, priorite))

    def derniers(self, n: int) -> list[dict[str, Any]]:
        return [asdict(e) for e in list(self.evenements)[-n:]]

    def exporter(self) -> list[dict[str, Any]]:
        return [asdict(e) for e in self.evenements]

    def importer(self, donnees: list[dict[str, Any]]) -> None:
        self.evenements.clear()
        self.evenements.extend(Evenement(**d) for d in donnees)


@dataclass
class EtatAlarme:
    active: bool
    acquittee: bool
    t_apparition_s: float


@dataclass
class Temporisation:
    depuis_s: float               # instant où la condition a changé d'état (confirmation en cours)
    condition: bool


class GestionAlarmes:
    """Alarmes à seuil définies dans plant.yaml (haut et/ou bas, avec hystérésis)."""

    def __init__(self, definitions: list[AlarmeCfg], hysteresis_pct: float, temporisation_s: float) -> None:
        self.definitions = definitions
        self.hysteresis = hysteresis_pct / POURCENT
        self.temporisation_s = temporisation_s
        self.etats: dict[str, EtatAlarme] = {}
        self._tempo: dict[str, Temporisation] = {}

    def _depasse(self, d: AlarmeCfg, valeur: float, active: bool) -> bool:
        """Seuil franchi ? Une alarme active ne disparaît qu'après un retour au-delà de l'hystérésis."""
        if d.haut is not None:
            seuil = d.haut - abs(d.haut) * self.hysteresis if active else d.haut
            if valeur > seuil:
                return True
        if d.bas is not None:
            seuil = d.bas + abs(d.bas) * self.hysteresis if active else d.bas
            if valeur < seuil:
                return True
        return False

    def evaluer(self, t_s: float, mesures: dict[str, float], journal: Journal) -> None:
        for d in self.definitions:
            valeur = mesures.get(d.mesure)
            if valeur is None:
                continue
            etat = self.etats.get(d.id)
            active = etat is not None and etat.active
            condition = self._depasse(d, valeur, active)
            # temporisation : le changement doit durer pour être pris en compte (anti-papillotement)
            tempo = self._tempo.get(d.id)
            if condition == active:
                self._tempo.pop(d.id, None)
                continue
            if tempo is None or tempo.condition != condition:
                tempo = self._tempo[d.id] = Temporisation(depuis_s=t_s, condition=condition)
            delai = self.temporisation_s if d.temporisation_s is None else d.temporisation_s
            if t_s - tempo.depuis_s < delai:
                continue
            self._tempo.pop(d.id, None)
            if condition:
                if not active:
                    self.etats[d.id] = EtatAlarme(active=True, acquittee=False, t_apparition_s=t_s)
                    journal.ajouter(t_s, "alarme", f"↑ {d.libelle}", d.priorite)
            elif active and etat is not None:
                etat.active = False
                journal.ajouter(t_s, "alarme", f"↓ {d.libelle}", d.priorite)
                if etat.acquittee:
                    del self.etats[d.id]

    def acquitter(self, id_alarme: str | None = None) -> None:
        """Acquitte une alarme (ou toutes) ; une alarme disparue et acquittée sort de la liste."""
        for k in list(self.etats):
            if id_alarme is None or k == id_alarme:
                self.etats[k].acquittee = True
                if not self.etats[k].active:
                    del self.etats[k]

    def actives(self) -> list[str]:
        return [k for k, e in self.etats.items() if e.active]

    def liste(self) -> list[dict[str, Any]]:
        """Alarmes à afficher (actives ou non acquittées), par priorité puis ordre d'apparition."""
        par_id = {d.id: d for d in self.definitions}
        lignes = [{"id": k, "libelle": par_id[k].libelle, "priorite": par_id[k].priorite, **asdict(e)}
                  for k, e in self.etats.items()]
        return sorted(lignes, key=lambda x: (x["priorite"], -x["t_apparition_s"]))

    def exporter(self) -> dict[str, Any]:
        return {k: asdict(e) for k, e in self.etats.items()}

    def importer(self, donnees: dict[str, Any]) -> None:
        self.etats = {k: EtatAlarme(**v) for k, v in donnees.items()}
        self._tempo = {}
