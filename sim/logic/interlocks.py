"""Verrous de manœuvre : pour chaque (équipement, action), la liste des conditions ✓/✗.

Une action est refusée si au moins une condition est fausse ; l'interface affiche
le texte de chaque condition, ce qui dit au joueur POURQUOI c'est refusé.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sim.components.base import Composant, Condition
from sim.components.pump import Pompe
from sim.components.valve import Vanne
from sim.core_model.coeur import Coeur
from sim.electrical.reseau import Diesel, TableauSecouru
from sim.logic.regulations import ConsigneReglable
from sim.systems.gct import Contournement
from sim.systems.pzr import GroupeChaufferettes
from sim.systems.rri import PANNE_PERMANENTE_S
from sim.units import POURCENT, S_PAR_MIN

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
        if p in c.primaire.pompes:
            i = c.primaire.pompes.index(p)
            pc = c.cfg.primaire
            conds.append(Condition(f"Pression primaire ≥ {pc.p_min_demarrage_pompe_bar:g} bar (joint n°1)",
                                   c.pzr.p_bar >= pc.p_min_demarrage_pompe_bar))
            duree = c.primaire.etat.huile_s[i]
            conds.append(Condition(f"Pompe de soulèvement d'huile {c.primaire.huile[i].id} en service depuis "
                                   f"≥ {pc.soulevement_huile_s:g} s ({duree:.0f} s)",
                                   duree >= pc.soulevement_huile_s))
        if p is c.asg.turbopompe:
            conds.append(Condition(f"Pression vapeur des GV d'alimentation ≥ {c.cfg.asg.p_vapeur_min_bar:g} bar",
                                   c.asg.vapeur_disponible(c.gvs)))
        if p in c.primaire.pompes:
            conds.append(Condition("RRI en service (paliers et barrière thermique)", c.rri.disponible()))
        if p in c.rcv.pompes:
            conds.append(Condition("Aspiration ouverte (VCT ou PTR)",
                                   c.rcv.asp_vct.etat.position > 0.0 or c.rcv.asp_ptr.etat.position > 0.0))
        if p in c.rra.pompes:
            i = c.rra.pompes.index(p)
            en_is = c.logique.etat.is_actif and (c.ris.recirculation or
                                                 c.rcv.niveau_ptr_pct >= c.cfg.ris.ptr_recirculation_pct)
            conds.append(Condition("Aspiration du train ouverte (branche chaude), ou IS avec PTR / puisards",
                                   c.rra.aspiration_ouverte(i) or en_is))
        if p in c.rri.pompes:
            reste = c.rri.etat.panne_jusqua_s - c.t_s
            conds.append(Condition("Circuit RRI réparé" + (f" ({reste / S_PAR_MIN:.0f} min)"
                                                            if 0 < reste < PANNE_PERMANENTE_S / 2 else ""), reste <= 0.0))
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
        conds += conditions_ouverture_v2(c, v)
    elif action == "fermer":
        conds.append(Condition("Pas d'ordre automatique d'ouverture"
                               + (f" ({v.etat.ordre_raison})" if ordre == 1.0 else ""), ordre != 1.0))
        if v in c.accus.isolement:
            seuil = c.cfg.logique.p11_p_pzr_bar
            conds.append(Condition(f"P-11 présent (P PZR < {seuil:g} bar)", c.logique.etat.p11))
    elif action in ("auto", "position"):
        conds.append(Condition("Pas d'ordre automatique en cours"
                               + (f" ({v.etat.ordre_raison})" if ordre is not None else ""), ordre is None))
        if action == "position":
            conds += [Condition("Vanne en manuel", not v.etat.auto), _plage(valeur, 0.0, POURCENT, "%")]
    return conds


def conditions_ouverture_v2(c: Centrale, v: Vanne) -> list[Condition]:
    """Ordre imposé de mise en service du RCV (§4.2), verrou RRA, borication d'urgence."""
    rcv, lg = c.rcv, c.logique.etat
    seuil_niveau = c.cfg.pressuriseur.niveau_bas_pct
    niveau_ok = Condition(f"Niveau PZR > {seuil_niveau:g} %", c.pzr.capteur_niveau.mediane > seuil_niveau)
    if v in rcv.lcv:
        ouverts = [o.id for o in rcv.orifices if o.etat.position > 0.0]
        return [Condition("Aucune vanne d'orifice ouverte" + (f" ({', '.join(ouverts)})" if ouverts else ""),
                          not ouverts), niveau_ok]
    if v in rcv.orifices:
        return [Condition("Pompe de charge en marche", rcv.nb_pompes() > 0),
                Condition("LCV-459 et LCV-460 ouvertes", all(x.etat.position >= 1.0 for x in rcv.lcv)), niveau_ok]
    if v is rcv.isol_enc or v is rcv.isol_charge:
        return [Condition("Pas d'IS", not lg.is_actif)]
    if v is rcv.urgence:
        return [Condition("Pompe de charge en marche", rcv.nb_pompes() > 0)]
    if v in c.ris.puisard:
        mini = c.cfg.ris.puisard_min_m3
        return [Condition(f"Eau dans les puisards ≥ {mini:g} m³ ({c.enceinte.etat.puisard_m3:.0f} m³)",
                          c.enceinte.etat.puisard_m3 >= mini)]
    if v in c.rra.vannes_aspiration():
        seuil = c.cfg.rra.p_ouverture_max_bar
        return [Condition(f"Pression primaire < {seuil:g} bar ({c.pzr.p_bar:.1f} bar)", c.pzr.p_bar < seuil)]
    return []


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
        maxi = cfg.p_elec_nom_mw * cfg.consigne_max_pct / POURCENT
        e = c.logique.etat
        conds = [Condition("Alternateur couplé", t.couplee), _plage(valeur, 0.0, maxi, "MW")]
        if valeur is not None and valeur > t.consigne_eff_mw:
            conds.append(Condition("Pas de préalarme ΔT (C-3 / C-4)", not (e.c3 or e.c4)))
        return conds
    return []


