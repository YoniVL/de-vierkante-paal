"""Teamstatistieken voor de twee ploegen van de volgende wedstrijd.

Bronnen:
- Sofascore season-statistics (1 request/ploeg): aanval, verdediging, opbouw,
  discipline, xG, strafschoppen, en de thuis/uit-splitsing (aparte standings).
- FotMob shotmap + attacking-zones per competitiematch (gecacht op match-id, een
  seizoen lang): doelpunt-types (gescoord én geïncasseerd), schotkwaliteit,
  minuut-verdeling, de posities voor het veldje en de aanvalszones.
- FotMob team-stats: ranking binnen de competitie.
- Transfermarkt startseite: selectie-profiel (waarde, leeftijd, kadergrootte).

Zit achter een aparte knop; de shotmaps blijven gecacht zodat een herhaalde
verversing enkel de nieuw gespeelde matchen ophaalt.
"""

from __future__ import annotations

import datetime as _dt

from ..http_client import get_json_impersonated as _get
from ..names import normaliseer
from ..store import get_kv, set_kv
from . import transfermarkt

SS = "https://api.sofascore.com/api/v1"
FM = "https://www.fotmob.com/api/data"

_SHOTMAP_KV = "teamstats_shotmap"   # { "_versie":N, "<match_id>": {"h":,"a":,"sh":[[...]],"az":{}} }
_SHOTMAP_VERSIE = 3                 # ophogen = alle gecachte shotmaps opnieuw ophalen

# FotMob-schotsituatie -> Nederlands
_SITUATIE = {
    "Penalty": "Strafschop",
    "FastBreak": "Tegenaanval",
    "FromCorner": "Uit corner",
    "SetPiece": "Stilstaande fase",
    "ThrowInSetPiece": "Uit ingooi",
    "RegularPlay": "Open spel",
}
_LICHAAM = {"RightFoot": "Rechts", "LeftFoot": "Links", "Header": "Kopbal"}

_TIMING_LABELS = ["1-15", "16-30", "31-45", "46-60", "61-75", "76-90+"]


