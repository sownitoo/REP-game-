"""Tables eau/vapeur pré-calculées avec CoolProp (IAPWS-IF97) et interpolation rapide.

Un appel CoolProp direct coûte trop cher pour tourner à ×60 : on calcule une
fois des tables (grille uniforme en ln P et en T), puis on interpole
linéairement (accès en O(1), sans recherche).

Les tables sont enregistrées dans config/tables_eau.json : le simulateur n'a
donc pas besoin de CoolProp pour tourner (indispensable dans le navigateur).
Régénération : python -m sim.tools.tables_eau
"""

from __future__ import annotations

import bisect
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from sim.units import J_PAR_KJ, PA_PAR_BAR, ZERO_C_K

CHEMIN_TABLES = Path(__file__).resolve().parent.parent.parent / "config" / "tables_eau.json"
CHIFFRES_SIGNIFICATIFS = 12


@dataclass(frozen=True)
class Saturation:
    """Propriétés de saturation à une pression donnée."""

    p_bar: float
    t_c: float
    hf_kj_kg: float
    hg_kj_kg: float
    vf_m3_kg: float
    vg_m3_kg: float
    uf_kj_kg: float
    ug_kj_kg: float
    sf_kj_kgk: float
    sg_kj_kgk: float

    @property
    def hfg_kj_kg(self) -> float:
        return self.hg_kj_kg - self.hf_kj_kg

    @property
    def rho_l_kg_m3(self) -> float:
        return 1.0 / self.vf_m3_kg

    @property
    def rho_v_kg_m3(self) -> float:
        return 1.0 / self.vg_m3_kg


_COLONNES_P = ("t", "hf", "hg", "vf", "vg", "uf", "ug", "sf", "sg")
Parametres = tuple[float, float, int, float, float]   # p_min, p_max, nb points, pas T, P du liquide primaire


def calculer_tables(parametres: Parametres) -> dict[str, Any]:
    """Calcule toutes les colonnes avec CoolProp (IF97)."""
    import CoolProp.CoolProp as CP
    from CoolProp import AbstractState

    p_min_bar, p_max_bar, nb_points, t_pas_c, p_liq_bar = parametres
    etat = AbstractState("IF97", "Water")
    ln_p0 = math.log(p_min_bar)
    dln = (math.log(p_max_bar) - ln_p0) / (nb_points - 1)
    col: dict[str, list[float]] = {k: [] for k in _COLONNES_P}
    for i in range(nb_points):
        p_pa = math.exp(ln_p0 + i * dln) * PA_PAR_BAR
        for titre, suffixe in ((0.0, "f"), (1.0, "g")):
            etat.update(CP.PQ_INPUTS, p_pa, titre)
            col["h" + suffixe].append(etat.hmass() / J_PAR_KJ)
            col["v" + suffixe].append(1.0 / etat.rhomass())
            col["u" + suffixe].append(etat.umass() / J_PAR_KJ)
            col["s" + suffixe].append(etat.smass() / J_PAR_KJ)
        col["t"].append(etat.T() - ZERO_C_K)
    # liquide saturé en fonction de T
    t_min, t_max = col["t"][0], col["t"][-1]
    sat_t: dict[str, list[float]] = {"p": [], "h": [], "rho": []}
    for j in range(int((t_max - t_min) / t_pas_c) + 1):
        etat.update(CP.QT_INPUTS, 0.0, t_min + j * t_pas_c + ZERO_C_K)
        sat_t["p"].append(etat.p() / PA_PAR_BAR)
        sat_t["h"].append(etat.hmass() / J_PAR_KJ)
        sat_t["rho"].append(etat.rhomass())
    # liquide comprimé à la pression du primaire, jusqu'à la saturation
    etat.update(CP.PQ_INPUTS, p_liq_bar * PA_PAR_BAR, 0.0)
    t_sat_liq = etat.T() - ZERO_C_K
    liq: dict[str, list[float]] = {"h": [], "rho": []}
    for j in range(int((t_sat_liq - t_min) / t_pas_c)):
        etat.update(CP.PT_INPUTS, p_liq_bar * PA_PAR_BAR, t_min + j * t_pas_c + ZERO_C_K)
        liq["h"].append(etat.hmass() / J_PAR_KJ)
        liq["rho"].append(etat.rhomass())

    def arrondir(d: dict[str, list[float]]) -> dict[str, list[float]]:
        return {k: [float(f"{x:.{CHIFFRES_SIGNIFICATIFS}g}") for x in v] for k, v in d.items()}

    return {"parametres": list(parametres), "saturation_p": arrondir(col),
            "saturation_t": arrondir(sat_t), "liquide_p": arrondir(liq)}


