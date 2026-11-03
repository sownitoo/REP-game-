"""Permissifs P-x et verrous de conduite C-x (§4.14), calculés à partir des mesures.

V1 : P-4, P-7, P-8, P-9, P-10, P-12, P-13, P-14, C-2, C-3, C-4, C-5, C-7, C-8, C-9, C-11.
(P-6, P-11, C-1 : avec l'instrumentation de démarrage et l'IS, versions suivantes.)
"""

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
    votes = lg.au.votes
    flux = c.voies_flux_pct()
    tmoy_boucles = [c.primaire.tmoy_boucle_c(i) for i in range(len(c.boucles))]
    # puissance
    e.p10 = vote(votes.flux, [x > lg.p10_puissance_pct for x in flux])
    e.p8 = not vote(votes.flux, [x > lg.p8_puissance_pct for x in flux])
    e.p9 = not vote(votes.flux, [x > lg.p9_puissance_pct for x in flux])
    e.p13 = c.turbine.charge_pct < lg.p7.charge_turbine_max_pct
    e.p7 = not e.p10 and e.p13
    e.p12 = vote(votes.dt, [t < lg.p12_tmoy_c for t in tmoy_boucles])
    # GV
    e.p14_gv = [vote(seuils.vote, gv.capteur.depasse(seuils.tres_haut_pct, au_dessus=True)) for gv in c.gvs]
    e.p14 = any(e.p14_gv)
    e.niveau_tres_bas_gv = [vote(seuils.vote, gv.capteur.depasse(seuils.tres_bas_pct, au_dessus=False))
                            for gv in c.gvs]
    # condenseur (C-9, avec hystérésis sur la pression)
    p_cond = c.condenseur.etat.p_bar
    crf_ok = c.condenseur.nb_crf_en_marche() >= lg.c9.crf_mini
    if not crf_ok or p_cond > lg.c9.p_cond_perte_bar:
        e.c9 = False
    elif p_cond < lg.c9.p_cond_max_bar:
        e.c9 = True
    # verrous de grappes
    e.c2 = vote(votes.flux, [x > lg.c2_puissance_pct for x in flux])
    e.c5 = c.turbine.charge_pct < lg.c5_charge_pct
    e.c11 = c.coeur.etat.z_pas > lg.c11_pas
    e.c7 = c.gct.etat.c7
    e.c8 = c.gct.etat.c8
    # P-4 : disjoncteurs d'AU ouverts
    e.p4 = e.au
    # le blocage de l'AU flux seuil bas est levé dès que P-10 disparaît (règle générale §4.14)
    if not e.p10:
        e.flux_bas_bloque = False
