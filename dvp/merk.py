"""Welke variant draait er: de DVP-versie (vast op Antwerp) of de generieke
("Aftrap", je kiest zelf een ploeg)?

De build-scripts leggen optioneel een ``merk.json`` naast de app:

    {"app_naam": "Aftrap", "toon_kiezer": true, "vaste_ploeg": null}

Geen bestand  ->  DVP-gedrag (ontwikkelopstelling en de bestaande Windows-build).
"""

from __future__ import annotations

import json
from functools import lru_cache

from . import config

_DVP_DEFAULT = {
    "app_naam": "De Vierkante Paal",
    "toon_kiezer": False,
    # in de DVP-variant komt de vaste ploeg uit config.py (zie ploeg.py)
    "vaste_ploeg": None,
}


@lru_cache(maxsize=1)
def merk() -> dict:
    try:
        data = json.loads((config.BASE_DIR / "merk.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return dict(_DVP_DEFAULT)
    return {**_DVP_DEFAULT, **data}


def app_naam() -> str:
    return merk()["app_naam"]


def toon_kiezer() -> bool:
    return bool(merk()["toon_kiezer"])
