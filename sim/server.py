"""Serveur web du simulateur : FastAPI + WebSocket + page HTML/SVG/JS.

Lancement : python -m sim.server   puis ouvrir http://localhost:8000
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from sim.config import RACINE
from sim.core.engine import Simulateur
from sim.plant import Centrale
from sim.scenarios.chargement import centrale_scenario, lister_scenarios

DOSSIER_WEB = RACINE / "web"
SCENARIO_DEFAUT = "s0_bac_a_sable_100"
HOTE_DEFAUT = "127.0.0.1"
PORT_DEFAUT = 8000
NB_EVENEMENTS_DIFFUSES = 60


def etat_standard(c: Centrale) -> str:
    """État standard du réacteur (V0 : RP ou AN/GV)."""
    if c.logique.etat.au:
        return "AN/GV — arrêt à chaud sur GV"
    return "RP — en production" if c.turbine.etat.couplee else "RP — turbine découplée"


def etat_ui(c: Centrale, sim: Simulateur) -> dict[str, Any]:
    composants = {k: o.etat_ui() for k, o in c.commandables.items()}
    composants.update({gv.id: gv.etat_ui() for gv in c.gvs})
    composants.update(c.vapeur.etats_ui())
    composants.update({k: o.etat_ui() for k, o in c.composants.items() if k not in composants})
    composants[c.condenseur.id] = c.condenseur.etat_ui()
    lg = c.logique.etat
    return {
        "type": "etat",
        "t_s": c.t_s,
        "acceleration": sim.acceleration,
        "acceleration_reelle": sim.acceleration_reelle,
        "pause": sim.pause,
        "scenario": sim.scenario,
        "etat_standard": etat_standard(c),
        "mesures": c.mesures,
        "composants": composants,
        "logique": {
            "au": lg.au, "au_causes": lg.au_causes, "causes_au": lg.causes_au, "p4": lg.p4, "p7": lg.p7,
            "p14": lg.p14, "p14_gv": lg.p14_gv, "niveau_tres_bas_gv": lg.niveau_tres_bas_gv, "c9": lg.c9,
            "causes_turbine": lg.causes_turbine, "isolement_are_au": lg.isolement_are_au,
            "isolement_are_complet": lg.isolement_are_complet, "recirc_cex": lg.recirc_cex,
        },
        "alarmes": c.alarmes.liste(),
        "journal": c.journal.derniers(NB_EVENEMENTS_DIFFUSES),
    }


def message_init(c: Centrale, sim: Simulateur) -> dict[str, Any]:
    cfg = c.cfg
    lg, gv = cfg.logique, cfg.generateurs_vapeur.seuils
    return {
        "type": "init",
        "meta": {"version": cfg.meta.version, "nom": cfg.meta.nom},
        "accelerations": cfg.simulation.accelerations,
        "variables": sorted(c.mesures),
        "scenarios": [{"id": s.id, "titre": s.titre, "description": s.description} for s in lister_scenarios()],
        "seuils": {
            "P-7": f"puissance < {lg.p7.puissance_max_pct:g} % ET charge turbine < {lg.p7.charge_turbine_max_pct:g} %",
            "P-14": f"niveau GV > {gv.tres_haut_pct:g} % ({gv.vote} sur 1 GV)",
            "C-9": (f"≥ {lg.c9.crf_mini} pompe CRF ET P condenseur < {lg.c9.p_cond_max_bar:g} bar "
                    f"(perdu à {lg.c9.p_cond_perte_bar:g} bar)"),
            "AU niveau GV très bas": f"niveau GV < {gv.tres_bas_pct:g} % ({gv.vote} sur 1 GV)",
            "AU déclenchement turbine": "4/4 vannes d'arrêt fermées, au-dessus de P-7",
            "Isolement ARE GD": f"AU (P-4) ET Tmoy < {lg.isolement_are_au.tmoy_max_c:g} °C",
            "Isolement ARE complet": "P-14 (mémorisé, réarmement opérateur)",
            "Déclenchement turbine": (f"P-4, P-14, P condenseur > {lg.declenchement_turbine.p_cond_max_bar:g} bar, "
                                      f"survitesse > {lg.declenchement_turbine.survitesse_pct:g} %"),
            "Déclenchement APP": (f"P-14, aspiration < {lg.declenchement_app.p_aspiration_min_bar:g} bar "
                                  f"({lg.declenchement_app.temporisation_s:g} s), "
                                  f"refoulement > {lg.declenchement_app.p_refoulement_max_bar:g} bar"),
        },
        "etat": etat_ui(c, sim),
    }


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
    centrale = centrale_scenario(SCENARIO_DEFAUT)
    simulateur = Simulateur(centrale, centrale.cfg.simulation)
    simulateur.scenario = SCENARIO_DEFAUT
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
    app.mount("/web", StaticFiles(directory=DOSSIER_WEB), name="web")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(DOSSIER_WEB / "index.html")

    @app.get("/api/historique")
    def historique(vars: str = "") -> dict[str, list[float]]:
        noms = [v for v in vars.split(",") if v]
        return simulateur.centrale.historique.series(noms)

    @app.get("/api/sauvegarde")
    def sauvegarde() -> JSONResponse:
        c = simulateur.centrale
        nom = f"centrale_t{int(c.t_s)}s.json"
        return JSONResponse(c.exporter(), headers={"Content-Disposition": f'attachment; filename="{nom}"'})

    @app.post("/api/chargement")
    async def chargement(requete: Request) -> dict[str, Any]:
        donnees = await requete.json()
        c = Centrale()
        try:
            c.importer(donnees)
        except (KeyError, TypeError, ValueError) as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Sauvegarde invalide : {e}") from e
        simulateur.remplacer(c, "sauvegarde chargée")
        return {"ok": True, "t_s": c.t_s}

    @app.post("/api/scenario/{id_scenario}")
    def scenario(id_scenario: str) -> dict[str, Any]:
        if id_scenario not in {s.id for s in lister_scenarios()}:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scénario inconnu")
        simulateur.remplacer(centrale_scenario(id_scenario), id_scenario)
        return {"ok": True}

    @app.websocket("/ws")
    async def ws(socket: WebSocket) -> None:
        await socket.accept()
        diffuseur.clients.add(socket)
        await socket.send_text(json.dumps(message_init(simulateur.centrale, simulateur), ensure_ascii=False))
        try:
            while True:
                msg = json.loads(await socket.receive_text())
                reponse = traiter_message(simulateur, msg)
                if reponse is not None:
                    await socket.send_text(json.dumps(reponse, ensure_ascii=False))
        except WebSocketDisconnect:
            diffuseur.clients.discard(socket)

    return app


def traiter_message(sim: Simulateur, msg: dict[str, Any]) -> dict[str, Any] | None:
    """Traite un message du navigateur ; renvoie la réponse éventuelle."""
    c = sim.centrale
    genre = msg.get("type")
    if genre == "commande":
        valeur = msg.get("valeur")
        valeur = float(valeur) if valeur is not None and valeur != "" else None
        r = c.commande(str(msg.get("cible")), str(msg.get("action")), valeur)
        return {"type": "reponse", "cible": msg.get("cible"), "action": msg.get("action"),
                "ok": r.ok, "raisons": r.raisons}
    if genre == "conditions":
        cible = str(msg.get("cible"))
        if cible not in c.commandables:
            return {"type": "conditions", "cible": cible, "commandes": []}
        return {"type": "conditions", "cible": cible, "commandes": c.liste_commandes(cible)}
    if genre == "acceleration":
        valeur = int(msg.get("valeur", 1))
        if valeur in sim.cfg.accelerations:
            sim.acceleration = valeur
            sim.pause = False
        return None
    if genre == "pause":
        sim.pause = bool(msg.get("valeur", True))
        return None
    if genre == "acquitter":
        c.alarmes.acquitter(msg.get("id"))
        return None
    return {"type": "erreur", "texte": f"message inconnu : {genre}"}


app = creer_app()


def main() -> None:
    import uvicorn

    hote = os.environ.get("REP_HOTE", HOTE_DEFAUT)
    port = int(os.environ.get("REP_PORT", PORT_DEFAUT))
    print(f"Mini-Centrale REP : ouvrir http://{hote}:{port}")
    uvicorn.run(app, host=hote, port=port, log_level="warning")


if __name__ == "__main__":
    main()
