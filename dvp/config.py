"""Vaste instellingen. Alleen aanpassen bij een clubwissel of nieuwe speler-aliassen."""

from __future__ import annotations

import datetime as _dt
import os
import sys
from pathlib import Path

# --- Club ---------------------------------------------------------------------
CLUB_NAAM = "Royal Antwerp FC"

# Sofascore team-id (stabiel). Terug te vinden via api.sofascore.com/api/v1/search/all?q=...
SOFASCORE_TEAM_ID = 2889

# FotMob team-id (stabiel). Via apigw.fotmob.com/searchapi/suggest?term=...
FOTMOB_TEAM_ID = 9988

# Transfermarkt club (stabiel).
TRANSFERMARKT_CLUB_ID = 1096
TRANSFERMARKT_CLUB_SLUG = "royal-antwerpen-fc"

# WhoScored laat geen directe match-links toe zonder scrapen; we linken naar de
# clubpagina (met recente matchen + ratings). Team-id 752 is stabiel.
WHOSCORED_TEAM_URL = "https://www.whoscored.com/teams/752/show/belgium-royal-antwerp"

# Clubnaam (zoals Sofascore ze noemt) -> (Transfermarkt-verein-id, slug).
# Enkel geverifieerde ids; voor de rest gebruikt de tool de snelzoekfunctie.
PRO_LEAGUE_TM: dict[str, tuple[int, str]] = {
    "Sint-Truidense VV": (475, "vv-st-truiden"),
    "KRC Genk": (1184, "krc-genk"),
    "Club Brugge KV": (2282, "fc-brugge"),
}

# --- Opslag / basismap ------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# --- Server ------------------------------------------------------------------
HOST = "127.0.0.1"
# Poort: standaard 8756 (DVP), of wat merk.json onder "poort" zet (Aftrap: 8757),
# zodat beide varianten naast elkaar kunnen draaien. Te overschrijven met de
# omgevingsvariabele DVP_PORT of een bestandje poort.txt naast de app.
def _poort() -> int:
    ev = os.environ.get("DVP_PORT", "")
    if ev.isdigit():
        return int(ev)
    try:
        return int((BASE_DIR / "poort.txt").read_text().strip())
    except (OSError, ValueError):
        pass
    try:
        import json
        p = json.loads((BASE_DIR / "merk.json").read_text(encoding="utf-8-sig")).get("poort")
        return int(p) if p else 8756
    except (OSError, ValueError, TypeError):
        return 8756


PORT = _poort()

# Waar data/afleveringen geschreven worden. Naast de app (Windows/Linux),
# op macOS in Application Support (niet in de .app-bundel), en op Android
# geeft de app een schrijfbare map mee via DVP_DATA_DIR (de bronmap is daar
# read-only).
if os.environ.get("DVP_DATA_DIR"):
    DATA_ROOT = Path(os.environ["DVP_DATA_DIR"])
elif sys.platform == "darwin":
    DATA_ROOT = Path.home() / "Library" / "Application Support" / "De Vierkante Paal"
else:
    DATA_ROOT = BASE_DIR

DATA_DIR = DATA_ROOT / "data"
DB_PATH = DATA_DIR / "dvp.sqlite"

# --- Netwerk --------------------------------------------------------------------
REQUEST_TIMEOUT = 25
# Kleine pauze tussen opeenvolgende requests naar dezelfde site (beleefdheid).
REQUEST_PAUSE = 0.8
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# --- Versie ------------------------------------------------------------------
def versie() -> str:
    """Builddatum uit versie.txt (naast de app), of "" in de ontwikkelopstelling."""
    try:
        return (BASE_DIR / "versie.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


# --- Seizoen ------------------------------------------------------------------
def huidig_seizoen_jaar(vandaag: _dt.date | None = None) -> int:
    """Startjaar van het lopende seizoen. Een seizoen start in juli."""
    vandaag = vandaag or _dt.date.today()
    return vandaag.year if vandaag.month >= 7 else vandaag.year - 1


# --- Speler-aliassen ---------------------------------------------------------
# Vul hier één keer namen in die de tool niet automatisch koppelt tussen bronnen.
# Sleutel = genormaliseerde naam zoals ze bij Transfermarkt/FotMob staat,
# waarde = genormaliseerde naam zoals ze bij Sofascore (de "master") staat.
# Normaliseren = kleine letters, geen accenten, geen leestekens.
SPELER_ALIASSEN: dict[str, str] = {
    # "vincent janssen": "v janssen",
}
