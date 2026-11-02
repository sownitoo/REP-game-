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

## Version actuelle : V0 (boucle secondaire)

Quatre GV chauffés par une **source imposée** (elle remplace le primaire jusqu'en V1) →
vapeur (VIV, VDA, soupapes) → turbine + alternateur → condenseur (CRF, puits, CST) →
CEX → réchauffeurs BP → reprise des purges → APP → réchauffeurs HP → ARE → GV.

| Quoi | Détail |
|---|---|
| Manœuvres | pompes (marche/arrêt, vitesse), vannes (ouvrir/fermer, auto/manu, position), turbine (déclencher, réarmer, vitesse, couplage, charge), source (auto/manu, puissance), AU manuel et réarmements |
| Automatismes | AU (niveau GV très bas 2/3, déclenchement turbine au-dessus de P-7), P-4, P-7, P-14, C-9, isolement ARE, déclenchements turbine / APP / CEX, recirculation CEX |
| Régulations | niveau GV 3 éléments (PD + GD), vitesse APP sur ΔP, charge turbine (rampe 5 %/min, échelon 10 %), GCT-c (pression), VDA, niveau du puits |
| Interface | synoptique SVG, onglet Logique, courbes (1 à 6 variables), journal, alarmes avec acquittement, accélération ×1/×10/×60/×600, sauvegarde/chargement JSON |
| Refus motivés | chaque commande affiche ses conditions ✓/✗, et tout refus dit pourquoi |

## Prise en main (5 manips)

1. **Fermer une ARE** : clic sur `GD` du GV1 → *Passer en MANU* → *Position* `0`, idem pour `PD`. Le niveau
   gonfle légèrement, puis chute et provoque l'AU sur niveau très bas vers 27 s.
2. **Échelon de charge** : clic sur la turbine → *Consigne (MW)* `1017` (−10 %). Tassement d'environ 3 % des niveaux GV, retour à la consigne.
3. **Déclenchement turbine** : *Déclencher*. On obtient l'AU, le GCT-c s'ouvre, le tassement descend à environ 26 % et l'ARE GD s'isole.
4. **Redémarrer** après déclenchement :
   1. `RPR` → *Réarmer l'AU* ;
   2. `SOURCE` → *Consigne* `250` MW ;
   3. turbine → *Réarmer*, *Consigne vitesse* `1500` ;
   4. *Coupler* une fois à ±0,5 % du synchronisme ;
   5. *Consigne (MW)* `60`, puis `SOURCE` → *auto* et monter la charge.
5. **Perte des CRF** : arrêter `CRF1` et `CRF2`. C-9 est perdu, la turbine déclenche sur vide dégradé, l'AU tombe et les VDA prennent le relais.

## Tests

```bash
python -m pytest              # tout (≈ 45 s)
python -m pytest -m "not lent"  # sans les longs transitoires
```

Le détail des critères d'acceptation et des chiffres obtenus est dans [`CHANGELOG.md`](CHANGELOG.md).

## Organisation

```
config/plant.yaml        toutes les valeurs numériques (# HYPOTHESE = absente de la spec)
config/etats/rp100.json  état initial stabilisé RP 100 %
sim/core/                réseau hydraulique (Newton), horloge, journal/alarmes, historique
sim/components/          pompe, vannes, clapet, soupape, bâche, volume diphasique, capteur, PI
sim/thermo/              tables eau/vapeur pré-calculées (CoolProp IF97)
sim/systems/             source V0, GV, VVP, turbine, GCT-c, condenseur, poste d'eau
sim/logic/               permissifs, AU, automatismes, régulations, verrous
sim/plant.py             assemblage + pas de calcul (ordre du §2.3 de la spec)
sim/server.py            FastAPI + WebSocket
web/                     page HTML/SVG/JS vanilla
tests/                   unitaires + acceptation
```

Outils :

- `python -m sim.tools.etat_initial` régénère `config/etats/rp100.json` (à relancer après modification du YAML).
- `python -m sim.tools.hypotheses` liste toutes les hypothèses, voir [`docs/HYPOTHESES.md`](docs/HYPOTHESES.md).
