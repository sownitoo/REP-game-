# Proposition V0 — à valider avant de coder

> Référence : `SPEC_simulateur_REP.md` (§10, ligne V0).
> V0 = moteur générique + **boucle secondaire seule** (GV chauffés par une source imposée → VVP → turbine → condenseur → CEX → APP → ARE) + UI avec 1 synoptique.

---

## 1. Périmètre V0

| Dans la V0 | Hors V0 (version prévue) |
|---|---|
| 4 GV côté secondaire, gonflement / tassement | Primaire 4 boucles, PZR, cœur neutronique (V1) |
| Source de chaleur imposée **1 nœud** (remplace primaire + cœur) | RCV, REA, RRA, RRI, SEC (V2) |
| VVP : lignes, VIV, VDA (GCT-a), 5 soupapes / ligne, collecteur | Électricité réelle, diesels, air comprimé (V3) — *stubs en V0* |
| Turbine (vannes d'arrêt/réglage, vitesse, couplage), soutirages | ASG (voir §7, point 2) |
| GCT-c (mode pression) + C-9 | GCT-c mode Tmoy, C-7, C-8, P-12 (V1) |
| Condenseur + CRF + puits + CST | CVI (éjecteurs) : vide supposé maintenu |
| CEX (+ recirculation débit mini), ABP, pompes de reprise, APP, AHP, ARE GD/PD + isolement | Déminéraliseurs condensat, injection chimique |
| Logique V0 : AU (manuel, niveau GV très bas, déclenchement turbine), P-4, P-7, P-14, C-9, isolement ARE, déclenchements APP/turbine | IS, isolements enceinte, isolement vapeur auto (V4) |
| UI : barre du haut, synoptique « Secondaire », onglet Logique, panneau équipement (✓/✗ + raison), alarmes, courbes, accélération, sauvegarde/chargement | Score, débrief (V5) |

---

## 2. Arborescence

```
REP-game-/
├── SPEC_simulateur_REP.md
├── README.md                    # lancement en 1 commande
├── CHANGELOG.md
├── requirements.txt             # numpy, CoolProp, pyyaml, fastapi, uvicorn, pytest, httpx
├── pyproject.toml               # config pytest
├── config/
│   └── plant.yaml               # TOUTES les valeurs numériques
├── sim/
│   ├── server.py                # FastAPI + WebSocket  →  python -m sim.server
│   ├── config.py                # YAML → dataclasses typées + validation des références
│   ├── units.py                 # constantes physiques/conversions (g, 273,15, bar→Pa) — pas de valeurs centrale
│   ├── core/
│   │   ├── engine.py            # boucle de calcul (8 étapes du §2.3), horloge, accélération
│   │   ├── network.py           # solveur réseau hydraulique quasi statique (Newton sur les nœuds)
│   │   ├── commands.py          # file d'actions joueur + conditions ✓/✗ avec raisons
│   │   ├── events.py            # journal horodaté + alarmes (priorité, acquittement)
│   │   ├── history.py           # ring buffer pour les courbes
│   │   └── snapshot.py          # état complet ⇄ JSON (sauvegarde / chargement)
│   ├── components/
│   │   ├── base.py              # Component : id, system, power_supply, air_supply, fail_position
│   │   ├── pump.py              # Pump (centrifuge, similitude, inertie)
│   │   ├── valve.py             # Valve MOV / AOV, ControlValve, CheckValve
│   │   ├── relief.py            # ReliefValve / SafetyValve (hystérésis)
│   │   ├── tank.py              # Tank (puits, CST)
│   │   ├── volume2phase.py      # Volume2Phase (GV ; puis PZR, PRT en V1+)
│   │   ├── sensor.py            # Sensor multi-voies (panne = valeur figée)
│   │   └── pid.py               # PI/PID auto ⇄ manu sans à-coup
│   ├── thermo/
│   │   ├── tables.py            # tables de saturation pré-calculées avec CoolProp
│   │   └── water.py             # tsat_c(p_bar), hf/hg, ρ, flash (v, u) → p_bar
│   ├── systems/
│   │   ├── source_v0.py         # source de chaleur imposée (supprimée en V1)
│   │   ├── gv.py                # 4 GV côté secondaire + niveau GE
│   │   ├── vvp.py               # lignes vapeur, VIV, VDA, soupapes, collecteur
│   │   ├── turbine.py           # GRE : vannes, vitesse, alternateur, soutirages
│   │   ├── gct.py               # contournement condenseur (GCT-c)
│   │   ├── condenseur.py        # condenseur, CRF, puits, CST
│   │   └── poste_eau.py         # CEX, ABP, reprise, APP, AHP, ARE
│   ├── logic/
│   │   ├── voting.py            # votes 1/2, 2/3, 2/4
│   │   ├── permissives.py       # P-4, P-7, P-14, C-9 (V0)
│   │   ├── protection.py        # AU
│   │   ├── automatismes.py      # isolement ARE, déclenchements APP / turbine
│   │   ├── regulations.py       # niveau GV 3 éléments, ΔP APP, charge turbine, GCT-c, VDA, puits
│   │   └── interlocks.py        # conditions de manœuvre par commande (avec raisons)
│   ├── core_model/              # vide en V0 (cœur boîte noire en V1)
│   ├── electrical/              # stub V0 : tous les tableaux sous tension
│   ├── scenarios/
│   │   └── s0_bac_a_sable_100.yaml
│   └── scoring/                 # V5
├── web/
│   ├── index.html
│   ├── app.js                   # WebSocket, onglets, panneau équipement, alarmes
│   ├── curves.js                # courbes canvas (1 à 6 variables, fenêtre glissante)
│   ├── style.css
│   └── synoptics/
│       └── secondaire.svg       # éléments repérés par data-id = repère du composant
└── tests/
    ├── unit/
    └── integration/
```

Repères : trigramme EDF + n° de boucle (`ARE1_GD`, `VIV2`, `APP1`, `GCTC_G3`), repères NRC conservés quand la spec les donne (`PCV-131`, `LCV-459`… en V2).

---

## 3. Choix de modélisation V0

| Bloc | Modèle | Pourquoi |
|---|---|---|
| **Source V0** | 1 nœud primaire : `C·dTmoy/dt = P_source − Σ Q_GV` ; `Q_GV = UA·(Tmoy − Tsat(P_GV))` (§9.3). `P_source` en **auto** (suit `Tref(charge)` à vitesse limitée → émule les grappes) ou **manu**. AU → puissance résiduelle Way-Wigner (§4.16). | Le couplage P_GV ↔ Tmoy est déjà le bon ; en V1 on remplace juste ce nœud par le primaire. |
| **GV** | Masse `m` et énergie `U` conservées → `P` par flash saturé sur tables. Niveau GE = `(V_liq + k·V_bulles − V_bas) / V_plage`. `V_bulles` → 1ᵉʳ ordre vers `τ_séjour · ṁ_vaporisé / ρ_v`, où `ṁ_vaporisé` inclut le sous-refroidissement de l'eau alimentaire **et** la vaporisation éclair (−dP/dt). | Gonflement / tassement **émergent** de la physique, sans fonction de transfert plaquée. Le terme bulles n'affecte que la mesure de niveau → conservation masse/énergie exacte. |
| **Réseaux liquides** | Quasi statique. Tous les éléments sont quadratiques : pompe `H0·s² − k·Q²`, vanne `(Q/Kv)²·d`, tuyau `k·Q²`, clapet `Q ≥ 0`. Débit d'une branche en forme fermée → **Newton sur les pressions des nœuds**. Vannes // : `Kv = ΣKv`. | Générique, rapide (pas d'itération interne), réutilisé tel quel pour RCV/RRA/RIS. |
| **Collecteur vapeur** | 1 nœud quasi statique. Lignes `ΔP ∝ ṁ²/ρ` ; turbine et GCT-c en débit critique `ṁ = K·y·P`. | Simple, robuste. |
| **Turbine** | `P_méca = η_is · Δh_is(P_adm, P_cond) · ṁ · (1 − f_sout/2)`. Soutirages : fraction `f` → réchauffeurs (T alimentaire = table(charge) + retard) et pompes de reprise. Vitesse + couplage simples. | Le vide dégradé fait perdre des MW ; relance possible après déclenchement. |
| **Condenseur** | Nœud thermique `C·dT/dt = Q_in − ε·ṁ_CRF·cp·(T − T_mer)` ; `P = Psat(T)`. | Perte CRF → perte de vide en quelques secondes, réaliste. |
| **Thermo** | Tables de saturation pré-calculées (CoolProp IAPWS-IF97), interpolation. | Un appel CoolProp coûte ~150 µs : trop lent à ×60. |
| **Élec / air** | Stubs (tout alimenté). Les champs `alim` / `air` sont déjà dans le YAML. | La V3 se branche sans toucher aux composants. |

