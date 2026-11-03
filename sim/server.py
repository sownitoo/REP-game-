"""Serveur web du simulateur (mode serveur) : FastAPI + WebSocket + page HTML/SVG/JS.

Lancement : python -m sim.server   puis ouvrir http://localhost:8000
(Le même site peut aussi tourner sans serveur, simulation dans le navigateur : voir sim/navigateur.py.)
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from sim.config import RACINE
from sim.interface import creer_simulateur, etat_ui, message_init, traiter_message
from sim.scenarios.chargement import lister_scenarios

DOSSIER_WEB = RACINE / "web"
HOTE_DEFAUT = "127.0.0.1"
PORT_DEFAUT = 8000


class Diffuseur:
    """Liste des clients WebSocket connectés."""

    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()

    async def envoyer_a_tous(self, message: dict[str, Any]) -> None:
        texte = json.dumps(message, ensure_ascii=False)
        for ws in list(self.clients):
            try:
                await ws.send_text(texte)
            except (WebSocketDisconnect, RuntimeError):
                self.clients.discard(ws)


def creer_app() -> FastAPI:
    simulateur = creer_simulateur()
    diffuseur = Diffuseur()
    cfg_sim = simulateur.cfg

    async def boucle() -> None:
        derniere_diffusion = 0.0
        horloge = asyncio.get_running_loop().time
        while True:
            debut = horloge()
            simulateur.tick(cfg_sim.tick_reel_s)
            if debut - derniere_diffusion >= cfg_sim.diffusion_periode_s and diffuseur.clients:
                derniere_diffusion = debut
                await diffuseur.envoyer_a_tous(etat_ui(simulateur.centrale, simulateur))
            await asyncio.sleep(max(0.0, cfg_sim.tick_reel_s - (horloge() - debut)))

    @contextlib.asynccontextmanager
    async def cycle_de_vie(_: FastAPI) -> AsyncIterator[None]:
        tache = asyncio.create_task(boucle())
        yield
        tache.cancel()

    app = FastAPI(title="Mini-Centrale REP", lifespan=cycle_de_vie)
    app.state.simulateur = simulateur

    @app.get("/mode.js")
    def mode() -> Response:
        """En mode serveur, la page dialogue par WebSocket (le fichier statique web/mode.js dit « navigateur »)."""
        return Response('window.REP_MODE = "serveur";\n', media_type="text/javascript")

    @app.get("/api/historique")
    def historique(vars: str = "") -> dict[str, list[float]]:
        return simulateur.centrale.historique.series([v for v in vars.split(",") if v])

    @app.get("/api/sauvegarde")
    def sauvegarde() -> JSONResponse:
        c = simulateur.centrale
        nom = f"centrale_t{int(c.t_s)}s.json"
        return JSONResponse(c.exporter(), headers={"Content-Disposition": f'attachment; filename="{nom}"'})

    @app.post("/api/chargement")
    async def chargement(requete: Request) -> dict[str, Any]:
        r = traiter_message(simulateur, {"type": "importer", "donnees": await requete.json()}) or {}
        if not r.get("ok"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=r.get("erreur"))
        return {"ok": True, "t_s": r["t_s"]}

    @app.post("/api/scenario/{id_scenario}")
    def scenario(id_scenario: str) -> dict[str, Any]:
        if id_scenario not in {s.id for s in lister_scenarios()}:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scénario inconnu")
        traiter_message(simulateur, {"type": "scenario", "id": id_scenario})
        return {"ok": True}

    @app.websocket("/ws")
    async def ws(socket: WebSocket) -> None:
        await socket.accept()
        diffuseur.clients.add(socket)
        await socket.send_text(json.dumps(message_init(simulateur.centrale, simulateur), ensure_ascii=False))
        try:
            while True:
                reponse = traiter_message(simulateur, json.loads(await socket.receive_text()))
                if reponse is not None:
                    await socket.send_text(json.dumps(reponse, ensure_ascii=False))
        except WebSocketDisconnect:
            diffuseur.clients.discard(socket)

    app.mount("/", StaticFiles(directory=DOSSIER_WEB, html=True), name="web")
    return app


app = creer_app()


def main() -> None:
    import uvicorn

    hote = os.environ.get("REP_HOTE", HOTE_DEFAUT)
    port = int(os.environ.get("REP_PORT", PORT_DEFAUT))
    print(f"Mini-Centrale REP : ouvrir http://{hote}:{port}")
    uvicorn.run(app, host=hote, port=port, log_level="warning")


if __name__ == "__main__":
    main()