def conditions_grappes(c: Centrale, coeur: Coeur, action: str, valeur: float | None) -> list[Condition]:
    e, lg = c.logique.etat, c.cfg.logique
    pas_au = Condition("AU réarmé (grappes non maintenues insérées)", not e.au)
    blocages = [Condition(f"Pas de C-2 (flux > {lg.c2_puissance_pct:g} %)", not e.c2),
                Condition("Pas de C-3 / C-4 (préalarme ΔT)", not (e.c3 or e.c4))]
    if action == "auto":
        return [pas_au, Condition("Groupes d'arrêt extraits", coeur.etat.arret_insere <= 0.0)]
    if action == "manu":
        return []
    if action == "position":
        conds = [pas_au, Condition("Grappes en manuel", not coeur.etat.auto),
                 _plage(valeur, 0.0, coeur.cfg.grappes.pas_max, "pas")]
        if valeur is not None and valeur > coeur.etat.z_pas:
            conds += blocages
        return conds
    if action == "extraire_arret":
        return [pas_au, Condition("Groupes d'arrêt insérés", coeur.etat.arret_insere > 0.0)] + blocages
    if action == "position_g":
        conds = [pas_au, _plage(valeur, 0.0, coeur.cfg.grappes.pas_max, "pas")]
        if valeur is not None and valeur > coeur.etat.g_pas:
            conds += blocages
        return conds
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
    if action == "bloquer_flux_bas":
        return [Condition("AU flux seuil bas non bloqué", not e.flux_bas_bloque),
                Condition(f"P-10 présent (puissance > {c.cfg.logique.p10_puissance_pct:g} %)", e.p10)]
    if action == "debloquer_flux_bas":
        return [Condition("AU flux seuil bas bloqué", e.flux_bas_bloque)]
    if action == "rearmer_isolement_are":
        return [Condition("Isolement ARE complet présent", e.isolement_are_complet),
                Condition("P-14 disparu (niveaux GV < seuil très haut)", not e.p14),
                Condition("Pas d'IS", not e.is_actif)]
    if action == "bloquer_is":
        return [Condition("IS non bloquée", not e.is_bloquee),
                Condition(f"P-11 présent (P PZR < {c.cfg.logique.p11_p_pzr_bar:g} bar)", e.p11)]
    if action == "rearmer_isolement_vapeur":
        return [Condition("Isolement vapeur présent", e.isolement_vapeur),
                Condition("Aucune cause présente" + (f" ({', '.join(e.causes_isolement_vapeur)})"
                                                     if e.causes_isolement_vapeur else ""), not e.causes_isolement_vapeur)]
    if action == "rearmer_phase_b":
        seuil = c.cfg.logique.p_enceinte_tres_haute_bar_rel
        return [Condition("Phase B présente", e.phase_b),
                Condition(f"P enceinte < {seuil:g} bar rel ({c.enceinte.p_rel_bar:.2f})", c.enceinte.p_rel_bar < seuil)]
    if action == "declencher_is":
        return [Condition("IS non déjà présente", not e.is_actif)]
    if action == "rearmer_is":
        duree = c.t_s - e.is_t_s
        delai = c.cfg.logique.injection_securite.rearmement_s
        return [Condition("IS présente", e.is_actif),
                Condition(f"IS présente depuis ≥ {delai:g} s ({duree:.0f} s)", e.is_actif and duree >= delai),
                Condition("AU présent (P-4)", e.au),
                Condition("Aucune cause d'IS présente" + (f" ({', '.join(e.causes_is)})" if e.causes_is else ""),
                          not e.causes_is)]
    return []


