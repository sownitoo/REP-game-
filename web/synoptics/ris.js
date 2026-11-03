// Synoptique « RIS · EAS · Enceinte » : aspiration PTR (injection directe) ou puisards (recirculation) →
// pompes HP (charge par la BIT), MP (SI), BP (RRA en injection), EAS (aspersion) → branches froides / rampes.
// À droite, l'enceinte : primaire, accumulateurs, PRT et son disque, atmosphère, puisards. Repère 1400 × 820.
"use strict";

function construireRIS(svg) {
  Sym.defs(svg);
  const D = el => Sym.detail(el);
  const X_ASP = 250, X_REF = 600;
  const POMPES = [["RCV_PC1", 120, "charge 1 (HP)"], ["RCV_PC2", 170, "charge 2 (HP)"], ["RIS_PMP1", 260, "SI 1 (MP)"],
                  ["RIS_PMP2", 310, "SI 2 (MP)"], ["RRA_P1", 400, "RRA 1 (BP)"], ["RRA_P2", 450, "RRA 2 (BP)"],
                  ["EAS_P1", 560, "aspersion 1"], ["EAS_P2", 610, "aspersion 2"]];

  // ------------------------------------------------------------------ enceinte (dessous)
  const enc = svgEl("g", { "data-info": "barriere3" }, svg);
  svgEl("rect", { x: 680, y: 40, width: 690, height: 760, rx: 150, class: "paroi-externe" }, enc);
  svgEl("rect", { x: 692, y: 52, width: 666, height: 736, rx: 140, class: "paroi-interne" }, enc);
  Sym.texte(svg, 1025, 30, "ENCEINTE DE CONFINEMENT", "titre-zone");

  // ------------------------------------------------------------------ aspiration : PTR et puisards
  Sym.bache(svg, 60, 120, 110, 240, "PTR", "rcv.ptr_pct", "Bâche PTR");
  Sym.texte(svg, 115, 112, "PTR 2 500 ppm", "lib-fort");
  Sym.valeur(svg, 115, 380, "rcv.ptr_pct", "%", 0, "val-fort");
  [[48, "48 % : recirculation"], [17, "17 % : arrêt aspersion"]].forEach(([pct, lib]) => {
    const y = 120 + 240 * (1 - pct / 100);
    svgEl("line", { x1: 55, y1: y, x2: 175, y2: y, class: "repere-niveau" }, svg);
    D(Sym.texte(svg, 52, y + 4, lib, "atm", "end"));
  });
  Sym.tuyau(svg, [[170, 340], [X_ASP, 340]], "eau");
  Sym.tuyau(svg, [[X_ASP, 120], [X_ASP, 730]], "eau", "ris.qm_kg_s", 0.5);
  ["RIS_PUISARD1", "RIS_PUISARD2"].forEach((id, k) => {
    const y = 690 + k * 40;
    Sym.tuyau(svg, [[X_ASP, y], [760, y]], "eau", "ris.recirculation", 0.5);
    Sym.vanne(svg, 470, y, id, { label: `puisard ${k + 1}`, cote: "haut" });
  });
  D(Sym.texte(svg, 470, 790, "recirculation : aspiration dans les puisards (ouverture manuelle, PTR < 48 %)", "atm"));

  // ------------------------------------------------------------------ pompes
  POMPES.forEach(([id, y, lib]) => {
    Sym.tuyau(svg, [[X_ASP, y], [346, y]], "eau");
    Sym.pompe(svg, 360, y, id, { sens: "droite", cote: "aucun", rayon: 14 });
    Sym.texte(svg, 340, y - 18, lib, "lib", "start");
    const fin = id.startsWith("EAS") ? 640 : id.startsWith("RCV") ? 420 : X_REF;
    Sym.tuyau(svg, [[374, y], [fin, y]], "eau");
  });
  // pompes de charge : collecteur → BIT (ouverte sur IS) → branches froides
  Sym.tuyau(svg, [[420, 120], [420, 170]], "eau");
  Sym.tuyau(svg, [[420, 145], [X_REF, 145]], "eau", "ris.q_hp_m3h", 0.5);
  Sym.vanne(svg, 500, 145, "RIS_BIT", { label: "BIT (IS)", cote: "bas" });
  D(Sym.texte(svg, 430, 196, "charge normale (RCV) : voir onglet RCV", "atm", "start"));
  Sym.valeur(svg, 520, 128, "ris.q_hp_m3h", "m³/h", 0, "val", "start", "HP ");
  Sym.valeur(svg, 520, 252, "ris.q_mp_m3h", "m³/h", 0, "val", "start", "MP ");
  Sym.valeur(svg, 520, 392, "ris.q_bp_m3h", "m³/h", 0, "val", "start", "BP ");
  Sym.valeur(svg, 520, 552, "ris.q_eas_m3h", "m³/h", 0, "val", "start", "EAS ");
  D(Sym.texte(svg, 520, 268, "débit nul > 106 bar", "atm", "start"));
  D(Sym.texte(svg, 520, 408, "débit nul > 14 bar", "atm", "start"));

  // ------------------------------------------------------------------ injection → branches froides
  Sym.tuyau(svg, [[X_REF, 120], [X_REF, 450], [X_REF, 300], [790, 300]], "eau", "ris.qm_kg_s", 0.5);
  Sym.texte(svg, 700, 292, "→ branches froides", "atm");
  const prim = Sym._groupe(svg, "GRAPPES", "source", "Primaire (onglet Primaire)");
  svgEl("rect", { x: 790, y: 190, width: 190, height: 220, rx: 12, class: "corps" }, prim);
  Sym.texte(prim, 885, 214, "PRIMAIRE", "lib-fort");
  Sym.valeur(prim, 885, 240, "pzr.p_bar", "bar", 1, "val-fort", "middle", "P ");
  Sym.valeur(prim, 885, 258, "pzr.niveau_pct", "%", 0, "val", "middle", "PZR ");
  Sym.valeur(prim, 885, 276, "cuve.marge_saturation_c", "°C", 1, "val", "middle", "marge sat. ");
  Sym.valeur(prim, 885, 300, "breche.primaire_kg_s", "kg/s", 1, "val breche", "middle", "brèche ");
  Sym.valeur(prim, 885, 318, "breche.rtgv_kg_s", "kg/s", 1, "val breche", "middle", "RTGV ");
  Sym.valeur(prim, 885, 336, "breche.vapeur_kg_s", "kg/s", 0, "val breche", "middle", "brèche vapeur ");
  Sym.valeur(prim, 885, 360, "accu.qm_kg_s", "kg/s", 1, "val", "middle", "accumulateurs ");
  Sym.valeur(prim, 885, 384, "cuve.niveau_pct", "%", 0, "val-fort", "middle", "niveau cuve ");
  D(Sym.valeur(prim, 885, 400, "primaire.vide_m3", "m³", 1, "val", "middle", "vide (vapeur) "));
  // accumulateurs
  [1, 2, 3, 4].forEach((b, k) => {
    const x = 800 + k * 45;
    svgEl("rect", { x, y: 440, width: 32, height: 50, rx: 6, class: "contour-acc" }, svg);
    Sym.vanne(svg, x + 16, 510, `ACC${b}_ISOL`, { orient: "v", label: "", cote: "bas" });
    Sym.texte(svg, x + 16, 470, `${b}`, "atm");
  });
  D(Sym.texte(svg, 885, 540, "accumulateurs (42 bar)", "atm"));

  // ------------------------------------------------------------------ aspersion (EAS) : rampes en haut de l'enceinte
  Sym.tuyau(svg, [[640, 610], [640, 560], [660, 560], [660, 90], [1300, 90]], "eau", "ris.q_eas_m3h", 1);
  for (let x = 780; x <= 1280; x += 50) svgEl("circle", { cx: x, cy: 102, r: 3, class: "goutte" }, svg);
  Sym.texte(svg, 1025, 80, "rampes d'aspersion (EAS)", "atm");

  // ------------------------------------------------------------------ PRT (bâche de décharge du PZR)
  Sym.tuyau(svg, [[980, 220], [1060, 220], [1060, 180]], "vapeur", "pzr.porv_qm_kg_s", 0.1);
  D(Sym.texte(svg, 1068, 236, "décharge PZR (PORV, soupapes)", "atm", "start"));
  Sym.bache(svg, 1040, 130, 130, 50, "PRT", null, "Bâche de décharge du PZR");
  Sym.texte(svg, 1105, 160, "PRT", "lib-fort");
  Sym.valeur(svg, 1180, 148, "prt.p_bar", "bar", 2, "val", "start");
  Sym.valeur(svg, 1180, 164, "prt.t_c", "°C", 0, "val", "start");
  svgEl("text", { x: 1105, y: 196, class: "val", "text-anchor": "middle", "data-disque": "1" }, svg).textContent = "disque intact";

  // ------------------------------------------------------------------ atmosphère et puisards
  const atm = svgEl("g", { "data-info": "barriere3" }, svg);
  svgEl("rect", { x: 1060, y: 290, width: 230, height: 120, rx: 10, class: "corps" }, atm);
  Sym.texte(atm, 1175, 312, "ATMOSPHÈRE", "lib-fort");
  Sym.valeur(atm, 1175, 338, "enceinte.p_rel_bar", "bar rel", 2, "val-geant");
  Sym.valeur(atm, 1175, 360, "enceinte.t_c", "°C", 1, "val");
  D(Sym.texte(atm, 1175, 380, "IS > 0,24 bar rel · aspersion > 2,07", "atm"));
  Sym.bache(svg, 760, 600, 540, 150, "PUISARDS", "enceinte.puisard_pct", "Puisards de l'enceinte");
  Sym.texte(svg, 1030, 594, "PUISARDS", "lib-fort");
  Sym.valeur(svg, 1030, 670, "enceinte.puisard_m3", "m³", 0, "val-fort");
  Sym.valeur(svg, 1030, 690, "enceinte.t_puisard_c", "°C", 0, "val");
}