---

## 4. Point nominal 100 % (calculé avec CoolProp)

| Grandeur | Valeur | Origine |
|---|---|---|
| Puissance source | 3 411 MW | spec (Trojan) |
| P GV / Tsat | 63 bar / 278,8 °C | spec / CoolProp |
| h vapeur − h eau alim (224 °C) | 2 781 − 963 = 1 818 kJ/kg | CoolProp |
| Débit vapeur | 3 411 000 / 1 818 = **1 876 kg/s** (469 par GV) | calcul (spec ~475) |
| UA par GV | 852,75 MW / (307 − 278,8) °C = **30,2 MW/°C** | recalé |
| P GV à 0 % | Psat(292 °C) = **76,6 bar** | CoolProp |
| Δh isentrope turbine (60 → 0,14 bar) | 886 kJ/kg | CoolProp |
| η_is pour 1 150 MWe | 1 150 / (886 × 1 876 × 0,833) = **0,83** | HYPOTHESE calée |
| Chaleur aux réchauffeurs | 1 395 MW | calcul |
| Chaleur au condenseur | 2 267 MW | calcul |
| Débit CRF (ΔT mer 11 °C, T mer 12 °C) | **48 m³/s** | HYPOTHESE |
| Condensat (2/3 du débit, 1/3 par reprise) | **4 560 m³/h** → 2 × 2 280 (CEX nominal 2 500) | cohérent spec |
| Débit APP total (180 °C) | 7 600 m³/h → 2 × 3 800 (APP nominal 4 500) | cohérent spec |
| Débit ARE par GV (224 °C) | 2 010 m³/h | calcul |
| Volume de bulles par GV à 100 % | 1,5 s × 469 / 32,5 = **21,6 m³** | HYPOTHESE τ |

