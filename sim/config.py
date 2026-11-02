"""Chargement de config/plant.yaml en dataclasses typées, avec validation.

- Les gabarits sont fusionnés dans les composants (`gabarit: nom`).
- Tout repère contenant « {b} » est dupliqué pour chaque boucle.
- Une clé inconnue ou manquante lève une ErreurConfig (pas de faute de frappe silencieuse).
"""

from __future__ import annotations

import copy
import types
import typing
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import Any

import yaml

RACINE = Path(__file__).resolve().parent.parent
CHEMIN_CONFIG = RACINE / "config" / "plant.yaml"
MARQUE_BOUCLE = "{b}"

Table = list[list[float]]


class ErreurConfig(Exception):
    """Erreur dans config/plant.yaml."""


# =============================================================================
# Sections
# =============================================================================
@dataclass
class MetaCfg:
    version: str
    nom: str


@dataclass
class SimulationCfg:
    dt_s: float
    accelerations: list[int]
    historique_duree_s: float
    historique_pas_s: float
    diffusion_periode_s: float
    tick_reel_s: float
    budget_calcul_pct: float
    journal_max: int
    p_atm_bar: float


@dataclass
class FlashCfg:
    tolerance_lnp: float
    pas_derivee_lnp: float
    iterations_max: int


@dataclass
class ReseauNumCfg:
    tolerance_kg_s: float
    iterations_max: int
    recherche_lineaire_max: int
    pas_max_bar: float
    zone_lineaire_bar: float
    fuite_vanne_fermee_kg_s_bar: float
    fuite_clapet_kg_s_bar: float
    regularisation_jacobien: float


@dataclass
class CollecteurNumCfg:
    tolerance_kg_s: float
    iterations_max: int


@dataclass
class NumeriqueCfg:
    table_p_min_bar: float
    table_p_max_bar: float
    table_nb_points: int
    table_t_pas_c: float
    flash: FlashCfg
    reseau: ReseauNumCfg
    collecteur: CollecteurNumCfg
    alarmes_hysteresis_pct: float
    iterations_initialisation: int
    duree_stabilisation_s: float


@dataclass
class PointNominalCfg:
    p_source_mw: float
    tmoy_c: float
    p_gv_bar: float
    niveau_gv_pct: float
    qm_vapeur_kg_s: float
    t_alim_c: float
    p_collecteur_bar: float


@dataclass
class ResiduelleCfg:
    a: float
    b: float
    t_fonctionnement_s: float


@dataclass
class CoeurCfg:
    beta_pcm: float
    lambda_s: float
    rho_au_pcm: float
    residuelle: ResiduelleCfg


@dataclass
class SourceV0Cfg:
    p_nom_mw: float
    capacite_thermique_mj_c: float
    tref_programme_c: Table
    mode_initial: str
    kp_mw_c: float
    ti_s: float
    vitesse_max_pct_min: float
    p_max_pct: float


@dataclass
class NiveauGECfg:
    v_bas_m3: float
    v_plage_m3: float
    k_bulles: float
    tau_sejour_s: float
    tau_bulles_s: float
    filtre_dpdt_s: float
    voies: int
    retard_mesure_s: float


@dataclass
class SeuilsGVCfg:
    tres_bas_pct: float
    tres_haut_pct: float
    vote: str


@dataclass
class GVCfg:
    boucles: list[int]
    ua_mw_c: float
    masse_assechement_t: float
    v_secondaire_m3: float
    debit_vapeur_nom_kg_s: float
    niveau_ge: NiveauGECfg
    programme_niveau_pct: Table
    seuils: SeuilsGVCfg


@dataclass
class LigneVapeurCfg:
    qm_nom_kg_s: float
    dp_nom_bar: float
    p_nom_bar: float
    limiteur_kg_s: float
    fraction_bypass_viv: float


@dataclass
class SoupapesCfg:
    tarages_bar: list[float]
    capacite_kg_s: float
    fermeture_pct: float


@dataclass
class VdaCfg:
    capacite_kg_s: float
    p_ref_bar: float


@dataclass
class VapeurCfg:
    ligne: LigneVapeurCfg
    soupapes: SoupapesCfg
    vda: VdaCfg


@dataclass
class RegulationChargeCfg:
    rampe_pct_min: float
    echelon_max_pct: float
    kp: float
    ti_s: float


@dataclass
class RegulationVitesseCfg:
    rampe_pct_min: float
    kp: float
    ti_s: float


@dataclass
class CouplageCfg:
    ecart_vitesse_max_pct: float


