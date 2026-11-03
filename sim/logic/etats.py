"""États standards du réacteur (§5) et check-list des conditions pour passer à l'état voisin.

V2 : RP (en production), AN/GV (arrêt à chaud sur GV), AN/RRA (arrêt sur RRA), AF (arrêt à froid).
Les états « ouverts » (API, APR, RCD) sont hors périmètre du simulateur à ce stade.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sim.plant import Centrale

PUISSANCE_CRITIQUE_PCT = 0.1     # au-dessus : réacteur considéré comme critique (chaînes de puissance)

LIBELLES = {
    "RP": "RP — en production",
    "AN/GV": "AN/GV — arrêt à chaud sur GV",
    "AN/RRA": "AN/RRA — arrêt sur RRA",
    "AF": "Arrêt à froid",
}


@dataclass
class Point:
    texte: str
    ok: bool


def code_etat(c: Centrale) -> str:
    et = c.cfg.logique.etats
    shutdown = c.logique.etat.au or c.coeur.puissance_pct < PUISSANCE_CRITIQUE_PCT or c.coeur.etat.arret_insere > 0.0
    if not shutdown:
        return "RP"
    if c.rra.en_service() and c.primaire.tmoy_c <= et.t_rra_max_c:
        return "AF" if c.primaire.tmoy_c < et.t_arret_froid_c else "AN/RRA"
    return "AN/GV"


def checklist(c: Centrale, code: str) -> tuple[str, list[Point]]:
    """(état visé, conditions) pour l'état voisin « en descente » (vers l'arrêt)."""
    et, lg, m = c.cfg.logique.etats, c.logique.etat, c.mesures
    bore, bore_requis = m["primaire.bore_ppm"], m["coeur.bore_arret_froid_ppm"]
    marge_chaud = m["coeur.marge_arret_chaud_pcm"]
    vitesse = m["primaire.vitesse_refroidissement_c_h"]
    point_bore = Point(f"Bore ≥ bore d'arrêt à froid ({bore:.0f} / {bore_requis:.0f} ppm)", bore >= bore_requis)
    if code == "RP":
        return "AN/GV", [
            Point("Réacteur sous-critique (AU ou grappes insérées)", False),
            Point(f"Marge d'arrêt à chaud ≥ {et.marge_arret_pcm:g} pcm ({marge_chaud:.0f} pcm)",
                  marge_chaud >= et.marge_arret_pcm),
        ]
    if code == "AN/GV":
        tmoy, p = c.primaire.tmoy_c, c.pzr.p_bar
        return "AN/RRA", [
            point_bore,
            Point(f"P-11 présent et IS bloquée (P PZR {p:.1f} bar)", lg.p11 and lg.is_bloquee),
            Point("Accumulateurs isolés", c.accus.isoles()),
            Point(f"Vitesse de refroidissement ≤ {et.vitesse_refroidissement_max_c_h:g} °C/h ({vitesse:.0f} °C/h)",
                  vitesse <= et.vitesse_refroidissement_max_c_h),
            Point(f"P primaire ≤ {et.p_rra_max_bar:g} bar ({p:.1f} bar)", p <= et.p_rra_max_bar),
            Point(f"Tmoy ≤ {et.t_rra_max_c:g} °C ({tmoy:.1f} °C)", tmoy <= et.t_rra_max_c),
            Point("RRA en service (aspiration ouverte, une pompe en marche)", c.rra.en_service()),
        ]
    if code == "AN/RRA":
        tmoy = c.primaire.tmoy_c
        return "AF", [
            point_bore,
            Point(f"Vitesse de refroidissement ≤ {et.vitesse_refroidissement_max_c_h:g} °C/h ({vitesse:.0f} °C/h)",
                  vitesse <= et.vitesse_refroidissement_max_c_h),
            Point(f"Tmoy < {et.t_arret_froid_c:g} °C ({tmoy:.1f} °C)", tmoy < et.t_arret_froid_c),
        ]
    return "", []


def etat_ui(c: Centrale) -> dict:
    code = code_etat(c)
    vise, points = checklist(c, code)
    return {"code": code, "libelle": LIBELLES[code], "vise": vise, "libelle_vise": LIBELLES.get(vise, ""),
            "checklist": [{"texte": p.texte, "ok": p.ok} for p in points]}