class TableEau:
    """Tables de saturation (grille en ln P), liquide saturé (grille en T) et liquide
    comprimé à la pression du primaire (grille en T)."""

    def __init__(self, donnees: dict[str, Any]) -> None:
        p_min_bar, p_max_bar, nb_points, t_pas_c, p_liq_bar = donnees["parametres"]
        self.parametres: Parametres = (p_min_bar, p_max_bar, int(nb_points), t_pas_c, p_liq_bar)
        self.p_min_bar = p_min_bar
        self.p_max_bar = p_max_bar
        self.p_liquide_bar = p_liq_bar
        self._ln_p0 = math.log(p_min_bar)
        self._dln = (math.log(p_max_bar) - self._ln_p0) / (nb_points - 1)
        self._n = int(nb_points)
        self._col: dict[str, list[float]] = donnees["saturation_p"]
        self.t_min_c = self._col["t"][0]
        self.t_max_c = self._col["t"][-1]
        self._t_pas = t_pas_c
        self._t_p: list[float] = donnees["saturation_t"]["p"]
        self._t_h: list[float] = donnees["saturation_t"]["h"]
        self._t_rho: list[float] = donnees["saturation_t"]["rho"]
        self._l_h: list[float] = donnees["liquide_p"]["h"]
        self._l_rho: list[float] = donnees["liquide_p"]["rho"]
        self.t_max_liquide_c = self.t_min_c + (len(self._l_h) - 1) * t_pas_c

    # ------------------------------------------------------------------ saturation(P)
    def _index_p(self, p_bar: float) -> tuple[int, float]:
        p = min(max(p_bar, self.p_min_bar), self.p_max_bar)
        r = (math.log(p) - self._ln_p0) / self._dln
        i = min(int(r), self._n - 2)
        return i, r - i

    def _val_p(self, nom: str, i: int, w: float) -> float:
        c = self._col[nom]
        return c[i] + w * (c[i + 1] - c[i])

    def sat(self, p_bar: float) -> Saturation:
        """Propriétés de saturation à p_bar (bornée à la plage de la table)."""
        i, w = self._index_p(p_bar)
        c = self._col
        return Saturation(
            p_bar=p_bar,
            t_c=c["t"][i] + w * (c["t"][i + 1] - c["t"][i]),
            hf_kj_kg=c["hf"][i] + w * (c["hf"][i + 1] - c["hf"][i]),
            hg_kj_kg=c["hg"][i] + w * (c["hg"][i + 1] - c["hg"][i]),
            vf_m3_kg=c["vf"][i] + w * (c["vf"][i + 1] - c["vf"][i]),
            vg_m3_kg=c["vg"][i] + w * (c["vg"][i + 1] - c["vg"][i]),
            uf_kj_kg=c["uf"][i] + w * (c["uf"][i + 1] - c["uf"][i]),
            ug_kj_kg=c["ug"][i] + w * (c["ug"][i + 1] - c["ug"][i]),
            sf_kj_kgk=c["sf"][i] + w * (c["sf"][i + 1] - c["sf"][i]),
            sg_kj_kgk=c["sg"][i] + w * (c["sg"][i + 1] - c["sg"][i]),
        )

    def tsat_c(self, p_bar: float) -> float:
        i, w = self._index_p(p_bar)
        return self._val_p("t", i, w)

    def hg_kj_kg(self, p_bar: float) -> float:
        i, w = self._index_p(p_bar)
        return self._val_p("hg", i, w)

    def dhf_dp_kj_kg_bar(self, p_bar: float) -> float:
        """Pente dhf/dP du liquide saturé (pente de la maille de table)."""
        i, _ = self._index_p(p_bar)
        p0 = math.exp(self._ln_p0 + i * self._dln)
        p1 = math.exp(self._ln_p0 + (i + 1) * self._dln)
        return (self._col["hf"][i + 1] - self._col["hf"][i]) / (p1 - p0)

    def rho_v_kg_m3(self, p_bar: float) -> float:
        i, w = self._index_p(p_bar)
        return 1.0 / self._val_p("vg", i, w)

    # ------------------------------------------------------------------ liquide(T)
    def _index_t(self, t_c: float) -> tuple[int, float]:
        t = min(max(t_c, self.t_min_c), self.t_max_c)
        r = (t - self.t_min_c) / self._t_pas
        i = min(int(r), len(self._t_p) - 2)
        return i, r - i

    def psat_bar(self, t_c: float) -> float:
        """Pression de saturation à t_c."""
        i, w = self._index_t(t_c)
        return self._t_p[i] + w * (self._t_p[i + 1] - self._t_p[i])

    def h_liq_kj_kg(self, t_c: float) -> float:
        """Enthalpie de l'eau liquide à t_c (approximée par le liquide saturé)."""
        i, w = self._index_t(t_c)
        return self._t_h[i] + w * (self._t_h[i + 1] - self._t_h[i])

    def rho_liq_kg_m3(self, t_c: float) -> float:
        """Masse volumique de l'eau liquide à t_c (approximée par le liquide saturé)."""
        i, w = self._index_t(t_c)
        return self._t_rho[i] + w * (self._t_rho[i + 1] - self._t_rho[i])

    def t_liq_c(self, h_kj_kg: float) -> float:
        """Température de l'eau liquide d'enthalpie h (inverse de h_liq_kj_kg)."""
        j = bisect.bisect_left(self._t_h, h_kj_kg)
        j = min(max(j, 1), len(self._t_h) - 1)
        h0, h1 = self._t_h[j - 1], self._t_h[j]
        w = (h_kj_kg - h0) / (h1 - h0)
        return self.t_min_c + (j - 1 + w) * self._t_pas

    # ------------------------------------------------------------------ liquide primaire(T)
    def _index_l(self, t_c: float) -> tuple[int, float]:
        t = min(max(t_c, self.t_min_c), self.t_max_liquide_c)
        r = (t - self.t_min_c) / self._t_pas
        i = min(int(r), len(self._l_h) - 2)
        return i, r - i

    def h_primaire_kj_kg(self, t_c: float) -> float:
        """Enthalpie de l'eau du primaire (liquide comprimé à la pression nominale)."""
        i, w = self._index_l(t_c)
        return self._l_h[i] + w * (self._l_h[i + 1] - self._l_h[i])

    def rho_primaire_kg_m3(self, t_c: float) -> float:
        i, w = self._index_l(t_c)
        return self._l_rho[i] + w * (self._l_rho[i + 1] - self._l_rho[i])

    def cp_primaire_kj_kgk(self, t_c: float) -> float:
        """Capacité thermique massique (pente de la maille)."""
        i, _ = self._index_l(t_c)
        return (self._l_h[i + 1] - self._l_h[i]) / self._t_pas

    def t_primaire_c(self, h_kj_kg: float) -> float:
        """Température de l'eau du primaire d'enthalpie h."""
        j = bisect.bisect_left(self._l_h, h_kj_kg)
        j = min(max(j, 1), len(self._l_h) - 1)
        h0, h1 = self._l_h[j - 1], self._l_h[j]
        return self.t_min_c + (j - 1 + (h_kj_kg - h0) / (h1 - h0)) * self._t_pas

    # ------------------------------------------------------------------ détentes
    def h_isentrope_kj_kg(self, s_kj_kgk: float, p_bar: float) -> float:
        """Enthalpie après détente isentrope jusqu'à p_bar (mélange saturé, titre borné à [0, 1])."""
        s = self.sat(p_bar)
        x = (s_kj_kgk - s.sf_kj_kgk) / (s.sg_kj_kgk - s.sf_kj_kgk)
        x = min(max(x, 0.0), 1.0)
        return s.hf_kj_kg + x * s.hfg_kj_kg

    def flash_vu(self, v_m3_kg: float, u_kj_kg: float, p_depart_bar: float,
                 tolerance: float, pas_derivee: float, iterations_max: int) -> tuple[float, float]:
        """Équilibre de saturation d'un volume (v, u imposés) → (p_bar, titre x).

        Résout u = uf(P) + x(P)·(ug − uf) avec x(P) = (v − vf)/(vg − vf) par
        Newton sur ln P, sécurisé par un encadrement (bissection si besoin).
        """
        def residu(ln_p: float) -> tuple[float, float]:
            i, w = self._index_p(math.exp(ln_p))
            vf, vg = self._val_p("vf", i, w), self._val_p("vg", i, w)
            uf, ug = self._val_p("uf", i, w), self._val_p("ug", i, w)
            x = (v_m3_kg - vf) / (vg - vf)
            return uf + x * (ug - uf) - u_kj_kg, x

        lo, hi = math.log(self.p_min_bar), math.log(self.p_max_bar)
        ln_p = math.log(min(max(p_depart_bar, self.p_min_bar), self.p_max_bar))
        g, x = residu(ln_p)
        for _ in range(iterations_max):
            if g > 0.0:
                hi = ln_p
            else:
                lo = ln_p
            g_d, _ = residu(ln_p + pas_derivee)
            derivee = (g_d - g) / pas_derivee
            nouveau = ln_p - g / derivee if derivee > 0.0 else 0.5 * (lo + hi)
            if not lo < nouveau < hi:
                nouveau = 0.5 * (lo + hi)
            if abs(nouveau - ln_p) < tolerance:
                ln_p = nouveau
                g, x = residu(ln_p)
                break
            ln_p = nouveau
            g, x = residu(ln_p)
        return math.exp(ln_p), x


def lire_tables(chemin: Path = CHEMIN_TABLES) -> dict[str, Any] | None:
    if not chemin.exists():
        return None
    return json.loads(chemin.read_text(encoding="utf-8"))


@lru_cache(maxsize=4)
def obtenir_table(p_min_bar: float, p_max_bar: float, nb_points: int, t_pas_c: float,
                  p_liquide_bar: float) -> TableEau:
    """Table pour ces paramètres : lue dans config/tables_eau.json si elle correspond,
    sinon calculée avec CoolProp (une seule fois par processus)."""
    parametres: Parametres = (p_min_bar, p_max_bar, nb_points, t_pas_c, p_liquide_bar)
    donnees = lire_tables()
    if donnees is None or tuple(donnees["parametres"]) != parametres:
        donnees = calculer_tables(parametres)
    return TableEau(donnees)
