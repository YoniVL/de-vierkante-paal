"""De actieve ploeg: welke club de tool op dit moment voorbereidt.

DVP-variant: altijd Antwerp (uit ``config.py``).
Generieke variant: wat de gebruiker koos, bewaard in de kv-store
(``settings:actieve_ploeg``), met een lijst favorieten om snel te wisselen.
"""

from __future__ import annotations

from . import config, merk, store

_ANTWERP: dict = {
    "naam": config.CLUB_NAAM,
    "sofascore_id": config.SOFASCORE_TEAM_ID,
    "fotmob_id": config.FOTMOB_TEAM_ID,
    "fotmob_ccode3": "BEL",
    "tm_id": config.TRANSFERMARKT_CLUB_ID,
    "tm_slug": config.TRANSFERMARKT_CLUB_SLUG,
    "competitie": {"naam": "Jupiler Pro League", "sofascore_ut": 38, "tm_code": "BE1"},
}

_CACHE_SLEUTELS = (
    "bron:sofascore", "bron:fotmob", "bron:transfermarkt", "bron:voorbeschouwing",
    "settings:vorige_event", "fouten",
)


def _standaard() -> dict:
    vast = merk.merk().get("vaste_ploeg")
    return dict(vast) if vast else dict(_ANTWERP)


def actieve() -> dict:
    """De ploeg die de tool nu voorbereidt (altijd een volledig dict)."""
    gekozen = store.get_kv("settings:actieve_ploeg")
    if isinstance(gekozen, dict) and gekozen.get("sofascore_id"):
        return {**_ANTWERP, **gekozen}  # ontbrekende sleutels aanvullen
    return _standaard()


def sleutel(ploeg: dict | None = None) -> str:
    """Stabiele korte id voor DB-rijen (statistiek-momentopnames, afleveringen)."""
    p = ploeg or actieve()
    return f"ss{p['sofascore_id']}"


def favorieten() -> list[dict]:
    return store.get_kv("settings:favorieten", []) or []


def zet_actief(ploeg: dict, *, ververs: bool = True) -> None:
    store.set_kv("settings:actieve_ploeg", ploeg)
    favs = [f for f in favorieten() if f.get("sofascore_id") != ploeg["sofascore_id"]]
    favs.insert(0, ploeg)
    store.set_kv("settings:favorieten", favs[:12])
    if ververs:
        wis_caches()


def wis_caches() -> None:
    """Bron-data van de vorige ploeg weggooien (wordt opnieuw opgehaald)."""
    store.del_kv(*_CACHE_SLEUTELS)


def is_gekozen() -> bool:
    return isinstance(store.get_kv("settings:actieve_ploeg"), dict)