def _timing_bak(minuut: float) -> int:
    return min(5, max(0, int((minuut - 1) // 15)))


# --- Sofascore ------------------------------------------------------------
def _season_stats(team_id: int, ut: int, seizoen: int) -> dict:
    try:
        return _get(
            f"{SS}/team/{team_id}/unique-tournament/{ut}/season/{seizoen}/statistics/overall"
        ).get("statistics") or {}
    except Exception:
        return {}


def _season_kaart(s: dict) -> dict:
    """De ruwe 100+ Sofascore-velden -> de cijfers die de pagina toont (met per-match)."""
    n = s.get("matches") or 0
    pm = (lambda v: round((v or 0) / n, 2) if n else None)
    rood = (s.get("redCards") or 0) + (s.get("yellowRedCards") or 0)
    return {
        "matches": n,
        "rating": round(s["avgRating"], 2) if s.get("avgRating") is not None else None,
        "clean_sheets": s.get("cleanSheets"),
        "balbezit": s.get("averageBallPossession"),
        # aanval
        "goals": s.get("goalsScored"),
        "goals_pm": pm(s.get("goalsScored")),
        "schoten_pm": pm(s.get("shots")),
        "op_doel_pm": pm(s.get("shotsOnTarget")),
        "conversie": (round(100 * (s.get("goalsScored") or 0) / s["shots"], 1)
                      if s.get("shots") else None),
        "grote_kansen": s.get("bigChances"),
        "grote_kansen_gemist": s.get("bigChancesMissed"),
        "corners": s.get("corners"),
        "corners_tegen": s.get("cornersAgainst"),
        "corners_pm": pm(s.get("corners")),
        "xg": round(s["expectedGoals"], 2) if s.get("expectedGoals") is not None else None,
        "xa": round(s["expectedAssists"], 2) if s.get("expectedAssists") is not None else None,
        "goals_prevented": (round(s["goalsPrevented"], 2)
                            if s.get("goalsPrevented") is not None else None),
        # strafschoppen (echte in-play + door de ploeg veroorzaakt)
        "pen_benut": s.get("penaltyGoals"),
        "pen_genomen": s.get("penaltiesTaken"),
        "pen_weg": s.get("penaltiesCommited"),
        "pen_tegen": s.get("penaltyGoalsConceded"),
        # verdediging
        "tegen": s.get("goalsConceded"),
        "tegen_pm": pm(s.get("goalsConceded")),
        "schoten_tegen_pm": pm(s.get("shotsAgainst")),
        "grote_kansen_tegen": s.get("bigChancesAgainst"),
        "tackles_pm": pm(s.get("tackles")),
        "intercepties_pm": pm(s.get("interceptions")),
        "clearances_pm": pm(s.get("clearances")),
        "fouten_naar_goal": s.get("errorsLeadingToGoal"),
        "reddingen_pm": pm(s.get("saves")),
        # opbouw
        "passes_pm": pm(s.get("totalPasses")),
        "pass_pct": (round(s["accuratePassesPercentage"], 1)
                     if s.get("accuratePassesPercentage") is not None else None),
        "lange_bal_pct": (round(s["accurateLongBallsPercentage"], 1)
                          if s.get("accurateLongBallsPercentage") is not None else None),
        "buitenspel_pm": pm(s.get("offsides")),
        # discipline
        "geel": s.get("yellowCards"),
        "rood": rood,
        "geel_pm": pm(s.get("yellowCards")),
        "rood_pm": pm(rood),
    }


def _thuisuit(ut: int, seizoen: int) -> dict:
    """{sofascore_team_id: {"thuis": {...}, "uit": {...}}} uit de aparte standings."""
    uit: dict[int, dict] = {}
    for kant, sleutel in (("home", "thuis"), ("away", "uit")):
        try:
            data = _get(f"{SS}/unique-tournament/{ut}/season/{seizoen}/standings/{kant}")
        except Exception:
            continue
        for r in (data.get("standings") or [{}])[0].get("rows", []):
            tid = (r.get("team") or {}).get("id")
            if not tid:
                continue
            uit.setdefault(tid, {})[sleutel] = {
                "gespeeld": r.get("matches"), "w": r.get("wins"), "g": r.get("draws"),
                "v": r.get("losses"), "dp_voor": r.get("scoresFor"),
                "dp_tegen": r.get("scoresAgainst"), "punten": r.get("points"),
                "positie": r.get("position"),
            }
    return uit


# --- FotMob --------------------------------------------------------------
def _fm_team(team_id: int, ccode3: str) -> dict | None:
    try:
        return _get(f"{FM}/teams?id={team_id}&ccode3={ccode3}", key="fotmob")
    except Exception:
        return None


def _fm_league_fixtures(blob: dict) -> list[int]:
    """Afgewerkte competitiematchen (match-ids)."""
    liga = (blob.get("stats") or {}).get("primaryLeagueId")
    fx = ((blob.get("fixtures") or {}).get("allFixtures") or {}).get("fixtures") or []
    return [
        f["id"] for f in fx
        if f.get("status", {}).get("finished")
        and (not liga or (f.get("tournament") or {}).get("leagueId") == liga)
        and f.get("id")
    ]


def _zones(blok: dict | None) -> dict | None:
    t = (blok or {}).get("total") or {}
    if not t:
        return None
    return {"links": t.get("left", 0), "centraal": t.get("center", 0), "rechts": t.get("right", 0)}


def _shotmap(match_id: int) -> dict | None:
    """Compacte shotmap + aanvalszones van één match voor de cache."""
    try:
        md = _get(f"{FM}/matchDetails?matchId={match_id}", key="fotmob")
    except Exception:
        return None
    g = md.get("general") or {}
    inhoud = md.get("content") or {}
    sm = (inhoud.get("shotmap") or {}).get("shots")
    if not g.get("homeTeam") or sm is None:
        return None
    rijen = []
    for s in sm:
        if not s.get("eventType"):
            continue
        minuut = (s.get("min") or 0) + (s.get("minAdded") or 0)
        # strafschoppenreeks (na verlengingen) telt niet mee — geen echt spelmoment.
        periode = (s.get("period") or "").lower()
        if "shootout" in periode or periode in ("penalties", "penaltyshootout"):
            continue
        if s.get("situation") == "Penalty" and not 0 < minuut <= 130:
            continue
        rijen.append([
            s.get("teamId"),
            1 if s.get("eventType") == "Goal" else 0,
            1 if s.get("isOwnGoal") else 0,
            1 if s.get("isFromInsideBox") else 0,
            s.get("situation") or "RegularPlay",
            s.get("shotType") or "",
            minuut,
            round(float(s.get("expectedGoals") or 0.0), 4),
            round(float(s.get("x") or 0.0), 1),
            round(float(s.get("y") or 0.0), 1),
        ])
    az = inhoud.get("attackingZones") or {}
    return {
        "h": g["homeTeam"]["id"], "a": g["awayTeam"]["id"], "sh": rijen,
        "az": {"h": _zones(az.get("home")), "a": _zones(az.get("away"))},
    }


def _ververs_shotmaps(match_ids: list[int]) -> dict:
    cache = get_kv(_SHOTMAP_KV, {}) or {}
    if cache.get("_versie") != _SHOTMAP_VERSIE:
        cache = {"_versie": _SHOTMAP_VERSIE}   # oud/ander formaat -> alles opnieuw
    veranderd = False
    for mid in match_ids:
        if str(mid) in cache:
            continue
        sm = _shotmap(mid)
        if sm:
            cache[str(mid)] = sm
            veranderd = True
    houden = {str(m) for m in match_ids} | {"_versie"}
    for oud in [k for k in cache if k not in houden]:
        cache.pop(oud)
        veranderd = True
    if veranderd:
        set_kv(_SHOTMAP_KV, cache)
    return cache


def _leeg() -> dict:
    return {"totaal": 0, "fases": {}, "lichaam": {}, "binnen": 0, "buiten": 0}


def _aggregeer(team_id: int, cache: dict) -> dict:
    voor, tegen = _leeg(), _leeg()
    t_voor, t_tegen = [0] * 6, [0] * 6
    xg_voor = xg_tegen = 0.0
    schoten_voor = schoten_tegen = 0
    punten_voor: list[dict] = []
    punten_tegen: list[dict] = []
    zone_som = {"links": 0.0, "centraal": 0.0, "rechts": 0.0}
    zone_n = 0
    matchen = 0

    for sleutel, m in cache.items():
        if sleutel == "_versie" or team_id not in (m["h"], m["a"]):
            continue
        matchen += 1
        kant = "h" if m["h"] == team_id else "a"
        zn = (m.get("az") or {}).get(kant)
        if zn:
            for k in zone_som:
                zone_som[k] += zn.get(k, 0)
            zone_n += 1

        for st, goal, og, box, sit, typ, minuut, xg, x, y in m["sh"]:
            if og:
                begunstigde = m["a"] if st == m["h"] else m["h"]
                if goal:
                    is_v = begunstigde == team_id
                    doel = voor if is_v else tegen
                    doel["totaal"] += 1
                    doel["fases"]["Eigen doelpunt"] = doel["fases"].get("Eigen doelpunt", 0) + 1
                    (t_voor if is_v else t_tegen)[_timing_bak(minuut)] += 1
                continue
            is_voor = st == team_id
            if is_voor:
                xg_voor += xg
                schoten_voor += 1
            else:
                xg_tegen += xg
                schoten_tegen += 1
            if not goal:
                continue
            doel = voor if is_voor else tegen
            fase = _SITUATIE.get(sit, "Open spel")
            doel["totaal"] += 1
            doel["fases"][fase] = doel["fases"].get(fase, 0) + 1
            doel["lichaam"][_LICHAAM.get(typ, "Andere")] = \
                doel["lichaam"].get(_LICHAAM.get(typ, "Andere"), 0) + 1
            doel["binnen" if box else "buiten"] += 1
            (t_voor if is_voor else t_tegen)[_timing_bak(minuut)] += 1
            (punten_voor if is_voor else punten_tegen).append(
                {"x": x, "y": y, "xg": round(xg, 3), "fase": fase})

    zones = ({k: round(v / zone_n) for k, v in zone_som.items()} if zone_n else None)
    return {
        "matchen_met_data": matchen,
        "gescoord": voor,
        "geincasseerd": tegen,
        "timing_labels": _TIMING_LABELS,
        "timing_voor": t_voor,
        "timing_tegen": t_tegen,
        "xg_voor": round(xg_voor, 2),
        "xg_tegen": round(xg_tegen, 2),
        "schoten_voor": schoten_voor,
        "schoten_tegen": schoten_tegen,
        "xg_per_schot_voor": round(xg_voor / schoten_voor, 3) if schoten_voor else None,
        "xg_per_schot_tegen": round(xg_tegen / schoten_tegen, 3) if schoten_tegen else None,
        "punten_voor": punten_voor,
        "punten_tegen": punten_tegen,
        "zones": zones,
    }


def _hoekschot_rendement(doelpunten: dict | None, corners: int | None) -> dict | None:
    if not doelpunten or not corners:
        return None
    goals = (doelpunten["gescoord"]["fases"].get("Uit corner", 0))
    return {"goals": goals, "corners": corners, "pct": round(100 * goals / corners, 1)}


# FotMob-kop (Engels) -> (Nederlands, volgorde, omgekeerd). "omgekeerd" = hoog
# in de ranglijst is slecht (veel tegengoals, veel kaarten ...).
_RANKING_NL: dict[str, tuple[str, int, bool]] = {
    "FotMob rating": ("Teamrating", 1, False),
    "Goals per match": ("Goals per match", 2, False),
    "Expected goals": ("xG (totaal)", 3, False),
    "xG difference": ("xG-verschil", 4, False),
    "Big chances": ("Grote kansen", 5, False),
    "Set piece goals": ("Goals uit stilstaande fase", 6, False),
    "Goals conceded per match": ("Tegengoals per match", 7, True),
    "xG conceded": ("xG tegen", 8, True),
    "Set piece goals conceded": ("Tegengoals uit stilstaande fase", 9, True),
    "Penalties conceded": ("Strafschoppen weggegeven", 10, True),
    "Clean sheets": ("Clean sheets", 11, False),
    "Average possession": ("Balbezit", 12, False),
    "Accurate passes per match": ("Passes per match", 13, False),
    "Tackles per match": ("Tackles per match", 14, False),
    "Interceptions per match": ("Intercepties per match", 15, False),
    "Fouls per match": ("Fouten per match", 16, True),
    "Yellow cards": ("Gele kaarten", 17, True),
    "Red cards": ("Rode kaarten", 18, True),
}


def _ranking(blob: dict, ploegen: int | None) -> list[dict]:
    grens = max(3, round((ploegen or 18) / 4))
    uit = []
    for it in ((blob.get("stats") or {}).get("teams") or []):
        p = it.get("participant") or {}
        kop = it.get("header") or it.get("stat") or ""
        if p.get("rank") is None or kop not in _RANKING_NL:
            continue
        nl, volg, omgekeerd = _RANKING_NL[kop]
        rank = p["rank"]
        # markering: sterk (groen ▲) of zwak (rood ▼) uitschieter, anders niets
        sterk = (rank <= grens) if not omgekeerd else (ploegen and rank > ploegen - grens)
        zwak = (ploegen and rank > ploegen - grens) if not omgekeerd else (rank <= grens)
        uit.append({
            "label": nl, "waarde": p.get("value"), "rank": rank, "volgorde": volg,
            "markering": "sterk" if sterk else "zwak" if zwak else "",
        })
    uit.sort(key=lambda r: r["volgorde"])
    return uit


# --- Transfermarkt ------------------------------------------------------
def _tm_ids(naam: str, competitie: str | None) -> tuple[int, str] | None:
    gecacht = get_kv(f"club:tm:{naam.lower()}")
    if gecacht:
        return tuple(gecacht)
    try:
        return transfermarkt.zoek_club(naam, competitie)
    except Exception:
        return None


# --- competitie per ploeg --------------------------------------------
def _comp_van_ploeg(ss_id: int, standaard: dict) -> dict:
    """De competitie waarin deze ploeg dit seizoen speelt (voor season-stats +
    standings). Nodig als de volgende match een beker- of Europees duel is: dan
    is de tegenstander niet onze competitie en heeft die daar geen cijfers.
    Valt terug op ``standaard`` (onze competitie)."""
    from .sofascore import _competitie_context
    try:
        events = _get(f"{SS}/team/{ss_id}/events/last/0").get("events", [])
    except Exception:
        events = []
    ctx = _competitie_context(events) if events else None
    if ctx and ctx.get("ut") and ctx.get("seizoen"):
        return {"ut": ctx["ut"], "seizoen": ctx["seizoen"],
                "naam": ctx.get("naam") or standaard.get("naam", "")}
    return dict(standaard)


# --- ploeg-koppeling ---------------------------------------------------
def _overlap(a: str | None, b: str | None) -> bool:
    return bool(set(normaliseer(a or "").split()) & set(normaliseer(b or "").split()))


def _zoek_fm(naam: str) -> int | None:
    from .fotmob import zoek_team
    treffers = [o for o in zoek_team(naam) if _overlap(o["naam"], naam)]
    return treffers[0]["id"] if treffers else None


# --- publiek ----------------------------------------------------------
def fetch(sofascore_blob: dict, ploeg: dict | None = None) -> dict:
    from .. import ploeg as _ploeg_mod

    so = sofascore_blob or {}
    volgende = so.get("volgende") or {}
    comp = so.get("competitie") or {}
    ut, seizoen = comp.get("ut"), comp.get("seizoen")
    eigen = ploeg or _ploeg_mod.actieve()
    teg = volgende.get("tegenstander") or {}

    onze_comp = {"ut": ut, "seizoen": seizoen, "naam": comp.get("naam")
                 or (eigen.get("competitie") or {}).get("naam") or ""}
    out: dict = {
        "opgehaald_op": _dt.datetime.now().isoformat(timespec="seconds"),
        "competitie": onze_comp["naam"],
        "ploegen": [],
        "status": "ok",
    }
    if not (volgende and teg.get("id") and ut and seizoen):
        out["status"] = {"code": "leeg",
                         "tekst": "geen volgende competitiewedstrijd bekend — "
                                  "teamstatistieken niet beschikbaar"}
        return out

    eigen_thuis = bool(volgende.get("antwerp_thuis"))
    ccode3 = eigen.get("fotmob_ccode3") or "BEL"

    # FotMob-blob van de eigen ploeg (ranking, fixtures én de tegenstander-id)
    eigen_fm = _fm_team(eigen.get("fotmob_id"), ccode3) if eigen.get("fotmob_id") else None
    opp_fm_id = None
    if eigen_fm:
        nm = ((eigen_fm.get("overview") or {}).get("nextMatch") or {}).get("opponent") or {}
        if nm.get("id") and _overlap(nm.get("name"), teg["naam"]):
            opp_fm_id = nm["id"]
    opp_fm_id = opp_fm_id or _zoek_fm(teg["naam"])
    opp_fm = _fm_team(opp_fm_id, ccode3) if opp_fm_id else None

    # Elke ploeg z'n eigen competitie: bij een beker-/Europees duel speelt de
    # tegenstander niet in onze competitie en heeft die daar geen cijfers.
    opp_comp = _comp_van_ploeg(teg["id"], onze_comp)
    zelfde = opp_comp["ut"] == onze_comp["ut"]
    if zelfde:
        opp_comp["naam"] = onze_comp["naam"]   # zelfde competitie -> zelfde naam
    out["zelfde_competitie"] = zelfde

    thuisuit = _thuisuit(onze_comp["ut"], onze_comp["seizoen"])
    grootte = {onze_comp["ut"]: len(thuisuit) or None}
    if not zelfde:
        tu2 = _thuisuit(opp_comp["ut"], opp_comp["seizoen"])
        grootte[opp_comp["ut"]] = len(tu2) or None
        thuisuit = {**thuisuit, **tu2}

    # shotmaps van beide ploegen samen (ontdubbeld) ophalen/cachen
    alle_ids: list[int] = []
    for blob in (eigen_fm, opp_fm):
        if blob:
            alle_ids += _fm_league_fixtures(blob)
    cache = _ververs_shotmaps(sorted(set(alle_ids)))

    spec = [
        {"rol": "thuis" if eigen_thuis else "uit", "naam": eigen["naam"],
         "ss_id": eigen["sofascore_id"], "fm": eigen_fm, "fm_id": eigen.get("fotmob_id"),
         "comp": onze_comp, "tm": (eigen.get("tm_id"), eigen.get("tm_slug"))},
        {"rol": "uit" if eigen_thuis else "thuis", "naam": teg["naam"],
         "ss_id": teg["id"], "fm": opp_fm, "fm_id": opp_fm_id,
         "comp": opp_comp, "tm": _tm_ids(teg["naam"], opp_comp["naam"])},
    ]

    for p in spec:
        pc = p["comp"]
        n_ploegen = grootte.get(pc["ut"])
        seizoen_kaart = _season_kaart(_season_stats(p["ss_id"], pc["ut"], pc["seizoen"]))
        doelpunten = _aggregeer(p["fm_id"], cache) if p["fm_id"] else None
        tm_id, tm_slug = p["tm"] or (None, None)
        out["ploegen"].append({
            "rol": p["rol"],
            "naam": p["naam"],
            "sofascore_id": p["ss_id"],
            "competitie": {"naam": pc["naam"], "ploegen": n_ploegen},
            "seizoen": seizoen_kaart,
            "thuisuit": thuisuit.get(p["ss_id"], {}),
            "doelpunten": doelpunten,
            "hoekschot": _hoekschot_rendement(doelpunten, seizoen_kaart.get("corners")),
            "ranking": _ranking(p["fm"], n_ploegen) if p["fm"] else [],
            "selectie": (transfermarkt.club_profiel(tm_id, tm_slug)
                         if tm_id and tm_slug else None),
        })

    out["ploegen"].sort(key=lambda x: 0 if x["rol"] == "thuis" else 1)
    if not any(pl["seizoen"].get("matches") for pl in out["ploegen"]):
        out["status"] = {"code": "leeg",
                         "tekst": "Sofascore gaf geen seizoenscijfers voor deze ploegen"}
    return out
