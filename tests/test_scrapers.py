"""Draait de scrapers tegen opgenomen responses (tests/fixtures/) en controleert
dat de vorm van de data klopt. Faalt = een van de sites is waarschijnlijk gewijzigd
of de parser is stuk.  Vernieuw de fixtures met  py tests/opnemen.py .
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dvp import aggregate, config, store  # noqa: E402
from dvp.sources import fotmob, preview, sofascore, teamstats, transfermarkt  # noqa: E402
from tests.nep_http import NepHttp  # noqa: E402
from tests.opnemen import SCENARIOS  # noqa: E402


def _verse_db():
    tmp = Path(tempfile.mkdtemp(prefix="dvp_test_"))
    config.DATA_DIR = tmp
    config.DB_PATH = tmp / "test.sqlite"
    store.init()


class ScraperTests(unittest.TestCase):
    scenario = "antwerp"

    @classmethod
    def setUpClass(cls):
        _verse_db()
        cls.ploeg = SCENARIOS[cls.scenario]
        with NepHttp(cls.scenario):
            cls.so = sofascore.fetch(None, cls.ploeg)
            v = cls.so.get("vorige") or {}
            hint = ({"datum": v.get("datum"),
                     "thuis": (v.get("thuis") or {}).get("naam"),
                     "uit": (v.get("uit") or {}).get("naam")}
                    if v.get("datum") else None)
            cls.fm = fotmob.fetch(hint, cls.ploeg)
            cls.tm = transfermarkt.fetch(ploeg=cls.ploeg)
            cls.pv = preview.fetch(cls.so, [s["speler"] for s in cls.tm["spelers"]], cls.ploeg)
            store.set_kv("bron:sofascore", cls.so)
            store.set_kv("bron:fotmob", cls.fm)
            store.set_kv("bron:transfermarkt", cls.tm)
            store.save_stat_snapshot(aggregate.snapshot_rijen(cls.tm), "ss" + str(cls.ploeg["sofascore_id"]))
            store.set_kv("bron:voorbeschouwing", cls.pv)
            cls.ts = teamstats.fetch(cls.so, cls.ploeg)
            store.set_kv("bron:teamstats", cls.ts)
            cls.ov = aggregate.bouw_overzicht()

    # --- Sofascore ---------------------------------------------------
    def test_sofascore_vorige_match(self):
        v = self.so["vorige"]
        self.assertIsNotNone(v["thuis"]["score"])
        self.assertIsNotNone(v["uit"]["score"])
        self.assertGreaterEqual(len(v["opstelling"]), 10)   # spelers met minuten
        self.assertTrue(any(s["rating"] for s in v["opstelling"]))

    def test_sofascore_volgende_en_voorbeschouwing(self):
        self.assertIn("volgende", self.so)
        self.assertTrue(self.so["volgende"]["tegenstander"]["naam"])
        vb = self.so["voorbeschouwing"]
        self.assertGreaterEqual(len(vb["klassement"]), 14)
        self.assertLessEqual(len(vb["klassement"]), 24)
        self.assertTrue(any(r["antwerp"] for r in vb["klassement"]))
        self.assertTrue(vb["topschutters"].get("goals"))

    def test_sofascore_competitie_context(self):
        c = self.so["competitie"]
        self.assertEqual(c["ut"], self.ploeg["competitie"]["sofascore_ut"])
        self.assertTrue(c["seizoen"])

    # --- FotMob ----------------------------------------------------
    def test_fotmob_beschikbaar_met_ratings(self):
        self.assertTrue(self.fm["beschikbaar"])
        self.assertTrue(self.fm.get("ratings_antwerp"))

    # --- Transfermarkt -------------------------------------------
    def test_transfermarkt_spelers(self):
        sp = self.tm["spelers"]
        self.assertGreaterEqual(len(sp), 18)
        met_min = [s for s in sp if s["minuten"] > 0]
        self.assertTrue(met_min)
        for s in met_min:
            self.assertGreaterEqual(s["wedstrijden"], 1)
            self.assertLessEqual(s["goals"], s["wedstrijden"] + 5)
            self.assertGreaterEqual(s["minuten"], s["wedstrijden"])  # min ≥ apps (elk ≥ 1')

    def test_transfermarkt_uitval_vorm(self):
        u = self.tm["uitval"]
        self.assertIn("geblesseerd", u)
        self.assertIn("geschorst", u)

    # --- Preview / connecties ------------------------------------
    def test_preview(self):
        self.assertTrue(self.pv["tegenstander_naam"])
        self.assertIsNotNone(self.pv["connecties"])

    # --- Aggregatie ---------------------------------------------
    def test_bouw_overzicht(self):
        o = self.ov
        self.assertGreaterEqual(len(o["scoretabel"]), 10)
        self.assertGreaterEqual(len(o["stattabel"]), 18)
        self.assertTrue(o["opstellingen"]["vorige_antwerp"])
        # minstens de helft van de scoretabel heeft een TM-profiel-link
        met_link = [r for r in o["scoretabel"] if r.get("profiel_url")]
        self.assertGreaterEqual(len(met_link), len(o["scoretabel"]) // 2)
        self.assertIn("diagnose", o)

    def test_teamstats(self):
        ts = self.ts
        self.assertEqual(ts["status"], "ok")
        self.assertEqual(len(ts["ploegen"]), 2)
        rollen = {p["rol"] for p in ts["ploegen"]}
        self.assertEqual(rollen, {"thuis", "uit"})
        # de scenario's spelen een competitiewedstrijd -> zelfde competitie
        self.assertTrue(ts["zelfde_competitie"])
        for p in ts["ploegen"]:
            self.assertTrue(p["naam"])
            self.assertTrue(p["competitie"]["naam"])
            self.assertGreaterEqual(p["competitie"]["ploegen"], 14)
            self.assertGreaterEqual(p["seizoen"]["matches"], 1)
            self.assertIsNotNone(p["seizoen"]["goals"])
            dp = p["doelpunten"]
            self.assertIsNotNone(dp)
            self.assertGreaterEqual(dp["matchen_met_data"], 1)
            # shotmap-goals ~= Sofascore-seizoensgoals (competitie), kleine marge voor eigen goals/gaten
            self.assertLessEqual(abs(dp["gescoord"]["totaal"] - (p["seizoen"]["goals"] or 0)), 3)
            self.assertEqual(len(dp["timing_voor"]), 6)
            self.assertEqual(sum(dp["timing_voor"]), dp["gescoord"]["totaal"])
            self.assertEqual(sum(dp["timing_tegen"]), dp["geincasseerd"]["totaal"])
            # schotkwaliteit + posities voor het veldje
            self.assertGreater(dp["schoten_voor"], 0)
            self.assertGreater(dp["xg_per_schot_voor"], 0)
            self.assertEqual(len(dp["punten_voor"]), dp["gescoord"]["totaal"]
                             - dp["gescoord"]["fases"].get("Eigen doelpunt", 0))
            for pt in dp["punten_voor"]:
                self.assertIn("x", pt); self.assertIn("xg", pt); self.assertIn("fase", pt)
            # aanvalszones ~ 100%
            if dp["zones"]:
                self.assertAlmostEqual(sum(dp["zones"].values()), 100, delta=3)
            # strafschoppen uit de season-stats
            self.assertIsNotNone(p["seizoen"]["pen_benut"])
            self.assertTrue(p["ranking"])
            self.assertTrue(any(r["markering"] for r in p["ranking"]))
            self.assertTrue(p["selectie"]["waarde_totaal_m"] > 0)
        # aggregatie neemt het mee
        self.assertTrue(self.ov["teamstats"]["ploegen"])

    def test_praatpunten(self):
        pp = self.ov["praatpunten"]
        self.assertGreaterEqual(len(pp), 4)
        self.assertTrue(all(isinstance(x, str) and x.strip() for x in pp))
        # de uitslag van de vorige match hoort erbij te staan
        self.assertTrue(any("Vorige match" in x for x in pp))


class ScraperTestsArsenal(ScraperTests):
    scenario = "arsenal"


if __name__ == "__main__":
    unittest.main()
