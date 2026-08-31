"""Bouwt uit de opgeslagen bron-data één overzicht voor de webpagina en de export."""

from __future__ import annotations

import datetime as _dt
import urllib.parse

from . import config, merk, ploeg, store
from .names import NaamKoppelaar, normaliseer


def _gemiddelde(waarden: list[float]) -> float | None:
    echte = [w for w in waarden if w is not None]
    return round(sum(echte) / len(echte), 2) if echte else None


def _delta(nu, toen) -> int | None:
    return None if toen is None else nu - toen


def _aliassen() -> dict:
    return store.get_kv("aliassen", {}) or {}


def _speler_tm() -> dict:
    """Handmatig toegevoegde Transfermarkt-links: {genormaliseerde spelernaam: {url, spieler_id}}."""
    return store.get_kv("speler_tm", {}) or {}


def _whoscored_link() -> str | None:
    if not merk.toon_whoscored():
        return None
    vast = getattr(config, "WHOSCORED_TEAM_URL", "")
    if vast and not ploeg.is_gekozen():
        return vast
    naam = ploeg.actieve().get("naam") or ""
    return f"https://www.whoscored.com/search/?t={urllib.parse.quote(naam)}"


def bouw_scoretabel(sofascore: dict, fotmob: dict, event_id: str | None) -> list[dict]:
    vorige = (sofascore or {}).get("vorige") or {}
    opstelling = vorige.get("opstelling") or []
    handmatig = store.manual_ratings(event_id) if event_id else {}

    fm_ratings = (fotmob or {}).get("ratings_antwerp") or {}
    fm_koppelaar = NaamKoppelaar(list(fm_ratings), _aliassen()) if fm_ratings else None
    met_whoscored = merk.toon_whoscored()

    rijen: list[dict] = []
    for sp in opstelling:
        key = normaliseer(sp["naam"])
        ss = sp.get("rating")
        fm = None
        if fm_koppelaar:
            match = fm_koppelaar.koppel(sp["naam"])
            if match:
                fm = fm_ratings[match]
        ws = handmatig.get((key, "whoscored")) if met_whoscored else None
        rijen.append(
            {
                "speler": sp["naam"],
                "player_key": key,
                "positie": sp.get("positie"),
                "invaller": sp.get("invaller"),
                "minuten": sp.get("minuten"),
                "sofascore": ss,
                "fotmob": fm,
                "whoscored": ws,
                "gemiddelde": _gemiddelde([ss, fm, ws]),
                "doelpunten": sp.get("doelpunten") or 0,
                "assists": sp.get("assists") or 0,
            }
        )
    return rijen


def bouw_stattabel(transfermarkt: dict, sofascore: dict | None = None) -> list[dict]:
    spelers = (transfermarkt or {}).get("spelers") or []
    vorige_snapshot = store.previous_stat_snapshot(ploeg.sleutel())

    seizoen_ratings = ((sofascore or {}).get("seizoen_ratings") or {}).get("spelers") or {}
    rating_koppelaar = NaamKoppelaar(list(seizoen_ratings), _aliassen()) if seizoen_ratings else None
    # handmatige Transfermarkt-links koppelen de seizoensrating via het spieler-id
    _handmatig = _speler_tm()
    _id_naar_rating = {
        _handmatig[normaliseer(naam)]["spieler_id"]: naam
        for naam in seizoen_ratings
        if _handmatig.get(normaliseer(naam), {}).get("spieler_id")
    }

    uitval = (transfermarkt or {}).get("uitval") or {}
    geschorst = {normaliseer(p["speler"]): p for p in uitval.get("geschorst", [])}
    geblesseerd = {normaliseer(p["speler"]): p for p in uitval.get("geblesseerd", [])}

    rijen: list[dict] = []
    for sp in spelers:
        if not sp.get("wedstrijden"):
            continue
        key = normaliseer(sp["speler"])
        toen = vorige_snapshot.get(key, {})
        rating = None
        if sp.get("tm_id") and str(sp["tm_id"]) in _id_naar_rating:
            rating = seizoen_ratings[_id_naar_rating[str(sp["tm_id"])]].get("rating")
        elif rating_koppelaar:
            match = rating_koppelaar.koppel(sp["speler"])
            if match:
                rating = seizoen_ratings[match].get("rating")
        rijen.append(
            {
                "speler": sp["speler"],
                "player_key": key,
                "profiel_url": sp.get("profiel_url"),
                "wedstrijden": sp["wedstrijden"],
                "goals": sp["goals"],
                "assists": sp["assists"],
                "geel": sp.get("geel", 0),
                "rood": sp.get("rood", 0),
                "minuten": sp["minuten"],
                "gem_rating": rating,
                "geschorst": geschorst.get(key),
                "geblesseerd": geblesseerd.get(key),
                "d_wedstrijden": _delta(sp["wedstrijden"], toen.get("apps")),
                "d_goals": _delta(sp["goals"], toen.get("goals")),
                "d_assists": _delta(sp["assists"], toen.get("assists")),
                "d_geel": _delta(sp.get("geel", 0), toen.get("yellow")),
                "d_rood": _delta(sp.get("rood", 0), toen.get("red")),
                "d_minuten": _delta(sp["minuten"], toen.get("minutes")),
            }
        )
    rijen.sort(key=lambda r: (-r["minuten"], r["speler"]))
    return rijen


