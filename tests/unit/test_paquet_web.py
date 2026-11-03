"""Le paquet du mode navigateur (web/sim_bundle.zip) doit correspondre au code et à la config."""

from __future__ import annotations

import io
import json
import zipfile

from sim.tools.paquet_web import CHEMIN_PAQUET, construire


def test_paquet_web_a_jour() -> None:
    assert CHEMIN_PAQUET.exists(), "lancer : python -m sim.tools.paquet_web"
    assert CHEMIN_PAQUET.read_bytes() == construire(), "paquet périmé : relancer python -m sim.tools.paquet_web"


def test_paquet_web_contenu() -> None:
    with zipfile.ZipFile(io.BytesIO(construire())) as z:
        noms = set(z.namelist())
        assert {"sim/navigateur.py", "sim/plant.py", "config/plant.json", "config/tables_eau.json",
                "config/etats/rp100.json", "sim/scenarios/s0_bac_a_sable_100.json"} <= noms
        assert "sim/server.py" not in noms
        assert json.loads(z.read("config/plant.json"))["meta"]["version"]
