"""Spelernamen koppelen tussen bronnen (Sofascore, FotMob, Transfermarkt).

Sofascore-opstelling is de 'master'. Andere bronnen worden daar tegenaan gematcht:
1. exacte match op genormaliseerde volledige naam
2. handmatige alias (config + runtime)
3. match op achternaam + eerste letter voornaam
4. match op enkel achternaam als die uniek is
"""

from __future__ import annotations

import re
import unicodedata

from . import config

_CLUB_STOPWOORDEN = {
    "fc", "kv", "krc", "rsc", "sk", "vv", "royal", "koninklijke", "cercle", "club",
    "sporting", "union", "st", "sint", "the", "de", "raal", "kaa", "kvc", "rwd",
    "afc", "cf", "sc", "ac", "as", "us", "calcio", "cd", "sd", "u18", "u19", "u21", "u23",
}


def normaliseer(naam: str) -> str:
    if not naam:
        return ""
    zonder_accent = "".join(
        c for c in unicodedata.normalize("NFKD", naam) if not unicodedata.combining(c)
    )
    schoon = "".join(c if c.isalnum() or c.isspace() else " " for c in zonder_accent)
    return " ".join(schoon.lower().split())


def kernwoord(naam: str) -> str:
    """Meest onderscheidende woord uit een ploegnaam (voor matching tussen bronnen)."""
    zonder = "".join(c for c in unicodedata.normalize("NFKD", naam) if not unicodedata.combining(c))
    woorden = [w for w in re.findall(r"[a-z]+", zonder.lower()) if w not in _CLUB_STOPWOORDEN]
    return max(woorden, key=len) if woorden else normaliseer(naam)


def clubs_gelijk(a: str, b: str) -> bool:
    if not a or not b:
        return False
    na, nb = normaliseer(a), normaliseer(b)
    if na == nb or na in nb or nb in na:
        return True
    return kernwoord(a) == kernwoord(b)


def _sleutels(genormaliseerd: str) -> tuple[str, str]:
    """(achternaam, 'voorletter achternaam') voor een genormaliseerde naam."""
    delen = genormaliseerd.split()
    if not delen:
        return "", ""
    achternaam = delen[-1]
    voorletter = delen[0][0] if len(delen) > 1 else ""
    return achternaam, (f"{voorletter} {achternaam}" if voorletter else achternaam)


class NaamKoppelaar:
    """Bouw op met de master-namen, zoek dan externe namen op."""

    def __init__(self, master_namen: list[str], extra_aliassen: dict[str, str] | None = None) -> None:
        self._aliassen = {**config.SPELER_ALIASSEN, **(extra_aliassen or {})}
        self._exact: dict[str, str] = {}
        self._voorletter: dict[str, list[str]] = {}
        self._achternaam: dict[str, list[str]] = {}
        for naam in master_namen:
            norm = normaliseer(naam)
            self._exact[norm] = naam
            achter, voorletter = _sleutels(norm)
            self._voorletter.setdefault(voorletter, []).append(naam)
            self._achternaam.setdefault(achter, []).append(naam)

    def koppel(self, externe_naam: str) -> str | None:
        """Geef de master-naam terug die bij ``externe_naam`` hoort, of None."""
        norm = normaliseer(externe_naam)
        if not norm:
            return None
        if norm in self._exact:
            return self._exact[norm]

        alias = self._aliassen.get(norm)
        if alias and normaliseer(alias) in self._exact:
            return self._exact[normaliseer(alias)]

        achter, voorletter = _sleutels(norm)
        kandidaten = self._voorletter.get(voorletter, [])
        if len(kandidaten) == 1:
            return kandidaten[0]
        kandidaten = self._achternaam.get(achter, [])
        if len(kandidaten) == 1:
            return kandidaten[0]
        return None
