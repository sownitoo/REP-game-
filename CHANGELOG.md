# Changelog

## V4 — 2026-11-03 — RIS, EAS, enceinte, brèches, primaire saturé, tous les signaux de sauvegarde

### Ajouté
- **Injection de sécurité** (`sim/systems/ris.py`) : HP = pompes de charge par la ligne BIT (ouverte sur IS),
  MP = 2 pompes IS (débit nul au-dessus de 106 bar), BP = pompes RRA en injection (sous 14 bar), accumulateurs.
  Aspiration PTR, puis **recirculation** sur les puisards (vannes `RIS_PUISARD1/2`, ouvrables si puisard > 50 m³) :
  PTR < 48 % → arrêt automatique des pompes RRA, PTR < 17 % → arrêt de l'aspersion.
- **Aspersion enceinte (EAS)** : 2 pompes, démarrage + **phase B** (RRI coupé des pompes primaires) sur
  P enceinte > 2,07 bar rel.
- **Enceinte** (`sim/systems/enceinte.py`) : 70 000 m³ d'air + vapeur, parois (béton + acier), puisards, aspersion,
  condensation. **PRT** (bâche de décharge du PZR) : azote + eau, **disque de rupture à 8 bar**.
- **Brèches** (`sim/systems/breches.py`) : primaire (débit critique : sous-refroidi → saturé → vapeur quand les
  joints hydrauliques se vident), **RTGV** avec **activité** de l'eau du GV, **brèche vapeur** (en amont de la VIV),
  PORV bloquée ouverte, grappe la plus efficace coincée, perte du RRI.
- **Primaire saturé** (`sim/systems/pzr.py`) : quand l'eau la plus chaude atteint la saturation, un **vide** se forme
  dans la cuve, **P = Psat(T chaude)**, la vapeur formée prend sa chaleur latente à l'eau ; le PZR est ramené à cette
  pression en échangeant de l'eau avec le primaire → **le niveau PZR monte quand la PORV crache (TMI)**.
  **Niveau cuve** (type RVLIS) affiché. **PZR plein d'eau** : la pression vient de la compressibilité (40 kg/bar),
  les PORV/soupapes déchargent de l'eau. Le seul gel de simulation restant : **cœur découvert** (accident grave).
- **Signaux** : IS sur P PZR basse (bloquable sous P-11), P enceinte > 0,24 bar rel, écart de pression entre lignes
  vapeur, débit vapeur haut + (P vapeur basse ou P-12) ; **isolement vapeur** (VIV + by-pass) mémorisé, réarmable ;
  seuil « débit vapeur haut » 40 % sous 20 % de charge → 110 % à pleine charge ; phase A (CV-8152, charge isolée).
- **Pupitre formateur** (☰ → ⚠ Pannes) : brèche primaire (∅ au choix), RTGV, brèche vapeur, PORV bloquée, perte RRI,
  grappe coincée, rupture d'air, perte / retour réseau, supprimer les brèches — à tout moment.
