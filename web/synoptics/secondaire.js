// Synoptique « Secondaire » : 4 GV → VVP → turbine → condenseur → CEX → APP → ARE → GV.
// Coordonnées dans un repère 1500 × 880 (viewBox). Chaque data-id = repère côté serveur.
"use strict";

function construireSecondaire(svg) {
  Sym.defs(svg);
  const D = el => Sym.detail(el);
  const GV_X = [110, 290, 470, 650];
  const Y_COLLECTEUR = 70, Y_HAUT_GV = 230, Y_BAS_GV = 430, Y_ARE = 640, Y_POSTE = 720;

  // ------------------------------------------------------------------ tuyauteries (dessous)
  Sym.tuyau(svg, [[GV_X[0], Y_COLLECTEUR], [955, Y_COLLECTEUR]], "vapeur", "turbine.qm_kg_s", 5);
  Sym.tuyau(svg, [[955, Y_COLLECTEUR], [1000, Y_COLLECTEUR]], "vapeur", "turbine.qm_kg_s", 5);
  GV_X.forEach((x, i) => {
    const b = i + 1;
    Sym.tuyau(svg, [[x, Y_HAUT_GV], [x, Y_COLLECTEUR]], "vapeur", `GV${b}.qm_vapeur_kg_s`, 2);
    Sym.tuyau(svg, [[x, 180], [x + 32, 180], [x + 32, 120], [x, 120]], "vapeur");
    Sym.tuyau(svg, [[x, 205], [x - 50, 205], [x - 50, 125]], "vapeur", `GV${b}.qm_decharge_kg_s`, 0.5);
    Sym.tuyau(svg, [[x, 95], [x - 68, 95]], "vapeur");
    Sym.tuyau(svg, [[x, Y_ARE], [x, 585]], "eau", `GV${b}.qm_alim_kg_s`, 1);
    Sym.tuyau(svg, [[x, 585], [x - 16, 585], [x - 16, 505], [x, 505]], "eau", `GV${b}.qm_alim_kg_s`, 1);
    Sym.tuyau(svg, [[x, 585], [x + 16, 585], [x + 16, 505], [x, 505]], "eau", `GV${b}.qm_alim_kg_s`, 1);
    Sym.tuyau(svg, [[x, 505], [x, Y_BAS_GV]], "eau", `GV${b}.qm_alim_kg_s`, 1);
  });
  // contournement condenseur
  Sym.tuyau(svg, [[880, Y_COLLECTEUR], [880, 130]], "vapeur", "gctc.qm_kg_s", 1);
  Sym.tuyau(svg, [[840, 130], [920, 130]], "vapeur", "gctc.qm_kg_s", 1);
  [840, 867, 893, 920].forEach(x => Sym.tuyau(svg, [[x, 130], [x, 200]], "vapeur"));
  Sym.tuyau(svg, [[840, 200], [920, 200]], "vapeur", "gctc.qm_kg_s", 1);
  Sym.tuyau(svg, [[880, 200], [880, 300], [1060, 300], [1060, 330]], "vapeur", "gctc.qm_kg_s", 1);
  // échappement turbine BP → condenseur
  Sym.tuyau(svg, [[1160, 120], [1160, 330]], "vapeur", "turbine.qm_kg_s", 5);
  // eau de mer (CRF)
  Sym.tuyau(svg, [[1490, 345], [1440, 345], [1440, 395]], "mer", "crf.debit_m3s", 1);
  Sym.tuyau(svg, [[1440, 345], [1340, 345], [1340, 395], [1440, 395]], "mer");
  Sym.tuyau(svg, [[1340, 370], [1300, 370]], "mer", "crf.debit_m3s", 1);
  Sym.tuyau(svg, [[1300, 405], [1490, 405]], "mer", "crf.debit_m3s", 1);
  // condensat : puits → CEX → ligne du poste d'eau
  Sym.tuyau(svg, [[1170, 500], [1170, 525]], "eau", "cex.q_m3h", 10);
  Sym.tuyau(svg, [[1130, 525], [1210, 525]], "eau", "cex.q_m3h", 10);
  Sym.tuyau(svg, [[1130, 525], [1130, 640], [1210, 640], [1210, 525]], "eau");
  Sym.tuyau(svg, [[1170, 640], [1170, Y_POSTE]], "eau", "cex.q_m3h", 10);
  Sym.tuyau(svg, [[1170, Y_POSTE], [1380, Y_POSTE]], "eau");
  Sym.tuyau(svg, [[1100, Y_POSTE], [1060, Y_POSTE], [1060, 440]], "eau");
  Sym.tuyau(svg, [[1380, 640], [1330, 640], [1330, 430], [1300, 430]], "eau");
  Sym.tuyau(svg, [[1170, Y_POSTE], [700, Y_POSTE]], "eau", "alim.qm_kg_s", 5);
  Sym.tuyau(svg, [[920, 760], [920, Y_POSTE]], "purge", "reprise.qm_kg_s", 5);
  Sym.tuyau(svg, [[895, 760], [945, 760]], "purge", "reprise.qm_kg_s", 5);
  Sym.tuyau(svg, [[880, 680], [880, 770], [780, 770], [780, 680], [880, 680]], "eau");
  Sym.tuyau(svg, [[700, Y_POSTE], [690, Y_POSTE], [690, Y_ARE], [GV_X[0], Y_ARE]], "eau", "alim.qm_kg_s", 5);

  // ------------------------------------------------------------------ GV + lignes vapeur
  GV_X.forEach((x, i) => {
    const b = i + 1;
    Sym.gv(svg, x - 28, Y_HAUT_GV, 56, Y_BAS_GV - Y_HAUT_GV, `GV${b}`);
    Sym.texte(svg, x - 36, 290, `GV${b}`, "lib-fort", "end");
    D(Sym.valeur(svg, x - 36, 306, `GV${b}.p_bar`, "bar", 2, "val", "end"));
    Sym.valeur(svg, x - 36, 320, `GV${b}.niveau_pct`, "% GE", 1, "val", "end");
    D(Sym.valeur(svg, x - 36, 334, `GV${b}.q_mw`, "MW", 0, "val", "end", "Q "));
    D(Sym.valeur(svg, x + 6, 60, `GV${b}.qm_vapeur_kg_s`, "kg/s", 0, "val", "start"));
    Sym.vanne(svg, x, 150, `VIV${b}`, { orient: "v", label: `VIV${b}`, cote: "gauche" });
    Sym.vanne(svg, x + 32, 150, `VIV${b}_BP`, { orient: "v", label: "by-pass", cote: "droite", detail: true });
    Sym.vanne(svg, x - 50, 170, `VDA${b}`, { orient: "v", reg: true, label: `VDA${b}`, cote: "gauche", detail: true });
    D(Sym.texte(svg, x - 50, 118, "atm ↑", "atm"));
    for (let n = 1; n <= 5; n++) Sym.soupape(svg, x - 64 + (n - 1) * 11, 95, `SOUP${b}_${n}`);
    // alimentation
    Sym.vanne(svg, x, 615, `ARE${b}_ISOL`, { orient: "v", label: "isol", cote: "gauche", detail: true });
    Sym.vanne(svg, x - 16, 545, `ARE${b}_GD`, { orient: "v", reg: true, label: "GD", cote: "bas", detail: true });
    Sym.vanne(svg, x + 16, 545, `ARE${b}_PD`, { orient: "v", reg: true, label: "PD", cote: "bas", detail: true });
    Sym.clapet(svg, x, 470, `ARE${b}_CLAPET`, "v");
    D(Sym.valeur(svg, x + 8, 632, `GV${b}.qm_alim_kg_s`, "kg/s", 0, "val", "start"));
    Sym.texte(svg, x - 22, 660, `ARE${b}`, "lib", "middle");
  });
  Sym.valeur(svg, 560, 40, "collecteur.p_bar", "bar", 2, "val-fort", "middle", "Collecteur vapeur ");
  D(Sym.texte(svg, 20, 20, "▲ soupapes VVP (5 par ligne, 82 → 86 bar)   ⊠ vanne régulée   M = en manuel   contour orange = ordre automatique", "atm", "start"));
  D(Sym.valeur(svg, 370, 660, "N_ARE.p_bar", "bar", 1, "val", "middle", "P refoul. ARE "));

  // ------------------------------------------------------------------ rappel du primaire
  const prim = Sym._groupe(svg, "GRAPPES", "source", "Primaire (détail dans l'onglet Primaire)");
  svgEl("rect", { x: 735, y: 240, width: 140, height: 100, rx: 6, class: "corps" }, prim);
  Sym.texte(prim, 805, 258, "PRIMAIRE", "lib-fort");
  Sym.valeur(prim, 805, 276, "coeur.puissance_pct", "%", 1, "val-fort");
  Sym.valeur(prim, 805, 294, "primaire.tmoy_c", "°C", 1, "val", "middle", "Tmoy ");
  Sym.valeur(prim, 805, 310, "pzr.p_bar", "bar", 1, "val", "middle", "P PZR ");
  D(Sym.texte(prim, 805, 328, "chaleur → 4 GV", "atm"));
  Sym.fleche(svg, 735, 300, 684, 330);

  // ------------------------------------------------------------------ contournement
  ["GCTC_G1", "GCTC_G2", "GCTC_G3", "GCTC_G4"].forEach((id, k) =>
    Sym.vanne(svg, [840, 867, 893, 920][k], 165, id, { orient: "v", reg: true, label: `G${k + 1}`, cote: "bas" }));
  const regGct = Sym._groupe(svg, "REG_GCTC", "regulation", "Régulation du contournement (consigne)");
  svgEl("rect", { x: 830, y: 225, width: 100, height: 22, rx: 4, class: "corps" }, regGct);
  Sym.texte(regGct, 880, 240, "GCT-c", "lib");
  svgEl("text", { x: 880, y: 222, class: "val", "text-anchor": "middle", "data-gct-mode": "1" }, svg).textContent = "—";
  D(Sym.valeur(svg, 890, 270, "gctc.qm_kg_s", "kg/s", 0, "val", "start"));

  // ------------------------------------------------------------------ turbine + alternateur
  const tu = Sym._groupe(svg, "TURBINE", "turbine", "Groupe turbo-alternateur");
  svgEl("polygon", { points: "1000,52 1060,37 1060,103 1000,88", class: "corps" }, tu);
  svgEl("polygon", { points: "1080,45 1240,15 1240,125 1080,95", class: "corps" }, tu);
  svgEl("line", { x1: 1060, y1: 70, x2: 1080, y2: 70, stroke: "#c8d2dc", "stroke-width": 3 }, tu);
  svgEl("line", { x1: 1240, y1: 70, x2: 1294, y2: 70, stroke: "#c8d2dc", "stroke-width": 3 }, tu);
  svgEl("circle", { cx: 1320, cy: 70, r: 26, class: "corps alternateur-corps" }, tu);
  Sym.texte(tu, 1030, 74, "HP", "lib-fort");
  Sym.texte(tu, 1160, 74, "BP", "lib-fort");
  Sym.texte(tu, 1320, 75, "~", "lib-fort");
  const arret = svgEl("g", { "data-vanne-turbine": "ouverture_arret_pct" }, svg);
  Sym.vanne(arret, 955, Y_COLLECTEUR, "TURBINE", { label: "arrêt", cote: "haut" });
  const reglage = svgEl("g", { "data-vanne-turbine": "ouverture_reglage_pct" }, svg);
  Sym.vanne(reglage, 980, Y_COLLECTEUR, "TURBINE", { label: "réglage", reg: true, cote: "bas" });
  svgEl("line", { x1: 1346, y1: 70, x2: 1440, y2: 70, stroke: "#c8d2dc", "stroke-width": 3, "data-couplage": "1" }, svg);
  Sym.texte(svg, 1465, 74, "400 kV", "lib", "middle");
  Sym.valeur(svg, 1320, 118, "turbine.p_elec_mw", "MWe", 0, "val-fort");
  D(Sym.valeur(svg, 1320, 134, "turbine.vitesse_tr_min", "tr/min", 0, "val"));
  D(Sym.valeur(svg, 1170, 145, "turbine.charge_pct", "%", 1, "val", "start", "charge "));

  // ------------------------------------------------------------------ RPR (protection)
  const rpr = Sym._groupe(svg, "RPR", "regulation", "Protection réacteur : AU, réarmements");
  svgEl("rect", { x: 1365, y: 190, width: 115, height: 50, rx: 6, class: "corps" }, rpr);
  Sym.texte(rpr, 1422, 210, "RPR — AU", "lib-fort");
  Sym.texte(rpr, 1422, 228, "déclencher / réarmer", "atm");

  // ------------------------------------------------------------------ condenseur, CRF, puits, CST
  const cd = Sym._groupe(svg, "CONDENSEUR", "echangeur", "Condenseur");
  svgEl("rect", { x: 1040, y: 330, width: 260, height: 110, rx: 8, class: "corps" }, cd);
  Sym.texte(cd, 1105, 352, "CONDENSEUR", "lib-fort");
  Sym.valeur(svg, 1230, 352, "condenseur.p_bar", "bar", 3, "val-fort");
  D(Sym.valeur(svg, 1230, 370, "condenseur.t_c", "°C", 1, "val"));
  D(Sym.valeur(svg, 1105, 370, "condenseur.q_mw", "MW", 0, "val", "middle", "Q "));
  Sym.pompe(svg, 1390, 345, "CRF1", { sens: "gauche", cote: "droite", label: "CRF1" });
  Sym.pompe(svg, 1390, 395, "CRF2", { sens: "gauche", cote: "droite", label: "CRF2" });
  D(Sym.valeur(svg, 1465, 335, "crf.debit_m3s", "m³/s", 1, "val"));
  D(Sym.texte(svg, 1470, 420, "→ mer", "atm"));
  Sym.bache(svg, 1100, 440, 140, 60, "PUITS", "puits.niveau_pct", "Puits");
  Sym.valeur(svg, 1170, 476, "puits.niveau_pct", "%", 1, "val-fort", "middle", "puits ");
  const regPuits = Sym._groupe(svg, "REG_PUITS", "regulation", "Régulation niveau puits (consigne)");
  svgEl("rect", { x: 1245, y: 470, width: 72, height: 20, rx: 4, class: "corps" }, regPuits);
  Sym.texte(regPuits, 1281, 484, "rég. puits", "lib");
  Sym.pompe(svg, 1130, 560, "CEX1", { sens: "bas", cote: "gauche" });
  Sym.pompe(svg, 1210, 560, "CEX2", { sens: "bas", cote: "droite" });
  Sym.clapet(svg, 1130, 605, "CEX1_CLAPET", "v");
  Sym.clapet(svg, 1210, 605, "CEX2_CLAPET", "v");
  D(Sym.valeur(svg, 1180, 700, "cex.q_m3h", "m³/h", 0, "val", "start", "CEX "));
  Sym.vanne(svg, 1060, 600, "CEX_RECIRC", { orient: "v", label: "recirc.", cote: "gauche" });
  Sym.bache(svg, 1380, 600, 90, 180, "CST", "cst.niveau_pct", "CST");
  Sym.texte(svg, 1425, 620, "CST", "lib-fort");
  Sym.valeur(svg, 1425, 800, "cst.volume_m3", "m³", 0, "val");
  Sym.vanne(svg, 1330, 560, "PUITS_APPOINT", { orient: "v", reg: true, label: "appoint", cote: "gauche" });
  Sym.vanne(svg, 1320, Y_POSTE, "PUITS_REJET", { reg: true, label: "rejet", cote: "bas" });

  // ------------------------------------------------------------------ poste d'eau
  Sym.echangeur(svg, 980, Y_POSTE - 15, 60, 30, "ABP", "ABP (réch. BP)");
  D(Sym.valeur(svg, 1010, Y_POSTE + 46, "abp.t_c", "°C", 0, "val"));
  Sym.pompe(svg, 895, 790, "REP1", { sens: "haut", cote: "gauche" });
  Sym.pompe(svg, 945, 790, "REP2", { sens: "haut", cote: "droite" });
  D(Sym.texte(svg, 920, 838, "reprise des purges", "atm"));
  D(Sym.valeur(svg, 912, 745, "reprise.qm_kg_s", "kg/s", 0, "val", "end"));
  Sym.pompe(svg, 830, 680, "APP1", { sens: "gauche", cote: "droite" });
  Sym.pompe(svg, 830, Y_POSTE, "APP2", { sens: "gauche", cote: "droite" });
  Sym.pompe(svg, 830, 770, "APD", { sens: "gauche", cote: "droite" });
  Sym.clapet(svg, 800, 680, "APP1_CLAPET");
  Sym.clapet(svg, 800, Y_POSTE, "APP2_CLAPET");
  Sym.clapet(svg, 800, 770, "APD_CLAPET");
  D(Sym.valeur(svg, 830, 662, "APP1.vitesse_pct", "%", 0, "val"));
  D(Sym.valeur(svg, 830, 822, "N_ABP.p_bar", "bar", 1, "val", "middle", "aspi "));
  Sym.echangeur(svg, 700, Y_POSTE - 15, 60, 30, "AHP", "AHP (réch. HP)");
  Sym.valeur(svg, 730, Y_POSTE + 46, "alim.t_c", "°C", 0, "val", "middle", "T alim ");
  D(Sym.valeur(svg, 740, 690, "alim.dp_bar", "bar", 1, "val", "middle", "ΔP "));
}
