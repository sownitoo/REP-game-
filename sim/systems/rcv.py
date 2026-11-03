"""Contrôle chimique et volumétrique (RCV, §4.2), appoint eau-bore (REA) et bore du primaire.

Charge   : pompes centrifuges (aspiration VCT ou PTR) → FCV-121 (régulation de niveau PZR)
           → MO-8105/8106 → branche froide B1 ; injection aux joints (HCV-182) dont une partie
           entre au primaire, le reste revient à la VCT.
           Débit disponible des pompes : Q = n·Qn·√((ΔP0 − ΔP)/(ΔP0 − ΔPn)).
Décharge : branche en U B3 → LCV-459/460 → orifices → CV-8152 → échangeur (RRI) → PCV-131 → VCT ;
           débit des orifices ∝ √(P primaire − P aval PCV-131). En RRA : HCV-128 (RRA → RCV).
VCT      : bâche bien mélangée (volume, bore). Déviation LCV-112A vers les effluents si niveau haut.
REA      : modes auto (appoint à la VCT sur niveau bas, à la concentration du primaire), borication
           (acide à l'aspiration des pompes de charge), dilution (eau à la VCT), arrêt ;
           borication d'urgence MO-8104 directement à l'aspiration des pompes de charge.
Bore     : primaire + PZR = un seul volume bien mélangé : M·dC/dt = Σ ṁ_entrant·(C_entrant − C).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from sim.components.base import Composant
from sim.components.pump import Pompe
from sim.components.valve import Vanne
from sim.config import RcvCfg, ReaCfg
from sim.units import POURCENT, S_PAR_H

MODES_REA = ("auto", "borication", "dilution", "arret")
VOLUME_DEFAUT_M3 = 5.0          # volume proposé pour une borication / dilution sans valeur saisie
SURDEBIT_MAX = 1.5              # débit maxi d'une pompe de charge / nominal (bas de courbe)


@dataclass
class EtatRea:
    mode: str = "auto"
    volume_restant_m3: float = 0.0
    appoint_auto: bool = False
    acide_m3: float = 0.0          # contenu des bâches d'acide borique
    eau_m3: float = 0.0            # bâche d'eau d'appoint
    q_acide_m3h: float = 0.0
    q_eau_m3h: float = 0.0


class Rea(Composant):
    """Appoint eau et bore (repère REA)."""

    type_ui = "rea"

    def __init__(self, cfg: ReaCfg) -> None:
        super().__init__("REA", "REA")
        self.cfg = cfg
        self.etat = EtatRea(acide_m3=cfg.volume_acide_m3, eau_m3=cfg.volume_eau_m3)

    def commandes(self) -> list[str]:
        return ["auto", "borication", "dilution", "arret"]

    def executer(self, action: str, valeur: float | None) -> None:
        e = self.etat
        e.mode = action
        e.volume_restant_m3 = valeur if (valeur is not None and valeur > 0.0) else VOLUME_DEFAUT_M3
        e.appoint_auto = False

    def calculer(self, dt: float, niveau_vct_pct: float, bore_primaire_ppm: float, seuil_bas_pct: float,
                 seuil_arret_pct: float) -> None:
        """Débits d'acide et d'eau envoyés à la VCT (m³/h) pour ce pas."""
        c, e = self.cfg, self.etat
        q_acide = q_eau = 0.0
        if e.mode == "auto":
            if niveau_vct_pct < seuil_bas_pct:
                e.appoint_auto = True
            elif niveau_vct_pct > seuil_arret_pct:
                e.appoint_auto = False
            if e.appoint_auto:                          # mélange à la concentration du primaire
                q_acide = c.debit_auto_m3h * min(1.0, bore_primaire_ppm / c.bore_acide_ppm)
                q_eau = c.debit_auto_m3h - q_acide
        elif e.mode == "borication":
            q_acide = c.debit_borication_m3h
        elif e.mode == "dilution":
            q_eau = c.debit_dilution_m3h
        if e.mode in ("borication", "dilution"):
            e.volume_restant_m3 -= (q_acide + q_eau) * dt / S_PAR_H
            if e.volume_restant_m3 <= 0.0:              # totalisateur atteint : retour en automatique
                e.volume_restant_m3 = 0.0
                e.mode = "auto"
        q_acide = q_acide if e.acide_m3 > 0.0 else 0.0
        q_eau = q_eau if e.eau_m3 > 0.0 else 0.0
        e.acide_m3 = max(0.0, e.acide_m3 - q_acide * dt / S_PAR_H)
        e.eau_m3 = max(0.0, e.eau_m3 - q_eau * dt / S_PAR_H)
        e.q_acide_m3h, e.q_eau_m3h = q_acide, q_eau

    def etat_ui(self) -> dict[str, Any]:
        d = super().etat_ui()
        e = self.etat
        d.update(mode=e.mode, volume_restant_m3=e.volume_restant_m3, acide_m3=e.acide_m3, eau_m3=e.eau_m3,
                 q_acide_m3h=e.q_acide_m3h, q_eau_m3h=e.q_eau_m3h, appoint_auto=e.appoint_auto)
        return d


@dataclass
class EtatRcv:
    vct_m3: float
    vct_bore_ppm: float
    ptr_m3: float
    bore_primaire_ppm: float
    effluents_m3: float = 0.0
    # débits du dernier pas (m³/h, eau à la température de la VCT)
    q_dispo_m3h: float = 0.0
    q_charge_m3h: float = 0.0
    q_joints_m3h: float = 0.0
    q_bit_m3h: float = 0.0          # injection de sécurité haute pression (charge → BIT → branches froides)
    q_decharge_m3h: float = 0.0
    q_rra_m3h: float = 0.0
    q_deviation_m3h: float = 0.0
    q_urgence_m3h: float = 0.0
    bore_charge_ppm: float = 0.0
    t_charge_c: float = 0.0
    q_echangeur_kw: float = 0.0     # chaleur cédée au RRI par l'échangeur de décharge


class RCV:
    """Charge, décharge, VCT, PTR et bore du primaire."""

    def __init__(self, cfg: RcvCfg, rea: Rea, composants: dict[str, Composant], bore_initial_ppm: float,
                 rho_vct_kg_m3: float) -> None:
        self.cfg = cfg
        self.rea = rea
        self.rho_vct = rho_vct_kg_m3
        v = lambda rep: composants[rep]                     # noqa: E731
        self.pompes: list[Pompe] = [v("RCV_PC1"), v("RCV_PC2")]    # type: ignore[list-item]
        self.fcv121: Vanne = v("RCV_CHARGE")                        # type: ignore[assignment]
        self.isol_charge: Vanne = v("RCV_ISOL_CHARGE")              # type: ignore[assignment]
        self.joints: Vanne = v("RCV_JOINTS")                        # type: ignore[assignment]
        self.lcv: list[Vanne] = [v("RCV_LCV459"), v("RCV_LCV460")]   # type: ignore[list-item]
        self.orifices: list[Vanne] = [v(f"RCV_ORIF{k + 1}") for k in range(len(cfg.orifices_m3h))]  # type: ignore[misc]
        self.isol_enc: Vanne = v("RCV_ISOL_ENC")                    # type: ignore[assignment]
        self.hcv128: Vanne = v("RCV_HCV128")                        # type: ignore[assignment]
        self.deviation: Vanne = v("RCV_DEVIATION")                  # type: ignore[assignment]
        self.asp_vct: Vanne = v("RCV_ASP_VCT")                      # type: ignore[assignment]
        self.asp_ptr: Vanne = v("RCV_ASP_PTR")                      # type: ignore[assignment]
        self.urgence: Vanne = v("RCV_BORI_URG")                     # type: ignore[assignment]
        self.bit: Vanne = v("RIS_BIT")                              # type: ignore[assignment]
        self.etat = EtatRcv(vct_m3=cfg.vct_volume_m3 * cfg.vct_niveau_initial_pct / POURCENT,
                            vct_bore_ppm=bore_initial_ppm, ptr_m3=cfg.ptr.volume_m3,
                            bore_primaire_ppm=bore_initial_ppm)

    # ------------------------------------------------------------------ grandeurs
    @property
    def niveau_vct_pct(self) -> float:
        return POURCENT * self.etat.vct_m3 / self.cfg.vct_volume_m3

    @property
    def niveau_ptr_pct(self) -> float:
        return POURCENT * self.etat.ptr_m3 / self.cfg.ptr.volume_m3

    def nb_pompes(self) -> int:
        return sum(p.etat.en_marche for p in self.pompes)

    def kg_s(self, q_m3h: float) -> float:
        return q_m3h * self.rho_vct / S_PAR_H

    def debit_disponible_m3h(self, p_primaire_bar: float) -> float:
        """Débit total que peuvent fournir les pompes de charge en service (caractéristique quadratique)."""
        pc = self.cfg.pompe_charge
        if self.asp_vct.etat.position <= 0.0 and self.asp_ptr.etat.position <= 0.0:
            return 0.0                                         # pas d'aspiration
        dp = p_primaire_bar + self.cfg.dp_ligne_charge_bar
        x = max(0.0, (pc.dp0_bar - dp) / (pc.dp0_bar - pc.dp_nom_bar))
        return sum(p.etat.vitesse for p in self.pompes) * pc.q_nom_m3h * min(math.sqrt(x), SURDEBIT_MAX)

    def capacite_decharge_m3h(self, p_primaire_bar: float) -> float:
        """Débit de la décharge normale (orifices) à la pression primaire actuelle."""
        c = self.cfg
        chemin = min(v.etat.position for v in self.lcv + [self.isol_enc])
        capacite = sum(v.etat.position * q for v, q in zip(self.orifices, c.orifices_m3h))
        dp = max(0.0, p_primaire_bar - c.p_aval_orifices_bar)
        return chemin * capacite * math.sqrt(dp / (c.p_orifices_ref_bar - c.p_aval_orifices_bar))

    # ------------------------------------------------------------------ pas de calcul
    def calculer(self, dt: float, p_primaire_bar: float, t_decharge_c: float, rra_en_service: bool, rri_ok: bool,
                 masse_primaire_kg: float, apports_bore: list[tuple[float, float]], cp_kj_kgk: float) -> None:
        """apports_bore : autres entrées d'eau dans le primaire (débit kg/s, bore ppm) : accumulateurs, RIS."""
        """Débits, températures, VCT, bore du primaire (un pas)."""
        c, e = self.cfg, self.etat
        sv = c.vct_seuils_pct
        self.rea.calculer(dt, self.niveau_vct_pct, e.bore_primaire_ppm, sv.bas, 0.5 * (sv.bas + sv.haut))
        # charge
        e.q_dispo_m3h = self.debit_disponible_m3h(p_primaire_bar)
        demande_joints = c.joints.injection_m3h * self.joints.etat.position
        demande_charge = c.charge_max_m3h * self.fcv121.etat.position * self.isol_charge.etat.position
        e.q_joints_m3h = min(demande_joints, e.q_dispo_m3h)
        e.q_charge_m3h = min(demande_charge, e.q_dispo_m3h - e.q_joints_m3h)
        e.q_bit_m3h = (e.q_dispo_m3h - e.q_joints_m3h - e.q_charge_m3h) * self.bit.etat.position
        q_pompes = e.q_charge_m3h + e.q_joints_m3h + e.q_bit_m3h
        # aspiration : borication d'urgence et borication REA (acide envoyé à l'aspiration des pompes),
        # complétées par la VCT ou la PTR
        rea = self.rea.etat
        e.q_urgence_m3h = (min(self.rea.cfg.debit_urgence_m3h * self.urgence.etat.position, q_pompes)
                           if rea.acide_m3 > 0.0 else 0.0)
        acide_aspiration = min(rea.q_acide_m3h if rea.mode == "borication" else 0.0, q_pompes - e.q_urgence_m3h)
        acide_vct = rea.q_acide_m3h - acide_aspiration
        q_acide_direct = e.q_urgence_m3h + acide_aspiration
        q_source = q_pompes - q_acide_direct
        depuis_vct = self.asp_vct.etat.position > 0.0 and e.vct_m3 > 0.0
        bore_source = e.vct_bore_ppm if depuis_vct else c.ptr.bore_ppm
        e.bore_charge_ppm = ((q_source * bore_source + q_acide_direct * self.rea.cfg.bore_acide_ppm) / q_pompes
                             if q_pompes > 0.0 else bore_source)
        acide_urgence = e.q_urgence_m3h * dt / S_PAR_H
        self.rea.etat.acide_m3 = max(0.0, self.rea.etat.acide_m3 - acide_urgence)
        # décharge
        e.q_decharge_m3h = self.capacite_decharge_m3h(p_primaire_bar)
        e.q_rra_m3h = c.rra_vers_rcv_m3h * self.hcv128.etat.position if rra_en_service else 0.0
        q_sortie = e.q_decharge_m3h + e.q_rra_m3h
        e.q_deviation_m3h = q_sortie * self.deviation.etat.position
        # températures : régénérateur (la charge se réchauffe sur la décharge), puis échangeur de décharge
        t_vct = c.t_vct_c
        if e.q_charge_m3h > 0.0 and e.q_decharge_m3h > 0.0:
            rapport = min(1.0, e.q_decharge_m3h / e.q_charge_m3h)
            e.t_charge_c = t_vct + c.efficacite_regenerateur * rapport * (t_decharge_c - t_vct)
            t_apres_regen = t_decharge_c - (e.q_charge_m3h / e.q_decharge_m3h) * (e.t_charge_c - t_vct)
        else:
            e.t_charge_c = t_vct
            t_apres_regen = t_decharge_c
        t_sortie = c.t_sortie_echangeur_c if rri_ok else max(t_vct, min(t_apres_regen, c.t_sortie_sans_rri_c))
        e.q_echangeur_kw = (self.kg_s(e.q_decharge_m3h) * cp_kj_kgk * max(0.0, t_apres_regen - t_sortie)
                            + self.kg_s(e.q_rra_m3h) * cp_kj_kgk * max(0.0, t_decharge_c - t_sortie))
        # VCT : entrées (décharge non déviée, retour joints, REA) − aspiration des pompes
        q_retour_joints = e.q_joints_m3h - c.joints.entree_primaire_m3h * min(1.0, e.q_joints_m3h / c.joints.injection_m3h)
        q_vers_vct = q_sortie - e.q_deviation_m3h
        q_in = q_vers_vct + q_retour_joints + acide_vct + rea.q_eau_m3h
        q_out = q_source if depuis_vct else 0.0
        if not depuis_vct:
            e.ptr_m3 = max(0.0, e.ptr_m3 - q_source * dt / S_PAR_H)
        v0 = e.vct_m3
        apport_bore = (q_vers_vct + q_retour_joints) * e.bore_primaire_ppm + acide_vct * self.rea.cfg.bore_acide_ppm
        e.vct_m3 = max(0.0, v0 + (q_in - q_out) * dt / S_PAR_H)
        if e.vct_m3 > 0.0:
            # bilan de bore (mélange parfait) : d(V·C)/dt = Σ q·C − q_out·C
            vc = v0 * e.vct_bore_ppm + (apport_bore - q_out * e.vct_bore_ppm) * dt / S_PAR_H
            e.vct_bore_ppm = max(0.0, vc / e.vct_m3)
        e.effluents_m3 += e.q_deviation_m3h * dt / S_PAR_H
        # bore du primaire : la décharge sort à la concentration du primaire (pas d'effet), les entrées diluent / borent
        q_entree_primaire = self.qm_entree_primaire_kg_s()
        flux = q_entree_primaire * (e.bore_charge_ppm - e.bore_primaire_ppm)
        flux += sum(qm * (bore - e.bore_primaire_ppm) for qm, bore in apports_bore)
        e.bore_primaire_ppm = max(0.0, e.bore_primaire_ppm + dt * flux / masse_primaire_kg)

    # ------------------------------------------------------------------ débits vers le primaire
    def qm_entree_primaire_kg_s(self) -> float:
        """Charge + injection HP (BIT) + part des joints qui entre au primaire."""
        e, j = self.etat, self.cfg.joints
        joints = j.entree_primaire_m3h * min(1.0, e.q_joints_m3h / j.injection_m3h)
        return self.kg_s(e.q_charge_m3h + e.q_bit_m3h + joints)

    def qm_sortie_primaire_kg_s(self) -> float:
        return self.kg_s(self.etat.q_decharge_m3h + self.etat.q_rra_m3h)

    def exporter_etat(self) -> dict[str, Any]:
        return vars(self.etat).copy()

    def importer_etat(self, d: dict[str, Any]) -> None:
        self.etat = EtatRcv(**d)
