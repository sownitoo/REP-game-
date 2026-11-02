"""Liste toutes les valeurs marquées « # HYPOTHESE » dans config/plant.yaml.

Usage : python -m sim.tools.hypotheses > docs/HYPOTHESES.md
"""

from __future__ import annotations

import re

from sim.config import CHEMIN_CONFIG

MARQUE = "HYPOTHESE"
LIGNE_CLE = re.compile(r"^(?P<indent>\s*)(?P<tiret>- )?(?P<cle>[\w{}\-]+):\s*(?P<reste>.*)$")


def lister() -> list[tuple[str, str, str]]:
    """(chemin de la clé, valeur, commentaire) pour chaque ligne marquée."""
    pile: list[tuple[int, str]] = []
    sortie = []
    for ligne in CHEMIN_CONFIG.read_text(encoding="utf-8").splitlines():
        m = LIGNE_CLE.match(ligne)
        if not m:
            continue
        indent = len(m["indent"]) + len(m["tiret"] or "")
        cle, reste = m["cle"], m["reste"]
        while pile and pile[-1][0] >= indent:
            pile.pop()
        chemin = ".".join([c for _, c in pile] + [cle])
        if MARQUE in reste:
            valeur, _, commentaire = reste.partition("#")
            texte = commentaire.replace(MARQUE, "").strip(" :—-")
            sortie.append((chemin, valeur.strip(), texte))
        if not reste or reste.startswith("#"):
            pile.append((indent, cle))
    return sortie


def main() -> None:
    lignes = lister()
    print("# Hypothèses (valeurs absentes de la spec)\n")
    print("Générée par `python -m sim.tools.hypotheses` depuis `config/plant.yaml`.\n")
    print(f"{len(lignes)} valeurs marquées `# HYPOTHESE`.\n")
    print("| Clé | Valeur | Justification |")
    print("|---|---|---|")
    for chemin, valeur, texte in lignes:
        print(f"| `{chemin}` | `{valeur.replace('|', '/')}` | {texte.replace('|', '/')} |")


if __name__ == "__main__":
    main()