def conditions_diesel(c: Centrale, d: Diesel, action: str) -> list[Condition]:
    e = d.etat
    tb = c.elec.tableaux[d.tableau]
    if action == "demarrer":
        return [Condition("Diesel à l'arrêt", e.etat in ("arret", "echec")),
                Condition("Pas de panne en cours (réarmer après réparation)", not e.refus)]
    if action == "arreter":
        return [Condition("Diesel en marche", d.en_service), Condition("Diesel découplé", e.etat != "couple")]
    if action == "coupler":
        return [Condition("Diesel à vitesse et tension", e.etat == "pret"),
                Condition(f"Tableau {tb.id} hors tension", not tb.sous_tension),
                Condition("Arrivée normale ouverte", not tb.etat.arrivee_fermee)]
    if action == "decoupler":
        return [Condition("Diesel couplé", e.etat == "couple")]
    if action == "rearmer":
        repare = e.reparation_t_s is not None and c.t_s >= e.reparation_t_s
        reste = "" if e.reparation_t_s is None else f" ({max(0.0, e.reparation_t_s - c.t_s) / S_PAR_MIN:.0f} min)"
        return [Condition("Diesel en panne ou en échec", e.refus or e.etat == "echec"),
                Condition("Panne réparée" + reste, repare or not e.refus)]
    return []


def conditions_tableau(c: Centrale, tb: TableauSecouru, action: str) -> list[Condition]:
    if action == "fermer_arrivee":
        return [Condition("Arrivée ouverte", not tb.etat.arrivee_fermee),
                Condition(f"Tableau normal {tb.normal} sous tension", c.elec.sous_tension(tb.normal))]
    if action == "ouvrir_arrivee":
        return [Condition("Arrivée fermée", tb.etat.arrivee_fermee)]
    return []


def conditions_rea(c: Centrale, action: str) -> list[Condition]:
    rea = c.rea.etat
    if action == "borication":
        return [Condition("Bâches d'acide borique non vides", rea.acide_m3 > 0.0)]
    if action == "dilution":
        return [Condition("Bâche d'eau d'appoint non vide", rea.eau_m3 > 0.0)]
    return []


def conditions_gct(c: Centrale, g: Contournement, action: str, valeur: float | None) -> list[Condition]:
    if action == "consigne":
        return [_plage(valeur, c.cfg.condenseur.p_incondensables_bar, max(c.cfg.vapeur.soupapes.tarages_bar), "bar")]
    if action == "mode_tmoy":
        return [Condition("Contournement en mode pression", g.etat.mode != "tmoy")]
    if action == "mode_pression":
        return [Condition("Contournement en mode Tmoy", g.etat.mode != "pression")]
    if action == "rearmer_c7":
        return [Condition("C-7 armé", g.etat.c7)]
    return []


def conditions_chaufferettes(c: Centrale, ch: GroupeChaufferettes, action: str,
                             valeur: float | None) -> list[Condition]:
    if action == "puissance":
        return [Condition("Chaufferettes en manuel", not ch.etat.auto), _plage(valeur, 0.0, POURCENT, "%"),
                Condition("Pas de coupure automatique" + (f" ({ch.etat.coupe})" if ch.etat.coupe else ""),
                          not ch.etat.coupe)]
    return []


def conditions(c: Centrale, obj: Composant, action: str, valeur: float | None) -> list[Condition]:
    """Conditions de l'action `action` sur `obj` (liste vide = toujours possible)."""
    if isinstance(obj, Pompe):
        return conditions_pompe(c, obj, action, valeur)
    if isinstance(obj, Vanne):
        return conditions_vanne(c, obj, action, valeur)
    if obj is c.turbine:
        return conditions_turbine(c, action, valeur)
    if isinstance(obj, Coeur):
        return conditions_grappes(c, obj, action, valeur)
    if obj is c.logique:
        return conditions_rpr(c, action)
    if isinstance(obj, Contournement):
        return conditions_gct(c, obj, action, valeur)
    if isinstance(obj, GroupeChaufferettes):
        return conditions_chaufferettes(c, obj, action, valeur)
    if isinstance(obj, ConsigneReglable):
        return [_plage(valeur, obj.mini, obj.maxi, obj.unite)]
    if obj is c.rea:
        return conditions_rea(c, action)
    if isinstance(obj, Diesel):
        return conditions_diesel(c, obj, action)
    if isinstance(obj, TableauSecouru):
        return conditions_tableau(c, obj, action)
    if obj is c.elec:
        return [Condition("Réseau disponible" if action == "perte_reseau" else "Réseau perdu",
                          c.elec.etat.reseau_ok == (action == "perte_reseau"))]
    if obj is c.air:
        return [Condition("Fuite présente sur le collecteur", c.air.etat.fuite > 0.0)]
    return []
