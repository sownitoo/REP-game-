"""Circuit primaire principal (RCP) : cuve + 4 boucles, pompes primaires, échange avec les GV.

Nodalisation (§9.1) : cuve en 3 nœuds (descente, cœur, plénum supérieur), 3 nœuds par
boucle (branche chaude BC, tubes du GV, branche froide BF avec la pompe). Chaque nœud
est un volume liquide fixe bien mélangé :
    C·dT/dt = Σ ṁ_entrant·(h_amont − h) + Q        C = m·cp + capacité du métal
Débits : réseau quasi statique (pompes + pertes de charge + moteur de circulation
naturelle (ρ_froid − ρ_chaud)·g·Δz). Une boucle à l'arrêt peut être traversée à
l'envers (antidévireur = rotor bloqué).
Échange GV (§9.3) : ε-NTU avec côté secondaire saturé, UA ∝ débit^0,8.
Dilatation : la masse expulsée des nœuds (volumes fixes) va au pressuriseur par
la ligne d'expansion, ce qui conserve exactement la masse.
RRA (V2) : branches du même réseau, du plénum à la descente ; l'échangeur retire sa chaleur
à l'arrivée dans la descente. Apports externes (charge, joints, accumulateurs) : (nœud, débit, h).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from sim.components.base import Composant
from sim.components.pump import Pompe
from sim.config import NumeriqueCfg, PrimaireCfg, ReseauCfg
from sim.core.network import Reseau, construire_reseau
from sim.systems.gv import GenerateurVapeur
from sim.thermo.tables import TableEau
from sim.units import G_M_S2, KJ_PAR_MJ, KW_PAR_MW, PA_PAR_BAR, POURCENT

DESCENTE, COEUR, PLENUM = "DESCENTE", "COEUR", "PLENUM"
EXPOSANT_PUISSANCE_POMPE = 3      # loi de similitude : puissance ∝ vitesse³


def bc(b: int) -> str:
    return f"BC{b}"


def gvp(b: int) -> str:
    return f"GVP{b}"


def bf(b: int) -> str:
    return f"BF{b}"


class Thermosiphon:
    """Élément de branche : moteur de circulation naturelle (ΔP imposé, en bar)."""

    anti_retour = False

    def __init__(self) -> None:
        self.dp_bar = 0.0

    def hydraulique(self, rho_kg_m3: float) -> tuple[float, float]:
        return self.dp_bar, 0.0


@dataclass
class EtatPrimaire:
    t_c: dict[str, float]
    w_boucles_kg_s: list[float]
    w_cuve_kg_s: float = 0.0
    masse_liquide_kg: float = 0.0
    qm_expansion_kg_s: float = 0.0         # vers le PZR (> 0 = entrée dans le PZR)
    q_gv_kw: list[float] = field(default_factory=list)
    q_pompes_kw: float = 0.0
    huile_s: list[float] = field(default_factory=list)   # durée de marche des pompes de soulèvement d'huile
    w_rra_kg_s: list[float] = field(default_factory=list)   # débit de chaque train RRA


class CircuitPrimaire:
    """Thermohydraulique du primaire (hors pressuriseur)."""

    def __init__(self, cfg: PrimaireCfg, reseau_cfg: ReseauCfg, composants: dict[str, Composant],
                 num: NumeriqueCfg, table: TableEau, boucles: list[int], t_initiale_c: float) -> None:
        self.cfg = cfg
        self.table = table
        self.boucles = boucles
        self.pompes: list[Pompe] = [composants[f"PP{b}"] for b in boucles]    # type: ignore[misc]
        self.huile: list[Pompe] = [composants[f"PSH{b}"] for b in boucles]    # type: ignore[misc]
        self.reseau: Reseau = construire_reseau("primaire", reseau_cfg, composants, num.reseau,
                                                table.rho_primaire_kg_m3(t_initiale_c),
                                                table.p_liquide_bar)
        self.thermosiphons = [Thermosiphon() for _ in boucles]
        for b, ts in zip(boucles, self.thermosiphons):
            self.reseau.branche[f"L_BOUCLE{b}"].elements.append(ts)
        v, cm = cfg.volumes_m3, cfg.capacites_metal_mj_c
        self.volumes: dict[str, float] = {DESCENTE: v.descente, COEUR: v.coeur, PLENUM: v.plenum}
        self.metal_kj_c: dict[str, float] = {DESCENTE: cm.descente * KJ_PAR_MJ, COEUR: cm.coeur * KJ_PAR_MJ,
                                             PLENUM: cm.plenum * KJ_PAR_MJ}
        for b in boucles:
            for nom, vol, met in ((bc(b), v.branche_chaude, cm.branche_chaude), (gvp(b), v.gv, cm.gv),
                                  (bf(b), v.branche_froide, cm.branche_froide)):
                self.volumes[nom] = vol
                self.metal_kj_c[nom] = met * KJ_PAR_MJ
        n = len(boucles)
        self.branches_rra = sorted(k for k in self.reseau.branche if k.startswith("L_RRA"))
        self.etat = EtatPrimaire(t_c={k: t_initiale_c for k in self.volumes}, w_boucles_kg_s=[0.0] * n,
                                 q_gv_kw=[0.0] * n, huile_s=[0.0] * n,
                                 w_rra_kg_s=[0.0] * len(self.branches_rra))
        self.etat.masse_liquide_kg = self.masse_liquide_kg()

    # ------------------------------------------------------------------ grandeurs
    def t(self, noeud: str) -> float:
        return self.etat.t_c[noeud]

    def masse_liquide_kg(self) -> float:
        return sum(self.table.rho_primaire_kg_m3(self.etat.t_c[k]) * v for k, v in self.volumes.items())

    def tmoy_boucle_c(self, i: int) -> float:
        b = self.boucles[i]
        return 0.5 * (self.t(bc(b)) + self.t(bf(b)))

    def dt_boucle_c(self, i: int) -> float:
        b = self.boucles[i]
        return self.t(bc(b)) - self.t(bf(b))

    @property
    def tmoy_c(self) -> float:
        return sum(self.tmoy_boucle_c(i) for i in range(len(self.boucles))) / len(self.boucles)

    @property
    def t_moderateur_c(self) -> float:
        """Température moyenne du modérateur dans le cœur (entrée + sortie) / 2."""
        return 0.5 * (self.t(DESCENTE) + self.t(COEUR))

    def debit_pct(self, i: int) -> float:
        return POURCENT * self.etat.w_boucles_kg_s[i] / self.cfg.debit_nom_boucle_kg_s

    # ------------------------------------------------------------------ hydraulique
    def resoudre_hydraulique(self) -> None:
        tab = self.table
        g_dz = G_M_S2 * self.cfg.hauteur_thermique_m / PA_PAR_BAR
        for b, ts in zip(self.boucles, self.thermosiphons):
            branche = self.reseau.branche[f"L_BOUCLE{b}"]
            rho_f = tab.rho_primaire_kg_m3(self.t(bf(b)))
            branche.rho_kg_m3 = rho_f
            ts.dp_bar = (rho_f - tab.rho_primaire_kg_m3(self.t(bc(b)))) * g_dz
        self.reseau.branche["L_CUVE"].rho_kg_m3 = tab.rho_primaire_kg_m3(self.t_moderateur_c)
        for k in self.branches_rra:
            self.reseau.branche[k].rho_kg_m3 = tab.rho_primaire_kg_m3(self.t(PLENUM))
        self.reseau.resoudre()
        self.etat.w_boucles_kg_s = [self.reseau.branche[f"L_BOUCLE{b}"].qm_kg_s for b in self.boucles]
        self.etat.w_cuve_kg_s = self.reseau.branche["L_CUVE"].qm_kg_s
        self.etat.w_rra_kg_s = [self.reseau.branche[k].qm_kg_s for k in self.branches_rra]

    # ------------------------------------------------------------------ échange GV
    def chaleur_gv_kw(self, i: int, gv: GenerateurVapeur) -> float:
        """ε-NTU, secondaire saturé : Q = ε·ṁ·cp·(T_entrée − Tsat)."""
        cfg, b = self.cfg, self.boucles[i]
        w = self.etat.w_boucles_kg_s[i]
        t_entree = self.t(bc(b)) if w >= 0.0 else self.t(bf(b))
        w = abs(w)
        if w <= 0.0:
            return 0.0
        # cp moyen entre l'entrée et la température de saturation (le cp de l'eau varie beaucoup vers 325 °C)
        tsat = gv.tsat_c
        dh = self.table.h_primaire_kj_kg(t_entree) - self.table.h_primaire_kj_kg(tsat)
        cp = dh / (t_entree - tsat) if abs(t_entree - tsat) > 0.0 else self.table.cp_primaire_kj_kgk(t_entree)
        rapport = w / cfg.debit_nom_boucle_kg_s
        ua = (cfg.gv_ua_mw_c * KW_PAR_MW * max(cfg.gv_fraction_ua_min, rapport ** cfg.gv_exposant_debit)
              * gv.facteur_mouillage())
        efficacite = 1.0 - math.exp(-ua / (w * cp))
        return efficacite * w * dh

    # ------------------------------------------------------------------ thermique
    def avancer(self, dt: float, q_coeur_kw: float, gvs: list[GenerateurVapeur],
                apports_externes: list[tuple[str, float, float]], qm_sorties_kg_s: float, qm_aspersion_kg_s: float,
                hf_pzr_kj_kg: float, q_rra_kw: float) -> None:
        """Bilans d'énergie des nœuds puis débit d'expansion vers le pressuriseur.
        apports_externes : (nœud, débit entrant kg/s, enthalpie kJ/kg) ; qm_sorties : décharge (à la température du nœud)."""
        e, tab, cfg = self.etat, self.table, self.cfg
        t = e.t_c
        h = {k: tab.h_primaire_kj_kg(v) for k, v in t.items()}
        w_v = e.w_cuve_kg_s
        apports: dict[str, list[tuple[float, float]]] = {k: [] for k in t}   # (débit, h amont)
        q: dict[str, float] = {k: 0.0 for k in t}

        def ecoulement(amont: str, aval: str, debit: float) -> None:
            apports[aval].append((debit, h[amont]))

        if w_v >= 0.0:
            ecoulement(DESCENTE, COEUR, w_v)
            ecoulement(COEUR, PLENUM, w_v)
        else:
            ecoulement(PLENUM, COEUR, -w_v)
            ecoulement(COEUR, DESCENTE, -w_v)
        e.q_pompes_kw = 0.0
        for i, b in enumerate(self.boucles):
            w = e.w_boucles_kg_s[i]
            chaine = [PLENUM, bc(b), gvp(b), bf(b), DESCENTE] if w >= 0.0 else [DESCENTE, bf(b), gvp(b), bc(b), PLENUM]
            for amont, aval in zip(chaine, chaine[1:]):
                ecoulement(amont, aval, abs(w))
            e.q_gv_kw[i] = self.chaleur_gv_kw(i, gvs[i])
            q[gvp(b)] -= e.q_gv_kw[i]
            q_pompe = cfg.chaleur_pompe_mw * KW_PAR_MW * self.pompes[i].etat.vitesse ** EXPOSANT_PUISSANCE_POMPE
            q[bf(b)] += q_pompe
            e.q_pompes_kw += q_pompe
        for w in e.w_rra_kg_s:                       # RRA : plénum → (échangeur) → descente
            if w > 0.0:
                ecoulement(PLENUM, DESCENTE, w)
        q[DESCENTE] -= q_rra_kw
        q[COEUR] += q_coeur_kw
        qm_apports = 0.0
        for noeud, debit, h_entree in apports_externes:
            q[noeud] += debit * (h_entree - h[noeud])
            qm_apports += debit
        if e.qm_expansion_kg_s < 0.0:      # le PZR se vide dans la branche chaude B2
            q[bc(cfg.boucle_expansion)] += -e.qm_expansion_kg_s * (hf_pzr_kj_kg - h[bc(cfg.boucle_expansion)])

        nouveau = {}
        for k, tk in t.items():
            cp = tab.cp_primaire_kj_kgk(tk)
            capacite = tab.rho_primaire_kg_m3(tk) * self.volumes[k] * cp + self.metal_kj_c[k]
            flux = sum(debit * (h_amont - h[k]) for debit, h_amont in apports[k]) + q[k]
            nouveau[k] = tk + dt * flux / capacite
        e.t_c = nouveau
        # dilatation → ligne d'expansion (conservation exacte de la masse)
        masse = self.masse_liquide_kg()
        e.qm_expansion_kg_s = ((e.masse_liquide_kg - masse) / dt + qm_apports - qm_sorties_kg_s
                               - qm_aspersion_kg_s)
        e.masse_liquide_kg = masse

    def avancer_huile(self, dt: float) -> None:
        """Durée de marche des pompes de soulèvement d'huile (verrou de démarrage des pompes primaires)."""
        for i, p in enumerate(self.huile):
            self.etat.huile_s[i] = self.etat.huile_s[i] + dt if p.etat.en_marche else 0.0

    # ------------------------------------------------------------------ sauvegarde
    def exporter_etat(self) -> dict[str, Any]:
        e = self.etat
        return {"t_c": dict(e.t_c), "w_boucles_kg_s": list(e.w_boucles_kg_s), "w_cuve_kg_s": e.w_cuve_kg_s,
                "masse_liquide_kg": e.masse_liquide_kg, "qm_expansion_kg_s": e.qm_expansion_kg_s,
                "q_gv_kw": list(e.q_gv_kw), "q_pompes_kw": e.q_pompes_kw, "huile_s": list(e.huile_s),
                "w_rra_kg_s": list(e.w_rra_kg_s),
                "reseau_p_bar": dict(self.reseau.etat.p_bar)}

    def importer_etat(self, d: dict[str, Any]) -> None:
        d = dict(d)
        self.reseau.etat.p_bar = dict(d.pop("reseau_p_bar"))
        self.etat = EtatPrimaire(**d)
