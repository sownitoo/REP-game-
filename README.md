# Mini-Centrale REP — simulateur pédagogique

Jeu / simulateur **schématique** d'une centrale REP 4 boucles : circuits, lignages de vannes,
automatismes et thermo simple. Spécification de référence : [`SPEC_simulateur_REP.md`](SPEC_simulateur_REP.md).

> Centrale **générique** à but pédagogique (ordres de grandeur des manuels publics USNRC).
> Ce ne sont **pas** des valeurs, réglages ou consignes EDF.

## Lancer (une commande)

```bash
pip install -r requirements.txt && python -m sim.server
```

Ouvrir ensuite <http://127.0.0.1:8000>. Python ≥ 3.11. Variables optionnelles : `REP_HOTE`, `REP_PORT`.
(Un mode « navigateur » sans serveur existe aussi — `web/` + `web/sim_bundle.zip`, Pyodide — voir `web/worker.js`.)

## Se déplacer dans l'interface

| Geste | Effet |
|---|---|
| Molette / pincer | zoom (au curseur) ; **plus on zoome, plus il y a de détails** |
| Glisser | se déplacer · touches + − 0 et flèches · boutons + − ⤢ en bas à droite |
| Clic sur un équipement | panneau de commande (conditions ✓/✗ seulement si une action est bloquée) |
| **Double-clic sur la cuve** | **vue du cœur** (onglet Cœur) |
| Badge d'état en haut | état standard + check-list pour passer à l'état suivant |
| Survol d'un équipement | **fiche** : nom, type, circuit, rôle (aussi en tête du panneau au clic) |
| Survol d'un sigle | **décomposition** (RCV = R Réacteur · CV Contrôle chimique et Volumétrique) et rôle |
| ☰ | scénarios (avec fiche de conduite), sauvegarde, chargement, **glossaire des sigles**, **⚠ pannes (formateur)** |
| Espace / Échap | pause / fermer le panneau |

## Version actuelle : V4

| Onglet | Contenu |
|---|---|
| **Vue d'ensemble** | toute la centrale en un schéma, rangée par bâtiment (réacteur, auxiliaires nucléaires, salle des machines, électricité, mer) ; flux reliés ; bordure = état du circuit ; **clic = onglet détaillé** |
| **Primaire** | vue de dessus : cuve au centre (carte des 193 assemblages + grappes), 4 boucles en étoile, PZR, renvois RCV / RRA |
| **Cœur** | carte du cœur (nappe de puissance illustrative), vue axiale des groupes R / G / S, bilan de réactivité, pilotage des grappes et du bore, **vue neutronique** (⚛) |
| Secondaire · ASG | vapeur, turbine, condenseur, poste d'eau ; alimentation de secours |
| **RCV · REA** | charge (pompes, FCV-121, joints), décharge (LCV-459/460, orifices, CV-8152), VCT, PTR, appoint eau / bore |
| **RRA · RRI · SEC** | 2 trains RRA (verrou 30 bar, fermeture auto 41 bar), boucle RRI, eau de mer, accumulateurs |
| **RIS · EAS · Enceinte** | PTR et puisards, injection HP (charge par la BIT) / MP / BP (pompes RRA), aspersion, enceinte (pression, température, puisards), PRT et son disque, brèches, niveau cuve |
| **Électricité · Air** | schéma unifilaire : réseau, alternateur, TA/TS, tableaux LG/LH, diesels, séquenceur, batteries 125 V, air comprimé |
| Logique · Courbes · Journal | permissifs (dont P-11), IS (signal), seuils ; 1 à 6 courbes ; chronologie |

