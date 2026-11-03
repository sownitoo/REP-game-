// Client du simulateur : synoptiques, panneau équipement, alarmes, logique, courbes, sauvegarde.
// Le transport (WebSocket ou Web Worker Pyodide) est choisi par transport.js selon window.REP_MODE.
"use strict";

const LIBELLES_ACTIONS = {
  demarrer: "Démarrer", arreter: "Arrêter", ouvrir: "Ouvrir", fermer: "Fermer",
  auto: "Passer en AUTO", manu: "Passer en MANU", position: "Position", vitesse: "Vitesse (%)",
  declencher: "Déclencher", rearmer: "Réarmer", consigne_vitesse: "Consigne vitesse (tr/min)",
  coupler: "Coupler", decoupler: "Découpler", consigne_mw: "Consigne (MW)", consigne: "Consigne",
  declencher_au: "AU manuel", rearmer_au: "Réarmer l'AU", rearmer_isolement_are: "Réarmer l'isolement ARE",
  bloquer_flux_bas: "Bloquer l'AU flux seuil bas", debloquer_flux_bas: "Débloquer l'AU flux seuil bas",
  extraire_arret: "Extraire les groupes d'arrêt", puissance: "Puissance (%)", position_g: "Groupe G (pas)",
  mode_tmoy: "Mode Tmoy (C-7 / C-8)", mode_pression: "Mode pression", rearmer_c7: "Réarmer C-7",
  borication: "Borication (m³ d'acide)", dilution: "Dilution (m³ d'eau)", arret: "Arrêt",
  bloquer_is: "Bloquer l'IS (sous P-11)", declencher_is: "IS manuelle", rearmer_is: "Réarmer l'IS",
  ouvrir_arrivee: "Ouvrir l'arrivée normale", fermer_arrivee: "Fermer l'arrivée normale",
  perte_reseau: "Perte du réseau (formateur)", retour_reseau: "Retour du réseau (formateur)",
  isoler_fuite: "Isoler la fuite", decoupler: "Découpler",
  rearmer_isolement_vapeur: "Réarmer l'isolement vapeur", rearmer_phase_b: "Réarmer la phase B",
  breche_primaire: "Brèche primaire (∅ cm)", rtgv: "Rupture de tube de GV (n° GV)",
  breche_vapeur: "Brèche vapeur (n° GV)", porv_bloquee: "PORV bloquée ouverte (n° 1 ou 2)", perte_rri: "Perte du RRI",
  rupture_air: "Rupture du collecteur d'air", supprimer_breches: "Supprimer les brèches",
  grappe_coincee: "Grappe la plus efficace coincée (fin de cycle)",
};
const ACTIONS_AVEC_VALEUR = new Set(["breche_primaire", "rtgv", "breche_vapeur", "porv_bloquee", "position", "position_g", "vitesse", "consigne_vitesse", "consigne_mw", "consigne", "puissance",
                                     "borication", "dilution"]);
const MESURES_BARRE = [
  ["coeur.puissance_pct", "Puissance", "%", 1], ["primaire.tmoy_c", "Tmoy", "°C", 1],
  ["pzr.p_bar", "P PZR", "bar", 1], ["pzr.niveau_pct", "Niv. PZR", "%", 0],
  ["collecteur.p_bar", "P vapeur", "bar", 1], ["turbine.p_elec_mw", "P élec", "MWe", 0],
];
// champs montrés en tête du panneau équipement (le reste est dans « État détaillé »)
const RESUME_CLES = ["en_marche", "defaut", "position_pct", "auto", "vitesse_pct", "ouverte", "ouvert", "puissance_pct",
                     "position_pas", "arret_insere_pct", "rho_pcm", "p_bar", "niveau_pct", "consigne", "mode",
                     "declenchee", "couplee", "p_elec_mw", "au"];
const RESUME_MAX = 5;
const SYNOPTIQUES = [["synoptique-ensemble", "construireEnsemble"], ["synoptique-primaire", "construirePrimaire"], ["synoptique-secondaire", "construireSecondaire"],
                     ["synoptique-asg", "construireASG"], ["synoptique-rcv", "construireRCV"],
                     ["synoptique-rra", "construireRRA"], ["synoptique-coeur", "construireVueCoeur"],
                     ["synoptique-elec", "construireElec"], ["synoptique-ris", "construireRIS"]];
function construireVueCoeur(svg) { VueCoeur.construire(svg); }

const VERSION_UI = "V4";     // doit correspondre à meta.version de plant.yaml
const etat = { transport: null, dernier: null, selection: null, minuterieConditions: null, seuils: {} };