def snapshot_rijen(transfermarkt: dict) -> list[dict]:
    """Vorm voor store.save_stat_snapshot()."""
    return [
        {
            "player_key": normaliseer(sp["speler"]),
            "speler": sp["speler"],
            "apps": sp.get("wedstrijden") or 0,
            "goals": sp.get("goals") or 0,
            "assists": sp.get("assists") or 0,
            "yellow": sp.get("geel") or 0,
            "red": sp.get("rood") or 0,
            "minutes": sp.get("minuten") or 0,
        }
        for sp in (transfermarkt or {}).get("spelers") or []
    ]


def koppel_profielen(scoretabel: list[dict], transfermarkt: dict) -> None:
    """Voeg aan elke scorerij de Transfermarkt-profiel-URL toe (indien te matchen)."""
    tm_spelers = (transfermarkt or {}).get("spelers") or []
    handmatig = _speler_tm()
    per_naam = {s["speler"]: s for s in tm_spelers}
    koppelaar = NaamKoppelaar([s["speler"] for s in tm_spelers], _aliassen()) if tm_spelers else None
    for rij in scoretabel:
        if koppelaar:
            master = koppelaar.koppel(rij["speler"])
            if master and master in per_naam:
                rij["profiel_url"] = per_naam[master].get("profiel_url")
        # handmatig toegevoegde link wint altijd
        eigen = handmatig.get(rij["player_key"])
        if eigen and eigen.get("url"):
            rij["profiel_url"] = eigen["url"]


def _kies_opstellingen(sofascore: dict, fotmob: dict) -> dict:
    """Sofascore-opstellingen als standaard; FotMob enkel als terugval."""
    so_v = (sofascore or {}).get("vorige") or {}
    so_vb = (sofascore or {}).get("voorbeschouwing") or {}
    fm_v = (fotmob or {}).get("vorige") or {}
    fm_n = (fotmob or {}).get("volgende") or {}

    bron = "Sofascore" if so_v.get("opstelling_antwerp") else "FotMob"
    return {
        "bron": bron,
        "vorige_antwerp": so_v.get("opstelling_antwerp") or fm_v.get("opstelling_antwerp"),
        "vorige_tegenstander": so_v.get("opstelling_tegenstander") or fm_v.get("opstelling_tegenstander"),
        "volgende_tegenstander": so_vb.get("tegenstander_opstelling") or fm_n.get("tegenstander_opstelling"),
    }


def _diagnose(overzicht: dict) -> dict:
    """Namen die de tool niet kon koppelen tussen bronnen."""
    so = overzicht["sofascore"]
    handmatig = _speler_tm()
    ongekoppeld_tm = [
        {"speler": r["speler"], "player_key": r["player_key"]}
        for r in overzicht["scoretabel"] if not r.get("profiel_url")
    ]
    # seizoensrating-namen niet in de stattabel
    stat_namen = {normaliseer(r["speler"]) for r in overzicht["stattabel"]}
    rating_koppelaar = NaamKoppelaar([r["speler"] for r in overzicht["stattabel"]], _aliassen())
    ongekoppeld_rating = [
        naam for naam in ((so.get("seizoen_ratings") or {}).get("spelers") or {})
        if normaliseer(naam) not in stat_namen and not rating_koppelaar.koppel(naam)
        and not handmatig.get(normaliseer(naam), {}).get("spieler_id")
    ]
    return {
        "scoretabel_zonder_transfermarkt": ongekoppeld_tm,
        "rating_zonder_stattabel": ongekoppeld_rating,
        "speler_links": handmatig,
        "aliassen_config": dict(config.SPELER_ALIASSEN),
        "aliassen_eigen": _aliassen(),
    }


