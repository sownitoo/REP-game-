# Hypothèses (valeurs absentes de la spec)

Générée par `python -m sim.tools.hypotheses` depuis `config/plant.yaml`.

94 valeurs marquées `# HYPOTHESE`.

| Clé | Valeur | Justification |
|---|---|---|
| `simulation.historique_duree_s` | `7200` | fenêtre des courbes (2 h simulées) |
| `simulation.historique_pas_s` | `1.0` | échantillonnage des courbes |
| `simulation.diffusion_periode_s` | `0.25` | période d'envoi de l'état à l'interface (temps réel) |
| `simulation.journal_max` | `2000` | nb d'événements gardés en mémoire |
| `numerique.alarmes_hysteresis_pct` | `1.0` |  |
| `point_nominal.niveau_gv_pct` | `50.0` |  |
| `point_nominal.p_collecteur_bar` | `60.0` | (perte de charge lignes 3 bar) |
| `coeur.residuelle` | `{a: 0.0622, b: 0.2, t_fonctionnement_s: 3.0e+7}` | Way-Wigner ; t_fonct  (~1 an) |
| `source_v0.capacite_thermique_mj_c` | `1600` | eau primaire (~250 t) + métal |
| `source_v0.kp_mw_c` | `100.0` | (≈ contre-réaction modérateur) |
| `source_v0.ti_s` | `120.0` |  |
| `source_v0.vitesse_max_pct_min` | `20.0` | (grappes + contre-réaction modérateur) |
| `source_v0.p_max_pct` | `105.0` |  |
| `generateurs_vapeur.masse_assechement_t` | `8.0` | en dessous, UA réduit (tubes découverts) |
| `generateurs_vapeur.v_secondaire_m3` | `165` |  |
| `generateurs_vapeur.niveau_ge.v_bas_m3` | `46.7` | → ~42 t d'eau à 100 % et 50 % GE |
| `generateurs_vapeur.niveau_ge.v_plage_m3` | `40.0` | (≈ 11 m² × 3,6 m) |
| `generateurs_vapeur.niveau_ge.k_bulles` | `0.6` | calé : tassement ≈ −25 %GE sur déclenchement turbine |
| `generateurs_vapeur.niveau_ge.tau_sejour_s` | `1.5` | temps de séjour des bulles sous le niveau |
| `generateurs_vapeur.niveau_ge.tau_bulles_s` | `1.0` | constante de temps du taux de vide |
| `generateurs_vapeur.niveau_ge.filtre_dpdt_s` | `0.5` | filtrage de dP/dt (vaporisation éclair) |
| `generateurs_vapeur.niveau_ge.retard_mesure_s` | `0.5` |  |
| `generateurs_vapeur.programme_niveau_pct` | `[[0, 50.0], [100, 50.0]]` | (consigne constante) |
| `vapeur.ligne.dp_nom_bar` | `3.0` | perte de charge GV → collecteur à 100 % |
| `vapeur.ligne.fraction_bypass_viv` | `0.02` | capacité du by-pass de VIV |
| `vapeur.soupapes.fermeture_pct` | `4.0` | (blowdown) |
| `turbine.ouverture_nom` | `0.85` | ouverture des vannes de réglage à 100 % |
| `turbine.eta_isentropique` | `0.835` | calée : 1 130 MWe pour 1 876 kg/s |
| `turbine.part_travail_soutirage` | `0.5` | un soutirage fait en moyenne la moitié de la détente |
| `turbine.rendement_alternateur` | `0.985` |  |
| `turbine.p_elec_nom_mw` | `1130` | (résultat du calage) |
| `turbine.constante_inertie_s` | `4.0` | H (énergie cinétique / puissance apparente) |
| `turbine.pertes_ventilation_pct` | `0.5` | à vitesse nominale |
| `turbine.temps_fermeture_arret_s` | `0.3` |  |
| `turbine.temps_ouverture_arret_s` | `10.0` |  |
| `turbine.temps_course_reglage_s` | `2.0` |  |
| `turbine.regulation_charge` | `{rampe_pct_min: 5.0, echelon_max_pct: 10.0, kp: 0.5, ti_s: 5.0}` | rampe/échelon : spec ; PI |
| `turbine.regulation_vitesse` | `{rampe_pct_min: 20.0, kp: 5.0, ti_s: 10.0}` |  |
| `turbine.couplage` | `{ecart_vitesse_max_pct: 0.5}` |  |
| `gct_c.capacite_groupe_kg_s` | `188` | 10 % du débit nominal par groupe (40 % au total) |
| `gct_c.temps_course_s` | `3.0` |  |
| `gct_c.regulation` | `{consigne_bar: 76.0, bande_bar: 3.0}` | mode pression ; |
| `condenseur.t_mer_c` | `12.0` | Manche, moyenne annuelle |
| `condenseur.capacite_thermique_mj_c` | `1000` | (métal + eau du puits) |
| `condenseur.p_incondensables_bar` | `0.005` | (éjecteurs en service) |
| `condenseur.t_max_c` | `105.0` | borne numérique (disques de rupture) |
| `puits.volume_m3` | `300` | (~2 min de débit CEX) |
| `puits.hauteur_m` | `2.0` |  |
| `puits.hauteur_aspiration_m` | `8.0` | charge statique au-dessus des CEX |
| `cst.volume_initial_m3` | `1400` |  |
| `cst.hauteur_m` | `15.0` |  |
| `cst.t_c` | `30.0` | eau déminéralisée stockée à l'extérieur |
| `poste_eau.rechauffeurs.abp_sortie_c` | `[[0, 50.0], [20, 120.0], [50, 160.0], [100, 182.0]]` | spec 49 → 182 °C ; loi en charge |
| `poste_eau.rechauffeurs.ahp_sortie_c` | `[[0, 50.0], [20, 150.0], [50, 195.0], [100, 224.0]]` | spec 182 → 227 °C ; loi en charge |
| `poste_eau.rechauffeurs.tau_s` | `120.0` | inertie thermique des réchauffeurs |
| `poste_eau.reprise.capacite_pompe_pct` | `60.0` | (1 pompe ≈ 90 % de puissance, spec) |
| `poste_eau.reprise.p_plein_debit_bar` | `32.0` | débit max tant que P refoulement < cette valeur |
| `poste_eau.reprise.p_arret_bar` | `45.0` | pression à débit nul (pompe en butée) |
| `gabarits.pompe_cex.h0_m` | `400` |  |
| `gabarits.pompe_cex.temps_demarrage_s` | `5.0` |  |
| `gabarits.pompe_cex.temps_ralentissement_s` | `10.0` |  |
| `gabarits.pompe_app.h_nom_m` | `520` |  |
| `gabarits.pompe_app.h0_m` | `650` |  |
| `gabarits.pompe_app.vitesse_min` | `0.3` |  |
| `gabarits.pompe_app.vitesse_max` | `1.1` |  |
| `gabarits.pompe_app.temps_demarrage_s` | `20.0` |  |
| `gabarits.pompe_app.temps_ralentissement_s` | `15.0` |  |
| `gabarits.pompe_crf.q_nom_m3h` | `86600` | 2 × 50 % (48 m³/s au total) |
| `gabarits.pompe_crf.temps_demarrage_s` | `30.0` |  |
| `gabarits.pompe_crf.temps_ralentissement_s` | `60.0` |  |
| `gabarits.pompe_reprise.q_nom_m3h` | `1360` | 60 % des purges nominales |
| `gabarits.clapet.kv_max` | `8000` | (perte de charge faible) |
| `gabarits.vanne_are_gd.kv_max` | `1080` | (≈ 2 010 m³/h à 56 % sous 6 bar) |
| `gabarits.vanne_are_gd.temps_course_s` | `5.0` |  |
| `gabarits.vanne_are_pd.kv_max` | `160` | (~15 % du débit) |
| `gabarits.vanne_are_pd.temps_course_s` | `10.0` |  |
| `gabarits.vanne_are_isol.kv_max` | `6000` | vanne à passage direct |
| `gabarits.vanne_viv_bypass.temps_course_s` | `20.0` |  |
| `gabarits.vanne_vda.temps_course_s` | `10.0` |  |
| `gabarits.vanne_vda.reserve_air_min` | `30.0` | (secours azote, spec) |
| `composants.CEX_RECIRC` | `{type: Valve, systeme: CEX, actionneur: AOV, air: SAR, kv_max: 150,` | kv  (~900 m³/h) |
| `composants.PUITS_APPOINT` | `{type: ControlValve, systeme: CEX, actionneur: AOV, air: SAR, kv_max: 140,` | ~200 m³/h |
| `composants.PUITS_REJET` | `{type: ControlValve, systeme: CEX, actionneur: AOV, air: SAR, kv_max: 35,` | ~200 m³/h |
| `composants.ABP` | `{type: Resistance, systeme: ABP, dp_nom_bar: 5.0, q_nom_m3h: 4560, rho_nom_kg_m3: 987}` | ΔP réchauffeurs BP |
| `composants.APD` | `{type: Pump, systeme: APP, alim: LHA, q_nom_m3h: 230,` | spec ; hauteurs |
| `composants.AHP` | `{type: Resistance, systeme: AHP, dp_nom_bar: 3.0, q_nom_m3h: 7600, rho_nom_kg_m3: 888}` | ΔP réchauffeurs HP |
| `regulations.niveau_gv` | `` | 3 éléments : niveau + débit vapeur + débit eau ; réglages |
| `regulations.dp_app` | `` | vitesse APP régulée sur ΔP (refoulement ARE − collecteur vapeur) ; |
| `regulations.vda` | `{consigne_bar: 79.0, bande_bar: 2.0}` | tarage spec ; bande |
| `regulations.puits` | `{consigne_pct: 50.0, kp_par_pct: 0.1, ti_s: 600.0}` |  |
| `logique.declenchement_app` | `{p_aspiration_min_bar: 14.5, p_refoulement_max_bar: 128.0, temporisation_s: 2.0}` | tempo |
| `logique.declenchement_turbine` | `{p_cond_max_bar: 0.30, survitesse_pct: 110.0}` |  |
| `logique.declenchement_cex` | `{niveau_puits_min_pct: 10.0}` |  |
| `logique.ouverture_viv` | `{dp_max_bar: 5.0}` | équilibrer par le by-pass avant d'ouvrir une VIV |