// ============================================================================ utilitaires
function formatTemps(s) {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = Math.floor(s % 60);
  return [h, m, sec].map(x => String(x).padStart(2, "0")).join(":");
}
function fmt(v, dec) {
  if (typeof v !== "number" || !isFinite(v)) return "—";
  const t = v.toFixed(dec);
  return /^-0(\.0*)?$/.test(t) ? t.slice(1) : t;          // pas de « -0 »
}
function el(tag, attrs = {}, texte) {
  const e = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v));
  if (texte !== undefined) e.textContent = texte;
  return e;
}
function envoyer(msg) { etat.transport.envoyer(msg); }
function telecharger(nom, objet) {
  const blob = new Blob([JSON.stringify(objet)], { type: "application/json" });
  const a = el("a", { href: URL.createObjectURL(blob), download: nom });
  a.click();
}

// ============================================================================ messages du simulateur
function surMessage(msg) {
  if (msg.type === "init") initialiser(msg);
  else if (msg.type === "etat") majEtat(msg);
  else if (msg.type === "conditions") afficherCommandes(msg);
  else if (msg.type === "reponse") afficherReponse(msg);
  else if (msg.type === "historique") Courbes.recevoir(msg.series);
  else if (msg.type === "export") telecharger(`centrale_${formatTemps(msg.t_s).replaceAll(":", "h")}.json`, msg.donnees);
  else if (msg.type === "import") alert(msg.ok ? `État chargé (t = ${formatTemps(msg.t_s)})` : `Échec : ${msg.erreur}`);
  else if (msg.type === "erreur") alert(msg.texte);
}

function surStatut(texte) {
  document.getElementById("chargement").style.display = "flex";
  document.getElementById("chargement-texte").textContent = texte;
}

function initialiser(msg) {
  document.getElementById("chargement").style.display = "none";
  const mode = window.REP_MODE === "serveur" ? "serveur Python" : "dans le navigateur";
  document.getElementById("version").textContent = `${msg.meta.version} — simulation ${mode}`;
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
  etat.scenarios = msg.scenarios;
  const info = () => {
    const sc = etat.scenarios.find(x => x.id === sel.value);
    document.getElementById("scenario-info").innerHTML = sc ? `<p>${sc.description}</p>`
      + (sc.objectifs.length ? `<ol>${sc.objectifs.map(o => `<li>${o}</li>`).join("")}</ol>` : "") : "";
  };
  sel.onchange = info;
  info();
  etat.seuils = msg.seuils;
  if (msg.meta.version !== VERSION_UI) {
    surStatut(`Interface (${VERSION_UI}) et simulateur (${msg.meta.version}) différents : recharger la page sans cache `
              + "(Ctrl + F5, ou Cmd + Maj + R sur Mac).");
  }
  SYNOPTIQUES.forEach(([id, fonction]) => {
    const svg = document.getElementById(id);
    if (svg.childElementCount) return;
    try {
      window[fonction](svg);
    } catch (err) {                        // un schéma en erreur ne doit pas empêcher les autres de s'afficher
      console.error(err);
      svgEl("text", { x: 40, y: 80, class: "lib-fort", fill: "#e5484d" }, svg).textContent =
        `Erreur d'affichage de ce schéma : ${err.message}`;
      return;
    }
    preparerDescriptions(svg);
    Zoom.activer(svg);
    svg.addEventListener("click", ev => {
      const lien = ev.target.closest("[data-lien-onglet]");
      if (lien) { ouvrirOnglet(lien.dataset.lienOnglet); return; }
      const g = ev.target.closest("[data-id]");
      if (g) selectionner(g.dataset.id);
    });
    svg.addEventListener("dblclick", ev => {
      const g = ev.target.closest("[data-id]");
      if (g) ouvrirDetail(svg, g);
    });
  });
  const barre = document.getElementById("mesures-barre");
  barre.innerHTML = "";
  MESURES_BARRE.forEach(([k, lib]) => {
    const d = el("div", { class: "m" });
    d.append(el("span", {}, lib), el("span", { class: "valeur", "data-barre": k }, "—"));
    barre.appendChild(d);
  });
  if (!document.getElementById("pc-r")) PilotageCoeur.init();
  Courbes.init(msg.variables);
  majEtat(msg.etat);
}

// ============================================================================ mise à jour
function majEtat(e) {
  etat.dernier = e;
  const m = e.mesures;
  document.getElementById("temps").textContent = formatTemps(e.t_s);
  const tenue = e.acceleration_reelle, freine = !e.pause && tenue < 0.9 * e.acceleration;
  document.getElementById("accel-reelle").textContent = e.pause ? "en pause" : freine ? `tenue ×${fmt(tenue, 0)}` : "";
  document.querySelectorAll("#accelerations button[data-acc]").forEach(b =>
    b.classList.toggle("actif", !e.pause && Number(b.dataset.acc) === e.acceleration));
  document.querySelector("#accelerations [data-pause]").classList.toggle("actif", e.pause);
  majEtats(e.etats);
  MESURES_BARRE.forEach(([k, , unite, dec]) => {
    const s = document.querySelector(`[data-barre="${k}"]`);
    if (s) s.textContent = `${fmt(m[k], dec)} ${unite}`;
  });
  majVoyants(e);
  majSynoptiques(e);
  if (document.getElementById("onglet-coeur").classList.contains("actif")) { VueCoeur.maj(m); PilotageCoeur.maj(e); }
  VueNeutrons.maj(e);
  majAlarmes(e.alarmes);
  majLogique(e);
  majJournal(e.journal);
  if (etat.selection) majPanneauEtat();
}

