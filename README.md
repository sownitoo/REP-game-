# Mini-Centrale REP — simulateur pédagogique

Jeu / simulateur **schématique** d'une centrale REP 4 boucles : circuits, lignages de vannes,
automatismes et thermo simple. Spécification de référence : [`SPEC_simulateur_REP.md`](SPEC_simulateur_REP.md).

> Centrale **générique** à but pédagogique (ordres de grandeur des manuels publics USNRC).
> Ce ne sont **pas** des valeurs, réglages ou consignes EDF.

## Deux façons de lancer

| Mode | Commande | Simulation | Accélération tenue |
|---|---|---|---|
| **Local (serveur)** | `pip install -r requirements.txt && python -m sim.server` puis <http://127.0.0.1:8000> | Python (CPython) côté serveur, WebSocket | ×600 → ≈ ×240 |
| **Navigateur (statique, Vercel)** | rien à installer : ouvrir le site | Python dans le navigateur (Pyodide, Web Worker) | ×60 tenu, ×600 → ≈ ×110 |

Python ≥ 3.11 pour le mode local. Variables optionnelles : `REP_HOTE`, `REP_PORT`.
Le code de simulation est **le même** dans les deux modes (`sim/interface.py`, même protocole JSON).

### Déployer sur Vercel (mode navigateur)

Le site est 100 % statique : le dossier `web/` + `web/sim_bundle.zip` (code `sim/` + config). Pas de build.

1. Sur vercel.com : **Add New… → Project** → importer le dépôt GitHub `REP-game-`.
2. Les réglages sont lus dans `vercel.json` (Framework : *Other*, pas de build, dossier de sortie `web`). Ne rien changer → **Deploy**.
3. Vercel déploie la branche de production (`main`). Chaque autre branche poussée obtient une URL de *preview*
   (utile pour tester une version avant de la fusionner dans `main`).

Après toute modification de `sim/` ou `config/`, régénérer le paquet avant de pousser
(un test échoue s'il n'est pas à jour) :

```bash
python -m sim.tools.paquet_web
```

Au premier chargement, le navigateur télécharge Pyodide (≈ 10 Mo, depuis cdn.jsdelivr.net, mis en cache ensuite).
Pour un test hors ligne : `index.html?pyodide=/chemin/vers/pyodide/`.

## Version actuelle : V1 (primaire + secondaire)

Cœur (boîte noire) → cuve → **4 boucles** (branche chaude → GV → pompe primaire → branche froide) + **pressuriseur**
→ 4 GV → vapeur → turbine → condenseur → poste d'eau → ARE → GV. **ASG** (2 motopompes + 1 turbopompe) en secours.

| Quoi | Détail |
|---|---|
| Cœur | cinétique ponctuelle 1 groupe (saut prompt), contre-réactions Doppler + modérateur + bore, grappes (courbe en S), chute en 2 s, puissance résiduelle (Way-Wigner) |
| Primaire | 3 nœuds cuve + 3 nœuds/boucle, débit par réseau hydraulique (pompes, antidévireur), circulation naturelle (thermosiphon), échange GV ε-NTU |
| Pressuriseur | équilibre liquide/vapeur, chaufferettes P + TOR, aspersion B2/B3, 2 PORV + isolements, 3 soupapes, expansion/contraction |
| RCV (simplifié) | charge régulée sur le niveau programmé du PZR, décharge en tout-ou-rien |
| Régulations | grappes en auto (Tmoy − Tref + écart de puissance), pression PZR, niveau PZR, niveau GV (ARE), ASG, GCT-c Tmoy / pression |
| Protections | AU : flux haut/bas, ΔT surtempérature et surpuissance, P PZR haute/basse, niveau PZR haut, débit primaire bas, niveau GV très bas, déclenchement turbine (P-7)… ; permissifs P-4, P-7, P-8, P-9, P-10, P-12, P-13, P-14, C-3/C-4, C-7, C-8, C-9, C-11 |
| Verrous | pompe primaire sans huile ou P < 29 bar, décharge RCV sans charge, grappes avec AU présent, blocage flux bas sans P-10… : refus motivés |
| Interface | onglets Primaire / Secondaire / ASG / Logique / Courbes / Journal, alarmes temporisées, ×1…×600, sauvegarde/chargement |

## Prise en main (6 manips)

Toutes partent de l'état RP 100 % (menu *S0 — Bac à sable à 100 %* pour revenir au départ).

1. **AU manuel** : clic sur `RPR` → *AU manuel*. Les grappes tombent en 2 s, la puissance chute à ~8 % (saut prompt)
   puis décroît, la turbine déclenche, le GCT-c (C-8) évacue la chaleur résiduelle. Tmoy → ~292 °C.
2. **Échelon −10 %** : clic sur la turbine → *Consigne (MW)* `1020`. Les grappes s'insèrent, Tmoy suit Tref, pas d'AU.
3. **Déclenchement turbine** : *Déclencher*. AU par P-7, P PZR descend vers ~138 bar, niveau PZR ~30 %, puis tout se stabilise.
4. **Perte d'une pompe primaire** : `PP1` → *Arrêter*. AU sur débit bas en ~2 s ; la boucle 1 tourne à l'envers (≈ −15 %, antidévireur).
5. **Perte totale ARE** : passer les 8 vannes `ARE*_GD/PD` en manu à 0 %. AU, puis l'ASG démarre (3 pompes, ~110 kg/s) et remonte les niveaux GV.
6. **Circulation naturelle** : après un déclenchement, arrêter les 4 `PP`, puis `GCT-c` → *mode pression*. Débit ≈ 5 % par boucle, marge à la saturation > 20 °C.

## Tests

```bash
python -m pytest              # tout (≈ 2 min)
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
sim/systems/             primaire (rcp), pressuriseur, ASG, GV, VVP, turbine, GCT-c, condenseur, poste d'eau
sim/logic/               permissifs, AU, automatismes, régulations, verrous
sim/plant.py             assemblage + pas de calcul (ordre du §2.3 de la spec)
sim/interface.py         protocole JSON commun aux deux modes
sim/server.py            mode local : FastAPI + WebSocket
sim/navigateur.py        mode navigateur : point d'entrée Pyodide
web/                     page HTML/SVG/JS vanilla (+ worker.js, transport.js, sim_bundle.zip)
tests/                   unitaires + acceptation
```

Outils :

- `python -m sim.tools.etat_initial` régénère `config/etats/rp100.json` (à relancer après modification du YAML).
- `python -m sim.tools.hypotheses > docs/HYPOTHESES.md` liste toutes les hypothèses.
- `python -m sim.tools.paquet_web` régénère `web/sim_bundle.zip` (mode navigateur).
- `python -m sim.tools.tables_eau` régénère les tables eau/vapeur (seul outil qui a besoin de CoolProp).

Dépendances à l'exécution : aucune hors bibliothèque standard (PyYAML si présent ; sinon la config JSON du paquet).
FastAPI/uvicorn pour le mode local, CoolProp seulement pour régénérer les tables.
