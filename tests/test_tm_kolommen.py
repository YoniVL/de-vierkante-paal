"""Transfermarkt-kolommen: op kop lezen én de positionele fallback moeten
hetzelfde resultaat geven."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup  # noqa: E402

from dvp.sources import transfermarkt as tm  # noqa: E402
from tests.nep_http import NepHttp, bestandsnaam, lees_fixture  # noqa: E402


def _leistungsdaten_html(scenario: str, club_id: int, slug: str) -> str:
    url = tm._leistungsdaten_url(club_id, slug, 2026)
    return lees_fixture(NepHttp(scenario).map / bestandsnaam(url, "html"))


class KolomTests(unittest.TestCase):
    def test_kolom_index_herkent_de_koppen(self):
        html = _leistungsdaten_html("antwerp", 1096, "royal-antwerpen-fc")
        tabel = BeautifulSoup(html, "html.parser").select_one("table.items")
        kol = tm._kolom_index(tabel)
        for veld in ("wedstrijden", "goals", "assists", "geel", "tweede_geel", "rood", "minuten"):
            self.assertIn(veld, kol, f"kolom '{veld}' niet gevonden in de kop")
        # de statistiekkolommen komen ná de naam/leeftijd/nat-kolommen
        self.assertGreater(kol["wedstrijden"], 3)
        self.assertLess(kol["wedstrijden"], kol["goals"])

    def test_kop_en_fallback_geven_hetzelfde(self):
        for scen, cid, slug in (("antwerp", 1096, "royal-antwerpen-fc"),
                                ("arsenal", 11, "fc-arsenal")):
            ploeg = {"tm_id": cid, "tm_slug": slug}
            nep = NepHttp(scen)
            with nep:
                op_kop = tm.fetch(ploeg=ploeg)["spelers"]

            # forceer de fallback door de sorteerlinks uit de kop te strippen
            # (blijft uit de fixtures lezen, geen netwerk)
            def zonder_koplinks(url, *, key="transfermarkt", _nep=nep):
                html = _nep.get_html(url, key=key)
                if "leistungsdaten" in url:
                    html = re.sub(r'href="[^"]*/sort/[^"]*"', 'href="#"', html)
                return html

            with NepHttp(scen):
                tm.get_html = zonder_koplinks
                fallback = tm.fetch(ploeg=ploeg)["spelers"]

            self.assertEqual(len(op_kop), len(fallback), scen)
            for a, b in zip(op_kop, fallback):
                self.assertEqual(
                    (a["speler"], a["wedstrijden"], a["goals"], a["assists"],
                     a["geel"], a["rood"], a["minuten"]),
                    (b["speler"], b["wedstrijden"], b["goals"], b["assists"],
                     b["geel"], b["rood"], b["minuten"]),
                    f"{scen}: {a['speler']}",
                )


if __name__ == "__main__":
    unittest.main()
