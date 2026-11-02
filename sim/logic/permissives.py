"""Permissifs P-x et verrous C-x (V0 : P-4, P-7, P-14, C-9) + seuils GV votés."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sim.logic.voting import vote

if TYPE_CHECKING:
    from sim.logic.protection import EtatLogique
    from sim.plant import Centrale


def calculer_permissifs(c: Centrale, e: EtatLogique) -> None:
    """Met à jour les permissifs à partir des mesures du pas précédent."""
    lg = c.cfg.logique
    seuils = c.cfg.generateurs_vapeur.seuils
    # P-7 : puissance < 10 % ET charge turbine < 10 % (P-13)
    e.p7 = c.source.puissance_pct < lg.p7.puissance_max_pct and c.turbine.charge_pct < lg.p7.charge_turbine_max_pct
    # P-14 et niveau très bas : 2/3 sur un GV
    e.p14_gv = [vote(seuils.vote, gv.capteur.depasse(seuils.tres_haut_pct, au_dessus=True)) for gv in c.gvs]
    e.p14 = any(e.p14_gv)
    e.niveau_tres_bas_gv = [vote(seuils.vote, gv.capteur.depasse(seuils.tres_bas_pct, au_dessus=False))
                            for gv in c.gvs]
    # C-9 : condenseur disponible (avec hystérésis sur la pression)
    p_cond = c.condenseur.etat.p_bar
    crf_ok = c.condenseur.nb_crf_en_marche() >= lg.c9.crf_mini
    if not crf_ok or p_cond > lg.c9.p_cond_perte_bar:
        e.c9 = False
    elif p_cond < lg.c9.p_cond_max_bar:
        e.c9 = True
    # P-4 : disjoncteurs d'AU ouverts
    e.p4 = e.au
