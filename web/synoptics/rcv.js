// Synoptique « RCV · REA » : décharge (haut) → VCT ← REA ; charge (bas) : VCT / PTR → pompes → FCV-121 → primaire.
// Repère 1400 × 800.
"use strict";

function construireRCV(svg) {
  Sym.defs(svg);
  const D = el => Sym.detail(el);
  const Y_DECH = 150, Y_CH = 560, Y_JOINTS = 660;

  // ------------------------------------------------------------------ primaire (renvoi)
  const prim = Sym._groupe(svg, "GRAPPES", "source", "Primaire (onglet Primaire)");
  svgEl("rect", { x: 30, y: 320, width: 190, height: 160, rx: 10, class: "corps" }, prim);
  Sym.texte(prim, 125, 344, "PRIMAIRE", "lib-fort");
  Sym.valeur(prim, 125, 372, "primaire.bore_ppm", "ppm", 0, "val-geant");
  Sym.texte(prim, 125, 390, "bore", "atm");
  Sym.valeur(prim, 125, 414, "pzr.p_bar", "bar", 1, "val", "middle", "P ");
  Sym.valeur(prim, 125, 432, "pzr.niveau_pct", "%", 1, "val", "middle", "niveau PZR ");
  D(Sym.valeur(prim, 125, 458, "coeur.bore_arret_froid_ppm", "ppm", 0, "val", "middle", "requis à froid "));

  // ------------------------------------------------------------------ décharge
  Sym.tuyau(svg, [[125, 320], [125, Y_DECH], [500, Y_DECH]], "primaire-chaud", "rcv.decharge_m3h", 0.5).classList.add("fin");
  [110, 150, 190].forEach(y => Sym.tuyau(svg, [[500, Y_DECH], [500, y], [620, y], [620, Y_DECH]], "eau"));
  Sym.tuyau(svg, [[620, Y_DECH], [1000, Y_DECH], [1000, 210], [1080, 210], [1080, 250]], "eau", "rcv.decharge_m3h", 0.5);
  Sym.tuyau(svg, [[960, Y_DECH], [960, 70], [1010, 70]], "purge", "rcv.deviation_m3h", 0.5);
  Sym.vanne(svg, 250, Y_DECH, "RCV_LCV459", { label: "LCV-459", cote: "haut" });
  Sym.vanne(svg, 320, Y_DECH, "RCV_LCV460", { label: "LCV-460", cote: "haut" });
  Sym.echangeur(svg, 380, Y_DECH - 15, 70, 30, "REGEN", "régénérateur");
  ["RCV_ORIF1", "RCV_ORIF2", "RCV_ORIF3"].forEach((id, k) =>
    Sym.vanne(svg, 560, [110, 150, 190][k], id, { label: `orifice ${k + 1}`, cote: "haut", detail: k > 0 }));
  D(Sym.texte(svg, 560, 216, "17 / 17 / 10 m³/h", "atm"));
  Sym.vanne(svg, 680, Y_DECH, "RCV_ISOL_ENC", { label: "CV-8152", cote: "haut" });
  Sym.echangeur(svg, 740, Y_DECH - 15, 70, 30, "ECH_DECH", "échangeur (RRI)");
  D(Sym.texte(svg, 870, Y_DECH - 10, "PCV-131 (24,5 bar)", "atm"));
  Sym.vanne(svg, 960, 110, "RCV_DEVIATION", { orient: "v", label: "LCV-112A", cote: "gauche" });
  Sym.texte(svg, 1016, 74, "effluents", "atm", "start");
  Sym.valeur(svg, 880, Y_DECH + 24, "rcv.decharge_m3h", "m³/h", 1, "val-fort", "middle", "décharge ");
  D(Sym.valeur(svg, 775, Y_DECH + 48, "rcv.echangeur_mw", "MW", 2, "val", "middle", "vers RRI "));
  // RRA → RCV (HCV-128)
  Sym.tuyau(svg, [[710, 290], [710, Y_DECH]], "eau", "rcv.decharge_m3h", 1000);
  Sym.vanne(svg, 710, 240, "RCV_HCV128", { orient: "v", reg: true, label: "HCV-128", cote: "gauche" });
  Sym.texte(svg, 710, 306, "← RRA", "atm");

  // ------------------------------------------------------------------ VCT + REA
  Sym.bache(svg, 1030, 250, 100, 180, "VCT", "rcv.vct_niveau_pct", "VCT");
  Sym.texte(svg, 1080, 244, "VCT", "lib-fort");
  Sym.valeur(svg, 1145, 320, "rcv.vct_niveau_pct", "%", 0, "val-fort", "start");
  Sym.valeur(svg, 1145, 338, "rcv.vct_bore_ppm", "ppm", 0, "val", "start");
  Sym.bache(svg, 1200, 60, 70, 130, "ACIDE", "rea.acide_pct", "Acide borique");
  Sym.bache(svg, 1300, 60, 70, 130, "EAU_APPOINT", "rea.eau_pct", "Eau d'appoint");
  Sym.texte(svg, 1235, 52, "acide 7000 ppm", "atm");
  Sym.texte(svg, 1335, 52, "eau", "atm");
  D(Sym.valeur(svg, 1235, 206, "rea.acide_m3", "m³", 0, "val"));
  D(Sym.valeur(svg, 1335, 206, "rea.eau_m3", "m³", 0, "val"));
  Sym.tuyau(svg, [[1235, 190], [1235, 240]], "purge", "rea.q_acide_m3h", 0.1);
  Sym.tuyau(svg, [[1335, 190], [1335, 240]], "eau", "rea.q_eau_m3h", 0.1);
  const rea = Sym._groupe(svg, "REA", "regulation", "Appoint eau et bore : auto, borication, dilution, arrêt");
  svgEl("rect", { x: 1200, y: 240, width: 170, height: 46, rx: 6, class: "corps" }, rea);
  Sym.texte(rea, 1285, 259, "REA", "lib-fort");
  svgEl("text", { x: 1285, y: 277, class: "val", "text-anchor": "middle", "data-rea-mode": "1" }, rea).textContent = "—";
  Sym.tuyau(svg, [[1200, 300], [1130, 300]], "purge", "rea.q_total_m3h", 0.1);
  D(Sym.valeur(svg, 1285, 304, "rea.volume_restant_m3", "m³", 1, "val", "middle", "reste "));

  // ------------------------------------------------------------------ charge
  Sym.tuyau(svg, [[1080, 430], [1080, Y_CH], [960, Y_CH]], "eau", "rcv.charge_m3h", 0.5);
  Sym.tuyau(svg, [[1210, 680], [960, 680], [960, Y_CH]], "eau");
  Sym.tuyau(svg, [[1285, 286], [1285, 500], [960, 500], [960, Y_CH]], "purge", "rea.q_urgence_m3h", 0.1);
  Sym.vanne(svg, 1020, Y_CH, "RCV_ASP_VCT", { label: "LCV-112B/C", cote: "bas" });
  Sym.vanne(svg, 1060, 680, "RCV_ASP_PTR", { label: "LCV-112D/E", cote: "bas" });
  Sym.vanne(svg, 1140, 500, "RCV_BORI_URG", { label: "borication d'urgence", cote: "haut" });
  Sym.bache(svg, 1210, 620, 110, 150, "PTR", "rcv.ptr_pct", "Bâche PTR");
  Sym.texte(svg, 1265, 612, "PTR 2500 ppm", "atm");
  D(Sym.valeur(svg, 1265, 790, "rcv.ptr_m3", "m³", 0, "val"));
  [520, 600].forEach(y => Sym.tuyau(svg, [[960, Y_CH], [920, Y_CH], [920, y], [820, y], [820, Y_CH]], "eau"));
  Sym.pompe(svg, 870, 520, "RCV_PC1", { sens: "gauche", cote: "haut", label: "pompe de charge 1" });
  Sym.pompe(svg, 870, 600, "RCV_PC2", { sens: "gauche", cote: "bas", label: "pompe de charge 2" });
  Sym.tuyau(svg, [[820, Y_CH], [125, Y_CH], [125, 480]], "primaire-froid", "rcv.charge_m3h", 0.5).classList.add("fin");
  Sym.vanne(svg, 740, Y_CH, "RCV_CHARGE", { reg: true, label: "FCV-121", cote: "bas" });
  Sym.vanne(svg, 640, Y_CH, "RCV_ISOL_CHARGE", { label: "MO-8105/8106", cote: "bas" });
  Sym.valeur(svg, 420, Y_CH - 10, "rcv.charge_m3h", "m³/h", 1, "val-fort", "middle", "charge ");
  D(Sym.valeur(svg, 420, Y_CH + 22, "rcv.t_charge_c", "°C", 0, "val", "middle", "après régénérateur "));
  D(Sym.valeur(svg, 870, 470, "rcv.dispo_m3h", "m³/h", 0, "val", "middle", "disponible "));
  Sym.texte(svg, 140, 540, "→ BF1", "atm", "start");
  // injection aux joints
  Sym.tuyau(svg, [[800, Y_CH], [800, Y_JOINTS], [180, Y_JOINTS], [180, 480]], "eau", "rcv.joints_m3h", 0.5);
  Sym.vanne(svg, 560, Y_JOINTS, "RCV_JOINTS", { reg: true, label: "HCV-182 joints PP", cote: "bas" });
  D(Sym.valeur(svg, 400, Y_JOINTS - 8, "rcv.joints_m3h", "m³/h", 1, "val", "middle", "joints "));

  D(Sym.texte(svg, 20, 785, "Mise en service : pompe de charge → LCV-459/460 → orifice. Niveau PZR < 17 % ou IS : décharge isolée. "
              + "VCT très basse : aspiration sur la PTR.", "atm", "start"));
}