// état standard + check-list des conditions pour l'état suivant (§5)
function majEtats(et) {
  const b = document.getElementById("etat-standard");
  const pret = et.checklist.length && et.checklist.every(p => p.ok);
  b.textContent = et.libelle + (et.vise ? (pret ? "  ✓" : `  → ${et.vise}`) : "");
  const zone = document.getElementById("etat-contenu");
  if (zone.hidden) return;
  zone.innerHTML = `<b>${et.libelle}</b>`
    + (et.vise ? `<p class="discret petit">Pour passer en <b>${et.libelle_vise}</b> :</p>` : "")
    + `<ul class="checklist">${et.checklist.map(p => `<li class="${p.ok ? "ok" : "ko"}">${p.texte}</li>`).join("")}</ul>`;
}

// seuls les signaux importants et présents sont affichés (le détail est dans l'onglet Logique)
function majVoyants(e) {
  const lg = e.logique, t = e.composants.TURBINE;
  const v = [
    ["AU", lg.au, "on-rouge", lg.au_causes.join(", ")], ["IS", lg.is_actif, "on-rouge", lg.is_causes.join(", ")],
    ["IS bloquée", lg.is_bloquee && !lg.is_actif, "on-orange", "blocage sous P-11"],
    ["Turbine déclenchée", t.declenchee, "on-rouge", t.cause],
    ["Perte RRI", lg.perte_rri, "on-rouge", "pompes primaires à arrêter"],
    ["Réseau perdu", e.mesures["elec.reseau_ok"] < 0.5, "on-rouge", "perte des alimentations externes"],
    ["Diesels", e.mesures["elec.DIESEL_A.en_service"] > 0.5 || e.mesures["elec.DIESEL_B.en_service"] > 0.5, "on-orange",
     "groupe(s) électrogène(s) en service"],
    ["Batteries", e.mesures["elec.LBA.decharge"] > 0.5 || e.mesures["elec.LBB.decharge"] > 0.5, "on-orange",
     `A ${fmt(e.mesures["elec.LBA.charge_pct"], 0)} % · B ${fmt(e.mesures["elec.LBB.charge_pct"], 0)} %`],
    ["Air perdu", e.mesures["air.p_bar"] < 5, "on-rouge", "vannes pneumatiques en repli"],
    ["Simulation figée", e.mesures["primaire.hors_domaine"] > 0.5, "on-rouge", "primaire hors du domaine du modèle"],
    ["Injection", e.mesures["ris.qm_kg_s"] > 0.5, "on-rouge", "injection de sécurité en cours"],
    ["Isolement vapeur", lg.isolement_vapeur, "on-orange", ""], ["Phase B", lg.phase_b, "on-rouge", "aspersion enceinte"],
    ["P-14", lg.p14, "on-rouge", "niveau GV très haut"], ["Runback", lg.c3 || lg.c4, "on-rouge", "C-3 / C-4"],
    ["Isolement ARE", lg.isolement_are_au || lg.isolement_are_complet, "on-orange", ""],
    ["ASG", e.mesures["asg.qm_kg_s"] > 1, "on-orange", "alimentation de secours des GV en service"],
    ["Contournement", e.mesures["gctc.qm_kg_s"] > 1, "on-orange", "GCT-c ouvert"],
  ].filter(x => x[1]);
  const zone = document.getElementById("voyants");
  const cle = v.map(x => x[0]).join("|");
  if (zone.dataset.cle === cle) return;
  zone.dataset.cle = cle;
  zone.innerHTML = "";
  v.forEach(([lib, , cls, titre]) => zone.appendChild(el("span", { class: `voyant ${cls}`, title: titre || "" }, lib)));
}

