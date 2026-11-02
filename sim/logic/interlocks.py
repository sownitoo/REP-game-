"""Verrous de manœuvre : pour chaque (équipement, action), la liste des conditions ✓/✗.

Une action est refusée si au moins une condition est fausse ; l'interface affiche
le texte de chaque condition, ce qui dit au joueur POURQUOI c'est refusé.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sim.components.base import Composant, Condition
from sim.components.pump import Pompe
from sim.components.valve import Vanne
from sim.logic.regulations import ConsigneReglable
from sim.systems.gct import Contournement
from sim.units import POURCENT

if TYPE_CHECKING:
    from sim.plant import Centrale


def _plage(valeur: float | None, mini: float, maxi: float, unite: str) -> Condition:
    ok = valeur is not None and mini <= valeur <= maxi
    return Condition(f"Valeur entre {mini:g} et {maxi:g} {unite}", ok)


def conditions_pompe(c: Centrale, p: Pompe, action: str, valeur: float | None) -> list[Condition]:
    lg = c.cfg.logique
    if action == "demarrer":
        conds = [Condition("Pompe à l'arrêt", not p.etat.en_marche)]
        if p.alim:
            conds.append(Condition(f"Tableau {p.alim} sous tension", c.sources(p).electricite_ok))
        if p in c.apps or p.id == "APD":
            seuil = lg.declenchement_app.p_aspiration_min_bar
            conds.append(Condition(f"Pression d'aspiration ≥ {seuil:g} bar (une CEX en service)",
                                   c.poste_eau.p("N_ABP") >= seuil))
        if p in c.apps:
            conds.append(Condition("Pas d'ordre de déclenchement P-14", not c.logique.etat.p14))
        if p in c.cexs:
            seuil = lg.declenchement_cex.niveau_puits_min_pct
            conds.append(Condition(f"Niveau puits > {seuil:g} %", c.condenseur.niveau_puits_pct() > seuil))
        return conds
    if action == "arreter":
        return [Condition("Pompe en marche", p.etat.en_marche)]
    if action in ("auto", "manu"):
        return [Condition("Pompe à vitesse variable", p.cfg.vitesse_variable)]
    if action == "vitesse":
        mini = POURCENT * (p.cfg.vitesse_min or 0.0)
        maxi = POURCENT * (p.cfg.vitesse_max or 1.0)
        return [Condition("Pompe à vitesse variable", p.cfg.vitesse_variable),
                Condition("Pompe en manuel", not p.etat.auto), _plage(valeur, mini, maxi, "%")]
    return []


def conditions_vanne(c: Centrale, v: Vanne, action: str, valeur: float | None) -> list[Condition]:
    conds: list[Condition] = []
    src = c.sources(v)
    if v.cfg.actionneur == "MOV" and v.alim:
        conds.append(Condition(f"Tableau {v.alim} sous tension (vanne motorisée)", src.electricite_ok))
    if v.cfg.actionneur == "AOV" and v.air:
        conds.append(Condition(f"Air comprimé {v.air} disponible", src.air_ok or v.etat.air_restant_s > 0.0))
    ordre = v.etat.ordre
    if action == "ouvrir":
        conds.append(Condition("Pas d'ordre automatique de fermeture"
                               + (f" ({v.etat.ordre_raison})" if ordre == 0.0 else ""), ordre != 0.0))
        if v.id.startswith("VIV") and not v.id.endswith("_BP"):
            b = v.id[len("VIV"):]
            dp = c.gv(int(b)).p_bar - c.vapeur.etat.p_collecteur_bar
            seuil = c.cfg.logique.ouverture_viv.dp_max_bar
            conds.append(Condition(f"ΔP GV{b} − collecteur < {seuil:g} bar (équilibrer par le by-pass)",
                                   abs(dp) < seuil))
    elif action == "fermer":
        conds.append(Condition("Pas d'ordre automatique d'ouverture"
                               + (f" ({v.etat.ordre_raison})" if ordre == 1.0 else ""), ordre != 1.0))
    elif action in ("auto", "position"):
        conds.append(Condition("Pas d'ordre automatique en cours"
                               + (f" ({v.etat.ordre_raison})" if ordre is not None else ""), ordre is None))
        if action == "position":
            conds += [Condition("Vanne en manuel", not v.etat.auto), _plage(valeur, 0.0, POURCENT, "%")]
    return conds


def conditions_turbine(c: Centrale, action: str, valeur: float | None) -> list[Condition]:
    t = c.turbine.etat
    cfg = c.cfg.turbine
    lg = c.cfg.logique
    if action == "declencher":
        return [Condition("Turbine non déclenchée", not t.declenchee)]
    if action == "rearmer":
        conds = [Condition("Turbine déclenchée", t.declenchee)]
        causes = c.logique.etat.causes_turbine
        conds.append(Condition("Aucune cause de déclenchement présente"
                               + (f" (présentes : {', '.join(causes)})" if causes else ""), not causes))
        return conds
    if action == "consigne_vitesse":
        return [Condition("Turbine réarmée", not t.declenchee), Condition("Alternateur découplé", not t.couplee),
                _plage(valeur, 0.0, cfg.vitesse_nom_tr_min, "tr/min")]
    if action == "coupler":
        ecart = abs(t.vitesse_tr_min - cfg.vitesse_nom_tr_min) / cfg.vitesse_nom_tr_min * POURCENT
        seuil = cfg.couplage.ecart_vitesse_max_pct
        return [Condition("Turbine réarmée", not t.declenchee), Condition("Alternateur découplé", not t.couplee),
                Condition(f"Vitesse à ± {seuil:g} % du synchronisme (écart {ecart:.2f} %)", ecart <= seuil)]
    if action == "decoupler":
        seuil = lg.p7.charge_turbine_max_pct
        return [Condition("Alternateur couplé", t.couplee),
                Condition(f"Charge < {seuil:g} % (P-13)", t.p_elec_mw < seuil / POURCENT * cfg.p_elec_nom_mw)]
    if action == "consigne_mw":
        maxi = cfg.p_elec_nom_mw * c.cfg.source_v0.p_max_pct / POURCENT
        return [Condition("Alternateur couplé", t.couplee), _plage(valeur, 0.0, maxi, "MW")]
    return []


def conditions_source(c: Centrale, action: str, valeur: float | None) -> list[Condition]:
    au = c.logique.etat.au
    pas_au = Condition("AU réarmé (grappes non chutées)", not au)
    if action == "auto":
        return [pas_au]
    if action == "consigne_mw":
        maxi = c.cfg.source_v0.p_nom_mw * c.cfg.source_v0.p_max_pct / POURCENT
        return [pas_au, Condition("Source en manuel", not c.source.etat.auto), _plage(valeur, 0.0, maxi, "MW")]
    return []


def conditions_rpr(c: Centrale, action: str) -> list[Condition]:
    e = c.logique.etat
    if action == "declencher_au":
        return [Condition("AU non déjà présent", not e.au)]
    if action == "rearmer_au":
        causes = c.logique.causes_au_presentes()
        return [Condition("AU présent", e.au),
                Condition("Aucune cause d'AU présente" + (f" (présentes : {', '.join(causes)})" if causes else ""),
                          not causes)]
    if action == "rearmer_isolement_are":
        return [Condition("Isolement ARE complet présent", e.isolement_are_complet),
                Condition("P-14 disparu (niveaux GV < seuil très haut)", not e.p14)]
    return []


def conditions(c: Centrale, obj: Composant, action: str, valeur: float | None) -> list[Condition]:
    """Conditions de l'action `action` sur `obj` (liste vide = toujours possible)."""
    if isinstance(obj, Pompe):
        return conditions_pompe(c, obj, action, valeur)
    if isinstance(obj, Vanne):
        return conditions_vanne(c, obj, action, valeur)
    if obj is c.turbine:
        return conditions_turbine(c, action, valeur)
    if obj is c.source:
        return conditions_source(c, action, valeur)
    if obj is c.logique:
        return conditions_rpr(c, action)
    if isinstance(obj, ConsigneReglable):
        return [_plage(valeur, obj.mini, obj.maxi, obj.unite)]
    if isinstance(obj, Contournement):
        return [_plage(valeur, c.cfg.condenseur.p_incondensables_bar, max(c.cfg.vapeur.soupapes.tarages_bar), "bar")]
    return []
