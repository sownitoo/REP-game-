"""Signaux et automatismes V2 : P-11, injection de sécurité (signal), RCV, VCT, RRA, RRI, accumulateurs.

IS (V2 : le signal et ses ordres « hors RIS » ; l'injection elle-même arrive en V4) :
  causes : P PZR < 122 bar (2/4) ou P vapeur < 41 bar sur un GV, bloquables sous P-11, ou manuelle.
  ordres : AU, isolement complet de l'eau alimentaire, démarrage des motopompes ASG, phase A
  (isolement enceinte de la décharge RCV), aspiration des pompes de charge sur la PTR,
  ouverture des accumulateurs.
P-11 (P PZR < 138 bar) : autorise le blocage de l'IS ; au-dessus, le blocage est levé et les
  accumulateurs sont rouverts automatiquement.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sim.core.events import PRIORITE_HAUTE, PRIORITE_MOYENNE
from sim.logic.voting import vote
from sim.units import POURCENT

if TYPE_CHECKING:
    from sim.logic.protection import EtatLogique
    from sim.plant import Centrale

FERMEE = 0.0
OUVERTE = 1.0


def calculer_is(c: Centrale, e: EtatLogique) -> None:
    lg = c.cfg.logique
    isc = lg.injection_securite
    votes = lg.au.votes.p_pzr
    capteur = c.pzr.capteur_p
    e.p11 = vote(votes, capteur.depasse(lg.p11_p_pzr_bar, au_dessus=False))
    if not e.p11 and e.is_bloquee:
        e.is_bloquee = False
        c.journal.ajouter(c.t_s, "automatisme", "P-11 perdu : blocage de l'IS levé", PRIORITE_MOYENNE)
    causes = []
    if not e.is_bloquee and vote(votes, capteur.depasse(isc.p_pzr_basse_bar, au_dessus=False)):
        causes.append(f"pression PZR < {isc.p_pzr_basse_bar:g} bar")
    p_rel = c.enceinte.p_rel_bar
    if p_rel > isc.p_enceinte_haute_bar_rel:
        causes.append(f"pression enceinte > {isc.p_enceinte_haute_bar_rel:g} bar rel")
    p_gv = [gv.p_bar for gv in c.gvs]
    if max(p_gv) - min(p_gv) > isc.ecart_vapeur_bar:
        causes.append(f"écart de pression entre lignes vapeur > {isc.ecart_vapeur_bar:g} bar")
    e.causes_isolement_vapeur = causes_isolement_vapeur(c, e)
    if e.causes_isolement_vapeur and not e.causes_isolement_vapeur[0].startswith("pression enceinte"):
        causes.append(e.causes_isolement_vapeur[0])
    if e.is_inhibee:                       # après réarmement de l'IS : seulement manuelle, jusqu'au réarmement de l'AU
        causes = []
    if e.is_manuel:
        causes = ["manuelle"] + causes
        e.is_manuel = False
    e.causes_is = causes
    if causes and not e.is_actif:
        e.is_actif = True
        e.is_causes = list(causes)
        e.is_t_s = c.t_s
        c.journal.ajouter(c.t_s, "automatisme", f"INJECTION DE SÉCURITÉ : {', '.join(causes)}", PRIORITE_HAUTE)


def causes_isolement_vapeur(c: Centrale, e: EtatLogique) -> list[str]:
    """Débit vapeur haut ET (P vapeur basse OU Tmoy très basse P-12) ; ou P enceinte très haute."""
    isc, lg = c.cfg.logique.injection_securite, c.cfg.logique
    causes = []
    if c.enceinte.p_rel_bar > lg.p_enceinte_tres_haute_bar_rel:
        causes.append(f"pression enceinte > {lg.p_enceinte_tres_haute_bar_rel:g} bar rel")
    # seuil « débit vapeur haut » : 40 % sous 20 % de charge turbine, puis linéaire jusqu'à 110 % à pleine charge
    charge = min(max(c.turbine.charge_pct, isc.charge_debit_bas_pct), POURCENT)
    pente = (isc.debit_vapeur_haut_pct - isc.debit_vapeur_haut_bas_pct) / (POURCENT - isc.charge_debit_bas_pct)
    seuil = (isc.debit_vapeur_haut_bas_pct + pente * (charge - isc.charge_debit_bas_pct)) / POURCENT
    seuil *= c.cfg.generateurs_vapeur.debit_vapeur_nom_kg_s
    debit_haut = any(gv.etat.qm_ligne_kg_s + gv.etat.qm_decharge_kg_s > seuil for gv in c.gvs)
    p_basse = min(gv.p_bar for gv in c.gvs) < isc.p_vapeur_basse_bar
    if debit_haut and (p_basse or e.p12):
        causes.append("débit vapeur haut + " + ("pression vapeur basse" if p_basse else "Tmoy très basse (P-12)"))
    return causes


def appliquer_automatismes_v2(c: Centrale, e: EtatLogique, dt: float) -> None:
    journal, t = c.journal, c.t_s
    cfg = c.cfg
    rcv = c.rcv
    p_pzr = c.pzr.capteur_p.mediane

    # --- IS : ordres ---
    if e.is_actif:
        e.isolement_are_complet = True
        ptr_bas = rcv.niveau_ptr_pct < cfg.ris.ptr_recirculation_pct
        demarrage = c.asg.motopompes + rcv.pompes + c.ris.pompes_mp + c.rri.pompes + c.rri.pompes_sec
        if not ptr_bas or c.ris.recirculation:
            demarrage += c.ris.pompes_bp
        for p in demarrage:
            if not p.etat.en_marche and not p.etat.defaut and c.sources(p).electricite_ok:
                p.demarrer()
                journal.ajouter(t, "automatisme", f"Démarrage {p.id} (IS)", PRIORITE_MOYENNE)
    raison_is = "IS (phase A)"
    rcv.isol_enc.fixer_ordre(FERMEE if e.is_actif else None, raison_is)
    rcv.isol_charge.fixer_ordre(FERMEE if e.is_actif else None, "IS")
    c.ris.bit.fixer_ordre(OUVERTE if e.is_actif else None, "IS : injection haute pression")

    # --- isolement vapeur (mémorisé) ---
    if e.causes_isolement_vapeur and not e.isolement_vapeur:
        e.isolement_vapeur = True
        journal.ajouter(t, "automatisme", f"ISOLEMENT VAPEUR : {e.causes_isolement_vapeur[0]}", PRIORITE_HAUTE)
    for b in c.boucles:
        for rep_ in (f"VIV{b}", f"VIV{b}_BP"):
            c.vannes[rep_].fixer_ordre(FERMEE if e.isolement_vapeur else None, "isolement vapeur")

    # --- pression enceinte très haute : aspersion (EAS) + phase B (isole le RRI des pompes primaires) ---
    if c.enceinte.p_rel_bar > cfg.logique.p_enceinte_tres_haute_bar_rel and not e.phase_b:
        e.phase_b = True
        journal.ajouter(t, "automatisme", "Pression enceinte très haute : aspersion EAS + isolement phase B", PRIORITE_HAUTE)
    if e.phase_b:
        for p in c.ris.pompes_eas:
            if not p.etat.en_marche and not p.etat.defaut and c.sources(p).electricite_ok:
                p.demarrer()

    # --- recirculation : PTR à 48 % → arrêt des pompes RRA ; à 17 % → arrêt de l'aspersion ---
    if not c.ris.recirculation:
        if rcv.niveau_ptr_pct < cfg.ris.ptr_recirculation_pct:
            for p in c.ris.pompes_bp:
                if p.etat.en_marche and not any(c.rra.aspiration_ouverte(i) for i in range(len(c.rra.pompes))):
                    p.declencher("PTR basse : passer en recirculation")
                    journal.ajouter(t, "automatisme", f"Arrêt {p.id} : PTR à 48 %", PRIORITE_HAUTE)
        if rcv.niveau_ptr_pct < cfg.ris.ptr_tres_bas_pct:
            for p in c.ris.pompes_eas:
                if p.etat.en_marche:
                    p.declencher("PTR très basse : aspersion sur les puisards")

    # --- VCT : bascule de l'aspiration sur la PTR (niveau très bas ou IS) ; retour manuel (les vannes
    #     restent en place quand l'ordre disparaît) ; déviation vers les effluents sur niveau haut ---
    sv = cfg.rcv.vct_seuils_pct
    niveau = rcv.niveau_vct_pct
    if (niveau < sv.tres_bas or e.is_actif) and not e.aspiration_ptr:
        e.aspiration_ptr = True
        journal.ajouter(t, "automatisme", "Aspiration des pompes de charge basculée sur la PTR", PRIORITE_HAUTE)
    elif e.aspiration_ptr and niveau > sv.bas and not e.is_actif:
        e.aspiration_ptr = False
    raison = "IS" if e.is_actif else "niveau VCT très bas"
    rcv.asp_ptr.fixer_ordre(OUVERTE if e.aspiration_ptr else None, raison)
    rcv.asp_vct.fixer_ordre(FERMEE if e.aspiration_ptr else None, raison)
    if niveau > sv.haut:
        e.deviation_vct = True
    elif niveau < sv.haut - (sv.haut - sv.bas) / 4:
        e.deviation_vct = False
    if e.deviation_vct:
        rcv.deviation.fixer_ordre(OUVERTE, "niveau VCT haut")
    elif rcv.deviation.etat.ordre == OUVERTE:
        rcv.deviation.fixer_ordre(FERMEE, "niveau VCT revenu")     # refermée (mémorisé), puis plus d'ordre
    else:
        rcv.deviation.fixer_ordre(None)

    # --- décharge : niveau PZR bas (LCV-459/460 + orifices), pas de pompe de charge (orifices) ---
    niveau_bas = c.pzr.capteur_niveau.mediane < cfg.pressuriseur.niveau_bas_pct
    if niveau_bas and not e.decharge_isolee:
        journal.ajouter(t, "automatisme", "Niveau PZR bas : décharge isolée, chaufferettes coupées", PRIORITE_HAUTE)
    e.decharge_isolee = niveau_bas
    for v in rcv.lcv:
        v.fixer_ordre(FERMEE if niveau_bas else None, "niveau PZR bas")
    sans_charge = rcv.nb_pompes() == 0
    for v in rcv.orifices:
        if niveau_bas:
            v.fixer_ordre(FERMEE, "niveau PZR bas")
        elif sans_charge:
            v.fixer_ordre(FERMEE, "aucune pompe de charge")
        else:
            v.fixer_ordre(None)
    for ch in (c.pzr.chauffe_prop, c.pzr.chauffe_tor):
        ch.etat.coupe = "niveau PZR bas" if niveau_bas else ""

    # --- accumulateurs : rouverts au-dessus de P-11 et sur IS ---
    for v in c.accus.isolement:
        if e.is_actif:
            v.fixer_ordre(OUVERTE, "IS")
        elif not e.p11:
            v.fixer_ordre(OUVERTE, "P > P-11")
        else:
            v.fixer_ordre(None)

    # --- RRA : aspiration refermée si P > 41 bar ---
    rr = cfg.rra
    if p_pzr > rr.p_fermeture_auto_bar:
        ouvertes = [v for v in c.rra.vannes_aspiration() if v.etat.position > 0.0 or v.etat.demande_manu > 0.0]
        if ouvertes and not e.rra_isole_auto:
            e.rra_isole_auto = True
            journal.ajouter(t, "automatisme", f"Aspiration RRA fermée : P > {rr.p_fermeture_auto_bar:g} bar",
                            PRIORITE_HAUTE)
        for v in c.rra.vannes_aspiration():
            v.fixer_ordre(FERMEE, f"P primaire > {rr.p_fermeture_auto_bar:g} bar")
    else:
        for v in c.rra.vannes_aspiration():
            v.fixer_ordre(None)
        if p_pzr < rr.p_ouverture_max_bar:
            e.rra_isole_auto = False

    # --- RRI perdu : les pompes primaires perdent leur refroidissement ---
    pp_en_marche = [p for p in c.primaire.pompes if p.etat.en_marche]
    e.perte_rri = bool(pp_en_marche) and (not c.rri.disponible() or e.phase_b)
    if e.perte_rri:
        c.rri.etat.sans_rri_s += dt
        if c.rri.etat.sans_rri_s > cfg.rri.delai_pompes_primaires_s:
            for p in pp_en_marche:
                p.declencher("perte RRI (paliers / barrière thermique)")
                journal.ajouter(t, "automatisme", f"Défaut {p.id} : perte du RRI", PRIORITE_HAUTE)
    else:
        c.rri.etat.sans_rri_s = 0.0
