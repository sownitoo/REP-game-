"""Logiques de vote k/n (1/2, 2/3, 2/4…)."""

from __future__ import annotations


def vote(regle: str, voies: list[bool]) -> bool:
    """Vrai si au moins k voies sur n sont actives (règle « k/n »)."""
    k, n = (int(x) for x in regle.split("/"))
    if len(voies) != n:
        raise ValueError(f"vote {regle} : {len(voies)} voies fournies")
    return sum(voies) >= k
