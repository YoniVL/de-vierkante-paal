"""Spelersstatistieken voor de twee ploegen van de volgende wedstrijd.

Bronnen:
- Sofascore: selectie met profielgegevens, seizoenscijfers per speler (~140 velden)
  en de vaardigheidsradar (met gemiddelde van de positie).
- FotMob: statistieken met percentielen t.o.v. de competitie (ook per 90 minuten),
  blessure-info. FotMob-spelers worden via de naam aan de Sofascore-selectie gekoppeld.

Zit achter een aparte knop (net als teamstats): de eerste keer zijn dat zo'n 100
verzoeken, daarna is het resultaat een halve dag gecacht.
"""

from __future__ import annotations

import datetime as _dt
import math

from ..http_client import get_json_impersonated as _get
from ..names import NaamKoppelaar
from ..store import get_kv
from . import teamstats

SS = "https://www.sofascore.com/api/v1"
FM = "https://www.fotmob.com/api/data"

POS_NL = {"G": "Keeper", "D": "Verdediger", "M": "Middenvelder", "F": "Aanvaller"}
_POS_VOLGORDE = {"G": 0, "D": 1, "M": 2, "F": 3}


# --- hulpjes ---------------------------------------------------------------
def _getal(x, nd: int = 2):
    """Afronden; hele getallen als int, ontbrekend als None."""
    if x is None or isinstance(x, bool):
        return None
    try:
        r = round(float(x), nd)
    except (TypeError, ValueError):
        return None
    return int(r) if r == int(r) else r


def _p90(waarde, minuten, nd: int = 2):
    if waarde is None or not minuten or minuten < 90:
        return None
    return _getal(waarde * 90 / minuten, nd)


