"""Sofascore: vorige wedstrijd (uitslag, opstelling, scores, tijdlijn) en
voorbeschouwing op de volgende tegenstander (klassement, vorm, onderlinge balans).
"""

from __future__ import annotations

import datetime as _dt

from .. import config
from ..http_client import get_json_impersonated as _get

API = "https://api.sofascore.com/api/v1"
WEB = "https://www.sofascore.com"

# De actieve ploeg. Wordt bovenaan fetch() gezet op basis van de gekozen ploeg;
# de rest van de module leest deze waarden (de verversing draait geserialiseerd).
TEAM = config.SOFASCORE_TEAM_ID
TEAM_NAAM = config.CLUB_NAAM


def _huidig_seizoen(ut: int) -> int | None:
    try:
        seasons = _get(f"{API}/unique-tournament/{ut}/seasons").get("seasons") or []
        return seasons[0]["id"] if seasons else None
    except Exception:
        return None


def _ts_to_iso(ts: int | None) -> str | None:
    if not ts:
        return None
    return _dt.datetime.fromtimestamp(ts).isoformat(timespec="minutes")


def _event_url(ev: dict) -> str:
    slug = ev.get("slug") or "match"
    cid = ev.get("customId", "")
    return f"{WEB}/football/match/{slug}/{cid}#id:{ev['id']}"


def _team_block(team: dict, score: dict | None) -> dict:
    return {
        "naam": team.get("name"),
        "id": team.get("id"),
        "score": (score or {}).get("current"),
    }


def _is_officieel(e: dict) -> bool:
    """Geen oefenwedstrijd: het toernooi hoort bij een land (competitie/beker/Europees)."""
    ut = (e.get("tournament") or {}).get("uniqueTournament") or {}
    naam = (ut.get("name") or "").lower()
    if ut.get("id") == 853 or "friendly" in naam or "oefen" in naam:
        return False
    return bool((ut.get("category") or {}).get("country"))


def _kies_events() -> tuple[dict | None, dict | None, list[dict]]:
    vorige = None
    volgende = None
    alle: list[dict] = []
    try:
        last = _get(f"{API}/team/{TEAM}/events/last/0")
        officieel = [e for e in last.get("events", []) if _is_officieel(e)]
        alle += officieel
        gespeeld = [e for e in officieel if e.get("status", {}).get("type") == "finished"]
        vorige = gespeeld[-1] if gespeeld else (officieel or [None])[-1]
    except Exception:
        pass
    try:
        nxt = _get(f"{API}/team/{TEAM}/events/next/0")
        toekomst = [e for e in nxt.get("events", []) if _is_officieel(e)]
        alle += toekomst
        volgende = toekomst[0] if toekomst else None
    except Exception:
        pass
    return vorige, volgende, alle


def _competitie_context(events: list[dict]) -> dict | None:
    """De nationale competitie van Antwerp (voor het klassement en seizoensratings).

    Kiest de unieke toernooi-id die het vaakst voorkomt en een echt klassement heeft
    (dus geen beker, geen oefenwedstrijden).
    """
    from collections import Counter

    teller: Counter = Counter()
    info: dict[int, dict] = {}
    for e in events:
        t = e.get("tournament") or {}
        ut = t.get("uniqueTournament") or {}
        uid = ut.get("id")
        seizoen = (e.get("season") or {}).get("id")
        naam = ut.get("name") or ""
        land = ((ut.get("category") or {}).get("country") or {})
        if not uid or not seizoen or not land:
            continue  # oefenwedstrijden hebben geen land
        if any(w in naam.lower() for w in ("cup", "beker", "coupe", "supercup")):
            continue
        teller[uid] += 1
        info.setdefault(uid, {"ut": uid, "seizoen": seizoen, "naam": naam})
        info[uid]["seizoen"] = seizoen  # nieuwste wint (events staan chronologisch)
    if not teller:
        return None
    beste = teller.most_common(1)[0][0]
    return info[beste]