- **Scénarios S7 à S11** avec fiche de conduite ; option de scénario `coeur:` (ex. fin de cycle, α_mod −60 pcm/°C).
- **Interface** : onglet **RIS · EAS · Enceinte** (PTR et repères 48 / 17 %, pompes HP/MP/BP/EAS, BIT, puisards,
  rampes d'aspersion, primaire avec brèches + niveau cuve, accumulateurs, PRT et disque, atmosphère) ; bloc RIS · EAS
  de la vue d'ensemble (injection, P enceinte) ; voyants Injection / Isolement vapeur / Phase B ; alarmes primaire
  saturé, niveau cuve bas, PZR plein d'eau, activité GV, PRT, puisards ; fiches et sigles RIS, EAS, PRT, BIT, RTGV, APRP.
- 111 tests (`pytest`, ≈ 8 min).

### Résultats des tests d'acceptation (mesurés, panne à t = 30 s depuis RP 100 %)

| # | Situation | Résultat |
|---|---|---|
| E1 | Situation normale | P enceinte 0, PRT 1,27 bar disque intact, pas d'injection, cuve 100 %, 0 alarme |
| E2 | **S7** brèche 5 cm branche froide | 125 kg/s au départ ; AU **+86 s**, IS **+91 s** (P PZR) ; **HP à +95 s, MP à +135 s** (sous 106 bar) ; plateau **82 bar** (température des GV), marge à la saturation mini 3,6 °C, cuve toujours pleine ; à 30 min : brèche 59 kg/s ≈ HP 95 + MP 126 m³/h, puisards 96 m³, P enceinte 0,35 bar rel, PTR 93 % |
| E3 | Recirculation | IS manuelle → pompes RRA lancées ; PTR forcée à 47 % → arrêt RRA (« PTR à 48 % ») ; `RIS_PUISARD1` refusée puisard vide ; puisard 400 m³ → ouverture, recirculation, RRA relançable |
| E4 | **S8** PORV bloquée ouverte | AU +37 s, IS +56 s ; **primaire saturé à +260 s** (75 bar), niveau PZR de 36 % → **99 %** pendant que le vide cuve atteint 10 m³ (TMI) ; **disque de la PRT rompu à +419 s** ; fermeture de `PZR_ISOL1` acceptée |
| E5 | **S9** RTGV GV1 | **alarme d'activité à +5 s**, GV2-4 à 0 ; fuite 44 → 26 kg/s ; AU +320 s, IS +325 s ; VIV1 + by-pass + ASG1 fermés |
| E6 | **S10** brèche vapeur 30 cm (fin de cycle, grappe coincée) | IS sur P enceinte **+15 s**, **isolement vapeur +53 s** (débit haut + P vapeur basse) ; Tmoy mini **160 °C** ; réactivité de −3 085 pcm → **+171 pcm à +18 min : retour critique** (puissance ≤ 1,2 %), puis le bore de la BIT la refait descendre ; P enceinte 2,07 bar rel → aspersion + phase B à +26 min ; ASG1 coupée → GV1 sec, brèche tarie |
| E7 | **S11** perte du RRI | pompes RRI non relançables ; PP en **défaut à +120 s** sans action ; AU manuel + arrêt des 4 PP à +30 s → pompes intactes |
| E8 | Pupitre formateur | brèche 2 cm → ~20 kg/s à 155 bar, eau aux puisards ; suppression → 0 |
| E9 | Brèche 15 cm (bac à sable) | primaire saturé à +20 s ; 122 → 64 bar (5 min) → **42 bar à 10 min : accumulateurs** ; cuve mini **32 %** puis renoyée (BP sous 14 bar à +38 min) ; P = Psat(T chaude) à 0,5 bar près |

### Écarts par rapport à la spec
- **Ordre d'injection** : la spec cite HP / MP / BP ; ici l'HP passe par les pompes de charge (BIT) et la BP par les
  pompes RRA (schéma « Westinghouse »). Les MP sont des pompes dédiées.
- **Seuil de débit vapeur haut** programmé sur la charge turbine (HYPOTHESE) : avec un seuil fixe à 110 %, une brèche
  vapeur après déclenchement turbine n'isolait jamais les lignes.
- **Fin de cycle** pour S10 : α_mod −60 pcm/°C (au lieu de −20) et grappe coincée (800 pcm), sinon pas de retour de
  réactivité visible.

### Ce qui reste approximatif (V4)
1. **Primaire diphasique en « vide + liquide »** : pas de mélange diphasique dans les boucles, la circulation
   naturelle n'est pas coupée par le vide (pas de rupture de thermosiphon, pas de condensation en reflux dans les GV).
2. Brèche : débit critique simplifié (K_sat·P quand l'eau est saturée), passage progressif à la vapeur entre 30 et
   60 % du volume de découvrement (HYPOTHESE) ; dépressurisation d'une grosse brèche plus lente que la réalité.
3. **Cœur découvert = simulation figée** (pas de modèle d'accident grave).
4. PZR plein d'eau : chauffage ignoré, compressibilité constante ; PZR toujours 1 zone (le refroidissement brutal d'un
   PZR par une insurge froide reste exagéré).
5. Enceinte 1 nœud (pas de stratification, pas d'hydrogène), puisards parfaitement mélangés, pas de filtres.
6. GV vidé par une brèche : il garde ~500 kg d'eau et sa vapeur à la pression de l'enceinte (pas de vapeur surchauffée).
7. Activité : un traceur (1 = eau primaire), sans décroissance ni rejets ; pas de dosimétrie.

227 valeurs marquées `# HYPOTHESE`, listées dans [`docs/HYPOTHESES.md`](docs/HYPOTHESES.md).

## V3.1 — 2026-11-03 — Vue d'ensemble, glossaire, fiches équipements
- **Vue d'ensemble** (premier onglet) : un bloc par circuit (RCP, GV, RCV, REA, RRA, RRI, SEC, PTR, RIS, RPR, VVP,
  turbine, alternateur, ARE, GCT-c, poste d'eau, condenseur, CRF, ASG, réseau, tableaux, diesels, batteries, air),
  rangés par bâtiment et reliés par les flux (chaleur, eau primaire, vapeur, eau alimentaire, eau de mer, électricité),
  animés quand ils circulent. Bordure : en service / à l'arrêt / sollicité / en défaut. Clic : onglet détaillé.
- **Bâtiment réacteur rond** (vue de dessus) avec les **3 barrières** : ① gaines du combustible (dans la cuve),
  ② enveloppe du circuit primaire (cuve, boucles, PZR, pompes, tubes des GV), ③ enceinte à double paroi
  (béton précontraint + béton armé, espace entre-enceintes) ; traversées de l'enceinte marquées ■ (vapeur, eau
  alimentaire, ASG, RCV, RRA). Survol : explication de chaque barrière et des traversées.
- **Glossaire** : ~60 sigles décomposés (lettre par lettre) avec leur rôle ; fenêtre de recherche dans le menu ☰.
- **Fiches** des 177 équipements (nom, type, circuit, rôle) : infobulle au survol + en tête du panneau au clic.
  Chaque texte des synoptiques qui contient un sigle connu est survolable. Onglets : sigles en infobulle.

## V3 — 2026-11-03 — Électricité, diesels, séquenceurs, batteries, air comprimé, joints des PP

### Ajouté
- **Électricité** (`sim/electrical/reseau.py`) : réseau 400 kV, alternateur, transformateurs de soutirage (TS) et
  auxiliaires (TA) avec basculement rapide, tableaux 6,6 kV normaux LGA/LGB et secourus LHA/LHB.
  Sur sous-tension (< 62 % pendant 1 s), le tableau est délesté, l'arrivée normale s'ouvre et le diesel démarre.
  Une fois à vitesse (10 s), le diesel se couple et lance le séquenceur arrêt ou accident (avec IS).
  Le diesel peut déclencher sur surcharge.
- **Batteries 125 V** LBA / LBB : chargées depuis LHA / LHB, autonomie de 2 h (A) et 30 min (B). Sans 125 V, on perd
  la turbopompe ASG (régulation sur la voie A), les électrovannes des VDA et des PORV.
- **Pompes et vannes** : chaque pompe et chaque vanne motorisée suit son tableau d'alimentation (une pompe sans tension
  déclenche, une vanne motorisée reste en place). Les vannes pneumatiques suivent l'air comprimé (repli après leur
  réserve locale). Une électrovanne sans tension met la vanne en repli tout de suite.
