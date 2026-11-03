"""Pannes programmées par les scénarios : liste de {t_s, type, cible?, reparation_s?}.

Types : perte_reseau, retour_reseau, diesel_refus (cible = DIESEL_A / DIESEL_B, réparable après
reparation_s si donné), rupture_air (fuite sur le collecteur d'air), declenchement (cible = pompe).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sim.core.events import PRIORITE_HAUTE

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
        texte = f"{d.id} indisponible" + (f" (réparé dans {panne['reparation_s'] / 60:.0f} min)"
                                          if "reparation_s" in panne else "")
    elif genre == "rupture_air":
        c.air.etat.fuite = c.cfg.air_comprime.fuite_rupture
        texte = "rupture sur le collecteur d'air comprimé"
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