# --- match-statistieken --------------------------------------------------------
_STAT_ROWS = {
    "Ball possession", "Expected goals", "Big chances", "Total shots", "Shots on target",
    "Shots off target", "Corner kicks", "Accurate passes", "Fouls", "Offsides",
    "Yellow cards", "Red cards", "Goalkeeper saves", "Total saves", "Passes",
    "Touches in penalty area", "Big chances scored", "Big chances missed",
    "Tackles won", "Interceptions", "Duels", "Aerial duels", "Dribbles",
}


def _match_statistiek(event_id: int) -> list[dict]:
    try:
        data = _get(f"{API}/event/{event_id}/statistics")
    except Exception:
        return []
    for periode in data.get("statistics", []):
        if periode.get("period") != "ALL":
            continue
        groepen = []
        for grp in periode.get("groups", []):
            rijen = [
                {"naam": it.get("name"), "thuis": it.get("home"), "uit": it.get("away")}
                for it in grp.get("statisticsItems", [])
                if it.get("name") in _STAT_ROWS
            ]
            if rijen:
                groepen.append({"groep": grp.get("groupName"), "rijen": rijen})
        return groepen
    return []


def _scheidsrechter(ev: dict) -> dict | None:
    r = ev.get("referee")
    if not r:
        try:
            detail = _get(f"{API}/event/{ev['id']}")
            r = (detail.get("event", detail) or {}).get("referee")
        except Exception:
            r = None
    if not r or not r.get("name"):
        return None
    games = r.get("games") or 0
    per = lambda n: round(n / games, 2) if games else None  # noqa: E731
    return {
        "naam": r.get("name"),
        "land": (r.get("country") or {}).get("name"),
        "matchen": games,
        "geel_totaal": r.get("yellowCards"),
        "rood_totaal": (r.get("redCards") or 0) + (r.get("yellowRedCards") or 0),
        "geel_per_match": per(r.get("yellowCards") or 0),
        "rood_per_match": per((r.get("redCards") or 0) + (r.get("yellowRedCards") or 0)),
    }


_STREAK_NL = {
    "No losses": "ongeslagen",
    "No wins": "zonder zege",
    "Wins": "op rij gewonnen",
    "Losses": "op rij verloren",
    "Draws": "op rij gelijk",
    "Scored": "op rij gescoord",
    "Conceded": "op rij tegengekregen",
    "Clean sheets": "op rij de nul gehouden",
    "Failed to score": "op rij niet gescoord",
    "More than 1.5 goals": "matchen met +1,5 goals",
    "More than 2.5 goals": "matchen met +2,5 goals",
    "Less than 2.5 goals": "matchen met -2,5 goals",
    "Less than 3.5 cards": "matchen met -3,5 kaarten",
    "Less than 4.5 cards": "matchen met -4,5 kaarten",
    "More than 3.5 cards": "matchen met +3,5 kaarten",
    "Both teams scored": "matchen met BTTS",
    "First to score": "matchen als eerste gescoord",
}


def _reeksen(volgende_ev: dict) -> dict:
    """Kant-en-klare reeksen van Sofascore voor de volgende match."""
    uit: dict = {"algemeen": [], "onderling": []}
    try:
        data = _get(f"{API}/event/{volgende_ev['id']}/team-streaks")
    except Exception:
        return uit
    h_is_antwerp = (volgende_ev.get("homeTeam") or {}).get("id") == TEAM
    teg_naam = (volgende_ev.get("awayTeam") if h_is_antwerp else volgende_ev.get("homeTeam") or {}).get("name")

    def _wie(kant: str) -> str:
        if kant == "both":
            return "beide ploegen"
        thuis = kant == "home"
        return TEAM_NAAM if thuis == h_is_antwerp else (teg_naam or "tegenstander")

    for sleutel, doel in (("general", "algemeen"), ("head2head", "onderling")):
        for item in data.get(sleutel, []):
            naam = item.get("name") or ""
            uit[doel].append({
                "wie": _wie(item.get("team")),
                "tekst": _STREAK_NL.get(naam, naam.lower()),
                "waarde": item.get("value"),
            })
    return uit


