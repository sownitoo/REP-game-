"""Pannes programmées par les scénarios : liste de {t_s, type, cible?, reparation_s?}.

Types : perte_reseau, retour_reseau, diesel_refus (cible = DIESEL_A / DIESEL_B, réparable après
reparation_s si donné), rupture_air (fuite sur le collecteur d'air), declenchement (cible = pompe),
breche_primaire (diametre_cm, boucle), rtgv (gv, tubes), breche_vapeur (gv, diametre_cm),
porv_bloquee (cible), perte_rri (reparation_s), grappe_coincee, supprimer_breches.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sim.core.events import PRIORITE_HAUTE
from sim.systems.breches import surface_m2
from sim.systems.rri import PANNE_PERMANENTE_S
from sim.units import S_PAR_MIN

if TYPE_CHECKING:
    from sim.plant import Centrale


def appliquer(c: Centrale, panne: dict[str, Any]) -> None:
    genre = panne["type"]
    if genre == "perte_reseau":
        c.elec.etat.reseau_ok = False
        texte = "perte du réseau 400 kV"
    elif genre == "retour_reseau":
        c.elec.etat.reseau_ok = True
        texte = "retour du réseau 400 kV"
    elif genre == "diesel_refus":
        d = c.elec.diesels[panne["cible"]]
        d.etat.refus = True
        d.etat.reparation_t_s = c.t_s + panne["reparation_s"] if "reparation_s" in panne else None
        if d.en_service:
            d.arreter("panne")
        texte = f"{d.id} indisponible" + (f" (réparé dans {panne['reparation_s'] / S_PAR_MIN:.0f} min)"
                                          if "reparation_s" in panne else "")
    elif genre == "rupture_air":
        c.air.etat.fuite = c.cfg.air_comprime.fuite_rupture
        texte = "rupture sur le collecteur d'air comprimé"
    elif genre == "breche_primaire":
        br = c.breches.etat
        br.primaire_m2 = surface_m2(panne["diametre_cm"])
        br.primaire_boucle = int(panne.get("boucle", 1))
        texte = f"brèche primaire ∅ {panne['diametre_cm']:g} cm sur la branche froide B{br.primaire_boucle}"
    elif genre == "rtgv":
        br = c.breches.etat
        br.rtgv_gv = int(panne["gv"])
        br.rtgv_m2 = 2 * surface_m2(c.cfg.breches.diametre_tube_gv_cm) * panne.get("tubes", 1)
        texte = f"rupture de tube du GV{br.rtgv_gv}"
    elif genre == "breche_vapeur":
        br = c.breches.etat
        br.vapeur_gv = int(panne["gv"])
        br.vapeur_m2 = surface_m2(panne["diametre_cm"])
        texte = f"brèche vapeur ∅ {panne['diametre_cm']:g} cm sur la ligne du GV{br.vapeur_gv} (dans l'enceinte)"
    elif genre == "porv_bloquee":
        c.breches.etat.porv_bloquee = panne.get("cible", "PZR_PORV1")
        texte = f"{c.breches.etat.porv_bloquee} bloquée ouverte"
    elif genre == "perte_rri":
        for p in c.rri.pompes:
            p.declencher("perte du RRI (fuite)")
        c.rri.etat.panne_jusqua_s = c.t_s + panne.get("reparation_s", PANNE_PERMANENTE_S)
        texte = "perte du RRI (fuite du circuit)"
    elif genre == "grappe_coincee":
        c.coeur.etat.rho_coincee_pcm = c.cfg.logique.etats.grappe_coincee_pcm
        texte = "la grappe la plus efficace restera coincée hors du cœur"
    elif genre == "supprimer_breches":
        br = c.breches.etat
        br.primaire_m2 = br.rtgv_m2 = br.vapeur_m2 = 0.0
        br.porv_bloquee = ""
        texte = "brèches supprimées (formateur)"
    elif genre == "declenchement":
        c.pompes[panne["cible"]].declencher("panne")
        texte = f"déclenchement de {panne['cible']}"
    else:
        raise ValueError(f"Panne inconnue : {genre}")
    c.journal.ajouter(c.t_s, "panne", f"PANNE : {texte}", PRIORITE_HAUTE)


def avancer(c: Centrale) -> None:
    for p in c.pannes:
        if not p.get("faite") and c.t_s >= p["t_s"]:
            p["faite"] = True
            appliquer(c, p)
