// Synoptique « RRA · RRI · SEC » : 2 trains RRA (aspiration branche chaude → pompe → échangeur ∥ by-pass
// → branches froides), boucle RRI → échangeurs RRI/SEC → mer, accumulateurs (RIS passif).
// Repère 1400 × 800.
"use strict";

function construireRRA(svg) {
  Sym.defs(svg);
  const D = el => Sym.detail(el);
  const TRAINS = [[1, 170], [2, 400]];

  // ------------------------------------------------------------------ primaire (renvoi)
  const prim = Sym._groupe(svg, "GRAPPES", "source", "Primaire (onglet Primaire)");
  svgEl("rect", { x: 30, y: 120, width: 170, height: 380, rx: 10, class: "corps" }, prim);
  Sym.texte(prim, 115, 150, "PRIMAIRE", "lib-fort");
  Sym.valeur(prim, 115, 180, "primaire.tmoy_c", "°C", 1, "val-fort", "middle", "Tmoy ");
  Sym.valeur(prim, 115, 200, "pzr.p_bar", "bar", 1, "val", "middle", "P ");
  Sym.valeur(prim, 115, 220, "primaire.vitesse_refroidissement_c_h", "°C/h", 0, "val", "middle", "refroid. ");
  D(Sym.texte(prim, 115, 236, "(baisse de Tmoy sur 1 h)", "atm"));
  D(Sym.valeur(prim, 115, 260, "coeur.p_thermique_mw", "MW", 1, "val", "middle", "résiduelle "));
  Sym.texte(prim, 115, 470, "aspiration BC4 →", "atm");
  Sym.texte(prim, 115, 486, "← retour BF1-4", "atm");

  // ------------------------------------------------------------------ trains RRA
  TRAINS.forEach(([k, y]) => {
    const yr = y + 80;
    Sym.tuyau(svg, [[200, y], [580, y]], "primaire-chaud", `RRA${k}.debit_m3h`, 5).classList.add("fin");
    Sym.tuyau(svg, [[580, y], [580, y - 40], [880, y - 40], [880, y]], "eau", `RRA${k}.debit_m3h`, 5);
    Sym.tuyau(svg, [[580, y], [580, y + 30], [880, y + 30], [880, y]], "eau");
    Sym.tuyau(svg, [[880, y], [930, y], [930, yr], [200, yr]], "primaire-froid", `RRA${k}.debit_m3h`, 5).classList.add("fin");
    Sym.vanne(svg, 270, y, `RRA_ASP${k}A`, { label: "asp. A", cote: "haut" });
    Sym.vanne(svg, 340, y, `RRA_ASP${k}B`, { label: "asp. B", cote: "haut" });
    Sym.pompe(svg, 440, y, `RRA_P${k}`, { sens: "droite", cote: "bas", label: `RRA_P${k}`, rayon: 16 });
    Sym.clapet(svg, 510, y, `RRA_CLAPET${k}`);
    Sym.echangeur(svg, 640, y - 55, 90, 30, `ECH_RRA${k}`, "");
    Sym.texte(svg, 685, y - 62, `échangeur ${k} (RRI)`, "atm");
    Sym.vanne(svg, 800, y - 40, `RRA_HX${k}`, { reg: true, label: "", cote: "haut" });
    Sym.vanne(svg, 730, y + 30, `RRA_BP${k}`, { reg: true, label: "by-pass", cote: "bas", detail: true });
    Sym.valeur(svg, 440, y + 50, `RRA${k}.debit_m3h`, "m³/h", 0, "val", "middle");
    Sym.valeur(svg, 1000, y + 4, `RRA${k}.q_mw`, "MW", 1, "val-fort", "start");
    D(Sym.valeur(svg, 1000, y + 22, `RRA${k}.t_sortie_c`, "°C", 1, "val", "start", "sortie "));
  });
  D(Sym.texte(svg, 560, 560, "Aspiration ouvrable si P < 30 bar, refermée si P > 41 bar. Vannes d'échangeur en auto : "
              + "refroidissement régulé (~30 °C/h).", "atm"));

  // ------------------------------------------------------------------ RRI / SEC
  const xr = 1060;
  Sym.texte(svg, xr + 120, 90, "RRI → échangeurs RRA, RCV, pompes primaires", "atm");
  Sym.tuyau(svg, [[xr, 140], [xr, 360], [xr + 240, 360], [xr + 240, 140], [xr, 140]], "eau", "rri.q_mw", 0.1);
  Sym.pompe(svg, xr, 200, "RRI_P1", { sens: "haut", cote: "gauche", label: "RRI_P1" });
  Sym.pompe(svg, xr, 300, "RRI_P2", { sens: "haut", cote: "gauche", label: "RRI_P2" });
  Sym.echangeur(svg, xr + 200, 230, 80, 40, "ECH_SEC", "RRI / SEC");
  Sym.valeur(svg, xr + 120, 200, "rri.t_c", "°C", 1, "val-fort", "middle", "RRI ");
  D(Sym.valeur(svg, xr + 120, 220, "rri.q_mw", "MW", 1, "val", "middle", "reçus "));
  Sym.tuyau(svg, [[xr + 240, 420], [xr + 240, 270]], "mer", "sec.q_mw", 0.1);
  Sym.tuyau(svg, [[xr + 260, 230], [xr + 260, 120], [1390, 120]], "mer", "sec.q_mw", 0.1);
  Sym.texte(svg, 1390, 112, "→ mer", "atm", "end");
  Sym.pompe(svg, xr + 180, 460, "SEC_P1", { sens: "droite", cote: "bas", label: "SEC_P1" });
  Sym.pompe(svg, xr + 240, 460, "SEC_P2", { sens: "droite", cote: "bas", label: "SEC_P2" });
  Sym.tuyau(svg, [[xr + 180, 447], [xr + 180, 420], [xr + 240, 420]], "mer");
  Sym.texte(svg, xr + 210, 510, "eau de mer", "atm");
  D(Sym.valeur(svg, xr + 120, 400, "sec.q_mw", "MW", 1, "val", "middle", "vers la mer "));

  // ------------------------------------------------------------------ accumulateurs
  const ya = 640;
  Sym.texte(svg, 30, ya - 40, "ACCUMULATEURS (RIS passif) — à isoler sous P-11, avant 42 bar", "lib-fort", "start");
  [1, 2, 3, 4].forEach((b, i) => {
    const x = 120 + i * 250;
    Sym.bache(svg, x - 30, ya - 20, 60, 110, `ACC${b}`, `ACC${b}.niveau_pct`, `Accumulateur ${b}`);
    Sym.texte(svg, x, ya - 26, `ACC${b}`, "lib");
    Sym.tuyau(svg, [[x + 30, ya + 70], [x + 110, ya + 70]], "eau", "accu.qm_kg_s", 0.5);
    Sym.vanne(svg, x + 70, ya + 70, `ACC${b}_ISOL`, { label: "", cote: "bas" });
    Sym.texte(svg, x + 116, ya + 74, `→ BF${b}`, "atm", "start");
    Sym.valeur(svg, x + 40, ya + 20, `ACC${b}.p_bar`, "bar", 1, "val", "start");
  });
}
