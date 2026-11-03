// Synoptique « ASG » : bâche CST → 2 motopompes + 1 turbopompe → vannes de réglage → 4 GV.
"use strict";

function construireASG(svg) {
  Sym.defs(svg);
  const Y_GV = [130, 270, 410, 550];
  const Y_POMPES = [220, 340, 460];
  // tuyauteries
  Sym.tuyau(svg, [[200, 560], [260, 560], [260, Y_POMPES[0]]], "eau", "asg.qm_kg_s", 0.5);
  Y_POMPES.forEach(y => Sym.tuyau(svg, [[260, y], [560, y]], "eau"));
  Sym.tuyau(svg, [[560, Y_POMPES[0]], [560, Y_POMPES[2]]], "eau", "asg.qm_kg_s", 0.5);
  Sym.tuyau(svg, [[560, 340], [700, 340], [700, Y_GV[0]], [700, Y_GV[3]]], "eau", "asg.qm_kg_s", 0.5);
  Y_GV.forEach((y, i) => Sym.tuyau(svg, [[700, y], [1150, y]], "eau", `GV${i + 1}.qm_asg_kg_s`, 0.3));
  Sym.tuyau(svg, [[380, 640], [380, Y_POMPES[2] + 13]], "vapeur", "ASG_TP.vitesse_pct", 1);

  // CST
  Sym.bache(svg, 80, 300, 120, 280, "CST", "cst.niveau_pct", "CST");
  Sym.texte(svg, 140, 290, "Bâche CST", "lib-fort");
  Sym.valeur(svg, 140, 600, "cst.volume_m3", "m³", 0, "val");

  // pompes
  Sym.pompe(svg, 380, Y_POMPES[0], "ASG_MP1", { sens: "droite", cote: "bas", label: "ASG_MP1 (motopompe)" });
  Sym.pompe(svg, 380, Y_POMPES[1], "ASG_MP2", { sens: "droite", cote: "bas", label: "ASG_MP2 (motopompe)" });
  Sym.pompe(svg, 380, Y_POMPES[2], "ASG_TP", { sens: "droite", cote: "bas", label: "ASG_TP (turbopompe)" });
  Sym.clapet(svg, 480, Y_POMPES[0], "ASG_MP1_CLAPET");
  Sym.clapet(svg, 480, Y_POMPES[1], "ASG_MP2_CLAPET");
  Sym.clapet(svg, 480, Y_POMPES[2], "ASG_TP_CLAPET");
  Sym.vanne(svg, 380, 600, "ASG_TP_VAP", { orient: "v", label: "prise vapeur", cote: "droite" });
  Sym.detail(Sym.texte(svg, 380, 660, "vapeur GV1 / GV2 ↑ (échappement à l'atmosphère)", "atm"));
  Sym.valeur(svg, 380, Y_POMPES[2] - 22, "ASG_TP.vitesse_pct", "%", 0, "val", "middle", "vitesse ");
  Sym.valeur(svg, 610, 330, "asg.p_refoulement_bar", "bar", 1, "val", "start", "refoulement ");
  Sym.valeur(svg, 610, 360, "asg.qm_kg_s", "kg/s", 1, "val-fort", "start", "total ");

  // vannes et GV
  Y_GV.forEach((y, i) => {
    const b = i + 1;
    Sym.vanne(svg, 850, y, `ASG${b}`, { reg: true, label: `ASG${b}`, cote: "bas" });
    Sym.clapet(svg, 980, y, `ASG${b}_CLAPET`);
    Sym.valeur(svg, 1050, y - 8, `GV${b}.qm_asg_kg_s`, "kg/s", 1, "val");
    Sym.gv(svg, 1150, y - 55, 60, 110, `GV${b}`);
    Sym.texte(svg, 1225, y - 20, `GV${b}`, "lib-fort", "start");
    Sym.valeur(svg, 1225, y, `GV${b}.niveau_pct`, "% GE", 1, "val", "start");
    Sym.valeur(svg, 1225, y + 18, `GV${b}.p_bar`, "bar", 1, "val", "start");
  });
  Sym.detail(Sym.texte(svg, 20, 690, "Démarrage automatique : niveau GV très bas (2 MP + TP) ou perte des 2 APP (2 MP). "
            + "Vannes ASG régulées sur le niveau GV (consigne sous celle de l'ARE).", "atm", "start"));
}
