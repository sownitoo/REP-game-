// Web Worker du mode navigateur : Python (Pyodide) fait tourner sim/ sans aucun serveur.
// Le paquet web/sim_bundle.zip (code + config) est généré par `python -m sim.tools.paquet_web`.
const VERSION_PYODIDE = "314.0.7";
const params = new URLSearchParams(self.location.search);
const URL_PYODIDE = params.get("pyodide") || `https://cdn.jsdelivr.net/npm/pyodide@${VERSION_PYODIDE}/`;

let py = null;          // module Python sim.navigateur
let tampon = [];        // messages reçus avant la fin du chargement

function statut(texte) { postMessage({ type: "statut", texte }); }

async function demarrer() {
  statut("Téléchargement de Python (Pyodide)…");
  const { loadPyodide } = await import(`${URL_PYODIDE}pyodide.mjs`);
  const pyodide = await loadPyodide({ indexURL: URL_PYODIDE });
  statut("Chargement du simulateur…");
  const paquet = await fetch(new URL("sim_bundle.zip", self.location.href));
  if (!paquet.ok) throw new Error(`sim_bundle.zip introuvable (${paquet.status})`);
  pyodide.unpackArchive(await paquet.arrayBuffer(), "zip", { extractDir: "/home/pyodide/rep" });
  pyodide.runPython("import sys; sys.path.insert(0, '/home/pyodide/rep')");
  py = pyodide.pyimport("sim.navigateur");
  statut("Calcul de l'état initial…");
  postMessage(JSON.parse(py.init()));
  const periodes = JSON.parse(py.periodes());
  let derniereDiffusion = 0;
  setInterval(() => {
    py.tick(periodes.tick_s);
    const maintenant = performance.now() / 1000;
    if (maintenant - derniereDiffusion >= periodes.diffusion_s) {
      derniereDiffusion = maintenant;
      postMessage(JSON.parse(py.etat()));
    }
  }, periodes.tick_s * 1000);
  tampon.forEach(traiter);
  tampon = [];
}

function traiter(msg) {
  const reponse = py.message(JSON.stringify(msg));
  if (reponse) postMessage(JSON.parse(reponse));
}

self.onmessage = ev => (py ? traiter(ev.data) : tampon.push(ev.data));

demarrer().catch(err => statut(`Échec du démarrage : ${err.message || err}`));