Bilan énergie : 1 150 (méca) + 2 267 (condenseur) = 3 417 MW ≈ 3 411 MW (écart 0,2 %, laminage vapeur).

---

## 5. Schéma de `config/plant.yaml` (extrait V0)

Règles : unités dans les clés, `# HYPOTHESE` sur toute valeur absente de la spec, `par_boucle: true` duplique un composant pour b = 1..4 (`{b}` dans le repère).

```yaml
# config/plant.yaml — SEULE source des valeurs numériques du simulateur.
# Unités dans les clés : _bar (abs), _c, _m3h, _kg_s, _m3, _mw, _s, _pct.

meta: {version: V0, nom: "Mini-Centrale REP 4 boucles (générique)"}

simulation:
  dt_s: 0.1
  accelerations: [1, 10, 60, 600]
  historique_duree_s: 3600        # HYPOTHESE fenêtre des courbes
  historique_pas_s: 1.0           # HYPOTHESE
  p_atm_bar: 1.013

thermo:
  table_p_min_bar: 0.006
  table_p_max_bar: 220.0
  table_nb_points: 3000           # HYPOTHESE (erreur < 0,05 % vs CoolProp)

# --- V0 uniquement : remplace primaire + cœur (supprimé en V1)
source_v0:
  p_nom_mw: 3411
  capacite_thermique_mj_c: 1600   # HYPOTHESE eau primaire + métal
  tref_programme_c: [[0, 292.0], [100, 307.0]]   # charge turbine % → Tref
  mode_initial: auto              # auto = suit Tref (émule grappes) | manu
  gain_mw_c: 150                  # HYPOTHESE
  vitesse_max_pct_min: 5.0        # HYPOTHESE
  residuelle: {a: 0.0622, b: 0.2, t_fonct_s: 3.0e7}   # Way-Wigner ; t_fonct HYPOTHESE (~1 an)

generateurs_vapeur:
  boucles: [1, 2, 3, 4]
  ua_mw_c: 30.2                   # recalé : 852,75 MW / 28,2 °C
  v_secondaire_m3: 165            # HYPOTHESE
  niveau_ge:
    v_bas_m3: 46.7                # HYPOTHESE → ~42 t d'eau à 100 % et 50 % GE
    v_plage_m3: 40.0              # HYPOTHESE (≈ 11 m² × 3,6 m)
    k_bulles: 0.5                 # HYPOTHESE calé : tassement ≈ −20 %GE sur déclenchement turbine
    tau_sejour_s: 1.5             # HYPOTHESE temps de séjour des bulles
    tau_bulles_s: 2.0             # HYPOTHESE
    voies: 3
    retard_mesure_s: 0.5          # HYPOTHESE
  programme_niveau_pct: [[0, 50.0], [100, 50.0]]   # HYPOTHESE
  seuils:
    tres_bas_pct: 11.5            # AU, 2/3 sur 1 GV
    tres_haut_pct: 69.0           # P-14

gabarits:                         # modèles partagés par plusieurs composants
  pompe_cex:
    type: Pump
    q_nom_m3h: 2500
    h_nom_m: 340
    h0_m: 400                     # HYPOTHESE
    temps_demarrage_s: 5          # HYPOTHESE
    temps_ralentissement_s: 10    # HYPOTHESE
  vanne_are_gd:
    type: ControlValve
    actionneur: AOV
    kv_max: 1080                  # HYPOTHESE (2 010 m³/h à ~70 % sous 6 bar)
    caracteristique: lineaire
    temps_course_s: 10            # HYPOTHESE
    position_repli: fermee
  soupape_vvp:
    type: SafetyValve
    capacite_kg_s: 102            # 109 % × 1 876 kg/s / 20 soupapes
    fermeture_pct: 4              # HYPOTHESE (blowdown)

composants:
  CEX1:        {gabarit: pompe_cex, systeme: CEX, alim: LGA}
  CEX2:        {gabarit: pompe_cex, systeme: CEX, alim: LGB}
  CEX_RECIRC:  {type: Valve, systeme: CEX, actionneur: AOV, kv_max: 400,   # kv HYPOTHESE
                debit_mini: {ouvre_m3h: 795, ferme_m3h: 1590}}
  APP1:        {type: Pump, systeme: APP, entrainement: turbine_vapeur,
                q_nom_m3h: 4500, h_nom_m: 520, h0_m: 650,                   # h HYPOTHESE
                vitesse_max_pct: 110}                                      # HYPOTHESE
  ARE{b}_GD:   {gabarit: vanne_are_gd, systeme: ARE, par_boucle: true, air: SAR}
  ARE{b}_ISOL: {type: Valve, systeme: ARE, actionneur: MOV, par_boucle: true,
                temps_course_s: 16, alim: LHA}
  VIV{b}:      {type: Valve, systeme: VVP, actionneur: AOV, par_boucle: true,
                temps_fermeture_s: 5.0, retard_s: 0.5, reserve_air_min: 15,
                position_repli: fermee}
  VDA{b}:      {type: ControlValve, systeme: VVP, par_boucle: true,
                capacite_kg_s: 47, secours: azote}                         # 10 % du débit d'un GV
  SOUP{b}_{n}: {gabarit: soupape_vvp, par_boucle: true,
                tarages_bar: [82, 83, 84, 85, 86]}                         # 1 soupape par tarage

reseaux:                          # topologie des circuits liquides (liaisons)
  eau_alimentaire:
    frontieres: [PUITS, CONDENSEUR, GV1, GV2, GV3, GV4]   # pression imposée par un volume
    noeuds: [N_CEX, N_ABP, N_APP, N_ARE]
    injections: [{noeud: N_ABP, source: REPRISE}]         # pompes de reprise des purges
    branches:
      - {id: L_CEX1,   de: PUITS, vers: N_CEX, elements: [CEX1, CEX1_CLAPET]}
      - {id: L_CEX2,   de: PUITS, vers: N_CEX, elements: [CEX2, CEX2_CLAPET]}
      - {id: L_RECIRC, de: N_CEX, vers: CONDENSEUR, elements: [CEX_RECIRC]}
      - {id: L_ABP,    de: N_CEX, vers: N_ABP, elements: [ABP]}   # ΔP 5 bar à 100 % (HYPOTHESE)
      - {id: L_APP1,   de: N_ABP, vers: N_APP, elements: [APP1, APP1_CLAPET]}
      - {id: L_APP2,   de: N_ABP, vers: N_APP, elements: [APP2, APP2_CLAPET]}
      - {id: L_APD,    de: N_ABP, vers: N_APP, elements: [APD, APD_CLAPET]}  # pompe de démarrage
      - {id: L_AHP,    de: N_APP, vers: N_ARE, elements: [AHP]}
      - {id: L_ARE{b}, de: N_ARE, vers: GV{b}, par_boucle: true,
         elements: [ARE{b}_ISOL, [ARE{b}_GD, ARE{b}_PD], ARE{b}_CLAPET]}   # [x, y] = en parallèle

regulations:
  niveau_gv:      {kp: 4.0, ti_s: 60, anticipation_debits: true, mode: auto}   # HYPOTHESE réglages
  dp_app:         {consigne_bar: [[0, 4.0], [100, 10.0]], kp: 2.0, ti_s: 20}   # HYPOTHESE
  charge_turbine: {rampe_pct_min: 5.0, echelon_max_pct: 10.0}
  gct_c:          {mode: pression, consigne_bar: 76.0, bande_bar: 3.0}         # HYPOTHESE
  vda:            {consigne_bar: 79.0, bande_bar: 2.0}                         # bande HYPOTHESE
  puits:          {consigne_pct: 50, appoint_max_m3h: 200, rejet_max_m3h: 200} # HYPOTHESE

logique:
  P-7:  {puissance_max_pct: 10, charge_turbine_max_pct: 10}
  P-14: {niveau_gv_pct: 69.0}
  C-9:  {p_cond_max_bar: 0.17, p_cond_perte_bar: 0.26, crf_mini: 1}
  isolement_are_sur_au: {tmoy_max_c: 296.0, ferme: [ARE{b}_GD]}               # PD reste dispo
  isolement_are_complet: {ferme: [ARE{b}_GD, ARE{b}_PD, ARE{b}_ISOL]}         # P-14
  declenchement_app: {p_aspiration_min_bar: 14.5, p_refoulement_max_bar: 128.0}
  declenchement_turbine: {p_cond_max_bar: 0.30, survitesse_pct: 110}           # HYPOTHESE

alarmes:
  - {id: GV{b}_NIV_BAS,  mesure: "GV{b}.niveau_pct", bas: 40.0, priorite: 2}   # HYPOTHESE
  - {id: COND_VIDE,      mesure: "CONDENSEUR.p_bar", haut: 0.17, priorite: 1}
```

