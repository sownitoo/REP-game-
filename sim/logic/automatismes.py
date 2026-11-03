"""Automatismes : déclenchements (turbine, APP, CEX), isolement eau alimentaire,
contournement (C-9, P-12, armements C-7/C-8), démarrage ASG, isolement de la décharge
et coupure des chaufferettes sur niveau PZR bas, runback turbine (C-3/C-4),
recirculation débit mini des CEX.

Les ordres sont posés sur les vannes (`fixer_ordre`) : ils priment sur l'opérateur
et la régulation, et la raison est affichée dans l'interface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sim.core.events import PRIORITE_HAUTE, PRIORITE_MOYENNE
from sim.units import POURCENT

if TYPE_CHECKING:
    from sim.logic.protection import EtatLogique
    from sim.plant import Centrale

FERMEE = 0.0
OUVERTE = 1.0


def causes_turbine_presentes(c: Centrale, e: EtatLogique) -> list[str]:
    lg = c.cfg.logique.declenchement_turbine
    causes = []
    if e.p4:
        causes.append("P-4 (AU)")
    if e.p14:
        causes.append("P-14 niveau GV très haut")
    if c.condenseur.etat.p_bar > lg.p_cond_max_bar:
        causes.append(f"vide condenseur dégradé (> {lg.p_cond_max_bar} bar)")
    if c.turbine.etat.vitesse_tr_min > lg.survitesse_pct / POURCENT * c.cfg.turbine.vitesse_nom_tr_min:
        causes.append("survitesse")
    return causes


def appliquer_automatismes(c: Centrale, e: EtatLogique, dt: float) -> None:
    journal, t = c.journal, c.t_s
    lg = c.cfg.logique

    # --- turbine ---
    e.causes_turbine = causes_turbine_presentes(c, e)
    if e.causes_turbine and not c.turbine.etat.declenchee:
        c.turbine.declencher(e.causes_turbine[0])
        journal.ajouter(t, "automatisme", f"Déclenchement turbine : {e.causes_turbine[0]}", PRIORITE_HAUTE)

    # --- isolement eau alimentaire ---
    if e.p14 and not e.isolement_are_complet:
        e.isolement_are_complet = True
        journal.ajouter(t, "automatisme", "Isolement ARE complet (P-14)", PRIORITE_HAUTE)
    au_tmoy_bas = e.au and c.primaire.tmoy_c < lg.isolement_are_au.tmoy_max_c
    if au_tmoy_bas and not e.isolement_are_au:
        journal.ajouter(t, "automatisme", "Isolement ARE grand débit (P-4 et Tmoy basse)", PRIORITE_MOYENNE)
    e.isolement_are_au = au_tmoy_bas
    for b in c.boucles:
        gd, pd, isol = (c.vannes[f"ARE{b}_GD"], c.vannes[f"ARE{b}_PD"], c.vannes[f"ARE{b}_ISOL"])
        if e.isolement_are_complet:
            for v in (gd, pd, isol):
                v.fixer_ordre(FERMEE, "isolement ARE (P-14)")
        else:
            pd.fixer_ordre(None)
            isol.fixer_ordre(None)
            if e.isolement_are_au:
                gd.fixer_ordre(FERMEE, "isolement ARE (P-4 et Tmoy < seuil)")
            else:
                gd.fixer_ordre(None)

    # --- pompes alimentaires ---
    dap = lg.declenchement_app
    p_asp, p_ref = c.poste_eau.p("N_ABP"), c.poste_eau.p("N_APP")
    e.app_declenchee = False
    for i, app in enumerate(c.apps):
        if not app.etat.en_marche:
            e.tempo_aspiration_app_s[i] = 0.0
        else:
            e.tempo_aspiration_app_s[i] = e.tempo_aspiration_app_s[i] + dt if p_asp < dap.p_aspiration_min_bar else 0.0
            cause = None
            if e.p14:
                cause = "P-14 niveau GV très haut"
            elif e.tempo_aspiration_app_s[i] > dap.temporisation_s:
                cause = "pression d'aspiration basse"
            elif p_ref > dap.p_refoulement_max_bar:
                cause = "pression de refoulement haute"
            if cause:
                app.declencher(cause)
                journal.ajouter(t, "automatisme", f"Déclenchement {app.id} : {cause}", PRIORITE_HAUTE)
        e.app_declenchee = e.app_declenchee or bool(app.etat.defaut)

    # --- pompes d'extraction ---
    e.cex_declenchee = False
    niveau_puits = c.condenseur.niveau_puits_pct()
    for cex in c.cexs:
        if cex.etat.en_marche and niveau_puits < lg.declenchement_cex.niveau_puits_min_pct:
            cex.declencher("niveau puits très bas")
            journal.ajouter(t, "automatisme", f"Déclenchement {cex.id} : niveau puits très bas", PRIORITE_HAUTE)
        e.cex_declenchee = e.cex_declenchee or bool(cex.etat.defaut)

    # --- contournement : interdit sans C-9 ; sous P-12, seul le groupe « refroidissement » ---
    c.gct.mettre_a_jour_armements(dt, c.turbine.charge_pct, c.turbine.etat.declenchee)
    autorises = c.cfg.gct_c.p12.groupes_autorises
    for i, v in enumerate(c.gct.groupes):
        if not e.c9:
            v.fixer_ordre(FERMEE, "C-9 absent (condenseur indisponible)")
        elif e.p12 and i >= autorises:
            v.fixer_ordre(FERMEE, "P-12 : Tmoy très basse")
        else:
            v.fixer_ordre(None)

    # --- ASG : démarrage sur niveau GV très bas ou perte des 2 APP ---
    app_en_service = any(a.etat.en_marche for a in c.apps)
    perte_app = e.app_en_service and not app_en_service
    e.app_en_service = app_en_service
    niveau_tres_bas = any(e.niveau_tres_bas_gv)
    if niveau_tres_bas or perte_app:
        cause = "niveau GV très bas" if niveau_tres_bas else "perte des 2 APP"
        for p in c.asg.motopompes:
            if not p.etat.en_marche:
                p.demarrer()
                journal.ajouter(t, "automatisme", f"Démarrage {p.id} ({cause})", PRIORITE_MOYENNE)
        if niveau_tres_bas and not c.asg.turbopompe.etat.en_marche:
            c.asg.vanne_vapeur.demander(OUVERTE)
            c.asg.turbopompe.demarrer()
            journal.ajouter(t, "automatisme", f"Démarrage ASG_TP ({cause})", PRIORITE_MOYENNE)

    # --- PZR : niveau bas → isolement de la décharge + chaufferettes coupées (spec : 17 %) ---
    niveau_bas = c.pzr.capteur_niveau.mediane < c.cfg.pressuriseur.niveau_bas_pct
    if niveau_bas and not e.decharge_isolee:
        journal.ajouter(t, "automatisme", "Niveau PZR bas : décharge isolée, chaufferettes coupées", PRIORITE_HAUTE)
    e.decharge_isolee = niveau_bas
    c.vannes["RCV_DECHARGE"].fixer_ordre(FERMEE if niveau_bas else None, "niveau PZR bas")
    for ch in (c.pzr.chauffe_prop, c.pzr.chauffe_tor):
        ch.etat.coupe = "niveau PZR bas" if niveau_bas else ""

    # --- préalarmes ΔT (C-3 / C-4) : runback turbine ---
    m_ot, m_op = c.logique.marges_dt_pct()
    e.c3 = m_ot < lg.otdt.prealarme_pct
    e.c4 = m_op < lg.opdt.prealarme_pct
    if (e.c3 or e.c4) and not c.turbine.etat.declenchee:
        c.turbine.runback(dt)

    # --- recirculation débit mini CEX ---
    rc = c.cfg.regulations.cex_recirculation
    debit = c.poste_eau.debit_cex_m3h(c.condenseur.rho_puits_kg_m3)
    if debit < rc.ouvre_m3h:
        e.recirc_cex = True
    elif debit > rc.ferme_m3h:
        e.recirc_cex = False
    c.vannes["CEX_RECIRC"].fixer_ordre(OUVERTE if e.recirc_cex else FERMEE, "débit mini CEX")
