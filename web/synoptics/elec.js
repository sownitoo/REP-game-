// Synoptique « Électricité · Air » : schéma unifilaire (réseau 400 kV, alternateur, TA / TS,
// tableaux 6,6 kV normaux LG et secourus LH, diesels, batteries 125 V) + collecteur d'air comprimé.
// Trait épais vert = tableau sous tension. Repère 1400 × 820.
"use strict";

function construireElec(svg) {
  Sym.defs(svg);
  const D = el => Sym.detail(el);
  const barre = (x1, x2, y, mesure, lib) => {
    svgEl("line", { x1, y1: y, x2, y2: y, class: "barre-elec", "data-tension": mesure }, svg);
    Sym.texte(svg, x1 - 10, y + 5, lib, "lib-fort", "end");
    Sym.valeur(svg, x2 + 10, y + 5, mesure, "%", 0, "val", "start");
  };
  const liaison = (pts, mesure) => svgEl("polyline", { points: pts.map(p => p.join(",")).join(" "),
    class: "liaison-elec", "data-tension": mesure }, svg);
  const disjoncteur = (x, y, attr) => svgEl("rect", { x: x - 8, y: y - 8, width: 16, height: 16, class: "disjoncteur",
                                                     "data-disj": attr }, svg);

  // ------------------------------------------------------------------ réseau, alternateur, transformateurs
  const res = Sym._groupe(svg, "RESEAU", "regulation", "Réseau 400 kV (commandes formateur : perte / retour)");
  svgEl("line", { x1: 120, y1: 70, x2: 1180, y2: 70, class: "barre-elec", "data-tension": "elec.reseau_pct" }, res);
  svgEl("rect", { x: 100, y: 40, width: 1100, height: 60, class: "zone-clic" }, res);
  Sym.texte(res, 110, 60, "RÉSEAU 400 kV", "lib-fort", "start");
  // alternateur → transfo principal → réseau ; soutirage (TS) vers LG
  svgEl("circle", { cx: 1290, cy: 150, r: 26, class: "corps alternateur-elec", "data-alternateur": "1" }, svg);
  Sym.texte(svg, 1290, 156, "~", "lib-fort");
  Sym.texte(svg, 1290, 196, "alternateur", "atm");
  liaison([[1264, 150], [1150, 150], [1150, 70]], "elec.alternateur_pct");
  Sym.texte(svg, 1160, 118, "transfo principal", "atm", "start");
  // TA (depuis le réseau) et TS (depuis l'alternateur) vers les deux tableaux normaux
  liaison([[300, 70], [300, 250]], "elec.ta_pct");
  liaison([[900, 70], [900, 250]], "elec.ta_pct");
  liaison([[1150, 150], [1150, 200], [480, 200], [480, 250]], "elec.ts_pct");
  liaison([[1080, 200], [1080, 250]], "elec.ts_pct");
  Sym.texte(svg, 310, 160, "TA (auxiliaires)", "atm", "start");
  Sym.texte(svg, 700, 193, "TS (soutirage)", "atm");
  svgEl("text", { x: 700, y: 236, class: "val", "text-anchor": "middle", "data-source-lg": "1" }, svg).textContent = "—";

  // ------------------------------------------------------------------ tableaux normaux et secourus
  barre(150, 550, 250, "elec.LGA.tension_pct", "LGA");
  barre(750, 1150, 250, "elec.LGB.tension_pct", "LGB");
  D(Sym.texte(svg, 350, 276, "PP1 · PP3 · CEX · CRF · chaufferettes proportionnelles", "atm"));
  D(Sym.texte(svg, 950, 276, "PP2 · PP4 · CEX · CRF", "atm"));
  barre(150, 550, 430, "elec.LHA.tension_pct", "LHA");
  barre(750, 1150, 430, "elec.LHB.tension_pct", "LHB");
  [["LHA", 350, "LGA"], ["LHB", 950, "LGB"]].forEach(([lh, x, lg]) => {
    liaison([[x, 250], [x, 430]], `elec.${lg}.tension_pct`);
    const g = Sym._groupe(svg, lh, "tableau", `${lh} : arrivée normale depuis ${lg}`);
    svgEl("rect", { x: x - 60, y: 315, width: 120, height: 50, class: "zone-clic" }, g);
    svgEl("rect", { x: x - 8, y: 332, width: 16, height: 16, class: "disjoncteur", "data-disj": `${lh}.arrivee_fermee` }, g);
    Sym.texte(g, x + 16, 344, "arrivée normale", "atm", "start");
  });

  // ------------------------------------------------------------------ diesels
  [["DIESEL_A", 90, "LHA", 150], ["DIESEL_B", 1310, "LHB", 1150]].forEach(([id, x, lh, xb]) => {
    const g = Sym._groupe(svg, id, "diesel", `${id} : groupe électrogène de secours (4,4 MW)`);
    svgEl("circle", { cx: x, cy: 540, r: 34, class: "corps" }, g);
    Sym.texte(g, x, 546, "G", "lib-fort");
    Sym.texte(g, x, 592, id.replace("_", " "), "lib-fort");
    svgEl("text", { x, y: 610, class: "val", "text-anchor": "middle", "data-diesel": id }, g).textContent = "—";
    liaison([[x, 506], [x, 470], [xb, 470], [xb, 430]], `elec.${id}.tension_pct`);
    disjoncteur((x + xb) / 2, 470, `${id}.couple`);
    D(Sym.valeur(svg, x, 628, `elec.${id}.charge_kw`, "kW", 0, "val", "middle", "charge "));
  });

  // ------------------------------------------------------------------ charges secourues
  const charges = { LHA: ["RCV_PC1", "RRI_P1", "SEC_P1", "ASG_MP1", "RRA_P1", "SAR_C1"],
                    LHB: ["RCV_PC2", "RRI_P2", "SEC_P2", "ASG_MP2", "RRA_P2", "SAR_C2"] };
  Object.entries(charges).forEach(([lh, ids]) => {
    const x0 = lh === "LHA" ? 180 : 780;
    ids.forEach((id, k) => {
      const x = x0 + k * 66;
      liaison([[x, 430], [x, 492]], `elec.${lh}.tension_pct`);
      Sym.pompe(svg, x, 506, id, { sens: "bas", cote: "bas", label: id.replace("_", " "), rayon: 12 });
    });
  });
  D(Sym.texte(svg, 700, 470, "Séquenceur après couplage : charge (2 s) · RRI (6,5 s) · SEC (11 s) · ASG (15,5 s) · air (20 s)", "atm"));

  // ------------------------------------------------------------------ batteries 125 V
  [["LBA", 575, "LHA", "2 h"], ["LBB", 1175, "LHB", "30 min"]].forEach(([lb, x, lh, autonomie]) => {
    liaison([[x - 30, 430], [x - 30, 640], [x, 640], [x, 680]], `elec.${lh}.tension_pct`);
    svgEl("rect", { x: x - 40, y: 680, width: 80, height: 50, rx: 4, class: "corps batterie" }, svg);
    Sym.texte(svg, x, 700, `${lb} 125 V`, "lib-fort");
    Sym.valeur(svg, x, 720, `elec.${lb}.charge_pct`, "%", 0, "val");
    Sym.jauge(svg, x + 54, 705, 50, `elec.${lb}.charge_pct`);
    D(Sym.texte(svg, x, 748, `autonomie ${autonomie} · contrôle-commande voie ${lb.slice(-1)}`, "atm"));
  });
  D(Sym.texte(svg, 830, 712, "chargeurs ← LH · onduleurs → 220 V ondulé", "atm"));

  // ------------------------------------------------------------------ air comprimé
  const sar = Sym._groupe(svg, "SAR", "regulation", "Collecteur d'air comprimé (isoler une fuite)");
  svgEl("rect", { x: 1196, y: 290, width: 180, height: 90, rx: 8, class: "corps" }, sar);
  Sym.texte(sar, 1286, 310, "AIR COMPRIMÉ", "lib-fort");
  Sym.valeur(sar, 1286, 334, "air.p_bar", "bar", 2, "val-geant");
  Sym.texte(sar, 1286, 354, "< 5 bar : vannes en repli", "atm");
  Sym.jauge(svg, 1388, 335, 80, "air.p_pct");
}