@dataclass
class TurbineCfg:
    debit_nom_kg_s: float
    p_admission_nom_bar: float
    ouverture_nom: float
    eta_isentropique: float
    fraction_soutirage: float
    part_travail_soutirage: float
    rendement_alternateur: float
    p_elec_nom_mw: float
    vitesse_nom_tr_min: float
    constante_inertie_s: float
    puissance_apparente_mva: float
    pertes_ventilation_pct: float
    vannes_arret: int
    temps_fermeture_arret_s: float
    temps_ouverture_arret_s: float
    temps_course_reglage_s: float
    regulation_charge: RegulationChargeCfg
    regulation_vitesse: RegulationVitesseCfg
    couplage: CouplageCfg


@dataclass
class RegulationGctCfg:
    consigne_bar: float
    bande_bar: float


@dataclass
class GctCfg:
    groupes: int
    capacite_groupe_kg_s: float
    p_ref_bar: float
    temps_course_s: float
    regulation: RegulationGctCfg


@dataclass
class CondenseurCfg:
    t_mer_c: float
    cp_eau_mer_kj_kgk: float
    rho_eau_mer_kg_m3: float
    ua_mw_c: float
    capacite_thermique_mj_c: float
    p_incondensables_bar: float
    t_max_c: float


@dataclass
class PuitsCfg:
    volume_m3: float
    hauteur_m: float
    hauteur_aspiration_m: float
    niveau_initial_pct: float


@dataclass
class CstCfg:
    volume_m3: float
    volume_initial_m3: float
    volume_mini_m3: float
    hauteur_m: float
    t_c: float


@dataclass
class RechauffeursCfg:
    abp_sortie_c: Table
    ahp_sortie_c: Table
    tau_s: float


@dataclass
class RepriseCfg:
    pompes: list[str]
    capacite_pompe_pct: float
    p_plein_debit_bar: float
    p_arret_bar: float


@dataclass
class PosteEauCfg:
    rechauffeurs: RechauffeursCfg
    reprise: RepriseCfg


# ----------------------------------------------------------------- composants
@dataclass
class PompeCfg:
    type: str
    systeme: str
    q_nom_m3h: float
    temps_demarrage_s: float
    temps_ralentissement_s: float
    h_nom_m: float | None = None
    h0_m: float | None = None
    alim: str | None = None
    entrainement: str | None = None
    vitesse_variable: bool = False
    vitesse_min: float | None = None
    vitesse_max: float | None = None


@dataclass
class VanneCfg:
    type: str                         # Valve (tout ou rien) | ControlValve (régulée)
    systeme: str
    actionneur: str                   # MOV (motorisée) | AOV (pneumatique)
    temps_course_s: float
    kv_max: float | None = None       # vannes eau (m³/h sous 1 bar, d = 1)
    capacite_kg_s: float | None = None  # vannes vapeur (débit critique à p_ref)
    p_ref_bar: float | None = None
    position_repli: str | None = None  # AOV : fermee | ouverte
    reserve_air_min: float | None = None
    alim: str | None = None
    air: str | None = None


@dataclass
class ClapetCfg:
    type: str
    systeme: str
    kv_max: float


@dataclass
class ResistanceCfg:
    type: str
    systeme: str
    dp_nom_bar: float
    q_nom_m3h: float
    rho_nom_kg_m3: float


ComposantCfg = PompeCfg | VanneCfg | ClapetCfg | ResistanceCfg
TYPES_COMPOSANTS: dict[str, type] = {
    "Pump": PompeCfg,
    "Valve": VanneCfg,
    "ControlValve": VanneCfg,
    "CheckValve": ClapetCfg,
    "Resistance": ResistanceCfg,
}


@dataclass
class BrancheCfg:
    id: str
    de: str
    vers: str
    elements: list[Any]               # repères ; une sous-liste = vannes en parallèle


@dataclass
class ReseauCfg:
    frontieres: list[str]
    noeuds: list[str]
    injections: list[str]
    branches: list[BrancheCfg]


# ----------------------------------------------------------------- régulations
@dataclass
class RegNiveauGVCfg:
    kp_debit_pct_par_pct: float
    ti_s: float
    integrale_max_pct: float
    trim_kp: float
    trim_ti_s: float
    dp_min_bar: float
    debit_max_pct: float


@dataclass
class RegDpAppCfg:
    consigne_bar: Table
    kp_par_bar: float
    ti_s: float


@dataclass
class RegVdaCfg:
    consigne_bar: float
    bande_bar: float


@dataclass
class RegPuitsCfg:
    consigne_pct: float
    kp_par_pct: float
    ti_s: float


@dataclass
class RegRecircCfg:
    ouvre_m3h: float
    ferme_m3h: float