- **Air comprimé** (`sim/systems/air.py`) : collecteur + 2 compresseurs (LHA / LHB), rupture du collecteur, isolement de la fuite.
- **Joints des pompes primaires** (`sim/systems/joints.py`) : sans injection aux joints ET sans RRI, fuite d'environ
  5 m³/h par pompe après 13 min, puis 68 m³/h une heure plus tard. Garde-fou : si le PZR se vide ou se remplit, la
  simulation se fige avec une alarme (hors du domaine du modèle).
- **AU** sur sous-tension des 2 tableaux normaux (au-dessus de P-7) ; déclenchement turbine sur perte du réseau.
- **Pannes de scénario** (`sim/scenarios/pannes.py`) : perte et retour du réseau, refus diesel (réparable), rupture d'air,
  déclenchement d'une pompe. Commandes « formateur » : `RESEAU` → perte / retour du réseau.
- **Interface** : onglet *Électricité · Air* (schéma unifilaire, trait vert = sous tension, disjoncteurs, diesels,
  charges, séquenceur, batteries, air), voyants Réseau perdu / Diesels / Batteries / Air perdu / Simulation figée.
- Scénarios **S5**, **S6**, **S12** avec leur fiche de conduite.
- 101 tests (`pytest`, ≈ 6 min).

### Résultats des tests d'acceptation (mesurés)

| # | Situation | Résultat |
|---|---|---|
| D1 | Situation normale | 4 tableaux à 100 %, LG sur le soutirage, diesels à l'arrêt, batteries 100 %, air 7 bar, 0 alarme |
| D2 | **S5** perte du réseau à 100 % | AU à +0,1 s (sous-tension 2/2) ; LHA/LHB repris par les diesels à **+11,2 s** ; séquenceur fini à +31 s (charge, RRI, SEC, ASG, air) ; à 1 h : circulation naturelle **5,0 %**, marge à la saturation **42,6 °C**, P PZR 155 bar (chaufferettes de secours), P GV 79 bar (VDA), diesel A chargé à 2 650 kW / 4 400 |
| D3 | **S6** perte totale, diesel A réparé à 45 min | batterie B vide à 30 min, A à ~62 % à 45 min ; turbopompe ASG en service ; fuite aux joints > 10 m³/h ; DIESEL_A réarmé + démarré → couplé, charge relancée, plus de dégradation des joints, batterie A rechargée. Sans action : PZR vide vers 73 min → simulation figée |
| D4 | **S12** rupture d'air | air < 5 bar à +69 s ; ARE, aspersion et décharge fermées, FCV-121 ouverte ; perte du vide → turbine → AU à +87 s ; VIV tenues 15 min ; fuite isolée + 2e compresseur : air revenu en 10 min |
| D5 | Verrous électriques | couplage diesel (pas à vitesse, tableau sous tension), arrêt d'un diesel couplé, fermeture de l'arrivée sur LG mort, pompe primaire sans tension : refusés avec raison ; retour réseau + fermeture de l'arrivée : transfert, le diesel se découple |

