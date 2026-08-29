"""Transfermarkt: seizoensstatistieken per speler over alle competities
(wedstrijden, goals, assists, kaarten, gespeelde minuten), de lijst met
geblesseerde/geschorste spelers, en transferconnecties tussen twee clubs.
"""

from __future__ import annotations

import datetime as _dt
import re
import urllib.parse

from bs4 import BeautifulSoup

from .. import config
from ..http_client import get_html

BASE = "https://www.transfermarkt.com"


def _getal(tekst: str) -> int:
    """'270\\'' -> 270 ; '1.234' -> 1234 ; '-' -> 0."""
    cijfers = re.sub(r"[^\d]", "", tekst or "")
    return int(cijfers) if cijfers else 0


# Transfermarkt-sorteersleutels in de kolomkoppen -> ons veld. Deze sleutels
# staan in de href van de sorteerlinks en zijn taal-onafhankelijk en stabiel.
_KOLOM_SLEUTELS = {
    "einsaetze": "wedstrijden",
    "tore": "goals",
    "vorlagen": "assists",
    "gelbe": "geel",
    "gelbrote": "tweede_geel",
    "rote": "rood",
    "einsatzzeit": "minuten",
    "pps": "ppg",
}


def _kolom_index(tabel) -> dict[str, int]:
    """{onze-veldnaam: kolomindex} afgeleid uit de sorteerlinks in de tabelkop."""
    uit: dict[str, int] = {}
    koppen = tabel.select("thead th")
    for idx, th in enumerate(koppen):
        a = th.select_one('a[href*="/sort/"]')
        if not a:
            continue
        m = re.search(r"/sort/([a-z_]+)", a.get("href", ""))
        if m and m.group(1) in _KOLOM_SLEUTELS:
            uit[_KOLOM_SLEUTELS[m.group(1)]] = idx
    return uit


def _leistungsdaten_url(club_id: int, club_slug: str, seizoen: int) -> str:
    # reldata/%26<jaar>  ->  '&' + jaar  =  alle competities, dat seizoen
    return (
        f"{BASE}/{club_slug}/leistungsdaten/verein/"
        f"{club_id}/reldata/%26{seizoen}/plus/1"
    )


def fetch(seizoen: int | None = None, ploeg: dict | None = None) -> dict:
    club_id = (ploeg or {}).get("tm_id") or config.TRANSFERMARKT_CLUB_ID
    club_slug = (ploeg or {}).get("tm_slug") or config.TRANSFERMARKT_CLUB_SLUG
    seizoen = seizoen or config.huidig_seizoen_jaar()
    if not club_id or not club_slug:
        return {
            "opgehaald_op": _dt.datetime.now().isoformat(timespec="seconds"),
            "seizoen": f"{seizoen}/{str(seizoen + 1)[-2:]}", "bron_url": None,
            "spelers": [], "uitval": {"geblesseerd": [], "geschorst": []},
            "status": {"code": "leeg", "tekst": "geen Transfermarkt-club ingesteld"},
        }
    url = _leistungsdaten_url(club_id, club_slug, seizoen)
    html = get_html(url, key="transfermarkt")
    soup = BeautifulSoup(html, "html.parser")
    tabel = soup.select_one("table.items")

    # Kolommen bij voorkeur op kop lezen; anders terugvallen op vaste posities
    # vanaf het einde ([-10]=wedstrijden … [-1]=minuten).
    kol = _kolom_index(tabel) if tabel else {}
    op_kop = len(kol) >= 5
    _POS = {"wedstrijden": -10, "goals": -9, "assists": -8, "geel": -7,
            "tweede_geel": -6, "rood": -5, "ppg": -2, "minuten": -1}

    def _cel(waarden: list[str], veld: str) -> str:
        idx = kol.get(veld) if op_kop else _POS[veld]
        try:
            return waarden[idx]
        except (IndexError, TypeError):
            return ""

    spelers: list[dict] = []
    if tabel:
        for tr in tabel.select("tbody > tr"):
            tds = tr.find_all("td", recursive=False)
            naam_link = tr.select_one("td.hauptlink a")
            if not naam_link or len(tds) < 12:
                continue
            naam = naam_link.get_text(strip=True)
            profiel = naam_link.get("href", "")
            speler_id_match = re.search(r"/spieler/(\d+)", profiel)
            waarden = [td.get_text(strip=True) for td in tds]
            tweede_geel = _getal(_cel(waarden, "tweede_geel"))
            rood = _getal(_cel(waarden, "rood"))
            ppg = _cel(waarden, "ppg")
            spelers.append(
                {
                    "speler": naam,
                    "tm_id": speler_id_match.group(1) if speler_id_match else None,
                    "profiel_url": BASE + profiel if profiel.startswith("/") else profiel,
                    "wedstrijden": _getal(_cel(waarden, "wedstrijden")),
                    "goals": _getal(_cel(waarden, "goals")),
                    "assists": _getal(_cel(waarden, "assists")),
                    "geel": _getal(_cel(waarden, "geel")),
                    "tweede_geel": tweede_geel,
                    "rood": rood + tweede_geel,  # totaal rood (direct + 2e geel)
                    "minuten": _getal(_cel(waarden, "minuten")),
                    "ppg": ppg if ppg not in ("-", "") else None,
                }
            )

    return {
        "opgehaald_op": _dt.datetime.now().isoformat(timespec="seconds"),
        "seizoen": f"{seizoen}/{str(seizoen + 1)[-2:]}",
        "bron_url": url,
        "spelers": spelers,
        "uitval": blessures_schorsingen(club_id, club_slug),
        "status": "ok" if spelers else {
            "code": "leeg", "tekst": "Transfermarkt gaf geen spelers in de statistiektabel terug"},
    }