def _datum(ts) -> _dt.datetime | None:
    try:
        return _dt.datetime.fromtimestamp(int(ts), _dt.timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


# --- Sofascore: kerncijfers per positie -----------------------------------------------
# (label, Sofascore-veld, soort)   soort: n = totaal + per 90, d = idem met decimalen,
#                                  t = enkel totaal, % = percentage
_AANVAL = [
    ("Goals", "goals", "n"), ("xG", "expectedGoals", "d"), ("Schoten", "totalShots", "n"),
    ("Schoten op doel", "shotsOnTarget", "n"), ("Conversie", "goalConversionPercentage", "%"),
    ("Grote kansen gemist", "bigChancesMissed", "t"),
    ("Aanrakingen in de 16 van de tegenstander", "touchesInOppBox", "n"),
    ("Dribbels gelukt", "successfulDribbles", "n"), ("Dribbel %", "successfulDribblesPercentage", "%"),
]
_CREATIE = [
    ("Assists", "assists", "n"), ("xA", "expectedAssists", "d"), ("Sleutelpassen", "keyPasses", "n"),
    ("Grote kansen gecreëerd", "bigChancesCreated", "t"),
    ("Geslaagde voorzetten", "accurateCrosses", "n"), ("Voorzet %", "accurateCrossesPercentage", "%"),
]
_OPBOUW = [
    ("Passes", "totalPasses", "n"), ("Passnauwkeurigheid", "accuratePassesPercentage", "%"),
    ("Passes in het laatste derde", "accurateFinalThirdPasses", "n"),
    ("Lange ballen %", "accurateLongBallsPercentage", "%"),
    ("Aanrakingen", "touches", "n"), ("Balverlies", "possessionLost", "n"),
]
_VERDEDIGING = [
    ("Tackles gewonnen", "tacklesWon", "n"), ("Intercepties", "interceptions", "n"),
    ("Wegwerkacties", "clearances", "n"), ("Ballen veroverd", "ballRecovery", "n"),
    ("Geblokte schoten", "outfielderBlocks", "n"),
    ("Duels gewonnen %", "totalDuelsWonPercentage", "%"),
    ("Luchtduels gewonnen %", "aerialDuelsWonPercentage", "%"),
    ("Gepasseerd", "dribbledPast", "n"), ("Fouten die tot een goal leidden", "errorLeadToGoal", "t"),
]
_FYSIEK = [
    ("Overtredingen", "fouls", "n"), ("Fouten afgedwongen", "wasFouled", "n"),
    ("Gele kaarten", "yellowCards", "t"), ("Rode kaarten", "redCards", "t"),
    ("Afstand per 90 (km)", "kilometersCoveredPer90", "d"),
    ("Sprints per 90", "numberOfSprintsPer90", "d"), ("Topsnelheid (km/u)", "topSpeed", "d"),
]
_KEEPEN = [
    ("Reddingen", "saves", "n"), ("Reddingspercentage", "savesPercentage", "%"),
    ("Goals tegen", "goalsConceded", "n"), ("xGOT tegen", "expectedGoalsOnTargetConceded", "d"),
    ("Clean sheets", "cleanSheet", "t"), ("Strafschoppen gestopt", "penaltySave", "t"),
    ("Strafschoppen tegen", "penaltyFaced", "t"), ("Hoge ballen", "highClaims", "n"),
    ("Uitkomsten", "runsOut", "n"), ("Weggeboksd", "punches", "n"),
    ("Fouten die tot een goal leidden", "errorLeadToGoal", "t"),
]
_KEEPER_OPBOUW = [
    ("Passes", "totalPasses", "n"), ("Passnauwkeurigheid", "accuratePassesPercentage", "%"),
    ("Lange ballen %", "accurateLongBallsPercentage", "%"), ("Aanrakingen", "touches", "n"),
]

_GROEPEN = {
    "G": [("Keepen", _KEEPEN), ("Opbouw", _KEEPER_OPBOUW), ("Fysiek & discipline", _FYSIEK)],
    "D": [("Verdedigen", _VERDEDIGING), ("Opbouw", _OPBOUW), ("Creatie", _CREATIE),
          ("Aanval", _AANVAL), ("Fysiek & discipline", _FYSIEK)],
    "M": [("Opbouw", _OPBOUW), ("Creatie", _CREATIE), ("Aanval", _AANVAL),
          ("Verdedigen", _VERDEDIGING), ("Fysiek & discipline", _FYSIEK)],
    "F": [("Aanval", _AANVAL), ("Creatie", _CREATIE), ("Opbouw", _OPBOUW),
          ("Verdedigen", _VERDEDIGING), ("Fysiek & discipline", _FYSIEK)],
}


def _kern(pos: str, s: dict) -> list[dict]:
    """De ruwe Sofascore-velden -> [{groep, rijen:[{label, waarde, p90, eenheid}]}]."""
    minuten = s.get("minutesPlayed") or 0
    uit = []
    for titel, spec in _GROEPEN.get(pos, _GROEPEN["M"]):
        rijen = []
        for label, veld, soort in spec:
            v = s.get(veld)
            if v is None:
                continue
            if soort == "%":
                rijen.append({"label": label, "waarde": _getal(v, 1), "p90": None, "eenheid": "%"})
            elif soort == "t":
                rijen.append({"label": label, "waarde": _getal(v, 0), "p90": None, "eenheid": ""})
            else:
                nd = 2 if soort == "d" else 0
                rijen.append({"label": label, "waarde": _getal(v, nd if soort == "d" else 0),
                              "p90": _p90(v, minuten), "eenheid": ""})
        if pos == "G" and titel == "Keepen":
            xgot, tegen = s.get("expectedGoalsOnTargetConceded"), s.get("goalsConceded")
            if xgot is not None and tegen is not None:
                rijen.insert(4, {"label": "Goals voorkomen (xGOT − tegen)",
                                 "waarde": _getal(xgot - tegen, 2), "p90": None, "eenheid": ""})
        if rijen:
            uit.append({"groep": titel, "rijen": rijen})
    return uit


# --- radar (inline SVG-geometrie, zodat de template geen goniometrie hoeft) ----------
_RADAR_UIT = [("attacking", "Aanvallen"), ("technical", "Technisch"), ("tactical", "Tactisch"),
              ("defending", "Verdedigen"), ("creativity", "Creativiteit")]
_RADAR_KEEPER = [("saves", "Reddingen"), ("anticipation", "Anticipatie"),
                 ("ballDistribution", "Opbouw"), ("aerial", "Lucht"), ("tactical", "Tactisch")]
_CX, _CY, _R = 140.0, 102.0, 66.0


def _punt(i: int, n: int, straal: float) -> tuple[float, float]:
    hoek = -math.pi / 2 + 2 * math.pi * i / n
    return _CX + straal * math.cos(hoek), _CY + straal * math.sin(hoek)


def _pts(waarden: list[float]) -> str:
    n = len(waarden)
    return " ".join("%.1f,%.1f" % _punt(i, n, _R * max(0.0, min(100.0, w)) / 100) for i, w in enumerate(waarden))


def _radar(pos: str, blob: dict | None) -> dict | None:
    if not blob:
        return None
    assen = _RADAR_KEEPER if pos == "G" else _RADAR_UIT
    nu = next((o for o in blob.get("playerAttributeOverviews") or [] if o.get("yearShift") == 0), None)
    if not nu or any(nu.get(k) is None for k, _ in assen):
        return None
    gem = next((o for o in blob.get("averageAttributeOverviews") or [] if o.get("yearShift") == 0), None)
    gem_ok = bool(gem) and all(gem.get(k) is not None for k, _ in assen)
    n = len(assen)
    labels = []
    for i, (k, tekst) in enumerate(assen):
        x, y = _punt(i, n, _R + 14)
        anker = "middle" if abs(x - _CX) < 6 else ("start" if x > _CX else "end")
        labels.append({"x": round(x, 1), "y": round(y + 3, 1), "tekst": tekst,
                       "anker": anker, "waarde": nu[k]})
    return {
        "speler": _pts([nu[k] for k, _ in assen]),
        "gem": _pts([gem[k] for k, _ in assen]) if gem_ok else None,
        "ringen": [_pts([p] * n) for p in (25, 50, 75, 100)],
        "assen": [{"x": round(_punt(i, n, _R)[0], 1), "y": round(_punt(i, n, _R)[1], 1)}
                  for i in range(n)],
        "labels": labels, "cx": _CX, "cy": _CY,
    }


# --- FotMob: percentielen -----------------------------------------------------------
_FM_SECTIE = {"shooting": "Schieten", "passing": "Passing", "possession": "Balbezit & duels",
              "defending": "Verdedigen", "discipline": "Tucht", "goalkeeping": "Keepen",
              "distribution": "Opbouw"}
_FM_STAT = {
    "ShotsOnTarget": "Schoten op doel", "expected_goals": "xG",
    "expected_goals_on_target": "xGOT", "goals": "Goals", "headed_shots": "Kopbalschoten",
    "non_penalty_xg": "xG excl. strafschoppen", "shots": "Schoten", "assists": "Assists",
    "big_chance_created_team_title": "Grote kansen gecreëerd",
    "chances_created": "Kansen gecreëerd", "crosses_succeeeded": "Geslaagde voorzetten",
    "crosses_succeeeded_accuracy": "Voorzet %", "expected_assists": "xA",
    "line_breaking_passes": "Lijnbrekende passes",
    "long_ball_succeeeded_accuracy": "Lange ballen %", "long_balls_accurate": "Geslaagde lange ballen",
    "successful_passes": "Geslaagde passes", "successful_passes_accuracy": "Passnauwkeurigheid",
    "aerials_won": "Luchtduels gewonnen", "aerials_won_percent": "Luchtduels %",
    "dispossessed": "Bal verloren aan tegenstander", "dribbles_succeeded": "Dribbels",
    "duel_won": "Duels gewonnen", "duel_won_percent": "Duels %", "fouls_won": "Fouten afgedwongen",
    "penalty_won_title": "Strafschoppen verdiend", "touches": "Aanrakingen",
    "touches_opp_box": "Aanrakingen in de 16 van de tegenstander", "won_contest_subtitle": "Dribbel %",
    "blocked_shots": "Geblokte schoten", "clean_sheet_team_title": "Clean sheets",
    "clearances": "Wegwerkacties", "defensive_actions": "Verdedigende acties",
    "dribbled_past": "Gepasseerd", "expected_goals_against_while_on_pitch": "xG tegen (op het veld)",
    "fouls": "Overtredingen", "goals_conceded_while_on_pitch": "Goals tegen (op het veld)",
    "interceptions": "Intercepties", "matchstats.headers.tackles": "Tackles",
    "poss_won_att_3rd_team_title": "Bal veroverd in het laatste derde", "recoveries": "Ballen veroverd",
    "red_cards": "Rode kaarten", "yellow_cards": "Gele kaarten",
    "error_led_to_goal": "Fouten die tot een goal leidden", "goals_conceded": "Goals tegen",
    "goals_prevented": "Goals voorkomen", "keeper_high_claim": "Hoge ballen",
    "keeper_sweeper": "Uitkomsten als sweeper", "save_percentage": "Reddingspercentage",
    "saves": "Reddingen",
}

def _fm_percentielen(d: dict) -> dict | None:
    fs = d.get("firstSeasonStats") or {}
    secties = (fs.get("statsSection") or {}).get("items") or []
    uit = []
    for sec in secties:
        rijen = []
        for it in sec.get("items") or []:
            sid = it.get("localizedTitleId") or ""
            p90 = it.get("per90")
            pct = it.get("percentileRankPer90") if p90 is not None else it.get("percentileRank")
            if pct is None:
                pct = it.get("percentileRank")
            waarde = it.get("statValue")
            rijen.append({
                "label": _FM_STAT.get(sid) or it.get("title") or sid,
                "waarde": waarde,
                "p90": _getal(p90, 2),
                # FotMob oriënteert percentielen zo dat hoger altijd beter is (0 rode kaarten = 100)
                "pct": None if pct is None else int(round(pct)),
            })
        if rijen:
            sid = sec.get("localizedTitleId") or ""
            uit.append({"titel": _FM_SECTIE.get(sid) or sec.get("title") or sid, "rijen": rijen})
    if not uit:
        return None
    toernooi = ""
    try:
        toernooi = d["statSeasons"][0]["tournaments"][0]["name"]
    except (KeyError, IndexError, TypeError):
        pass
    return {"competitie": toernooi, "secties": uit}


_BLESSURE_NL = [
    ("injury", "blessure"), ("Knee", "Knie"), ("Ankle", "Enkel"), ("Calf", "Kuit"),
    ("Thigh", "Dij"), ("Groin", "Lies"), ("Muscle", "Spier"), ("Back", "Rug"), ("Foot", "Voet"),
    ("Hip", "Heup"), ("Shoulder", "Schouder"), ("Illness", "Ziekte"), ("Suspended", "Geschorst"),
    ("Day to day", "dag per dag"), ("Unknown", "onbekend"),
]


def _nl_blessure(tekst: str) -> str:
    for en, nl in _BLESSURE_NL:
        tekst = tekst.replace(en, nl)
    return tekst


def _blessure(inj) -> str | None:
    """Tekst uit FotMob's blessure-info (selectie-lid of speler-pagina), of None."""
    if not inj:
        return None
    if not isinstance(inj, dict):
        return _nl_blessure(str(inj))
    naam = inj.get("name") or inj.get("title") or "geblesseerd"
    terug = inj.get("expectedReturn")
    if isinstance(terug, dict):
        terug = terug.get("expectedReturnFallback") or terug.get("expectedReturnDateParam")
    naam = _nl_blessure(str(naam))
    return f"{naam} (terug: {_nl_blessure(str(terug))})" if terug else naam


# --- per ploeg ------------------------------------------------------------------------
def _selectie(team_id: int) -> list[dict]:
    data = _get(f"{SS}/team/{team_id}/players")
    return [x["player"] for x in data.get("players") or [] if x.get("player")]


def _json(url: str, key: str = "sofascore") -> dict | None:
    try:
        return _get(url, key=key)
    except Exception:
        return None


def _speler(p: dict, ut: int, seizoen: int, fm_lid: dict | None) -> dict:
    pid = p["id"]
    pos = p.get("position") or "?"
    geboren = _datum(p.get("dateOfBirthTimestamp"))
    leeftijd = int((_dt.datetime.now(_dt.timezone.utc) - geboren).days // 365.25) if geboren else None
    contract = _datum(p.get("contractUntilTimestamp"))
    waarde = p.get("proposedMarketValue")
    s = ((_json(f"{SS}/player/{pid}/unique-tournament/{ut}/season/{seizoen}/statistics/overall")
          or {}).get("statistics")) or {}
    apps = s.get("appearances") or 0
    minuten = s.get("minutesPlayed") or 0

    speler = {
        "id": pid, "naam": p.get("name"), "kort": p.get("shortName") or p.get("name"),
        "nummer": p.get("shirtNumber") or p.get("jerseyNumber"),
        "pos": pos, "pos_nl": POS_NL.get(pos, "Speler"),
        "pos_detail": (p.get("positionsDetailed") or [None])[0],
        "leeftijd": leeftijd, "lengte": p.get("height"), "voet": p.get("preferredFoot"),
        "land": (p.get("country") or {}).get("name"),
        "contract": contract.strftime("%m/%Y") if contract and contract.year >= 2020 else None,
        "waarde_m": _getal(waarde / 1e6, 2) if waarde else None,
        "blessure": None,
        "apps": apps, "starts": s.get("matchesStarted") or 0, "minuten": minuten,
        "rating": _getal(s.get("rating"), 2),
        "goals": s.get("goals") or 0, "assists": s.get("assists") or 0,
        "xg": _getal(s.get("expectedGoals"), 2), "xa": _getal(s.get("expectedAssists"), 2),
        "geel": s.get("yellowCards") or 0,
        "rood": (s.get("redCards") or 0),
        "kern": [], "radar": None, "fm": None,
    }
    if not apps:
        speler["blessure"] = _blessure((fm_lid or {}).get("injury"))
        return speler

    speler["kern"] = _kern(pos, s)
    attr = _json(f"{SS}/player/{pid}/attribute-overviews")
    speler["radar"] = _radar(pos, attr)
    if fm_lid:
        fm = _json(f"{FM}/playerData?id={fm_lid['id']}", key="fotmob")
        if fm:
            speler["fm"] = _fm_percentielen(fm)
            speler["blessure"] = _blessure(fm.get("injuryInformation"))
        speler["blessure"] = speler["blessure"] or _blessure(fm_lid.get("injury"))
    return speler


def _fm_leden(fm_id: int | None, ccode3: str, namen: list[str]) -> dict[str, dict]:
    """{sofascore-naam: FotMob-lid} via de naamkoppeling op de FotMob-selectie."""
    if not fm_id:
        return {}
    blob = teamstats._fm_team(fm_id, ccode3)
    groepen = ((blob or {}).get("squad") or {}).get("squad") or []
    koppelaar = NaamKoppelaar(namen)
    uit: dict[str, dict] = {}
    for g in groepen:
        if g.get("title") == "coach":
            continue
        for m in g.get("members") or []:
            naam = koppelaar.koppel(m.get("name") or "")
            if naam and naam not in uit:
                uit[naam] = m
    return uit


def _ploeg_blok(wie: str, ss_id: int, naam: str, fm_id: int | None, comp: dict,
                ccode3: str) -> dict:
    blok = {"wie": wie, "naam": naam, "sofascore_id": ss_id, "fotmob_id": fm_id,
            "competitie": {"naam": comp.get("naam"), "ut": comp["ut"], "seizoen": comp["seizoen"]},
            "spelers": [], "fm_gekoppeld": 0, "fout": None}
    try:
        selectie = _selectie(ss_id)
    except Exception as exc:  # noqa: BLE001
        blok["fout"] = f"{type(exc).__name__}: {exc}"
        return blok
    leden = _fm_leden(fm_id, ccode3, [p["name"] for p in selectie if p.get("name")])
    spelers = []
    for p in selectie:
        if p.get("retired") or not p.get("id"):
            continue
        spelers.append(_speler(p, comp["ut"], comp["seizoen"], leden.get(p.get("name"))))
    spelers.sort(key=lambda x: (-x["minuten"], _POS_VOLGORDE.get(x["pos"], 9), x["naam"] or ""))
    blok["spelers"] = spelers
    blok["fm_gekoppeld"] = sum(1 for x in spelers if x["fm"])
    return blok


def _fm_id_tegenstander(teg: dict) -> int | None:
    """FotMob-id van de tegenstander: uit de teamstats-blob (zelfde koppeling), anders zoeken."""
    for pl in (get_kv("bron:teamstats", {}) or {}).get("ploegen") or []:
        if pl.get("sofascore_id") == teg.get("id") and pl.get("fotmob_id"):
            return pl["fotmob_id"]
    try:
        return teamstats._zoek_fm(teg.get("naam") or "")
    except Exception:
        return None


# --- publiek ----------------------------------------------------------------------------
def fetch(sofascore_blob: dict, ploeg: dict | None = None) -> dict:
    from .. import ploeg as _ploeg_mod

    so = sofascore_blob or {}
    eigen = ploeg or _ploeg_mod.actieve()
    comp = so.get("competitie") or {}
    teg = (so.get("volgende") or {}).get("tegenstander") or {}
    out: dict = {"opgehaald_op": _dt.datetime.now().isoformat(timespec="seconds"),
                 "ploegen": [], "status": "ok"}
    if not (eigen.get("sofascore_id") and comp.get("ut") and comp.get("seizoen")):
        out["status"] = {"code": "leeg",
                         "tekst": "geen competitie bekend — eerst Sofascore verversen"}
        return out

    onze_comp = {"ut": comp["ut"], "seizoen": comp["seizoen"],
                 "naam": comp.get("naam") or (eigen.get("competitie") or {}).get("naam") or ""}
    ccode3 = eigen.get("fotmob_ccode3") or "BEL"
    out["ploegen"].append(_ploeg_blok("eigen", eigen["sofascore_id"], eigen.get("naam") or "",
                                      eigen.get("fotmob_id"), onze_comp, ccode3))
    if teg.get("id"):
        opp_comp = teamstats._comp_van_ploeg(teg["id"], onze_comp)
        out["ploegen"].append(_ploeg_blok("tegenstander", teg["id"], teg.get("naam") or "",
                                          _fm_id_tegenstander(teg), opp_comp, ccode3))

    if not any(x["apps"] for pl in out["ploegen"] for x in pl["spelers"]):
        fouten = [pl["fout"] for pl in out["ploegen"] if pl.get("fout")]
        tekst = "Sofascore gaf geen spelerscijfers voor deze ploegen"
        if fouten:
            tekst += f" ({fouten[0]})"
        out["status"] = {"code": "leeg", "tekst": tekst}
    return out
