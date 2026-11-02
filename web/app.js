// Client du simulateur : WebSocket, mise à jour du synoptique, panneau équipement, alarmes.
"use strict";

const LIBELLES_ACTIONS = {
  demarrer: "Démarrer", arreter: "Arrêter", ouvrir: "Ouvrir", fermer: "Fermer",
  auto: "Passer en AUTO", manu: "Passer en MANU", position: "Position (%)", vitesse: "Vitesse (%)",
  declencher: "Déclencher", rearmer: "Réarmer", consigne_vitesse: "Consigne vitesse (tr/min)",
  coupler: "Coupler au réseau", decoupler: "Découpler", consigne_mw: "Consigne (MW)", consigne: "Consigne",
  declencher_au: "AU manuel", rearmer_au: "Réarmer l'AU", rearmer_isolement_are: "Réarmer l'isolement ARE",
};
const ACTIONS_AVEC_VALEUR = new Set(["position", "vitesse", "consigne_vitesse", "consigne_mw", "consigne"]);
const MESURES_BARRE = [
  ["source.p_mw", "P source", "MW", 0], ["source.tmoy_c", "Tmoy", "°C", 1],
  ["collecteur.p_bar", "P vapeur", "bar", 1], ["GV1.niveau_pct", "N GV1", "%", 1],
  ["GV2.niveau_pct", "N GV2", "%", 1], ["GV3.niveau_pct", "N GV3", "%", 1], ["GV4.niveau_pct", "N GV4", "%", 1],
  ["turbine.p_elec_mw", "P élec", "MWe", 0], ["condenseur.p_bar", "P cond", "bar", 3],
];

const etat = { ws: null, dernier: null, selection: null, minuterieConditions: null };

// ============================================================================ utilitaires
function formatTemps(s) {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = Math.floor(s % 60);
  return [h, m, sec].map(x => String(x).padStart(2, "0")).join(":");
}
function fmt(v, dec) { return (typeof v === "number" && isFinite(v)) ? v.toFixed(dec) : "—"; }
function el(tag, attrs = {}, texte) {
  const e = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v));
  if (texte !== undefined) e.textContent = texte;
  return e;
}
function envoyer(msg) { if (etat.ws && etat.ws.readyState === 1) etat.ws.send(JSON.stringify(msg)); }

// ============================================================================ connexion
function connecter() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  etat.ws = ws;
  ws.onmessage = ev => {
    const msg = JSON.parse(ev.data);
    if (msg.type === "init") initialiser(msg);
    else if (msg.type === "etat") majEtat(msg);
    else if (msg.type === "conditions") afficherCommandes(msg);
    else if (msg.type === "reponse") afficherReponse(msg);
  };
  ws.onclose = () => setTimeout(connecter, 1000);
}

function initialiser(msg) {
  document.getElementById("version").textContent = `${msg.meta.version} — ${msg.meta.nom}`;
  const acc = document.getElementById("accelerations");
  acc.querySelectorAll("button[data-acc]").forEach(b => b.remove());
  msg.accelerations.forEach(a => {
    const b = el("button", { "data-acc": a }, `×${a}`);
    b.onclick = () => envoyer({ type: "acceleration", valeur: a });
    acc.appendChild(b);
  });
  acc.querySelector("[data-pause]").onclick = () => envoyer({ type: "pause", valeur: !(etat.dernier && etat.dernier.pause) });
  const sel = document.getElementById("choix-scenario");
  sel.innerHTML = "";
  msg.scenarios.forEach(s => sel.appendChild(el("option", { value: s.id, title: s.description }, s.titre)));
  etat.seuils = msg.seuils;
  const svg = document.getElementById("synoptique");
  if (!svg.childElementCount) {
    construireSecondaire(svg);
    svg.addEventListener("click", ev => {
      const g = ev.target.closest("[data-id]");
      if (g) selectionner(g.dataset.id);
    });
  }
  const barre = document.getElementById("mesures-barre");
  barre.innerHTML = "";
  MESURES_BARRE.forEach(([k, lib]) => {
    const d = el("div", { class: "m" });
    d.append(el("span", {}, lib), el("span", { class: "valeur", "data-barre": k }, "—"));
    barre.appendChild(d);
  });
  Courbes.init(msg.variables);
  majEtat(msg.etat);
}

