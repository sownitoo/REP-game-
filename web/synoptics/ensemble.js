// Vue d'ensemble de la centrale : un bloc par circuit, rangés par bâtiment, reliés par les flux
// (chaleur, eau primaire, vapeur, eau alimentaire, eau de mer, électricité). Clic sur un bloc :
// ouvre l'onglet détaillé. Survol : le sigle décomposé et le rôle. Bordure : état du circuit.
// Repère 1600 × 920.
"use strict";

const BLOCS_ENSEMBLE = [
  // clé, onglet, sigle(s), titre, sous-titre, x, y, l, h, valeurs [mesure, unité, décimales, préfixe]
  ["coeur", "coeur", "RGL", "CŒUR", "cuve + grappes", 60, 200, 170, 130,
   [["coeur.puissance_pct", "%", 1, ""], ["coeur.p_thermique_mw", "MWth", 0, ""]]],
  ["rcp", "primaire", "RCP PZR", "RCP", "circuit primaire · 4 boucles + PZR", 260, 120, 180, 140,
   [["primaire.tmoy_c", "°C", 1, "Tmoy "], ["pzr.p_bar", "bar", 1, "P "], ["B1.debit_pct", "%", 0, "débit "]]],
  ["gv", "primaire", "GV", "GV ×4", "générateurs de vapeur", 470, 120, 150, 140,
   [["GV1.p_bar", "bar", 1, "P "], ["GV1.niveau_pct", "%", 0, "niveau "]]],
  ["rpr", "logique", "RPR AU IS", "RPR", "protection : AU, IS, permissifs", 60, 400, 170, 80, []],
  ["ris", "rra", "RIS", "RIS", "accumulateurs (injection passive)", 470, 400, 150, 80, [["ACC1.p_bar", "bar", 0, "N₂ "]]],
  ["rra", "rra", "RRA", "RRA", "refroidissement à l'arrêt", 60, 580, 160, 80, [["rra.q_mw", "MW", 1, ""]]],
  ["rcv", "rcv", "RCV VCT", "RCV", "chimie et volume du primaire", 250, 580, 160, 84,
   [["rcv.charge_m3h", "m³/h", 1, "charge "], ["primaire.bore_ppm", "ppm", 0, "bore "]]],
  ["rri", "rra", "RRI", "RRI", "réfrigération intermédiaire", 440, 580, 180, 80, [["rri.t_c", "°C", 1, ""], ["rri.q_mw", "MW", 1, ""]]],
  ["ptr", "rcv", "PTR", "PTR", "réserve d'eau borée", 60, 700, 160, 80, [["rcv.ptr_m3", "m³", 0, ""]]],
  ["rea", "rcv", "REA", "REA", "appoint en eau et en bore", 250, 700, 160, 80, [["rcv.vct_niveau_pct", "%", 0, "VCT "]]],
  ["sec", "rra", "SEC", "SEC", "eau brute secourue (mer)", 440, 700, 180, 80, [["sec.q_mw", "MW", 1, ""]]],
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
  ["air", "elec", "SAR", "AIR COMPRIMÉ", "vannes pneumatiques", 1340, 530, 220, 70, [["air.p_bar", "bar", 2, ""]]],
];