def _resultaten(team_id: int, aantal: int = 10) -> list[dict]:
    try:
        data = _get(f"{API}/team/{team_id}/events/last/0")
    except Exception:
        return []
    out = []
    for e in data.get("events", []):
        if e.get("status", {}).get("type") != "finished" or not _is_officieel(e):
            continue
        hs = (e.get("homeScore") or {}).get("current")
        as_ = (e.get("awayScore") or {}).get("current")
        if hs is None or as_ is None:
            continue
        thuis = (e.get("homeTeam") or {}).get("id") == team_id
        gf, ga = (hs, as_) if thuis else (as_, hs)
        out.append({
            "datum": _ts_to_iso(e.get("startTimestamp")),
            "thuis": thuis,
            "gf": gf, "ga": ga,
            "res": "W" if gf > ga else "L" if gf < ga else "D",
            "competitie": (e.get("tournament") or {}).get("name"),
            "tekst": f"{e['homeTeam']['name']} {hs}-{as_} {e['awayTeam']['name']}",
        })
    return out[-aantal:]


def _vorm_detail(resultaten: list[dict]) -> dict:
    laatste5 = resultaten[-5:]
    thuis5 = [r for r in resultaten if r["thuis"]][-5:]
    uit5 = [r for r in resultaten if not r["thuis"]][-5:]

    def _blok(rs: list[dict]) -> dict:
        if not rs:
            return {}
        return {
            "vorm": "".join(r["res"] for r in rs),
            "gf": sum(r["gf"] for r in rs),
            "ga": sum(r["ga"] for r in rs),
            "clean_sheets": sum(1 for r in rs if r["ga"] == 0),
            "n": len(rs),
        }

    # actuele reeksen
    ongeslagen = scoren = 0
    for r in reversed(resultaten):
        if r["res"] != "L":
            ongeslagen += 1
        else:
            break
    for r in reversed(resultaten):
        if r["gf"] > 0:
            scoren += 1
        else:
            break
    return {
        "laatste5": _blok(laatste5),
        "thuis5": _blok(thuis5),
        "uit5": _blok(uit5),
        "ongeslagen": ongeslagen,
        "scoren_op_rij": scoren,
    }


def _topschutters(ut: int, seizoen: int, antwerp_namen: set[str]) -> dict:
    from ..names import normaliseer

    try:
        tp = _get(f"{API}/unique-tournament/{ut}/season/{seizoen}/top-players/overall?limit=15")
    except Exception:
        return {}
    antwerp_norm = {normaliseer(n) for n in antwerp_namen}
    uit: dict = {}
    for kat, sleutel in (("goals", "goals"), ("assists", "assists"), ("goalsAssistsSum", "goalsAssistsSum")):
        uit[kat] = [
            {
                "naam": (it.get("player") or {}).get("name"),
                "waarde": (it.get("statistics") or {}).get(sleutel),
                "wedstrijden": (it.get("statistics") or {}).get("appearances"),
                "antwerp": normaliseer((it.get("player") or {}).get("name", "")) in antwerp_norm,
            }
            for it in (tp.get("topPlayers") or {}).get(kat, [])[:10]
        ]
    return uit


def _formatie_lijnen(formatie: str | None) -> list[int]:
    if not formatie:
        return []
    return [int(x) for x in formatie.split("-") if x.isdigit()]


def _speler_blok(p: dict) -> dict:
    st = p.get("statistics") or {}
    sp = p.get("player") or {}
    return {
        "naam": sp.get("name"),
        "kort": sp.get("shortName") or sp.get("name"),
        "positie": p.get("position"),
        "nummer": p.get("shirtNumber") or p.get("jerseyNumber") or sp.get("jerseyNumber"),
        "invaller": bool(p.get("substitute")),
        "minuten": st.get("minutesPlayed") or 0,
        "rating": float(st["rating"]) if st.get("rating") is not None else None,
        "doelpunten": 0,
        "assists": 0,
    }


# Vaste lijnen op het veld: doelman, verdedigers, verdedigende mid, mid,
# aanvallende mid, aanvallers. Sofascore geeft geen fijne positie-code, dus we
# leiden de lijnen af uit de formatie-string.
BANDEN = ["GK", "DEF", "DM", "MID", "AM", "FWD"]
_FORMATIE_BANDEN = {
    2: ["DEF", "FWD"],
    3: ["DEF", "MID", "FWD"],
    4: ["DEF", "DM", "AM", "FWD"],
    5: ["DEF", "DM", "MID", "AM", "FWD"],
}


