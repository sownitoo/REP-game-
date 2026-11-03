// Géométrie du cœur (vue de dessus), partagée par le synoptique primaire et la vue cœur.
// Cœur générique de 193 assemblages (grille 15 × 15 sans les coins), comme un REP 4 boucles.
// Grappes sur une maille paire : R = groupe de régulation, S = groupes d'arrêt, G = groupes de compensation.
"use strict";

const CoeurGeo = (() => {
  const LARGEURS = [7, 11, 13, 13, 15, 15, 15, 15, 15, 15, 15, 13, 13, 11, 7];   // assemblages par rangée
  const N = LARGEURS.length, MILIEU = (N - 1) / 2;
  const assemblages = [];
  LARGEURS.forEach((l, j) => {
    const debut = (N - l) / 2;
    for (let i = debut; i < debut + l; i++) assemblages.push({ i, j, dx: i - MILIEU, dy: j - MILIEU });
  });
  const dedans = (dx, dy) => assemblages.some(a => a.dx === dx && a.dy === dy);
  const R = new Set(["0,0", "4,0", "-4,0", "0,4", "0,-4", "4,4", "4,-4", "-4,4", "-4,-4"]);
  const grappes = [];
  for (let dx = -6; dx <= 6; dx += 2) {
    for (let dy = -6; dy <= 6; dy += 2) {
      if (!dedans(dx, dy)) continue;
      const cle = `${dx},${dy}`;
      const groupe = R.has(cle) ? "R" : ((dx + dy) / 2) % 2 === 0 ? "S" : "G";
      grappes.push({ dx, dy, groupe });
    }
  }
  return { N, MILIEU, assemblages, grappes };
})();
