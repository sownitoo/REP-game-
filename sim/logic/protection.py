"""Protection réacteur (RPR) : arrêt automatique (AU), P-4, mémorisation et réarmement.

Ordre d'évaluation à chaque pas : permissifs → causes d'AU → automatismes.
Causes d'AU en V0 : manuel, niveau GV très bas (2/3 sur 1 GV),
déclenchement turbine (4/4 vannes d'arrêt fermées) au-dessus de P-7.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

from sim.components.base import Composant
from sim.core.events import PRIORITE_HAUTE
from sim.logic.automatismes import appliquer_automatismes
from sim.logic.permissives import calculer_permissifs

if TYPE_CHECKING:
    from sim.plant import Centrale


@dataclass
class EtatLogique:
    au: bool = False
    au_causes: list[str] = field(default_factory=list)   # causes mémorisées à l'apparition de l'AU
    au_t_s: float = 0.0
    au_manuel: bool = False                               # demande manuelle en attente
    p4: bool = False
    p7: bool = True
    p14: bool = False
    p14_gv: list[bool] = field(default_factory=list)
    niveau_tres_bas_gv: list[bool] = field(default_factory=list)
    c9: bool = False
    causes_au: list[str] = field(default_factory=list)          # causes présentes
    causes_turbine: list[str] = field(default_factory=list)     # causes présentes
    isolement_are_au: bool = False
    isolement_are_complet: bool = False                   # mémorisé (P-14), réarmement opérateur
    tempo_aspiration_app_s: list[float] = field(default_factory=list)
    recirc_cex: bool = True
    app_declenchee: bool = False
    cex_declenchee: bool = False


class Logique(Composant):
    """Protection et automatismes (repère RPR)."""

    type_ui = "logique"

    def __init__(self, c: Centrale) -> None:
        super().__init__("RPR", "RPR")
        self.c = c
        self.etat = EtatLogique(p14_gv=[False] * len(c.gvs), niveau_tres_bas_gv=[False] * len(c.gvs),
                                tempo_aspiration_app_s=[0.0] * len(c.apps))

    # ------------------------------------------------------------------ AU
    def causes_au_presentes(self) -> list[str]:
        e = self.etat
        causes = [f"niveau très bas GV{gv.b}" for gv, bas in zip(self.c.gvs, e.niveau_tres_bas_gv) if bas]
        if self.c.turbine.arret_ferme() and not e.p7:
            causes.append("déclenchement turbine au-dessus de P-7")
        return causes

    def evaluer(self, dt: float) -> None:
        c, e = self.c, self.etat
        calculer_permissifs(c, e)
        if c.inhiber_protections:          # stabilisation de l'état initial uniquement
            e.causes_au, e.p14, e.p14_gv = [], False, [False] * len(c.gvs)
            appliquer_automatismes(c, e, dt)
            return
        e.causes_au = self.causes_au_presentes()
        if e.au_manuel:
            e.causes_au = ["manuel"] + e.causes_au
            e.au_manuel = False
        if e.causes_au and not e.au:
            e.au = True
            e.au_causes = list(e.causes_au)
            e.au_t_s = c.t_s
            c.source.chute_grappes()
            c.journal.ajouter(c.t_s, "automatisme", f"AU : {', '.join(e.au_causes)}", PRIORITE_HAUTE)
        e.p4 = e.au
        appliquer_automatismes(c, e, dt)

    # ------------------------------------------------------------------ commandes
    def commandes(self) -> list[str]:
        return ["declencher_au", "rearmer_au", "rearmer_isolement_are"]

    def executer(self, action: str, valeur: float | None) -> None:
        e = self.etat
        if action == "declencher_au":
            e.au_manuel = True
        elif action == "rearmer_au":
            e.au = False
            e.au_causes = []
            e.p4 = False
            self.c.source.rearmer()
        elif action == "rearmer_isolement_are":
            e.isolement_are_complet = False

    def exporter_etat(self) -> dict[str, Any]:
        return asdict(self.etat)

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        d.update(asdict(self.etat))
        return d
