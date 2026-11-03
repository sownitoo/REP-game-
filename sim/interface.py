"""Protocole entre le simulateur et l'interface web, commun aux deux modes :
- mode serveur : FastAPI + WebSocket (sim/server.py) ;
- mode navigateur : Pyodide dans un Web Worker (sim/navigateur.py), pour un hébergement statique (Vercel).

Messages reçus (dict JSON) : commande, conditions, acceleration, pause, acquitter,
historique, exporter, importer, scenario ; mode tuto : tuto (charger), observer, continuer, commente.
Messages envoyés : init, etat, reponse, conditions, historique, export, import, tuto, erreur.
"""

from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache
from typing import Any

from sim.core.engine import Simulateur
from sim.tutos.chargement import Catalogue, Tuto, centrale_tuto, lire_catalogue, lister_tutos
from sim.logic import etats
from sim.plant import Centrale
from sim.scenarios.chargement import centrale_scenario, lister_scenarios

SCENARIO_DEFAUT = "s0_bac_a_sable_100"
NB_EVENEMENTS_DIFFUSES = 60


@lru_cache(maxsize=1)
def catalogue() -> Catalogue:
    return lire_catalogue()


@lru_cache(maxsize=1)
def tutos() -> dict[str, Tuto]:
    return {t.id: t for t in lister_tutos()}


def creer_simulateur(scenario: str = SCENARIO_DEFAUT) -> Simulateur:
    c = centrale_scenario(scenario)
    sim = Simulateur(c, c.cfg.simulation)
    sim.scenario = scenario
    return sim


def etat_standard(c: Centrale) -> str:
    """État standard du réacteur (§5)."""
    return etats.LIBELLES[etats.code_etat(c)]


def etat_ui(c: Centrale, sim: Simulateur) -> dict[str, Any]:
    composants = {k: o.etat_ui() for k, o in c.commandables.items()}
    composants.update({gv.id: gv.etat_ui() for gv in c.gvs})
    composants.update(c.vapeur.etats_ui())
    composants.update({s.id: s.etat_ui() for s in c.pzr.soupapes})
    composants.update({k: o.etat_ui() for k, o in c.composants.items() if k not in composants})
    composants[c.condenseur.id] = c.condenseur.etat_ui()
    composants[c.pzr.id] = c.pzr.etat_ui()
    lg = c.logique.etat
    noms = ("au", "au_causes", "causes_au", "p4", "p7", "p8", "p9", "p10", "p12", "p13", "p14", "p14_gv",
            "niveau_tres_bas_gv", "c2", "c3", "c4", "c5", "c7", "c8", "c9", "c11", "flux_bas_bloque",
            "causes_turbine", "isolement_are_au", "isolement_are_complet", "recirc_cex", "decharge_isolee",
            "otdt_seuil_c", "opdt_seuil_c", "p11", "is_actif", "is_causes", "causes_is", "is_bloquee",
            "rra_isole_auto", "perte_rri", "aspiration_ptr", "isolement_vapeur", "phase_b", "causes_isolement_vapeur",
            "is_inhibee")
    return {
        "type": "etat",
        "t_s": c.t_s,
        "acceleration": sim.acceleration,
        "acceleration_reelle": sim.acceleration_reelle,
        "pause": sim.pause,
        "scenario": sim.scenario,
        "etat_standard": etat_standard(c),
        "etats": etats.etat_ui(c),
        "mesures": c.mesures,
        "composants": composants,
        "logique": {k: getattr(lg, k) for k in noms},
        "gct": {"mode": c.gct.etat.mode, "c7": c.gct.etat.c7, "c8": c.gct.etat.c8},
        "alarmes": c.alarmes.liste(),
        "journal": c.journal.derniers(NB_EVENEMENTS_DIFFUSES),
        "arret": sim.arret,
        "arrets_en_attente": len(sim.file),
        "observation": {"points": sorted(sim.points), "fin_s": sim.fin_observation_s, "commente": sim.permanents},
    }