@dataclass
class RegulationsCfg:
    niveau_gv: RegNiveauGVCfg
    dp_app: RegDpAppCfg
    vda: RegVdaCfg
    puits: RegPuitsCfg
    cex_recirculation: RegRecircCfg


# ----------------------------------------------------------------- logique
@dataclass
class P7Cfg:
    puissance_max_pct: float
    charge_turbine_max_pct: float


@dataclass
class C9Cfg:
    p_cond_max_bar: float
    p_cond_perte_bar: float
    crf_mini: int


@dataclass
class IsolAreAuCfg:
    tmoy_max_c: float


@dataclass
class DeclAppCfg:
    p_aspiration_min_bar: float
    p_refoulement_max_bar: float
    temporisation_s: float


@dataclass
class DeclTurbineCfg:
    p_cond_max_bar: float
    survitesse_pct: float


@dataclass
class DeclCexCfg:
    niveau_puits_min_pct: float


@dataclass
class OuvertureVivCfg:
    dp_max_bar: float


@dataclass
class LogiqueCfg:
    p7: P7Cfg
    c9: C9Cfg
    isolement_are_au: IsolAreAuCfg
    declenchement_app: DeclAppCfg
    declenchement_turbine: DeclTurbineCfg
    declenchement_cex: DeclCexCfg
    ouverture_viv: OuvertureVivCfg


@dataclass
class AlarmeCfg:
    id: str
    mesure: str
    priorite: int
    libelle: str
    haut: float | None = None
    bas: float | None = None


@dataclass
class CentraleCfg:
    meta: MetaCfg
    simulation: SimulationCfg
    numerique: NumeriqueCfg
    point_nominal: PointNominalCfg
    coeur: CoeurCfg
    source_v0: SourceV0Cfg
    generateurs_vapeur: GVCfg
    vapeur: VapeurCfg
    turbine: TurbineCfg
    gct_c: GctCfg
    condenseur: CondenseurCfg
    puits: PuitsCfg
    cst: CstCfg
    poste_eau: PosteEauCfg
    composants: dict[str, ComposantCfg]
    reseaux: dict[str, ReseauCfg]
    regulations: RegulationsCfg
    logique: LogiqueCfg
    alarmes: list[AlarmeCfg]


# =============================================================================
# Construction générique dataclass ← dict
# =============================================================================
def construire(cls: Any, donnees: Any, chemin: str) -> Any:
    """Construit une instance du type `cls` à partir des données YAML."""
    origine = typing.get_origin(cls)
    if cls is Any:
        return donnees
    if origine in (typing.Union, types.UnionType):
        options = typing.get_args(cls)
        if donnees is None and type(None) in options:
            return None
        erreurs = []
        for opt in options:
            if opt is type(None):
                continue
            try:
                return construire(opt, donnees, chemin)
            except ErreurConfig as e:
                erreurs.append(str(e))
        raise ErreurConfig(f"{chemin} : aucun type ne convient ({'; '.join(erreurs)})")
    if origine is list:
        (elem,) = typing.get_args(cls)
        if not isinstance(donnees, list):
            raise ErreurConfig(f"{chemin} : liste attendue")
        return [construire(elem, d, f"{chemin}[{i}]") for i, d in enumerate(donnees)]
    if origine is dict:
        _, val = typing.get_args(cls)
        if not isinstance(donnees, dict):
            raise ErreurConfig(f"{chemin} : dictionnaire attendu")
        return {k: construire(val, v, f"{chemin}.{k}") for k, v in donnees.items()}
    if is_dataclass(cls):
        if not isinstance(donnees, dict):
            raise ErreurConfig(f"{chemin} : section attendue")
        indices = typing.get_type_hints(cls)
        noms = {f.name for f in fields(cls)}
        inconnues = set(donnees) - noms
        if inconnues:
            raise ErreurConfig(f"{chemin} : clé(s) inconnue(s) {sorted(inconnues)}")
        kwargs = {}
        for f in fields(cls):
            if f.name in donnees:
                kwargs[f.name] = construire(indices[f.name], donnees[f.name], f"{chemin}.{f.name}")
        try:
            return cls(**kwargs)
        except TypeError as e:
            raise ErreurConfig(f"{chemin} : {e}") from e
    if cls is float:
        if isinstance(donnees, bool) or not isinstance(donnees, (int, float)):
            raise ErreurConfig(f"{chemin} : nombre attendu, reçu {donnees!r}")
        return float(donnees)
    if cls is int:
        if isinstance(donnees, bool) or not isinstance(donnees, int):
            raise ErreurConfig(f"{chemin} : entier attendu, reçu {donnees!r}")
        return donnees
    if cls in (str, bool):
        if not isinstance(donnees, cls):
            raise ErreurConfig(f"{chemin} : {cls.__name__} attendu, reçu {donnees!r}")
        return donnees
    raise ErreurConfig(f"{chemin} : type non géré {cls}")


