"""Pont Pyodide (mode navigateur) : la simulation tourne dans un Web Worker, sans serveur.

Le worker JavaScript (web/worker.js) appelle ces fonctions ; tout passe en texte JSON.
C'est ce mode qui permet un hébergement purement statique (Vercel).
"""

from __future__ import annotations

import json

from sim.core.engine import Simulateur
from sim.interface import creer_simulateur, etat_ui, message_init, traiter_message

_sim: Simulateur | None = None


def _simulateur() -> Simulateur:
    global _sim
    if _sim is None:
        _sim = creer_simulateur()
    return _sim


def init() -> str:
    """Crée la centrale (scénario par défaut) et renvoie le message d'initialisation."""
    s = _simulateur()
    return json.dumps(message_init(s.centrale, s), ensure_ascii=False)


def tick(duree_reelle_s: float) -> None:
    """Avance la simulation pour `duree_reelle_s` de temps réel (accélération et budget compris)."""
    _simulateur().tick(duree_reelle_s)


def etat() -> str:
    s = _simulateur()
    return json.dumps(etat_ui(s.centrale, s), ensure_ascii=False)


def message(texte: str) -> str:
    """Traite un message de l'interface ; renvoie la réponse JSON (chaîne vide si aucune)."""
    reponse = traiter_message(_simulateur(), json.loads(texte))
    return json.dumps(reponse, ensure_ascii=False) if reponse is not None else ""


def periodes() -> str:
    """Périodes d'horloge (tick et diffusion) lues dans plant.yaml."""
    cfg = _simulateur().cfg
    return json.dumps({"tick_s": cfg.tick_reel_s, "diffusion_s": cfg.diffusion_periode_s})