def seuils(c: Centrale) -> dict[str, str]:
    """Textes des seuils et permissifs pour l'onglet Logique (tirés de plant.yaml)."""
    lg, gv = c.cfg.logique, c.cfg.generateurs_vapeur.seuils
    au, v = lg.au, lg.au.votes
    return {
        "P-7": f"non P-10 ET charge turbine < {lg.p7.charge_turbine_max_pct:g} % (P-13) : bloque les AU « en puissance »",
        "P-8": f"puissance < {lg.p8_puissance_pct:g} % : pas d'AU sur perte d'une seule boucle",
        "P-9": f"puissance < {lg.p9_puissance_pct:g} %",
        "P-10": f"puissance > {lg.p10_puissance_pct:g} % ({v.flux}) : autorise le blocage de l'AU flux seuil bas",
        "P-12": f"Tmoy < {lg.p12_tmoy_c:g} °C ({v.dt}) : contournement limité au groupe 1",
        "P-11": f"P PZR < {lg.p11_p_pzr_bar:g} bar ({v.p_pzr}) : blocage de l'IS autorisé, accumulateurs isolables",
        "P-14": f"niveau GV > {gv.tres_haut_pct:g} % ({gv.vote} sur 1 GV) : turbine + APP + isolement ARE",
        "C-2": f"flux > {lg.c2_puissance_pct:g} % : retrait des grappes interdit",
        "C-3": f"préalarme ΔT surtempérature ({lg.otdt.prealarme_pct:g} %) : retrait interdit + runback turbine",
        "C-4": f"préalarme ΔT surpuissance ({lg.opdt.prealarme_pct:g} %) : retrait interdit + runback turbine",
        "C-5": f"charge turbine < {lg.c5_charge_pct:g} % : retrait automatique interdit",
        "C-7": f"baisse de charge > {c.cfg.gct_c.c7.echelon_pct:g} % : arme le contournement (mémorisé)",
        "C-8": "turbine déclenchée : arme le contournement (régulateur déclenchement)",
        "C-9": (f"≥ {lg.c9.crf_mini} pompe CRF ET P condenseur < {lg.c9.p_cond_max_bar:g} bar "
                f"(perdu à {lg.c9.p_cond_perte_bar:g} bar) : autorise le contournement"),
        "C-11": f"groupe de régulation > {lg.c11_pas:g} pas : retrait automatique interdit",
        "AU flux haut": f"> {au.flux_haut_pct:g} % ({v.flux}), jamais bloqué",
        "AU flux seuil bas": f"> {au.flux_bas_pct:g} % ({v.flux}), bloquable au-dessus de P-10",
        "AU variation de flux": f"± {au.variation_flux_pct:g} % ({au.variation_flux_constante_s:g} s, {v.flux})",
        "AU ΔT surtempérature": f"ΔT > seuil calculé (Tmoy, P) ({v.dt})",
        "AU ΔT surpuissance": f"ΔT > seuil calculé (Tmoy, dTmoy/dt) ({v.dt})",
        "AU P PZR basse": f"< {au.p_pzr_basse_bar:g} bar ({v.p_pzr}), au-dessus de P-7",
        "AU P PZR haute": f"> {au.p_pzr_haute_bar:g} bar ({v.p_pzr})",
        "AU niveau PZR haut": f"> {au.niveau_pzr_haut_pct:g} % ({v.niveau_pzr}), au-dessus de P-7",
        "AU débit primaire bas": f"< {au.debit_bas_pct:g} % ({v.debit} par boucle) : 1 boucle > P-8, 2 boucles > P-7",
        "AU pompes primaires": f"disjoncteurs ouverts ({v.pompes}), au-dessus de P-7",
        "AU niveau GV très bas": f"< {gv.tres_bas_pct:g} % ({gv.vote} sur 1 GV)",
        "AU débit d'eau insuffisant": (f"écart vapeur/eau > {au.ecart_vapeur_eau_pct:g} % ET niveau GV "
                                       f"< {au.niveau_gv_bas_pct:g} %"),
        "AU déclenchement turbine": "4/4 vannes d'arrêt fermées, au-dessus de P-7",
        "Isolement ARE GD": f"AU (P-4) ET Tmoy < {lg.isolement_are_au.tmoy_max_c:g} °C",
        "Isolement ARE complet": "P-14 (mémorisé, réarmement opérateur)",
        "Démarrage ASG": "niveau GV très bas (2 MP + TP) ; perte des 2 APP (2 MP)",
        "Niveau PZR bas": f"< {c.cfg.pressuriseur.niveau_bas_pct:g} % : décharge isolée, chaufferettes coupées",
    }


