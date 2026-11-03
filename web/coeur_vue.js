// Vue « Cœur » : carte des 193 assemblages (vue de dessus), vue axiale des groupes de grappes,
// bilan de réactivité, et panneau de pilotage (grappes R / G / S, bore, AU, vue neutronique).
// La nappe de puissance est ILLUSTRATIVE (cosinus radial creusé près des grappes insérées),
// les chiffres (puissance, ρ, k, période, bore) sont ceux du simulateur.
"use strict";

const VueCoeur = {
  PAS_MAX: 228,
  C: { x: 330, y: 440 }, CELL: 36,
  R_EXT: 8.6,                         // rayon d'extinction du cosinus radial (en pas d'assemblage)
  EFFET_GRAPPE: 0.35,                 // creusement local de la nappe par une grappe insérée
  PORTEE_GRAPPE: 1.6,                 // portée (pas d'assemblage²) de ce creusement
  ECHELLE_RHO_PCM: 5000,
  GROUPES: [["R", "régulation", "#4ea1ff"], ["G", "compensation", "#3fbf6a"], ["S", "arrêt", "#c58af9"]],

  construire(svg) {
    Sym.defs(svg);
    const { C, CELL } = this;
    Sym.texte(svg, C.x, 120, "CŒUR — vue de dessus (193 assemblages)", "lib-fort");
    svgEl("circle", { cx: C.x, cy: C.y, r: 8.4 * CELL, class: "enveloppe-coeur" }, svg);
    this.rects = CoeurGeo.assemblages.map(a => {
      const r = svgEl("rect", { x: C.x + a.dx * CELL - CELL / 2 + 1, y: C.y + a.dy * CELL - CELL / 2 + 1,
                                width: CELL - 2, height: CELL - 2, rx: 3, class: "assemblage" }, svg);
      svgEl("title", {}, r);
      return r;
    });
    this.grappes = CoeurGeo.grappes.map(g => svgEl("circle", { cx: C.x + g.dx * CELL, cy: C.y + g.dy * CELL, r: 10,
      class: `grappe-pt groupe-${g.groupe}`, "data-groupe": g.groupe }, svg));
    // repères de colonnes / rangées (A..R sans I, O, Q comme sur les cœurs réels : simplifié A..P)
    const lettres = "ABCDEFGHJKLMNPR";
    for (let i = 0; i < CoeurGeo.N; i++) {
      Sym.detail(Sym.texte(svg, C.x + (i - CoeurGeo.MILIEU) * CELL, C.y - 8.2 * CELL, lettres[i], "atm"));
      Sym.detail(Sym.texte(svg, C.x - 8.2 * CELL, C.y + (i - CoeurGeo.MILIEU) * CELL + 4, String(i + 1), "atm"));
    }
    this.GROUPES.forEach(([g, lib], k) => {
      const x = 90 + k * 170;
      svgEl("circle", { cx: x, cy: 770, r: 8, class: `grappe-pt groupe-${g}` }, svg);
      Sym.texte(svg, x + 14, 774, `${g} : ${lib}`, "lib", "start");
    });
    Sym.texte(svg, 70, 800, "Plein = grappe insérée · couleur des assemblages = puissance locale", "atm", "start");
    this.fq = Sym.texte(svg, C.x, 830, "", "val");

    // ---------------------------------------------------------------- vue axiale
    const xa = 700, ya = 200, ha = 440;
    this.axe = { xa, ya, ha };
    Sym.texte(svg, xa + 100, 96, "VUE AXIALE", "lib-fort");
    Sym.texte(svg, xa + 100, 112, "hauteur des grappes", "atm");
    svgEl("rect", { x: xa, y: ya, width: 200, height: ha, rx: 6, class: "boite-coeur" }, svg);
    for (let k = 0; k < 10; k++) svgEl("line", { x1: xa + 10 + k * 20, y1: ya + 6, x2: xa + 10 + k * 20, y2: ya + ha - 6,
                                                 class: "crayon" }, svg);
    this.barres = {};
    this.GROUPES.forEach(([g, , couleur], k) => {
      const x = xa + 30 + k * 60;
      this.barres[g] = svgEl("rect", { x: x - 9, y: ya - 30, width: 18, height: 0, fill: couleur, rx: 2, class: "barre-grappe" }, svg);
      svgEl("line", { x1: x, y1: ya - 60, x2: x, y2: ya - 30, stroke: couleur, "stroke-width": 3 }, svg);
      Sym.texte(svg, x, ya - 66, g, "lib-fort");
      this.barres[g + "_txt"] = Sym.texte(svg, x, ya + ha + 22, "", "val");
    });
    Sym.texte(svg, xa - 8, ya + 10, "haut", "atm", "end");
    Sym.texte(svg, xa - 8, ya + ha, "bas", "atm", "end");
    this.profil = svgEl("polyline", { class: "profil-axial", fill: "none" }, svg);
    Sym.texte(svg, xa + 265, ya - 10, "puissance", "atm");
    this.ao = Sym.texte(svg, xa + 265, ya + ha + 22, "", "val");

    // ---------------------------------------------------------------- bilan de réactivité
    const yb = 720, x0 = 900;
    Sym.texte(svg, x0, yb - 30, "BILAN DE RÉACTIVITÉ (pcm, 0 au point nominal)", "lib-fort");
    svgEl("line", { x1: x0, y1: yb - 12, x2: x0, y2: yb + 130, stroke: "#556372", "stroke-width": 1 }, svg);
    this.bilan = [["coeur.rho_grappes_pcm", "grappes"], ["coeur.rho_moderateur_pcm", "modérateur"],
                  ["coeur.rho_doppler_pcm", "Doppler"], ["coeur.rho_bore_pcm", "bore"]].map(([m, lib], k) => {
      const y = yb + k * 28;
      Sym.texte(svg, x0 - 210, y + 4, lib, "lib", "end");
      return { m, barre: svgEl("rect", { x: x0, y: y - 8, width: 0, height: 14, rx: 2 }, svg),
               txt: Sym.texte(svg, x0 + 200, y + 4, "", "val", "end") };
    });
  },

  // nappe radiale illustrative, creusée près des grappes insérées
  nappe(insertion) {
    const p = CoeurGeo.assemblages.map(a => Math.max(0.05, Math.cos(Math.PI / 2 * Math.hypot(a.dx, a.dy) / this.R_EXT)));
    CoeurGeo.grappes.forEach(g => {
      const f = insertion[g.groupe];
      if (f <= 0) return;
      CoeurGeo.assemblages.forEach((a, i) => {
        const d2 = (a.dx - g.dx) ** 2 + (a.dy - g.dy) ** 2;
        p[i] *= 1 - this.EFFET_GRAPPE * f * Math.exp(-d2 / this.PORTEE_GRAPPE);
      });
    });
    const moy = p.reduce((s, x) => s + x, 0) / p.length;
    return p.map(x => x / moy);
  },

  couleur(x) {                         // 0 → sombre, 1 → orange, 1,5 → jaune pâle
    const t = Math.max(0, Math.min(1.5, x)) / 1.5;
    const l = 12 + 62 * t, s = 85, h = 20 + 30 * t;
    return `hsl(${h.toFixed(0)},${s}%,${l.toFixed(0)}%)`;
  },

  maj(m) {
    if (!this.rects) return;
    const ins = { R: 1 - (m["grappes.position_pas"] ?? 0) / this.PAS_MAX, G: 1 - (m["grappes.g_pas"] ?? 0) / this.PAS_MAX,
                  S: (m["grappes.arret_insere_pct"] ?? 0) / 100 };
    const p = this.nappe(ins);
    const niveau = (m["coeur.p_thermique_mw"] ?? 0) / 3411;
    const lettres = "ABCDEFGHJKLMNPR";
    this.rects.forEach((r, i) => {
      r.setAttribute("fill", this.couleur(p[i] * Math.min(1.2, niveau * 1.2 + 0.02)));
      const a = CoeurGeo.assemblages[i];
      r.firstChild.textContent = `Assemblage ${lettres[a.i]}${a.j + 1} — puissance relative ${p[i].toFixed(2)}`;
    });
    this.grappes.forEach(c => { c.style.fillOpacity = (0.15 + 0.85 * ins[c.dataset.groupe]).toFixed(2); });
    this.fq.textContent = `facteur de point chaud radial ≈ ${Math.max(...p).toFixed(2)} (illustratif)`;
    // vue axiale
    const { xa, ya, ha } = this.axe;
    ["R", "G", "S"].forEach(g => {
      this.barres[g].setAttribute("height", (30 + ins[g] * ha).toFixed(1));
      const txt = g === "S" ? `${(ins.S * 100).toFixed(0)} % insérés`
                            : `${(g === "R" ? m["grappes.position_pas"] : m["grappes.g_pas"])?.toFixed(0)} pas`;
      this.barres[g + "_txt"].textContent = txt;
    });
    // profil axial : sinus creusé dans la partie haute où les grappes R / G sont insérées
    const profondeur = Math.max(ins.R, ins.G * 0.8, ins.S);
    const pts = [];
    let haut = 0, bas = 0;
    for (let k = 0; k <= 40; k++) {
      const z = k / 40;                                   // 0 = bas, 1 = haut
      let v = Math.sin(Math.PI * (0.04 + 0.92 * z));
      if (z > 1 - profondeur) v *= 0.35;
      (z > 0.5 ? (haut += v) : (bas += v));
      pts.push([z, v]);
    }
    const vmax = Math.max(...pts.map(q => q[1]));
    this.profil.setAttribute("points", pts.map(([z, v]) =>
      `${(xa + 220 + 90 * v / vmax).toFixed(1)},${(ya + ha * (1 - z)).toFixed(1)}`).join(" "));
    this.ao.textContent = `déséquilibre axial ${(100 * (haut - bas) / (haut + bas)).toFixed(0)} %`;
    // bilan de réactivité
    const x0 = 900, l = 200 / this.ECHELLE_RHO_PCM;
    this.bilan.forEach(b => {
      const v = m[b.m] ?? 0;
      const w = Math.min(200, Math.abs(v) * l);
      b.barre.setAttribute("x", v < 0 ? x0 - w : x0);
      b.barre.setAttribute("width", w);
      b.barre.setAttribute("fill", v < 0 ? "#4ea1ff" : "#f0a030");
      b.txt.textContent = `${v > 0 ? "+" : ""}${fmt(v, 0)}`;
    });
  },
};