def _zijde_opstelling(blok: dict) -> dict:
    """Volledige opstelling van één ploeg: basiself verdeeld over vaste lijnen, plus bank."""
    spelers = [_speler_blok(p) for p in blok.get("players", [])]
    basis = [s for s in spelers if not s["invaller"]][:11]
    bank = [s for s in spelers if s["invaller"]]
    formatie = blok.get("formation")

    banden: dict[str, list] = {b: [] for b in BANDEN}
    if basis:
        banden["GK"] = [basis[0]]
        rest = basis[1:]
        lijnen = _formatie_lijnen(formatie) or [4, 4, 2]
        doelen = _FORMATIE_BANDEN.get(len(lijnen))
        if not doelen:
            doelen = (["DEF", "DM", "MID", "AM", "FWD"] + ["FWD"] * len(lijnen))[: len(lijnen)]
        idx = 0
        for aantal, band in zip(lijnen, doelen):
            banden[band].extend(rest[idx : idx + aantal])
            idx += aantal
        if idx < len(rest):
            banden["FWD"].extend(rest[idx:])

    return {
        "formatie": formatie,
        "basis": basis,
        "bank": bank,
        "veld": [banden[b] for b in BANDEN],
        "ontbrekend": [
            {"naam": (m.get("player") or {}).get("name"), "reden": m.get("reason")}
            for m in blok.get("missingPlayers", [])
        ],
    }


def _haal_lineups(event_id: int) -> dict | None:
    try:
        data = _get(f"{API}/event/{event_id}/lineups")
    except Exception:
        return None
    if not (data.get("home") or {}).get("players"):
        return None
    return {
        "bevestigd": bool(data.get("confirmed")),
        "home": _zijde_opstelling(data.get("home") or {}),
        "away": _zijde_opstelling(data.get("away") or {}),
    }


def _tegenstander_opstelling(tegenstander_id: int, volgende_event_id: int) -> dict | None:
    """Opstelling van de tegenstander: de opgestelde ploeg voor de volgende match
    als die al bevestigd is, anders hoe ze hun laatste wedstrijd begonnen."""
    lu = _haal_lineups(volgende_event_id)
    if lu and lu["bevestigd"]:
        # bepaal welke kant de tegenstander is via het event zelf
        try:
            ev = _get(f"{API}/event/{volgende_event_id}")
            ev = ev.get("event", ev)
            thuis = (ev.get("homeTeam") or {}).get("id") == tegenstander_id
            zijde = lu["home"] if thuis else lu["away"]
            zijde["herkomst"] = "bevestigde opstelling"
            zijde["herkomst_detail"] = "de opgestelde ploeg voor déze wedstrijd"
            return zijde
        except Exception:
            pass
    try:
        tl = _get(f"{API}/team/{tegenstander_id}/events/last/0")
        gespeeld = [e for e in tl.get("events", [])
                    if e.get("status", {}).get("type") == "finished" and _is_officieel(e)]
        if not gespeeld:
            return None
        ev = gespeeld[-1]
        lu = _haal_lineups(ev["id"])
        if not lu:
            return None
        thuis = (ev.get("homeTeam") or {}).get("id") == tegenstander_id
        zijde = lu["home"] if thuis else lu["away"]
        uitslag = (
            f"{ev['homeTeam']['name']} {ev.get('homeScore', {}).get('current', '-')}"
            f"-{ev.get('awayScore', {}).get('current', '-')} {ev['awayTeam']['name']}"
        )
        datum = (_ts_to_iso(ev.get("startTimestamp")) or "")[:10]
        zijde["herkomst"] = "opstelling van hun vorige wedstrijd"
        zijde["herkomst_detail"] = f"{uitslag} ({datum}) — {(ev.get('tournament') or {}).get('name', '')}"
        return zijde
    except Exception:
        return None


def _inc_naam(inc: dict) -> str:
    return (
        (inc.get("player") or {}).get("name")
        or (inc.get("manager") or {}).get("name")
        or inc.get("playerName")
        or "?"
    )


def _inc_minuut(inc: dict) -> int | None:
    t = inc.get("time")
    if isinstance(t, int) and t > 0:
        toegevoegd = inc.get("addedTime") or 0
        return t + toegevoegd if toegevoegd else t
    return inc.get("benchTime") or None


