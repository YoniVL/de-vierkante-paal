"""Vernieuw de test-fixtures met echte responses.

    py tests/opnemen.py            # alle scenario's
    py tests/opnemen.py antwerp    # alleen dit scenario

Nodig: internet + curl_cffi (bv. de host-Python met de deps, of installer/build/payload).
Draai dit opnieuw als een van de sites (Sofascore/FotMob/Transfermarkt) wijzigt.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dvp import config, http_client, store  # noqa: E402

# verse tijdelijke database, zodat de transfers-cache niet meespeelt
_tmp = Path(tempfile.mkdtemp(prefix="dvp_opnemen_"))
config.DATA_DIR = _tmp
config.DB_PATH = _tmp / "opnemen.sqlite"
from dvp.sources import fotmob, preview, sofascore, teamstats, transfermarkt  # noqa: E402
from tests.nep_http import FIXTURES, bestandsnaam, schrijf_fixture  # noqa: E402

# scenario -> ploeg-dict (zoals ploeg.actieve() er een teruggeeft)
SCENARIOS: dict[str, dict] = {
    "antwerp": {
        "naam": "Royal Antwerp FC", "sofascore_id": 2889, "fotmob_id": 9988,
        "fotmob_ccode3": "BEL", "tm_id": 1096, "tm_slug": "royal-antwerpen-fc",
        "competitie": {"naam": "Jupiler Pro League", "sofascore_ut": 38, "tm_code": "BE1"},
    },
    "arsenal": {
        "naam": "Arsenal", "sofascore_id": 42, "fotmob_id": 9825,
        "fotmob_ccode3": "ENG", "tm_id": 11, "tm_slug": "fc-arsenal",
        "competitie": {"naam": "Premier League", "sofascore_ut": 17, "tm_code": "GB1"},
    },
}


def _maak_opnemers(doelmap: Path):
    doelmap.mkdir(parents=True, exist_ok=True)
    echt_json = http_client.get_json_impersonated
    echt_html = http_client.get_html

    def rec_json(url, *, key="sofascore"):
        data = echt_json(url, key=key)
        schrijf_fixture(doelmap / bestandsnaam(url, "json"), json.dumps(data, ensure_ascii=False))
        return data

    def rec_html(url, *, key="transfermarkt"):
        html = echt_html(url, key=key)
        schrijf_fixture(doelmap / bestandsnaam(url, "html"), html)
        return html

    return rec_json, rec_html


def neem_op(scenario: str, ploeg: dict) -> None:
    doelmap = FIXTURES / scenario
    if doelmap.exists():
        shutil.rmtree(doelmap)
    rec_json, rec_html = _maak_opnemers(doelmap)
    sofascore._get = rec_json
    fotmob._get = rec_json
    teamstats._get = rec_json
    transfermarkt.get_html = rec_html

    print(f"\n=== {scenario} ({ploeg['naam']}) ===")
    so = sofascore.fetch(None, ploeg)
    print(f"  sofascore: vorige={bool(so.get('vorige'))} volgende={bool(so.get('volgende'))}")
    vorige = so.get("vorige") or {}
    hint = {"datum": vorige.get("datum"),
            "thuis": (vorige.get("thuis") or {}).get("naam"),
            "uit": (vorige.get("uit") or {}).get("naam")} if vorige.get("datum") else None
    fm = fotmob.fetch(hint, ploeg)
    print(f"  fotmob: beschikbaar={fm.get('beschikbaar')}")
    tm = transfermarkt.fetch(ploeg=ploeg)
    print(f"  transfermarkt: {len(tm.get('spelers') or [])} spelers")
    pv = preview.fetch(so, [s['speler'] for s in (tm.get('spelers') or [])], ploeg)
    print(f"  preview: tegenstander={pv.get('tegenstander_naam')}")
    ts = teamstats.fetch(so, ploeg)
    print(f"  teamstats: {len(ts.get('ploegen') or [])} ploegen, status={ts.get('status')}")

    n = len(list(doelmap.iterdir()))
    print(f"  -> {n} fixture-bestanden")


def main() -> None:
    store.init()
    keuze = sys.argv[1:] or list(SCENARIOS)
    for s in keuze:
        if s not in SCENARIOS:
            print(f"onbekend scenario: {s} (kies uit {', '.join(SCENARIOS)})")
            continue
        neem_op(s, SCENARIOS[s])
    print("\nklaar. Commit de tests/fixtures/-map.")


if __name__ == "__main__":
    main()
