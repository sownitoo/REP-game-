// Synoptique « Primaire » : cuve + 4 boucles (BC → GV → pompe → BF), pressuriseur, charge/décharge.
// Repère 1500 × 880. Chaque data-id = repère côté serveur.
"use strict";

function construirePrimaire(svg) {
  Sym.defs(svg);
  const Y = [150, 310, 470, 630];             // branche chaude de chaque boucle
  const X_CUVE = 290, X_GV = 520, X_POMPE = 760;

  // ------------------------------------------------------------------ ligne d'expansion, aspersion, décharges PZR
  Sym.tuyau(svg, [[440, Y[1]], [440, 282], [1090, 282], [1090, 262]], "primaire-chaud", "pzr.expansion_kg_s", 0.3);
  Sym.tuyau(svg, [[X_POMPE, Y[1] + 95], [1180, Y[1] + 95]], "primaire-froid", "pzr.aspersion_kg_s", 0.5);
  Sym.tuyau(svg, [[X_POMPE, Y[2] + 95], [1180, Y[2] + 95], [1180, 58], [1115, 58], [1115, 72]], "primaire-froid",
            "pzr.aspersion_kg_s", 0.5);
  Sym.tuyau(svg, [[1065, 72], [1065, 12], [900, 12]], "vapeur", "pzr.porv_qm_kg_s", 0.1);
  Sym.tuyau(svg, [[1065, 30], [900, 30]], "vapeur", "pzr.porv_qm_kg_s", 0.1);
  Sym.tuyau(svg, [[1065, 48], [975, 48]], "vapeur");
  Sym.texte(svg, 892, 25, "PRT (V2) ←", "atm", "end");

  // ------------------------------------------------------------------ boucles
  Y.forEach((y, i) => {
    const b = i + 1;
    Sym.tuyau(svg, [[X_CUVE, y], [X_GV, y]], "primaire-chaud", `B${b}.debit_pct`, 1);
    Sym.tuyau(svg, [[X_GV + 120, y + 60], [X_POMPE - 13, y + 60]], "primaire-froid", `B${b}.debit_pct`, 1);
    Sym.tuyau(svg, [[X_POMPE, y + 73], [X_POMPE, y + 95], [X_CUVE, y + 95]], "primaire-froid", `B${b}.debit_pct`, 1);
    const gv = Sym._groupe(svg, `GV${b}`, "echangeur", `Générateur de vapeur ${b} (côté primaire)`);
    svgEl("rect", { x: X_GV, y: y - 45, width: 120, height: 120, rx: 10, class: "corps" }, gv);
    svgEl("path", { d: `M${X_GV} ${y} H${X_GV + 30} V${y - 30} Q${X_GV + 60} ${y - 55} ${X_GV + 90} ${y - 30} V${y + 60} H${X_GV + 120}`,
                    fill: "none", stroke: "#e07a4f", "stroke-width": 2 }, gv);
    Sym.texte(gv, X_GV + 60, y + 30, `GV${b}`, "lib-fort");
    Sym.valeur(gv, X_GV + 60, y + 48, `GV${b}.q_mw`, "MW", 0, "val");
    Sym.valeur(gv, X_GV + 60, y + 64, `GV${b}.p_bar`, "bar", 1, "val");
    Sym.pompe(svg, X_POMPE, y + 60, `PP${b}`, { sens: "bas", cote: "droite", label: `PP${b}` });
    Sym.pompe(svg, X_POMPE + 75, y + 20, `PSH${b}`, { sens: "droite", cote: "droite", label: "huile" });
    Sym.valeur(svg, 405, y - 7, `B${b}.t_bc_c`, "°C", 1, "val", "middle", "BC ");
    Sym.valeur(svg, 405, y + 88, `B${b}.t_bf_c`, "°C", 1, "val", "middle", "BF ");
    Sym.valeur(svg, 405, y + 48, `B${b}.dt_c`, "°C", 1, "val", "middle", "ΔT ");
    Sym.valeur(svg, X_POMPE + 25, y + 90, `B${b}.debit_pct`, "%", 1, "val", "start", "débit ");
    Sym.texte(svg, X_CUVE + 12, y - 8, `B${b}`, "lib-fort", "start");
  });

  // ------------------------------------------------------------------ cuve + cœur + grappes
  const cuve = Sym._groupe(svg, "GRAPPES", "cuve", "Cuve, cœur et grappes (cliquer pour piloter les grappes)");
  svgEl("rect", { x: 130, y: 80, width: 160, height: 690, rx: 70, class: "corps" }, cuve);
  svgEl("rect", { x: 160, y: 440, width: 100, height: 220, rx: 6, class: "coeur" }, cuve);
  Sym.texte(cuve, 210, 560, "CŒUR", "lib-fort");
  // grappes : barres dont la hauteur insérée suit la position
  svgEl("rect", { x: 178, y: 300, width: 14, height: 0, class: "grappe", "data-grappe": "grappes.position_pas",
                  "data-bas": 440, "data-haut": 140, "data-max": 228, "data-inverse": "1" }, cuve);
  svgEl("rect", { x: 228, y: 300, width: 14, height: 0, class: "grappe arret", "data-grappe": "grappes.arret_insere_pct",
                  "data-bas": 440, "data-haut": 140, "data-max": 100 }, cuve);
  Sym.texte(cuve, 185, 292, "rég.", "atm");
  Sym.texte(cuve, 235, 292, "arrêt", "atm");
  Sym.valeur(cuve, 210, 590, "coeur.puissance_pct", "%", 1, "val-fort");
  Sym.valeur(cuve, 210, 608, "coeur.rho_pcm", "pcm", 0, "val");
  Sym.valeur(cuve, 210, 430, "cuve.t_sortie_c", "°C", 1, "val", "middle", "sortie ");
  Sym.valeur(cuve, 210, 690, "cuve.t_entree_c", "°C", 1, "val", "middle", "entrée ");
  Sym.valeur(cuve, 210, 110, "grappes.position_pas", "pas", 0, "val");

  // ------------------------------------------------------------------ pressuriseur
  const pzr = Sym._groupe(svg, "PZR", "gv", "Pressuriseur");
  svgEl("rect", { x: 1050, y: 72, width: 80, height: 190, rx: 36, class: "contour" }, pzr);
  svgEl("rect", { x: 1053, y: 250, width: 74, height: 0, class: "eau", "data-niveau": "pzr.niveau_pct",
                  "data-bas": 258, "data-haut": 182 }, pzr);
  Sym.texte(pzr, 1090, 100, "PZR", "lib-fort");
  const chP = Sym._groupe(svg, "PZR_CHAUF_P", "chaufferette", "Chaufferettes proportionnelles");
  svgEl("rect", { x: 1055, y: 266, width: 32, height: 12, rx: 2, class: "corps" }, chP);
  const chT = Sym._groupe(svg, "PZR_CHAUF_T", "chaufferette", "Chaufferettes tout-ou-rien");
  svgEl("rect", { x: 1093, y: 266, width: 32, height: 12, rx: 2, class: "corps" }, chT);
  Sym.texte(svg, 1090, 300, "chaufferettes P / TOR", "atm");
  Sym.vanne(svg, 1000, Y[1] + 95, "PZR_ASP2", { reg: true, label: "aspersion B2", cote: "bas" });
  Sym.vanne(svg, 1000, Y[2] + 95, "PZR_ASP3", { reg: true, label: "aspersion B3", cote: "bas" });
  Sym.vanne(svg, 1010, 12, "PZR_ISOL1", { label: "" });
  Sym.vanne(svg, 950, 12, "PZR_PORV1", { label: "" });
  Sym.vanne(svg, 1010, 30, "PZR_ISOL2", { label: "" });
  Sym.vanne(svg, 950, 30, "PZR_PORV2", { label: "" });
  Sym.texte(svg, 1010, 78, "isolement", "atm");
  Sym.texte(svg, 940, 78, "PORV 1 / 2", "atm");
  [1040, 1015, 990].forEach((x, k) => Sym.soupape(svg, x, 48, `PZR_SOUP${k + 1}`));
  Sym.texte(svg, 980, 64, "soupapes", "atm", "end");
  Sym.valeur(svg, 1145, 120, "pzr.p_bar", "bar", 2, "val-fort", "start", "P ");
  Sym.valeur(svg, 1145, 138, "pzr.niveau_pct", "%", 1, "val", "start", "niveau ");
  Sym.valeur(svg, 1145, 154, "pzr.niveau_programme_pct", "%", 1, "val", "start", "programme ");
  Sym.valeur(svg, 1145, 170, "pzr.chauffe_kw", "kW", 0, "val", "start", "chauffe ");
  Sym.valeur(svg, 1145, 186, "pzr.aspersion_kg_s", "kg/s", 1, "val", "start", "aspersion ");
  Sym.valeur(svg, 1145, 202, "pzr.expansion_kg_s", "kg/s", 1, "val", "start", "expansion ");
  const regP = Sym._groupe(svg, "REG_P_PZR", "regulation", "Régulation de pression PZR (consigne)");
  svgEl("rect", { x: 1145, y: 214, width: 105, height: 20, rx: 4, class: "corps" }, regP);
  Sym.texte(regP, 1197, 228, "consigne pression", "lib");

  // ------------------------------------------------------------------ charge / décharge (RCV simplifié)
  Sym.texte(svg, 300, Y[0] + 112, "← charge (RCV)", "atm", "start");
  Sym.texte(svg, 300, Y[2] + 112, "→ décharge (RCV)", "atm", "start");
  Sym.texte(svg, 330, 806, "RCV simplifié (V1)", "lib-fort", "start");
  Sym.vanne(svg, 360, 835, "RCV_CHARGE", { reg: true, label: "charge", cote: "bas" });
  Sym.vanne(svg, 500, 835, "RCV_DECHARGE", { label: "décharge", cote: "bas" });
  Sym.valeur(svg, 380, 840, "rcv.charge_kg_s", "kg/s", 1, "val", "start");
  Sym.valeur(svg, 520, 840, "rcv.decharge_kg_s", "kg/s", 1, "val", "start");

  // ------------------------------------------------------------------ synthèse cœur + protections
  const x0 = 1265;
  Sym.texte(svg, x0, 330, "CŒUR ET PROTECTIONS", "lib-fort", "start");
  [["coeur.puissance_pct", "puissance neutronique", "%", 1], ["coeur.p_thermique_mw", "puissance thermique", "MW", 0],
   ["coeur.rho_pcm", "réactivité", "pcm", 0], ["coeur.t_comb_c", "T combustible", "°C", 0],
   ["grappes.position_pas", "groupe de régulation", "pas", 1], ["grappes.arret_insere_pct", "groupes d'arrêt insérés", "%", 0],
   ["primaire.tmoy_c", "Tmoy", "°C", 2], ["primaire.tref_c", "Tref", "°C", 2],
   ["cuve.marge_saturation_c", "marge à la saturation", "°C", 1], ["otdt.marge_pct", "marge ΔT surtempérature", "%", 1],
   ["opdt.marge_pct", "marge ΔT surpuissance", "%", 1], ["primaire.q_pompes_mw", "chaleur des pompes", "MW", 1]]
    .forEach(([m, lib, u, d], k) => {
      Sym.texte(svg, x0, 356 + k * 22, lib, "lib", "start");
      Sym.valeur(svg, 1490, 356 + k * 22, m, u, d, "val", "end");
    });
  const rpr = Sym._groupe(svg, "RPR", "regulation", "Protection réacteur : AU, réarmements, blocages");
  svgEl("rect", { x: 1265, y: 640, width: 225, height: 46, rx: 6, class: "corps" }, rpr);
  Sym.texte(rpr, 1377, 660, "RPR — AU, blocages", "lib-fort");
  Sym.texte(rpr, 1377, 677, "déclencher / réarmer / bloquer", "atm");
  Sym.texte(svg, 20, 878, "Cliquer sur la cuve pour piloter les grappes ; sur RPR pour l'AU. Couleurs : rouge = chaud, bleu = froid.",
            "atm", "start");
}
