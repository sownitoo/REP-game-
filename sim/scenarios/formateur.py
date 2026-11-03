"""Pupitre du formateur (repère FORMATEUR) : injecter une panne à tout moment, hors scénario."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sim.components.base import Composant
from sim.scenarios import pannes

if TYPE_CHECKING:
    from sim.plant import Centrale

DIAMETRE_BRECHE_DEFAUT_CM = 2.0
DIAMETRE_BRECHE_VAPEUR_DEFAUT_CM = 30.0


class Formateur(Composant):
    type_ui = "formateur"

    def __init__(self, c: Centrale) -> None:
        super().__init__("FORMATEUR", "FORMATEUR")
        self.c = c

    def commandes(self) -> list[str]:
        return ["breche_primaire", "rtgv", "breche_vapeur", "porv_bloquee", "perte_rri", "grappe_coincee",
                "rupture_air", "perte_reseau", "retour_reseau", "supprimer_breches"]

    def executer(self, action: str, valeur: float | None) -> None:
        panne: dict[str, Any] = {"type": action}
        if action == "breche_primaire":
            panne["diametre_cm"] = valeur or DIAMETRE_BRECHE_DEFAUT_CM
        elif action == "rtgv":
            panne["gv"] = int(valeur or 1)
        elif action == "breche_vapeur":
            panne.update(gv=int(valeur or 1), diametre_cm=DIAMETRE_BRECHE_VAPEUR_DEFAUT_CM)
        elif action == "porv_bloquee":
            panne["cible"] = f"PZR_PORV{int(valeur or 1)}"
        pannes.appliquer(self.c, panne)

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        br = self.c.breches.etat
        d.update(breche_primaire_kg_s=br.qm_primaire_kg_s, rtgv_kg_s=br.qm_rtgv_kg_s, breche_vapeur_kg_s=br.qm_vapeur_kg_s,
                 porv_bloquee=br.porv_bloquee or "non")
        return d