La V0 complète fera ~300 lignes (mêmes motifs pour CRF, CST, puits, turbine, GCT-c, AHP, APD…).

---

## 6. Tests d'acceptation

### Tests unitaires (`tests/unit/`)

| # | Test | Critère |
|---|---|---|
| U1 | Tables thermo vs CoolProp | Tsat, hf, hg, ρ : écart < 0,05 % sur 0,01–200 bar |
| U2 | Flash (v, u) → P | aller-retour P → (v, u) → P : écart < 0,01 bar |
| U3 | Pompe | H(0) = H0·s², point nominal respecté, similitude, ralentissement sans moteur |
| U4 | Vannes | MOV : temps de course, reste en place sans tension ; AOV : repli sur perte d'air (sauf réserve) ; clapet : pas de débit inverse |
| U5 | Soupape | ouvre au tarage, referme à tarage − blowdown |
| U6 | Réseau | 2 pompes // + résistance : débit = solution analytique (< 0,1 %) ; Σ débits aux nœuds < 1e-6 |
| U7 | Volume2Phase | GV fermé chauffé : P suit Psat ; masse et énergie conservées |
| U8 | PI | auto ⇄ manu sans à-coup, anti-emballement |
| U9 | Logique | votes 2/3 et 2/4 ; signal bloqué réactivé dès la perte du permissif |
| U10 | Verrous | tout refus renvoie ≥ 1 raison lisible |
| U11 | Config | YAML valide, toutes les références existent, littéraux numériques dans `sim/` limités à une liste blanche |