function majSynoptiques(e) {
  const m = e.mesures, comp = e.composants;
  document.querySelectorAll(".synoptique [data-mesure]").forEach(t => {
    const v = m[t.dataset.mesure];
    t.textContent = `${t.dataset.prefixe || ""}${fmt(v, Number(t.dataset.dec))} ${t.dataset.unite}`;
  });
  document.querySelectorAll(".synoptique [data-niveau]").forEach(r => {
    const n = Math.max(0, Math.min(100, m[r.dataset.niveau] ?? 0));
    const h = Number(r.dataset.haut) * n / 100;
    r.setAttribute("y", Number(r.dataset.bas) - h);
    r.setAttribute("height", h);
  });
  document.querySelectorAll(".synoptique [data-grappe]").forEach(r => {
    const v = m[r.dataset.grappe] ?? 0, max = Number(r.dataset.max);
    const insere = r.dataset.inverse ? 1 - v / max : v / max;      // position en pas → fraction insérée
    const h = Number(r.dataset.haut) * Math.max(0, Math.min(1, insere));
    r.setAttribute("y", Number(r.dataset.bas) - Number(r.dataset.haut));
    r.setAttribute("height", h);
  });
  document.querySelectorAll(".synoptique [data-debit]").forEach(p => {
    const q = m[p.dataset.debit] ?? 0, actif = Math.abs(q) > Number(p.dataset.seuil);
    p.classList.toggle("circule", actif);
    p.classList.toggle("inverse", actif && q < 0);
    if (actif && p.dataset.nominal) {           // vitesse de l'animation ∝ débit
      const duree = Math.min(6, 0.8 * Number(p.dataset.nominal) / Math.abs(q));
      p.style.animationDuration = `${duree.toFixed(2)}s`;
    }
  });
  document.querySelectorAll(".synoptique [data-chaleur]").forEach(g =>
    g.style.fillOpacity = (0.12 + 0.75 * Math.max(0, Math.min(1, (m[g.dataset.chaleur] ?? 0) / 100))).toFixed(2));
  const inseree = { R: 1 - (m["grappes.position_pas"] ?? 0) / 228, S: (m["grappes.arret_insere_pct"] ?? 0) / 100,
                   G: 1 - (m["grappes.g_pas"] ?? 228) / 228 };
  document.querySelectorAll(".synoptique [data-grappe-groupe]").forEach(c =>
    c.style.fillOpacity = (0.15 + 0.85 * Math.max(0, Math.min(1, inseree[c.dataset.grappeGroupe]))).toFixed(2));
  document.querySelectorAll(".synoptique .equip[data-id]").forEach(g => {
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
    } else if (g.classList.contains("diesel")) {
      g.classList.toggle("marche", !!c.en_service);
      g.classList.toggle("defaut", c.etat === "echec");
    } else if (g.classList.contains("chaufferette")) {
      g.classList.toggle("active", c.puissance_kw > 0);
      g.classList.toggle("en-manu", !c.auto);
    }
  });
  document.querySelectorAll(".synoptique [data-vanne-turbine]").forEach(grp =>
    grp.querySelectorAll(".vanne").forEach(g => classerVanne(g, comp.TURBINE[grp.dataset.vanneTurbine])));
  const couplage = document.querySelector(".synoptique [data-couplage]");
  if (couplage) couplage.setAttribute("stroke", comp.TURBINE.couplee ? "#3fbf6a" : "#4b5560");
  document.querySelectorAll(".synoptique [data-tension]").forEach(l =>
    l.classList.toggle("sous-tension", (m[l.dataset.tension] ?? 100) >= 62));
  document.querySelectorAll(".synoptique [data-disj]").forEach(r => {
    const [id, champ] = r.dataset.disj.split(".");
    const c = comp[id] || {};
    r.classList.toggle("ferme", champ === "couple" ? c.etat === "couple" : !!c[champ]);
  });
  document.querySelectorAll(".synoptique [data-diesel]").forEach(t => {
    const d = comp[t.dataset.diesel];
    if (d) t.textContent = { arret: "à l'arrêt", demarrage: "démarrage…", pret: "à vitesse", couple: "couplé",
                             echec: "ÉCHEC" }[d.etat] + (d.refus ? " · en panne" : "");
  });
  const disque = document.querySelector(".synoptique [data-disque]");
  if (disque) disque.textContent = m["prt.disque_rompu"] > 0.5 ? "DISQUE ROMPU" : "disque intact";
  const srcLg = document.querySelector(".synoptique [data-source-lg]");
  if (srcLg && comp.RESEAU) srcLg.textContent = { TS: "LG sur le soutirage", TA: "LG sur les transfos auxiliaires",
                                                   "": "LG HORS TENSION" }[comp.RESEAU.source_normale];
  const alt = document.querySelector(".synoptique [data-alternateur]");
  if (alt) alt.classList.toggle("couple", !!comp.TURBINE.couplee);
  if (document.getElementById("onglet-ensemble").classList.contains("actif")) {
    const etats = etatsEnsemble(e);
    document.querySelectorAll("#synoptique-ensemble [data-bloc]").forEach(g => {
      const st = etats[g.dataset.bloc] || "ok";
      ["ok", "arret", "alerte", "defaut"].forEach(k => g.classList.toggle(`etat-${k}`, k === st));
    });
  }
  const rea = document.querySelector(".synoptique [data-rea-mode]");
  if (rea && comp.REA) rea.textContent = `mode ${comp.REA.mode}` + (comp.REA.appoint_auto ? " · appoint" : "");
  const mode = document.querySelector(".synoptique [data-gct-mode]");
  if (mode) mode.textContent = `mode ${e.gct.mode}${e.gct.c8 ? " · C-8" : e.gct.c7 ? " · C-7" : ""}`;
}