### Écarts par rapport à la spec
- **Chaufferettes TOR du PZR sur le tableau secouru LHB** (spec : 6,6 kV normal). Sans elles, la pression PZR baisse de
  ~6 bar/h en S5 et l'IS arrive au bout de 4 h ; c'est le « groupe de secours » des chaufferettes (HYPOTHESE).
- **Vannes ASG avec 2 h de réserve d'azote** : sans cela, elles s'ouvrent en grand en black-out, noient les GV, et le
  primaire se contracte jusqu'à vider le PZR.
- **Séquenceur** : ASG à 15,5 s et air à 20 s ajoutés (HYPOTHESE). Avec IS, RRA et pompes IS attendront la V4.
- Pas d'îlotage : la perte du réseau déclenche toujours la turbine.

### Ce qui reste approximatif (V3)
1. Tensions en tout-ou-rien (pas de chute de tension, de fréquence ni de courant de démarrage).
2. Onduleurs et 220 V ondulé non représentés à part : « 125 V perdu » = contrôle-commande de la voie perdu.
3. Air : un seul collecteur, consommation constante, sans sécheurs ni réservoirs.
4. Joints : loi de fuite en marches d'escalier (13 min, +1 h), eau perdue dans l'enceinte sans effet (V4).
5. Primaire diphasique et PZR plein hors domaine : la simulation se fige (V4 : brèches).
6. Reste de la V2 : pas de xénon, vues cœur et neutrons illustratives, PZR 1 zone.

204 valeurs marquées `# HYPOTHESE`, listées dans [`docs/HYPOTHESES.md`](docs/HYPOTHESES.md).

## V2 — 2026-11-03 — Interface zoomable, RCV + REA + RRA + RRI + SEC, états standards, vue cœur et neutrons

### Interface
- **Zoom et déplacement** sur tous les synoptiques (molette, glisser, pincer, double-clic, + − ⤢, clavier) avec
  **niveaux de détail** : vue d'ensemble épurée, les valeurs secondaires apparaissent en zoomant.