def _praatpunten(overzicht: dict) -> list[str]:
    """Kant-en-klare gesprekstof: vat de al opgehaalde cijfers samen tot losse zinnen.
    Puur samenvatten van bestaande data — geen extra requests."""
    eigen = ploeg.actieve().get("naam") or config.CLUB_NAAM
    so = overzicht.get("sofascore") or {}
    vorige = so.get("vorige") or {}
    volgende = so.get("volgende") or {}
    vb = so.get("voorbeschouwing") or {}
    ve = overzicht.get("voorbeschouwing_extra") or {}
    teg = (volgende.get("tegenstander") or {}).get("naam")
    klassement = vb.get("klassement") or []
    vd = vb.get("vorm_detail") or {}
    uit: list[str] = []

    # vorige wedstrijd
    t, u = vorige.get("thuis") or {}, vorige.get("uit") or {}
    if t.get("score") is not None and u.get("score") is not None:
        ant_thuis = vorige.get("antwerp_thuis")
        eg, og = (t["score"], u["score"]) if ant_thuis else (u["score"], t["score"])
        opp = (u if ant_thuis else t).get("naam") or "de tegenstander"
        wdl = "won" if eg > og else "verloor" if eg < og else "speelde gelijk"
        waar = "thuis" if ant_thuis else "uit"
        uit.append(f"📅 Vorige match: {eigen} {wdl} {waar} {eg}–{og} tegen {opp}"
                   + (f" ({vorige.get('competitie')})" if vorige.get("competitie") else "") + ".")

    # eigen klassementspositie + kloof
    eigen_rij = next((r for r in klassement if r.get("antwerp")), None)
    if eigen_rij and eigen_rij.get("positie"):
        pos = eigen_rij["positie"]
        gesp = eigen_rij["gespeeld"]
        zin = (f"📊 {eigen} staat {pos}e met {eigen_rij['punten']} punten "
               f"na {gesp} {'match' if gesp == 1 else 'matchen'}")

        def _kloof(buur: dict | None) -> str | None:
            if not buur:
                return None
            d = buur["punten"] - eigen_rij["punten"]
            if d > 0:
                return f"{d} achter {buur['team']} ({buur['positie']}e)"
            if d < 0:
                return f"{-d} voor op {buur['team']} ({buur['positie']}e)"
            return f"gelijk met {buur['team']} ({buur['positie']}e)"

        stukjes = [s for s in (
            _kloof(next((r for r in klassement if r.get("positie") == pos - 1), None)),
            _kloof(next((r for r in klassement if r.get("positie") == pos + 1), None)),
        ) if s]
        uit.append(zin + (" — " + ", ".join(stukjes) if stukjes else "") + ".")

    # eigen vorm
    eigen_v = vd.get("antwerp") or {}
    eigen_vorm = (eigen_v.get("laatste5") or {}).get("vorm")
    if eigen_vorm:
        zin = f"📈 Vorm {eigen} (laatste 5): {eigen_vorm}"
        if eigen_v.get("ongeslagen", 0) >= 3:
            zin += f" — {eigen_v['ongeslagen']} matchen ongeslagen"
        uit.append(zin + ".")

    # tegenstander: positie + vorm
    if teg:
        teg_rij = next((r for r in klassement if r.get("tegenstander")), None)
        teg_v = vd.get("tegenstander") or {}
        teg_vorm = (teg_v.get("laatste5") or {}).get("vorm")
        stukjes = []
        if teg_rij and teg_rij.get("positie"):
            stukjes.append(f"{teg_rij['positie']}e met {teg_rij['punten']} ptn")
        if teg_vorm:
            stukjes.append(f"vorm {teg_vorm}")
        if teg_v.get("ongeslagen", 0) >= 3:
            stukjes.append(f"{teg_v['ongeslagen']}x ongeslagen")
        if stukjes:
            uit.append(f"🔮 Tegenstander {teg}: " + ", ".join(stukjes) + ".")

    # onderlinge balans
    h = vb.get("h2h") or {}
    if h.get("aantal"):
        uit.append(f"⚔️ Onderling ({h['aantal']} duels): {h['antwerp_winst']}× {eigen}, "
                   f"{h['gelijk']}× gelijk, {h['tegenstander_winst']}× {teg}.")

    # scheidsrechter
    ref = vb.get("scheidsrechter") or {}
    if ref.get("naam"):
        uit.append(f"🧑‍⚖️ Ref {ref['naam']}: {ref.get('geel_per_match', '?')} geel en "
                   f"{ref.get('rood_per_match', '?')} rood per match "
                   f"({ref.get('matchen', '?')} matchen).")

    # ex-spelers
    con = ve.get("connecties") or {}
    if con.get("ex_antwerp_bij_tegenstander"):
        uit.append(f"↩️ Ex-{eigen} bij {teg}: "
                   + ", ".join(c["speler"] for c in con["ex_antwerp_bij_tegenstander"]) + ".")
    if con.get("ex_tegenstander_bij_antwerp"):
        uit.append(f"↪️ Ex-{teg} bij {eigen}: "
                   + ", ".join(c["speler"] for c in con["ex_tegenstander_bij_antwerp"]) + ".")

    # afwezigen
    def _weg(blok: dict) -> list[str]:
        return ([p["speler"] for p in blok.get("geschorst", [])]
                + [p["speler"] for p in blok.get("geblesseerd", [])])

    eigen_weg = _weg((overzicht.get("transfermarkt") or {}).get("uitval") or {})
    if eigen_weg:
        uit.append(f"🚑 Afwezig/onzeker bij {eigen}: " + ", ".join(eigen_weg[:6])
                   + ("…" if len(eigen_weg) > 6 else "") + ".")
    teg_weg = _weg(ve.get("uitval") or {})
    if teg_weg:
        uit.append(f"🚑 Afwezig bij {teg}: " + ", ".join(teg_weg[:6])
                   + ("…" if len(teg_weg) > 6 else "") + ".")

    # topschutter eigen ploeg
    scorers = [r for r in (overzicht.get("stattabel") or []) if r.get("goals")]
    if scorers:
        top = max(scorers, key=lambda r: r["goals"])
        if top["goals"] >= 2:
            uit.append(f"⚽ Meeste goals {eigen}: {top['speler']} ({top['goals']})"
                       + (f", {top['assists']} assists" if top.get("assists") else "") + ".")

    # gevaarlijkste tegenstander
    sh_goals = (vb.get("tegenstander_sterkhouders") or {}).get("goals") or []
    if sh_goals and sh_goals[0].get("waarde"):
        s = sh_goals[0]
        uit.append(f"⭐ Gevaarlijkste man {teg}: {s['naam']} ({s['waarde']} goals).")

    # opvallend doelpunt-type-patroon (uit de teamstatistieken)
    for pl in (overzicht.get("teamstats") or {}).get("ploegen", []):
        dp = pl.get("doelpunten") or {}
        for kant, woord in (("gescoord", "maakt"), ("geincasseerd", "slikt")):
            blok = dp.get(kant) or {}
            tot = blok.get("totaal") or 0
            fases = blok.get("fases") or {}
            if tot >= 6 and fases:
                fase, n = max(fases.items(), key=lambda x: x[1])
                if fase not in ("Open spel", "Eigen doelpunt") and n / tot >= 0.33:
                    uit.append(f"🎯 {pl['naam']} {woord} veel doelpunten via "
                               f"“{fase.lower()}” ({n} van {tot}).")

    return uit


