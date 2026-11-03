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
    if not e.is_bloquee:
        if vote(votes, capteur.depasse(isc.p_pzr_basse_bar, au_dessus=False)):
            causes.append(f"pression PZR < {isc.p_pzr_basse_bar:g} bar")
        for gv in c.gvs:
            if gv.p_bar < isc.p_vapeur_basse_bar:
                causes.append(f"pression vapeur GV{gv.b} < {isc.p_vapeur_basse_bar:g} bar")
    if e.is_manuel:
        causes = ["manuelle"] + causes
        e.is_manuel = False
    e.causes_is = causes
    if causes and not e.is_actif:
        e.is_actif = True
        e.is_causes = list(causes)
        e.is_t_s = c.t_s
        c.journal.ajouter(c.t_s, "automatisme", f"INJECTION DE SÉCURITÉ : {', '.join(causes)}", PRIORITE_HAUTE)


def appliquer_automatismes_v2(c: Centrale, e: EtatLogique, dt: float) -> None:
    journal, t = c.journal, c.t_s
    cfg = c.cfg
    rcv = c.rcv
    p_pzr = c.pzr.capteur_p.mediane

    # --- IS : ordres ---
    if e.is_actif:
        e.isolement_are_complet = True
        for p in c.asg.motopompes + rcv.pompes:
            if not p.etat.en_marche:
                p.demarrer()
                journal.ajouter(t, "automatisme", f"Démarrage {p.id} (IS)", PRIORITE_MOYENNE)
    raison_is = "IS (phase A)"
    rcv.isol_enc.fixer_ordre(FERMEE if e.is_actif else None, raison_is)
    rcv.isol_charge.fixer_ordre(FERMEE if e.is_actif else None, "IS")

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
    e.perte_rri = bool(pp_en_marche) and not c.rri.disponible()
    if e.perte_rri:
        c.rri.etat.sans_rri_s += dt
        if c.rri.etat.sans_rri_s > cfg.rri.delai_pompes_primaires_s:
            for p in pp_en_marche:
                p.declencher("perte RRI (paliers / barrière thermique)")
                journal.ajouter(t, "automatisme", f"Défaut {p.id} : perte du RRI", PRIORITE_HAUTE)
    else:
        c.rri.etat.sans_rri_s = 0.0
