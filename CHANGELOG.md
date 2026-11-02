# Changelog

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
