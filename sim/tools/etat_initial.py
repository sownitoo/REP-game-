"""Génère l'état initial stabilisé « RP 100 % » (config/etats/rp100.json).

Usage : python -m sim.tools.etat_initial [durée de stabilisation en s]
La centrale part du point nominal approché, tourne protections inhibées le temps
que les régulations se posent, puis l'état est sauvegardé (temps remis à zéro).
"""

from __future__ import annotations

import json
import sys

from sim.config import RACINE
from sim.core.events import PRIORITE_INFO
from sim.plant import Centrale

CHEMIN_RP100 = RACINE / "config" / "etats" / "rp100.json"


def generer(duree_s: float | None = None) -> dict:
    c = Centrale()
    c.inhiber_protections = True
    c.avancer(duree_s if duree_s is not None else c.cfg.numerique.duree_stabilisation_s)
    c.inhiber_protections = False
    c.t_s = 0.0
    c.journal.evenements.clear()
    c.alarmes.etats.clear()
    c.journal.ajouter(0.0, "info", "État initial : RP 100 % stabilisé", PRIORITE_INFO)
    return c.exporter()


def main() -> None:
    duree = float(sys.argv[1]) if len(sys.argv) > 1 else None
    etat = generer(duree)
    CHEMIN_RP100.parent.mkdir(parents=True, exist_ok=True)
    CHEMIN_RP100.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"État écrit : {CHEMIN_RP100}")


if __name__ == "__main__":
    main()
