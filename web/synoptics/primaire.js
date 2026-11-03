// Synoptique « Primaire » en étoile (vue de dessus) : la cuve au centre, les 4 boucles en araignée.
// Chaque boucle : cuve → branche chaude → GV → branche en U → pompe primaire → branche froide → cuve.
// Repère 1400 × 900. Les éléments .detail n'apparaissent qu'en zoomant.
"use strict";

function construirePrimaire(svg) {
  Sym.defs(svg);
  const C = { x: 700, y: 450 };
  const R_CUVE = 118, R_GV = 50, R_PP = 22;
  // boucle 1 en haut à gauche, puis sens horaire ; (sx, sy) = sens de la diagonale
  const BOUCLES = [[1, -1, -1], [2, 1, -1], [3, 1, 1], [4, -1, 1]];
  // repère local d'un quart de plan (x vers l'extérieur, y vers le haut ou le bas selon la boucle)
  const GEO = { gv: [370, 215], pompe: [165, 305], angleChaud: 22, angleFroid: 62 };
  const D = el => { el.classList.add("detail"); return el; };

  const vers = (a, b, r) => {                       // point à distance r de a sur le segment a → b
    const dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy);
    return [a[0] + dx * r / l, a[1] + dy * r / l];
  };
  const milieu = (a, b, decalage = 0) => {          // milieu d'un segment, décalé perpendiculairement
    const dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy);
    return [(a[0] + b[0]) / 2 - dy / l * decalage, (a[1] + b[1]) / 2 + dx / l * decalage];
  };
  // valeur posée à côté du milieu d'un segment, du côté opposé au point « loin » (ne chevauche pas le trait)
  const etiquette = (a, b, loin, mesure, unite, dec, cls, prefixe = "") => {
    const dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy);
    let n = [-dy / l, dx / l];
    const m = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
    if (n[0] * (loin[0] - m[0]) + n[1] * (loin[1] - m[1]) > 0) n = [-n[0], -n[1]];
    const ancre = n[0] > 0.3 ? "start" : n[0] < -0.3 ? "end" : "middle";
    return Sym.valeur(svg, m[0] + n[0] * 12, m[1] + n[1] * 12 + (n[1] > 0 ? 9 : 0), mesure, unite, dec, cls, ancre, prefixe);
  };

  // ------------------------------------------------------------------ boucles
  const points = {};
  BOUCLES.forEach(([b, sx, sy]) => {
    const P = ([x, y]) => [C.x + sx * x, C.y + sy * y];
    const rad = d => d * Math.PI / 180;
    const buseChaude = P([R_CUVE * Math.cos(rad(GEO.angleChaud)), R_CUVE * Math.sin(rad(GEO.angleChaud))]);
    const buseFroide = P([R_CUVE * Math.cos(rad(GEO.angleFroid)), R_CUVE * Math.sin(rad(GEO.angleFroid))]);
    const gv = P(GEO.gv), pompe = P(GEO.pompe);
    const chaudFin = vers(gv, buseChaude, R_GV);
    const uDebut = vers(gv, pompe, R_GV), uFin = vers(pompe, gv, R_PP);
    const froidDebut = vers(pompe, buseFroide, R_PP);
    points[b] = { buseChaude, gv, pompe, chaudFin };
    const debit = `B${b}.debit_pct`;
    Sym.tuyau(svg, [buseChaude, chaudFin], "primaire-chaud", debit, 1).dataset.nominal = 100;
    Sym.tuyau(svg, [uDebut, uFin], "primaire-froid", debit, 1).dataset.nominal = 100;
    Sym.tuyau(svg, [froidDebut, buseFroide], "primaire-froid", debit, 1).dataset.nominal = 100;

    // GV (vue de dessus) + jauge de niveau côté extérieur
    const g = Sym._groupe(svg, `GV${b}`, "gv", `Générateur de vapeur ${b}`);
    svgEl("circle", { cx: gv[0], cy: gv[1], r: R_GV, class: "contour" }, g);
    svgEl("circle", { cx: gv[0], cy: gv[1], r: R_GV - 9, class: "faisceau" }, g);
    Sym.texte(g, gv[0], gv[1] - 4, `GV${b}`, "lib-fort");
    Sym.valeur(g, gv[0], gv[1] + 13, `GV${b}.q_mw`, "MW", 0, "val");
    const xj = gv[0] + sx * (R_GV + 14);
    Sym.jauge(svg, xj, gv[1], 70, `GV${b}.niveau_vrai_pct`);
    D(Sym.valeur(svg, xj + sx * 10, gv[1] - 26, `GV${b}.niveau_pct`, "%", 0, "val", sx > 0 ? "start" : "end"));
    D(Sym.valeur(svg, gv[0], gv[1] + sy * (R_GV + 16) + (sy > 0 ? 4 : 0), `GV${b}.p_bar`, "bar", 1, "val"));

    // pompe primaire + pompe de soulèvement d'huile
    const sensPompe = sy < 0 ? "bas" : "haut";
    Sym.pompe(svg, pompe[0], pompe[1], `PP${b}`, { sens: sensPompe, cote: "aucun", rayon: R_PP });
    const lib = [pompe[0] - sx * 34, pompe[1] + sy * 4];
    Sym.texte(svg, lib[0], lib[1], `PP${b}`, "lib-fort", sx > 0 ? "end" : "start");
    Sym.valeur(svg, lib[0], lib[1] + 15, debit, "%", 0, "val", sx > 0 ? "end" : "start");
    const huile = [pompe[0] + sx * 34, pompe[1] + sy * 26];
    Sym.pompe(svg, huile[0], huile[1], `PSH${b}`, { sens: "droite", cote: "aucun", rayon: 8, titre: `PSH${b} : soulèvement d'huile de PP${b}` });
    D(Sym.texte(svg, huile[0] + sx * 13, huile[1] + 4, "huile", "atm", sx > 0 ? "start" : "end"));

    // températures : branche chaude côté extérieur, branche froide côté extérieur, ΔT à l'intérieur (détail)
    etiquette(buseChaude, chaudFin, pompe, `B${b}.t_bc_c`, "°C", 1, "val chaud");
    etiquette(froidDebut, buseFroide, gv, `B${b}.t_bf_c`, "°C", 1, "val froid");
    D(etiquette(buseChaude, chaudFin, P([600, -600]), `B${b}.dt_c`, "°C", 1, "val", "ΔT "));
    Sym.texte(svg, C.x + sx * 520, C.y + sy * 400, `BOUCLE ${b}`, "titre-boucle", sx > 0 ? "end" : "start");
  });

  // ------------------------------------------------------------------ cuve + carte du cœur
  const cuve = Sym._groupe(svg, "GRAPPES", "cuve", "Cuve et cœur — clic : grappes ; double-clic : vue du cœur");
  svgEl("circle", { cx: C.x, cy: C.y, r: R_CUVE, class: "corps" }, cuve);
  svgEl("circle", { cx: C.x, cy: C.y, r: R_CUVE - 12, class: "enveloppe" }, cuve);
  const PAS = 9.2, taille = PAS - 1.2;
  const assemblages = svgEl("g", { class: "assemblages", "data-chaleur": "coeur.puissance_pct" }, cuve);
  CoeurGeo.assemblages.forEach(a => svgEl("rect", { x: C.x + a.dx * PAS - taille / 2, y: C.y + a.dy * PAS - taille / 2,
                                                     width: taille, height: taille, rx: 1 }, assemblages));
  CoeurGeo.grappes.forEach(gr => svgEl("circle", { cx: C.x + gr.dx * PAS, cy: C.y + gr.dy * PAS, r: 2.8,
                                                   class: `grappe-pt groupe-${gr.groupe}`, "data-grappe-groupe": gr.groupe }, cuve));
  Sym.valeur(svg, C.x, C.y + R_CUVE + 30, "coeur.puissance_pct", "%", 1, "val-geant");
  Sym.valeur(svg, C.x, C.y + R_CUVE + 50, "coeur.p_thermique_mw", "MWth", 0, "val");
  D(Sym.valeur(svg, C.x, C.y - R_CUVE - 54, "cuve.t_sortie_c", "°C", 1, "val chaud", "middle", "sortie "));
  D(Sym.valeur(svg, C.x, C.y - R_CUVE - 38, "cuve.t_entree_c", "°C", 1, "val froid", "middle", "entrée "));
  Sym.texte(svg, C.x, C.y - R_CUVE - 12, "CUVE", "lib-fort");
  D(Sym.texte(svg, C.x, C.y + R_CUVE + 68, "double-clic sur la cuve : vue du cœur", "atm"));

  // ------------------------------------------------------------------ pressuriseur (ligne d'expansion sur la branche chaude B3)
  const pz = { x: 1255, y: 425, l: 74, h: 170 };
  const haut = pz.y - pz.h / 2, bas = pz.y + pz.h / 2;
  const piquage = milieu(points[3].buseChaude, points[3].chaudFin, 0);
  Sym.tuyau(svg, [piquage, [pz.x, piquage[1]], [pz.x, bas]],
            "primaire-chaud", "pzr.expansion_kg_s", 0.3).classList.add("fin");
  D(Sym.texte(svg, 1100, piquage[1] - 8, "ligne d'expansion", "atm"));
  const groupePzr = Sym._groupe(svg, "PZR", "gv", "Pressuriseur");
  svgEl("rect", { x: pz.x - pz.l / 2, y: haut, width: pz.l, height: pz.h, rx: 34, class: "contour" }, groupePzr);
  svgEl("rect", { x: pz.x - pz.l / 2 + 3, y: bas - 8, width: pz.l - 6, height: 0, class: "eau",
                  "data-niveau": "pzr.niveau_pct", "data-bas": bas - 8, "data-haut": pz.h - 30 }, groupePzr);
  Sym.texte(groupePzr, pz.x, haut + 30, "PZR", "lib-fort");
  const chP = Sym._groupe(svg, "PZR_CHAUF_P", "chaufferette", "Chaufferettes proportionnelles");
  svgEl("rect", { x: pz.x - 34, y: bas + 6, width: 30, height: 10, rx: 2, class: "corps" }, chP);
  const chT = Sym._groupe(svg, "PZR_CHAUF_T", "chaufferette", "Chaufferettes tout-ou-rien");
  svgEl("rect", { x: pz.x + 4, y: bas + 6, width: 30, height: 10, rx: 2, class: "corps" }, chT);
  D(Sym.texte(svg, pz.x + 42, bas + 15, "chaufferettes", "atm", "start"));
  Sym.valeur(svg, pz.x + 48, pz.y - 18, "pzr.p_bar", "bar", 1, "val-fort", "start");
  Sym.valeur(svg, pz.x + 48, pz.y, "pzr.niveau_pct", "%", 1, "val", "start", "niveau ");
  D(Sym.valeur(svg, pz.x + 48, pz.y + 16, "pzr.niveau_programme_pct", "%", 1, "val", "start", "progr. "));
  D(Sym.valeur(svg, pz.x + 48, pz.y + 30, "pzr.chauffe_kw", "kW", 0, "val", "start", "chauffe "));
  D(Sym.valeur(svg, pz.x + 48, pz.y + 44, "pzr.aspersion_kg_s", "kg/s", 1, "val", "start", "asp. "));
  const regP = Sym._groupe(svg, "REG_P_PZR", "regulation", "Régulation de pression PZR (consigne)");
  svgEl("rect", { x: pz.x + 46, y: pz.y + 54, width: 92, height: 20, rx: 4, class: "corps" }, regP);
  Sym.texte(regP, pz.x + 92, pz.y + 68, "consigne P", "lib");

  // aspersion (depuis les branches froides B2 et B3, par renvoi)
  const yAsp = haut - 30;
  Sym.tuyau(svg, [[1120, yAsp], [pz.x - 16, yAsp], [pz.x - 16, haut + 4]], "primaire-froid", "pzr.aspersion_kg_s", 0.5)
    .classList.add("fin");
  Sym.tuyau(svg, [[1120, yAsp + 26], [1195, yAsp + 26], [1195, yAsp]], "primaire-froid", "pzr.aspersion_kg_s", 0.5)
    .classList.add("fin");
  Sym.vanne(svg, 1160, yAsp, "PZR_ASP2", { reg: true, label: "" });
  Sym.vanne(svg, 1160, yAsp + 26, "PZR_ASP3", { reg: true, label: "" });
  Sym.texte(svg, 1116, yAsp + 4, "BF2 →", "atm", "end");
  Sym.texte(svg, 1116, yAsp + 30, "BF3 →", "atm", "end");
  D(Sym.texte(svg, 1160, yAsp - 22, "aspersion", "atm"));

  // décharges : 2 PORV (avec isolement) + 3 soupapes → PRT
  const yDech = haut - 70, xD = pz.x + 16;
  Sym.tuyau(svg, [[xD, haut + 4], [xD, yDech - 40], [1385, yDech - 40]], "vapeur");
  Sym.tuyau(svg, [[xD, yDech], [1385, yDech]], "vapeur", "pzr.porv_qm_kg_s", 0.1);
  Sym.tuyau(svg, [[xD, yDech + 22], [1385, yDech + 22]], "vapeur", "pzr.porv_qm_kg_s", 0.1);
  Sym.vanne(svg, xD + 34, yDech, "PZR_ISOL1", { label: "" });
  Sym.vanne(svg, xD + 74, yDech, "PZR_PORV1", { label: "" });
  Sym.vanne(svg, xD + 34, yDech + 22, "PZR_ISOL2", { label: "" });
  Sym.vanne(svg, xD + 74, yDech + 22, "PZR_PORV2", { label: "" });
  [0, 1, 2].forEach(k => Sym.soupape(svg, xD + 30 + k * 26, yDech - 46, `PZR_SOUP${k + 1}`));
  D(Sym.texte(svg, xD + 34, yDech + 46, "isol.", "atm"));
  D(Sym.texte(svg, xD + 74, yDech + 46, "PORV", "atm"));
  D(Sym.texte(svg, xD + 56, yDech - 66, "soupapes", "atm"));
  Sym.texte(svg, 1390, yDech + 12, "PRT", "atm", "end");

  // ------------------------------------------------------------------ carte cœur + RPR (à gauche)
  const x0 = 24, y0 = 360;
  Sym.texte(svg, x0, y0, "CŒUR", "lib-fort", "start");
  [["coeur.rho_pcm", "réactivité", "pcm", 0, false], ["grappes.position_pas", "groupe R", "pas", 0, false],
   ["grappes.arret_insere_pct", "arrêt insérés", "%", 0, false], ["primaire.bore_ppm", "bore", "ppm", 0, false],
   ["primaire.tmoy_c", "Tmoy", "°C", 1, false], ["coeur.marge_arret_chaud_pcm", "marge d'arrêt", "pcm", 0, true],
   ["primaire.tref_c", "Tref", "°C", 1, true], ["cuve.marge_saturation_c", "marge saturation", "°C", 1, true],
   ["otdt.marge_pct", "marge ΔT surtemp.", "%", 1, true], ["opdt.marge_pct", "marge ΔT surpuiss.", "%", 1, true]]
    .forEach(([m, lib, u, d, det], k) => {
      const y = y0 + 22 + k * 19;
      const t = Sym.texte(svg, x0, y, lib, "lib", "start");
      const v = Sym.valeur(svg, x0 + 210, y, m, u, d, "val", "end");
      if (det) { D(t); D(v); }
    });
  const rpr = Sym._groupe(svg, "RPR", "regulation", "Protection réacteur : AU, réarmements, blocages");
  svgEl("rect", { x: x0, y: y0 + 222, width: 210, height: 34, rx: 6, class: "corps" }, rpr);
  Sym.texte(rpr, x0 + 105, y0 + 244, "RPR — AU · IS", "lib-fort");

  // ------------------------------------------------------------------ renvois RCV et RRA (cliquer : onglet)
  const lien = (x, y, onglet, titre, lignes) => {
    const g = svgEl("g", { class: "lien-onglet", "data-lien-onglet": onglet }, svg);
    svgEl("title", {}, g).textContent = `Ouvrir l'onglet ${titre}`;
    svgEl("rect", { x: x - 95, y: y - 16, width: 190, height: 22 + lignes.length * 16, rx: 6, class: "corps" }, g);
    Sym.texte(g, x, y, `${titre} ›`, "lib-fort");
    lignes.forEach(([m, u, d, p], k) => Sym.valeur(g, x, y + 18 + k * 16, m, u, d, "val", "middle", p));
    return g;
  };
  lien(700, 790, "rcv", "RCV · REA", [["primaire.bore_ppm", "ppm", 0, "bore "], ["rcv.charge_m3h", "m³/h", 1, "charge "]]);
  lien(130, 765, "rra", "RRA · RRI", [["rra.q_mw", "MW", 1, "RRA "], ["rri.t_c", "°C", 1, "RRI "]]);

  D(Sym.texte(svg, 20, 885, "Molette : zoom · glisser : se déplacer · clic : piloter · rouge = chaud, bleu = froid",
              "atm", "start"));
}