function classerVanne(g, pct) {
  g.classList.toggle("ouverte", pct >= 99);
  g.classList.toggle("fermee", pct <= 1);
  g.classList.toggle("partielle", pct > 1 && pct < 99);
}

function majAlarmes(alarmes) {
  const nonAcq = alarmes.filter(a => !a.acquittee).length;
  const nb = document.getElementById("nb-alarmes");
  nb.textContent = alarmes.length;
  document.getElementById("btn-panneau").classList.toggle("alerte", nonAcq > 0);
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
  const lg = e.logique, s = etat.seuils, m = e.mesures, t = e.composants.TURBINE;
  const ligne = (nom, actif, texte, alerte = false, libOn = "PRÉSENT") =>
    `<tr><td><b>${nom}</b></td><td class="${actif ? (alerte ? "etat-alerte" : "etat-on") : "etat-off"}">${actif ? libOn : "absent"}</td><td class="discret">${texte || ""}</td></tr>`;
  const seuilsAu = Object.entries(s).filter(([k]) => k.startsWith("AU "))
    .map(([k, v]) => `<tr><td>${k.slice(3)}</td><td colspan="2" class="discret">${v}</td></tr>`).join("");
  const dts = [1, 2, 3, 4].map(b => `B${b} : ${fmt(m[`B${b}.dt_c`], 1)} / ${fmt(lg.otdt_seuil_c[b - 1], 1)} / ${fmt(lg.opdt_seuil_c[b - 1], 1)}`).join("<br>");
  document.getElementById("logique").innerHTML = `
    <div class="carte"><h2>Arrêt automatique (AU)</h2><table>
      ${ligne("AU", lg.au, lg.au ? "causes : " + lg.au_causes.join(", ") : "", true)}
      <tr><td>Causes présentes</td><td colspan="2">${lg.causes_au.join(", ") || "aucune"}</td></tr>
      ${ligne("Flux seuil bas", lg.flux_bas_bloque, "bloqué par l'opérateur (au-dessus de P-10)", false, "BLOQUÉ")}
      <tr><td>ΔT mesuré / seuils</td><td colspan="2" class="discret">${dts}<br>(ΔT / surtempérature / surpuissance, °C)</td></tr>
      ${seuilsAu}
    </table></div>
    <div class="carte"><h2>Permissifs (P)</h2><table>
      ${ligne("P-4", lg.p4, "disjoncteurs d'AU ouverts : turbine, isolement ARE si Tmoy basse", true)}
      ${ligne("P-7", lg.p7, s["P-7"])}
      ${ligne("P-8", lg.p8, s["P-8"])}
      ${ligne("P-9", lg.p9, s["P-9"])}
      ${ligne("P-10", lg.p10, s["P-10"])}
      ${ligne("P-12", lg.p12, s["P-12"], true)}
      ${ligne("P-13", lg.p13, "charge turbine faible")}
      ${ligne("P-14", lg.p14, s["P-14"], true)}
    </table></div>
    <div class="carte"><h2>Verrous de conduite (C)</h2><table>
      ${ligne("C-2", lg.c2, s["C-2"], true)}
      ${ligne("C-3", lg.c3, s["C-3"], true)}
      ${ligne("C-4", lg.c4, s["C-4"], true)}
      ${ligne("C-5", lg.c5, s["C-5"])}
      ${ligne("C-7", lg.c7, s["C-7"])}
      ${ligne("C-8", lg.c8, s["C-8"])}
      ${ligne("C-9", lg.c9, s["C-9"])}
      ${ligne("C-11", lg.c11, s["C-11"])}
      <tr><td>Contournement</td><td colspan="2">mode ${e.gct.mode}</td></tr>
    </table></div>
    <div class="carte"><h2>Injection de sécurité (signal) et P-11</h2><table>
      ${ligne("IS", lg.is_actif, lg.is_actif ? "causes : " + lg.is_causes.join(", ") : "", true)}
      <tr><td>Causes présentes</td><td colspan="2">${lg.causes_is.join(", ") || "aucune"}</td></tr>
      ${ligne("P-11", lg.p11, s["P-11"])}
      ${ligne("IS bloquée", lg.is_bloquee, "blocage manuel autorisé sous P-11, levé au-dessus", false, "BLOQUÉE")}
      ${ligne("Aspiration RRA fermée auto", lg.rra_isole_auto, "P > 41 bar", true)}
      ${ligne("Aspiration charge sur PTR", lg.aspiration_ptr, "niveau VCT très bas ou IS", true)}
      ${ligne("Perte RRI", lg.perte_rri, "pompes primaires en défaut après le délai", true)}
    </table></div>
    <div class="carte"><h2>Turbine et eau alimentaire</h2><table>
      ${ligne("Turbine déclenchée", t.declenchee, t.cause, true)}
      <tr><td>Causes présentes</td><td colspan="2">${lg.causes_turbine.join(", ") || "aucune"}</td></tr>
      ${ligne("Isolement ARE GD", lg.isolement_are_au, s["Isolement ARE GD"], true)}
      ${ligne("Isolement ARE complet", lg.isolement_are_complet, s["Isolement ARE complet"], true)}
      ${ligne("Décharge RCV isolée", lg.decharge_isolee, s["Niveau PZR bas"], true)}
      <tr><td>ASG</td><td colspan="2" class="discret">${s["Démarrage ASG"]}</td></tr>
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
  document.getElementById("panneau-equipement").hidden = false;
  document.querySelector("main").classList.remove("sans-panneau");
  document.getElementById("eq-titre").textContent = id;
  document.getElementById("eq-fiche").innerHTML = Glossaire.html(id);
  document.getElementById("eq-message").textContent = "";
  document.getElementById("eq-commandes").innerHTML = "";
  majPanneauEtat();
  envoyer({ type: "conditions", cible: id });
  clearInterval(etat.minuterieConditions);
  etat.minuterieConditions = setInterval(() => envoyer({ type: "conditions", cible: id }), 1000);
}

const LIBELLES_ETAT = {
  type: "Type", systeme: "Système", alim: "Alimentation", air: "Air comprimé", en_marche: "En marche",
  vitesse_pct: "Vitesse (%)", auto: "Auto", defaut: "Défaut", position_pct: "Position (%)", demande_pct: "Demande (%)",
  ordre_raison: "Ordre automatique", actionneur: "Actionneur", air_restant_min: "Réserve d'air (min)",
  p_bar: "Pression (bar)", niveau_pct: "Niveau (%)", m_eau_t: "Masse d'eau (t)", ouverte: "Ouverte",
  tarage_bar: "Tarage (bar)", sollicitations: "Sollicitations", declenchee: "Déclenchée", cause: "Cause",
  couplee: "Couplée", vitesse_tr_min: "Vitesse (tr/min)", p_elec_mw: "P électrique (MW)", consigne_mw: "Consigne (MW)",
  consigne_eff_mw: "Consigne rampée (MW)", ouverture_reglage_pct: "Vannes de réglage (%)",
  ouverture_arret_pct: "Vannes d'arrêt (%)", consigne: "Consigne", unite: "Unité", ouverture_pct: "Ouverture (%)",
  t_c: "Température (°C)", niveau_puits_pct: "Niveau puits (%)", volume_cst_m3: "Volume CST (m³)", ouvert: "Ouvert",
  puissance_pct: "Puissance (%)", rho_pcm: "Réactivité (pcm)", position_pas: "Groupe de régulation (pas)",
  arret_insere_pct: "Groupes d'arrêt insérés (%)", chute: "Grappes chutées (AU)", t_comb_c: "T combustible (°C)",
  bore_ppm: "Bore (ppm)", vitesse_pas_min: "Vitesse grappes (pas/min)", consigne_manu_pas: "Consigne manuelle (pas)",
  puissance_kw: "Puissance (kW)", coupe: "Coupure", chauffe_mw: "Chauffe (MW)", aspersion_kg_s: "Aspersion (kg/s)",
  porv_kg_s: "PORV (kg/s)", mode: "Mode", c7: "C-7 armé", c8: "C-8 armé", demande: "Demande",
  consigne_bar: "Consigne (bar)", charge_retard_pct: "Charge filtrée (%)",
};
const ETAT_CACHE = new Set(["regulee", "vitesse_variable", "ordre", "niveau_voies", "mini", "maxi", "consigne_vitesse_tr_min",
                            "proportionnel", "voies_pression", "voies_niveau"]);

function deselectionner() {
  etat.selection = null;
  clearInterval(etat.minuterieConditions);
  document.getElementById("panneau-equipement").hidden = true;
  if (etat.dernier) majSynoptiques(etat.dernier);
}

function valeurLisible(v) {
  return typeof v === "number" ? fmt(v, Math.abs(v) >= 100 ? 0 : 1) : v === true ? "oui" : v === false ? "non" : v;
}

function majPanneauEtat() {
  const c = etat.dernier && etat.dernier.composants[etat.selection];
  const div = document.getElementById("eq-etat");
  const resume = document.getElementById("eq-resume");
  if (!c) { div.innerHTML = ""; resume.innerHTML = ""; return; }
  const cles = RESUME_CLES.filter(k => c[k] !== undefined && c[k] !== null && c[k] !== ""
                                       && !(k === "defaut" && !c[k])).slice(0, RESUME_MAX);
  resume.innerHTML = `<div class="sous-titre discret">${[c.type, c.systeme].filter(Boolean).join(" · ")}</div>`
    + cles.map(k => `<div class="pastille"><span class="discret">${LIBELLES_ETAT[k] || k}</span>`
                    + `<b>${valeurLisible(c[k])}</b></div>`).join("");
  const lignes = Object.entries(c)
    .filter(([k, v]) => !ETAT_CACHE.has(k) && v !== null && v !== "" && !(typeof v === "object"))
    .map(([k, v]) => `<tr><td>${LIBELLES_ETAT[k] || k}</td><td class="valeur">${typeof v === "number" ? fmt(v, 2) : v === true ? "oui" : v === false ? "non" : v}</td></tr>`);
  for (const k of ["niveau_voies", "voies_pression", "voies_niveau"]) {
    if (c[k]) lignes.push(`<tr><td>Voies de mesure</td><td class="valeur">${c[k].map(x => fmt(x, 1)).join(" / ")}</td></tr>`);
  }
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
    // conditions : détaillées seulement si l'une d'elles bloque (sinon une coche discrète)
    if (cmd.conditions.length) {
      const bloquee = cmd.conditions.some(c => !c.ok);
      if (bloquee) {
        const ul = el("ul");
        cmd.conditions.forEach(c => ul.appendChild(el("li", { class: c.ok ? "ok" : "ko" }, c.texte)));
        bloc.appendChild(ul);
      } else {
        bouton.title = cmd.conditions.map(c => `✓ ${c.texte}`).join("\n");
        ligne.appendChild(el("span", { class: "coche", title: bouton.title }, "✓"));
      }
    }
    zone.appendChild(bloc);
  });
}

function afficherReponse(msg) {
  PilotageCoeur.reponse(msg);
  const d = document.getElementById("eq-message");
  d.className = msg.ok ? "ok" : "ko";
  d.textContent = msg.ok ? `✓ ${msg.cible} : ${LIBELLES_ACTIONS[msg.action] || msg.action}`
                         : `✗ Refusé : ${msg.raisons.join(" ; ")}`;
  envoyer({ type: "conditions", cible: msg.cible });
}

// ============================================================================ onglets, sauvegarde
function ouvrirOnglet(nom) {
  document.querySelectorAll("#onglets [data-onglet]").forEach(x => x.classList.toggle("actif", x.dataset.onglet === nom));
  document.querySelectorAll(".onglet").forEach(o => o.classList.toggle("actif", o.id === `onglet-${nom}`));
  if (etat.dernier) majEtat(etat.dernier);
  if (nom === "courbes") Courbes.demander();
}
document.querySelectorAll("#onglets [data-onglet]").forEach(b => b.addEventListener("click", () => ouvrirOnglet(b.dataset.onglet)));
setInterval(() => {
  if (document.getElementById("onglet-courbes").classList.contains("actif")) Courbes.demander();
}, 1000);

document.getElementById("btn-acquitter-tout").onclick = () => envoyer({ type: "acquitter", id: null });
document.getElementById("btn-fermer-eq").onclick = deselectionner;
document.getElementById("btn-panneau").onclick = () => document.querySelector("main").classList.toggle("sans-panneau");
document.getElementById("etat-standard").onclick = ev => {
  ev.stopPropagation();
  const z = document.getElementById("etat-contenu");
  z.hidden = !z.hidden;
  if (etat.dernier) majEtats(etat.dernier.etats);
};
document.getElementById("btn-menu").onclick = ev => {
  ev.stopPropagation();
  const m = document.getElementById("menu-contenu");
  m.hidden = !m.hidden;
};
document.addEventListener("click", ev => {
  if (!ev.target.closest(".menu")) {
    document.getElementById("menu-contenu").hidden = true;
    document.getElementById("etat-contenu").hidden = true;
  }
});
document.addEventListener("keydown", ev => {
  if (ev.target.closest("input, select, textarea")) return;
  if (ev.key === " ") { ev.preventDefault(); envoyer({ type: "pause", valeur: !(etat.dernier && etat.dernier.pause) }); }
  if (ev.key === "Escape") deselectionner();
});

// ============================================================================ descriptions (glossaire)
// Après construction d'un synoptique : les équipements décrits perdent leur infobulle native (remplacée
// par une fiche riche), et chaque texte qui contient un sigle connu devient survolable.
function preparerDescriptions(svg) {
  svg.querySelectorAll("[data-id] > title").forEach(t => {
    if (Glossaire.fiche(t.parentNode.dataset.id)) t.remove();
  });
  svg.querySelectorAll("text").forEach(t => {
    if (t.closest("[data-id], [data-sigle], [data-info]") || t.dataset.mesure) return;
    const sigles = Glossaire.sigles(t.textContent);
    if (sigles.length) { t.dataset.sigle = sigles.join(" "); t.classList.add("texte-sigle"); }
  });
}

function contenuInfobulle(cible) {
  const id = cible.dataset.id;
  if (id && Glossaire.fiche(id)) {
    const c = etat.dernier && etat.dernier.composants[id];
    let etatTxt = "";
    if (c && c.en_marche !== undefined) etatTxt = c.en_marche ? "en marche" : (c.defaut ? `arrêtée (${c.defaut})` : "à l'arrêt");
    else if (c && c.position_pct !== undefined) etatTxt = `ouverte à ${fmt(c.position_pct, 0)} %` + (c.regulee ? (c.auto ? " · auto" : " · manuel") : "");
    return Glossaire.html(id, ` <span class="discret">(${id})</span>`)
      + (etatTxt ? `<div class="fiche-etat">${etatTxt}</div>` : "") + `<div class="discret petit">clic : commandes</div>`;
  }
  if (cible.dataset.info) return Glossaire.htmlInfo(cible.dataset.info);
  const sigles = (cible.dataset.sigle || "").split(" ").filter(Boolean);
  const html = sigles.map(sg => Glossaire.htmlSigle(sg)).join("");
  return html + (cible.dataset.lienOnglet ? `<div class="discret petit">clic : ouvrir l'onglet</div>` : "");
}

