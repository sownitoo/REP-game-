"""Constantes physiques et conversions d'unités.

Ce module ne contient AUCUNE donnée de la centrale (elles sont toutes dans
config/plant.yaml) : seulement des constantes universelles et des facteurs
de conversion.
"""

from __future__ import annotations

G_M_S2 = 9.80665            # accélération de la pesanteur
ZERO_C_K = 273.15           # 0 °C en kelvins
PA_PAR_BAR = 1.0e5
J_PAR_KJ = 1.0e3
KJ_PAR_MJ = 1.0e3
KG_PAR_T = 1.0e3
KW_PAR_MW = 1.0e3
S_PAR_H = 3600.0
S_PAR_MIN = 60.0
RHO_REF_KG_M3 = 1000.0      # densité de référence de la définition du Kv
POURCENT = 100.0


def m3h_vers_kg_s(q_m3h: float, rho_kg_m3: float) -> float:
    """Débit volumique (m³/h) → débit massique (kg/s)."""
    return q_m3h * rho_kg_m3 / S_PAR_H


def kg_s_vers_m3h(qm_kg_s: float, rho_kg_m3: float) -> float:
    """Débit massique (kg/s) → débit volumique (m³/h)."""
    return qm_kg_s * S_PAR_H / rho_kg_m3


def hauteur_vers_bar(h_m: float, rho_kg_m3: float) -> float:
    """Hauteur de colonne de liquide (m) → pression (bar)."""
    return rho_kg_m3 * G_M_S2 * h_m / PA_PAR_BAR


def interp_table(table: list[list[float]], x: float) -> float:
    """Interpolation linéaire dans une table [[x0, y0], [x1, y1], …] (bornée aux extrémités)."""
    if x <= table[0][0]:
        return table[0][1]
    for (x0, y0), (x1, y1) in zip(table, table[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return table[-1][1]


def borner(x: float, x_min: float, x_max: float) -> float:
    """Limite x à l'intervalle [x_min, x_max]."""
    return x_min if x < x_min else x_max if x > x_max else x
