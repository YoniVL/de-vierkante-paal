"""Zwaardere voorbeschouwing-data (aparte knop, 24u-cache):
blessures/schorsingen van de tegenstander + ex-speler-connecties tussen de ploegen.
Haalt ~8-12 Transfermarkt-pagina's op, dus niet bij elke verversing.
"""

from __future__ import annotations

import datetime as _dt

from . import transfermarkt
from .. import config
from ..store import get_kv, set_kv


def _tm_club(naam: str) -> tuple[int, str] | None:
    if not naam:
        return None
    sleutel = f"club:tm:{naam.lower()}"
    gecacht = get_kv(sleutel)
    if gecacht:
        return tuple(gecacht)
    gevonden = transfermarkt.zoek_club(naam)
    if gevonden:
        set_kv(sleutel, list(gevonden))
    return gevonden


def _squad_namen(zijde: dict | None) -> list[str]:
    if not zijde:
        return []
    return [p["naam"] for p in (zijde.get("basis", []) + zijde.get("bank", [])) if p.get("naam")]


def fetch(sofascore_blob: dict, antwerp_squad: list[str], ploeg: dict | None = None) -> dict:
    so = sofascore_blob or {}
    eigen_id = (ploeg or {}).get("tm_id") or config.TRANSFERMARKT_CLUB_ID
    eigen_slug = (ploeg or {}).get("tm_slug") or config.TRANSFERMARKT_CLUB_SLUG
    eigen_kader = transfermarkt.kader(eigen_id, eigen_slug) if (eigen_id and eigen_slug) else []
    if eigen_kader:
        antwerp_squad = eigen_kader
    volgende = so.get("volgende") or {}
    vb = so.get("voorbeschouwing") or {}
    tegenstander = volgende.get("tegenstander") or {}
    naam = tegenstander.get("naam")

    out: dict = {
        "opgehaald_op": _dt.datetime.now().isoformat(timespec="seconds"),
        "tegenstander_id": tegenstander.get("id"),
        "tegenstander_naam": naam,
        "uitval": None,
        "connecties": None,
        "status": "ok",   # geen tegenstander = niks te doen, geen fout
    }
    if not naam:
        return out

    club = _tm_club(naam)
    # Huidige selectie van de tegenstander: volledige Transfermarkt-kader indien mogelijk,
    # anders de opstelling van hun laatste match.
    opp_squad = _squad_namen(vb.get("tegenstander_opstelling"))
    if club:
        try:
            tm_kader = transfermarkt.kader(club[0], club[1])
            if tm_kader:
                opp_squad = tm_kader
        except Exception:
            pass
        try:
            out["uitval"] = transfermarkt.blessures_schorsingen(club[0], club[1])
        except Exception:
            pass

    try:
        out["connecties"] = transfermarkt.connecties(
            naam, opp_squad, antwerp_squad, eigen_tm=(eigen_id, eigen_slug)
        )
    except Exception:
        pass

    if out["connecties"] is None and out["uitval"] is None:
        out["status"] = {"code": "leeg",
                         "tekst": f"kon geen Transfermarkt-gegevens ophalen voor {naam}"}
    return out