def message_init(c: Centrale, sim: Simulateur) -> dict[str, Any]:
    cfg = c.cfg
    return {
        "type": "init",
        "meta": {"version": cfg.meta.version, "nom": cfg.meta.nom, "reacteur": cfg.meta.reacteur,
                 "reacteur_detail": cfg.meta.reacteur_detail},
        "accelerations": cfg.simulation.accelerations,
        "variables": sorted(c.mesures),
        "scenarios": [{"id": s.id, "titre": s.titre, "description": s.description, "objectifs": s.objectifs}
                      for s in lister_scenarios()],
        "seuils": seuils(c),
        "tutos": [t.vers_ui() for t in tutos().values()],
        "explications": {e.id: asdict(e) for e in catalogue().explications},
        "etat": etat_ui(c, sim),
    }


def traiter_message(sim: Simulateur, msg: dict[str, Any]) -> dict[str, Any] | None:
    """Traite un message de l'interface ; renvoie la réponse éventuelle."""
    c = sim.centrale
    genre = msg.get("type")
    if genre == "commande":
        valeur = msg.get("valeur")
        valeur = float(valeur) if valeur is not None and valeur != "" else None
        r = c.commande(str(msg.get("cible")), str(msg.get("action")), valeur)
        return {"type": "reponse", "cible": msg.get("cible"), "action": msg.get("action"),
                "ok": r.ok, "raisons": r.raisons}
    if genre == "conditions":
        cible = str(msg.get("cible"))
        commandes = c.liste_commandes(cible) if cible in c.commandables else []
        return {"type": "conditions", "cible": cible, "commandes": commandes}
    if genre == "acceleration":
        valeur = int(msg.get("valeur", 1))
        if valeur in sim.cfg.accelerations:
            sim.acceleration = valeur
            if sim.arret is not None:          # relancer pendant une explication = « continuer »
                sim.continuer()
            else:
                sim.pause = False
        return None
    if genre == "pause":
        if not msg.get("valeur", True) and sim.arret is not None:
            sim.continuer()
        else:
            sim.pause = bool(msg.get("valeur", True))
        return None
    if genre == "acquitter":
        c.alarmes.acquitter(msg.get("id"))
        return None
    if genre == "historique":
        return {"type": "historique", "series": c.historique.series(list(msg.get("vars", [])))}
    if genre == "exporter":
        return {"type": "export", "donnees": c.exporter(), "t_s": c.t_s}
    if genre == "importer":
        nouvelle = Centrale(c.cfg)
        try:
            nouvelle.importer(msg.get("donnees") or {})
        except (KeyError, TypeError, ValueError) as e:
            return {"type": "import", "ok": False, "erreur": f"Sauvegarde invalide : {e}"}
        sim.remplacer(nouvelle, "sauvegarde chargée")
        return {"type": "import", "ok": True, "t_s": nouvelle.t_s}
    if genre == "scenario":
        ident = str(msg.get("id"))
        if ident not in {s.id for s in lister_scenarios()}:
            return {"type": "erreur", "texte": f"Scénario inconnu : {ident}"}
        sim.remplacer(centrale_scenario(ident), ident)
        return {"type": "import", "ok": True, "t_s": sim.centrale.t_s}
    if genre == "tuto":                          # charger l'état de départ d'un tuto (en pause)
        t = tutos().get(str(msg.get("id")))
        if t is None:
            return {"type": "erreur", "texte": f"Tuto inconnu : {msg.get('id')}"}
        sim.remplacer(centrale_tuto(t), t.scenario or t.etat_initial)
        sim.pause = True
        sim.acceleration = sim.cfg.accelerations[0]
        return {"type": "tuto", "id": t.id, "t_s": sim.centrale.t_s}
    if genre == "observer":                      # étape d'observation : points d'arrêt + durée
        ids = [str(x) for x in msg.get("points", [])]
        duree = msg.get("duree_s")
        valeur = int(msg.get("acceleration", sim.cfg.accelerations[0]))
        if valeur in sim.cfg.accelerations:
            sim.acceleration = valeur
        sim.observer(catalogue().motifs(ids), float(duree) if duree else None)
        return None
    if genre == "continuer":
        sim.continuer()
        return None
    if genre == "commente":                      # mode libre commenté : pause sur chaque automatisme expliqué
        pause = sim.pause and sim.arret is None
        if msg.get("valeur"):
            cat = catalogue()
            sim.observer(cat.motifs(), None, permanents=True, reprise_s=cat.reprise_mode_commente_s)
        else:
            sim.arreter_observation()
        sim.pause = pause
        return None
    return {"type": "erreur", "texte": f"message inconnu : {genre}"}
