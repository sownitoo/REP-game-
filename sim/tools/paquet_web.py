"""Construit web/sim_bundle.zip : le simulateur pour le mode navigateur (Pyodide, hébergement statique).

Contenu : le code sim/ (sans le serveur ni les outils), la config convertie en JSON
(PyYAML n'existe pas dans Pyodide), les tables eau/vapeur et les états sauvegardés.
Le zip est déterministe : un test vérifie qu'il est à jour.

Usage : python -m sim.tools.paquet_web   (à relancer après toute modification de sim/ ou config/)
"""

from __future__ import annotations

import io
import json
import zipfile

import yaml

from sim.config import RACINE

CHEMIN_PAQUET = RACINE / "web" / "sim_bundle.zip"
EXCLUS = {"server.py"}                       # FastAPI n'existe pas dans le navigateur
DOSSIERS_EXCLUS = {"tools", "__pycache__"}
ANNEE_FIXE = 2026                          # horodatage fixe (1er janvier) : zip reproductible
DATE_FIXE = (ANNEE_FIXE, 1, 1, 0, 0, 0)
OCTETS_PAR_KO = 1024


def fichiers() -> list[tuple[str, bytes]]:
    """(chemin dans le zip, contenu) triés."""
    sortie: list[tuple[str, bytes]] = []
    for f in sorted((RACINE / "sim").rglob("*")):
        rel = f.relative_to(RACINE)
        if f.is_dir() or DOSSIERS_EXCLUS & set(rel.parts) or f.name in EXCLUS:
            continue
        if f.suffix == ".py":
            sortie.append((rel.as_posix(), f.read_bytes()))
        elif f.suffix == ".yaml":                                    # scénarios
            donnees = yaml.safe_load(f.read_text(encoding="utf-8"))
            sortie.append((rel.with_suffix(".json").as_posix(), json.dumps(donnees, ensure_ascii=False).encode()))
    config = RACINE / "config"
    plant = yaml.safe_load((config / "plant.yaml").read_text(encoding="utf-8"))
    sortie.append(("config/plant.json", json.dumps(plant, ensure_ascii=False).encode()))
    sortie.append(("config/tables_eau.json", (config / "tables_eau.json").read_bytes()))
    for f in sorted((config / "etats").glob("*.json")):
        sortie.append((f.relative_to(RACINE).as_posix(), f.read_bytes()))
    return sorted(sortie)


def construire() -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
        for nom, contenu in fichiers():
            info = zipfile.ZipInfo(nom, date_time=DATE_FIXE)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, contenu)
    return tampon.getvalue()


def main() -> None:
    contenu = construire()
    CHEMIN_PAQUET.write_bytes(contenu)
    print(f"Paquet écrit : {CHEMIN_PAQUET} ({len(contenu) // OCTETS_PAR_KO} ko, {len(fichiers())} fichiers)")


if __name__ == "__main__":
    main()