def _tijdlijn(event_id: int, antwerp_thuis: bool) -> list[dict]:
    try:
        data = _get(f"{API}/event/{event_id}/incidents")
    except Exception:
        return []
    uit: list[dict] = []
    for inc in data.get("incidents", []):
        soort = inc.get("incidentType")
        minuut = _inc_minuut(inc)
        is_thuis = bool(inc.get("isHome"))
        basis = {
            "minuut": minuut,
            "antwerp": is_thuis == antwerp_thuis,
            "thuis": is_thuis,
            "stand": "",
        }
        if soort == "goal":
            speler = _inc_naam(inc)
            assist = (inc.get("assist1") or {}).get("name")
            klasse = inc.get("incidentClass")
            extra = " (strafschop)" if klasse == "penalty" else " (owngoal)" if klasse == "ownGoal" else ""
            tekst = f"⚽ {speler}{extra}"
            if assist:
                tekst += f" — assist {assist}"
            uit.append({**basis, "type": "goal", "tekst": tekst,
                        "stand": f"{inc.get('homeScore', '')}-{inc.get('awayScore', '')}"})
        elif soort == "card":
            speler = _inc_naam(inc)
            staf = " (staf)" if inc.get("manager") else ""
            kl = inc.get("incidentClass")
            icoon = "🟨" if kl == "yellow" else "🟥" if kl in ("red", "yellowRed") else "🟨"
            uit.append({**basis, "type": "card", "tekst": f"{icoon} {speler}{staf}"})
        elif soort == "substitution":
            erin = (inc.get("playerIn") or {}).get("name") or "?"
            eruit = (inc.get("playerOut") or {}).get("name") or "?"
            uit.append({**basis, "type": "sub", "tekst": f"🔁 {erin} voor {eruit}"})
    uit.sort(key=lambda x: (x["minuut"] is None, x["minuut"] or 0))
    return uit


def _tel_goals_assists(spelers: list[dict], tijdlijn: list[dict]) -> None:
    """Vul doelpunten/assists per speler in op basis van de wedstrijdtijdlijn."""
    per_naam = {s["naam"]: s for s in spelers}
    for e in tijdlijn:
        if e["type"] != "goal" or not e["antwerp"]:
            continue
        tekst = e["tekst"]
        scorer = tekst.split("⚽ ", 1)[-1].split(" (", 1)[0].split(" — assist", 1)[0].strip()
        if scorer in per_naam:
            per_naam[scorer]["doelpunten"] += 1
        if " — assist " in tekst:
            gever = tekst.split(" — assist ", 1)[1].strip()
            if gever in per_naam:
                per_naam[gever]["assists"] += 1


def _h2h(custom_id: str | None, tegenstander_id: int) -> dict:
    """Volledige onderlinge balans + grootste zege/nederlaag voor Antwerp."""
    if not custom_id:
        return {}
    try:
        data = _get(f"{API}/event/{custom_id}/h2h/events")
    except Exception:
        return {}
    matches = []
    for e in data.get("events", []):
        hs = (e.get("homeScore") or {}).get("current")
        as_ = (e.get("awayScore") or {}).get("current")
        if hs is None or as_ is None or not _is_officieel(e):
            continue
        ant_thuis = (e.get("homeTeam") or {}).get("id") == TEAM
        ant, opp = (hs, as_) if ant_thuis else (as_, hs)
        matches.append(
            {
                "datum": _ts_to_iso(e.get("startTimestamp")),
                "tekst": f"{e['homeTeam']['name']} {hs}-{as_} {e['awayTeam']['name']}",
                "competitie": (e.get("tournament") or {}).get("name"),
                "diff": ant - opp,
                "ant": ant,
                "opp": opp,
            }
        )
    if not matches:
        return {}
    matches.sort(key=lambda m: m["datum"] or "", reverse=True)
    zeges = [m for m in matches if m["diff"] > 0]
    nederlagen = [m for m in matches if m["diff"] < 0]
    return {
        "aantal": len(matches),
        "antwerp_winst": len(zeges),
        "tegenstander_winst": len(nederlagen),
        "gelijk": sum(1 for m in matches if m["diff"] == 0),
        "laatste": matches[:10],
        "grootste_zege": max(zeges, key=lambda m: (m["diff"], m["ant"]), default=None),
        "grootste_nederlaag": min(nederlagen, key=lambda m: (m["diff"], -m["opp"]), default=None),
    }


