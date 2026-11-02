"""Historique des mesures pour les courbes : tampon circulaire numpy (fenêtre glissante)."""

from __future__ import annotations

import numpy as np


class Historique:
    """Enregistre toutes les mesures à pas fixe de temps simulé."""

    def __init__(self, duree_s: float, pas_s: float) -> None:
        self.pas_s = pas_s
        self.taille = int(duree_s / pas_s)
        self.variables: list[str] = []
        self._index: dict[str, int] = {}
        self._t = np.zeros(self.taille)
        self._v = np.zeros((0, self.taille))
        self._n = 0                       # nombre total d'échantillons enregistrés
        self._prochain_t_s: float | None = None

    def enregistrer(self, t_s: float, mesures: dict[str, float]) -> None:
        if self._prochain_t_s is not None and t_s < self._prochain_t_s:
            return
        if not self.variables:
            self.variables = sorted(mesures)
            self._index = {k: i for i, k in enumerate(self.variables)}
            self._v = np.zeros((len(self.variables), self.taille))
        k = self._n % self.taille
        self._t[k] = t_s
        for nom, i in self._index.items():
            self._v[i, k] = mesures.get(nom, np.nan)
        self._n += 1
        self._prochain_t_s = t_s + self.pas_s

    def vider(self) -> None:
        self._n = 0
        self._prochain_t_s = None

    def series(self, noms: list[str]) -> dict[str, list[float]]:
        """Temps + séries demandées, dans l'ordre chronologique."""
        n = min(self._n, self.taille)
        debut = self._n % self.taille if self._n > self.taille else 0
        ordre = (np.arange(n) + debut) % self.taille
        sortie: dict[str, list[float]] = {"t_s": self._t[ordre].tolist()}
        for nom in noms:
            if nom in self._index:
                sortie[nom] = self._v[self._index[nom], ordre].tolist()
        return sortie
