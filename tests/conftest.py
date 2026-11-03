"""Fixtures communes."""

from __future__ import annotations

import pytest

from sim.config import CentraleCfg, charger_config
from sim.plant import Centrale
from sim.scenarios.chargement import centrale_depuis_etat
from sim.thermo.tables import TableEau, obtenir_table


@pytest.fixture(scope="session")
def cfg() -> CentraleCfg:
    return charger_config()


@pytest.fixture(scope="session")
def table(cfg: CentraleCfg) -> TableEau:
    n = cfg.numerique
    return obtenir_table(n.table_p_min_bar, n.table_p_max_bar, n.table_nb_points, n.table_t_pas_c,
                                   n.table_p_liquide_bar)


@pytest.fixture
def rp100() -> Centrale:
    """Centrale neuve dans l'état stabilisé RP 100 %."""
    return centrale_depuis_etat("rp100")


def serie(c: Centrale, duree_s: float, pas_s: float, *mesures: str) -> list[dict[str, float]]:
    """Avance de `duree_s` et relève les mesures demandées tous les `pas_s`."""
    sortie = []
    for _ in range(round(duree_s / pas_s)):
        c.avancer(pas_s)
        sortie.append({"t_s": c.t_s, **{m: c.mesures[m] for m in mesures}})
    return sortie
