// Vue neutronique : illustration animée de la réaction en chaîne dans un petit réseau de crayons.
// - neutrons rapides (rouges) issus des fissions, ralentis par l'eau (chocs) → thermiques (bleus) ;
// - un neutron thermique qui traverse un crayon peut faire fissionner un noyau d'U-235 (éclair,
//   2 ou 3 neutrons rapides) ou être capturé (U-238) ; les grappes et le bore absorbent ;
// - quelques neutrons sont « retardés » (jaunes) : émis plus tard par les produits de fission.
// L'échelle est illustrative : la réactivité du simulateur est amplifiée (×AMPLIFICATION) pour être
// visible à l'œil, et la population est ramenée vers un niveau qui suit la puissance du simulateur.
// Les chiffres affichés à droite sont ceux du simulateur.
"use strict";

const VueNeutrons = {
  AMPLIFICATION: 60,                 // ρ visuel = 60 × ρ réel (sinon 100 pcm serait invisible)
  NU: 2.43,                          // neutrons par fission
  BETA_VISUEL: 0.05,                 // fraction de neutrons retardés montrée (réel : 0,65 %)
  POPULATION_REF: 70,                // nombre de neutrons affichés à 100 % de puissance
  VITESSE_RAPIDE: 320, VITESSE_THERMIQUE: 120,  // px/s
  CHOCS_THERMALISATION: 4,
  COLS: 12, RANGS: 6, RAYON_CRAYON: 22,
  ouvert: false,

  ouvrir() {
    const o = document.getElementById("vue-neutrons");
    o.hidden = false;
    this.ouvert = true;
    if (!this.canvas) this._init();
    this._redimensionner();
    if (!this.neutrons.length) {
      for (let k = 0; k < 30; k++) this._emettre(Math.random() * this.W(), Math.random() * this.H(), false);
    }
    this.t_prec = performance.now();
    requestAnimationFrame(t => this._boucle(t));
  },

  fermer() {
    document.getElementById("vue-neutrons").hidden = true;
    this.ouvert = false;
  },

  _init() {
    this.canvas = document.getElementById("canvas-neutrons");
    this.ctx = this.canvas.getContext("2d");
    this.neutrons = [];
    this.eclairs = [];
    this.retardes = [];               // [délai restant, x, y]
    this.compteurs = { fissions: 0, captures: 0, grappes: 0, bore: 0, fuites: 0, produits: 0, perdus: 0 };
    this.fenetre = [];                // (produits, perdus) par seconde pour le k apparent
    this.etat = { rho_pcm: 0, puissance_pct: 100, bore_ppm: 1000, insertion: { R: 0.2, G: 0, S: 0 } };
    document.getElementById("btn-fermer-neutrons").onclick = () => this.fermer();
    document.addEventListener("keydown", ev => { if (ev.key === "Escape" && this.ouvert) this.fermer(); });
    window.addEventListener("resize", () => this.ouvert && this._redimensionner());
    const c = document.getElementById("nv-r");
    c.oninput = () => { document.getElementById("nv-r-val").textContent = `${c.value} pas →`; c.dataset.touche = "1"; };
    c.onchange = () => { envoyer({ type: "commande", cible: "GRAPPES", action: "position", valeur: c.value }); c.dataset.touche = ""; };
    document.getElementById("nv-manu").onclick = () => envoyer({ type: "commande", cible: "GRAPPES", action: "manu" });
    document.getElementById("nv-au").onclick = () => envoyer({ type: "commande", cible: "RPR", action: "declencher_au" });
  },

  W() { return this.canvas.width / this.dpr; },
  H() { return this.canvas.height / this.dpr; },

  _redimensionner() {
    const r = this.canvas.getBoundingClientRect();
    this.dpr = window.devicePixelRatio || 1;
    this.canvas.width = Math.max(300, r.width) * this.dpr;
    this.canvas.height = Math.max(200, r.height) * this.dpr;
    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    // crayons combustibles en réseau, grappes (absorbants) dans 3 colonnes d'eau
    const w = this.W(), h = this.H();
    this.pas_x = w / (this.COLS + 1);
    this.pas_y = h / (this.RANGS + 1);
    this.crayons = [];
    for (let i = 1; i <= this.COLS; i++) for (let j = 1; j <= this.RANGS; j++) this.crayons.push({ x: i * this.pas_x, y: j * this.pas_y });
    this.colonnes = [["R", 3.5], ["G", 6.5], ["S", 9.5]].map(([g, i]) => ({ g, x: i * this.pas_x, l: 18 }));
  },

  // ------------------------------------------------------------------ données du simulateur
  maj(e) {
    const m = e.mesures, g = e.composants.GRAPPES || {};
    this.etat = {
      rho_pcm: m["coeur.rho_pcm"] ?? 0, puissance_pct: m["coeur.puissance_pct"] ?? 0, bore_ppm: m["primaire.bore_ppm"] ?? 0,
      insertion: { R: 1 - (m["grappes.position_pas"] ?? 0) / 228, G: 1 - (m["grappes.g_pas"] ?? 0) / 228,
                   S: (m["grappes.arret_insere_pct"] ?? 0) / 100 },
    };
    if (!this.ouvert) return;
    const t = (id, v) => { document.getElementById(id).textContent = v; };
    t("nv-p", `${fmt(m["coeur.puissance_pct"], m["coeur.puissance_pct"] < 1 ? 4 : 1)} %`);
    t("nv-rho", `${m["coeur.rho_pcm"] > 0 ? "+" : ""}${fmt(m["coeur.rho_pcm"], 0)} pcm`);
    t("nv-k", fmt(m["coeur.k_eff"], 5));
    const T = m["coeur.periode_s"];
    t("nv-periode", Math.abs(T) > 1e6 ? "∞ (critique)" : `${fmt(T, 0)} s`);
    t("nv-fissions", notationSci(m["coeur.fissions_par_s"]));
    t("nv-bore", `${fmt(m["primaire.bore_ppm"], 0)} ppm`);
    t("nv-mode", g.chute ? "grappes chutées (AU)" : g.auto ? "R en AUTO (passer en manuel pour piloter)" : "R en manuel");
    const c = document.getElementById("nv-r");
    if (!c.dataset.touche) {
      c.value = Math.round(g.consigne_manu_pas ?? 0);
      t("nv-r-val", `${fmt(g.position_pas, 0)} pas`);
    }
    c.disabled = !!g.auto || !!g.chute;
  },

  // ------------------------------------------------------------------ physique illustrative
  _emettre(x, y, retarde) {
    const a = Math.random() * 2 * Math.PI;
    this.neutrons.push({ x, y, vx: Math.cos(a) * this.VITESSE_RAPIDE, vy: Math.sin(a) * this.VITESSE_RAPIDE,
                         rapide: true, chocs: 0, retarde, dans: -1 });
    this.compteurs.produits++;
  },

  _perdre(n, type, couleur) {
    n.mort = true;
    this.compteurs[type]++;
    this.compteurs.perdus++;
    if (couleur) this.eclairs.push({ x: n.x, y: n.y, r: 4, vie: 0.35, couleur });
  },

  _fission(x, y) {
    this.compteurs.fissions++;
    this.eclairs.push({ x, y, r: 16, vie: 0.5, couleur: "255,236,160", fission: true });
    const nb = Math.random() < this.NU - 2 ? 3 : 2;
    for (let k = 0; k < nb; k++) {
      if (Math.random() < this.BETA_VISUEL) this.retardes.push([0.8 + Math.random() * 2.5, x, y]);
      else this._emettre(x, y, false);
    }
  },

  _pas(dt) {
    const e = this.etat, w = this.W(), h = this.H();
    // probabilité de fission d'un thermique qui entre dans un crayon : réglée pour donner k_visuel,
    // puis corrigée doucement pour que la population suive la puissance du simulateur
    const k_vis = Math.max(0.5, Math.min(1.5, 1 + this.AMPLIFICATION * e.rho_pcm * 1e-5));
    const cible = Math.max(3, this.POPULATION_REF * Math.pow(Math.max(e.puissance_pct, 1e-6) / 100, 0.3));
    const correction = Math.pow(cible / Math.max(1, this.neutrons.length), 0.25);
    const p_fission = Math.min(0.95, 0.42 * k_vis * correction);
    const p_bore = 0.00003 * e.bore_ppm * dt;               // absorption par le bore, par seconde dans l'eau
    for (const n of this.neutrons) {
      n.x += n.vx * dt;
      n.y += n.vy * dt;
      if (n.x < 0 || n.x > w || n.y < 0 || n.y > h) {        // fuite… ou réflexion (réflecteur)
        if (Math.random() < 0.3) { this._perdre(n, "fuites", null); continue; }
        n.vx *= (n.x < 0 || n.x > w) ? -1 : 1;
        n.vy *= (n.y < 0 || n.y > h) ? -1 : 1;
        n.x = Math.max(0, Math.min(w, n.x));
        n.y = Math.max(0, Math.min(h, n.y));
      }
      // grappes : colonne absorbante sur la hauteur insérée (depuis le haut)
      const col = this.colonnes.find(c => Math.abs(n.x - c.x) < c.l / 2);
      if (col && n.y < e.insertion[col.g] * h) { this._perdre(n, "grappes", "197,138,249"); continue; }
      // ralentissement par l'eau (chocs aléatoires)
      if (n.rapide && Math.random() < 3.0 * dt) {
        n.chocs++;
        const a = Math.random() * 2 * Math.PI;
        const v = n.chocs >= this.CHOCS_THERMALISATION ? this.VITESSE_THERMIQUE : Math.hypot(n.vx, n.vy) * 0.7;
        n.vx = Math.cos(a) * v; n.vy = Math.sin(a) * v;
        if (n.chocs >= this.CHOCS_THERMALISATION) n.rapide = false;
      }
      if (!n.rapide && Math.random() < p_bore) { this._perdre(n, "bore", "120,200,255"); continue; }
      // traversée d'un crayon
      const i = this.crayons.findIndex(c => (n.x - c.x) ** 2 + (n.y - c.y) ** 2 < this.RAYON_CRAYON ** 2);
      if (i >= 0 && i !== n.dans) {
        n.dans = i;
        if (!n.rapide) {
          const u = Math.random();
          if (u < p_fission) { n.mort = true; this.compteurs.perdus++; this._fission(n.x, n.y); }
          else if (u < p_fission + 0.25) this._perdre(n, "captures", "150,150,150");
        }
      } else if (i < 0) n.dans = -1;
    }
    this.neutrons = this.neutrons.filter(n => !n.mort);
    // neutrons retardés
    this.retardes.forEach(r => { r[0] -= dt; });
    this.retardes.filter(r => r[0] <= 0).forEach(([, x, y]) => {
      this._emettre(x, y, true);
      this.neutrons[this.neutrons.length - 1].rapide = true;
      this.neutrons[this.neutrons.length - 1].retarde = true;
    });
    this.retardes = this.retardes.filter(r => r[0] > 0);
    // source de démarrage : quelques neutrons si la population s'éteint (fissions spontanées, source)
    if (this.neutrons.length < 2 && Math.random() < dt * 2) this._emettre(Math.random() * w, Math.random() * h, false);
    if (this.neutrons.length > 400) this.neutrons.splice(0, this.neutrons.length - 400);
    this.eclairs.forEach(f => { f.vie -= dt; });
    this.eclairs = this.eclairs.filter(f => f.vie > 0);
  },

  _dessiner() {
    const ctx = this.ctx, w = this.W(), h = this.H(), e = this.etat;
    ctx.fillStyle = "#0b1a2a";                         // eau (modérateur)
    ctx.fillRect(0, 0, w, h);
    for (const c of this.crayons) {                    // crayons d'oxyde d'uranium
      ctx.beginPath(); ctx.arc(c.x, c.y, this.RAYON_CRAYON, 0, 2 * Math.PI);
      ctx.fillStyle = "#3a2a1a"; ctx.fill();
      ctx.strokeStyle = "#8a6a3a"; ctx.lineWidth = 2; ctx.stroke();
      for (let k = 0; k < 4; k++) {                    // noyaux d'U-235 (points jaunes)
        ctx.beginPath();
        ctx.arc(c.x + 10 * Math.cos(k * 1.57 + 0.6), c.y + 10 * Math.sin(k * 1.57 + 0.6), 2.5, 0, 2 * Math.PI);
        ctx.fillStyle = "#e8c860"; ctx.fill();
      }
    }
    const couleurs = { R: "#4ea1ff", G: "#3fbf6a", S: "#c58af9" };
    for (const c of this.colonnes) {                   // grappes : insertion depuis le haut
      const l = e.insertion[c.g] * h;
      ctx.fillStyle = "#2b2f36"; ctx.fillRect(c.x - c.l / 2, 0, c.l, l);
      ctx.strokeStyle = couleurs[c.g]; ctx.lineWidth = 2; ctx.strokeRect(c.x - c.l / 2, -2, c.l, l + 2);
      ctx.fillStyle = couleurs[c.g]; ctx.font = "12px system-ui"; ctx.fillText(c.g, c.x - 4, Math.max(14, l + 14));
    }
    for (const f of this.eclairs) {
      const a = Math.max(0, f.vie / (f.fission ? 0.5 : 0.35));
      ctx.beginPath(); ctx.arc(f.x, f.y, f.r * (f.fission ? 1.6 - a : 1), 0, 2 * Math.PI);
      ctx.fillStyle = `rgba(${f.couleur},${(0.8 * a).toFixed(2)})`; ctx.fill();
    }
    for (const n of this.neutrons) {
      ctx.beginPath(); ctx.arc(n.x, n.y, n.rapide ? 3 : 2.5, 0, 2 * Math.PI);
      ctx.fillStyle = n.retarde ? "#ffd84a" : n.rapide ? "#ff6a4d" : "#7fc4ff";
      ctx.fill();
    }
  },

  _boucle(t) {
    if (!this.ouvert) return;
    const dt = Math.min(0.05, (t - this.t_prec) / 1000);
    this.t_prec = t;
    this._pas(dt);
    this._dessiner();
    // compteurs de l'animation + k apparent sur ~3 s
    this.fenetre.push([this.compteurs.produits, this.compteurs.perdus, t]);
    while (this.fenetre.length > 2 && t - this.fenetre[0][2] > 3000) this.fenetre.shift();
    const [p0, l0] = this.fenetre[0];
    const k_app = (this.compteurs.produits - p0) / Math.max(1, this.compteurs.perdus - l0);
    const c = this.compteurs;
    document.getElementById("nv-anim").innerHTML =
      `neutrons à l'écran : <b>${this.neutrons.length}</b> · fissions : <b>${c.fissions}</b> · captures U-238 : ${c.captures}`
      + ` · absorbés par les grappes : ${c.grappes} · par le bore : ${c.bore} · fuites : ${c.fuites}`
      + ` · k apparent (illustration) : <b>${k_app.toFixed(2)}</b>`;
    requestAnimationFrame(tt => this._boucle(tt));
  },
};
