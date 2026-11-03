"""Pressuriseur (§4.1) : volume diphasique à saturation qui fixe la pression du primaire.

- Chaufferettes : groupe proportionnel + groupes tout-ou-rien (coupés si niveau < 17 %).
- Aspersion : 2 vannes alimentées par les branches froides B2/B3 (débit ∝ vitesse des
  pompes primaires) + débit permanent.
- 2 PORV (pneumatiques, réserve d'air) derrière leur vanne d'isolement, 3 soupapes.
- Expansion : entrée d'eau de la branche chaude B2 ou sortie d'eau saturée.
Modèle à 1 zone (équilibre liquide/vapeur), l'option 2 zones de la spec n'est pas faite.

V4 — primaire saturé (« vide » dans le primaire) : quand l'eau la plus chaude du primaire atteint la
saturation (marge nulle) ou que le PZR ne peut plus fournir l'eau demandée, un volume de vapeur se forme
dans le plénum supérieur / les branches chaudes. La pression du primaire est alors celle de saturation
de l'eau la plus chaude, P = Psat(T chaude) ; le PZR est ramené à cette pression en échangeant de l'eau
avec le primaire (vapeur qui sort par les PORV → eau poussée dans le PZR : le niveau monte alors que le
primaire se vide, comme à TMI). La vapeur formée (ou condensée) dans le vide prend (ou rend) sa chaleur
latente à l'eau la plus chaude au pas suivant. PZR plein en eau : les PORV/soupapes déchargent de l'eau.
Primaire plein d'eau (plus de bulle) : l'excédent d'eau comprime le primaire, P = P_bulle + m_comprimée / C
(C ≈ 40 kg/bar) jusqu'à ce que les PORV / soupapes déchargent autant que l'injection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sim.components.base import Composant, Sources
from sim.components.relief import Soupape
from sim.components.sensor import Capteur
from sim.components.valve import Vanne
from sim.components.volume2phase import Volume2Phase
from sim.config import FlashCfg, PressuriseurCfg
from sim.thermo.tables import TableEau
from sim.units import KW_PAR_MW, POURCENT, S_PAR_H, interp_table

NIVEAU_PLEIN_PCT = 99.0          # PZR « plein » : la décharge par le haut devient de l'eau
FACTEUR_DEBIT_EAU = 3.0          # HYPOTHESE débit massique d'eau d'une PORV / soupape ≈ 3 × débit vapeur
FRACTION_LIQUIDE_MIN = 1.0e-4    # liquide minimal laissé au PZR (le flash reste dans le domaine diphasique)


@dataclass
class EtatChaufferettes:
    auto: bool
    demande_auto: float          # 0..1
    demande_manu: float          # 0..1
    coupe: str                   # raison de coupure automatique ("" = aucune)
    puissance_kw: float


class GroupeChaufferettes(Composant):
    """Groupe de chaufferettes (proportionnel ou tout-ou-rien)."""

    type_ui = "chaufferettes"

    def __init__(self, id: str, puissance_kw: float, proportionnel: bool, alim: str | None) -> None:
        super().__init__(id, "RCP", alim)
        self.puissance_max_kw = puissance_kw
        self.proportionnel = proportionnel
        self.etat = EtatChaufferettes(auto=True, demande_auto=0.0, demande_manu=0.0, coupe="", puissance_kw=0.0)

    def commandes(self) -> list[str]:
        return ["auto", "manu", "puissance"]

    def executer(self, action: str, valeur: float | None) -> None:
        e = self.etat
        if action == "auto":
            e.auto = True
        elif action == "manu":
            e.auto = False
            e.demande_manu = e.puissance_kw / self.puissance_max_kw
        elif action == "puissance" and valeur is not None:
            frac = valeur / POURCENT
            e.demande_manu = frac if self.proportionnel else float(frac > 0.0)

    def avancer(self, sources: Sources) -> None:
        e = self.etat
        demande = e.demande_auto if e.auto else e.demande_manu
        if e.coupe or not sources.electricite_ok:
            demande = 0.0
        e.puissance_kw = self.puissance_max_kw * min(max(demande, 0.0), 1.0)

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        d.update(auto=self.etat.auto, puissance_kw=self.etat.puissance_kw, coupe=self.etat.coupe,
                 proportionnel=self.proportionnel, puissance_pct=POURCENT * self.etat.puissance_kw / self.puissance_max_kw)
        return d


@dataclass
class EtatPressuriseur:
    qm_aspersion_kg_s: float
    qm_porv_kg_s: float
    qm_soupapes_kg_s: float
    q_chauffe_kw: float
    v_vide_m3: float = 0.0           # vapeur dans le primaire (hors PZR)
    q_vide_kw: float = 0.0           # chaleur latente à rendre à l'eau la plus chaude (< 0 : vaporisation)
    sature: bool = False             # primaire saturé : P = Psat(T chaude)
    hors_domaine: str = ""           # raison du gel de la simulation (cœur découvert)
    m_comprime_kg: float = 0.0       # primaire plein d'eau : masse stockée par compression


class Pressuriseur(Composant):
    """Pressuriseur (repère PZR)."""

    type_ui = "pzr"

    def __init__(self, cfg: PressuriseurCfg, composants: dict[str, Composant],
                 table: TableEau, flash: FlashCfg, boucles_aspersion: list[int]) -> None:
        super().__init__("PZR", "RCP")
        self.cfg = cfg
        self.table = table
        self.vol = Volume2Phase(cfg.volume_m3, table, flash)
        self.chauffe_prop = GroupeChaufferettes("PZR_CHAUF_P", cfg.chaufferettes.proportionnelles_kw, True, "LGA")
        self.chauffe_tor = GroupeChaufferettes("PZR_CHAUF_T", cfg.chaufferettes.tor_kw, False, "LHB")   # groupe de secours (HYPOTHESE)
        self.aspersion: list[Vanne] = [composants[f"PZR_ASP{b}"] for b in boucles_aspersion]   # type: ignore[misc]
        self.porv: list[Vanne] = [composants["PZR_PORV1"], composants["PZR_PORV2"]]          # type: ignore[list-item]
        self.isol: list[Vanne] = [composants["PZR_ISOL1"], composants["PZR_ISOL2"]]          # type: ignore[list-item]
        s = cfg.soupapes
        self.soupapes = [Soupape(f"PZR_SOUP{n}", "RCP", tarage, s.capacite_kg_s, s.fermeture_pct)
                         for n, tarage in enumerate(s.tarages_bar, start=1)]
        self.capteur_p = Capteur("PZR_P", "RCP", cfg.voies_pression, cfg.retard_mesure_s, 0.0,
                                 cfg.gamme_pression_bar, 0.0)
        self.capteur_niveau = Capteur("PZR_NIV", "RCP", cfg.voies_niveau, cfg.retard_mesure_s, 0.0, POURCENT, 0.0)
        self.etat = EtatPressuriseur(qm_aspersion_kg_s=0.0, qm_porv_kg_s=0.0, qm_soupapes_kg_s=0.0, q_chauffe_kw=0.0)

    def initialiser(self, p_bar: float, niveau_pct: float) -> None:
        s = self.table.sat(p_bar)
        self.vol.initialiser(p_bar, niveau_pct / POURCENT * self.cfg.volume_m3 / s.vf_m3_kg)
        self.capteur_p.initialiser(p_bar)
        self.capteur_niveau.initialiser(self.niveau_pct)

    # ------------------------------------------------------------------ grandeurs
    @property
    def p_bar(self) -> float:
        return self.vol.p_bar + self.etat.m_comprime_kg / self.cfg.compressibilite_kg_bar

    @property
    def en_eau(self) -> bool:
        """Primaire plein d'eau (plus de bulle) : la pression vient de la compression."""
        return self.etat.m_comprime_kg > 0.0

    @property
    def niveau_pct(self) -> float:
        return POURCENT * self.vol.v_liq_m3 / self.cfg.volume_m3

    def niveau_programme_pct(self, tmoy_c: float) -> float:
        return interp_table(self.cfg.programme_niveau_pct, tmoy_c)

    def debit_aspersion_kg_s(self, vitesses_pompes: list[float], rho_kg_m3: float) -> float:
        """Aspersion : débit ∝ ouverture × vitesse de la pompe de la boucle d'origine, + débit permanent."""
        a = self.cfg.aspersion
        debit_m3h = sum(v.etat.position * a.debit_vanne_m3h * s for v, s in zip(self.aspersion, vitesses_pompes))
        debit_m3h += a.debit_permanent_m3h * max(vitesses_pompes, default=0.0)
        return debit_m3h * rho_kg_m3 / S_PAR_H

    @property
    def plein(self) -> bool:
        return self.niveau_pct >= NIVEAU_PLEIN_PCT

    def debit_porv_kg_s(self) -> float:
        c = self.cfg.porv
        facteur = FACTEUR_DEBIT_EAU if self.plein else 1.0
        return facteur * sum(c.capacite_kg_s * min(p.etat.position, i.etat.position) * self.p_bar / c.p_ref_bar
                             for p, i in zip(self.porv, self.isol))

    @property
    def h_decharge_kj_kg(self) -> float:
        """Enthalpie de ce qui sort par les PORV / soupapes (vapeur, ou eau si le PZR est plein)."""
        return self.vol.sat.hf_kj_kg if self.plein else self.vol.sat.hg_kj_kg

    # ------------------------------------------------------------------ dynamique
    def avancer(self, dt: float, qm_expansion_kg_s: float, h_branche_chaude_kj_kg: float,
                qm_aspersion_kg_s: float, h_aspersion_kj_kg: float,
                sources: Callable[[Composant], Sources], t_chaud_c: float, qm_vapeur_vide_kg_s: float = 0.0) -> list[str]:
        """Bilans du pressuriseur (et du vide primaire) ; renvoie les soupapes qui viennent de s'ouvrir.
        t_chaud_c : température de l'eau la plus chaude du primaire ; qm_vapeur_vide : vapeur qui quitte le vide
        (brèche) — elle est remplacée par de l'eau vaporisée, qui prend sa chaleur latente à l'eau chaude."""
        e, s = self.etat, self.vol.sat
        for ch in (self.chauffe_prop, self.chauffe_tor):
            ch.avancer(sources(ch))
        e.q_chauffe_kw = self.chauffe_prop.etat.puissance_kw + self.chauffe_tor.etat.puissance_kw
        e.qm_aspersion_kg_s = qm_aspersion_kg_s
        e.qm_porv_kg_s = self.debit_porv_kg_s()
        ouvertures = [sp.id for sp in self.soupapes if sp.mettre_a_jour(self.p_bar)]
        e.qm_soupapes_kg_s = sum(sp.debit_kg_s(self.p_bar) for sp in self.soupapes) * (
            FACTEUR_DEBIT_EAU if self.plein else 1.0)
        qm_vapeur = e.qm_porv_kg_s + e.qm_soupapes_kg_s
        h_decharge = self.h_decharge_kj_kg
        v_vide_debut = e.v_vide_m3
        if e.v_vide_m3 > 0.0:
            e.v_vide_m3 += qm_vapeur_vide_kg_s * dt * s.vf_m3_kg
        # l'eau échangée avec le primaire comble (ou creuse) d'abord le vide ; le PZR ne fournit que son liquide
        if e.v_vide_m3 > 0.0 and qm_expansion_kg_s > 0.0:
            comble = min(e.v_vide_m3, qm_expansion_kg_s * dt * s.vf_m3_kg)
            e.v_vide_m3 -= comble
            qm_expansion_kg_s -= comble / (s.vf_m3_kg * dt)
        elif qm_expansion_kg_s < 0.0:
            dispo = max(0.0, self.vol.m_liq_kg - FRACTION_LIQUIDE_MIN * self.vol.etat.m_kg) / dt
            if e.v_vide_m3 > 0.0:
                dispo = 0.0
            manque = -qm_expansion_kg_s - min(dispo, -qm_expansion_kg_s)
            e.v_vide_m3 += manque * dt * s.vf_m3_kg
            qm_expansion_kg_s += manque
        entree_kg_s = qm_aspersion_kg_s
        entree_kw = qm_aspersion_kg_s * h_aspersion_kj_kg + e.q_chauffe_kw
        sortie_kg_s = qm_vapeur
        sortie_kw = qm_vapeur * h_decharge + self.cfg.pertes_thermiques_kw
        if qm_expansion_kg_s >= 0.0:
            entree_kg_s += qm_expansion_kg_s
            entree_kw += qm_expansion_kg_s * h_branche_chaude_kj_kg
        else:
            sortie_kg_s -= qm_expansion_kg_s
            sortie_kw -= qm_expansion_kg_s * s.hf_kj_kg
        net = entree_kg_s - sortie_kg_s
        if e.m_comprime_kg > 0.0 or (self.plein and net > 0.0 and e.v_vide_m3 <= 0.0):
            # primaire en eau : le bilan de masse comprime (ou décomprime) l'eau ; seule la chaleur va au PZR
            e.m_comprime_kg += net * dt
            entree_kg_s = sortie_kg_s = 0.0
            entree_kw = sortie_kw = 0.0               # PZR plein : chauffage et pertes négligés
            if e.m_comprime_kg < 0.0:               # la bulle réapparaît : le reste sort du PZR
                sortie_kg_s = -e.m_comprime_kg / dt
                sortie_kw += sortie_kg_s * s.hf_kj_kg
                e.m_comprime_kg = 0.0
        self.vol.integrer(dt, entree_kg_s, entree_kw, sortie_kg_s, sortie_kw)
        self._saturer(t_chaud_c)
        sat = self.vol.sat
        h_fg = sat.hg_kj_kg - sat.hf_kj_kg
        e.q_vide_kw = -(e.v_vide_m3 - v_vide_debut) * h_fg / sat.vg_m3_kg / dt
        if e.v_vide_m3 > 0.0:
            e.q_vide_kw -= qm_vapeur_vide_kg_s * h_fg
        self.capteur_p.mesurer(dt, self.p_bar)
        self.capteur_niveau.mesurer(dt, self.niveau_pct)
        return ouvertures

    def _saturer(self, t_chaud_c: float) -> None:
        """Primaire saturé : P = Psat(T chaude). Le PZR (m, U) est ramené à P en échangeant de l'eau
        saturée avec le vide du primaire (Δm > 0 : de l'eau sort du PZR et comble le vide)."""
        e, tab, vol = self.etat, self.table, self.vol
        p = min(max(tab.psat_bar(t_chaud_c), tab.p_min_bar), tab.p_max_bar)
        e.sature = e.v_vide_m3 > 0.0 or self.p_bar < p
        if not e.sature:
            return
        s = tab.sat(p)
        if e.m_comprime_kg > 0.0:                      # décompression : l'eau stockée revient au PZR
            vol.etat.m_kg += e.m_comprime_kg
            vol.etat.u_kj += e.m_comprime_kg * s.hf_kj_kg
            e.m_comprime_kg = 0.0
        m, u = vol.etat.m_kg, vol.etat.u_kj
        r = (s.vg_m3_kg - s.vf_m3_kg) / (s.ug_kj_kg - s.uf_kj_kg)
        dm = (m * s.vf_m3_kg + (u - m * s.uf_kj_kg) * r - vol.v_m3) / (s.vf_m3_kg + (s.hf_kj_kg - s.uf_kj_kg) * r)
        if dm > 0.0:                                   # l'eau sortie ne peut pas dépasser le vide à combler
            dm = min(dm, e.v_vide_m3 / s.vf_m3_kg)
        m2, u2 = m - dm, u - dm * s.hf_kj_kg
        m_vap = (u2 - m2 * s.uf_kj_kg) / (s.ug_kj_kg - s.uf_kj_kg)
        borne = None
        if m_vap > m2 * (1.0 - FRACTION_LIQUIDE_MIN):  # plus de liquide : PZR plein de vapeur à P
            borne = 1.0 - FRACTION_LIQUIDE_MIN
        elif m_vap < FRACTION_LIQUIDE_MIN * m2:        # PZR plein d'eau à P
            borne = FRACTION_LIQUIDE_MIN
        if borne is not None:
            m2 = vol.v_m3 / (s.vf_m3_kg + borne * (s.vg_m3_kg - s.vf_m3_kg))
            u2 = m2 * (s.uf_kj_kg + borne * (s.ug_kj_kg - s.uf_kj_kg))
            dm = m - m2
            if dm > 0.0:                               # seule l'eau sortie comble le vide
                dm = min(dm, vol.m_liq_kg)
        e.v_vide_m3 = max(0.0, e.v_vide_m3 - dm * s.vf_m3_kg)
        vol.etat.m_kg, vol.etat.u_kj = m2, u2
        vol.etat.p_bar = p
        vol.mettre_a_jour()

    def nb_soupapes_ouvertes(self) -> int:
        return sum(sp.etat.ouverte for sp in self.soupapes)

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        d.update(p_bar=self.p_bar, niveau_pct=self.niveau_pct, chauffe_mw=self.etat.q_chauffe_kw / KW_PAR_MW,
                 aspersion_kg_s=self.etat.qm_aspersion_kg_s, porv_kg_s=self.etat.qm_porv_kg_s,
                 voies_pression=self.capteur_p.etat.valeurs, voies_niveau=self.capteur_niveau.etat.valeurs)
        return d