### Tests d'intégration V0 (`tests/integration/`)

| # | Situation | Critère de réussite |
|---|---|---|
| A1 | **Équilibre 100 %**, 30 min sans action | P GV 63 ± 0,5 bar ; niveaux 50 ± 2 % ; P élec dérive < 0,5 % ; aucune alarme ; pas d'AU |
| A2 | Bilan énergie à l'équilibre | \|P_source − (P_méca + Q_mer)\| < 1 % |
| A3 | Masse en circuit fermé (VDA/soupapes fermées) | dérive < 0,1 %/h sur 1 h simulée |
| A4 | **Fermeture ARE GV1** (GD en manu → 0 %) | gonflement initial ≥ +1 %GE dans les 5 s, puis baisse ; AU niveau très bas (2/3) entre 10 et 60 s ; débits vapeur GV2-4 ↑ |
| A5 | Échelon de charge −10 % (100 → 90 %) | **tassement** initial ; retour consigne ± 2 % en < 5 min ; ni AU ni soupape |
| A6 | Échelon de charge +10 % (90 → 100 %) | **gonflement** initial ; retour consigne ; pas d'AU |
| A7 | Ouverture ARE GV1 +20 % (manu) | tassement initial (eau froide) puis montée du niveau |
| A8 | Déclenchement turbine à 100 % | AU < 1 s ; GCT-c ouvert ; soupapes VVP non sollicitées ; isolement ARE GD (AU + Tmoy < 296 °C) ; à 10 min : P GV 76 ± 1 bar, niveaux 30–60 % |
| A9 | Perte des 2 CRF | C-9 perdu à 0,26 bar ; déclenchement turbine sur vide → AU ; GCT-c bloqué ; VDA prennent le relais |
| A10 | Verrous | GCT-c sans C-9, APP sans aspiration, couplage hors synchro, réarmement turbine avec P-14 présent : **refusés + raison** |
| A11 | Sauvegarde / chargement | save → 60 s → état S ; load → 60 s → état identique (déterministe) |
| A12 | Serveur | `python -m sim.server` répond ; WebSocket : état diffusé, commande acceptée ou refusée avec raison |
| A13 | Performance | ≥ 600 pas/s (×60 tenu en temps réel) |