// ============================================================================ mise à jour
function majEtat(e) {
  etat.dernier = e;
  const m = e.mesures;
  document.getElementById("temps").textContent = formatTemps(e.t_s);
  document.getElementById("accel-reelle").textContent = e.pause ? "pause" : `×${fmt(e.acceleration_reelle, 0)}`;
  document.querySelectorAll("#accelerations button[data-acc]").forEach(b =>
    b.classList.toggle("actif", !e.pause && Number(b.dataset.acc) === e.acceleration));
  document.querySelector("#accelerations [data-pause]").classList.toggle("actif", e.pause);
  document.getElementById("etat-standard").textContent = e.etat_standard;
  MESURES_BARRE.forEach(([k, , unite, dec]) => {
    const s = document.querySelector(`[data-barre="${k}"]`);
    if (s) s.textContent = `${fmt(m[k], dec)} ${unite}`;
  });
  majVoyants(e);
  majSynoptique(e);
  majAlarmes(e.alarmes);
  majLogique(e);
  majJournal(e.journal);
  if (etat.selection) majPanneauEtat();
}

function majVoyants(e) {
  const lg = e.logique, t = e.composants.TURBINE;
  const v = [
    ["AU", lg.au, "on-rouge"], ["Turbine décl.", t.declenchee, "on-rouge"], ["P-7", lg.p7, "on-vert"],
    ["P-14", lg.p14, "on-rouge"], ["C-9", lg.c9, "on-vert"],
    ["Isol. ARE", lg.isolement_are_au || lg.isolement_are_complet, "on-orange"],
    ["Couplé", t.couplee, "on-vert"],
  ];
  const zone = document.getElementById("voyants");
  zone.innerHTML = "";
  v.forEach(([lib, actif, cls]) => zone.appendChild(el("span", { class: `voyant ${actif ? cls : ""}` }, lib)));
  ["IS", "Phase A", "Phase B"].forEach(lib =>
    zone.appendChild(el("span", { class: "voyant futur", title: "Signaux de sauvegarde : V4" }, lib)));
  zone.appendChild(el("span", { class: "voyant on-vert", title: "Électricité modélisée en V3 : tableaux supposés sous tension" }, "6,6 kV ✓"));
}

function majSynoptique(e) {
  const m = e.mesures, comp = e.composants;
  document.querySelectorAll("#synoptique [data-mesure]").forEach(t => {
    const v = m[t.dataset.mesure];
    t.textContent = `${t.dataset.prefixe || ""}${fmt(v, Number(t.dataset.dec))} ${t.dataset.unite}`;
  });
  document.querySelectorAll("#synoptique [data-niveau]").forEach(r => {
    const n = Math.max(0, Math.min(100, m[r.dataset.niveau] ?? 0));
    const h = Number(r.dataset.haut) * n / 100;
    r.setAttribute("y", Number(r.dataset.bas) - h);
    r.setAttribute("height", h);
  });
  document.querySelectorAll("#synoptique [data-debit]").forEach(p =>
    p.classList.toggle("circule", Math.abs(m[p.dataset.debit] ?? 0) > Number(p.dataset.seuil)));
  document.querySelectorAll("#synoptique .equip[data-id]").forEach(g => {
    const c = comp[g.dataset.id];
    g.classList.toggle("selection", g.dataset.id === etat.selection);
    if (!c) return;
    if (g.classList.contains("pompe")) {
      g.classList.toggle("marche", c.en_marche);
      g.classList.toggle("arret", !c.en_marche && !c.defaut);
      g.classList.toggle("defaut", !c.en_marche && !!c.defaut);
    } else if (g.classList.contains("vanne") && c.position_pct !== undefined) {
      classerVanne(g, c.position_pct);
      g.classList.toggle("ordre", c.ordre !== null && c.ordre !== undefined);
      g.classList.toggle("en-manu", c.regulee && !c.auto);
    } else if (g.classList.contains("clapet")) {
      g.classList.toggle("ouvert", c.ouvert);
    } else if (g.classList.contains("soupape")) {
      g.classList.toggle("ouverte", c.ouverte);
    } else if (g.classList.contains("turbine")) {
      g.classList.toggle("declenchee", c.declenchee);
    }
  });
  document.querySelectorAll("#synoptique [data-vanne-turbine]").forEach(grp =>
    grp.querySelectorAll(".vanne").forEach(g => classerVanne(g, comp.TURBINE[grp.dataset.vanneTurbine])));
  const couplage = document.querySelector("#synoptique [data-couplage]");
  if (couplage) couplage.setAttribute("stroke", comp.TURBINE.couplee ? "#3fbf6a" : "#4b5560");
}

