// Vue d'ensemble de la centrale : un bloc par circuit, rangés par bâtiment, reliés par les flux
// (chaleur, eau primaire, vapeur, eau alimentaire, eau de mer, électricité). Clic sur un bloc :
// ouvre l'onglet détaillé. Survol : le sigle décomposé et le rôle. Bordure : état du circuit.
// Le bâtiment réacteur est vu de dessus (cylindre) avec les 3 barrières de confinement :
//   ① gaine des crayons combustibles · ② enveloppe du circuit primaire · ③ enceinte à double paroi.
// Repère 1600 × 940.
"use strict";

const CENTRE_BR = { x: 335, y: 300 };      // centre du bâtiment réacteur
const RAYON_EXT = 262, RAYON_INT = 246;     // paroi externe (béton armé) et interne (béton précontraint)

const BLOCS_ENSEMBLE = [
  // clé, onglet, sigle(s), titre, sous-titre, x, y, l, h, valeurs [mesure, unité, décimales, préfixe], forme
  ["coeur", "coeur", "RGL", "CUVE · CŒUR", "", 273, 238, 124, 124,
   [["coeur.puissance_pct", "%", 1, ""], ["coeur.p_thermique_mw", "MWth", 0, ""]], "cercle"],
  ["pzr", "primaire", "PZR RCP", "PZR", "pressuriseur", 275, 120, 120, 64, [["pzr.p_bar", "bar", 1, ""]]],
  ["gv", "primaire", "GV", "GV ×4", "1 par boucle", 452, 250, 108, 100,
   [["GV1.p_bar", "bar", 1, ""], ["GV1.niveau_pct", "%", 0, "niv. "]]],
  ["pp", "primaire", "PP RCP", "PP ×4", "pompes primaires", 275, 410, 120, 64, [["B1.debit_pct", "%", 0, "débit "]]],
  ["ris", "rra", "RIS", "RIS", "accumulateurs", 112, 262, 104, 76, [["ACC1.p_bar", "bar", 0, "N₂ "]]],
  ["rra", "rra", "RRA", "RRA", "refroidissement à l'arrêt", 60, 620, 160, 80, [["rra.q_mw", "MW", 1, ""]]],
  ["rcv", "rcv", "RCV VCT", "RCV", "chimie et volume du primaire", 250, 620, 160, 84,
   [["rcv.charge_m3h", "m³/h", 1, "charge "], ["primaire.bore_ppm", "ppm", 0, "bore "]]],
  ["rri", "rra", "RRI", "RRI", "réfrigération intermédiaire", 440, 620, 180, 80, [["rri.t_c", "°C", 1, ""], ["rri.q_mw", "MW", 1, ""]]],
  ["ptr", "rcv", "PTR", "PTR", "réserve d'eau borée", 60, 740, 160, 80, [["rcv.ptr_m3", "m³", 0, ""]]],
  ["rea", "rcv", "REA", "REA", "appoint en eau et en bore", 250, 740, 160, 80, [["rcv.vct_niveau_pct", "%", 0, "VCT "]]],
  ["sec", "rra", "SEC", "SEC", "eau brute secourue (mer)", 440, 740, 180, 80, [["sec.q_mw", "MW", 1, ""]]],
  ["vvp", "secondaire", "VVP VDA VIV", "VVP", "vapeur principale · VIV · VDA", 700, 80, 160, 90,
   [["collecteur.p_bar", "bar", 1, ""], ["vapeur.vda_qm_kg_s", "kg/s", 0, "VDA "]]],
  ["turbine", "secondaire", "GRE", "TURBINE", "GRE · HP + BP", 900, 80, 180, 90, [["turbine.charge_pct", "%", 0, "charge "]]],
  ["alternateur", "elec", "TS", "ALTERNATEUR", "1 500 tr/min", 1110, 80, 160, 90, [["turbine.p_elec_mw", "MWe", 0, ""]]],
  ["are", "secondaire", "ARE", "ARE", "alimentation normale des GV", 700, 210, 160, 70, [["alim.qm_kg_s", "kg/s", 0, ""]]],
  ["gct", "secondaire", "GCT", "GCT-c", "contournement → condenseur", 900, 210, 180, 70, [["gctc.qm_kg_s", "kg/s", 0, ""]]],
  ["poste", "secondaire", "CEX ABP APP AHP", "POSTE D'EAU", "CEX → ABP → APP → AHP", 700, 320, 160, 150,
   [["alim.t_c", "°C", 0, "T eau "], ["cex.q_m3h", "m³/h", 0, "CEX "]]],
  ["condenseur", "secondaire", "CVI", "CONDENSEUR", "sous vide", 900, 320, 180, 90, [["condenseur.p_bar", "bar", 3, ""]]],
  ["crf", "secondaire", "CRF", "CRF", "eau de circulation (mer)", 1110, 320, 160, 90, [["crf.debit_m3s", "m³/s", 0, ""]]],
  ["asg", "asg", "ASG CST", "ASG", "secours des GV · bâche CST", 700, 510, 160, 90,
   [["asg.qm_kg_s", "kg/s", 0, ""], ["cst.volume_m3", "m³", 0, "CST "]]],
  ["reseau", "elec", "", "RÉSEAU 400 kV", "transport d'électricité", 1340, 80, 220, 70, []],
  ["tableaux", "elec", "LGA LHA TA", "TABLEAUX 6,6 kV", "LG normaux · LH secourus", 1340, 190, 220, 90,
   [["elec.LHA.tension_pct", "%", 0, "LHA "], ["elec.LHB.tension_pct", "%", 0, "LHB "]]],
  ["diesels", "elec", "LHA", "DIESELS A / B", "secours des tableaux LH", 1340, 320, 220, 80,
   [["elec.DIESEL_A.charge_kw", "kW", 0, "A "], ["elec.DIESEL_B.charge_kw", "kW", 0, "B "]]],
  ["batteries", "elec", "LBA", "BATTERIES 125 V", "contrôle-commande", 1340, 430, 220, 84,
   [["elec.LBA.charge_pct", "%", 0, "A "], ["elec.LBB.charge_pct", "%", 0, "B "]]],
  ["air", "elec", "SAR", "AIR COMPRIMÉ", "vannes pneumatiques", 1340, 540, 220, 70, [["air.p_bar", "bar", 2, ""]]],
  ["rpr", "logique", "RPR AU IS", "RPR", "protection : AU, IS, permissifs", 1340, 640, 220, 70, []],
];

