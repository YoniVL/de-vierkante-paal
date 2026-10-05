"""Serveert opgenomen HTTP-responses uit tests/fixtures/<scenario>/ i.p.v. het net.

Gebruik in een test:

    from tests.nep_http import NepHttp
    with NepHttp("antwerp"):
        blob = sofascore.fetch(None, PLOEG)
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from pathlib import Path
from unittest import mock

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def bestandsnaam(url: str, ext: str) -> str:
    # Fixtures zijn opgenomen toen de API nog op api.sofascore.com stond.
    url = url.replace("https://www.sofascore.com/api/", "https://api.sofascore.com/api/")
    schoon = re.sub(r"[^A-Za-z0-9]+", "_", url).strip("_")[:90]
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    return f"{schoon}__{h}.{ext}.gz"


def lees_fixture(pad: Path) -> str:
    return gzip.decompress(pad.read_bytes()).decode("utf-8")


def schrijf_fixture(pad: Path, tekst: str) -> None:
    pad.write_bytes(gzip.compress(tekst.encode("utf-8"), 9))


class NepHttp:
    """Contextmanager die de scraper-HTTP-calls omleidt naar fixture-bestanden."""

    def __init__(self, scenario: str):
        self.map = FIXTURES / scenario
        self._patchers: list = []

    # --- de vervangers -------------------------------------------------
    def _pad(self, url: str, ext: str) -> Path:
        p = self.map / bestandsnaam(url, ext)
        if not p.exists():
            raise AssertionError(
                f"ontbrekende fixture:\n  URL : {url}\n  pad : {p}\n"
                f"  -> draai  py tests/opnemen.py  om de fixtures te vernieuwen"
            )
        return p

    def get_json(self, url: str, *, key: str = "sofascore") -> dict:
        return json.loads(lees_fixture(self._pad(url, "json")))

    def get_html(self, url: str, *, key: str = "transfermarkt") -> str:
        return lees_fixture(self._pad(url, "html"))

    # --- context -----------------------------------------------------
    def __enter__(self):
        for doel, fn in (
            ("dvp.sources.sofascore._get", self.get_json),
            ("dvp.sources.fotmob._get", self.get_json),
            ("dvp.sources.transfermarkt.get_html", self.get_html),
            ("dvp.sources.teamstats._get", self.get_json),
        ):
            p = mock.patch(doel, fn)
            p.start()
            self._patchers.append(p)
        return self

    def __exit__(self, *exc):
        for p in self._patchers:
            p.stop()
        self._patchers.clear()
        return False