const infobulle = document.getElementById("infobulle");
document.addEventListener("mousemove", ev => {
  const cible = ev.target.closest && ev.target.closest(".synoptique [data-id], .synoptique [data-sigle], .synoptique [data-info]");
  const html = cible && !ev.buttons ? contenuInfobulle(cible) : "";
  if (!html) { infobulle.hidden = true; return; }
  const cle = cible.dataset.id || cible.dataset.info || cible.dataset.sigle;
  if (infobulle.dataset.cle !== cle) {
    infobulle.innerHTML = html;
    infobulle.dataset.cle = cle;
  }
  infobulle.hidden = false;
  const l = infobulle.offsetWidth, h = infobulle.offsetHeight;
  infobulle.style.left = `${Math.min(ev.clientX + 16, window.innerWidth - l - 8)}px`;
  infobulle.style.top = `${Math.min(ev.clientY + 16, window.innerHeight - h - 8)}px`;
});

// onglets : décomposition des sigles en infobulle
document.querySelectorAll("#onglets [data-onglet]").forEach(b => {
  const sigles = Glossaire.sigles(b.textContent);
  if (sigles.length) b.title = sigles.map(sg => `${sg} : ${Glossaire.SIGLES[sg].d.map(([l, s]) => `${l} = ${s}`).join(", ")}`).join("\n");
});