---

## 7. Points à valider / écarts relevés dans la spec

1. **Source V0** : 1 nœud primaire avec mode auto « suit Tref » (émule les grappes) — sinon une baisse de charge turbine n'a pas de retour vers la source et la pression part aux soupapes.
2. **ASG absente de la feuille de route §10**, alors que S4, S5 et S6 en ont besoin (S5/S6 attendus en V3). Proposition : ASG en V1. En V0, après AU, l'alimentation continue par ARE petit débit + APP.
3. **Pompes de reprise des purges dès la V0** : sans elles, 2 CEX × 2 500 m³/h ne passent pas 100 % (il faut 4 560 m³/h pour 2/3 du débit, 6 840 pour la totalité).
4. **P GV à 0 %** : Psat(292 °C) = 76,6 bar → baisse de 13,6 bar entre 0 et 100 % (spec : « ~10 bar »). Je garde le programme Tmoy 292 → 307 °C, plus structurant.
5. **×600** : pas garanti en Python pur quand toute la centrale sera modélisée (V4). L'UI affiche l'accélération réellement tenue.
6. **Turbine** : vitesse + couplage simples dès la V0, pour pouvoir relancer après un déclenchement.
7. **Électricité / air** : stubs en V0, les champs `alim` / `air` sont déjà renseignés.

Lancement prévu : `pip install -r requirements.txt && python -m sim.server` → http://localhost:8000
