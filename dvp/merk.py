"""Welke variant draait er: de DVP-versie (vast op Antwerp) of de generieke
("Aftrap", je kiest zelf een ploeg)?

De build-scripts leggen optioneel een ``merk.json`` naast de app:

    {"app_naam": "Aftrap", "toon_kiezer": true, "vaste_ploeg": null, "poort": 8757,
     "accent": "#20c063", "accent_diep": "#17a552"}

De poort wordt door config.py gelezen (niet hier), zodat DVP (8756) en Aftrap
(8757) tegelijk kunnen draaien. ``accent`` (+ optioneel ``accent_diep``) geeft de
variant een eigen kleur; ontbreekt het, dan blijft het DVP-koraalrood staan.

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


def toon_whoscored() -> bool:
    """WhoScored-kolom tonen? Standaard: wel in de DVP-variant, niet in de generieke."""
    return bool(merk().get("whoscored", not toon_kiezer()))


_DVP_ACCENT = "#ff4d67"


def thema() -> dict | None:
    """Kleuroverschrijvingen voor deze variant, of ``None`` voor het DVP-standaardthema.

    De templates zetten hiermee een handvol CSS-variabelen (`--rood`, `--rood-diep`,
    `--ant`, `--ant-bg`) opnieuw; de rest van de stijl blijft gedeeld.
    """
    accent = merk().get("accent")
    if not accent or accent == _DVP_ACCENT:
        return None
    diep = merk().get("accent_diep") or accent
    return {"accent": accent, "accent_diep": diep, "accent_zwak": _naar_rgba(accent, 0.14)}


def _naar_rgba(hexkleur: str, alpha: float) -> str:
    h = hexkleur.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return f"rgba(255,77,103,{alpha})"
    return f"rgba({r},{g},{b},{alpha})"