// glossaire complet
function afficherGlossaire() {
  const f = document.getElementById("filtre-glossaire").value.toLowerCase();
  const lignes = Object.entries(Glossaire.SIGLES)
    .filter(([k, s]) => !f || `${k} ${s.nom} ${s.role}`.toLowerCase().includes(f))
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, s]) => `<tr><td class="sigle-cle">${k}</td><td>${Glossaire.decomposition(k)}<div class="fiche-role">${s.nom} — ${s.role}</div></td></tr>`);
  document.getElementById("liste-glossaire").innerHTML = `<table class="table-glossaire">${lignes.join("")}</table>`;
}
document.getElementById("btn-formateur").onclick = () => {
  document.getElementById("menu-contenu").hidden = true;
  selectionner("FORMATEUR");
};
document.getElementById("btn-glossaire").onclick = () => {
  document.getElementById("menu-contenu").hidden = true;
  document.getElementById("vue-glossaire").hidden = false;
  afficherGlossaire();
  document.getElementById("filtre-glossaire").focus();
};
document.getElementById("filtre-glossaire").oninput = afficherGlossaire;
document.getElementById("btn-fermer-glossaire").onclick = () => { document.getElementById("vue-glossaire").hidden = true; };
document.addEventListener("keydown", ev => { if (ev.key === "Escape") document.getElementById("vue-glossaire").hidden = true; });

// double-clic sur un équipement : la cuve ouvre la vue du cœur, les autres équipements sont zoomés
function ouvrirDetail(svg, g) {
  if (g.dataset.id === "GRAPPES") { deselectionner(); ouvrirOnglet("coeur"); return; }
  const b = g.getBBox();
  Zoom.centrer(svg, b.x + b.width / 2, b.y + b.height / 2, 2.5);
}
document.getElementById("btn-sauver").onclick = () => envoyer({ type: "exporter" });
document.getElementById("btn-charger").onclick = () => document.getElementById("fichier").click();
document.getElementById("fichier").onchange = async ev => {
  const f = ev.target.files[0];
  if (!f) return;
  try {
    envoyer({ type: "importer", donnees: JSON.parse(await f.text()) });
  } catch (err) {
    alert(`Fichier illisible : ${err.message}`);
  }
  ev.target.value = "";
};
document.getElementById("btn-scenario").onclick = () => {
  const id = document.getElementById("choix-scenario").value;
  if (confirm(`Charger le scénario « ${id} » ? L'état actuel sera perdu (pensez à sauvegarder).`))
    envoyer({ type: "scenario", id });
};

etat.transport = creerTransport(surMessage, surStatut);