// ---------------------------------------------------------------------------- panneau de pilotage
const PilotageCoeur = {
  init() {
    const zone = document.getElementById("pilotage-coeur");
    zone.innerHTML = `
      <h2>Pilotage des grappes</h2>
      <div class="ligne-btn"><button data-cmd="GRAPPES:auto">AUTO</button><button data-cmd="GRAPPES:manu">MANU</button>
        <span id="pc-mode" class="discret"></span></div>
      <label class="curseur">Groupe R (régulation) <b id="pc-r-val">—</b>
        <input type="range" id="pc-r" min="0" max="228" step="1"></label>
      <label class="curseur">Groupe G (compensation) <b id="pc-g-val">—</b>
        <input type="range" id="pc-g" min="0" max="228" step="1"></label>
      <div class="ligne-btn">Groupes S (arrêt) : <b id="pc-s">—</b>
        <button data-cmd="GRAPPES:extraire_arret">Extraire</button></div>
      <button class="danger" data-cmd="RPR:declencher_au">Arrêt automatique (AU)</button>
      <button data-cmd="RPR:rearmer_au">Réarmer l'AU</button>
      <h2>Bore</h2>
      <div class="ligne-btn"><b id="pc-bore">—</b>
        <button data-cmd="REA:borication:2">Borer 2 m³</button><button data-cmd="REA:dilution:2">Diluer 2 m³</button></div>
      <p class="discret petit" id="pc-bore-requis"></p>
      <h2>Réaction en chaîne</h2>
      <table class="lecture">
        <tr><td>Puissance</td><td id="pc-p"></td></tr>
        <tr><td>Réactivité ρ</td><td id="pc-rho"></td></tr>
        <tr><td>k effectif</td><td id="pc-k"></td></tr>
        <tr><td>Période</td><td id="pc-periode"></td></tr>
        <tr><td>Fissions / s</td><td id="pc-fissions"></td></tr>
      </table>
      <button class="gros-btn" id="btn-neutrons">⚛ Voir les neutrons</button>
      <p id="pc-message" class="petit"></p>`;
    zone.querySelectorAll("[data-cmd]").forEach(b => b.onclick = () => {
      const [cible, action, valeur] = b.dataset.cmd.split(":");
      envoyer({ type: "commande", cible, action, valeur: valeur ?? null });
    });
    const curseur = (id, action) => {
      const c = document.getElementById(id);
      c.oninput = () => { document.getElementById(`${id}-val`).textContent = `${c.value} pas →`; c.dataset.touche = "1"; };
      c.onchange = () => { envoyer({ type: "commande", cible: "GRAPPES", action, valeur: c.value }); c.dataset.touche = ""; };
    };
    curseur("pc-r", "position");
    curseur("pc-g", "position_g");
    document.getElementById("btn-neutrons").onclick = () => VueNeutrons.ouvrir();
  },

  maj(e) {
    const m = e.mesures, g = e.composants.GRAPPES;
    if (!g || !document.getElementById("pc-r")) return;
    document.getElementById("pc-mode").textContent = g.chute ? "grappes chutées (AU)" : g.auto ? "R en automatique" : "manuel";
    for (const [id, val, cons] of [["pc-r", g.position_pas, g.consigne_manu_pas], ["pc-g", g.position_g_pas, g.consigne_g_pas]]) {
      const c = document.getElementById(id);
      if (!c.dataset.touche) c.value = Math.round(cons);
      if (!c.dataset.touche) document.getElementById(`${id}-val`).textContent = `${fmt(val, 0)} pas`;
      c.disabled = id === "pc-r" && g.auto;
    }
    document.getElementById("pc-s").textContent = `${fmt(g.arret_insere_pct, 0)} % insérés`;
    document.getElementById("pc-bore").textContent = `${fmt(m["primaire.bore_ppm"], 0)} ppm`;
    document.getElementById("pc-bore-requis").textContent =
      `arrêt à froid : ${fmt(m["coeur.bore_arret_froid_ppm"], 0)} ppm requis · REA en mode ${e.composants.REA?.mode ?? "—"}`;
    document.getElementById("pc-p").textContent = `${fmt(m["coeur.puissance_pct"], m["coeur.puissance_pct"] < 1 ? 4 : 1)} %`;
    const rho = m["coeur.rho_pcm"];
    document.getElementById("pc-rho").textContent = `${rho > 0 ? "+" : ""}${fmt(rho, 0)} pcm`;
    document.getElementById("pc-rho").className = rho > 5 ? "chaud" : rho < -5 ? "froid" : "";
    document.getElementById("pc-k").textContent = fmt(m["coeur.k_eff"], 5);
    const T = m["coeur.periode_s"];
    document.getElementById("pc-periode").textContent = Math.abs(T) > 1e6 ? "∞ (critique)"
      : `${T > 0 ? "+" : ""}${fmt(T, 0)} s ${T > 0 ? "(divergence)" : "(décroissance)"}`;
    document.getElementById("pc-fissions").textContent = notationSci(m["coeur.fissions_par_s"]);
  },

  reponse(msg) {
    const d = document.getElementById("pc-message");
    if (!d || !["GRAPPES", "REA", "RPR"].includes(msg.cible)) return;
    d.className = `petit ${msg.ok ? "ok" : "ko"}`;
    d.textContent = msg.ok ? `✓ ${LIBELLES_ACTIONS[msg.action] || msg.action}` : `✗ ${msg.raisons.join(" ; ")}`;
  },
};

function notationSci(v) {
  if (typeof v !== "number" || !isFinite(v) || v <= 0) return "0";
  const e = Math.floor(Math.log10(v));
  const exposants = "⁰¹²³⁴⁵⁶⁷⁸⁹";
  const sup = String(e).split("").map(ch => ch === "-" ? "⁻" : exposants[Number(ch)]).join("");
  return `${(v / 10 ** e).toFixed(2)} × 10${sup}`;
}