def _team_seizoen_ratings(ut: int, seizoen: int) -> dict[str, dict]:
    """{spelersnaam: {rating, apps}} voor Antwerp in de competitie (bv. Pro League)."""
    try:
        tp = _get(f"{API}/team/{TEAM}/unique-tournament/{ut}/season/{seizoen}/top-players/overall")
    except Exception:
        return {}
    uit: dict[str, dict] = {}
    for item in (tp.get("topPlayers") or {}).get("rating", []):
        sp = item.get("player") or {}
        st = item.get("statistics") or {}
        if sp.get("name") and st.get("rating") is not None:
            uit[sp["name"]] = {"rating": round(float(st["rating"]), 2), "apps": st.get("appearances")}
    return uit


def _voorbeschouwing(volgende: dict, tegenstander_id: int, comp_ctx: dict | None,
                     antwerp_namen: set[str] | None = None) -> dict:
    out: dict = {"klassement": [], "vorm": {}, "h2h": {}, "tegenstander_sterkhouders": {}}

    volgende_ut = ((volgende.get("tournament") or {}).get("uniqueTournament") or {}).get("id")
    volgende_naam = (volgende.get("tournament") or {}).get("name") or ""
    comp_ut = (comp_ctx or {}).get("ut")
    comp_seizoen = (comp_ctx or {}).get("seizoen")
    out["competitie_volgende"] = {
        "naam": volgende_naam,
        "is_competitie": bool(comp_ut) and volgende_ut == comp_ut,
        "klassement_naam": (comp_ctx or {}).get("naam", ""),
    }

    # Klassement: altijd de nationale competitie (ook bij een beker- of Europese match).
    tegenstander_in_klassement = False
    if comp_ut and comp_seizoen:
        try:
            st = _get(f"{API}/unique-tournament/{comp_ut}/season/{comp_seizoen}/standings/total")
            rows = (st.get("standings") or [{}])[0].get("rows", [])
            for r in rows:
                tid = (r.get("team") or {}).get("id")
                out["klassement"].append(
                    {
                        "positie": r.get("position"),
                        "team": (r.get("team") or {}).get("name"),
                        "gespeeld": r.get("matches"),
                        "gewonnen": r.get("wins"),
                        "gelijk": r.get("draws"),
                        "verloren": r.get("losses"),
                        "dp_voor": r.get("scoresFor"),
                        "dp_tegen": r.get("scoresAgainst"),
                        "saldo": r.get("scoreDiffFormatted"),
                        "punten": r.get("points"),
                        "antwerp": tid == TEAM,
                        "tegenstander": tid == tegenstander_id,
                    }
                )
                if tid == tegenstander_id:
                    tegenstander_in_klassement = True
        except Exception:
            pass
    out["competitie_volgende"]["tegenstander_in_klassement"] = tegenstander_in_klassement

    try:
        pf = _get(f"{API}/event/{volgende['id']}/pregame-form")
        h_is_antwerp = (volgende.get("homeTeam") or {}).get("id") == TEAM
        out["vorm"] = {
            "antwerp": (pf.get("homeTeam") if h_is_antwerp else pf.get("awayTeam") or {}).get("form", []),
            "tegenstander": (pf.get("awayTeam") if h_is_antwerp else pf.get("homeTeam") or {}).get("form", []),
            "antwerp_avg": (pf.get("homeTeam") if h_is_antwerp else pf.get("awayTeam") or {}).get("avgRating"),
            "tegenstander_avg": (pf.get("awayTeam") if h_is_antwerp else pf.get("homeTeam") or {}).get("avgRating"),
        }
    except Exception:
        pass

    out["h2h"] = _h2h(volgende.get("customId"), tegenstander_id)

    volgende_seizoen = (volgende.get("season") or {}).get("id")
    for ut, seizoen in [(comp_ut, comp_seizoen), (volgende_ut, volgende_seizoen)]:
        if not (ut and seizoen) or out["tegenstander_sterkhouders"]:
            continue
        try:
            tp = _get(
                f"{API}/team/{tegenstander_id}/unique-tournament/{ut}/season/{seizoen}/top-players/overall"
            )
            gevonden = {}
            for kat, sleutel in (("rating", "rating"), ("goals", "goals"), ("assists", "assists")):
                gevonden[kat] = [
                    {
                        "naam": (item.get("player") or {}).get("name"),
                        "waarde": (item.get("statistics") or {}).get(sleutel),
                        "wedstrijden": (item.get("statistics") or {}).get("appearances"),
                    }
                    for item in (tp.get("topPlayers") or {}).get(kat, [])[:3]
                ]
            if any(gevonden.values()):
                out["tegenstander_sterkhouders"] = gevonden
        except Exception:
            pass
    # laatste resultaten van de tegenstander
    try:
        tl = _get(f"{API}/team/{tegenstander_id}/events/last/0")
        matches = [e for e in tl.get("events", [])
                   if e.get("status", {}).get("type") == "finished" and _is_officieel(e)][-5:]
        out["tegenstander_vorm_matches"] = [
            {
                "datum": _ts_to_iso(e.get("startTimestamp")),
                "tekst": f"{e['homeTeam']['name']} {e.get('homeScore',{}).get('current','-')}"
                f"-{e.get('awayScore',{}).get('current','-')} {e['awayTeam']['name']}",
                "competitie": (e.get("tournament") or {}).get("name"),
            }
            for e in matches
        ]
    except Exception:
        out["tegenstander_vorm_matches"] = []

    # Scheidsrechter, reeksen, diepere vorm, competitie-topschutters
    out["scheidsrechter"] = _scheidsrechter(volgende)
    out["reeksen"] = _reeksen(volgende)
    ant_res = _resultaten(TEAM)
    teg_res = _resultaten(tegenstander_id)
    out["vorm_detail"] = {"antwerp": _vorm_detail(ant_res), "tegenstander": _vorm_detail(teg_res)}
    if comp_ut and comp_seizoen:
        out["topschutters"] = _topschutters(comp_ut, comp_seizoen, antwerp_namen or set())
    return out


