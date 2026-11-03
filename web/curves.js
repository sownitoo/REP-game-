// Courbes : 1 à 6 variables, une mini-courbe par variable (axe propre), fenêtre glissante.
"use strict";

const Courbes = {
  MAX: 6,
  couleurs: ["#4ea1ff", "#3fbf6a", "#f0a030", "#e5484d", "#c58af9", "#2fc5c0"],
  choisies: ["coeur.puissance_pct", "primaire.tmoy_c", "pzr.p_bar", "pzr.niveau_pct", "GV1.niveau_pct", "turbine.p_elec_mw"],
  donnees: null,

  init(variables) {
    this.variables = variables;
    document.getElementById("filtre-variables").addEventListener("input", () => this.liste());
    document.getElementById("fenetre-courbes").addEventListener("change", () => this.dessiner());
    this.liste();
  },

  liste() {
    const filtre = document.getElementById("filtre-variables").value.toLowerCase();
    const div = document.getElementById("liste-variables");
    div.innerHTML = "";
    for (const v of this.variables.filter(x => x.toLowerCase().includes(filtre))) {
      const lab = document.createElement("label");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = this.choisies.includes(v);
      cb.addEventListener("change", () => {
        if (cb.checked) {
          if (this.choisies.length >= this.MAX) { cb.checked = false; return; }
          this.choisies.push(v);
        } else {
          this.choisies = this.choisies.filter(x => x !== v);
        }
        this.demander();
      });
      lab.append(cb, " " + v);
      div.appendChild(lab);
    }
  },

  // l'historique est demandé au simulateur (même protocole en mode serveur et navigateur)
  demander() {
    if (!this.choisies.length) { this.donnees = null; this.dessiner(); return; }
    envoyer({ type: "historique", vars: this.choisies });
  },

  recevoir(series) {
    this.donnees = series;
    this.dessiner();
  },

  dessiner() {
    const zone = document.getElementById("graphes");
    zone.innerHTML = "";
    if (!this.donnees || !this.donnees.t_s.length) return;
    const fenetre = Number(document.getElementById("fenetre-courbes").value);
    const t = this.donnees.t_s;
    const tFin = t[t.length - 1];
    const tDebut = Math.max(t[0], tFin - fenetre);
    const debut = t.findIndex(x => x >= tDebut);
    this.choisies.forEach((nom, k) => {
      const serie = this.donnees[nom];
      if (!serie) return;
      const canvas = document.createElement("canvas");
      zone.appendChild(canvas);
      this._trace(canvas, t.slice(debut), serie.slice(debut), nom, this.couleurs[k % this.couleurs.length], tDebut, Math.max(tFin, tDebut + 1));
    });
  },

  _trace(canvas, t, y, nom, couleur, t0, t1) {
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth, h = canvas.clientHeight;
    canvas.width = w * dpr; canvas.height = h * dpr;
    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    const g = 52, d = 10, haut = 18, bas = 18;
    let ymin = Math.min(...y), ymax = Math.max(...y);
    if (ymax - ymin < 1e-6) { ymin -= 1; ymax += 1; }
    const marge = (ymax - ymin) * 0.08; ymin -= marge; ymax += marge;
    const X = v => g + (v - t0) / (t1 - t0) * (w - g - d);
    const Y = v => haut + (1 - (v - ymin) / (ymax - ymin)) * (h - haut - bas);
    ctx.strokeStyle = "#33414f"; ctx.fillStyle = "#8392a3"; ctx.font = "11px system-ui";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 3; i++) {
      const v = ymin + (ymax - ymin) * i / 3;
      ctx.beginPath(); ctx.moveTo(g, Y(v)); ctx.lineTo(w - d, Y(v)); ctx.stroke();
      ctx.fillText(v.toPrecision(4), 4, Y(v) + 4);
    }
    ctx.fillText(formatTemps(t0), g, h - 4);
    ctx.fillText(formatTemps(t1), w - d - 52, h - 4);
    ctx.fillStyle = couleur; ctx.font = "bold 12px system-ui";
    ctx.fillText(`${nom} = ${y[y.length - 1].toPrecision(5)}`, g + 4, 13);
    ctx.strokeStyle = couleur; ctx.lineWidth = 1.6;
    ctx.beginPath();
    y.forEach((v, i) => (i ? ctx.lineTo(X(t[i]), Y(v)) : ctx.moveTo(X(t[i]), Y(v))));
    ctx.stroke();
  },
};
