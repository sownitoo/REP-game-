// Zoom et déplacement des synoptiques SVG : molette (zoom au curseur), glisser (déplacement),
// pincer (tactile), double-clic sur le fond (zoom ×2), boutons + − ⤢ et clavier (+ − 0 flèches).
// Plus on zoome, plus on voit de détails : les éléments .detail n'apparaissent qu'au-delà de SEUIL_DETAIL.
"use strict";

const Zoom = {
  ECHELLE_MAX: 8,
  SEUIL_DETAIL: 1.4,
  SEUIL_GLISSER_PX: 5,
  PAS_BOUTON: 1.6,
  DUREE_ANIM_MS: 180,

  activer(svg) {
    const vb = svg.viewBox.baseVal;
    const z = { x0: vb.x, y0: vb.y, w0: vb.width, h0: vb.height, x: vb.x, y: vb.y, w: vb.width, h: vb.height,
                pointeurs: new Map(), depart: null, glisse: false, anim: null };
    svg._zoom = z;
    svg.addEventListener("wheel", ev => this._molette(svg, ev), { passive: false });
    svg.addEventListener("pointerdown", ev => this._appui(svg, ev));
    svg.addEventListener("pointermove", ev => this._mouvement(svg, ev));
    ["pointerup", "pointercancel", "pointerleave"].forEach(t => svg.addEventListener(t, ev => this._relache(svg, ev)));
    // un glisser ne doit pas sélectionner l'équipement sous le curseur
    svg.addEventListener("click", ev => { if (z.glisse) { ev.stopPropagation(); ev.preventDefault(); } }, true);
    svg.addEventListener("dblclick", ev => {
      if (ev.target.closest("[data-id]")) return;               // double-clic sur un équipement : géré par l'appli
      const p = this._versSvg(svg, ev.clientX, ev.clientY);
      this.zoomer(svg, 2, p, true);
    });
    this._outils(svg);
    this._appliquer(svg);
  },

  // ------------------------------------------------------------------ API
  zoomer(svg, facteur, centre, anime = false) {
    const z = svg._zoom;
    const echelle = Math.min(this.ECHELLE_MAX, Math.max(1, (z.w0 / z.w) * facteur));
    const w = z.w0 / echelle, h = z.h0 / echelle;
    const c = centre || { x: z.x + z.w / 2, y: z.y + z.h / 2 };
    const cible = { x: c.x - (c.x - z.x) * (w / z.w), y: c.y - (c.y - z.y) * (h / z.h), w, h };
    this._aller(svg, cible, anime);
  },

  ajuster(svg, anime = true) {
    const z = svg._zoom;
    this._aller(svg, { x: z.x0, y: z.y0, w: z.w0, h: z.h0 }, anime);
  },

  // centre la vue sur un point (coordonnées du synoptique) avec une échelle donnée
  centrer(svg, x, y, echelle, anime = true) {
    const z = svg._zoom;
    const w = z.w0 / echelle, h = z.h0 / echelle;
    this._aller(svg, { x: x - w / 2, y: y - h / 2, w, h }, anime);
  },

  deplacer(svg, dxFraction, dyFraction) {
    const z = svg._zoom;
    this._aller(svg, { x: z.x + dxFraction * z.w, y: z.y + dyFraction * z.h, w: z.w, h: z.h }, true);
  },

  // ------------------------------------------------------------------ interne
  _versSvg(svg, cx, cy) {
    const pt = svg.createSVGPoint();
    pt.x = cx; pt.y = cy;
    return pt.matrixTransform(svg.getScreenCTM().inverse());
  },

  _borner(svg, v) {
    const z = svg._zoom, marge = 0.25;
    v.x = Math.min(z.x0 + z.w0 - v.w * (1 - marge), Math.max(z.x0 - v.w * marge, v.x));
    v.y = Math.min(z.y0 + z.h0 - v.h * (1 - marge), Math.max(z.y0 - v.h * marge, v.y));
    return v;
  },

  _aller(svg, cible, anime) {
    const z = svg._zoom;
    cancelAnimationFrame(z.anim);
    cible = this._borner(svg, cible);
    if (!anime) { Object.assign(z, cible); this._appliquer(svg); return; }
    const debut = { x: z.x, y: z.y, w: z.w, h: z.h }, t0 = performance.now();
    const etape = t => {
      const a = Math.min(1, (t - t0) / this.DUREE_ANIM_MS), k = 1 - (1 - a) ** 3;
      for (const c of ["x", "y", "w", "h"]) z[c] = debut[c] + (cible[c] - debut[c]) * k;
      this._appliquer(svg);
      if (a < 1) z.anim = requestAnimationFrame(etape);
    };
    z.anim = requestAnimationFrame(etape);
  },

  _appliquer(svg) {
    const z = svg._zoom;
    svg.setAttribute("viewBox", `${z.x} ${z.y} ${z.w} ${z.h}`);
    const echelle = z.w0 / z.w;
    svg.classList.toggle("zoom-detail", echelle >= this.SEUIL_DETAIL);
    if (svg._indicateur) svg._indicateur.textContent = `${Math.round(echelle * 100)} %`;
  },

  _molette(svg, ev) {
    ev.preventDefault();
    const z = svg._zoom;
    cancelAnimationFrame(z.anim);
    const delta = ev.deltaY * (ev.deltaMode === 1 ? 16 : 1);
    this.zoomer(svg, Math.exp(-delta * 0.0015), this._versSvg(svg, ev.clientX, ev.clientY));
  },

  _appui(svg, ev) {
    const z = svg._zoom;
    z.pointeurs.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
    z.glisse = false;
    const m = svg.getScreenCTM();
    z.depart = { cx: ev.clientX, cy: ev.clientY, x: z.x, y: z.y, unite: 1 / m.a, pinch: null };
    if (z.pointeurs.size === 2) {
      const [a, b] = [...z.pointeurs.values()];
      z.depart.pinch = { d: Math.hypot(a.x - b.x, a.y - b.y), w: z.w };
    }
  },

  _mouvement(svg, ev) {
    const z = svg._zoom;
    if (!z.pointeurs.has(ev.pointerId) || !z.depart) return;
    z.pointeurs.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
    if (z.pointeurs.size === 2 && z.depart.pinch) {
      const [a, b] = [...z.pointeurs.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      const centre = this._versSvg(svg, (a.x + b.x) / 2, (a.y + b.y) / 2);
      this.zoomer(svg, (z.depart.pinch.w / z.w) * (d / z.depart.pinch.d), centre);
      z.glisse = true;
      return;
    }
    const dx = ev.clientX - z.depart.cx, dy = ev.clientY - z.depart.cy;
    if (!z.glisse && Math.hypot(dx, dy) < this.SEUIL_GLISSER_PX) return;
    if (!z.glisse) { z.glisse = true; svg.setPointerCapture(ev.pointerId); svg.classList.add("glisse"); }
    this._aller(svg, { x: z.depart.x - dx * z.depart.unite, y: z.depart.y - dy * z.depart.unite, w: z.w, h: z.h }, false);
  },

  _relache(svg, ev) {
    const z = svg._zoom;
    z.pointeurs.delete(ev.pointerId);
    if (z.pointeurs.size === 0) z.depart = null;
    svg.classList.remove("glisse");
    // le drapeau « glisse » reste levé jusqu'au click qui suit le relâchement, puis retombe
    setTimeout(() => { if (!z.pointeurs.size) z.glisse = false; }, 0);
  },

  _outils(svg) {
    const parent = svg.parentElement;
    const barre = document.createElement("div");
    barre.className = "zoom-outils";
    const bouton = (txt, titre, action) => {
      const b = document.createElement("button");
      b.textContent = txt; b.title = titre; b.onclick = action;
      barre.appendChild(b);
      return b;
    };
    bouton("+", "Zoomer (molette, double-clic, touche +)", () => this.zoomer(svg, this.PAS_BOUTON, null, true));
    bouton("−", "Dézoomer (molette, touche −)", () => this.zoomer(svg, 1 / this.PAS_BOUTON, null, true));
    bouton("⤢", "Vue d'ensemble (touche 0)", () => this.ajuster(svg));
    const ind = document.createElement("span");
    ind.className = "zoom-indicateur";
    barre.appendChild(ind);
    svg._indicateur = ind;
    parent.appendChild(barre);
  },
};

// clavier : agit sur le synoptique de l'onglet visible
document.addEventListener("keydown", ev => {
  if (ev.target.closest("input, select, textarea")) return;
  const svg = document.querySelector(".onglet.actif svg.synoptique");
  if (!svg || !svg._zoom) return;
  const actions = {
    "+": () => Zoom.zoomer(svg, Zoom.PAS_BOUTON, null, true), "=": () => Zoom.zoomer(svg, Zoom.PAS_BOUTON, null, true),
    "-": () => Zoom.zoomer(svg, 1 / Zoom.PAS_BOUTON, null, true), "0": () => Zoom.ajuster(svg),
    ArrowLeft: () => Zoom.deplacer(svg, -0.2, 0), ArrowRight: () => Zoom.deplacer(svg, 0.2, 0),
    ArrowUp: () => Zoom.deplacer(svg, 0, -0.2), ArrowDown: () => Zoom.deplacer(svg, 0, 0.2),
  };
  if (actions[ev.key]) { ev.preventDefault(); actions[ev.key](); }
});