function classerVanne(g, pct) {
  g.classList.toggle("ouverte", pct >= 99);
  g.classList.toggle("fermee", pct <= 1);
  g.classList.toggle("partielle", pct > 1 && pct < 99);
}

function majAlarmes(alarmes) {
  const ul = document.getElementById("alarmes");
  ul.innerHTML = "";
  if (!alarmes.length) { ul.appendChild(el("li", { class: "discret" }, "Aucune alarme")); return; }
  alarmes.forEach(a => {
    const li = el("li", { class: `p${a.priorite} ${a.active ? "active" : "disparue"} ${a.acquittee ? "" : "nonacq"}` });
    li.append(el("span", { class: "valeur" }, formatTemps(a.t_apparition_s)), el("span", {}, a.libelle));
    if (!a.acquittee) {
      const b = el("button", {}, "Acq.");
      b.onclick = () => envoyer({ type: "acquitter", id: a.id });
      li.appendChild(b);
    } else li.appendChild(el("span"));
    ul.appendChild(li);
  });
}

function majLogique(e) {
  if (!document.getElementById("onglet-logique").classList.contains("actif")) return;
  const lg = e.logique, s = etat.seuils || {};
  const ligne = (nom, actif, texte, alerte = false) =>
    `<tr><td><b>${nom}</b></td><td class="${actif ? (alerte ? "etat-alerte" : "etat-on") : "etat-off"}">${actif ? "PRÉSENT" : "absent"}</td><td class="discret">${texte || ""}</td></tr>`;
  const t = e.composants.TURBINE;
  document.getElementById("logique").innerHTML = `
    <div class="carte"><h2>Permissifs et verrous</h2><table>
      ${ligne("P-4", lg.p4, "disjoncteurs d'AU ouverts → déclenche la turbine, isole l'ARE si Tmoy basse", true)}
      ${ligne("P-7", lg.p7, s["P-7"])}
      ${ligne("P-14", lg.p14, s["P-14"], true)}
      ${ligne("C-9", lg.c9, s["C-9"])}
    </table></div>
    <div class="carte"><h2>Arrêt automatique (AU)</h2><table>
      ${ligne("AU", lg.au, lg.au ? "causes : " + lg.au_causes.join(", ") : "", true)}
      <tr><td>Causes présentes</td><td colspan="2">${lg.causes_au.join(", ") || "aucune"}</td></tr>
      <tr><td>Seuil niveau GV</td><td colspan="2" class="discret">${s["AU niveau GV très bas"] || ""}</td></tr>
      <tr><td>Déclenchement turbine</td><td colspan="2" class="discret">${s["AU déclenchement turbine"] || ""}</td></tr>
      <tr><td>Niveaux très bas</td><td colspan="2">${lg.niveau_tres_bas_gv.map((x, i) => `GV${i + 1} ${x ? "⚠" : "ok"}`).join(" · ")}</td></tr>
    </table></div>
    <div class="carte"><h2>Turbine</h2><table>
      ${ligne("Déclenchée", t.declenchee, t.cause, true)}
      <tr><td>Causes présentes</td><td colspan="2">${lg.causes_turbine.join(", ") || "aucune"}</td></tr>
      <tr><td>Seuils</td><td colspan="2" class="discret">${s["Déclenchement turbine"] || ""}</td></tr>
    </table></div>
    <div class="carte"><h2>Eau alimentaire</h2><table>
      ${ligne("Isolement GD", lg.isolement_are_au, s["Isolement ARE GD"], true)}
      ${ligne("Isolement complet", lg.isolement_are_complet, s["Isolement ARE complet"], true)}
      ${ligne("Recirculation CEX", lg.recirc_cex, "débit mini des pompes d'extraction")}
      <tr><td>Déclenchement APP</td><td colspan="2" class="discret">${s["Déclenchement APP"] || ""}</td></tr>
    </table></div>`;
}

