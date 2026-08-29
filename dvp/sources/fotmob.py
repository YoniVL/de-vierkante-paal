"""FotMob (vervangt Livescore).

FotMob's data-API (``/api/data/...``) werkt met een Chrome-fingerprint (curl_cffi),
net als Sofascore. Levert per wedstrijd de volledige opstelling mét spelersrating én
een positie-code per speler, waarmee we het veld in vaste lijnen kunnen tekenen:
doelman · verdedigers · verdedigende middenvelders · middenvelders ·
aanvallende middenvelders · aanvallers.
"""

from __future__ import annotations

import datetime as _dt
import urllib.parse

from .. import config
from ..http_client import get_json_impersonated as _get

DATA = "https://www.fotmob.com/api/data"
SITE = "https://www.fotmob.com"
SEARCH = "https://apigw.fotmob.com/searchapi/suggest"

# Actieve ploeg; bovenaan fetch() gezet (verversing draait geserialiseerd).
TEAM = config.FOTMOB_TEAM_ID
CCODE3 = "BEL"

BANDEN = ["GK", "DEF", "DM", "MID", "AM", "FWD"]


def _band(position_id: int | None) -> str:
    """FotMob positie-code -> vaste lijn op het veld."""
    if position_id is None:
        return "MID"
    if position_id < 20:
        return "GK"
    if position_id < 60:   # 30-59: centrale verdedigers, backs, wingbacks
        return "DEF"
    if position_id < 70:   # 60-69: verdedigende middenvelders
        return "DM"
    if position_id < 80:   # 70-79: centrale middenvelders
        return "MID"
    if position_id < 100:  # 80-99: aanvallende / brede middenvelders, flankaanvallers
        return "AM"
    return "FWD"            # 100+: spitsen


def _kort(p: dict) -> str:
    vn, an = (p.get("firstName") or "").strip(), (p.get("lastName") or "").strip()
    if vn and an:
        return f"{vn[0]}. {an}"
    return p.get("name") or "?"


def _minuten(p: dict, *, starter: bool) -> int:
    ev = (p.get("performance") or {}).get("substitutionEvents") or []
    erin = next((e.get("time") for e in ev if e.get("type") == "subIn"), None)
    eruit = next((e.get("time") for e in ev if e.get("type") == "subOut"), None)
    if starter:
        return eruit if eruit is not None else 90
    if erin is not None:
        return max(90 - erin, 1)
    return 0


def _speler(p: dict, *, starter: bool) -> dict:
    perf = p.get("performance") or {}
    events = perf.get("events") or []
    return {
        "naam": p.get("name"),
        "kort": _kort(p),
        "nummer": p.get("shirtNumber"),
        "positie_id": p.get("positionId"),
        "rating": float(perf["rating"]) if perf.get("rating") is not None else None,
        "invaller": not starter,
        "minuten": _minuten(p, starter=starter),
        "doelpunten": sum(1 for e in events if e.get("type") == "goal"),
        "assists": sum(1 for e in events if e.get("type") == "assist"),
        "_x": (p.get("verticalLayout") or {}).get("x", 0.5),
    }


def _zijde(team: dict) -> dict:
    starters = [_speler(p, starter=True) for p in team.get("starters") or []]
    banden: dict[str, list] = {b: [] for b in BANDEN}
    for sp in starters:
        banden[_band(sp["positie_id"])].append(sp)
    for lijst in banden.values():
        lijst.sort(key=lambda s: s["_x"])
    bank = [_speler(p, starter=False) for p in team.get("subs") or []]
    return {
        "formatie": team.get("formation"),
        "veld": [banden[b] for b in BANDEN],
        "basis": starters,
        "bank": bank,
        "coach": (team.get("coach") or {}).get("name"),
    }


def _match(match_id: int | str) -> dict | None:
    try:
        return _get(f"{DATA}/matchDetails?matchId={match_id}", key="fotmob")
    except Exception:
        return None


def _team_overview(team_id: int | str) -> dict | None:
    try:
        return _get(f"{DATA}/teams?id={team_id}&ccode3={CCODE3}", key="fotmob")
    except Exception:
        return None


def zoek_team(naam: str) -> list[dict]:
    """FotMob-ploegen die bij ``naam`` passen: [{id, naam, competitie}]."""
    try:
        data = _get(f"{SEARCH}?term={urllib.parse.quote(naam)}", key="fotmob")
    except Exception:
        return []
    uit: list[dict] = []
    for blok in data.get("teamSuggest", []):
        for opt in blok.get("options", []):
            tekst = opt.get("text", "")
            tid = (opt.get("payload") or {}).get("id")
            if "|" in tekst and tid:
                uit.append({
                    "id": int(tid),
                    "naam": tekst.rsplit("|", 1)[0],
                    "competitie": (opt.get("payload") or {}).get("leagueName", ""),
                })
    return uit


def _kant(md: dict, team_id: int) -> str:
    return "homeTeam" if (md.get("general") or {}).get("homeTeam", {}).get("id") == team_id else "awayTeam"


