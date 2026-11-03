// Mode tuto : écran d'accueil, carte guidée (étapes lecture / action / observation), explication de chaque
// automatisme quand la simulation s'arrête dessus, surbrillance des équipements, mode libre « commenté ».
// Les tutos et le catalogue d'explications viennent du simulateur (message init) ; les points d'arrêt sont
// gérés côté simulateur (pause exacte, même en accéléré).
"use strict";

const Tuto = {
  tutos: [], explications: {}, meta: {},
  actif: null, k: 0,
  phase: "",                // lecture | action | action-faite | pret | observe | arret | fin-observation
  vus: [], cleArret: "", debutObs: 0, depuisJournal: 0, commente: false, dernierEtat: null,

  init(tutos, explications, meta) {
    this.tutos = tutos; this.explications = explications; this.meta = meta;
    try { this.commente = localStorage.getItem("rep_commente") === "1"; } catch (e) { this.commente = false; }
    this.construireAccueil();
    document.getElementById("btn-tutos").onclick = () => this.ouvrirAccueil();
    document.getElementById("tuto-quitter").onclick = () => this.quitter();
    document.getElementById("tuto-reduire").onclick = () => document.getElementById("tuto").classList.toggle("reduit");
    document.getElementById("btn-commente").onclick = () => this.basculerCommente();
    this.majBoutonCommente();
    if (this.commente) envoyer({ type: "commente", valeur: true });
    let vu = false;
    try { vu = sessionStorage.getItem("rep_accueil_vu") === "1"; } catch (e) { vu = false; }
    if (!vu) this.ouvrirAccueil();
  },

  // ------------------------------------------------------------------ accueil
  construireAccueil() {
    const liste = document.getElementById("accueil-tutos");
    liste.innerHTML = "";
    this.tutos.forEach(t => {
      const carte = el("div", { class: "carte-tuto" });
      carte.innerHTML = `<div class="carte-tuto-tete"><b>${t.titre}</b><span class="discret petit">${t.niveau} · ~${t.duree_min} min</span></div>
        <p class="petit">${t.resume}</p>`;
      const b = el("button", { class: "gros-btn" }, "▶ Commencer");
      b.onclick = () => this.lancer(t.id);
      carte.appendChild(b);
      liste.appendChild(carte);
    });
    document.getElementById("accueil-reacteur").innerHTML =
      `<b>${this.meta.reacteur || ""}</b><br><span class="petit">${this.meta.reacteur_detail || ""}</span>`;
    document.getElementById("btn-mode-libre").onclick = () => this.fermerAccueil();
    const c = document.getElementById("accueil-commente");
    c.checked = this.commente;
    c.onchange = () => { if (c.checked !== this.commente) this.basculerCommente(); };
  },
  ouvrirAccueil() {
    document.getElementById("menu-contenu").hidden = true;
    document.getElementById("accueil-commente").checked = this.commente;
    document.getElementById("accueil").hidden = false;
  },
  fermerAccueil() {
    document.getElementById("accueil").hidden = true;
    try { sessionStorage.setItem("rep_accueil_vu", "1"); } catch (e) { /* stockage indisponible */ }
  },

  // ------------------------------------------------------------------ mode libre commenté
  basculerCommente() {
    this.commente = !this.commente;
    try { localStorage.setItem("rep_commente", this.commente ? "1" : "0"); } catch (e) { /* stockage indisponible */ }
    if (!this.actif) envoyer({ type: "commente", valeur: this.commente });
    this.majBoutonCommente();
  },
  majBoutonCommente() {
    const b = document.getElementById("btn-commente");
    b.classList.toggle("actif", this.commente);
    b.textContent = this.commente ? "💬 Automatismes expliqués : oui" : "💬 Automatismes expliqués : non";
  },

  // ------------------------------------------------------------------ déroulé d'un tuto
  lancer(id) {
    this.fermerAccueil();
    deselectionner();
    envoyer({ type: "tuto", id });
    this.actif = this.tutos.find(t => t.id === id);
    this.k = 0;
    this.afficherCarte(true);
  },
  afficherCarte(oui) {
    const carte = document.getElementById("tuto");
    carte.hidden = !oui;
    document.body.classList.toggle("mode-tuto", oui);
    if (oui) {
      carte.classList.remove("reduit");
      document.querySelector("main").classList.remove("sans-panneau");
    }
  },
  surCharge(msg) {                     // le simulateur a chargé l'état de départ (en pause)
    if (!this.actif || msg.id !== this.actif.id) return;
    this.entrer(0);
  },
  quitter() {
    this.actif = null;
    this.phase = "";
    this.afficherCarte(false);
    this.surligner([]);
    envoyer({ type: "commente", valeur: this.commente });
  },
  etape() { return this.actif ? this.actif.etapes[this.k] : null; },

  entrer(k) {
    this.k = k;
    const e = this.etape();
    this.vus = [];
    this.cleArret = "";
    this.phase = e.genre === "action" ? "action" : e.genre === "observation" ? "pret" : "lecture";
    if (e.onglet) ouvrirOnglet(e.onglet);
    this.surligner(e.voir.length ? e.voir : e.action ? [e.action.cible] : []);
    this.rendre();
  },
  suivant() {
    if (this.k + 1 < this.actif.etapes.length) this.entrer(this.k + 1);
    else this.terminer();
  },
  terminer() {
    const corps = document.getElementById("tuto-corps");
    corps.innerHTML = `<h3>✓ Tuto terminé</h3><p>La simulation reste là : tu peux continuer à explorer librement,
      ou choisir un autre tuto.</p>`;
    document.getElementById("tuto-mesures").innerHTML = "";
    const b = document.getElementById("tuto-boutons");
    b.innerHTML = "";
    b.append(this.bouton("🎓 Autres tutos", () => { this.quitter(); this.ouvrirAccueil(); }),
             this.bouton("Mode libre", () => this.quitter()));
    this.surligner([]);
    this.actif = null;
  },
  lancerObservation() {
    const o = this.etape().observer;
    this.phase = "observe";
    this.debutObs = this.dernierEtat ? this.dernierEtat.t_s : 0;
    this.depuisJournal = this.dernierEtat ? this.dernierEtat.t_s : 0;
    envoyer({ type: "observer", points: o.attendus, duree_s: o.duree_s, acceleration: o.acceleration });
    this.rendre();
  },
  faireAction() {
    const a = this.etape().action;
    envoyer({ type: "commande", cible: a.cible, action: a.action, valeur: a.valeur });
  },
  surReponse(msg) {                    // une commande a été exécutée (par le joueur ou « faire pour moi »)
    const e = this.etape();
    if (!e || this.phase !== "action" || !msg.ok) return;
    if (msg.cible === e.action.cible && msg.action === e.action.action) {
      this.phase = "action-faite";
      this.rendre();
      setTimeout(() => { if (this.etape() === e && this.phase === "action-faite") this.suivant(); }, 1200);
    }
  },

  // ------------------------------------------------------------------ mise à jour à chaque état reçu
  maj(etatSim) {
    this.dernierEtat = etatSim;
    const a = etatSim.arret;
    const cle = a ? `${a.id}@${a.t_s}` : "";
    if (cle !== this.cleArret) {
      this.cleArret = cle;
      if (a) this.surArret(a, etatSim);
      else if (this.phase === "arret") { this.phase = "observe"; this.rendre(); }
      else if (!this.actif) this.afficherCarte(false);
    }
    this.majMesures(etatSim);
    if (this.phase === "observe") this.majObservation(etatSim);
  },
  surArret(a, etatSim) {
    if (a.id === "fin") {
      if (this.actif && this.etape().genre === "observation") {
        this.phase = "fin-observation";
        this.surligner(this.etape().voir);
        this.rendre();
      }
      return;
    }
    if (!this.actif) this.afficherCarte(true);      // mode libre commenté
    if (!this.vus.includes(a.id)) this.vus.push(a.id);
    this.phase = "arret";
    this.arret = a;
    const x = this.explications[a.id];
    if (x) {
      if (x.onglet) ouvrirOnglet(x.onglet);
      this.surligner(x.voir);
    }
    this.rendre(etatSim);
  },

  // ------------------------------------------------------------------ affichage
  bouton(texte, action, classe = "") {
    const b = el("button", { class: classe }, texte);
    b.onclick = action;
    return b;
  },
  rendre() {
    const carte = document.getElementById("tuto");
    const corps = document.getElementById("tuto-corps");
    const boutons = document.getElementById("tuto-boutons");
    boutons.innerHTML = "";
    const t = this.actif, e = this.etape();
    document.getElementById("tuto-titre").textContent = t ? t.titre : "Automatisme expliqué";
    document.getElementById("tuto-progression").textContent = t ? `${this.k + 1} / ${t.etapes.length}` : "";
    document.getElementById("tuto-avance").style.width = t ? `${100 * (this.k + 1) / t.etapes.length}%` : "0";
    carte.classList.toggle("libre", !t);

    if (this.phase === "arret") {
      const a = this.arret, x = this.explications[a.id] || { titre: a.texte, pourquoi: "", effet: "" };
      corps.innerHTML = `<div class="tuto-arret"><div class="tuto-pause">⏸ Simulation en pause — t = ${formatTemps(a.t_s)}</div>
        <h3>${x.titre}</h3>
        <p class="tuto-declencheur">Journal : « ${a.texte} »</p>
        <h4>Pourquoi ?</h4><p>${x.pourquoi}</p>
        <h4>Ce que ça fait</h4><p>${x.effet}</p></div>`
        + (t && e.genre === "observation" ? this.htmlListe() : "");
      const n = this.dernierEtat ? this.dernierEtat.arrets_en_attente : 0;
      boutons.append(this.bouton(n > 0 ? `Automatisme suivant (${n}) ▶` : "Continuer ▶", () => envoyer({ type: "continuer" }), "gros-btn"));
      if (!t) boutons.append(this.bouton("Ne plus expliquer", () => { this.basculerCommente(); envoyer({ type: "continuer" }); }));
      return;
    }
    if (!t) return;
    let html = `<h3>${e.titre}</h3><div class="tuto-texte">${e.texte}</div>`;
    if (e.genre === "action") {
      html += this.phase === "action-faite" ? `<p class="tuto-ok">✓ Fait !</p>`
        : `<p class="tuto-attente">En attente de ton action sur <b>${e.action.cible}</b>…</p>`;
      boutons.append(this.bouton(`🤖 ${e.action.libelle} pour moi`, () => this.faireAction(), "gros-btn"));
    } else if (e.genre === "observation") {
      html += this.htmlListe();
      if (this.phase === "pret") {
        boutons.append(this.bouton(`▶ Lancer la simulation (×${e.observer.acceleration})`, () => this.lancerObservation(), "gros-btn"));
      } else if (this.phase === "observe") {
        html += `<p class="tuto-attente" id="tuto-chrono">⏵ Simulation en cours…</p><ul class="tuto-journal" id="tuto-journal"></ul>`;
      } else if (this.phase === "fin-observation") {
        html += `<p class="tuto-ok">Observation terminée.</p>`;
        boutons.append(this.bouton("Suivant ▶", () => this.suivant(), "gros-btn"));
      }
    } else {
      if (this.k > 0 && this.actif.etapes[this.k - 1].genre === "lecture") {
        boutons.append(this.bouton("◀ Précédent", () => this.entrer(this.k - 1)));
      }
      boutons.append(this.bouton(this.k + 1 < t.etapes.length ? "Suivant ▶" : "Terminer ✓", () => this.suivant(), "gros-btn"));
    }
    corps.innerHTML = html;
  },
  htmlListe() {
    const o = this.etape().observer;
    if (!o.attendus.length) return "";
    const lignes = o.attendus.map(id => {
      const x = this.explications[id];
      const vu = this.vus.includes(id);
      return `<li class="${vu ? "vu" : ""}">${vu ? "✓" : "○"} ${x ? x.titre : id}</li>`;
    }).join("");
    return `<h4>À observer (${this.vus.filter(v => o.attendus.includes(v)).length} / ${o.attendus.length})</h4><ul class="tuto-liste">${lignes}</ul>`;
  },
  majObservation(etatSim) {
    const chrono = document.getElementById("tuto-chrono");
    if (chrono) {
      const o = this.etape().observer;
      chrono.textContent = `⏵ Simulation en cours — ${formatTemps(etatSim.t_s - this.debutObs)} / ${formatTemps(o.duree_s)}`
        + (etatSim.pause ? " (en pause)" : "");
    }
    const ul = document.getElementById("tuto-journal");
    if (ul) {
      const evts = etatSim.journal.filter(j => j.t_s >= this.depuisJournal && j.categorie === "automatisme").slice(-4);
      ul.innerHTML = evts.map(j => `<li><span class="discret">${formatTemps(j.t_s)}</span> ${j.texte}</li>`).join("");
    }
  },
  majMesures(etatSim) {
    const table = document.getElementById("tuto-mesures");
    let liste = [];
    if (this.phase === "arret" && this.arret && this.explications[this.arret.id]) liste = this.explications[this.arret.id].mesures;
    else if (this.actif) liste = this.etape().mesures;
    table.innerHTML = liste.map(([m, lib, u, d]) =>
      `<tr><td>${lib}</td><td class="valeur">${fmt(etatSim.mesures[m], d)} ${u}</td></tr>`).join("");
  },
  surligner(ids) {
    document.querySelectorAll(".surbrillance").forEach(x => x.classList.remove("surbrillance"));
    ids.forEach(id => {
      const sel = id.startsWith("bloc:") ? `[data-bloc="${id.slice(5)}"]` : `.synoptique [data-id="${id}"]`;
      document.querySelectorAll(sel).forEach(x => x.classList.add("surbrillance"));
    });
  },
};