function majJournal(journal) {
  if (!document.getElementById("onglet-journal").classList.contains("actif")) return;
  const table = document.getElementById("journal");
  table.innerHTML = "";
  [...journal].reverse().forEach(ev => {
    const tr = el("tr", { class: ev.categorie });
    tr.append(el("td", {}, formatTemps(ev.t_s)), el("td", {}, ev.categorie), el("td", {}, ev.texte));
    table.appendChild(tr);
  });
}

// ============================================================================ panneau équipement
function selectionner(id) {
  etat.selection = id;
  document.getElementById("eq-titre").textContent = id;
  document.getElementById("eq-aide").style.display = "none";
  document.getElementById("eq-message").textContent = "";
  document.getElementById("eq-commandes").innerHTML = "";
  majPanneauEtat();
  envoyer({ type: "conditions", cible: id });
  clearInterval(etat.minuterieConditions);
  etat.minuterieConditions = setInterval(() => envoyer({ type: "conditions", cible: id }), 1000);
  document.querySelectorAll("#synoptique .equip").forEach(g => g.classList.toggle("selection", g.dataset.id === id));
}

const LIBELLES_ETAT = {
  type: "Type", systeme: "Système", alim: "Alimentation", air: "Air comprimé", en_marche: "En marche",
  vitesse_pct: "Vitesse (%)", auto: "Auto", defaut: "Défaut", position_pct: "Position (%)", demande_pct: "Demande (%)",
  ordre_raison: "Ordre automatique", actionneur: "Actionneur", air_restant_min: "Réserve d'air (min)",
  p_bar: "Pression (bar)", niveau_pct: "Niveau GE (%)", m_eau_t: "Masse d'eau (t)", ouverte: "Ouverte",
  tarage_bar: "Tarage (bar)", sollicitations: "Sollicitations", declenchee: "Déclenchée", cause: "Cause",
  couplee: "Couplée", vitesse_tr_min: "Vitesse (tr/min)", p_elec_mw: "P électrique (MW)", consigne_mw: "Consigne (MW)",
  consigne_eff_mw: "Consigne rampée (MW)", ouverture_reglage_pct: "Vannes de réglage (%)",
  ouverture_arret_pct: "Vannes d'arrêt (%)", p_mw: "Puissance (MW)", tmoy_c: "Tmoy (°C)", tref_c: "Tref (°C)",
  au: "AU", consigne: "Consigne", unite: "Unité", consigne_bar: "Consigne (bar)", ouverture_pct: "Ouverture (%)",
  t_c: "Température (°C)", niveau_puits_pct: "Niveau puits (%)", volume_cst_m3: "Volume CST (m³)", ouvert: "Ouvert",
};
const ETAT_CACHE = new Set(["regulee", "vitesse_variable", "ordre", "niveau_voies", "mini", "maxi", "consigne_vitesse_tr_min"]);

function majPanneauEtat() {
  const c = etat.dernier && etat.dernier.composants[etat.selection];
  const div = document.getElementById("eq-etat");
  if (!c) { div.innerHTML = ""; return; }
  const lignes = Object.entries(c)
    .filter(([k, v]) => !ETAT_CACHE.has(k) && v !== null && v !== "" && !(typeof v === "object"))
    .map(([k, v]) => `<tr><td>${LIBELLES_ETAT[k] || k}</td><td class="valeur">${typeof v === "number" ? fmt(v, 2) : v === true ? "oui" : v === false ? "non" : v}</td></tr>`);
  if (c.niveau_voies) lignes.push(`<tr><td>Voies de niveau</td><td class="valeur">${c.niveau_voies.map(x => fmt(x, 1)).join(" / ")}</td></tr>`);
  div.innerHTML = `<table>${lignes.join("")}</table>`;
}