function construireEnsemble(svg) {
  Sym.defs(svg);
  const D = el => Sym.detail(el);
  const C = CENTRE_BR;
  // ------------------------------------------------------------------ bâtiments
  const zone = (x, y, l, h, titre, cls = "") => {
    svgEl("rect", { x, y, width: l, height: h, rx: 18, class: `zone-batiment ${cls}` }, svg);
    Sym.texte(svg, x + 16, y + 22, titre, "titre-zone", "start");
  };
  zone(30, 580, 610, 260, "BÂTIMENT DES AUXILIAIRES NUCLÉAIRES");
  zone(670, 40, 630, 620, "SALLE DES MACHINES");
  zone(1320, 40, 260, 690, "ÉLECTRICITÉ · AIR · PROTECTION");
  svgEl("rect", { x: 30, y: 860, width: 1550, height: 70, rx: 14, class: "zone-mer" }, svg);
  Sym.texte(svg, 46, 902, "MER — station de pompage (source froide)", "titre-zone", "start");

  // ------------------------------------------------------------------ bâtiment réacteur : ③ enceinte
  const enceinte = svgEl("g", { "data-info": "barriere3" }, svg);
  svgEl("circle", { cx: C.x, cy: C.y, r: RAYON_EXT, class: "paroi-externe" }, enceinte);
  svgEl("circle", { cx: C.x, cy: C.y, r: (RAYON_EXT + RAYON_INT) / 2, class: "entre-enceinte" }, enceinte);
  svgEl("circle", { cx: C.x, cy: C.y, r: RAYON_INT, class: "paroi-interne" }, enceinte);
  Sym.texte(svg, C.x, C.y - RAYON_EXT - 10, "BÂTIMENT RÉACTEUR", "titre-zone");
  const t3 = Sym.texte(svg, C.x, C.y - RAYON_INT + 24, "③ ENCEINTE DE CONFINEMENT", "barriere-txt b3");
  t3.dataset.info = "barriere3";
  D(Sym.texte(svg, C.x, C.y - RAYON_INT + 40, "double paroi béton · espace entre-enceintes en dépression", "atm"));

  // ② enveloppe du circuit primaire (cuve, boucles, PZR, tubes des GV)
  const b2 = svgEl("rect", { x: 252, y: 104, width: 324, height: 386, rx: 46, class: "barriere-2", "data-info": "barriere2" }, svg);
  svgEl("title", {}, b2);
  const t2 = Sym.texte(svg, 566, 126, "② CIRCUIT PRIMAIRE", "barriere-txt b2", "end");
  t2.dataset.info = "barriere2";

  // ------------------------------------------------------------------ flux (dessous des blocs)
  const flux = (pts, cls, mesure, seuil, texte, tx, ty, ancre = "middle") => {
    const p = Sym.tuyau(svg, pts, `flux ${cls}`, mesure, seuil);
    p.setAttribute("marker-end", "url(#fleche-flux)");
    if (texte) D(Sym.texte(svg, tx, ty, texte, "atm", ancre));
    return p;
  };
  // boucles primaires : cuve → GV (branche chaude) → pompes → cuve (branche froide)
  flux([[397, 285], [450, 285]], "primaire-chaud", "B1.debit_pct", 1, "branche chaude", 424, 277);
  flux([[506, 350], [506, 442], [397, 442]], "primaire-froid", "B1.debit_pct", 1, "", 0, 0);
  flux([[335, 410], [335, 364]], "primaire-froid", "B1.debit_pct", 1, "branche froide", 343, 392, "start");
  flux([[395, 152], [430, 152], [430, 283]], "primaire-chaud fin", "pzr.expansion_kg_s", 0.3, "ligne d'expansion", 436, 200, "start");
  flux([[216, 300], [271, 300]], "primaire-froid", "accu.qm_kg_s", 0.5, "", 0, 0);
  // traversées de l'enceinte : vapeur, eau alimentaire, ASG, RCV, RRA
  flux([[506, 250], [506, 200], [688, 200], [688, 125], [698, 125]], "vapeur", "GV1.qm_vapeur_kg_s", 1, "vapeur", 620, 192);
  flux([[700, 245], [642, 245], [642, 305], [562, 305]], "eau", "alim.qm_kg_s", 1, "eau alimentaire", 610, 297);
  flux([[700, 555], [658, 555], [658, 335], [562, 335]], "eau secours", "asg.qm_kg_s", 1, "ASG", 615, 351);
  flux([[300, 490], [300, 618]], "primaire-chaud", "rcv.decharge_m3h", 0.5, "décharge", 292, 590, "end");
  flux([[370, 618], [370, 490]], "primaire-froid", "rcv.charge_m3h", 0.5, "charge", 378, 590, "start");
  flux([[252, 462], [150, 462], [150, 618]], "primaire-chaud", "rra.q_mw", 0.1, "aspiration RRA", 156, 590, "start");
  [[577, 200], [597, 305], [596, 335], [300, 560], [370, 560], [150, 485]].forEach(([x, y]) =>
    svgEl("rect", { x: x - 6, y: y - 6, width: 12, height: 12, rx: 2, class: "traversee", "data-info": "traversee" }, svg));
  // salle des machines
  flux([[860, 125], [898, 125]], "vapeur", "turbine.qm_kg_s", 1, "", 0, 0);
  flux([[1080, 125], [1108, 125]], "arbre", "turbine.vitesse_tr_min", 100, "", 0, 0);
  flux([[1270, 115], [1338, 115]], "elec", "turbine.p_elec_mw", 1, "MWe", 1304, 107);
  flux([[760, 80], [760, 52]], "vapeur", "vapeur.vda_qm_kg_s", 1, "VDA → atmosphère", 768, 58, "start");
  flux([[790, 170], [790, 190], [990, 190], [990, 208]], "vapeur", "gctc.qm_kg_s", 1, "", 0, 0);
  flux([[990, 280], [990, 318]], "vapeur", "gctc.qm_kg_s", 1, "", 0, 0);
  flux([[1060, 170], [1060, 186], [1095, 186], [1095, 300], [1050, 300], [1050, 318]], "vapeur", "turbine.qm_kg_s", 1,
       "échappement", 1100, 250, "start");
  flux([[1108, 345], [1082, 345]], "mer", "crf.debit_m3s", 1, "", 0, 0);
  flux([[1082, 385], [1108, 385]], "mer", "crf.debit_m3s", 1, "", 0, 0);
  flux([[1190, 858], [1190, 412]], "mer", "crf.debit_m3s", 1, "", 0, 0);
  flux([[898, 380], [862, 380]], "eau", "cex.q_m3h", 10, "condensat", 880, 372);
  flux([[780, 320], [780, 282]], "eau", "alim.qm_kg_s", 1, "", 0, 0);
  // auxiliaires nucléaires
  flux([[140, 700], [140, 722], [500, 722], [500, 702]], "chaleur", "rra.q_mw", 0.1, "chaleur résiduelle", 320, 716);
  flux([[410, 660], [438, 660]], "chaleur", "rcv.echangeur_mw", 0.05, "", 0, 0);
  flux([[560, 700], [560, 738]], "chaleur", "rri.q_mw", 0.1, "", 0, 0);
  flux([[530, 820], [530, 858]], "mer", "sec.q_mw", 0.1, "", 0, 0);
  flux([[330, 740], [330, 706]], "eau", "rea.q_total_m3h", 0.1, "", 0, 0);
  flux([[190, 740], [190, 732], [270, 732], [270, 706]], "eau", "rea.q_urgence_m3h", 0.1, "", 0, 0);
  // électricité
  flux([[1450, 150], [1450, 188]], "elec", "elec.reseau_pct", 1, "", 0, 0);
  flux([[1450, 318], [1450, 282]], "elec", "elec.DIESEL_A.charge_kw", 1, "", 0, 0);
  flux([[1552, 235], [1572, 235], [1572, 472], [1562, 472]], "elec", "elec.LHA.tension_pct", 50, "chargeurs", 1576, 350, "start");

  // ------------------------------------------------------------------ blocs
  BLOCS_ENSEMBLE.forEach(([cle, onglet, sigles, titre, sous, x, y, l, h, valeurs, forme]) => {
    const g = svgEl("g", { class: "bloc-ensemble", "data-lien-onglet": onglet, "data-bloc": cle, "data-sigle": sigles }, svg);
    if (forme === "cercle") svgEl("circle", { cx: x + l / 2, cy: y + h / 2, r: l / 2, class: "corps-bloc cuve-bloc" }, g);
    else svgEl("rect", { x, y, width: l, height: h, rx: 10, class: "corps-bloc" }, g);
    const y0 = forme === "cercle" ? y + 38 : y + 22;
    Sym.texte(g, x + l / 2, y0, titre, "titre-bloc");
    if (sous) Sym.texte(g, x + l / 2, y0 + 16, sous, "atm");
    valeurs.forEach(([m, u, d, p], k) => Sym.valeur(g, x + l / 2, y0 + (sous ? 36 : 22) + k * 16, m, u, d, "val", "middle", p));
    if (forme !== "cercle") svgEl("text", { x: x + l - 10, y: y + 18, class: "fleche-onglet", "text-anchor": "end" }, g).textContent = "›";
  });
  // ① gaine du combustible (dans la cuve)
  const t1 = Sym.texte(svg, C.x, C.y + 46, "① gaines du combustible", "barriere-txt b1");
  t1.dataset.info = "barriere1";

  // ------------------------------------------------------------------ légendes
  const y = 690;
  Sym.texte(svg, 690, y, "Clic sur un bloc : onglet détaillé · survol : sigle et rôle", "lib", "start");
  [["ok", "en service"], ["arret", "arrêt / prêt"], ["alerte", "sollicité"], ["defaut", "perdu / défaut"]]
    .forEach(([cls, lib], k) => {
      svgEl("rect", { x: 690 + k * 118, y: y + 14, width: 18, height: 12, rx: 3, class: `pastille-etat ${cls}` }, svg);
      Sym.texte(svg, 714 + k * 118, y + 24, lib, "atm", "start");
    });
  [["primaire-chaud", "eau primaire chaude"], ["primaire-froid", "eau primaire froide"], ["vapeur", "vapeur"],
   ["eau", "eau alimentaire"], ["mer", "eau de mer"], ["elec", "électricité"], ["chaleur", "chaleur évacuée"]]
    .forEach(([cls, lib], k) => {
      svgEl("line", { x1: 690 + (k % 3) * 150, y1: y + 46 + Math.floor(k / 3) * 16, x2: 710 + (k % 3) * 150,
                      y2: y + 46 + Math.floor(k / 3) * 16, class: `tuyau flux ${cls} circule` }, svg);
      Sym.texte(svg, 716 + (k % 3) * 150, y + 50 + Math.floor(k / 3) * 16, lib, "atm", "start");
    });
  const yb = 790;
  Sym.texte(svg, 690, yb, "LES 3 BARRIÈRES entre le combustible et l'environnement", "lib-fort", "start");
  [["b1", "① gaine des crayons (zirconium)", "barriere1"], ["b2", "② circuit primaire (acier)", "barriere2"],
   ["b3", "③ enceinte (béton, double paroi)", "barriere3"]].forEach(([cls, lib, info], k) => {
    const t = Sym.texte(svg, 690, yb + 20 + k * 17, lib, `barriere-txt ${cls}`, "start");
    t.dataset.info = info;
  });
  D(Sym.texte(svg, 690, yb + 76, "■ traversée de l'enceinte : vannes d'isolement (IS phase A)", "atm", "start"));
}

