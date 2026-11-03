// Glossaire des sigles et fiches des équipements (rôle, type, circuit).
// Les trigrammes suivent la logique EDF : 1re lettre = famille (R réacteur, A alimentation des GV,
// V vapeur, C condenseur, G turbine, L électricité, S services…), puis la fonction.
// Les repères du type FCV-121 / LCV-459 sont des repères « Westinghouse » (FCV = vanne de réglage de débit,
// LCV = de niveau, HCV = manuelle, PCV = de pression, MO = motorisée, CV = vanne de réglage).
"use strict";

const Glossaire = {
  // ---------------------------------------------------------------- sigles (décomposition + rôle)
  SIGLES: {
    REP: { d: [["R", "Réacteur"], ["E", "à Eau"], ["P", "Pressurisée"]], nom: "Réacteur à eau pressurisée",
           role: "L'eau du primaire reste liquide (155 bar) ; elle chauffe un circuit secondaire qui fait la vapeur." },
    RCP: { d: [["R", "Réacteur"], ["CP", "Circuit Primaire"]], nom: "Circuit primaire principal",
           role: "Cuve, 4 boucles (branche chaude → GV → pompe → branche froide) et pressuriseur : évacue la chaleur du cœur." },
    RCV: { d: [["R", "Réacteur"], ["CV", "Contrôle chimique et Volumétrique"]], nom: "Contrôle chimique et volumétrique",
           role: "Ajuste la quantité d'eau du primaire (charge / décharge), purifie l'eau, injecte l'eau des joints des pompes primaires." },
    REA: { d: [["R", "Réacteur"], ["EA", "appoint en Eau et Acide borique"]], nom: "Appoint en eau et en bore",
           role: "Fournit l'eau déminéralisée et l'acide borique au RCV : borication, dilution, appoint automatique." },
    RRA: { d: [["R", "Réacteur"], ["RA", "Refroidissement à l'Arrêt"]], nom: "Refroidissement à l'arrêt",
           role: "Sous 30 bar et 177 °C, prend le relais des GV pour refroidir le primaire jusqu'à l'arrêt à froid." },
    RRI: { d: [["R", "Réacteur"], ["RI", "Réfrigération Intermédiaire"]], nom: "Réfrigération intermédiaire",
           role: "Boucle d'eau fermée entre les échangeurs nucléaires (RRA, RCV, pompes primaires) et l'eau de mer (SEC) : barrière contre les fuites radioactives." },
    SEC: { d: [["S", "Système auxiliaire"], ["EC", "Eau brute seCourue"]], nom: "Eau brute secourue",
           role: "Eau de mer (ou de rivière) qui refroidit le RRI ; c'est la source froide des systèmes de sauvegarde." },
    RIS: { d: [["R", "Réacteur"], ["IS", "Injection de Sécurité"]], nom: "Injection de sécurité",
           role: "Réinjecte de l'eau borée dans le primaire en cas de brèche : HP (pompes de charge par la BIT), MP (pompes IS), BP (pompes RRA), accumulateurs ; puis recirculation sur les puisards." },
    EAS: { d: [["E", "Enceinte"], ["AS", "ASpersion"]], nom: "Aspersion de l'enceinte",
           role: "Pulvérise de l'eau borée en haut de l'enceinte : la vapeur se condense, la pression baisse (démarrage > 2,07 bar rel)." },
    RDP: { d: [["R", "Réservoir"], ["D", "de Décharge"], ["P", "du Pressuriseur"]], nom: "Réservoir de décharge du pressuriseur",
           role: "Recueille et condense la vapeur des PORV et soupapes du PZR ; disque de rupture à 8 bar vers l'enceinte. En anglais : PRT (Pressurizer Relief Tank)." },
    BIT: { d: [["B", "Boron"], ["I", "Injection"], ["T", "Tank"]], nom: "Ligne d'injection haute pression",
           role: "Sur IS, les pompes de charge injectent par cette ligne directement dans les branches froides (HP)." },
    RTGV: { d: [["R", "Rupture"], ["T", "de Tube"], ["GV", "de Générateur de Vapeur"]], nom: "Rupture de tube de GV",
           role: "L'eau primaire (active) passe dans le GV : on trouve le GV affecté à son activité, on l'isole et on égalise les pressions." },
    APRP: { d: [["A", "Accident"], ["P", "de Perte"], ["R", "de Réfrigérant"], ["P", "Primaire"]], nom: "Brèche primaire (LOCA)",
           role: "Perte d'eau du primaire : IS, puis recirculation sur les puisards quand la PTR est vide." },
    RPR: { d: [["R", "Réacteur"], ["PR", "Protection du Réacteur"]], nom: "Protection du réacteur",
           role: "Logique qui déclenche l'arrêt automatique (AU), l'IS et les permissifs (P-x, C-x)." },
    RGL: { d: [["R", "Réacteur"], ["GL", "commande des Grappes de régLage"]], nom: "Commande des grappes",
           role: "Monte et descend les groupes de grappes absorbantes pour piloter la réactivité." },
    PTR: { d: [["P", "Piscine"], ["TR", "Traitement et Refroidissement"]], nom: "Bâche PTR",
           role: "Grande réserve d'eau borée (2 500 ppm) : secours des pompes de charge et de l'IS." },
    ASG: { d: [["A", "Alimentation"], ["SG", "de Secours des Générateurs de vapeur"]], nom: "Alimentation de secours des GV",
           role: "2 motopompes + 1 turbopompe qui alimentent les GV en eau quand l'eau alimentaire normale est perdue." },
    ARE: { d: [["A", "Alimentation"], ["RE", "Régulation de l'Eau des GV"]], nom: "Régulation de l'alimentation normale des GV",
           role: "Vannes de réglage (grand et petit débit) qui tiennent le niveau d'eau de chaque GV." },
    APP: { d: [["A", "Alimentation"], ["PP", "Pompes alimentaires Principales"]], nom: "Pompes alimentaires",
           role: "Turbopompes qui envoient l'eau alimentaire à ~70 bar vers les GV." },
    APD: { d: [["A", "Alimentation"], ["PD", "Pompe de Démarrage"]], nom: "Pompe alimentaire de démarrage",
           role: "Motopompe d'eau alimentaire pour les faibles charges et les démarrages." },
    AHP: { d: [["A", "Alimentation"], ["HP", "réchauffeurs Haute Pression"]], nom: "Réchauffeurs haute pression",
           role: "Réchauffent l'eau alimentaire avec de la vapeur soutirée à la turbine (meilleur rendement)." },
    ABP: { d: [["A", "Alimentation"], ["BP", "réchauffeurs Basse Pression"]], nom: "Réchauffeurs basse pression",
           role: "Premier étage de réchauffage du condensat, par soutirages basse pression." },
    CEX: { d: [["C", "Condenseur"], ["EX", "EXtraction"]], nom: "Extraction du condensat",
           role: "Pompes qui reprennent l'eau condensée au fond du condenseur (puits) vers le poste d'eau." },
    CRF: { d: [["C", "Condenseur"], ["RF", "circulation d'eau de RéFrigération"]], nom: "Eau de circulation",
           role: "Énormes pompes d'eau de mer (~48 m³/s) qui refroidissent le condenseur." },
    CVI: { d: [["C", "Condenseur"], ["VI", "VIde"]], nom: "Vide du condenseur", role: "Maintient le vide (éjecteurs)." },
    VVP: { d: [["V", "Vapeur"], ["VP", "Vapeur Principale"]], nom: "Vapeur vive principale",
           role: "Lignes de vapeur des GV vers la turbine, avec VIV, VDA et soupapes de sûreté." },
    GCT: { d: [["G", "Groupe turbo-alternateur"], ["CT", "Contournement de la Turbine"]], nom: "Contournement de la turbine",
           role: "Envoie la vapeur directement au condenseur (GCT-c) quand la turbine ne l'absorbe pas (déclenchement, baisse de charge)." },
    GRE: { d: [["G", "Groupe turbo-alternateur"], ["RE", "RÉgulation"]], nom: "Régulation de la turbine",
           role: "Vannes d'admission et régulation de vitesse / charge de la turbine." },
    VDA: { d: [["V", "Vannes"], ["D", "de Décharge"], ["A", "à l'Atmosphère"]], nom: "Vannes de décharge à l'atmosphère",
           role: "Évacuent la vapeur des GV à l'air libre quand le condenseur n'est pas disponible." },
    VIV: { d: [["V", "Vannes"], ["I", "d'Isolement"], ["V", "Vapeur"]], nom: "Vannes d'isolement vapeur",
           role: "Ferment chaque ligne vapeur en moins de 5 s (brèche vapeur, isolement d'un GV)." },
    GV: { d: [["G", "Générateur"], ["V", "de Vapeur"]], nom: "Générateur de vapeur",
          role: "Échangeur à tubes en U : l'eau primaire (325 °C) fait bouillir l'eau secondaire (~63 bar). Frontière primaire / secondaire." },
    PZR: { d: [["PZR", "PressuriseuR"]], nom: "Pressuriseur",
           role: "Ballon à moitié rempli de vapeur qui fixe la pression du primaire (155 bar) : chaufferettes pour monter, aspersion pour baisser." },
    PP: { d: [["P", "Pompe"], ["P", "Primaire"]], nom: "Pompe primaire", role: "Fait circuler l'eau du primaire dans une boucle (~20 000 m³/h)." },
    PSH: { d: [["P", "Pompe"], ["S", "de Soulèvement"], ["H", "d'Huile"]], nom: "Pompe de soulèvement d'huile",
           role: "Met les paliers de la pompe primaire en pression d'huile avant son démarrage." },
    VCT: { d: [["V", "Volume"], ["C", "Control"], ["T", "Tank"]], nom: "Réservoir de contrôle volumétrique (bâche RCV)",
           role: "Tampon d'eau du RCV entre la décharge et l'aspiration des pompes de charge (sigle américain)." },
    PORV: { d: [["P", "Power"], ["O", "Operated"], ["R", "Relief"], ["V", "Valve"]], nom: "Vanne de décharge pilotée du PZR",
            role: "S'ouvre à 162 bar pour éviter l'arrêt automatique sur pression haute (sigle américain)." },
    CST: { d: [["C", "Condensate"], ["S", "Storage"], ["T", "Tank"]], nom: "Bâche de stockage d'eau",
           role: "Réserve d'eau déminéralisée : appoint du condenseur et aspiration de l'ASG." },
    SAR: { d: [["S", "Services"], ["AR", "Air comprimé de Régulation"]], nom: "Air comprimé de régulation",
           role: "Alimente les vannes pneumatiques ; sans air, chaque vanne va en position de repli." },
    LGA: { d: [["L", "éLectricité"], ["G", "6,6 kV normal"], ["A", "voie A"]], nom: "Tableau 6,6 kV normal A",
           role: "Alimente les gros consommateurs non secourus (pompes primaires, CEX, CRF). Perdu avec le réseau." },
    LGB: { d: [["L", "éLectricité"], ["G", "6,6 kV normal"], ["B", "voie B"]], nom: "Tableau 6,6 kV normal B", role: "Comme LGA, voie B." },
    LHA: { d: [["L", "éLectricité"], ["H", "6,6 kV secouru"], ["A", "voie A"]], nom: "Tableau 6,6 kV secouru A",
           role: "Alimente les matériels de sauvegarde ; repris par le diesel A si le réseau est perdu." },
    LHB: { d: [["L", "éLectricité"], ["H", "6,6 kV secouru"], ["B", "voie B"]], nom: "Tableau 6,6 kV secouru B", role: "Comme LHA, voie B (diesel B)." },
    LBA: { d: [["L", "éLectricité"], ["B", "125 V continu (Batteries)"], ["A", "voie A"]], nom: "Batterie 125 V A",
           role: "Contrôle-commande de la voie A ; 2 h d'autonomie sans chargeur." },
    LBB: { d: [["L", "éLectricité"], ["B", "125 V continu (Batteries)"], ["B", "voie B"]], nom: "Batterie 125 V B",
           role: "Contrôle-commande de la voie B ; 30 min d'autonomie sans chargeur." },
    TA: { d: [["T", "Transformateur"], ["A", "Auxiliaire"]], nom: "Transformateur auxiliaire", role: "Alimente les tableaux depuis le réseau 400 kV." },
    TS: { d: [["T", "Transformateur"], ["S", "de Soutirage"]], nom: "Transformateur de soutirage", role: "Alimente les tableaux depuis l'alternateur." },
    AU: { d: [["A", "Arrêt"], ["U", "d'Urgence (automatique)"]], nom: "Arrêt automatique du réacteur",
          role: "Chute de toutes les grappes en 2 s : la réaction en chaîne s'arrête." },
    IS: { d: [["I", "Injection"], ["S", "de Sécurité"]], nom: "Injection de sécurité", role: "Signal de sauvegarde (brèche) ; voir RIS." },
    BC: { d: [["B", "Branche"], ["C", "Chaude"]], nom: "Branche chaude", role: "Tuyauterie cuve → GV (~325 °C)." },
    BF: { d: [["B", "Branche"], ["F", "Froide"]], nom: "Branche froide", role: "Tuyauterie pompe → cuve (~289 °C)." },
    FCV: { d: [["F", "Flow"], ["C", "Control"], ["V", "Valve"]], nom: "Vanne de réglage de débit", role: "Repère américain." },
    LCV: { d: [["L", "Level"], ["C", "Control"], ["V", "Valve"]], nom: "Vanne liée au niveau", role: "Repère américain." },
    HCV: { d: [["H", "Hand"], ["C", "Control"], ["V", "Valve"]], nom: "Vanne de réglage manuelle", role: "Repère américain." },
    PCV: { d: [["P", "Pressure"], ["C", "Control"], ["V", "Valve"]], nom: "Vanne de réglage de pression", role: "Repère américain." },
  },

  // ---------------------------------------------------------------- équipements : [motif, fiche]
  // circuit = sigle du circuit ; m = résultat du motif (m[1] = numéro de boucle, de train…)
  EQUIPEMENTS: [
    [/^PP(\d)$/, m => ({ nom: `Pompe primaire de la boucle ${m[1]}`, type: "Pompe centrifuge verticale, ~20 000 m³/h, moteur 6,6 kV (~4,5 MW)",
      circuit: "RCP", role: "Fait circuler l'eau du primaire dans la boucle. Volant d'inertie (ralentissement ~25 s), antidévireur. Démarrage : huile depuis 2 min, P ≥ 29 bar (joint n°1), RRI en service." })],
    [/^PSH(\d)$/, m => ({ nom: `Pompe de soulèvement d'huile de PP${m[1]}`, type: "Petite motopompe d'huile", circuit: "RCP",
      role: "Met les paliers de la pompe primaire sous huile : obligatoire avant de la démarrer." })],
    [/^GV(\d)$/, m => ({ nom: `Générateur de vapeur ${m[1]}`, type: "Échangeur vertical à tubes en U (~5 000 m² d'échange)",
      circuit: "RCP / VVP / ARE", role: "L'eau primaire passe dans les tubes et fait bouillir l'eau secondaire autour (~63 bar, 855 MW par GV). Le niveau d'eau est tenu par l'ARE ou l'ASG." })],
    [/^GRAPPES$/, () => ({ nom: "Cuve, cœur et grappes", type: "Cuve en acier (~4,4 m de diamètre), 193 assemblages combustibles, grappes absorbantes",
      circuit: "RCP / RGL", role: "Le cœur produit ~3 400 MW thermiques. Les grappes (groupes R, G, S) pilotent la réactivité. Double-clic : vue du cœur." })],
    [/^PZR$/, () => ({ nom: "Pressuriseur", type: "Ballon vertical de 51 m³ (eau + vapeur saturées)", circuit: "RCP",
      role: "Fixe la pression du primaire (155 bar) et absorbe les dilatations de l'eau (niveau)." })],
    [/^PZR_CHAUF_P$/, () => ({ nom: "Chaufferettes proportionnelles du PZR", type: "Résistances électriques (414 kW), sur LGA", circuit: "RCP",
      role: "Réglage fin de la pression : chauffer l'eau du PZR fait de la vapeur et monte la pression." })],
    [/^PZR_CHAUF_T$/, () => ({ nom: "Chaufferettes tout-ou-rien du PZR", type: "Résistances électriques (1 380 kW), groupe de secours sur LHB", circuit: "RCP",
      role: "Appoint de chauffage quand la pression baisse franchement ; reprises par le diesel B." })],
    [/^PZR_ASP(\d)$/, m => ({ nom: `Vanne d'aspersion du PZR (branche froide B${m[1]})`, type: "Vanne de réglage pneumatique", circuit: "RCP",
      role: "Pulvérise de l'eau froide dans la vapeur du PZR : la vapeur se condense, la pression baisse. Il faut une pompe primaire en marche." })],
    [/^PZR_PORV(\d)$/, m => ({ nom: `PORV ${m[1]} (vanne de décharge pilotée du PZR)`, type: "Vanne pneumatique à électrovanne (125 V), 26,5 kg/s",
      circuit: "RCP", role: "S'ouvre à 162 bar pour éviter l'AU sur pression haute ; décharge vers le RDP. Schéma Westinghouse : sur les REP français, la protection du PZR est faite par des soupapes pilotées (type SEBIM)." })],
    [/^PZR_ISOL(\d)$/, m => ({ nom: `Vanne d'isolement de la PORV ${m[1]}`, type: "Vanne motorisée", circuit: "RCP",
      role: "Isole une PORV qui fuit ou reste ouverte (scénario S8)." })],
    [/^PZR_SOUP(\d)$/, m => ({ nom: `Soupape de sûreté n°${m[1]} du PZR`, type: "Soupape à ressort", circuit: "RCP",
      role: "Dernière protection contre la surpression du primaire (~172 bar)." })],
    [/^REG_P_PZR$/, () => ({ nom: "Consigne de pression du PZR", type: "Régulation (PI maître)", circuit: "RCP",
      role: "Pilote chaufferettes, aspersion et PORV pour tenir la pression de consigne." })],
    [/^RPR$/, () => ({ nom: "Protection du réacteur", type: "Logique de protection (votes 2/4, 2/3)", circuit: "RPR",
      role: "AU, IS, blocages et réarmements. Les seuils sont dans l'onglet Logique." })],
    // ---- RCV / REA
    [/^RCV_PC(\d)$/, m => ({ nom: `Pompe de charge n°${m[1]}`, type: "Pompe centrifuge haute pression (34 m³/h, ~185 bar à débit nul)",
      circuit: "RCV", role: "Réinjecte l'eau dans le primaire (charge) et aux joints des pompes primaires. Ce sont aussi les pompes d'IS haute pression." })],
    [/^RCV_CHARGE$/, () => ({ nom: "FCV-121 : vanne de réglage de la charge", type: "Vanne de réglage pneumatique (repli ouverte)", circuit: "RCV",
      role: "Règle le débit de charge sur la régulation de niveau du PZR." })],
    [/^RCV_ISOL_CHARGE$/, () => ({ nom: "MO-8105/8106 : isolement de la ligne de charge", type: "Vannes motorisées", circuit: "RCV",
      role: "Fermées par l'IS (l'eau passe alors par l'injection de sécurité)." })],
    [/^RCV_JOINTS$/, () => ({ nom: "HCV-182 : injection aux joints des pompes primaires", type: "Vanne de réglage manuelle", circuit: "RCV",
      role: "Envoie ~7,3 m³/h aux joints : 4,5 entrent au primaire, 2,7 reviennent à la VCT. Sans injection ni RRI, les joints se dégradent." })],
    [/^RCV_LCV(\d+)$/, m => ({ nom: `LCV-${m[1]} : isolement de la décharge`, type: "Vanne pneumatique (repli fermée)", circuit: "RCV",
      role: "Deux vannes en série à l'entrée de la décharge ; fermées si le niveau PZR < 17 %. À ouvrir AVANT un orifice." })],
    [/^RCV_ORIF(\d)$/, m => ({ nom: `Vanne de l'orifice de décharge n°${m[1]}`, type: "Vanne pneumatique + orifice calibré (17 / 17 / 10 m³/h à 155 bar)",
      circuit: "RCV", role: "Fixe le débit de décharge (∝ √ΔP). Ouverture : pompe de charge en marche et LCV-459/460 ouvertes." })],
    [/^RCV_ISOL_ENC$/, () => ({ nom: "CV-8152 : isolement enceinte de la décharge", type: "Vanne pneumatique", circuit: "RCV",
      role: "Fermée par la phase A de l'IS (isolement de l'enceinte)." })],
    [/^RCV_HCV128$/, () => ({ nom: "HCV-128 : décharge par le RRA", type: "Vanne de réglage manuelle", circuit: "RCV / RRA",
      role: "Purification de l'eau du primaire pendant le RRA, quand la décharge normale n'a plus assez de pression." })],
    [/^RCV_DEVIATION$/, () => ({ nom: "LCV-112A : déviation vers les effluents", type: "Vanne 3 voies pneumatique", circuit: "RCV",
      role: "Envoie la décharge vers le traitement des effluents quand la VCT est trop pleine." })],
    [/^RCV_ASP_VCT$/, () => ({ nom: "LCV-112B/C : aspiration sur la VCT", type: "Vannes motorisées", circuit: "RCV",
      role: "Aspiration normale des pompes de charge ; fermées si VCT très basse ou IS." })],
    [/^RCV_ASP_PTR$/, () => ({ nom: "LCV-112D/E : aspiration sur la PTR", type: "Vannes motorisées", circuit: "RCV / PTR",
      role: "Aspiration de secours (eau à 2 500 ppm) ; ouvertes si VCT très basse ou IS. Retour manuel." })],
    [/^RCV_BORI_URG$/, () => ({ nom: "MO-8104 : borication d'urgence", type: "Vanne motorisée", circuit: "REA / RCV",
      role: "Envoie l'acide borique (7 000 ppm) directement aux pompes de charge (grappe coincée, dilution intempestive)." })],
    [/^REGEN$/, () => ({ nom: "Échangeur régénérateur", type: "Échangeur tubulaire", circuit: "RCV",
      role: "La décharge chaude (288 °C) réchauffe la charge froide (→ 260 °C) : moins de choc thermique, moins de pertes." })],
    [/^ECH_DECH$/, () => ({ nom: "Échangeur de décharge", type: "Échangeur refroidi par le RRI", circuit: "RCV / RRI",
      role: "Refroidit la décharge à ~49 °C avant la purification et la VCT." })],
    [/^VCT$/, () => ({ nom: "VCT (bâche RCV)", type: "Réservoir sous hydrogène (~10 m³ utiles)", circuit: "RCV",
      role: "Tampon entre décharge et charge. Niveau bas : appoint REA ; très bas : bascule sur la PTR ; haut : déviation." })],
    [/^ACIDE$/, () => ({ nom: "Bâches d'acide borique", type: "2 × 92 m³ à 7 000 ppm", circuit: "REA", role: "Réserve de bore pour la borication." })],
    [/^EAU_APPOINT$/, () => ({ nom: "Bâche d'eau d'appoint", type: "770 m³ d'eau déminéralisée", circuit: "REA", role: "Eau pour la dilution et l'appoint." })],
    [/^PTR$/, () => ({ nom: "Bâche PTR", type: "Réservoir de ~1 600 m³ d'eau borée (2 500 ppm)", circuit: "PTR",
      role: "Secours des pompes de charge et de l'IS ; remplissage de la piscine. À 48 % : passage en recirculation." })],
    // ---- RIS / EAS / enceinte (V4)
    [/^RIS_PMP(\d)$/, m => ({ nom: `Pompe d'injection de sécurité MP n°${m[1]}`, type: "Pompe centrifuge (~100 m³/h à 46 bar, débit nul au-dessus de 106 bar)",
      circuit: "RIS", role: "Injection moyenne pression dans les branches froides, aspiration PTR puis puisards. Démarrée par le signal IS." })],
    [/^RIS_BIT$/, () => ({ nom: "Vanne de la ligne BIT", type: "Vanne motorisée, ouverte par l'IS", circuit: "RIS / RCV",
      role: "Ouvre l'injection haute pression : les pompes de charge refoulent directement dans les branches froides." })],
    [/^RIS_PUISARD(\d)$/, m => ({ nom: `Vanne d'aspiration aux puisards (train ${m[1]})`, type: "Vanne motorisée (ouverte si puisard > 50 m³)",
      circuit: "RIS / EAS", role: "Passage en recirculation : les pompes RIS et EAS aspirent l'eau tombée au fond de l'enceinte au lieu de la PTR." })],
    [/^EAS_P(\d)$/, m => ({ nom: `Pompe d'aspersion de l'enceinte n°${m[1]}`, type: "Pompe centrifuge (~700 m³/h)", circuit: "EAS",
      role: "Démarre sur pression enceinte très haute (> 2,07 bar rel) ; arrêtée si la PTR passe sous 17 % sans recirculation." })],
    [/^RDP$/, () => ({ nom: "RDP : réservoir de décharge du pressuriseur (PRT en anglais)", type: "Réservoir de 51 m³ (38 m³ d'eau sous azote), disque de rupture à 8 bar",
      circuit: "RCP", role: "Condense la vapeur des PORV / soupapes. Si elle monte à 8 bar, le disque crève : la décharge part dans l'enceinte." })],
    [/^PUISARDS$/, () => ({ nom: "Puisards de l'enceinte", type: "Fond du bâtiment réacteur", circuit: "RIS / EAS",
      role: "Recueillent l'eau des brèches et de l'aspersion : réserve pour la recirculation à long terme." })],
    [/^FORMATEUR$/, () => ({ nom: "Pupitre du formateur", type: "Injection de pannes", circuit: "—",
      role: "Brèches primaire / vapeur, RTGV, PORV bloquée, perte RRI, grappe coincée, perte réseau ou d'air, à tout moment." })],
    [/^REA$/, () => ({ nom: "Appoint eau et bore", type: "Mélangeur + pompes de transfert", circuit: "REA",
      role: "Modes auto (appoint VCT), borication (acide aux pompes de charge), dilution (eau à la VCT), arrêt." })],
    // ---- RRA / RRI / SEC / accumulateurs
    [/^RRA_P(\d)$/, m => ({ nom: `Pompe RRA du train ${m[1]}`, type: "Pompe centrifuge (~700 m³/h)", circuit: "RRA",
      role: "Aspire dans la branche chaude, refoule dans les branches froides à travers l'échangeur." })],
    [/^RRA_ASP(\d)([AB])$/, m => ({ nom: `Vanne d'aspiration RRA ${m[1]}${m[2]}`, type: "Vanne motorisée (2 en série par train)", circuit: "RRA",
      role: "Verrou : ouverture seulement si P < 30 bar ; refermeture automatique au-dessus de 41 bar (le RRA n'est pas fait pour 155 bar)." })],
    [/^RRA_HX(\d)$/, m => ({ nom: `HCV-606/607 : sortie de l'échangeur RRA ${m[1]}`, type: "Vanne de réglage", circuit: "RRA",
      role: "Règle la part du débit refroidie, donc la vitesse de refroidissement (auto : ~30 °C/h)." })],
    [/^RRA_BP(\d)$/, m => ({ nom: `HCV-618 : by-pass de l'échangeur RRA ${m[1]}`, type: "Vanne de réglage", circuit: "RRA",
      role: "Complète le débit qui ne passe pas dans l'échangeur : débit total à peu près constant." })],
    [/^ECH_RRA(\d)$/, m => ({ nom: `Échangeur RRA ${m[1]}`, type: "Échangeur refroidi par le RRI", circuit: "RRA / RRI",
      role: "Transfère la chaleur résiduelle du primaire vers le RRI." })],
    [/^RRI_P(\d)$/, m => ({ nom: `Pompe RRI n°${m[1]}`, type: "Pompe centrifuge (~2 500 m³/h)", circuit: "RRI",
      role: "Fait circuler l'eau de la boucle intermédiaire. Sans RRI, les pompes primaires doivent être arrêtées." })],
    [/^SEC_P(\d)$/, m => ({ nom: `Pompe d'eau brute secourue n°${m[1]}`, type: "Pompe d'eau de mer (~3 000 m³/h)", circuit: "SEC",
      role: "Refroidit le RRI avec l'eau de mer." })],
    [/^ECH_SEC$/, () => ({ nom: "Échangeurs RRI / SEC", type: "Échangeurs à plaques", circuit: "RRI / SEC", role: "Passage de la chaleur du RRI vers la mer." })],
    [/^ACC(\d)$/, m => ({ nom: `Accumulateur n°${m[1]}`, type: "Réservoir de 38 m³ (29 m³ d'eau borée sous 42 bar d'azote)", circuit: "RIS",
      role: "Injecte passivement dans la branche froide si la pression primaire passe sous 42 bar." })],
    [/^ACC(\d)_ISOL$/, m => ({ nom: `Vanne d'isolement de l'accumulateur ${m[1]}`, type: "Vanne motorisée", circuit: "RIS",
      role: "Ouverte en puissance (rouverte automatiquement au-dessus de P-11) ; à fermer avant 42 bar en refroidissement." })],
    // ---- vapeur, turbine, condenseur
    [/^VIV(\d)$/, m => ({ nom: `VIV ${m[1]} : vanne d'isolement vapeur`, type: "Vanne pneumatique à fermeture rapide (< 5 s), réserve d'air 15 min",
      circuit: "VVP", role: "Isole la ligne vapeur du GV (brèche vapeur, rupture de tube)." })],
    [/^VIV(\d)_BP$/, m => ({ nom: `By-pass de la VIV ${m[1]}`, type: "Vanne motorisée", circuit: "VVP", role: "Équilibre les pressions avant de rouvrir la VIV." })],
    [/^VDA(\d)$/, m => ({ nom: `VDA ${m[1]} : vanne de décharge à l'atmosphère`, type: "Vanne de réglage pneumatique (secours azote 30 min, électrovanne 125 V)",
      circuit: "VVP", role: "Évacue la vapeur du GV à l'air libre (consigne ~79 bar) quand le condenseur n'est pas là." })],
    [/^SOUP(\d)_(\d)$/, m => ({ nom: `Soupape de sûreté n°${m[2]} de la ligne vapeur ${m[1]}`, type: "Soupape à ressort (82 → 86 bar)",
      circuit: "VVP", role: "Protège le GV contre la surpression." })],
    [/^GCTC_G(\d)$/, m => ({ nom: `Groupe ${m[1]} du contournement condenseur (GCT-c)`, type: "Vannes de réglage pneumatiques (188 kg/s par groupe)",
      circuit: "GCT", role: "Envoie la vapeur au condenseur sans passer par la turbine. Interdit sans C-9 ; sous P-12, seul le groupe 1." })],
    [/^REG_GCTC$/, () => ({ nom: "Régulation du contournement", type: "Régulation (mode Tmoy ou mode pression)", circuit: "GCT",
      role: "Mode Tmoy : tient la température primaire après un déclenchement. Mode pression : tient la pression vapeur (refroidissement)." })],
    [/^TURBINE$/, () => ({ nom: "Groupe turbo-alternateur", type: "Turbine HP + BP, alternateur 1 500 tr/min (~1 135 MWe)", circuit: "GRE",
      role: "Transforme l'énergie de la vapeur en électricité envoyée sur le réseau 400 kV." })],
    [/^CONDENSEUR$/, () => ({ nom: "Condenseur", type: "Échangeur sous vide refroidi à l'eau de mer (~2 300 MW)", circuit: "CVI / CRF",
      role: "Condense la vapeur sortie de la turbine ; le vide (~0,05 bar) fait le rendement." })],
    [/^CRF(\d)$/, m => ({ nom: `Pompe de circulation n°${m[1]}`, type: "Pompe d'eau de mer (~24 m³/s)", circuit: "CRF", role: "Refroidit le condenseur." })],
    [/^PUITS$/, () => ({ nom: "Puits du condenseur", type: "Réserve d'eau condensée", circuit: "CEX", role: "Aspiration des pompes CEX." })],
    [/^REG_PUITS$/, () => ({ nom: "Régulation du niveau du puits", type: "Régulation", circuit: "CEX", role: "Appoint depuis la CST ou rejet vers la CST." })],
    [/^PUITS_APPOINT$/, () => ({ nom: "Vanne d'appoint au condenseur", type: "Vanne de réglage", circuit: "CEX", role: "Fait l'appoint d'eau depuis la CST." })],
    [/^PUITS_REJET$/, () => ({ nom: "Vanne de rejet vers la CST", type: "Vanne de réglage", circuit: "CEX", role: "Renvoie l'excédent d'eau vers la CST." })],
    [/^CEX(\d)$/, m => ({ nom: `Pompe d'extraction n°${m[1]}`, type: "Pompe centrifuge (2 500 m³/h)", circuit: "CEX", role: "Envoie le condensat vers les réchauffeurs BP et les pompes alimentaires." })],
    [/^CEX_RECIRC$/, () => ({ nom: "Recirculation des CEX", type: "Vanne pneumatique", circuit: "CEX", role: "Garantit un débit minimal aux pompes CEX." })],
    [/^CST$/, () => ({ nom: "Bâche de stockage (CST)", type: "Réserve d'eau déminéralisée (~1 400 m³)", circuit: "ASG / CEX", role: "Aspiration de l'ASG et appoint du condenseur." })],
    [/^REP(\d)$/, m => ({ nom: `Pompe de reprise des purges n°${m[1]}`, type: "Pompe centrifuge", circuit: "ABP", role: "Réinjecte l'eau des purges des réchauffeurs dans le poste d'eau." })],
    [/^APP(\d)$/, m => ({ nom: `Pompe alimentaire principale n°${m[1]}`, type: "Turbopompe à vitesse variable (4 500 m³/h)", circuit: "APP",
      role: "Monte l'eau alimentaire à ~70 bar ; vitesse réglée sur l'écart de pression avec la vapeur." })],
    [/^APD$/, () => ({ nom: "Pompe alimentaire de démarrage", type: "Motopompe (230 m³/h)", circuit: "APD", role: "Alimente les GV à faible charge." })],
    [/^AHP$/, () => ({ nom: "Réchauffeurs haute pression", type: "Échangeurs (soutirages HP)", circuit: "AHP", role: "Eau alimentaire portée à ~224 °C." })],
    [/^ABP$/, () => ({ nom: "Réchauffeurs basse pression", type: "Échangeurs (soutirages BP)", circuit: "ABP", role: "Premier réchauffage du condensat." })],
    [/^ARE(\d)_ISOL$/, m => ({ nom: `Vanne d'isolement ARE du GV${m[1]}`, type: "Vanne motorisée (fermeture < 16 s)", circuit: "ARE", role: "Isole l'eau alimentaire du GV (P-14, IS)." })],
    [/^ARE(\d)_GD$/, m => ({ nom: `Vanne ARE grand débit du GV${m[1]}`, type: "Vanne de réglage pneumatique (repli fermée)", circuit: "ARE",
      role: "Règle le niveau du GV en puissance (régulation 3 éléments : niveau, débit vapeur, débit d'eau)." })],
    [/^ARE(\d)_PD$/, m => ({ nom: `Vanne ARE petit débit du GV${m[1]}`, type: "Vanne de réglage pneumatique", circuit: "ARE", role: "Règle le niveau du GV à faible charge." })],
    // ---- ASG
    [/^ASG_MP(\d)$/, m => ({ nom: `Motopompe ASG n°${m[1]}`, type: "Pompe électrique (100 m³/h), sur tableau secouru", circuit: "ASG",
      role: "Démarre sur niveau GV très bas ou perte des 2 APP ; relancée par le séquenceur après une perte de tension." })],
    [/^ASG_TP$/, () => ({ nom: "Turbopompe ASG", type: "Pompe entraînée par une turbine à vapeur (vapeur des GV1 / GV2)", circuit: "ASG",
      role: "Fonctionne sans électricité alternative (régulation sur la batterie A) : seule eau des GV en perte totale des sources." })],
    [/^ASG_TP_VAP$/, () => ({ nom: "Vanne vapeur de la turbopompe ASG", type: "Vanne pneumatique (repli ouverte)", circuit: "ASG", role: "Admet la vapeur à la turbopompe." })],
    [/^ASG(\d)$/, m => ({ nom: `Vanne de réglage ASG du GV${m[1]}`, type: "Vanne pneumatique (repli ouverte, azote 2 h)", circuit: "ASG",
      role: "Règle le niveau du GV (consigne 40 %) quand l'ASG alimente." })],
    // ---- électricité, air
    [/^RESEAU$/, () => ({ nom: "Réseau 400 kV", type: "Réseau de transport (commandes formateur)", circuit: "Électricité",
      role: "Exporte la production et alimente la centrale par les TA quand l'alternateur est découplé." })],
    [/^LH([AB])$/, m => ({ nom: `Tableau 6,6 kV secouru LH${m[1]}`, type: "Tableau électrique + disjoncteur d'arrivée", circuit: "Électricité",
      role: `Alimente les matériels de sauvegarde de la voie ${m[1]} ; sur sous-tension : délestage, diesel ${m[1]}, séquenceur.` })],
    [/^DIESEL_([AB])$/, m => ({ nom: `Diesel ${m[1]}`, type: "Groupe électrogène de 4,4 MW (prêt en 10 s)", circuit: "Électricité",
      role: `Reprend le tableau LH${m[1]} si le réseau est perdu, puis le séquenceur relance charge, RRI, SEC, ASG, air.` })],
    [/^SAR$/, () => ({ nom: "Collecteur d'air comprimé", type: "Réseau d'air (7 bar)", circuit: "SAR", role: "Air de toutes les vannes pneumatiques ; < 5 bar : vannes en repli." })],
    [/^SAR_C(\d)$/, m => ({ nom: `Compresseur d'air n°${m[1]}`, type: "Compresseur électrique (sur tableau secouru)", circuit: "SAR", role: "Tient la pression d'air." })],
    // ---- clapets (en dernier : motif générique)
    [/^(.+)_CLAPET\d?$/, m => ({ nom: `Clapet anti-retour (${m[1]})`, type: "Clapet anti-retour", circuit: m[1].replace(/\d+$/, "").split("_")[0],
      role: "Laisse passer l'eau dans un seul sens (empêche le retour vers une pompe arrêtée)." })],
  ],

  // ---------------------------------------------------------------- notions (barrières de confinement…)
  INFOS: {
    barriere1: { nom: "① 1re barrière : la gaine du combustible",
      texte: "Tube en alliage de zirconium (~0,6 mm) qui enferme les pastilles d'oxyde d'uranium. Elle retient "
           + "les produits de fission. Elle est protégée tant que le cœur est bien refroidi (pas de crise d'ébullition)." },
    barriere2: { nom: "② 2e barrière : l'enveloppe du circuit primaire",
      texte: "Cuve, couvercle, boucles, pressuriseur, pompes primaires et tubes des GV (acier, ~20 cm d'épaisseur pour la "
           + "cuve). Elle retient l'eau radioactive à 155 bar. Une fuite de tube de GV la fait communiquer avec le secondaire." },
    barriere3: { nom: "③ 3e barrière : l'enceinte de confinement",
      texte: "Bâtiment réacteur. Ici à double paroi (type 1 300 MWe) : enceinte interne en béton précontraint "
           + "(tient la pression d'un accident), enceinte externe en béton armé (agressions externes), espace "
           + "entre-enceintes maintenu en dépression et filtré." },
    traversee: { nom: "Traversée de l'enceinte",
      texte: "Chaque tuyauterie qui sort du bâtiment réacteur passe par une traversée équipée de vannes d'isolement "
           + "(une de chaque côté de la paroi). L'IS (phase A, puis phase B) les ferme pour refermer la 3e barrière." },
  },

  htmlInfo(cle) {
    const i = this.INFOS[cle];
    return i ? `<div class="fiche"><div class="fiche-nom">${i.nom}</div><div class="fiche-role">${i.texte}</div></div>` : "";
  },

  fiche(id) {
    for (const [motif, f] of this.EQUIPEMENTS) {
      const m = id.match(motif);
      if (m) return f(m);
    }
    return null;
  },

  // trouve les sigles connus dans un texte (pour les infobulles et la décomposition)
  sigles(texte) {
    const trouves = [];
    for (const mot of String(texte).toUpperCase().match(/[A-Z]{2,4}/g) || []) {
      const cle = mot === "PORV" ? "PORV" : mot;
      if (this.SIGLES[cle] && !trouves.includes(cle)) trouves.push(cle);
    }
    return trouves;
  },

  decomposition(sigle) {
    const s = this.SIGLES[sigle];
    return s ? s.d.map(([l, sens]) => `<b>${l}</b> ${sens}`).join(" · ") : "";
  },

  // HTML d'une fiche complète (panneau équipement, infobulle)
  html(id, titreSupp = "") {
    const f = this.fiche(id);
    if (!f) return "";
    const circuits = f.circuit.split(" / ").map(c => {
      const s = this.SIGLES[c];
      return s ? `<span class="sigle-chip" title="${s.nom}">${c}</span> ${s.nom}` : c;
    }).join(" · ");
    return `<div class="fiche"><div class="fiche-nom">${f.nom}${titreSupp}</div>
      <div><span class="discret">Type :</span> ${f.type}</div>
      <div><span class="discret">Circuit :</span> ${circuits}</div>
      <div class="fiche-role">${f.role}</div></div>`;
  },

  htmlSigle(sigle) {
    const s = this.SIGLES[sigle];
    return s ? `<div class="fiche"><div class="fiche-nom">${sigle} — ${s.nom}</div>
      <div>${this.decomposition(sigle)}</div><div class="fiche-role">${s.role}</div></div>` : "";
  },
};