def _haal_event(event_id: str | int) -> dict | None:
    try:
        data = _get(f"{API}/event/{event_id}")
        return data.get("event", data)
    except Exception:
        return None


def fetch(gekozen_event_id: str | None = None, ploeg: dict | None = None) -> dict:
    """Alles wat Sofascore levert, in één blok voor de template."""
    global TEAM, TEAM_NAAM
    TEAM = (ploeg or {}).get("sofascore_id") or config.SOFASCORE_TEAM_ID
    TEAM_NAAM = (ploeg or {}).get("naam") or config.CLUB_NAAM

    vorige_ev, volgende_ev, alle_events = _kies_events()

    if gekozen_event_id and str(gekozen_event_id) != str((vorige_ev or {}).get("id")):
        gekozen = _haal_event(gekozen_event_id)
        if gekozen:
            vorige_ev = gekozen

    # De competitie voor klassement + topschutters: de gekozen competitie van de
    # ploeg (generieke variant), anders afgeleid uit de kalender.
    comp = ((ploeg or {}).get("competitie") or {})
    comp_ctx = None
    if comp.get("sofascore_ut"):
        seizoen = _huidig_seizoen(comp["sofascore_ut"])
        if seizoen:
            comp_ctx = {"ut": comp["sofascore_ut"], "seizoen": seizoen,
                        "naam": comp.get("naam") or ""}
    if not comp_ctx:
        comp_ctx = _competitie_context(alle_events)
    resultaat: dict = {"opgehaald_op": _dt.datetime.now().isoformat(timespec="seconds")}
    if comp_ctx:
        resultaat["competitie"] = comp_ctx

    # keuzelijst van recente matchen
    gezien = set()
    recente = []
    for e in reversed(alle_events):
        if e.get("status", {}).get("type") != "finished" or e["id"] in gezien:
            continue
        gezien.add(e["id"])
        h, a = e["homeTeam"]["name"], e["awayTeam"]["name"]
        hs = (e.get("homeScore") or {}).get("current", "-")
        as_ = (e.get("awayScore") or {}).get("current", "-")
        recente.append({
            "event_id": str(e["id"]),
            "datum": _ts_to_iso(e.get("startTimestamp")),
            "label": f"{(_ts_to_iso(e.get('startTimestamp')) or '')[:10]} · {h} {hs}-{as_} {a} "
                     f"({(e.get('tournament') or {}).get('name', '')})",
        })
    resultaat["recente_matches"] = recente[:14]
    resultaat["gekozen_event"] = str(gekozen_event_id) if gekozen_event_id else None

    if vorige_ev:
        antwerp_thuis = (vorige_ev.get("homeTeam") or {}).get("id") == TEAM
        lineups = _haal_lineups(vorige_ev["id"]) or {}
        antwerp_zijde = lineups.get("home" if antwerp_thuis else "away") or {}
        tegenstander_zijde = lineups.get("away" if antwerp_thuis else "home") or {}
        alle_antwerp = antwerp_zijde.get("basis", []) + antwerp_zijde.get("bank", [])

        tijdlijn = _tijdlijn(vorige_ev["id"], antwerp_thuis)
        _tel_goals_assists(alle_antwerp, tijdlijn)

        # score-tabel: Antwerp-spelers die effectief speelden
        opstelling = sorted(
            [s for s in alle_antwerp if s["minuten"] > 0],
            key=lambda s: (s["invaller"], -s["minuten"]),
        )
        resultaat["vorige"] = {
            "event_id": str(vorige_ev["id"]),
            "url": _event_url(vorige_ev),
            "competitie": (vorige_ev.get("tournament") or {}).get("name"),
            "ronde": (vorige_ev.get("roundInfo") or {}).get("round"),
            "datum": _ts_to_iso(vorige_ev.get("startTimestamp")),
            "thuis": _team_block(vorige_ev.get("homeTeam", {}), vorige_ev.get("homeScore")),
            "uit": _team_block(vorige_ev.get("awayTeam", {}), vorige_ev.get("awayScore")),
            "antwerp_thuis": antwerp_thuis,
            "formatie": antwerp_zijde.get("formatie"),
            "opstelling": opstelling,
            "opstelling_antwerp": antwerp_zijde,
            "opstelling_tegenstander": tegenstander_zijde,
            "ontbrekend": antwerp_zijde.get("ontbrekend", []),
            "tijdlijn": tijdlijn,
            "statistiek": _match_statistiek(vorige_ev["id"]),
        }

    # Antwerp-seizoensrating (ook nodig als Antwerp-namenlijst voor topschutters)
    seizoen_ratings = _team_seizoen_ratings(comp_ctx["ut"], comp_ctx["seizoen"]) if comp_ctx else {}
    if seizoen_ratings:
        resultaat["seizoen_ratings"] = {
            "competitie": comp_ctx["naam"], "spelers": seizoen_ratings,
        }

    if volgende_ev:
        antwerp_thuis = (volgende_ev.get("homeTeam") or {}).get("id") == TEAM
        tegenstander = volgende_ev.get("awayTeam") if antwerp_thuis else volgende_ev.get("homeTeam")
        tegenstander = tegenstander or {}
        resultaat["volgende"] = {
            "event_id": str(volgende_ev["id"]),
            "url": _event_url(volgende_ev),
            "competitie": (volgende_ev.get("tournament") or {}).get("name"),
            "ronde": (volgende_ev.get("roundInfo") or {}).get("round"),
            "datum": _ts_to_iso(volgende_ev.get("startTimestamp")),
            "thuis": _team_block(volgende_ev.get("homeTeam", {}), None),
            "uit": _team_block(volgende_ev.get("awayTeam", {}), None),
            "antwerp_thuis": antwerp_thuis,
            "tegenstander": {"naam": tegenstander.get("name"), "id": tegenstander.get("id")},
        }
        vb = _voorbeschouwing(
            volgende_ev, tegenstander.get("id"), comp_ctx, set(seizoen_ratings)
        )
        vb["tegenstander_opstelling"] = _tegenstander_opstelling(
            tegenstander.get("id"), volgende_ev["id"]
        )
        resultaat["voorbeschouwing"] = vb

    return resultaat