def zoek_club(naam: str, competitie_naam: str | None = None) -> tuple[int, str] | None:
    """Transfermarkt-verein-id + slug voor een clubnaam (via de snelzoekfunctie).

    ``competitie_naam`` (optioneel) helpt de juiste club kiezen als er meerdere
    matches zijn (bv. jeugdteams, gelijknamige clubs in andere landen).
    """
    vast = config.PRO_LEAGUE_TM.get(naam)
    if vast:
        return vast
    try:
        html = get_html(
            f"{BASE}/schnellsuche/ergebnis/schnellsuche?query={urllib.parse.quote(naam)}",
            key="transfermarkt",
        )
    except Exception:
        return None
    soup = BeautifulSoup(html, "html.parser")

    kandidaten: list[tuple[int, str, str]] = []   # (id, slug, competitie)
    for tr in soup.select("table.items tbody > tr"):
        a = tr.select_one("td.hauptlink a")
        if not a or "/verein/" not in a.get("href", ""):
            continue  # spelers- of stafrijen overslaan
        m = re.search(r"/([a-z0-9-]+)/(?:startseite|kader)/verein/(\d+)", a.get("href", ""))
        if not m:
            continue
        liga = tr.select_one("a[href*='/wettbewerb/']")
        kandidaten.append((int(m.group(2)), m.group(1), liga.get_text(strip=True) if liga else ""))

    if not kandidaten:
        return None
    if competitie_naam:
        from ..names import clubs_gelijk
        for cid, slug, liga in kandidaten:
            if liga and clubs_gelijk(liga, competitie_naam):
                return (cid, slug)
    return (kandidaten[0][0], kandidaten[0][1])


def kader(club_id: int, club_slug: str, seizoen: int | None = None) -> list[str]:
    """Namen van de huidige selectie van een club."""
    seizoen = seizoen or config.huidig_seizoen_jaar()
    url = f"{BASE}/{club_slug}/kader/verein/{club_id}/saison_id/{seizoen}/plus/1"
    try:
        soup = BeautifulSoup(get_html(url, key="transfermarkt"), "html.parser")
    except Exception:
        return []
    t = soup.select_one("table.items")
    if not t:
        return []
    return [
        a.get_text(strip=True)
        for a in t.select("td.hauptlink a")
        if "/profil/spieler/" in a.get("href", "")
    ]


def blessures_schorsingen(club_id: int, club_slug: str) -> dict:
    """Geblesseerde en geschorste spelers (mist de volgende wedstrijd)."""
    url = f"{BASE}/{club_slug}/sperrenundverletzungen/verein/{club_id}"
    out = {"bron_url": url, "geblesseerd": [], "geschorst": []}
    try:
        soup = BeautifulSoup(get_html(url, key="transfermarkt"), "html.parser")
    except Exception:
        return out
    tabel = soup.select_one("table.items")
    if not tabel:
        return out

    sectie = "geblesseerd"
    for tr in tabel.select("tbody > tr"):
        kop = tr.select_one("td.extrarow")
        if kop:
            tekst = kop.get_text(strip=True).lower()
            sectie = "geschorst" if ("suspen" in tekst or "sperr" in tekst or "schors" in tekst) else "geblesseerd"
            continue
        naam_link = tr.select_one("td.hauptlink a")
        if not naam_link:
            continue
        cellen = [td.get_text(" ", strip=True) for td in tr.find_all("td", recursive=False)]
        reden = cellen[-4] if len(cellen) >= 4 else ""
        terug = cellen[-2] if len(cellen) >= 2 else ""
        out[sectie].append(
            {"speler": naam_link.get_text(strip=True), "reden": reden, "terug": terug}
        )
    return out


