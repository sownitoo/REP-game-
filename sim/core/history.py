"""Historique des mesures pour les courbes : tampon circulaire (fenêtre glissante)."""

from __future__ import annotations

from array import array

NAN = float("nan")


class Historique:
    """Enregistre toutes les mesures à pas fixe de temps simulé."""

    def __init__(self, duree_s: float, pas_s: float, dt_s: float) -> None:
        self.pas_s = pas_s
        self.pas_par_echantillon = max(1, round(pas_s / dt_s))
        self.taille = int(duree_s / pas_s)
        self.variables: list[str] = []
        self._t = array("d", [0.0] * self.taille)
        self._v: dict[str, array] = {}
        self._n = 0                       # nombre total d'échantillons enregistrés
        self._compteur = 0                # pas de calcul depuis le dernier échantillon

    def enregistrer(self, t_s: float, mesures: dict[str, float]) -> None:
        self._compteur += 1
        if self._n and self._compteur < self.pas_par_echantillon:
            return
        self._compteur = 0
        if not self.variables:
            self.variables = sorted(mesures)
            self._v = {nom: array("d", [NAN] * self.taille) for nom in self.variables}
        k = self._n % self.taille
        self._t[k] = t_s
        for nom, serie in self._v.items():
            serie[k] = mesures.get(nom, NAN)
        self._n += 1

    def vider(self) -> None:
        self._n = 0
        self._compteur = 0

    def series(self, noms: list[str]) -> dict[str, list[float]]:
        """Temps + séries demandées, dans l'ordre chronologique."""
        n = min(self._n, self.taille)
        debut = self._n % self.taille if self._n > self.taille else 0
        ordre = [(i + debut) % self.taille for i in range(n)]
        sortie: dict[str, list[float]] = {"t_s": [self._t[i] for i in ordre]}
        for nom in noms:
            if nom in self._v:
                sortie[nom] = [self._v[nom][i] for i in ordre]
        return sortie
