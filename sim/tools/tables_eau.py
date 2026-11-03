"""Régénère config/tables_eau.json avec CoolProp (à relancer si les paramètres numériques changent).

Usage : python -m sim.tools.tables_eau
"""

from __future__ import annotations

import json

from sim.config import charger_config
from sim.thermo.tables import CHEMIN_TABLES, calculer_tables

OCTETS_PAR_KO = 1024


def main() -> None:
    n = charger_config().numerique
    donnees = calculer_tables((n.table_p_min_bar, n.table_p_max_bar, n.table_nb_points, n.table_t_pas_c,
                               n.table_p_liquide_bar))
    CHEMIN_TABLES.write_text(json.dumps(donnees, separators=(",", ":")), encoding="utf-8")
    print(f"Tables écrites : {CHEMIN_TABLES} ({CHEMIN_TABLES.stat().st_size // OCTETS_PAR_KO} ko)")


if __name__ == "__main__":
    main()
