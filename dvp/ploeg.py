"""De actieve ploeg: welke club de tool op dit moment voorbereidt.

DVP-variant: altijd Antwerp (uit ``config.py``).
Generieke variant: wat de gebruiker koos, bewaard in de kv-store
(``settings:actieve_ploeg``), met een lijst ploegen om snel te wisselen
(``settings:ploegen``): een paar vastgeprikt + de recent gebruikte.
"""

from __future__ import annotations

import datetime as _dt

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
    "bron:teamstats", "settings:vorige_event", "fouten",
)

_MAX_RECENT = 8


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


# --- de opgeslagen ploegenlijst -------------------------------------------
def ploegen() -> list[dict]:
    """De ruwe opgeslagen lijst (met migratie van de oude 'favorieten')."""
    lst = store.get_kv("settings:ploegen")
    if lst is None:
        oud = store.get_kv("settings:favorieten", []) or []
        lst = [{**p, "vast": False, "laatst": ""} for p in oud]
        if lst:
            store.set_kv("settings:ploegen", lst)
    return lst or []


def _bewaar(lst: list[dict]) -> None:
    store.set_kv("settings:ploegen", lst)


def lijst() -> list[dict]:
    """Voor de weergave: vastgeprikte eerst, dan recent (op datum), recent tot 8."""
    alle = ploegen()
    vast = [p for p in alle if p.get("vast")]
    los = sorted((p for p in alle if not p.get("vast")),
                 key=lambda p: p.get("laatst") or "", reverse=True)
    return vast + los[:_MAX_RECENT]


def bekend(sofascore_id: int) -> dict | None:
    """De opgeslagen (al gekoppelde) ploeg met dit Sofascore-id, of None."""
    for p in ploegen():
        if p.get("sofascore_id") == sofascore_id:
            return p
    return None


def prik(sofascore_id: int, vast: bool) -> None:
    lst = ploegen()
    for p in lst:
        if p.get("sofascore_id") == sofascore_id:
            p["vast"] = bool(vast)
    _bewaar(lst)


def verwijder(sofascore_id: int) -> None:
    if sofascore_id == actieve().get("sofascore_id"):
        return
    _bewaar([p for p in ploegen() if p.get("sofascore_id") != sofascore_id])


# --- wisselen ------------------------------------------------------------
def zet_actief(ploeg: dict, *, ververs: bool = True) -> None:
    nu = _dt.datetime.now().isoformat(timespec="seconds")
    lst = ploegen()
    bestaand = next((p for p in lst if p.get("sofascore_id") == ploeg["sofascore_id"]), None)
    entry = {**ploeg, "vast": bool(bestaand and bestaand.get("vast")), "laatst": nu}
    lst = [p for p in lst if p.get("sofascore_id") != ploeg["sofascore_id"]]
    lst.insert(0, entry)
    _bewaar(lst)
    store.set_kv("settings:actieve_ploeg", ploeg)
    if ververs:
        wis_caches()


def wis_caches() -> None:
    """Bron-data van de vorige ploeg weggooien (wordt opnieuw opgehaald)."""
    store.del_kv(*_CACHE_SLEUTELS)


def is_gekozen() -> bool:
    return isinstance(store.get_kv("settings:actieve_ploeg"), dict)