def _bron_status() -> dict:
    """Per bron: 'ok' | 'verouderd' (>8u) | 'leeg' (nooit) | 'fout'."""
    fouten = store.get_kv("fouten", {}) or {}
    uit: dict[str, str] = {}
    for naam in ("sofascore", "transfermarkt", "fotmob", "voorbeschouwing", "teamstats"):
        if naam in fouten:
            uit[naam] = "fout"
            continue
        ts = store.get_kv_updated(f"bron:{naam}")
        if not ts:
            uit[naam] = "leeg"
            continue
        try:
            oud = (_dt.datetime.now() - _dt.datetime.fromisoformat(ts)).total_seconds()
        except ValueError:
            oud = 0
        uit[naam] = "verouderd" if oud > 8 * 3600 else "ok"
    return uit


def bouw_overzicht() -> dict:
    sofascore = store.get_kv("bron:sofascore", {})
    transfermarkt = store.get_kv("bron:transfermarkt", {})
    fotmob = store.get_kv("bron:fotmob", {})
    voorbeschouwing_extra = store.get_kv("bron:voorbeschouwing", {})
    teamstats = store.get_kv("bron:teamstats", {})

    event_id = (sofascore.get("vorige") or {}).get("event_id")
    scoretabel = bouw_scoretabel(sofascore, fotmob, event_id)
    koppel_profielen(scoretabel, transfermarkt)
    stattabel = bouw_stattabel(transfermarkt, sofascore)

    overzicht = {
        "sofascore": sofascore,
        "transfermarkt": transfermarkt,
        "fotmob": fotmob,
        "voorbeschouwing_extra": voorbeschouwing_extra,
        "teamstats": teamstats,
        "event_id": event_id,
        "scoretabel": scoretabel,
        "stattabel": stattabel,
        "opstellingen": _kies_opstellingen(sofascore, fotmob),
        "score_links": {
            "sofascore": (sofascore.get("vorige") or {}).get("url"),
            "fotmob": (fotmob.get("vorige") or {}).get("url"),
            "whoscored": _whoscored_link(),
        },
        "tijdstippen": {
            "sofascore": store.get_kv_updated("bron:sofascore"),
            "transfermarkt": store.get_kv_updated("bron:transfermarkt"),
            "fotmob": store.get_kv_updated("bron:fotmob"),
            "voorbeschouwing": store.get_kv_updated("bron:voorbeschouwing"),
            "teamstats": store.get_kv_updated("bron:teamstats"),
        },
        "bron_status": _bron_status(),
    }
    overzicht["diagnose"] = _diagnose(overzicht)
    overzicht["praatpunten"] = _praatpunten(overzicht)
    return overzicht