def _transfers_seizoen(club_slug: str, club_id: int, jaar: int) -> dict:
    """{'aankomsten': [(speler, van_club)], 'vertrekkers': [(speler, naar_club)]}.

    Afgesloten seizoenen wijzigen niet meer -> permanent gecacht in de kv-store.
    """
    from ..store import get_kv, set_kv

    afgesloten = jaar < config.huidig_seizoen_jaar()
    sleutel = f"tm:transfers:{club_id}:{jaar}"
    if afgesloten:
        gecacht = get_kv(sleutel)
        if gecacht:
            return {k: [tuple(x) for x in v] for k, v in gecacht.items()}

    url = f"{BASE}/{club_slug}/transfers/verein/{club_id}/saison_id/{jaar}"
    result = {"aankomsten": [], "vertrekkers": []}
    try:
        soup = BeautifulSoup(get_html(url, key="transfermarkt"), "html.parser")
    except Exception:
        return result
    for box in soup.select("div.box"):
        h2 = box.select_one("h2")
        if not h2:
            continue
        kop = h2.get_text(strip=True)
        doel = "aankomsten" if kop == "Arrivals" else "vertrekkers" if kop == "Departures" else None
        if not doel:
            continue
        t = box.select_one("table.items")
        if not t:
            continue
        for tr in t.select("tbody > tr"):
            if len(tr.find_all("td", recursive=False)) < 5:
                continue
            speler = tr.select_one("td.hauptlink a")
            clubs = [a.get("title") for a in tr.select("a[href*='/verein/']") if a.get("title")]
            if speler and clubs:
                result[doel].append((speler.get_text(strip=True), clubs[-1]))

    if afgesloten and (result["aankomsten"] or result["vertrekkers"]):
        set_kv(sleutel, result)
    return result


def connecties(opp_naam: str, opp_squad: list[str], antwerp_squad: list[str],
               eigen_tm: tuple[int, str] | None = None, seizoenen: int = 8) -> dict:
    """Ex-spelers van de eigen ploeg die *nu* bij de tegenstander spelen, en omgekeerd.

    Een speler telt enkel mee als hij (a) in de laatste ``seizoenen`` de club
    verliet/kwam én (b) op dit moment nog in de huidige selectie van de andere club zit.
    """
    from ..names import clubs_gelijk, normaliseer

    eigen_id, eigen_slug = eigen_tm or (config.TRANSFERMARKT_CLUB_ID, config.TRANSFERMARKT_CLUB_SLUG)
    if not eigen_id or not eigen_slug:
        return {"ex_antwerp_bij_tegenstander": [], "ex_tegenstander_bij_antwerp": []}

    dit_jaar = config.huidig_seizoen_jaar()
    opp_norm = {normaliseer(n) for n in opp_squad}
    ant_norm = {normaliseer(n) for n in antwerp_squad}

    ex_antwerp: dict[str, str] = {}   # speler -> naar welke club hij de eigen ploeg verliet
    ex_opp: dict[str, str] = {}       # speler -> van welke club hij bij de eigen ploeg kwam
    for jaar in range(dit_jaar, dit_jaar - seizoenen, -1):
        data = _transfers_seizoen(eigen_slug, eigen_id, jaar)
        for speler, naar_club in data["vertrekkers"]:
            if normaliseer(speler) in opp_norm:  # zit nu in de kern van de tegenstander
                ex_antwerp.setdefault(speler, naar_club)
        for speler, van_club in data["aankomsten"]:
            if normaliseer(speler) in ant_norm and clubs_gelijk(van_club, opp_naam):
                ex_opp.setdefault(speler, van_club)

    return {
        "ex_antwerp_bij_tegenstander": [{"speler": s, "via": c} for s, c in ex_antwerp.items()],
        "ex_tegenstander_bij_antwerp": [{"speler": s, "van": c} for s, c in ex_opp.items()],
    }