function etatsEnsemble(e) {
  const m = e.mesures, c = e.composants, lg = e.logique;
  const marche = ids => ids.some(id => c[id] && c[id].en_marche);
  const s = {};
  s.coeur = lg.au ? "alerte" : m["coeur.puissance_pct"] > 1 ? "ok" : "arret";
  s.pp = marche(["PP1", "PP2", "PP3", "PP4"]) ? "ok" : m["B1.debit_pct"] > 2 ? "alerte" : "arret";
  s.pzr = m["pzr.p_bar"] > 162 || m["pzr.niveau_pct"] < 17 || m["pzr.niveau_pct"] > 92 ? "alerte" : "ok";
  s.gv = [1, 2, 3, 4].every(b => m[`GV${b}.niveau_pct`] > 20 && m[`GV${b}.niveau_pct`] < 75) ? "ok" : "alerte";
  s.rpr = lg.au || lg.is_actif ? "defaut" : "ok";
  s.ris = m["accu.qm_kg_s"] > 0.5 ? "defaut" : [1, 2, 3, 4].every(b => (c[`ACC${b}_ISOL`] || {}).position_pct <= 0) ? "arret" : "ok";
  s.rra = m["rra.q_mw"] > 0.1 ? "ok" : "arret";
  s.rcv = marche(["RCV_PC1", "RCV_PC2"]) ? (m["rcv.decharge_m3h"] > 0.5 ? "ok" : "alerte") : "defaut";
  s.rri = !marche(["RRI_P1", "RRI_P2"]) ? "defaut" : m["rri.t_c"] > 45 ? "alerte" : "ok";
  s.sec = marche(["SEC_P1", "SEC_P2"]) ? "ok" : "defaut";
  s.ptr = lg.aspiration_ptr ? "alerte" : "ok";
  s.rea = c.REA && c.REA.mode !== "auto" ? "alerte" : "ok";
  s.vvp = m["vapeur.soupapes_ouvertes"] > 0 || m["vapeur.vda_qm_kg_s"] > 1 ? "alerte" : "ok";
  s.turbine = c.TURBINE.declenchee ? "arret" : "ok";
  s.alternateur = c.TURBINE.couplee ? "ok" : "arret";
  s.gct = m["gctc.qm_kg_s"] > 1 ? "alerte" : lg.c9 ? "ok" : "arret";
  s.condenseur = lg.c9 ? "ok" : "defaut";
  s.crf = marche(["CRF1", "CRF2"]) ? "ok" : "defaut";
  s.poste = marche(["APP1", "APP2", "APD"]) ? "ok" : "arret";
  s.are = lg.isolement_are_au || lg.isolement_are_complet ? "alerte" : "ok";
  s.asg = m["asg.qm_kg_s"] > 1 ? "alerte" : "ok";
  s.reseau = m["elec.reseau_ok"] > 0.5 ? "ok" : "defaut";
  const lh = m["elec.LHA.tension_pct"] >= 62 && m["elec.LHB.tension_pct"] >= 62;
  s.tableaux = m["elec.LGA.tension_pct"] >= 62 && lh ? "ok" : lh ? "alerte" : "defaut";
  const d = [c.DIESEL_A, c.DIESEL_B].filter(Boolean);
  s.diesels = d.some(x => x.etat === "echec") ? "defaut" : d.some(x => x.en_service) ? "alerte" : "arret";
  s.batteries = m["elec.LBA.charge_pct"] <= 0 || m["elec.LBB.charge_pct"] <= 0 ? "defaut"
    : m["elec.LBA.decharge"] > 0.5 || m["elec.LBB.decharge"] > 0.5 ? "alerte" : "ok";
  s.air = m["air.p_bar"] >= 6 ? "ok" : m["air.p_bar"] >= 5 ? "alerte" : "defaut";
  return s;
}