- **Primaire en étoile** (vue de dessus) : cuve au centre avec la carte des 193 assemblages et des grappes, 4 boucles en araignée.
- Écran épuré : barre du haut réduite (6 mesures, voyants seulement s'ils sont actifs), menu ☰, panneau équipement
  refermable, conditions affichées seulement si une commande est bloquée.
- **Vue cœur** (double-clic sur la cuve) : nappe de puissance (illustrative), vue axiale des groupes R / G / S,
  bilan de réactivité, curseurs de pilotage des grappes, bore, AU, k effectif, période, fissions par seconde.
- **Vue neutronique** (⚛) : animation de la réaction en chaîne (rapides, thermiques, retardés, fissions, captures,
  absorption par les grappes et le bore), liée à la réactivité et à la puissance du simulateur.
- Badge d'état cliquable : **état standard + check-list** pour l'état suivant. Fiches de conduite des scénarios dans ☰.

### Modèle
- **RCV** : 2 pompes de charge (caractéristique), FCV-121 sur la régulation de niveau PZR, injection aux joints,
  décharge LCV-459/460 → 3 orifices (∝ √ΔP) → CV-8152 → échangeur (RRI), régénérateur, VCT, PTR, HCV-128 (RRA → RCV).
  Verrous de mise en service dans l'ordre de la spec, isolement sur niveau PZR bas, orifices fermés sans pompe de charge,
  bascule sur la PTR au niveau VCT très bas (retour manuel), déviation vers les effluents au niveau haut.
- **REA** : auto (appoint VCT sur niveau bas, à la concentration du primaire), borication (acide à l'aspiration des
  pompes de charge), dilution (eau à la VCT), arrêt, borication d'urgence MO-8104. **Bore du primaire dynamique**.
- **Cœur** : coefficient modérateur qui s'affaiblit à froid ; **groupe G** (compensation, manuel) en plus de R et S
  (R + G + S = −5 000 pcm) ; marges d'arrêt (grappe la plus efficace coincée) et bore d'arrêt à froid calculés.
- **RRA** : 2 trains dans le réseau primaire (aspiration au plénum, retour à la descente), échangeurs à contre-courant,
  vannes d'échangeur en auto (vitesse de refroidissement ~30 °C/h), by-pass complémentaire, verrou 30 bar, fermeture 41 bar.
- **RRI / SEC** : un nœud thermique, 2 voies ; sans RRI, défaut des pompes primaires après 5 min.
- **Accumulateurs** : 4 × 29 m³ sous 42 bar, injection ∝ √ΔP ; rouverts automatiquement au-dessus de P-11 ou sur IS.
- **IS (signal)** : P PZR < 122 bar ou P vapeur < 41 bar, blocable sous **P-11** (138 bar), manuelle ; ordres : AU,
  isolement ARE, ASG, phase A (décharge), aspiration PTR. L'injection elle-même arrive en V4.
- **États standards** RP / AN/GV / AN/RRA / arrêt à froid + check-lists ; vitesse de refroidissement sur une heure glissante.
- Scénario **S2** (RP → AN/GV → AN/RRA) avec sa fiche de conduite.
- 96 tests (`pytest`, ≈ 5 min).

### Résultats des tests d'acceptation (mesurés)

| # | Situation | Résultat |
|---|---|---|
| C1 | 1 h à 100 % | bore 1 000 ppm constant, VCT ~50 %, charge 12,5 m³/h (+ 4,5 par les joints = décharge 17), RRI ~20 °C, 0 alarme |
| C2 | Borication 2 m³ puis dilution 4 m³ | bore +20 ppm et plus en 30 min, retour REA en auto ; la dilution fait redescendre le bore (retard dû à la VCT) |
| C3 | Verrous V2 | aspiration RRA à 155 bar, fermeture accumulateurs sans P-11, blocage IS sans P-11, pompe RRA sans aspiration, LCV-459 avec orifice ouvert, pompe primaire sans RRI : refusés avec raison |
| C4 | VCT vidée | appoint REA automatique, puis bascule sur la PTR (charge à 2 500 ppm), retour manuel |
| C5 | Accumulateurs | injection sous 42 bar si non isolés, rien si isolés |
| C6 | Aspiration RRA ouverte à 155 bar | refermée automatiquement, alarme |
| C7 | Perte RRI | alarme immédiate, défaut des pompes primaires à 5 min, AU débit bas |
| C8 | États | RP → AN/GV après AU, check-list AN/RRA affichée (accumulateurs, RRA… ✗) |
| **S2** | RP → AN/GV → AN/RRA (fiche jouée pas à pas) | AN/RRA à **4,1 h**, arrêt à froid à **7,3 h** ; refroidissement ≤ **30 °C/h** (limite 56) ; bore 1 269 ppm pour 1 113 requis ; marge à la saturation ≥ 45 °C ; ni IS ni injection des accumulateurs ; RRA ~50 MW, RRI ~36 °C avec 2 voies |
| — | Performance | ≈ 2 400 pas/s (S2 complet, 7 h simulées : 3 min de calcul) |

### Écarts par rapport à la spec / à la V1
- **Groupe G ajouté** (spec : « groupes de régulation » lissés) : il donne un 2e levier manuel dans la vue cœur.
  Les groupes d'arrêt passent de −3 000 à −1 500 pcm pour garder −5 000 pcm au total.
- **Bore d'arrêt à froid modéré** (~1 113 ppm pour 1 000 ppm en puissance) : le coefficient modérateur s'annule
  vers 20 °C (hypothèse) et il n'y a pas de xénon. Un vrai cœur demande en général plus de bore.
- **RRA ramené au plénum / à la descente** (spec : branche chaude B4 / branches froides) : même effet thermique.
- Test **B8** : le verrou « décharge sans charge » devient l'ordre de mise en service du RCV (orifice sans pompe de charge).

### Ce qui reste approximatif (V2)
1. **Vues cœur et neutrons** : la nappe radiale/axiale et l'animation sont **illustratives** ; les chiffres
   (ρ, k, période, fissions/s, bore) viennent du modèle point.
2. **Pas de xénon** ni de samarium : après un arrêt, rien ne « s'empoisonne ».
3. **RCV** : PCV-131 supposée parfaite (24,5 bar), pas de TCV-129, VCT sans pression ni hydrogène, pas de joints détaillés.
4. **IS** : signal et ordres seulement, pas d'injection (V4). Pas de phase B, pas d'enceinte.
5. **RRI** : un seul nœud (pas de voies séparées, pas de bâche d'expansion), SEC sans encrassement.
6. **GV à l'arrêt** : les niveaux montent pendant la phase RRA si l'on ne coupe pas l'alimentation (régulation de
   niveau peu adaptée aux très faibles débits).
7. Reste de la V1 : pressuriseur 1 zone, électricité toujours disponible (V3), condenseur trop rapide en perte d'ARE.

182 valeurs marquées `# HYPOTHESE`, listées dans [`docs/HYPOTHESES.md`](docs/HYPOTHESES.md).

## V1 — 2026-11-03 — Primaire 4 boucles, pressuriseur, cœur, ASG + mode navigateur

### Ajouté
- **Cœur boîte noire** (`sim/core_model/coeur.py`) : cinétique ponctuelle 1 groupe (saut prompt), Doppler, modérateur,
  bore, grappes (courbe en S, chute en 2 s), nœud combustible, puissance résiduelle (Way-Wigner), régulation
  des grappes en auto (Tmoy − Tref + voie « écart de puissance »).
- **Primaire** (`sim/systems/rcp.py`) : 3 nœuds cuve + 3 nœuds par boucle, réseau hydraulique (4 pompes,
  antidévireur, pompes de soulèvement d'huile), circulation naturelle, échange GV ε-NTU (UA ∝ débit^0,8).
- **Pressuriseur** (`sim/systems/pzr.py`) : équilibre liquide/vapeur, chaufferettes P + TOR, aspersion B2/B3,
  2 PORV + isolements, 3 soupapes, expansion/contraction. **RCV simplifié** : charge régulée, décharge TOR.
- **ASG** (`sim/systems/asg.py`) : CST → 2 motopompes + 1 turbopompe (vapeur GV1/GV2) → 4 vannes régulées → GV.
- **Logique V1** : AU flux haut/bas, ΔT surtempérature/surpuissance (avance-retard), P PZR haute/basse, niveau PZR
  haut, débit primaire bas (2/3 par boucle, 1 ou 2 boucles selon P-8), permissifs P-4 → P-14, C-3/C-4 (runback),
  C-7, C-8, C-9, C-11 ; GCT-c en mode Tmoy ou pression ; démarrage auto ASG ; isolement/coupure sur PZR bas.
- **Alarmes** avec temporisation de confirmation (2 s) et hystérésis en valeur absolue (fini le papillotement).
- **Interface** : onglets Primaire et ASG, bandeau de permissifs, état d'exploitation (RP, AN/GV…), commandes RPR.
- **Mode navigateur** : la même simulation tourne dans le navigateur (Pyodide dans un Web Worker), donc
  déployable en statique sur Vercel (`vercel.json`, `web/sim_bundle.zip`). Le moteur n'a plus besoin de numpy,
  CoolProp ni PyYAML à l'exécution (tables pré-calculées, config JSON dans le paquet).
- 87 tests (`pytest`, ≈ 2 min).

### Résultats des tests d'acceptation (mesurés)

| # | Situation | Résultat |
|---|---|---|
| B1 | 1 h à 100 % sans action | P PZR 154,98 → 155,01 bar, niveau PZR 60,0 %, Tmoy 307,09 °C, 99,7 %, 1 135 MWe, 0 alarme |
| B1 | Bilan et masse primaire | cœur 3 402,4 + pompes 18,0 MW ≈ GV 3 419,7 MW (écart 0,02 %) ; dérive de masse −5·10⁻⁴ %/h |
| B2 | Échelon −10 % | pas d'AU ni de PORV/soupape ; P PZR 152,8 → 155,4 bar ; puissance mini 84,7 % ; Tmoy − Tref = −0,7 °C à 15 min |
| B3 | Déclenchement turbine | AU (P-7) ; GCT-c 90 % (C-8) ; P PZR mini 139,6 bar ; niveau PZR mini 28,8 % ; GV 31 → 58 % ; P GV max 77,0 bar ; Tmoy → 292,5 °C ; marge saturation mini 20,1 °C |
| B4 | Arrêt PP1 | AU « débit primaire bas B1 » à 2,0 s ; boucle 1 à −14,7 % (antidévireur), autres à 108,8 % |
| B5 | Perte totale ARE | AU à 18,4 s ; 3 pompes ASG, 120 kg/s maxi ; niveaux GV remontés à 39 % en 30 min ; −38 m³ dans la CST |
| B6 | Circulation naturelle (4 PP arrêtées) | débits 4,5 à 4,8 % ; ΔT boucle 8,9 °C ; marge saturation mini 37,4 °C ; 34 MW résiduels à 1 h |
| B7 | Consigne P PZR à 164 bar | PORV ouvertes à 162 bar (t = 313 s), P reste sous le seuil d'AU (165,5 bar), pas d'AU |
| B8 | Verrous | PP sans huile, grappes avec AU, blocage flux bas sans P-10, décharge RCV sans charge : refusés avec raison |
| — | Performance | serveur ≈ 2 400 pas/s (×600 tenu à ≈ ×240) ; navigateur ×60 tenu, ×600 tenu à ≈ ×110 |

### Écarts par rapport à la proposition validée
- **B5** : l'AU arrive par le déclenchement turbine (perte du vide condenseur, voir point 6 ci-dessous) et non par
  « niveau GV très bas ». Le test accepte la première cause atteinte. L'ASG démarre bien sur niveau très bas.
- **B6** : en circulation naturelle, le GCT-c en **mode Tmoy oscille** (Tmoy mesurée en retard sur la chaleur évacuée).
  Le test passe le GCT-c en **mode pression**, ce qu'on fait aussi en pratique pour piloter un refroidissement.
- **Ajouts** : voie « écart de puissance » sur les grappes (sans elle, l'échelon −10 % descendait à 77 %) ;
  pompes de soulèvement d'huile ; temporisation des alarmes.

### Ce qui reste approximatif
1. **Cœur** : 1 groupe de neutrons retardés, pas de xénon/samarium, pas de distribution axiale (ΔI = 0 dans
   les ΔT surtempérature/surpuissance), coefficients de contre-réaction constants, bore figé (REA en V2).
2. **Pressuriseur** : 1 zone à l'équilibre (pas d'eau sous-refroidie ni de vapeur surchauffée).
3. **RCV** : charge et décharge seulement (pas de VCT, de joints de pompes ni de borication).
4. **Primaire** : réseau quasi statique (pas d'inertie de la colonne d'eau ; le ralentissement vient de l'inertie
   des pompes), échange GV global (pas de zones préchauffage/ébullition).
5. **GCT-c en mode Tmoy instable en circulation naturelle** : utiliser le mode pression.
6. **Condenseur** : quand l'alimentation s'arrête, la chaleur des soutirages part d'un coup au condenseur,
   d'où une perte du vide trop rapide (~18 s) en perte totale ARE. À corriger en V2.
7. **ASG** : turbopompe sans modèle de turbine (vitesse imposée si la vapeur est disponible).
8. **Électricité et air comprimé** : toujours disponibles (V3). **Pas d'injection de sécurité** ni
   d'isolement vapeur automatique (V4) : le seuil P PZR basse fait l'AU, pas l'IS.
9. Reste de la V0 : turbine à 1 corps, réchauffeurs sans inertie, gonflement/tassement global (voir plus bas).

142 valeurs marquées `# HYPOTHESE`, listées dans [`docs/HYPOTHESES.md`](docs/HYPOTHESES.md).

## V0 — 2026-11-02 — Moteur générique + boucle secondaire

### Ajouté
- Moteur générique : config YAML typée et validée (clé inconnue = erreur), tables eau/vapeur CoolProp IF97
  pré-calculées (flash (v, u) → P en ~6 µs), solveur de réseau hydraulique quasi statique
  (Newton sur les nœuds + recherche linéaire), journal, alarmes, historique, sauvegarde/chargement JSON déterministe.
- Composants : pompe centrifuge (similitude, démarrage/ralentissement), vannes MOV/AOV (repli, réserve d'air),
  vanne régulée, clapet, perte de charge, soupape (blowdown), bâche, volume diphasique, capteur 3 voies, PI.
- Systèmes : source V0, 4 GV avec gonflement/tassement, VVP (VIV + by-pass, VDA, 5 soupapes/ligne),
  turbine + alternateur, GCT-c, condenseur/CRF/puits/CST, poste d'eau complet (CEX, ABP, reprise, APP, APD, AHP, ARE).
- Logique : AU, P-4, P-7, P-14, C-9, isolements ARE, déclenchements, régulations, verrous avec raisons.
- Interface web : synoptique, logique, courbes, journal, alarmes, accélération, sauvegarde/chargement, scénario S0.
- 69 tests (`pytest`, ≈ 45 s).

### Résultats des tests d'acceptation (mesurés)

| # | Situation | Résultat |
|---|---|---|
| A1 | 1 h à 100 % sans action | P GV 62,99 bar, niveaux 50,00 %, 1 130,0 MWe constants, 0 alarme |
| A2 | Bilan énergie | source 3 402,56 MW = méca + mer 3 402,56 MW (écart < 0,01 %) |
| A3 | Masse en circuit fermé | dérive 2·10⁻⁵ %/h (critère 0,1 %/h) |
| A4 | Fermeture ARE GV1 | gonflement +0,2 %, puis chute, AU niveau très bas à 27,5 s |
| A5 | Échelon −10 % | tassement −3,2 %, P GV max 67,5 bar, ni AU ni soupape |
| A6 | Échelon +10 % | gonflement +3,2 %, retour à la consigne, pas d'AU |
| A7 | ARE GV1 ouverte de +15 % | tassement −0,11 %, puis montée (+6,8 % à 30 s) |
| A8 | Déclenchement turbine | AU à 0,4 s, niveau mini 26 %, P GV max 77,0 bar, GCT-c 30 %, pas de soupape ; à 10 min : 76,1 bar |
| A9 | Perte des 2 CRF | déclenchement turbine sur vide à 76 s (0,30 bar), AU, GCT-c bloqué, VDA 44 kg/s, P GV max 79,5 bar |
| A10 | Verrous | GCT-c sans C-9, APP sans aspiration, couplage hors synchro, réarmement turbine avec P-14 : refusés avec raison |
| A11 | Sauvegarde → 60 s ⇄ chargement → 60 s | états identiques |
| A12 | Serveur | page, WebSocket, commandes, conditions, API sauvegarde/historique/scénario |
| A13 | Performance | ≈ 2 950 pas/s, donc ×60 tenu ; ×600 tenu à ≈ ×230 (affiché dans l'interface) |

### Écarts par rapport à la proposition validée
- **A4** : j'avais écrit « débits vapeur GV2-4 ↑ ». C'est l'inverse qui est physique : sans eau froide à réchauffer,
  le GV1 produit plus de vapeur. Le test vérifie donc que la vapeur du GV1 augmente.
- **A4 / A7** : la réponse inverse du niveau sur une variation d'eau alimentaire est faible (0,1 à 0,2 %GE), parce
  que les vannes ARE mettent 5 à 10 s à bouger. Les seuils sont de +0,1 % et −0,05 % au lieu de ±1 %.
  Les gros effets, pilotés par le débit vapeur, sont bien là (±3 % sur ±10 %, −24 % au déclenchement).
- **Ajouts** : by-pass des VIV (sans lui, impossible de rouvrir une VIV après isolement) ; caractéristique
  débit/pression des pompes de reprise (sinon le réseau n'a pas de solution quand l'aval est fermé).
- **Arborescence** : `thermo/water.py` est fusionné dans `thermo/tables.py`. Ajouts : `scenarios/chargement.py`
  et `tools/` (état initial, liste des hypothèses).

### Ce qui reste approximatif
1. **Source V0** : 1 seul nœud primaire (pas de boucles, de PZR ni de neutronique), remplacé en V1. En auto, elle
   suit Tref(charge) et joue le rôle des grappes et des contre-réactions.
2. **Gonflement/tassement** : modèle global de volume de bulles (`k_bulles`, `tau_sejour_s` calés).
   Il ne distingue pas la descente de la zone de tubes.
3. **Réchauffeurs** : T de sortie = table(charge) + retard de 120 s. Leur énergie stockée n'est pas suivie, donc le bilan
   n'est exact qu'à l'équilibre ; en transitoire, la chaleur vers le condenseur est bornée à ≥ 0.
4. **Turbine** : un corps équivalent, détente isentrope depuis la vapeur saturée, soutirages = fraction fixe du débit,
   pas de sécheurs-surchauffeurs (GSS), débit admis ∝ ouverture × pression.
5. **Condenseur** : un seul caisson, P = Psat(T) + incondensables constants, éjecteurs (CVI) non modélisés.
6. **APP** : vitesse régulée, mais la vapeur consommée par les turbopompes est négligée.
7. **Électricité et air comprimé** : tout est disponible (stubs). Les champs `alim` / `air` sont prêts pour la V3.
8. **Pas d'ASG ni de purges APG** : après AU, les GV sont alimentés par l'ARE petit débit et les APP. L'ASG est proposée en V1.
9. **GCT-c** en mode pression seulement ; mode Tmoy, C-7, C-8 et P-12 en V1.
10. **Isolements** : pas d'isolement vapeur automatique (V4). VIV sans retard de 0,5 s. L'isolement ARE sur P-4
    n'est pas mémorisé et ne déclenche pas les APP. La spec se contredit sur ce point (§4.8 vs §4.14) ; j'ai gardé
    le choix validé.
11. **Après réarmement de l'AU** : la source repart en manuel, sans phase de divergence (V1).
12. **Réseau quasi statique** : pas d'inertie hydraulique, et la masse volumique est prise par zone de température.
13. **Eau alimentaire après déclenchement** : elle refroidit vers ~50 °C (pas de vapeur auxiliaire ni d'ADG).

Toutes les valeurs choisies sans appui dans la spec sont listées dans [`docs/HYPOTHESES.md`](docs/HYPOTHESES.md)
(94 valeurs marquées `# HYPOTHESE`).