def _tegenstander_opstelling(volgende_id, tegenstander_id) -> dict | None:
    md = _match(volgende_id) if volgende_id else None
    lu = (md or {}).get("content", {}).get("lineup") if md else None
    if lu and lu.get("homeTeam", {}).get("starters"):
        kant = _kant(md, tegenstander_id)
        zijde = _zijde(lu[kant])
        if lu.get("lineupType") == "standard":
            zijde["herkomst"] = "bevestigde opstelling"
            zijde["herkomst_detail"] = "de opgestelde ploeg voor déze wedstrijd"
        else:
            zijde["herkomst"] = "vermoedelijke opstelling"
            zijde["herkomst_detail"] = "FotMob's voorspelling op basis van de laatste basiself"
        return zijde
    # terugval: laatste match van de tegenstander
    ov = _team_overview(tegenstander_id)
    lm = (ov or {}).get("overview", {}).get("lastMatch")
    if not lm:
        return None
    md = _match(lm["id"])
    lu = (md or {}).get("content", {}).get("lineup")
    if not lu or not lu.get("homeTeam", {}).get("starters"):
        return None
    kant = _kant(md, tegenstander_id)
    zijde = _zijde(lu[kant])
    g = md["general"]
    zijde["herkomst"] = "opstelling van hun vorige wedstrijd"
    zijde["herkomst_detail"] = (
        f"{g['homeTeam']['name']} {lm.get('home',{}).get('score','-')}-"
        f"{lm.get('away',{}).get('score','-')} {g['awayTeam']['name']} "
        f"({(g.get('matchTimeUTCDate') or '')[:10]}) — {g.get('leagueName','')}"
    )
    return zijde


def _zoek_fixture(ov: dict, hint: dict) -> dict | None:
    """Zoek in alle Antwerp-fixtures de match die past bij de hint (datum + tegenstander)."""
    from ..names import kernwoord

    fx = (ov.get("fixtures") or {}).get("allFixtures", {}).get("fixtures", [])
    dag = (hint.get("datum") or "")[:10]
    doelwoorden = {kernwoord(hint.get("thuis") or ""), kernwoord(hint.get("uit") or "")}
    for m in fx:
        mdag = (m.get("status") or {}).get("utcTime", "")[:10]
        namen = {kernwoord((m.get("home") or {}).get("name", "")), kernwoord((m.get("away") or {}).get("name", ""))}
        if mdag == dag and namen == doelwoorden:
            return m
        if namen == doelwoorden and abs_dagen(mdag, dag) <= 1:
            return m
    return None


def abs_dagen(a: str, b: str) -> int:
    try:
        return abs((_dt.date.fromisoformat(a) - _dt.date.fromisoformat(b)).days)
    except ValueError:
        return 99


def fetch(vorige_hint: dict | None = None, ploeg: dict | None = None) -> dict:
    global TEAM, CCODE3
    TEAM = (ploeg or {}).get("fotmob_id") or config.FOTMOB_TEAM_ID
    CCODE3 = (ploeg or {}).get("fotmob_ccode3") or "BEL"

    resultaat: dict = {
        "opgehaald_op": _dt.datetime.now().isoformat(timespec="seconds"),
        "beschikbaar": False,
    }
    if not TEAM:
        resultaat["reden"] = "geen FotMob-ploeg ingesteld"
        return resultaat
    ov = _team_overview(TEAM)
    if not ov:
        resultaat["reden"] = "FotMob niet bereikbaar"
        return resultaat

    overview = ov.get("overview") or {}
    laatste = overview.get("lastMatch") or {}
    volgende = overview.get("nextMatch") or {}

    if vorige_hint and vorige_hint.get("datum"):
        gevonden = _zoek_fixture(ov, vorige_hint)
        if gevonden:
            laatste = gevonden

    if laatste.get("id"):
        md = _match(laatste["id"])
        lu = (md or {}).get("content", {}).get("lineup")
        if lu and lu.get("homeTeam", {}).get("starters"):
            antwerp_thuis = _kant(md, TEAM) == "homeTeam"
            ant = _zijde(lu["homeTeam" if antwerp_thuis else "awayTeam"])
            teg = _zijde(lu["awayTeam" if antwerp_thuis else "homeTeam"])
            resultaat["beschikbaar"] = True
            resultaat["vorige"] = {
                "match_id": laatste["id"],
                "url": SITE + (laatste.get("pageUrl") or "").split("#")[0],
                "antwerp_thuis": antwerp_thuis,
                "opstelling_antwerp": ant,
                "opstelling_tegenstander": teg,
            }
            resultaat["ratings_antwerp"] = {
                sp["naam"]: sp["rating"]
                for sp in ant["basis"] + ant["bank"]
                if sp["naam"] and sp["rating"] is not None
            }

    if volgende.get("id"):
        opp_id = (volgende.get("opponent") or {}).get("id")
        opp = _tegenstander_opstelling(volgende["id"], opp_id)
        if opp:
            resultaat["volgende"] = {"tegenstander_opstelling": opp}

    return resultaat
