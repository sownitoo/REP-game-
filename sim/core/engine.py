"""Horloge de simulation : temps réel accéléré (×1, ×10, ×60, ×600) avec budget de calcul.

À chaque tick réel, on calcule autant de pas que l'accélération le demande, dans la
limite du budget ; l'accélération réellement tenue est mesurée et affichée.

Points d'arrêt (mode tuto) : une liste d'expressions régulières sur le texte du journal. Dès qu'un
automatisme correspondant apparaît, la simulation se met en pause et l'arrêt est publié (avec son
explication côté interface) ; « continuer » passe au suivant (plusieurs automatismes peuvent arriver
dans le même pas) puis relance. Une observation peut aussi s'arrêter d'elle-même au bout d'une durée.
"""

from __future__ import annotations

import re
import time
from typing import Any

from sim.config import SimulationCfg
from sim.core.events import Evenement
from sim.plant import Centrale
from sim.units import POURCENT

CATEGORIES_ARRET = ("automatisme", "panne", "alarme")   # ce qui peut déclencher un arrêt (pas les actions du joueur)
ARRET_FIN = "fin"                              # identifiant de l'arrêt « durée d'observation écoulée »


def correspondances(evenements: list[Evenement], points: dict[str, re.Pattern[str]]) -> list[dict[str, Any]]:
    """Arrêts déclenchés par ces événements : un seul par point, dans l'ordre d'apparition."""
    arrets: list[dict[str, Any]] = []
    vus: set[str] = set()
    for e in evenements:
        if e.categorie not in CATEGORIES_ARRET:
            continue
        for ident, motif in points.items():
            if ident not in vus and motif.search(e.texte):
                vus.add(ident)
                arrets.append({"id": ident, "texte": e.texte, "t_s": e.t_s})
                break
    return arrets


class Simulateur:
    """Fait avancer une centrale en temps réel accéléré."""

    def __init__(self, centrale: Centrale, cfg: SimulationCfg) -> None:
        self.centrale = centrale
        self.cfg = cfg
        self.acceleration = cfg.accelerations[0]
        self.pause = False
        self.acceleration_reelle = 0.0
        self.scenario = ""
        self.points: dict[str, re.Pattern[str]] = {}    # points d'arrêt actifs (id → motif)
        self.permanents = False                         # mode commenté : un point reste armé après usage
        self.reprise_s = 0.0                            # … mais ne se redéclenche qu'après ce délai simulé
        self._dernier_arret_s: dict[str, float] = {}
        self.arret: dict[str, Any] | None = None        # arrêt affiché (en pause)
        self.file: list[dict[str, Any]] = []            # arrêts en attente (même pas de calcul)
        self.fin_observation_s: float | None = None
        self._vu = centrale.journal.total

    def remplacer(self, centrale: Centrale, scenario: str) -> None:
        self.centrale = centrale
        self.scenario = scenario
        self.arreter_observation()

    # ------------------------------------------------------------------ points d'arrêt
    def observer(self, points: dict[str, re.Pattern[str]], duree_s: float | None, permanents: bool = False,
                 reprise_s: float = 0.0) -> None:
        """Arme des points d'arrêt (et éventuellement une fin d'observation) puis relance la simulation."""
        self.points = dict(points)
        self.permanents, self.reprise_s = permanents, reprise_s
        self.arret, self.file = None, []
        self._vu = self.centrale.journal.total
        self.fin_observation_s = self.centrale.t_s + duree_s if duree_s else None
        self.pause = False

    def arreter_observation(self) -> None:
        self.points, self.permanents, self.arret, self.file, self.fin_observation_s = {}, False, None, [], None
        self._vu = self.centrale.journal.total

    def continuer(self) -> None:
        """Passe à l'arrêt suivant s'il y en a un en attente, sinon relance la simulation."""
        if self.file:
            self.arret = self.file.pop(0)
            return
        self.arret = None
        self.pause = False

    def _verifier_arrets(self) -> bool:
        c = self.centrale
        nouveaux = c.journal.depuis(self._vu)
        self._vu = c.journal.total
        actifs = {k: m for k, m in self.points.items()
                  if c.t_s - self._dernier_arret_s.get(k, -float("inf")) >= self.reprise_s}
        arrets = correspondances(nouveaux, actifs) if actifs else []
        for a in arrets:
            self._dernier_arret_s[a["id"]] = c.t_s
            if not self.permanents:
                self.points.pop(a["id"], None)
        if self.fin_observation_s is not None and c.t_s >= self.fin_observation_s - c.dt_s / 2:
            arrets.append({"id": ARRET_FIN, "texte": "", "t_s": c.t_s})
            self.fin_observation_s = None
            self.points = {} if not self.permanents else self.points
        if not arrets:
            return False
        self.file.extend(arrets)
        self.arret = self.file.pop(0)
        self.pause = True
        return True

    # ------------------------------------------------------------------ horloge
    def tick(self, duree_reelle_s: float) -> int:
        """Avance la simulation pour `duree_reelle_s` de temps réel ; renvoie le nombre de pas."""
        if self.pause:
            self.acceleration_reelle = 0.0
            return 0
        c = self.centrale
        n_voulu = round(duree_reelle_s * self.acceleration / c.dt_s)
        budget_s = duree_reelle_s * self.cfg.budget_calcul_pct / POURCENT
        debut = time.perf_counter()
        n = 0
        surveiller = bool(self.points) or self.fin_observation_s is not None
        while n < n_voulu and time.perf_counter() - debut < budget_s:
            c.pas()
            n += 1
            if surveiller and self._verifier_arrets():
                break
        self.acceleration_reelle = n * c.dt_s / duree_reelle_s
        return n