# =============================================================================
# Prétraitement : boucles et gabarits
# =============================================================================
def _remplacer(valeur: Any, b: int) -> Any:
    """Remplace « {b} » par le numéro de boucle dans toutes les chaînes."""
    if isinstance(valeur, str):
        return valeur.replace(MARQUE_BOUCLE, str(b))
    if isinstance(valeur, list):
        return [_remplacer(v, b) for v in valeur]
    if isinstance(valeur, dict):
        return {k: _remplacer(v, b) for k, v in valeur.items()}
    return valeur


def _contient_marque(valeur: Any) -> bool:
    if isinstance(valeur, str):
        return MARQUE_BOUCLE in valeur
    if isinstance(valeur, list):
        return any(_contient_marque(v) for v in valeur)
    if isinstance(valeur, dict):
        return any(_contient_marque(v) for v in valeur.values())
    return False


def developper_boucles(valeur: Any, boucles: list[int]) -> Any:
    """Duplique pour chaque boucle les entrées dont le repère contient « {b} »."""
    if isinstance(valeur, dict):
        sortie: dict[str, Any] = {}
        for k, v in valeur.items():
            if MARQUE_BOUCLE in k:
                for b in boucles:
                    sortie[k.replace(MARQUE_BOUCLE, str(b))] = _remplacer(v, b)
            else:
                sortie[k] = developper_boucles(v, boucles)
        return sortie
    if isinstance(valeur, list):
        sortie_l: list[Any] = []
        for v in valeur:
            if _contient_marque(v) and (isinstance(v, (str, dict))):
                sortie_l.extend(_remplacer(v, b) for b in boucles)
            else:
                sortie_l.append(developper_boucles(v, boucles))
        return sortie_l
    return valeur


def _fusionner_gabarits(composants: dict[str, Any], gabarits: dict[str, Any]) -> dict[str, Any]:
    sortie = {}
    for repere, spec in composants.items():
        spec = dict(spec)
        nom = spec.pop("gabarit", None)
        if nom is not None:
            if nom not in gabarits:
                raise ErreurConfig(f"composants.{repere} : gabarit inconnu « {nom} »")
            base = copy.deepcopy(gabarits[nom])
            base.update(spec)
            spec = base
        sortie[repere] = spec
    return sortie


def _construire_composants(brut: dict[str, Any]) -> dict[str, ComposantCfg]:
    sortie: dict[str, ComposantCfg] = {}
    for repere, spec in brut.items():
        type_c = spec.get("type")
        if type_c not in TYPES_COMPOSANTS:
            raise ErreurConfig(f"composants.{repere} : type inconnu « {type_c} »")
        sortie[repere] = construire(TYPES_COMPOSANTS[type_c], spec, f"composants.{repere}")
    return sortie


def _verifier_references(cfg: CentraleCfg) -> None:
    """Toutes les références de repères doivent exister."""
    for nom_r, reseau in cfg.reseaux.items():
        connus = set(reseau.frontieres) | set(reseau.noeuds)
        for br in reseau.branches:
            for extremite in (br.de, br.vers):
                if extremite not in connus:
                    raise ErreurConfig(f"reseaux.{nom_r}.{br.id} : nœud inconnu « {extremite} »")
            for el in br.elements:
                for rep in (el if isinstance(el, list) else [el]):
                    if rep not in cfg.composants:
                        raise ErreurConfig(f"reseaux.{nom_r}.{br.id} : composant inconnu « {rep} »")
    for rep in cfg.poste_eau.reprise.pompes:
        if rep not in cfg.composants:
            raise ErreurConfig(f"poste_eau.reprise : composant inconnu « {rep} »")


def charger_config(chemin: Path = CHEMIN_CONFIG) -> CentraleCfg:
    """Lit, développe et valide config/plant.yaml."""
    with open(chemin, encoding="utf-8") as f:
        brut = yaml.safe_load(f)
    boucles = brut["generateurs_vapeur"]["boucles"]
    gabarits = brut.pop("gabarits", {})
    brut = developper_boucles(brut, boucles)
    composants_bruts = _fusionner_gabarits(brut.pop("composants"), gabarits)
    composants = _construire_composants(composants_bruts)
    brut["composants"] = {}
    cfg = construire(CentraleCfg, brut, "plant")
    cfg.composants = composants
    _verifier_references(cfg)
    return cfg