function construireEnsemble(svg) {
  Sym.defs(svg);
  const D = el => Sym.detail(el);
  // ------------------------------------------------------------------ bâtiments
  const zone = (x, y, l, h, titre, cls = "") => {
    svgEl("rect", { x, y, width: l, height: h, rx: 18, class: `zone-batiment ${cls}` }, svg);
    Sym.texte(svg, x + 16, y + 22, titre, "titre-zone", "start");
  };
  zone(30, 40, 610, 480, "BÂTIMENT RÉACTEUR (enceinte)", "zone-br");
  zone(30, 540, 610, 270, "BÂTIMENT DES AUXILIAIRES NUCLÉAIRES");
  zone(670, 40, 630, 620, "SALLE DES MACHINES");
  zone(1320, 40, 260, 620, "ÉLECTRICITÉ · AIR");
  svgEl("rect", { x: 30, y: 830, width: 1550, height: 70, rx: 14, class: "zone-mer" }, svg);
  Sym.texte(svg, 46, 872, "MER — station de pompage (source froide)", "titre-zone", "start");

  // ------------------------------------------------------------------ flux (dessous des blocs)
  const flux = (pts, cls, mesure, seuil, texte, tx, ty, ancre = "middle") => {
    const p = Sym.tuyau(svg, pts, `flux ${cls}`, mesure, seuil);
    p.setAttribute("marker-end", "url(#fleche-flux)");
    if (texte) D(Sym.texte(svg, tx, ty, texte, "atm", ancre));
    return p;
  };
  flux([[230, 240], [258, 240]], "primaire-chaud", "coeur.p_thermique_mw", 1, "chaleur", 244, 232);
  flux([[440, 160], [468, 160]], "primaire-chaud", "B1.debit_pct", 1, "", 0, 0);
  flux([[470, 220], [442, 220]], "primaire-froid", "B1.debit_pct", 1, "", 0, 0);
  D(Sym.texte(svg, 455, 196, "boucles", "atm"));
  flux([[545, 120], [545, 100], [698, 100]], "vapeur", "GV1.qm_vapeur_kg_s", 1, "vapeur", 620, 92);
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
  flux([[1190, 828], [1190, 412]], "mer", "crf.debit_m3s", 1, "", 0, 0);
  flux([[898, 380], [862, 380]], "eau", "cex.q_m3h", 10, "condensat", 880, 372);
  flux([[780, 320], [780, 282]], "eau", "alim.qm_kg_s", 1, "", 0, 0);
  flux([[700, 245], [655, 245], [655, 300], [580, 300], [580, 262]], "eau", "alim.qm_kg_s", 1, "eau alimentaire", 600, 316);
  flux([[700, 555], [668, 555], [668, 330], [510, 330], [510, 262]], "eau secours", "asg.qm_kg_s", 1, "ASG", 600, 344);
  // primaire ↔ auxiliaires
  flux([[310, 262], [310, 578]], "primaire-chaud", "rcv.decharge_m3h", 0.5, "décharge", 302, 540, "end");
  flux([[360, 578], [360, 262]], "primaire-froid", "rcv.charge_m3h", 0.5, "charge", 368, 540, "start");
  flux([[280, 262], [280, 555], [140, 555], [140, 578]], "primaire-chaud", "rra.q_mw", 0.1, "aspiration RRA", 150, 548, "start");
  flux([[520, 400], [520, 380], [420, 380], [420, 262]], "primaire-froid", "accu.qm_kg_s", 0.5, "", 0, 0);
  flux([[140, 660], [140, 682], [500, 682], [500, 662]], "chaleur", "rra.q_mw", 0.1, "chaleur résiduelle", 320, 676);
  flux([[410, 620], [438, 620]], "chaleur", "rcv.echangeur_mw", 0.05, "", 0, 0);
  flux([[560, 660], [560, 698]], "chaleur", "rri.q_mw", 0.1, "", 0, 0);
  flux([[530, 780], [530, 828]], "mer", "sec.q_mw", 0.1, "", 0, 0);
  flux([[330, 700], [330, 662]], "eau", "rea.q_total_m3h", 0.1, "", 0, 0);
  flux([[190, 700], [190, 692], [270, 692], [270, 662]], "eau", "rea.q_urgence_m3h", 0.1, "", 0, 0);
  // électricité
  flux([[1450, 150], [1450, 188]], "elec", "elec.reseau_pct", 1, "", 0, 0);
  flux([[1450, 318], [1450, 282]], "elec", "elec.DIESEL_A.charge_kw", 1, "", 0, 0);
  flux([[1552, 235], [1572, 235], [1572, 465], [1562, 465]], "elec", "elec.LHA.tension_pct", 50, "chargeurs", 1576, 350, "start");
  D(Sym.texte(svg, 1330, 640, "← alimentent pompes et vannes de toute la centrale", "atm", "start"));

  // ------------------------------------------------------------------ blocs
  BLOCS_ENSEMBLE.forEach(([cle, onglet, sigles, titre, sous, x, y, l, h, valeurs]) => {
    const g = svgEl("g", { class: "bloc-ensemble", "data-lien-onglet": onglet, "data-bloc": cle, "data-sigle": sigles }, svg);
    svgEl("rect", { x, y, width: l, height: h, rx: 10, class: "corps-bloc" }, g);
    Sym.texte(g, x + l / 2, y + 22, titre, "titre-bloc");
    Sym.texte(g, x + l / 2, y + 38, sous, "atm");
    valeurs.forEach(([m, u, d, p], k) => Sym.valeur(g, x + l / 2, y + 58 + k * 16, m, u, d, "val", "middle", p));
    svgEl("text", { x: x + l - 10, y: y + 18, class: "fleche-onglet", "text-anchor": "end" }, g).textContent = "›";
  });

  // ------------------------------------------------------------------ légende
  const y = 690;
  Sym.texte(svg, 690, y, "Clic sur un bloc : onglet détaillé · survol : sigle et rôle", "lib", "start");
  [["ok", "en service"], ["arret", "à l'arrêt / prêt"], ["alerte", "sollicité / à surveiller"], ["defaut", "perdu / en défaut"]]
    .forEach(([cls, lib], k) => {
      svgEl("rect", { x: 690 + k * 150, y: y + 14, width: 18, height: 12, rx: 3, class: `pastille-etat ${cls}` }, svg);
      Sym.texte(svg, 714 + k * 150, y + 24, lib, "atm", "start");
    });
  [["primaire-chaud", "eau primaire chaude"], ["primaire-froid", "eau primaire froide"], ["vapeur", "vapeur"],
   ["eau", "eau alimentaire"], ["mer", "eau de mer"], ["elec", "électricité"], ["chaleur", "chaleur évacuée"]]
    .forEach(([cls, lib], k) => {
      svgEl("line", { x1: 690 + (k % 4) * 150, y1: y + 48 + Math.floor(k / 4) * 18, x2: 710 + (k % 4) * 150,
                      y2: y + 48 + Math.floor(k / 4) * 18, class: `tuyau flux ${cls} circule` }, svg);
      Sym.texte(svg, 716 + (k % 4) * 150, y + 52 + Math.floor(k / 4) * 18, lib, "atm", "start");
    });
}

// état de chaque bloc (couleur de bordure) à partir des mesures et des composants
function etatsEnsemble(e) {
  const m = e.mesures, c = e.composants, lg = e.logique;
  const marche = ids => ids.some(id => c[id] && c[id].en_marche);
  const s = {};
  s.coeur = lg.au ? "alerte" : m["coeur.puissance_pct"] > 1 ? "ok" : "arret";
  s.rcp = marche(["PP1", "PP2", "PP3", "PP4"]) ? "ok" : m["B1.debit_pct"] > 2 ? "alerte" : "arret";
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
