"""Solveur générique de réseau hydraulique liquide, quasi statique.

Le réseau est un graphe :
- « frontières » : pressions imposées par des volumes (GV, puits, bâches…) ;
- « nœuds » : jonctions sans stockage (Σ débits massiques = 0) ;
- « branches » : éléments en série (pompes, vannes, clapets, pertes de charge),
  une sous-liste = vannes en parallèle (Kv additionnés).

Tous les éléments sont quadratiques en débit volumique Q (m³/h) :
    pompe  : ΔP = ΔP0·s² − k·Q²        vanne/échangeur : ΔP = d·(Q/Kv)²
d'où une loi de branche en forme fermée Q = √(moteur / R). On résout par Newton
sur les pressions des nœuds (jacobien analytique).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Protocol

from sim.config import ReseauCfg, ReseauNumCfg
from sim.units import RHO_REF_KG_M3, S_PAR_H


class ElementVanne(Protocol):
    anti_retour: bool

    def kv(self) -> float: ...


class ElementPompe(Protocol):
    def hydraulique(self, rho_kg_m3: float) -> tuple[float, float]: ...


Element = ElementVanne | ElementPompe | list[ElementVanne]


@dataclass
class Branche:
    """Branche orientée de `de` vers `vers` (sens positif du débit)."""

    id: str
    de: str
    vers: str
    elements: list[Element]
    rho_kg_m3: float
    qm_kg_s: float = 0.0
    # caractéristique figée pendant une résolution
    _dp0_bar: float = 0.0
    _r: float = 0.0
    _anti_retour: bool = False
    _fermee: bool = False
    _r_inverse: float = 0.0         # résistance supplémentaire en débit inverse (antidévireur)


@dataclass
class Injection:
    """Apport de débit dans un nœud par une pompe à caractéristique linéaire :
    plein débit sous p_plein_bar, nul au-delà de p_arret_bar."""

    qm_max_kg_s: float = 0.0
    p_plein_bar: float = 0.0
    p_arret_bar: float = 0.0
    qm_kg_s: float = 0.0

    def debit(self, p_bar: float) -> tuple[float, float]:
        """Débit injecté et dérivée d(qm)/dP."""
        if self.qm_max_kg_s <= 0.0 or p_bar >= self.p_arret_bar:
            return 0.0, 0.0
        if p_bar <= self.p_plein_bar:
            return self.qm_max_kg_s, 0.0
        pente = self.qm_max_kg_s / (self.p_arret_bar - self.p_plein_bar)
        return pente * (self.p_arret_bar - p_bar), -pente


@dataclass
class EtatReseau:
    p_bar: dict[str, float] = field(default_factory=dict)
    iterations: int = 0
    residu_kg_s: float = 0.0


class Reseau:
    """Réseau liquide résolu à chaque pas de temps."""

    def __init__(self, id: str, frontieres: list[str], noeuds: list[str], branches: list[Branche],
                 injections: list[str], num: ReseauNumCfg, p_initiale_bar: float) -> None:
        self.id = id
        self.frontieres = frontieres
        self.noeuds = noeuds
        self.branches = branches
        self.num = num
        self.injections: dict[str, Injection] = {n: Injection() for n in injections}
        self._index = {n: i for i, n in enumerate(noeuds)}
        self.etat = EtatReseau(p_bar={n: p_initiale_bar for n in frontieres + noeuds})
        self.branche = {b.id: b for b in branches}

    # ------------------------------------------------------------------ entrées
    def fixer_frontiere(self, nom: str, p_bar: float) -> None:
        self.etat.p_bar[nom] = p_bar

    def fixer_injection(self, noeud: str, qm_max_kg_s: float, p_plein_bar: float, p_arret_bar: float) -> None:
        inj = self.injections[noeud]
        inj.qm_max_kg_s, inj.p_plein_bar, inj.p_arret_bar = qm_max_kg_s, p_plein_bar, p_arret_bar

    def p(self, nom: str) -> float:
        return self.etat.p_bar[nom]

    # ------------------------------------------------------------------ lois de branche
    def _caracteriser(self, b: Branche) -> None:
        """Calcule ΔP0 des pompes, la résistance totale R, clapet, fermeture."""
        d = b.rho_kg_m3 / RHO_REF_KG_M3
        dp0, r, anti_retour, fermee, r_inv = 0.0, 0.0, False, False, 0.0
        for el in b.elements:
            if isinstance(el, list):
                kv = sum(v.kv() for v in el)
            elif hasattr(el, "hydraulique"):
                p0, k = el.hydraulique(b.rho_kg_m3)  # type: ignore[union-attr]
                dp0 += p0
                r += k
                if hasattr(el, "r_inverse_bar"):
                    r_inv += el.r_inverse_bar(b.rho_kg_m3)  # type: ignore[union-attr]
                continue
            else:
                kv = el.kv()  # type: ignore[union-attr]
                anti_retour = anti_retour or el.anti_retour  # type: ignore[union-attr]
            if kv <= 0.0:
                fermee = True
            else:
                r += d / (kv * kv)
        b._dp0_bar, b._r, b._anti_retour, b._fermee, b._r_inverse = dp0, r, anti_retour, fermee, r_inv

    def _debit(self, b: Branche, dp_bar: float) -> tuple[float, float]:
        """Débit massique (kg/s) et dérivée d(qm)/d(ΔP) pour ΔP = P_de − P_vers."""
        if b._fermee:
            g = self.num.fuite_vanne_fermee_kg_s_bar
            return g * dp_bar, g
        moteur = dp_bar + b._dp0_bar
        if moteur < 0.0 and b._anti_retour:
            g = self.num.fuite_clapet_kg_s_bar
            return g * moteur, g
        a = abs(moteur)
        eps = self.num.zone_lineaire_bar
        conv = b.rho_kg_m3 / S_PAR_H                     # m³/h → kg/s
        r = b._r + b._r_inverse if moteur < 0.0 else b._r
        if a > eps:
            q = math.sqrt(a / r)
            dq = q / (2.0 * a)
        else:                                            # zone linéaire (régularisation)
            c = math.sqrt(eps * r)
            q, dq = a / c, 1.0 / c
        return math.copysign(q, moteur) * conv, dq * conv

    # ------------------------------------------------------------------ résolution
    def _bilan(self, p: dict[str, float], avec_jacobien: bool) -> tuple[list[float], list[list[float]]]:
        """Résidu f (Σ débits entrants par nœud, kg/s) et jacobien ∂f/∂P ; met à jour les débits."""
        n = len(self.noeuds)
        f = [0.0] * n
        jac = [[0.0] * n for _ in range(n)] if avec_jacobien else []
        for nom, inj in self.injections.items():
            k = self._index[nom]
            inj.qm_kg_s, d_inj = inj.debit(p[nom])
            f[k] += inj.qm_kg_s
            if jac:
                jac[k][k] += d_inj
        for b in self.branches:
            qm, g = self._debit(b, p[b.de] - p[b.vers])
            b.qm_kg_s = qm
            i, j = self._index.get(b.de), self._index.get(b.vers)
            if i is not None:
                f[i] -= qm
            if j is not None:
                f[j] += qm
            if jac:
                if i is not None:
                    jac[i][i] -= g
                    if j is not None:
                        jac[i][j] += g
                if j is not None:
                    jac[j][j] -= g
                    if i is not None:
                        jac[j][i] += g
        return f, jac

    def resoudre(self) -> None:
        """Newton sur les pressions des nœuds (Σ débits = 0 en chaque nœud),
        avec recherche linéaire : le pas est divisé par 2 tant que le résidu n'a pas baissé.
        Le réseau est monotone (débit croissant avec ΔP), ce qui garantit la convergence."""
        for b in self.branches:
            self._caracteriser(b)
        num = self.num
        p = self.etat.p_bar
        f, jac = self._bilan(p, avec_jacobien=True)
        residu = max((abs(x) for x in f), default=0.0)
        iteration = 0
        for iteration in range(1, num.iterations_max + 1):
            if residu < num.tolerance_kg_s:
                break
            for k in range(len(f)):
                jac[k][k] -= num.regularisation_jacobien
            delta = resoudre_lineaire(jac, [-x for x in f])
            pas_max = max(abs(x) for x in delta)
            if pas_max > num.pas_max_bar:
                delta = [x * num.pas_max_bar / pas_max for x in delta]
            depart = {nom: p[nom] for nom in self._index}
            lam = 1.0
            for _ in range(num.recherche_lineaire_max):
                for nom, k in self._index.items():
                    p[nom] = depart[nom] + lam * delta[k]
                f_essai, _ = self._bilan(p, avec_jacobien=False)
                if max(abs(x) for x in f_essai) < residu:
                    break
                lam /= 2.0
            f, jac = self._bilan(p, avec_jacobien=True)
            residu = max(abs(x) for x in f)
        self.etat.iterations = iteration
        self.etat.residu_kg_s = residu


def resoudre_lineaire(a: list[list[float]], b: list[float]) -> list[float]:
    """Résout a·x = b (petit système dense) par élimination de Gauss avec pivot partiel."""
    n = len(b)
    m = [ligne[:] + [b[i]] for i, ligne in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[pivot] = m[pivot], m[col]
        diag = m[col][col]
        for r in range(col + 1, n):
            facteur = m[r][col] / diag
            if facteur:
                for c in range(col, n + 1):
                    m[r][c] -= facteur * m[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (m[r][n] - sum(m[r][c] * x[c] for c in range(r + 1, n))) / m[r][r]
    return x


def construire_reseau(id: str, cfg: ReseauCfg, composants: dict[str, Any], num: ReseauNumCfg,
                      rho_kg_m3: float, p_initiale_bar: float) -> Reseau:
    """Construit un réseau à partir de sa description YAML (repères → composants)."""
    branches = []
    for b in cfg.branches:
        elements: list[Any] = [[composants[x] for x in el] if isinstance(el, list) else composants[el]
                               for el in b.elements]
        branches.append(Branche(b.id, b.de, b.vers, elements, rho_kg_m3))
    return Reseau(id, cfg.frontieres, cfg.noeuds, branches, cfg.injections, num, p_initiale_bar)
