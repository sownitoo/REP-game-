// Petite bibliothèque de symboles SVG pour les synoptiques (P&ID simplifié).
// Chaque équipement manœuvrable porte data-id = repère du composant côté serveur.
"use strict";

const SVG_NS = "http://www.w3.org/2000/svg";

function svgEl(tag, attrs, parent) {
  const e = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}

const Sym = {
  defs(svg) {
    const defs = svgEl("defs", {}, svg);
    const g = svgEl("linearGradient", { id: "demi", x1: "0", x2: "1", y1: "0", y2: "0" }, defs);
    svgEl("stop", { offset: "50%", "stop-color": "#c8d2dc" }, g);
    svgEl("stop", { offset: "50%", "stop-color": "#0d1217" }, g);
    const m = svgEl("marker", { id: "fleche", viewBox: "0 0 10 10", refX: "8", refY: "5",
      markerWidth: "6", markerHeight: "6", orient: "auto-start-reverse" }, defs);
    svgEl("path", { d: "M0,0 L10,5 L0,10 z", fill: "#8392a3" }, m);
    const f = svgEl("marker", { id: "fleche-flux", viewBox: "0 0 10 10", refX: "7", refY: "5",
      markerWidth: "11", markerHeight: "11", orient: "auto-start-reverse", markerUnits: "userSpaceOnUse" }, defs);
    svgEl("path", { d: "M0,1 L9,5 L0,9 z", fill: "#aab6c2", class: "pointe-flux" }, f);
  },

  // Tuyau : liste de points [[x,y],…], classe = eau | vapeur | mer | purge ; débit animé si |mesure| > seuil
  tuyau(svg, points, classe, mesureDebit, seuil = 1) {
    const attrs = { points: points.map(p => p.join(",")).join(" "), class: `tuyau ${classe}` };
    if (mesureDebit) { attrs["data-debit"] = mesureDebit; attrs["data-seuil"] = seuil; }
    return svgEl("polyline", attrs, svg);
  },

  _groupe(svg, id, classe, titre) {
    const g = svgEl("g", { class: `equip ${classe}`, "data-id": id }, svg);
    if (titre) svgEl("title", {}, g).textContent = titre;
    return g;
  },

  // Vanne papillon (deux triangles) ; orient = "h" ou "v" ; reg = vanne régulée (actionneur)
  vanne(svg, x, y, id, { orient = "h", label = id, reg = false, cote = "bas", detail = false } = {}) {
    const g = this._groupe(svg, id, "vanne", id);
    const t = orient === "h"
      ? [`${x - 10},${y - 7} ${x - 10},${y + 7} ${x},${y}`, `${x + 10},${y - 7} ${x + 10},${y + 7} ${x},${y}`]
      : [`${x - 7},${y - 10} ${x + 7},${y - 10} ${x},${y}`, `${x - 7},${y + 10} ${x + 7},${y + 10} ${x},${y}`];
    t.forEach(p => svgEl("polygon", { points: p, class: "corps" }, g));
    if (reg) {
      const [dx, dy] = orient === "h" ? [0, -1] : [1, 0];
      svgEl("line", { x1: x, y1: y, x2: x + dx * 13, y2: y + dy * 13, stroke: "#c8d2dc", "stroke-width": 1.5 }, g);
      svgEl("rect", { x: x + dx * 13 - 5, y: y + dy * 13 - 5, width: 10, height: 10, class: "corps" }, g);
    }
    svgEl("text", { x: x + 12, y: y - 9, class: "manu" }, g).textContent = "M";
    if (label) {
      const pos = { bas: [x, y + 22, "middle"], haut: [x, y - 14, "middle"], droite: [x + 14, y + 4, "start"],
                    gauche: [x - 14, y + 4, "end"] }[cote];
      svgEl("text", { x: pos[0], y: pos[1], class: detail ? "lib detail" : "lib", "text-anchor": pos[2] }, g).textContent = label;
    }
    return g;
  },

  clapet(svg, x, y, id, orient = "h") {
    const g = this._groupe(svg, id, "clapet", `${id} (clapet anti-retour)`);
    const p = orient === "h"
      ? `${x - 7},${y - 6} ${x - 7},${y + 6} ${x + 5},${y}`
      : `${x - 6},${y + 7} ${x + 6},${y + 7} ${x},${y - 5}`;
    svgEl("polygon", { points: p, class: "corps" }, g);
    if (orient === "h") svgEl("line", { x1: x + 6, y1: y - 7, x2: x + 6, y2: y + 7, stroke: "#c8d2dc", "stroke-width": 2 }, g);
    else svgEl("line", { x1: x - 7, y1: y - 6, x2: x + 7, y2: y - 6, stroke: "#c8d2dc", "stroke-width": 2 }, g);
    return g;
  },

  pompe(svg, x, y, id, { label = id, sens = "droite", cote = "bas", rayon = 13, titre = id } = {}) {
    const g = this._groupe(svg, id, "pompe", titre);
    svgEl("circle", { cx: x, cy: y, r: rayon, class: "corps" }, g);
    const k = rayon / 13;
    const f = { droite: [[-6, -7], [-6, 7], [8, 0]], gauche: [[6, -7], [6, 7], [-8, 0]],
                haut: [[-7, 6], [7, 6], [0, -8]], bas: [[-7, -6], [7, -6], [0, 8]] }[sens];
    svgEl("polygon", { points: f.map(([a, b]) => `${x + a * k},${y + b * k}`).join(" "), class: "fleche" }, g);
    if (cote !== "aucun") {
      const pos = cote === "bas" ? [x, y + rayon + 14, "middle"] : cote === "droite" ? [x + rayon + 5, y + 4, "start"]
                                                                 : [x - rayon - 5, y + 4, "end"];
      svgEl("text", { x: pos[0], y: pos[1], class: "lib", "text-anchor": pos[2] }, g).textContent = label;
    }
    return g;
  },

  // Jauge verticale de niveau (mesure en %), centrée en (x, y), hauteur h
  jauge(svg, x, y, h, mesureNiveau) {
    const g = svgEl("g", { class: "jauge" }, svg);
    svgEl("rect", { x: x - 4, y: y - h / 2, width: 8, height: h, rx: 2, class: "jauge-fond" }, g);
    svgEl("rect", { x: x - 3, y: y + h / 2 - 1, width: 6, height: 0, class: "eau",
                    "data-niveau": mesureNiveau, "data-bas": y + h / 2 - 1, "data-haut": h - 2 }, g);
    return g;
  },

  soupape(svg, x, y, id, label) {
    const g = this._groupe(svg, id, "soupape", id);
    svgEl("polygon", { points: `${x - 6},${y + 6} ${x + 6},${y + 6} ${x},${y - 4}`, class: "corps" }, g);
    svgEl("polyline", { points: `${x},${y - 4} ${x - 3},${y - 7} ${x + 3},${y - 10} ${x - 3},${y - 13} ${x},${y - 15}`,
                        fill: "none", stroke: "#c8d2dc", "stroke-width": 1.2 }, g);
    if (label) svgEl("text", { x: x - 9, y: y + 4, class: "lib", "text-anchor": "end" }, g).textContent = label;
    return g;
  },

  echangeur(svg, x, y, w, h, id, label) {
    const g = this._groupe(svg, id, "echangeur", label);
    svgEl("rect", { x, y, width: w, height: h, rx: 4, class: "corps" }, g);
    svgEl("polyline", { points: `${x + 4},${y + h / 2} ${x + w * .25},${y + 4} ${x + w * .5},${y + h - 4} ${x + w * .75},${y + 4} ${x + w - 4},${y + h / 2}`,
                        fill: "none", stroke: "#e07a4f", "stroke-width": 1.5 }, g);
    svgEl("text", { x: x + w / 2, y: y + h + 14, class: "lib", "text-anchor": "middle" }, g).textContent = label;
    return g;
  },

  // Bâche avec niveau (mesure en %)
  bache(svg, x, y, w, h, id, mesureNiveau, label) {
    const g = this._groupe(svg, id, "bache", label);
    svgEl("rect", { x, y, width: w, height: h, class: "contour" }, g);
    if (mesureNiveau) svgEl("rect", { x: x + 1, y: y + h, width: w - 2, height: 0, class: "eau",
                                      "data-niveau": mesureNiveau, "data-bas": y + h - 1, "data-haut": h - 2 }, g);
    return g;
  },

  gv(svg, x, y, w, h, id) {
    const g = this._groupe(svg, id, "gv", id);
    svgEl("rect", { x, y, width: w, height: h, rx: w / 2.2, class: "contour" }, g);
    svgEl("rect", { x: x + 3, y: y + 20, width: w - 6, height: h - 40, class: "vapeur-zone" }, g);
    svgEl("rect", { x: x + 3, y: y + h - 20, width: w - 6, height: 0, class: "eau",
                    "data-niveau": `${id}.niveau_vrai_pct`, "data-bas": y + h - 20, "data-haut": h - 40 }, g);
    return g;
  },

  texte(svg, x, y, txt, cls = "lib", anchor = "middle") {
    const t = svgEl("text", { x, y, class: cls, "text-anchor": anchor }, svg);
    t.textContent = txt;
    return t;
  },

  // Valeur mesurée mise à jour en direct
  valeur(svg, x, y, mesure, unite, dec = 1, cls = "val", anchor = "middle", prefixe = "") {
    const t = svgEl("text", { x, y, class: cls, "text-anchor": anchor, "data-mesure": mesure,
                              "data-unite": unite, "data-dec": dec, "data-prefixe": prefixe }, svg);
    t.textContent = "—";
    return t;
  },

  // marque un élément comme « détail » : visible seulement en zoomant
  detail(el) { el.classList.add("detail"); return el; },

  fleche(svg, x1, y1, x2, y2) {
    return svgEl("line", { x1, y1, x2, y2, stroke: "#8392a3", "stroke-width": 1.5, "marker-end": "url(#fleche)" }, svg);
  },
};
