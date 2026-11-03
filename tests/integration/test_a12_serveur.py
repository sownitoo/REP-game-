"""A12 : serveur web — page, WebSocket (état, commandes, conditions), sauvegarde, historique."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from sim.server import creer_app

MESSAGES_MAX = 200


def attendre(ws: Any, genre: str) -> dict[str, Any]:
    """Lit les messages jusqu'à en trouver un du type voulu (l'état est diffusé en continu)."""
    for _ in range(MESSAGES_MAX):
        msg = ws.receive_json()
        if msg["type"] == genre:
            return msg
    raise AssertionError(f"pas de message « {genre} »")


def test_a12_serveur_websocket_et_api() -> None:
    with TestClient(creer_app()) as client:
        assert client.get("/").status_code == 200
        assert client.get("/app.js").status_code == 200
        assert "serveur" in client.get("/mode.js").text          # le mode serveur prime sur web/mode.js
        with client.websocket_connect("/ws") as ws:
            init = ws.receive_json()
            assert init["type"] == "init"
            assert "GV1.niveau_pct" in init["variables"]
            assert init["etat"]["composants"]["APP1"]["en_marche"]

            ws.send_json({"type": "commande", "cible": "TURBINE", "action": "coupler"})
            rep = attendre(ws, "reponse")
            assert not rep["ok"] and rep["raisons"], "un refus doit dire pourquoi"

            ws.send_json({"type": "commande", "cible": "CEX1", "action": "arreter"})
            assert attendre(ws, "reponse")["ok"]

            ws.send_json({"type": "conditions", "cible": "CEX1"})
            cond = attendre(ws, "conditions")
            demarrer = next(c for c in cond["commandes"] if c["action"] == "demarrer")
            assert demarrer["conditions"] and all("texte" in c and "ok" in c for c in demarrer["conditions"])

            ws.send_json({"type": "historique", "vars": ["GV1.p_bar"]})
            assert "t_s" in attendre(ws, "historique")["series"]
            ws.send_json({"type": "acceleration", "valeur": 10})
            etat = attendre(ws, "etat")
            assert "mesures" in etat and "alarmes" in etat and etat["etat_standard"]

        sauvegarde = client.get("/api/sauvegarde").json()
        assert client.post("/api/chargement", json=sauvegarde).json()["ok"]
        assert client.post("/api/chargement", json={"version": 999}).status_code == 400
        assert "t_s" in client.get("/api/historique?vars=GV1.p_bar").json()
        assert client.post("/api/scenario/s0_bac_a_sable_100").json()["ok"]
        assert client.post("/api/scenario/inexistant").status_code == 404
