// Transport entre l'interface et le simulateur, même protocole dans les deux modes :
// - « serveur » : WebSocket vers `python -m sim.server` ;
// - « navigateur » : Web Worker qui fait tourner Python (Pyodide) — hébergement statique (Vercel).
"use strict";

class TransportWebSocket {
  constructor(surMessage, surStatut) {
    this.surMessage = surMessage;
    this.surStatut = surStatut;
    this.connecter();
  }
  connecter() {
    const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
    this.ws = ws;
    ws.onmessage = ev => this.surMessage(JSON.parse(ev.data));
    ws.onclose = () => { this.surStatut("Connexion perdue, reconnexion…"); setTimeout(() => this.connecter(), 1000); };
  }
  envoyer(msg) { if (this.ws && this.ws.readyState === 1) this.ws.send(JSON.stringify(msg)); }
}

class TransportWorker {
  constructor(surMessage, surStatut) {
    // le paramètre d'URL ?pyodide=… permet de servir Pyodide localement (tests hors ligne)
    this.worker = new Worker(`worker.js${location.search}`, { type: "module" });
    this.worker.onmessage = ev => {
      const msg = ev.data;
      if (msg.type === "statut") surStatut(msg.texte);
      else surMessage(msg);
    };
    this.worker.onerror = ev => surStatut(`Erreur du simulateur : ${ev.message}`);
  }
  envoyer(msg) { this.worker.postMessage(msg); }
}

function creerTransport(surMessage, surStatut) {
  return window.REP_MODE === "serveur"
    ? new TransportWebSocket(surMessage, surStatut)
    : new TransportWorker(surMessage, surStatut);
}
