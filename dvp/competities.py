"""De competities waaruit je in de generieke variant een ploeg kan kiezen.

Vaste tabel (deze id's zijn jarenlang stabiel):
- ``sofascore_ut``  = Sofascore uniqueTournament-id (voor klassement + topschutters);
  het huidige seizoen wordt live opgehaald via ``unique-tournament/{ut}/seasons``.
- ``tm_code``       = Transfermarkt Wettbewerb-code (helpt clubs in de juiste
  competitie herkennen bij de snelzoekfunctie).
- ``fotmob_ccode3`` = landcode die FotMob's team-endpoint verwacht.
- ``fotmob_comp``   = hoe FotMob de competitie noemt (enkel als dat afwijkt van ``naam``);
  helpt de juiste ploeg kiezen bij het koppelen.
"""

from __future__ import annotations

COMPETITIES: list[dict] = [
    {"naam": "Premier League",         "land": "Engeland",  "sofascore_ut": 17,  "tm_code": "GB1", "fotmob_ccode3": "ENG"},
    {"naam": "Championship",           "land": "Engeland",  "sofascore_ut": 18,  "tm_code": "GB2", "fotmob_ccode3": "ENG"},
    {"naam": "Bundesliga",             "land": "Duitsland", "sofascore_ut": 35,  "tm_code": "L1",  "fotmob_ccode3": "GER"},
    {"naam": "LaLiga",                 "land": "Spanje",    "sofascore_ut": 8,   "tm_code": "ES1", "fotmob_ccode3": "ESP", "fotmob_comp": "LaLiga"},
    {"naam": "Serie A",                "land": "Italië",    "sofascore_ut": 23,  "tm_code": "IT1", "fotmob_ccode3": "ITA"},
    {"naam": "Ligue 1",               "land": "Frankrijk", "sofascore_ut": 34,  "tm_code": "FR1", "fotmob_ccode3": "FRA"},
    {"naam": "Eredivisie",            "land": "Nederland", "sofascore_ut": 37,  "tm_code": "NL1", "fotmob_ccode3": "NED"},
    {"naam": "Jupiler Pro League",    "land": "België",    "sofascore_ut": 38,  "tm_code": "BE1", "fotmob_ccode3": "BEL", "fotmob_comp": "Belgian Pro League"},
    {"naam": "Challenger Pro League", "land": "België",    "sofascore_ut": 9,   "tm_code": "BE2", "fotmob_ccode3": "BEL", "fotmob_comp": "First Division B"},
    {"naam": "Liga Portugal",        "land": "Portugal",  "sofascore_ut": 238, "tm_code": "PO1", "fotmob_ccode3": "POR"},
]

_PER_UT = {c["sofascore_ut"]: c for c in COMPETITIES}


def by_ut(sofascore_ut: int) -> dict | None:
    return _PER_UT.get(sofascore_ut)
