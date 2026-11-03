// Mode d'exécution de la simulation. Ce fichier statique sert au déploiement sans serveur
// (Vercel) : la simulation tourne dans le navigateur (Pyodide, web/worker.js).
// En local, `python -m sim.server` remplace ce fichier et passe en mode « serveur » (WebSocket).
window.REP_MODE = "navigateur";