function afficherCommandes(msg) {
  if (msg.cible !== etat.selection) return;
  const zone = document.getElementById("eq-commandes");
  const saisies = {};
  zone.querySelectorAll("input[data-action]").forEach(i => { saisies[i.dataset.action] = i.value; });
  zone.innerHTML = "";
  if (!msg.commandes.length) { zone.appendChild(el("p", { class: "discret" }, "Pas de commande sur cet équipement.")); return; }
  msg.commandes.forEach(cmd => {
    const bloc = el("div", { class: "commande" });
    const ligne = el("div", { class: "ligne" });
    const bouton = el("button", {}, LIBELLES_ACTIONS[cmd.action] || cmd.action);
    let saisie = null;
    if (ACTIONS_AVEC_VALEUR.has(cmd.action)) {
      saisie = el("input", { type: "number", step: "any", "data-action": cmd.action });
      saisie.value = saisies[cmd.action] ?? "";
      ligne.append(saisie);
    }
    bouton.onclick = () => envoyer({ type: "commande", cible: msg.cible, action: cmd.action,
                                     valeur: saisie ? saisie.value : null });
    if (!cmd.possible) bouton.disabled = true;
    ligne.prepend(bouton);
    bloc.appendChild(ligne);
    if (cmd.conditions.length) {
      const ul = el("ul");
      cmd.conditions.forEach(c => ul.appendChild(el("li", { class: c.ok ? "ok" : "ko" }, c.texte)));
      bloc.appendChild(ul);
    }
    zone.appendChild(bloc);
  });
}

function afficherReponse(msg) {
  const d = document.getElementById("eq-message");
  d.className = msg.ok ? "ok" : "ko";
  d.textContent = msg.ok ? `✓ ${msg.cible} : ${LIBELLES_ACTIONS[msg.action] || msg.action}`
                         : `✗ Refusé : ${msg.raisons.join(" ; ")}`;
  envoyer({ type: "conditions", cible: msg.cible });
}

// ============================================================================ onglets, sauvegarde
document.querySelectorAll("#onglets [data-onglet]").forEach(b => b.addEventListener("click", () => {
  document.querySelectorAll("#onglets [data-onglet]").forEach(x => x.classList.toggle("actif", x === b));
  document.querySelectorAll(".onglet").forEach(o => o.classList.toggle("actif", o.id === `onglet-${b.dataset.onglet}`));
  if (etat.dernier) majEtat(etat.dernier);
  if (b.dataset.onglet === "courbes") Courbes.rafraichir();
}));
setInterval(() => {
  if (document.getElementById("onglet-courbes").classList.contains("actif")) Courbes.rafraichir();
}, 1000);

document.getElementById("btn-acquitter-tout").onclick = () => envoyer({ type: "acquitter", id: null });
document.getElementById("btn-sauver").onclick = async () => {
  const r = await fetch("/api/sauvegarde");
  const blob = await r.blob();
  const a = el("a", { href: URL.createObjectURL(blob), download: `centrale_${formatTemps(etat.dernier.t_s).replaceAll(":", "h")}.json` });
  a.click();
};
document.getElementById("btn-charger").onclick = () => document.getElementById("fichier").click();
document.getElementById("fichier").onchange = async ev => {
  const f = ev.target.files[0];
  if (!f) return;
  const r = await fetch("/api/chargement", { method: "POST", headers: { "Content-Type": "application/json" }, body: await f.text() });
  const rep = await r.json();
  alert(r.ok ? `État chargé (t = ${formatTemps(rep.t_s)})` : `Échec : ${rep.detail}`);
  ev.target.value = "";
};
document.getElementById("btn-scenario").onclick = async () => {
  const id = document.getElementById("choix-scenario").value;
  if (confirm(`Charger le scénario « ${id} » ? L'état actuel sera perdu (pensez à sauvegarder).`))
    await fetch(`/api/scenario/${id}`, { method: "POST" });
};

connecter();
