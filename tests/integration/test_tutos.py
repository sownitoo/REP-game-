"""Tutos guidés : le contenu est cohérent avec le modèle, et chaque automatisme annoncé arrive vraiment.

Chaque tuto est rejoué sans interface : actions faites, puis observations avec les mêmes points d'arrêt
que dans le jeu. Si un automatisme attendu n'apparaît pas (modèle modifié, motif cassé), le test échoue.
"""

from __future__ import annotations

import re

import pytest

from sim.config import RACINE
from sim.core.engine import ARRET_FIN, Simulateur
from sim.interface import creer_simulateur, etat_ui
from sim.tutos.chargement import Tuto, centrale_tuto, lire_catalogue, lister_tutos

TUTOS = lister_tutos()
WEB = RACINE / "web"


def ids_affichables() -> set[str]:
    """Repères qu'on peut mettre en surbrillance : composants + repères écrits dans les schémas + blocs."""
    s = creer_simulateur()
    ids = set(etat_ui(s.centrale, s)["composants"])
    for f in (WEB / "synoptics").glob("*.js"):
        ids |= set(re.findall(r'"([A-Z][A-Z0-9_]+)"', f.read_text(encoding="utf-8")))
    blocs = re.findall(r'^\s*\["(\w+)", "\w+", ', (WEB / "synoptics" / "ensemble.js").read_text(encoding="utf-8"), re.M)
    return ids | {f"bloc:{b}" for b in blocs}


def onglets() -> set[str]:
    return set(re.findall(r'data-onglet="(\w+)"', (WEB / "index.html").read_text(encoding="utf-8")))


def test_t_catalogue_coherent() -> None:
    cat = lire_catalogue()
    s = creer_simulateur()
    mesures, affichables, tabs = s.centrale.mesures, ids_affichables(), onglets()
    for e in cat.explications:
        re.compile(e.motif)
        assert not e.onglet or e.onglet in tabs, (e.id, e.onglet)
        assert set(e.voir) <= affichables, (e.id, set(e.voir) - affichables)
        assert all(m[0] in mesures for m in e.mesures), (e.id, [m[0] for m in e.mesures if m[0] not in mesures])


@pytest.mark.parametrize("t", TUTOS, ids=[t.id for t in TUTOS])
def test_t_contenu_coherent(t: Tuto) -> None:
    cat = lire_catalogue().par_id()
    c = centrale_tuto(t)
    affichables, tabs = ids_affichables(), onglets()
    assert t.etapes and t.etapes[-1].genre == "lecture", "un tuto se termine par un bilan"
    for e in t.etapes:
        assert not e.onglet or e.onglet in tabs, (e.titre, e.onglet)
        assert set(e.voir) <= affichables, (e.titre, set(e.voir) - affichables)
        assert all(m[0] in c.mesures for m in e.mesures), (e.titre, [m[0] for m in e.mesures if m[0] not in c.mesures])
        if e.action:
            assert e.action.cible in c.commandables, e.action.cible
            assert e.action.action in c.commandables[e.action.cible].commandes(), e.action
        if e.observer:
            assert set(e.observer.attendus) <= set(cat), set(e.observer.attendus) - set(cat)
            assert e.observer.acceleration in c.cfg.simulation.accelerations


def jouer(t: Tuto) -> list[list[str]]:
    """Rejoue le tuto ; renvoie, pour chaque observation, les automatismes vus (dans l'ordre)."""
    cat = lire_catalogue()
    c = centrale_tuto(t)
    sim = Simulateur(c, c.cfg.simulation)
    vus_par_observation = []
    for e in t.etapes:
        if e.action:
            r = c.commande(e.action.cible, e.action.action, e.action.valeur)
            assert r.ok, (e.titre, r.raisons)
        if e.observer:
            sim.observer(cat.motifs(e.observer.attendus), e.observer.duree_s)
            vus: list[str] = []
            while ARRET_FIN not in vus:
                c.pas()
                if sim._verifier_arrets():
                    vus += [sim.arret["id"]] + [a["id"] for a in sim.file]   # type: ignore[index]
                    sim.file = []
                    sim.continuer()
            vus_par_observation.append(vus[:-1])
            assert not c.pzr.etat.hors_domaine
    return vus_par_observation


@pytest.mark.lent
@pytest.mark.parametrize("t", [t for t in TUTOS if any(e.observer for e in t.etapes)],
                         ids=[t.id for t in TUTOS if any(e.observer for e in t.etapes)])
def test_t_automatismes_annonces(t: Tuto) -> None:
    vus = jouer(t)
    observations = [e.observer for e in t.etapes if e.observer]
    for obs, v in zip(observations, vus):
        manquants = [a for a in obs.attendus if a not in v]
        assert not manquants, f"automatismes annoncés mais pas vus : {manquants} (vus : {v})"
