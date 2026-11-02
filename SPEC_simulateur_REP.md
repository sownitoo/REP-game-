# SPEC — Simulateur REP pédagogique « Mini-Centrale »

> **But** : un jeu / simulateur *schématique* d'une centrale REP 4 boucles, centré sur **les circuits, les lignages de vannes, l'électricité et la thermo**, pas sur la neutronique fine.
> **Base technique** : manuels publics USNRC *Westinghouse Technology Systems Manual* (cours R304P, centrale de référence Trojan, 4 boucles ≈ ~3400 MWth, proche d'un REP 1300 français) — voir §14.
> **Avertissement** : centrale **générique**. Les valeurs sont des ordres de grandeur issus des manuels NRC (converties en SI), **pas** des consignes ou réglages EDF. Les trigrammes EDF sont donnés à titre indicatif pour faire le lien.

---

## 0. Conventions

| Grandeur | Unité dans le code | Conversion depuis les manuels US |
|---|---|---|
| Pression | **bar abs** (sauf mention « bar rel ») | bar = (psig + 14,7) × 0,068948 |
| Température | °C | °C = (°F − 32) / 1,8 |
| Débit volumique | m³/h | 1 gpm = 0,2271 m³/h |
| Débit massique | kg/s | 1 lb/h = 1,26·10⁻⁴ kg/s |
| Volume | m³ | 1 gal = 3,785·10⁻³ m³ ; 1 ft³ = 0,02832 m³ |
| Puissance | MW / kW | 1 hp = 0,7457 kW |

- Fréquence réseau : **50 Hz** (France). Les seuils US à 60 Hz sont ramenés proportionnellement (57,7 Hz → ~48 Hz).
- Toutes les valeurs numériques vivent dans **un seul fichier de config** (`config/plant.yaml`) pour pouvoir les ajuster sans toucher au code.

---

## 1. Ce que le joueur doit pouvoir faire

1. **Voir** chaque circuit sur un synoptique (schéma type P&ID simplifié) avec l'état des vannes, pompes, disjoncteurs, niveaux, P, T, débits.
2. **Manœuvrer** : ouvrir/fermer/régler une vanne, démarrer/arrêter une pompe, fermer/ouvrir un disjoncteur, passer une régulation auto ↔ manu, bloquer/réarmer un signal quand un permissif l'autorise.
3. **Comprendre les conditions** : chaque action refusée affiche *pourquoi* (verrouillage, permissif, pas de tension, pas de débit mini…).
4. **Faire les transitions d'état** (RP → AN/GV → AN/RRA → API… et retour).
5. **Subir des scénarios** (pannes injectées) et voir les automatismes réagir (AU, IS, isolements, démarrage diesels…).
6. **Être noté** sur la préservation des 3 fonctions de sûreté (réactivité, refroidissement, confinement) et des 3 barrières (gaine, primaire, enceinte).

---

## 2. Architecture logicielle

### 2.1 Pile proposée (modifiable)

- **Cœur de simulation** : Python 3.11+, `numpy`, `CoolProp` (tables eau/vapeur IAPWS-IF97), `pyyaml`, `pytest`.
- **Interface** : page web unique (HTML + SVG + JS vanilla) servie par `FastAPI` + WebSocket. Synoptiques en SVG, un onglet par système.
- **Pas de framework lourd**. Tout doit tourner avec `pip install -r requirements.txt && python -m sim.server`.

### 2.2 Découpage en couches

```
config/plant.yaml        → toutes les données (composants, liaisons, consignes, seuils)
sim/core/                → moteur générique (graphe, pas de temps, solveur)
sim/components/          → Pump, Valve, CheckValve, ReliefValve, Tank, Volume2Phase, HeatExchanger, Pipe…
sim/systems/             → assemblage par système (rcp.py, rcv.py, rra.py, ris.py, vvp.py…)
sim/thermo/              → wrapper CoolProp + tables pré-calculées (rapidité)
sim/core_model/          → cœur « boîte noire » (puissance, résiduelle, contre-réactions)
sim/electrical/          → réseau, tableaux, disjoncteurs, diesels, séquenceurs, batteries
sim/logic/               → protection (AU), sauvegardes (IS…), permissifs P-x, verrous C-x, régulations
sim/scenarios/           → scénarios YAML (état initial + pannes + critères de réussite)
sim/scoring/             → fonctions de sûreté, barrières, score
web/                     → synoptiques SVG + panneau alarmes + chrono
tests/                   → tests unitaires + tests d'intégration par scénario
```

### 2.3 Boucle de calcul

- Pas de temps fixe **dt = 0,1 s** de temps simulé ; accélération ×1 / ×10 / ×60 / ×600 (sous-pas si nécessaire).
- Ordre d'un pas :
  1. Lecture des commandes joueur (file d'actions horodatée).
  2. **Électricité** : quels tableaux sont sous tension → quelles pompes/vannes motorisées sont alimentées.
  3. **Logique** : capteurs → seuils → permissifs → signaux AU / IS / isolements → ordres automatiques.
  4. **Régulations** (PID simples) → positions de vannes, vitesses.
  5. **Hydraulique** : débits dans chaque branche (voir §11.2).
  6. **Thermique** : bilans masse + énergie de chaque volume, puissances échangées.
  7. **Cœur** : puissance neutronique + résiduelle.
  8. Mise à jour alarmes, score, enregistrement historique (ring buffer pour les courbes).
- État complet sérialisable (JSON) → **sauvegarde / chargement** d'une situation à tout instant.

---

## 3. Modèle de composants génériques

Chaque composant a : `id` (repère), `system`, `type`, `params`, `state`, `power_supply` (tableau électrique ou `none`), `air_supply` (si pneumatique), `fail_position` (ouverte / fermée / en place).

| Type | Paramètres clés | Comportement |
|---|---|---|
| `Pump` (centrifuge) | Q_nom, H_nom, H_0 (hauteur à débit nul), n_nom, P_moteur, alimentation, débit mini, NPSH requis | H = H_0·(n/n_nom)² − k·Q². Débit mini → vanne de recirculation auto. Pas de tension → s'arrête (ralentissement selon inertie). |
| `PumpPD` (volumétrique) | Q par vitesse | Q ∝ vitesse, soupape de refoulement |
| `TurboPump` | vapeur amont mini | Puissance ∝ débit vapeur, pas besoin d'électricité alternative |
| `Valve` motorisée (MOV) | temps de course, Kv | Besoin d'alimentation électrique ; reste **en place** si perte de tension |
| `Valve` pneumatique (AOV) | temps de course, position de repli | Perte d'air → position de repli (souvent fermée), sauf réserve d'air locale (bouteille : N manœuvres ou N minutes) |
| `ControlValve` | Kv, caractéristique, consigne | Pilotée par un PID |
| `CheckValve` | ΔP d'ouverture | Ouvre si ΔP > seuil, interdit le retour |
| `ReliefValve` / `SafetyValve` | P_tarage, accumulation, fermeture (blowdown), capacité | Ouverture passive, hystérésis |
| `Tank` (bâche atmosphérique ou sous gaz) | volume, P_gaz, T | niveau, P, T, concentration en bore |
| `Volume2Phase` | volume, P, masse eau / vapeur | Équilibre de saturation (pressuriseur, GV côté secondaire, condenseur, bâche de décharge) |
| `HeatExchanger` | UA nominal, type (contre-courant / U) | Méthode ε-NTU |
| `Pipe` / `Node` | volume, ΔP nominal | Jonctions |
| `Sensor` | grandeur, gamme, nb de voies, retard | Alimente la logique ; peut tomber en panne (valeur figée) |
| `Breaker` | source, charge, temps de fermeture | Ouverture sur défaut / sous-tension |
| `Bus` | tension nominale | Sous tension si au moins une source connectée |
| `DieselGen` | P_nom, temps de démarrage | Démarre sur ordre, prend la charge via séquenceur |
| `Battery` | autonomie (h) | Se décharge sans chargeur |

---

## 4. Inventaire des systèmes

Pour chaque système : rôle, équivalent EDF (indicatif), composants, valeurs, automatismes. Les repères (`PCV-131`…) viennent du manuel NRC : on les garde comme repères génériques dans le code.

### 4.1 Circuit primaire principal — équivalent **RCP**

**Rôle** : transférer la chaleur du cœur aux GV, 2ᵉ barrière.

**Topologie** : cuve + 4 boucles en parallèle. Chaque boucle : branche chaude → GV → branche en U (« intermédiaire ») → pompe primaire → branche froide → cuve. Pressuriseur relié par la ligne d'expansion à la branche chaude de la boucle 2.

**Piquages par boucle** (utile pour brancher les autres systèmes) :

| Piquage | Boucle | Système relié |
|---|---|---|
| Ligne d'expansion pressuriseur | chaude B2 | Pressuriseur |
| Aspiration RRA | chaude B4 | RRA |
| Décharge RCV (letdown) | intermédiaire B3 | RCV |
| Charge RCV normale / de secours | froide B1 / B4 | RCV |
| Aspersion pressuriseur | froides B2 et B3 | Pressuriseur |
| Décharge excédentaire | froide B3 | RCV |
| Injection BP/MP + accumulateur | froides (toutes) | RIS |
| Injection HP | froides (toutes) | RIS (pompes de charge) |
| Recirculation branche chaude | chaudes | RIS |
| Purge vers RCDT | toutes | Purges primaires |

**Pompes primaires (×4)**

| Paramètre | Valeur |
|---|---|
| Débit par pompe | ~20 100 m³/h |
| Hauteur | ~84 m |
| Puissance moteur (chaud / froid) | ~4,5 MW / ~6,0 MW |
| Alimentation | tableaux **non secourus** (pas sur diesels) |
| Volant d'inertie | allonge le ralentissement de ~22 à 30 s |
| Antidévireur | empêche la rotation inverse (sinon courant de démarrage excessif) |
| Pompe de soulèvement d'huile | **verrou** : démarrage interdit sans pression d'huile depuis un temps donné |
| Injection aux joints | ~1,8 m³/h par pompe (≈ 1,1 vers le primaire, ≈ 0,7 vers les joints) |
| Joint n°1 | ΔP mini **~19 bar** pour fonctionner (soit P primaire ≥ ~29 bar) |
| Fuite joint n°1 (retour) | vers RCV (aspiration pompes de charge) |
| Fuite joint n°2 / n°3 | ~11 L/h / ~0,1 L/h vers RCDT |
| Refroidissement | barrière thermique + paliers moteur par **RRI** |
| Perte RRI | arrêt de la pompe sous **~2 min** |
| Perte injection joints **ET** perte barrière thermique | dégradation des joints → **petite brèche** (jusqu'à ~68 m³/h par pompe en black-out) |
| Fuite primaire dans la barrière thermique | débit RRI retour élevé → **isolement auto** du retour |

**Pressuriseur**

| Paramètre | Valeur |
|---|---|
| Volume | ~51 m³ (≈ 60 % eau / 40 % vapeur à pleine puissance) |
| Pression nominale | **155 bar** |
| Pression de calcul | 172 bar |
| Chaufferettes | 1 794 kW au total : groupe **proportionnel 414 kW** + groupes **tout-ou-rien 1 380 kW** (~30 °C/h de chauffe) |
| Aspersion | 2 vannes pneumatiques (depuis froides B2 et B3), ~95 m³/h chacune ; débit permanent de ~0,23 m³/h en by-pass |
| Aspersion auxiliaire | depuis la charge RCV, quand les pompes primaires sont arrêtées |
| Vannes de décharge pilotées (PORV) ×2 | ~26,5 kg/s chacune, pneumatiques, réserve d'air 10 min, **vanne d'isolement** en amont |
| Soupapes de sûreté ×3 | tarage **172 bar**, ~53 kg/s chacune |
| Rejet | vers la **bâche de décharge** (PRT) |

**Bâche de décharge du pressuriseur (PRT)** : ~51 m³, ~¾ d'eau sous azote, condensation par barboteur. Refroidissement par aspersion d'eau d'appoint si T > ~46 °C. Calcul ~8 bar abs, **disques de rupture** au même seuil.

**Générateurs de vapeur (×4)** — tubes en U, ~3 400 tubes

| Paramètre | Valeur |
|---|---|
| Débit vapeur par GV (100 %) | ~475 kg/s |
| Pression vapeur à 100 % | ~63 bar abs (baisse d'environ 10 bar entre 0 % et 100 % de charge) |
| Température vapeur | ~278 °C, humidité < 0,25 % |
| Eau alimentaire à 100 % | ~221–227 °C |
| Taux de recirculation | 3 à 5 × le débit alimentaire |
| Niveau GE (gamme étroite) | 3 voies, régulation + protection |
| Niveau très bas | **11,5 %** → AU (perte de source froide) |
| Niveau très haut | **69 %** → déclenchement turbine + isolement ARE |
| Phénomène à modéliser | **gonflement / tassement** (« swell / shrink ») du niveau lors des variations de débit vapeur |
| Purges | purge continue vers APG |

**Températures primaires** : Tmoy nominale à 100 % ≈ **307 °C** (programme Tmoy croissant avec la charge). Les limites de vitesse de chauffe / refroidissement (~55 °C/h, courbes P-T « rupture fragile » de la cuve) sont à imposer au joueur.

**Circulation naturelle** : possible pour évacuer la **puissance résiduelle** seulement (GV plus hauts que la cuve).

---

### 4.2 Contrôle chimique et volumétrique — équivalent **RCV** (+ **REA** pour l'appoint eau/bore)

**Chemin de décharge (letdown)** dans l'ordre :

| # | Composant | Rôle / valeur |
|---|---|---|
| 1 | Vannes d'isolement LCV-459/460 (série) | Fermeture auto si **niveau pressuriseur < 17 %** |
| 2 | Tuyau de retard | Décroissance de l'azote 16 |
| 3 | Échangeur régénérateur | Décharge 288 → 143 °C, réchauffe la charge 54 → 260 °C |
| 4 | Orifices ×3 (17 / 17 / 10 m³/h à 155 bar) + vannes d'orifice | Laminage et pression |
| 5 | Vanne d'isolement enceinte CV-8152 | Fermée par **isolement phase A** |
| 6 | Échangeur de décharge (refroidi par **RRI**) | Sortie régulée à ~49 °C |
| 7 | Vanne de régulation de pression PCV-131 | Maintient ~24,5 bar en amont pour **éviter la vaporisation** |
| 8 | Vanne de déviation TCV-129 | By-pass des déminéraliseurs si T > **58 °C** (retour manuel) |
| 9 | Déminéraliseurs à lits mélangés ×2 + cationique | Purification (débit max ~29 m³/h) |
| 10 | Filtre | Fines de résine |
| 11 | Vanne 3 voies LCV-112A | Dévie vers le traitement des effluents si niveau RCV haut |
| 12 | **Réservoir RCV (VCT)** | Sous hydrogène, soupape ~6,2 bar abs, ventilation fermée si P < ~2 bar abs |

**Soupapes** : ~42 bar abs après les orifices (vers PRT), ~21 bar abs après PCV-131 (vers VCT).

**Verrous de mise en service (ordre imposé)** :
1. Démarrer une pompe de charge.
2. Ouvrir LCV-459/460 (interdit si une vanne d'orifice est ouverte).
3. Ouvrir une vanne d'orifice (interdit sans pompe de charge en marche et sans LCV-459/460 ouvertes).
- Perte de la pompe de charge → fermeture des vannes d'orifice.
- Niveau pressuriseur bas ou isolement phase A → fermeture des vannes d'orifice.

**Charge** :

| Composant | Valeur / logique |
|---|---|
| Pompes de charge centrifuges ×2 (secourues) | ~34 m³/h nominal, hauteur à débit nul ~185 bar ; **ce sont aussi les pompes d'IS haute pression** |
| Pompe volumétrique ×1 (non secourue) | Vitesse variable |
| FCV-121 | Débit de charge piloté par la **régulation de niveau pressuriseur** |
| HCV-182 | Partage charge / injection aux joints |
| Isolement charge MO-8105/8106 | Fermé par **IS** |
| Vanne de charge normale (B1) / de secours (B4) | + clapet taré ~14 bar en parallèle |
| Aspersion auxiliaire CV-8145 | Vers le pressuriseur |
| Retour joints | Isolé par **phase A**, soupape vers PRT à ~11 bar abs |
| Échangeur eau de joints (RRI) | Refroidit retour joints + recirculation des pompes de charge |

**Bilan nominal** : décharge 17 m³/h ; charge 19,8 m³/h = 12,5 vers la boucle + 7,3 vers les joints ; 4,5 m³/h reviennent du primaire par les joints ; 2,7 m³/h de retour joints vers la VCT.

**Aspiration des pompes de charge** :
- Normale : VCT par LCV-112B/C (fermées sur **niveau VCT très bas** ou **IS**).
- Secours : **bâche PTR** par LCV-112D/E (ouvertes sur niveau VCT très bas ou **IS**).
- Recirculation après accident : refoulement des pompes RRA.

**Appoint eau-bore (REA)** — 5 modes : **Borication**, **Dilution**, **Dilution alternée**, **Automatique**, **Manuel**.

| Composant | Valeur |
|---|---|
| Bâches d'acide borique ×2 | ~92 m³ chacune à ~7 000 ppm ; minimum requis ~60 m³ |
| Pompes de transfert d'acide borique ×2 | Démarrent en borication / auto |
| Bâche d'eau d'appoint primaire | ~770 m³ |
| Mélangeur | Mélange eau + acide → aspiration pompes de charge ou VCT |
| Mode auto | Démarre sur niveau VCT bas, débit total ~18 m³/h, s'arrête sur niveau VCT haut |
| **Borication d'urgence** MO-8104 | Ouverture manuelle + pompe de transfert (ATWS, grappe coincée, dilution) |

**Purification pendant RRA** : piquage RRA → RCV via HCV-128.

**Exploitation en « primaire plein »** (sans bulle au pressuriseur) : la pression est réglée par le déséquilibre charge / décharge (PCV-131 en auto, charge fixe via HCV-182).

---

### 4.3 Refroidissement à l'arrêt — équivalent **RRA**

| Paramètre | Valeur |
|---|---|
| Configuration | 2 pompes + 2 échangeurs (refroidis par **RRI**), 2 voies électriques séparées |
| Aspiration | Branche chaude B4 par **2 vannes en série** (8701/8702) + soupape |
| Refoulement | 4 branches froides (lignes communes avec l'injection BP du RIS) |
| **Verrou d'ouverture** | Aspiration interdite si P primaire > **~30 bar abs** |
| **Fermeture auto** | Si P primaire remonte à **~41 bar abs** |
| Mise en service typique | ~4 h après l'arrêt, à ~177 °C / ~30 bar |
| Performance | 177 → 60 °C en ~16 h avec 2 voies ; dimensionné sur la résiduelle à 20 h |
| Débit mini des pompes | Vanne de recirculation ouvre < ~114 m³/h, ferme > ~227 m³/h |
| Réglage | Vannes en sortie d'échangeur + vanne de by-pass HCV-618 (débit total constant) |
| Mise en chauffe | Débit limité au début (choc thermique) |
| Remplissage piscine | RRA aspire à la bâche PTR (vanne 8812) → cuve → piscine du réacteur |
| Risque à modéliser | **Brèche inter-systèmes** : RRA exposé à la pression primaire hors enceinte |

---

### 4.4 Injection de sécurité — équivalent **RIS**

| Sous-système | Composants | Valeurs |
|---|---|---|
| **Accumulateurs ×4** (passif) | Eau borée + azote, 2 clapets en série, vanne motorisée d'isolement ouverte et **non alimentée** | ~38 m³ chacun dont ~25 m³ d'eau, ~1 900 ppm, **42–46 bar abs** |
| **Injection HP** | Pompes de charge (RCV) + réservoir de bore (BIT, ~3,4 m³) | Injectent jusqu'à la pression des soupapes |
| **Injection MP** | 2 pompes SI | ~97 m³/h à ~46 bar, hauteur à débit nul ~106 bar |
| **Injection BP** | 2 pompes RRA | Injectent sous ~14 bar, plusieurs centaines de m³/h |
| **Bâche PTR** (eau de rechargement) | Atmosphérique | ~1 660 m³, 2 000–2 500 ppm |
| **Puisards enceinte** | 2 aspirations, filtres | Recirculation long terme |

**Phases** :
1. **Injection directe** (aspiration PTR) — automatique sur signal IS.
2. **Recirculation branches froides** — au niveau bas PTR (**48 %**) : arrêt auto des pompes RRA, puis l'opérateur bascule l'aspiration sur les puisards, ouvre le RRI aux échangeurs RRA, et aligne le refoulement RRA vers l'aspiration des pompes de charge et SI (« piggy-back »).
3. **Niveau très bas PTR (17 %)** : arrêt auto des pompes d'aspersion, l'opérateur bascule leur aspiration sur les puisards.
4. **Recirculation branches chaudes** — ~24 h après : évite la précipitation du bore dans le cœur.

**Ordre d'injection** :
- Grosse brèche : accumulateurs d'abord, puis toutes les pompes.
- Petite brèche : HP → MP → accumulateurs → BP, au fil de la dépressurisation.

**Gavé-ouvert (feed & bleed)** : ultime moyen si plus de GV — injection HP + ouverture volontaire des PORV du pressuriseur.

---

### 4.5 Aspersion enceinte — équivalent **EAS**

- 2 pompes d'aspersion, aspiration PTR puis puisards, rampes d'aspersion, ajout de soude (additif).
- Démarrage auto sur **P enceinte très haute (~2,1 bar rel)** + séquenceur.
- Rôle : faire baisser P et T de l'enceinte, rabattre l'iode.

---

### 4.6 Vapeur principale — équivalent **VVP** (+ **GCT** contournement)

Par ligne vapeur (×4), dans l'ordre depuis le GV :

| # | Composant | Valeur / logique |
|---|---|---|
| 1 | Limiteur de débit (venturi) | Limite une brèche à ~1 220 kg/s par GV ; sert aussi à mesurer le débit |
| 2 | Prise vapeur turbopompe ASG | Vanne pneumatique, s'ouvre si perte de tension (sécurité positive) |
| 3 | Vanne de décharge à l'atmosphère (GCT-a / VDA selon palier) | ~10 % du débit nominal, **tarage ~79 bar**, pneumatique, repli fermé, secours azote |
| 4 | Soupapes de sûreté ×5 | Tarages étagés **~82 à ~86 bar**, 109 % du débit total à elles toutes |
| 5 | **Vanne d'isolement vapeur (VIV)** | Pneumatique, fermeture < 5 s (retard 0,5 s), réserve d'air 15 min |
| 6 | Clapet anti-retour vapeur | Protège en cas de VIV qui ne ferme pas |
| 7 | By-pass de VIV | Mise en chauffe / équilibrage |
| 8 | Purges haute pression | Fermées sur isolement vapeur |

Après les VIV : **collecteur commun** → turbine HP (vannes d'arrêt + réglage), sécheurs-surchauffeurs, turbines des pompes alimentaires, éjecteurs, vapeur des garnitures, **contournement condenseur (GCT-c)**.

**Contournement turbine (GCT-c)** : 12 vannes en 4 groupes ; mode « Tmoy » (sur rejet de charge / déclenchement turbine) ou mode « pression ». Interdit si condenseur indisponible (C-9) ou Tmoy très basse (P-12, sauf 1 groupe « refroidissement »).

**Évacuation de la résiduelle après AU** :
- Avec réseau : GV → GCT-c → condenseur.
- Sans réseau : GV alimentés par ASG → **vannes de décharge à l'atmosphère**.

**Vapeur auxiliaire** : chaudière auxiliaire au démarrage (garnitures, éjecteurs, évaporateurs bore).

---

### 4.7 Turbine, sécheurs-surchauffeurs, condenseur — équivalents **GRE**, **GSS**, **CVI**, **CRF**

- Turbine : 1 corps HP + 3 corps BP. Soutirages vers les réchauffeurs.
- **Sécheurs-surchauffeurs ×2** : séchage + 2 étages de surchauffe (soutirage HP puis vapeur vive).
- **Condenseur** : 3 caissons, pressions ~0,11 / 0,14 / 0,17 bar abs à pleine charge, pression mini à tenir en exploitation ~0,17 bar abs, **éjecteurs** (démarrage + maintien).
- **Disponibilité condenseur (C-9)** : au moins 1 pompe CRF en marche **et** pression condenseur < ~0,17 bar abs ; perdu si la pression monte à ~0,26 bar abs.
- **Circulation (CRF)** : pompes de circulation, eau de mer → condenseur.
- Déclenchement turbine : 4/4 vannes d'arrêt fermées ou 2/3 basse pression d'huile de déclenchement.
- Alternateur : 1 280 MVA, refroidi à l'hydrogène + stator à l'eau.

---

### 4.8 Poste d'eau — équivalents **CEX**, **ABP**, **ADG**, **APP**, **AHP**, **ARE**, **APG**

Ordre du circuit :

| # | Composant | Valeur / logique |
|---|---|---|
| 1 | Puits du condenseur | Régulation de niveau : appoint depuis la bâche de stockage, rejet vers celle-ci |
| 2 | Pompes d'extraction **CEX** ×2 (70 %) | ~2 500 m³/h, ~33 bar ; recirculation ouvre < 795, ferme > 1 590 m³/h |
| 3 | Déminéraliseurs du condensat (si en service) | By-pass auto si ΔP > ~4 bar |
| 4 | Injection chimique | Hydrazine (O₂), amine (pH) |
| 5 | Réchauffeurs BP ×5 étages **ABP** | 49 → 182 °C |
| 6 | Bâches + pompes de reprise des purges (≈ 1/3 du débit) | Puissance limitée à 90 % avec une seule pompe de reprise |
| 7 | Pompes alimentaires **APP** ×2 (70 %, turbopompes) | ~4 500 m³/h ; régulées sur ΔP aux vannes ARE |
| 8 | Réchauffeurs HP ×2 étages **AHP** | 182 → 203 → 227 °C |
| 9 | Vannes de régulation **ARE** (grand débit + petit débit) par GV | Régulation de niveau GV |
| 10 | Vannes d'isolement eau alimentaire | Fermeture < 16 s |
| 11 | Clapet + mesure de débit | — |

> Note : le parc français utilise une **bâche alimentaire dégazante (ADG)** entre BP et APP ; la centrale NRC dégaze dans le condenseur. Prévoir l'ADG comme option.

**Déclenchements d'une APP** : huile basse, survitesse, vide bas à l'échappement, température haute, refoulement > ~128 bar.
**Déclenchement des 2 APP** : IS, niveau GV très haut (69 %), aspiration basse (~14,5 bar abs).

**Isolement eau alimentaire** (fermeture ARE + isolements) : niveau GV très haut (P-14) **ou** IS **ou** (AU **et** Tmoy < 296 °C).

**Purges GV (APG)** : jusqu'à ~23 m³/h par GV, ballon de détente, déminéralisation, retour condenseur. **Isolées** par tout démarrage ASG.

**Pompe alimentaire de démarrage** (motopompe, ~230 m³/h) : utilisée au démarrage et à l'arrêt.

**Bâche de stockage d'eau (CST)** : ~1 700 m³, minimum ~905 m³ (2 h d'attente à chaud + 4 h de refroidissement jusqu'à 177 °C par ASG).

---

### 4.9 Alimentation de secours des GV — équivalent **ASG**

- Configuration conseillée pour le jeu (proche du parc français) : **1 turbopompe** (vapeur des GV, pas besoin d'alternatif) + **2 motopompes** (sur tableaux secourus A et B). Aspiration bâche ASG / CST.
- **Démarrage auto** : niveau très bas dans 1 GV, IS, perte des 2 APP, sous-tension d'un tableau secouru.
- Démarrage ASG → **isolement des purges GV**.
- Réglage du débit par vannes vers chaque GV.

---

### 4.10 Sources froides — équivalents **RRI**, **SEC**, **SRI**, **CRF**

**Chaîne** : composants « nucléaires » → **RRI** (circuit fermé, barrière) → échangeurs RRI/SEC → **SEC** (eau de mer) → mer.

| Circuit | Charges desservies |
|---|---|
| **RRI** | Échangeurs RRA, joints des pompes SI / aspersion / RRA, pompes primaires (barrière thermique + paliers), échangeur décharge RCV, échangeur décharge excédentaire, échangeur eau de joints, échangeurs piscine PTR, aéroréfrigérants enceinte, compresseurs effluents gazeux, évaporateurs |
| **SEC** (secouru) | Échangeurs RRI, diesels, réfrigérants des locaux des pompes de sauvegarde, réfrigérants d'huile des pompes, appoint de secours RRI / piscine / ASG |
| **SRI** (conventionnel) | Paliers, alternateur, auxiliaires salle des machines |

- RRI : **vase d'expansion** (niveau → détection de fuite entrante), **mesure d'activité**.
- Sur IS : RRI et SEC basculent en configuration accident + démarrage des pompes.
- Sur **isolement phase B** : fermeture du RRI vers les pompes primaires.

---

### 4.11 Piscine combustible — équivalent **PTR** (partie piscine)

- Refroidissement de la piscine (échangeur sur RRI), purification, maintien de la transparence.
- Pas de vidange en fond, **casse-siphons** sur les tuyauteries.
- Hauteur d'eau mini au-dessus du combustible : ~5,3 m (protection biologique).
- Transfert d'eau bâche PTR ↔ piscine réacteur via RRA.

---

### 4.12 Électricité — équivalents **LGx** (normal), **LHx** (secouru), diesels, **LBx** (continu), onduleurs

**Architecture (transposée en tensions françaises)**

```
Réseau 400 kV ──[transfo principal]── Alternateur 20–22 kV
     │                                    │
     │                         [transfo de soutirage]
[transfos auxiliaires]                    │
     └─────────► 6,6 kV normal (2 tableaux, non secourus) ──► pompes primaires, CEX, CRF, chaufferettes PZR, pompe volumétrique…
                       │
                       └──► 6,6 kV secourus voie A / voie B ◄── Diesel A / Diesel B
                                 │
                                 ├─► pompes de charge, SI, RRA, aspersion, RRI, SEC, motopompes ASG
                                 └─► 380 V secouru ─► chargeurs ─► 125 V cc (batteries) ─► onduleurs ─► 220 V ca ondulé (contrôle-commande, protection)
```

| Élément | Valeur / logique |
|---|---|
| Basculement rapide | Sur déclenchement de l'alternateur : auxiliaires transférés automatiquement sur les transfos auxiliaires (réseau) |
| Diesels | ~4,4 MW chacun, **démarrage + prise de charge ≤ 10 s** |
| Démarrage auto diesel | IS, sous-tension du tableau secouru (< ~62 % pendant 1 s), tension dégradée (< ~93 % pendant 55 s, 4 s si IS) |
| Couplage diesel | Disjoncteur diesel ne se ferme que si : tableau hors tension, arrivée normale ouverte, diesel à vitesse et tension, pas de verrouillage |
| Délestage | Sur sous-tension : ouverture de toutes les grosses charges du tableau secouru avant prise par le diesel |
| **Séquenceur accident** (avec IS) | t+2 s pompe de charge + réfrigérants · t+6,5 s pompe SI · t+11 s aspersion (si P enceinte très haute) · t+15,5 s RRA · t+20 s RRI · t+24,5 s SEC · t+29 s aéroréfrigérants enceinte · t+40 s aspersion (verrouillage) |
| **Séquenceur arrêt** (sans IS) | t+2 s pompe de charge · t+6,5 s RRI · t+11 s SEC |
| Batteries 125 V | Voie A : 2 h · voie B : 30 min sans chargeur |
| Onduleurs | Basculement statique automatique sur secours en cas de défaut ; pas de retour automatique |
| Pompes primaires | Sous-tension 6,6 kV normal (< 68,6 % sur 2/2 tableaux) ou sous-fréquence → AU ; sous-fréquence → déclenchement des pompes |

> Option « post-Fukushima » : diesel d'ultime secours, turbo-alternateur de secours (alimente le contrôle-commande minimal et une pompe d'injection aux joints).

---

### 4.13 Air comprimé — équivalents **SAR** (régulation), **SAP**

- Alimente toutes les vannes pneumatiques.
- **Perte d'air** → chaque vanne pneumatique va en position de repli, sauf réserves locales : PORV pressuriseur 10 min, VIV 15 min, vannes vapeur turbopompe ASG (3 manœuvres / 20 min), vannes de décharge atmosphère (secours azote).
- Scénario pédagogique majeur : la perte d'air ferme l'aspersion pressuriseur, change la charge RCV, etc.

---

### 4.14 Protection réacteur — équivalent **RPR**

#### Arrêts automatiques (AU)

| Signal | Logique | Seuil | Blocage / permissif |
|---|---|---|---|
| Manuel | 1/2 | — | — |
| Flux niveau source haut | 1/2 | 10⁵ c/s | Bloquable au-dessus de P-6 |
| Flux niveau intermédiaire haut | 1/2 | ≈ 25 % | Bloquable au-dessus de P-10 |
| Flux puissance haut, seuil bas | 2/4 | 25 % | Bloquable au-dessus de P-10 |
| Flux puissance haut, seuil haut | 2/4 | 109 % | Jamais bloqué |
| Variation rapide de flux + / − | 2/4 | ±5 % (constante 2 s) | Jamais bloqué |
| **ΔT surtempérature** | 2/4 | Seuil calculé (Tmoy, P, déséquilibre axial) | — |
| **ΔT surpuissance** | 2/4 | Seuil calculé (Tmoy, déséquilibre axial) | — |
| Pression pressuriseur basse | 2/4 | **129,6 bar** | Actif au-dessus de P-7 |
| Pression pressuriseur haute | 2/4 | **165,5 bar** | Jamais bloqué |
| Niveau pressuriseur haut | 2/3 | 92 % | Actif au-dessus de P-7 |
| Débit primaire bas | 2/3 par boucle | < 90 % | 1 boucle au-dessus de P-8 ; 2 boucles au-dessus de P-7 |
| Sous-tension tableaux pompes primaires | 1/2 sur 2/2 | 68,6 % | Au-dessus de P-7 |
| Sous-fréquence tableaux pompes primaires | 1/2 sur 2/2 | ≈ 96 % de la fréquence | Au-dessus de P-7, déclenche aussi les pompes |
| Disjoncteur pompe primaire ouvert | 2/4 pompes | — | Au-dessus de P-7 |
| Niveau GV très bas | 2/3 sur 1 GV | 11,5 % | — |
| Débit eau insuffisant | écart vapeur/eau + niveau bas (25,5 %) sur 1 GV | — | — |
| Déclenchement turbine | 4/4 vannes d'arrêt ou 2/3 huile | — | Au-dessus de P-7 (ou P-9) |
| Injection de sécurité | — | — | — |

Pré-alarmes ΔT (à 3 % du seuil) : **interdiction de retrait des grappes + baisse de charge turbine** (C-3 / C-4).

Équation du seuil ΔT surtempérature (pour le code) :
`ΔT_seuil = ΔT0 · [K1 − K2·(1+τ1·s)/(1+τ2·s)·(Tmoy − T') + K3·(P − P') − f1(ΔI)]`, avec T' ≈ 307 °C, P' ≈ 155 bar. Valeurs de K à régler pour que le seuil soit ~115–120 % de ΔT0 au nominal.

#### Permissifs (P) et verrous de conduite (C)

| Repère | Condition | Effet |
|---|---|---|
| P-4 | Disjoncteurs d'AU ouverts | Déclenche la turbine ; isole l'ARE si Tmoy < 296 °C ; permet le réarmement IS |
| P-6 | Niveau intermédiaire > 10⁻¹⁰ A | Autorise le blocage de l'AU niveau source |
| P-7 | Puissance < 10 % **et** charge turbine < 10 % | Bloque les AU « en puissance » |
| P-8 | Puissance < 39 % | Pas d'AU sur perte d'une seule boucle |
| P-9 | Puissance < 50 % | Pas d'AU sur déclenchement turbine (option) |
| P-10 | Puissance > 10 % (2/4) | Autorise le blocage des AU de démarrage |
| P-11 | P pressuriseur < 133 bar | Autorise le blocage de l'IS sur pression basse |
| P-12 | Tmoy < 289 °C | Autorise le blocage de l'IS sur débit vapeur haut ; bloque le contournement (sauf 1 groupe) |
| P-13 | Charge turbine < 10 % | Entrée de P-7 |
| P-14 | Niveau GV > 69 % (2/3 sur 1 GV) | Déclenche turbine + APP, ferme ARE et isolements |
| C-1 / C-2 | Flux intermédiaire > 20 % / flux puissance > 103 % | Interdit le retrait des grappes |
| C-5 | Charge < 15 % | Interdit le retrait auto des grappes |
| C-7 | Baisse de charge > 10 % en échelon ou > 5 %/min | Arme le contournement condenseur |
| C-8 | Turbine déclenchée | Arme le contournement (mode déclenchement turbine) |
| C-9 | Condenseur disponible | Autorise le contournement |
| C-11 | Groupe D > 223 pas | Stoppe le retrait auto |

**Règle générale** : un signal bloqué est **réactivé automatiquement** dès que la condition du permissif disparaît.

#### Signaux de sauvegarde

| Signal | Déclencheurs (seuils) | Actions |
|---|---|---|
| **Injection de sécurité (IS)** | P pressuriseur < **125,6 bar** (2/3, bloquable sous P-11) ; P enceinte > **0,24 bar rel** (2/3) ; écart de pression entre lignes vapeur > **6,9 bar** ; débit vapeur haut + (P vapeur < 42,4 bar **ou** Tmoy < 289 °C) ; manuel | AU ; démarrage pompes charge/SI/RRA ; aspiration charge sur PTR ; **isolement phase A** ; démarrage **ASG** ; **isolement ARE** + déclenchement APP + turbine ; **démarrage diesels** (à vide si réseau présent) ; RRI/SEC en configuration accident ; isolement ventilation salle de commande et enceinte. **Réarmement** seulement après ~60 s **et** AU (P-4). Après réarmement : plus d'IS auto jusqu'à refermeture des disjoncteurs d'AU (manuel toujours possible). |
| **Isolement phase A** | Toute IS ; manuel | Ferme toutes les traversées non essentielles (sauf RRI des pompes primaires et lignes vapeur) |
| **Aspersion enceinte + isolement phase B** | P enceinte > **2,07 bar rel** (2/4) ; manuel | Pompes d'aspersion, rampes, additif ; ferme le RRI des pompes primaires |
| **Isolement vapeur** | P enceinte très haute ; débit vapeur haut + (P vapeur basse **ou** Tmoy très basse) | Ferme VIV, by-pass VIV, purges |
| **Isolement eau alimentaire** | IS ; niveau GV très haut ; AU + Tmoy < 296 °C | Ferme ARE et isolements ; déclenche APP |
| **Démarrage ASG** | Niveau GV très bas ; perte des 2 APP ; sous-tension tableau secouru (< ~62 %, 1,1 s) ; IS | Démarre les pompes ASG, isole les purges GV |

---

### 4.15 Régulations à modéliser (PID simples)

| Régulation | Mesure | Actionneur | Comportement |
|---|---|---|---|
| Pression pressuriseur | P PZR | Chaufferettes proportionnelles, tout-ou-rien, aspersion, PORV | Paliers : TOR ON si P < consigne − 1,7 bar ; aspersion progressive au-dessus de consigne + ~1,7 bar ; PORV à ~162 bar *(valeurs à ajuster)* |
| Niveau pressuriseur | Niveau PZR vs programme(Tmoy) | Débit de charge (FCV-121) | Programme ~25 % à vide → ~60 % à pleine charge *(indicatif)* ; < 17 % : isolement décharge + chaufferettes coupées |
| Niveau GV (3 éléments) | Niveau + débit vapeur + débit eau | Vannes ARE + vitesse APP | Gonflement / tassement à gérer |
| Contournement | Tmoy vs Tref, ou P vapeur | Vannes GCT-c | Modes « Tmoy » / « pression » |
| Température moyenne | Tmoy vs Tref(charge) | Grappes (ou bore) | Simplifié |
| Pression décharge RCV | P aval échangeur | PCV-131 | Consigne ~24,5 bar |
| Niveau VCT | Niveau | LCV-112A + appoint REA | Déviation / appoint auto |
| Niveau puits condenseur | Niveau | Appoint / rejet CST | — |
| Turbine | Charge demandée | Vannes de réglage | Rampe max ~5 %/min, échelon 10 % |

---

### 4.16 Cœur « boîte noire »

Le cœur n'est **qu'une source de chaleur** pilotée simplement :

- **Puissance neutronique** : modèle 1 groupe de neutrons retardés (ou premier ordre) :
  `dP/dt = (ρ − β)/Λ · P + λ·C` ; `dC/dt = β/Λ · P − λ·C`, avec β ≈ 650 pcm, Λ ≈ 2·10⁻⁵ s, λ ≈ 0,08 s⁻¹.
- **Réactivité** : ρ = ρ_grappes + ρ_bore + α_mod·(Tmoy − Tref) + α_Doppler·(Tcomb − Tref) (+ xénon optionnel).
  Ordres de grandeur : α_mod ≈ −20 pcm/°C, α_Doppler ≈ −2,5 pcm/°C, bore ≈ −10 pcm/ppm.
- **AU** : insertion des grappes en ~2 s → ρ ≈ −5 000 pcm.
- **Puissance résiduelle** (Way-Wigner) :
  `P_res / P0 = 0,0622 · [t^(−0,2) − (t + T_fonct)^(−0,2)]`, t en s.
  Ordres de grandeur : ~6 % à t = 1 s, ~1 % à 1 h, ~0,5 % à 20 h.
- **Température combustible / gaine** : 1 nœud thermique chacun ; on calcule une **marge à l'ébullition critique** simplifiée (fonction de P, Tsortie, débit, puissance) pour le score.
- Option : bouton « mode expert » pour activer le xénon et les 6 groupes de neutrons retardés plus tard.

---

## 5. États standards du réacteur et transitions

| État | Primaire | Évacuation de la chaleur | Conditions pour y entrer |
|---|---|---|---|
| **RP** – en production | 155 bar, Tmoy 292 → 307 °C | GV → turbine → condenseur | Critique, P-7 franchi, ARE en auto |
| **AN/GV** – arrêt à chaud sur GV | 155 bar → dépressurisation progressive | GV → GCT-c (ou atmosphère), alimentés par ARE/pompe de démarrage/ASG | AU ou baisse de charge ; sous-critique et bore suffisant |
| **AN/RRA** – arrêt sur RRA | ≤ ~30 bar, ≤ ~177 °C | RRA → RRI → SEC | Blocage IS (P-11, P-12) fait ; accumulateurs isolés ; P et T sous le verrou RRA |
| **Arrêt à froid** | < 93 °C | RRA | — |
| **API** – arrêt pour intervention | Primaire ouvert ou dépressurisé | RRA (attention aux niveaux bas, « plage de travail basse ») | Pompes primaires arrêtées, couvercle en place |
| **APR** – arrêt pour rechargement | Cuve ouverte, piscine remplie | RRA + piscine | Remplissage piscine par RRA depuis PTR |
| **RCD** – cœur déchargé | — | Piscine BK → PTR → RRI → SEC | Tout le combustible en piscine |

Le jeu affiche en permanence l'état courant et la **check-list des conditions** pour passer à l'état voisin.

---

## 6. Scénarios à fournir (fichiers YAML)

Chaque scénario : état initial, pannes (avec instant), objectifs, critères d'échec, durée.

| # | Scénario | Ce que ça apprend |
|---|---|---|
| S0 | Bac à sable à 100 % | Explorer |
| S1 | Mise en service RCV depuis l'arrêt | Ordre imposé par les verrous |
| S2 | Passage RP → AN/GV → AN/RRA | Blocages P-11/P-12, isolement accumulateurs, verrou RRA, vitesse de refroidissement |
| S3 | Déclenchement turbine à 100 % | AU, contournement, gonflement/tassement GV |
| S4 | Perte totale d'eau alimentaire normale | ASG, niveau GV très bas |
| S5 | Perte des alimentations électriques externes | Basculement, diesels, séquenceur, circulation naturelle, vannes de décharge à l'atmosphère |
| S6 | **Perte totale des sources électriques** | Batteries qui se vident, joints pompes primaires, turbopompe ASG, temps compté |
| S7 | Petite brèche primaire (∅ 2–5 cm) | IS, ordre d'injection, bascule en recirculation |
| S8 | PORV du pressuriseur bloquée ouverte | Vanne d'isolement, bâche de décharge qui crève (disques de rupture) |
| S9 | Rupture de tube GV | IS, isolement du GV affecté, activité vapeur |
| S10 | Brèche vapeur | Isolement vapeur, surrefroidissement, retour de réactivité |
| S11 | Perte RRI | Pompes primaires à arrêter en ~2 min, fuite barrière thermique |
| S12 | Perte d'air comprimé | Positions de repli des vannes pneumatiques |
| S13 | Dilution intempestive à l'arrêt | Borication d'urgence |
| S14 | Perte RRA en API à niveau bas | Perte de la source froide à l'arrêt |

---

## 7. Interface (schématique, simple)

- **Barre du haut** : temps simulé, accélération, état standard, puissance, P/T primaire, P vapeur, niveau PZR, niveaux GV, tension des tableaux, voyants AU / IS / phase A / phase B.
- **Onglets synoptiques** (SVG) : Primaire · RCV/REA · RRA · RIS/EAS · Vapeur/Turbine · Poste d'eau · ASG · RRI/SEC · Électricité · Logique (permissifs, signaux, seuils).
- **Codes couleurs** : vanne ouverte = rempli, fermée = contour ; pompe en marche = vert, arrêt = gris, défaut = rouge clignotant ; tableau sous tension = trait épais.
- **Clic sur un équipement** : panneau avec état, commande, conditions de manœuvre (✓ / ✗ + raison), alimentation électrique, réserve d'air.
- **Alarmes** : liste horodatée, acquittement, priorité.
- **Courbes** : sélection de 1 à 6 variables, fenêtre glissante.
- **Débrief** de fin de scénario : chronologie des événements, actions du joueur, score.

---

## 8. Score et pédagogie

- **Fonctions de sûreté** suivies en continu (vert / orange / rouge) :
  - Sous-criticité (puissance, réactivité, bore).
  - Refroidissement du cœur (marge à la saturation en sortie cœur, T gaine).
  - Source froide (niveaux GV, débit ASG, RRA).
  - Intégrité du primaire (P vs courbes P-T, vitesse de refroidissement).
  - Confinement (P enceinte, isolements, activité).
  - Inventaire primaire (niveau PZR, niveau cuve).
- **Barrières** : gaine (T gaine > 1 200 °C = perdue), primaire (brèche, dépassement des soupapes), enceinte (P > P calcul).
- Pénalités : déclenchements évitables, sollicitation des soupapes, dépassement des vitesses de refroidissement, actions interdites forcées.

---

## 9. Hypothèses de modélisation physique

### 9.1 Volumes
- Volumes monophasiques liquides (boucles primaires, tuyauteries) : masse + énergie, T homogène par volume. **Nodalisation conseillée** : par boucle, 4 nœuds (branche chaude, GV côté primaire, branche froide, pompe) + cuve en 3 nœuds (descente, cœur, plénum supérieur).
- Volumes diphasiques (pressuriseur, GV secondaire, condenseur, PRT, ballon de purges) : masse d'eau + masse de vapeur, **équilibre de saturation** (P = Psat(T)) via CoolProp. Le pressuriseur peut avoir 2 zones (liquide sous-refroidi / vapeur) en option.
- Bâches à surface libre : niveau = f(volume), P = P_atm ou P_gaz (gaz parfait pour l'azote / l'hydrogène).

### 9.2 Hydraulique
- Chaque circuit = graphe. Débit dans une branche :
  `ΔP_pompes − ΔP_frottement(Q) − ΔP_vannes(Q, ouverture) + ΔP_gravité = P_aval − P_amont`.
- Résolution **quasi statique à chaque pas** (Newton sur le réseau ou itération de point fixe), avec débits limités aux bornes physiques. Les clapets sont traités comme des vannes à ouverture conditionnelle.
- Inertie des pompes : `J·dω/dt = C_moteur − C_hydraulique` → ralentissement réaliste des pompes primaires (volant).
- **Circulation naturelle** : moteur = ρ_froid − ρ_chaud × g × Δz (Δz GV/cœur ~10 m).

### 9.3 Échangeurs
- ε-NTU avec UA nominal recalé pour retrouver le point de fonctionnement nominal ; UA ∝ (débit)^0,8 en option.
- GV : `Q = UA·(Tmoy_primaire − Tsat(P_GV))`.

### 9.4 Brèches
- Débit critique simplifié : `G ≈ Cd·√(2·ρ·ΔP)` (liquide) ; pour la vapeur, débit sonique ~ `0,6 · A · P / √(R·T)`.

### 9.5 Enceinte
- 1 volume air + vapeur, puits thermiques simplifiés (masse de béton / acier), aspersion qui condense.

---

## 10. Feuille de route (chaque étape = jouable + testée)

| Version | Contenu | Test d'acceptation |
|---|---|---|
| **V0** | Moteur générique + boucle secondaire seule (GV alimenté par une chaleur imposée → VVP → turbine → condenseur → CEX → APP → ARE) + UI 1 synoptique | Équilibre stable à 100 % ; fermer une ARE fait baisser le niveau GV et tasser/gonfler correctement |
| **V1** | Primaire 4 boucles + pressuriseur + cœur boîte noire + régulations P/niveau PZR | Stable à 100 % ; échelon de charge −10 % encaissé sans AU |
| **V2** | RCV + REA + RRA + RRI + SEC + logique d'états standards | Scénario S2 (RP → AN/RRA) faisable de bout en bout |
| **V3** | Électricité complète + diesels + séquenceurs + air comprimé | S5, S6, S12 jouables |
| **V4** | RIS + EAS + enceinte + brèches + tous les signaux | S7 à S11 jouables |
| **V5** | Score, débrief, sauvegarde/rechargement, éditeur de scénarios | — |

---

## 11. Règles pour le code

- Python typé (`dataclasses`, `typing`), docstrings courtes en français, unités dans les noms (`p_bar`, `t_c`, `q_m3h`, `m_kg`).
- **Aucune valeur numérique en dur** dans le code : tout dans `config/plant.yaml`.
- Chaque composant testable seul (tests unitaires).
- Chaque scénario a un **test d'intégration** qui vérifie la réponse automatique attendue (ex. S3 : AU dans les 2 s, contournement ouvert, pas d'IS).
- Tests de cohérence physique : conservation de la masse par circuit fermé (< 0,1 %/h de dérive), bilan d'énergie à l'équilibre.
- Journal d'événements horodaté (alarmes, changements d'état, actions joueur).

---

## 12. Correspondance NRC ↔ EDF (indicatif)

| Fonction | NRC (Westinghouse) | EDF (REP) |
|---|---|---|
| Circuit primaire | RCS | RCP |
| Contrôle chimique et volumétrique | CVCS | RCV |
| Appoint eau / acide borique | Reactor Makeup | REA |
| Traitement effluents primaires | Boron Recycle | TEP |
| Refroidissement à l'arrêt | RHR | RRA |
| Injection de sécurité | ECCS / SI | RIS |
| Aspersion enceinte | Containment Spray | EAS |
| Bâche d'eau de rechargement + piscine | RWST + SFP cooling | PTR |
| Vapeur principale | Main Steam | VVP |
| Contournement turbine | Steam Dumps | GCT-c |
| Décharge atmosphère GV | SG PORV | GCT-a / VDA |
| Alimentation normale GV | Main Feedwater | ARE |
| Pompes alimentaires | Main Feed Pumps | APP |
| Réchauffeurs BP / HP | LP / HP heaters | ABP / AHP |
| Extraction condensat | Condensate | CEX |
| Vide condenseur | Air ejectors | CVI |
| Circulation | Circulating Water | CRF |
| Purges GV | SG Blowdown | APG |
| Alimentation de secours GV | AFW | ASG |
| Réfrigération intermédiaire | CCW | RRI |
| Eau brute secourue | Service Water | SEC |
| Sécheurs-surchauffeurs | MSR | GSS |
| Protection réacteur | RPS / SSPS | RPR |
| Commande grappes | Rod Control | RGL |
| Instrumentation nucléaire | Excore NIS | RPN |
| Instrumentation interne cœur | Incore | RIC |
| Air de régulation | Instrument Air | SAR |
| Mesure de radioactivité | Radiation Monitoring | KRT |
| Tableaux 6,6 kV secourus | 4,16 kV ESF buses | LHA / LHB |
| Diesels | EDG | LHP / LHQ |

---

## 13. Hors périmètre (volontairement)

- Neutronique 3D, distribution de puissance, gestion du combustible.
- Valeurs de réglage réelles d'une tranche EDF, procédures (consignes de conduite, RGE).
- Chimie détaillée (lithium, pH, activité), effluents détaillés.
- Thermo-hydraulique type code de sûreté (CATHARE, RELAP).

---

## 14. Sources

- USNRC, *Westinghouse Technology Systems Manual* (R304P), index : https://www.nrc.gov/docs/ML1122/ML11221A368.html
  - 3.2 Reactor Coolant System : https://www.nrc.gov/docs/ML1122/ML11223A213.pdf
  - 4.1 Chemical and Volume Control System : https://www.nrc.gov/docs/ML1122/ML11223A214.pdf
  - 5.1 Residual Heat Removal : https://www.nrc.gov/docs/ML1122/ML11223A219.pdf
  - 5.2 Emergency Core Cooling Systems : https://www.nrc.gov/docs/ML1122/ML11223A220.pdf
  - 6.0 Electrical Distribution : https://www.nrc.gov/docs/ML1122/ML11223A234.pdf
  - 7.1 Main and Auxiliary Steam : https://www.nrc.gov/docs/ML1122/ML11223A244.pdf
  - 7.2 Condensate and Feedwater : https://www.nrc.gov/docs/ML1122/ML11223A246.pdf
  - 12.2 Reactor Trip Signals : https://www.nrc.gov/docs/ML1122/ML11223A301.pdf
  - 12.3 ESF Actuation Signals : https://www.nrc.gov/docs/ML1122/ML11223A310.pdf
  - 14.4–14.7 Cooling Water (diapos) : https://www.nrc.gov/docs/ML1122/ML11223A410.pdf
  - Chapitres utiles à lire ensuite : 5.4 (enceinte), 5.8 (ASG), 10.x (régulations primaires), 11.1 (niveau GV), 11.2 (contournement), 13 (air), 19 (conduite).
- IAEA, *Reactor Simulator Development* (TCS-12), équations de base d'un simulateur : https://www-pub.iaea.org/MTCD/Publications/PDF/TCS-12.pdf
- EDF / AREVA, *UK EPR Pre-Construction Safety Report* (pour une future variante EPR) : https://www.edfenergy.com/media/20704/download