| Modèle | Détail |
|---|---|
| Cœur | cinétique 1 groupe (saut prompt), Doppler, modérateur (coefficient qui s'affaiblit à froid), **bore dynamique**, grappes R (régulation), **G (compensation)**, S (arrêt), puissance résiduelle, marges d'arrêt |
| Primaire | 4 boucles + cuve, pompes, circulation naturelle, GV ε-NTU, **branches RRA** dans le même réseau |
| RCV / REA | débit dispo des pompes de charge, décharge ∝ √ΔP, VCT (niveau, bore), PTR, borication / dilution / auto / urgence |
| RRA, RRI, SEC | échangeurs à contre-courant, RRI = un nœud thermique, perte RRI → défaut des pompes primaires |
| Logique | AU, **IS** (P PZR basse, P enceinte haute, écart vapeur, débit vapeur haut), **isolement vapeur**, **phase A / B**, recirculation (PTR 48 % / 17 %), P-4 → P-14, C-x, états standards |
| Primaire saturé | vide dans la cuve : **P = Psat(eau la plus chaude)**, PZR qui monte quand la PORV crache (TMI), niveau cuve ; PZR plein d'eau : pression par compressibilité, décharge d'eau par les PORV |
| Brèches, enceinte | débit critique (sous-refroidi → saturé → vapeur quand les joints hydrauliques se vident), RTGV + activité, brèche vapeur ; enceinte air + vapeur, parois, puisards, aspersion ; PRT + disque |
| Électricité | délestage, diesels (10 s), séquenceurs arrêt / accident, batteries (2 h / 30 min), perte du 125 V |
| Air, joints | rupture du collecteur, vannes pneumatiques en repli ; fuite des joints PP sans injection ni RRI |

| Scénario (menu ☰) | Ce qu'il apprend |
|---|---|
| S2 RP → AN/RRA | blocages P-11, accumulateurs, bore, vitesse de refroidissement, RRA |
| S5 perte des alimentations externes | délestage, diesels, séquenceur, circulation naturelle, VDA |
| S6 perte totale des sources | batteries, turbopompe ASG, joints, remettre le diesel A en service à temps |
| S12 perte d'air comprimé | positions de repli, AU, ASG, isoler la fuite |
| **S7** petite brèche primaire (5 cm) | IS, ordre HP puis MP, plateau ~80 bar, puisards, recirculation, arrêter l'IS à temps |
| **S8** PORV bloquée ouverte | vanne d'isolement, primaire qui bout, niveau PZR trompeur (TMI), disque de la PRT |
| **S9** rupture de tube de GV | activité du GV, isolement (VIV, ASG), égaliser les pressions |
| **S10** brèche vapeur (fin de cycle) | IS sur P enceinte, isolement vapeur, surrefroidissement, **retour critique**, aspersion |
| **S11** perte du RRI | arrêter les pompes primaires en moins de 2 min |

## Scénario S2 : de RP à AN/RRA (fiche résumée, détail dans ☰)

1. AU manuel → AN/GV. GCT-c en mode pression ; garder PP2 et PP3 (aspersion).
2. REA → *Borication* ~12 m³ (bore > bore d'arrêt à froid, affiché dans l'onglet Cœur).
3. Refroidir ~30 °C/h en baissant la consigne GCT-c ; dépressuriser en gardant ~45 °C de sous-refroidissement.
4. Sous P-11 : RPR → *Bloquer l'IS*. Vers 100 bar : fermer `ACC1..4_ISOL`.
5. Sous 30 bar et 177 °C : ouvrir `RRA_ASP*`, démarrer `RRA_P1/P2`, `RRI_P2`, `SEC_P2` → AN/RRA, puis arrêt à froid.

## Prise en main (V1, toujours valable)

1. **AU manuel** (onglet Cœur ou `RPR`) : grappes en 2 s, puissance ~8 % (saut prompt) puis décroissance.
2. **Échelon −10 %** : turbine → *Consigne (MW)* `1020`. Les grappes s'insèrent, pas d'AU.
3. **Déclenchement turbine** : AU par P-7, P PZR ~139 bar, niveau PZR ~29 %.
4. **Perte d'une pompe primaire** : `PP1` → *Arrêter*. AU débit bas en 2 s, boucle 1 à ≈ −15 %.
5. **Perte totale ARE** : `ARE*_GD/PD` en manu à 0 %. AU, l'ASG démarre.
6. **Circulation naturelle** : après un déclenchement, arrêter les 4 PP, GCT-c en mode pression.

## Tests

```bash
python -m pytest              # tout (≈ 8 min, dont S2, S5, S6, S7 à S10 de bout en bout)
python -m pytest -m "not lent"  # sans les longs transitoires
```

Le détail des critères d'acceptation et des chiffres obtenus est dans [`CHANGELOG.md`](CHANGELOG.md).

## Organisation

```
config/plant.yaml        toutes les valeurs numériques (# HYPOTHESE = absente de la spec)
config/etats/rp100.json  état initial stabilisé RP 100 %
sim/core/                réseau hydraulique (Newton), horloge, journal/alarmes, historique
sim/components/          pompe, vannes, clapet, soupape, bâche, volume diphasique, capteur, PI
sim/thermo/              tables eau/vapeur pré-calculées (CoolProp IF97, config/tables_eau.json)
sim/core_model/          cœur boîte noire : neutronique, grappes, puissance résiduelle
sim/systems/             primaire (rcp), pressuriseur (+ vide primaire), RCV/REA, RRA, RRI/SEC, accumulateurs,
                         RIS, enceinte + PRT, brèches, ASG, GV, VVP, turbine, GCT-c, condenseur, poste d'eau,
                         air comprimé, joints des PP
sim/electrical/          réseau, tableaux, diesels, séquenceurs, batteries
sim/scenarios/           scénarios (YAML), pannes programmées, pupitre formateur
sim/logic/               permissifs, AU, IS, automatismes, régulations, verrous, états standards
sim/plant.py             assemblage + pas de calcul (ordre du §2.3 de la spec)
sim/interface.py         protocole JSON commun aux deux modes
sim/server.py            mode local : FastAPI + WebSocket
sim/navigateur.py        mode navigateur : point d'entrée Pyodide
web/                     page HTML/SVG/JS vanilla : zoom.js, synoptics/, coeur_vue.js, neutrons.js
tests/                   unitaires + acceptation
```

Outils :

- `python -m sim.tools.etat_initial` régénère `config/etats/rp100.json` (à relancer après modification du YAML).
- `python -m sim.tools.hypotheses > docs/HYPOTHESES.md` liste toutes les hypothèses.
- `python -m sim.tools.paquet_web` régénère `web/sim_bundle.zip` (mode navigateur).
- `python -m sim.tools.tables_eau` régénère les tables eau/vapeur (seul outil qui a besoin de CoolProp).

Dépendances à l'exécution : aucune hors bibliothèque standard (PyYAML si présent ; sinon la config JSON du paquet).
FastAPI/uvicorn pour le mode local, CoolProp seulement pour régénérer les tables.
