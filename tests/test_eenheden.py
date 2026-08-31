"""Snelle unit tests zonder net/fixtures: naam-matching, merk-config, ploegenlijst."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dvp import config  # noqa: E402
from dvp.names import NaamKoppelaar, clubs_gelijk, kernwoord, normaliseer  # noqa: E402


class NaamTests(unittest.TestCase):
    def test_normaliseer(self):
        self.assertEqual(normaliseer("Vincent Janssen"), "vincent janssen")
        self.assertEqual(normaliseer("  Kanté "), "kante")
        self.assertEqual(normaliseer("De Cuyper"), "de cuyper")

    def test_kernwoord(self):
        self.assertEqual(kernwoord("Royal Antwerp FC"), "antwerp")
        self.assertEqual(kernwoord("KRC Genk"), "genk")

    def test_clubs_gelijk(self):
        self.assertTrue(clubs_gelijk("Club Brugge KV", "Club Brugge"))
        self.assertTrue(clubs_gelijk("KRC Genk", "Genk"))
        self.assertFalse(clubs_gelijk("Anderlecht", "Antwerp"))

    def test_koppelaar(self):
        k = NaamKoppelaar(["Vincent Janssen", "Arthur Vermeeren"])
        self.assertEqual(k.koppel("V. Janssen"), "Vincent Janssen")
        self.assertEqual(k.koppel("Vermeeren"), "Arthur Vermeeren")
        self.assertIsNone(k.koppel("Onbekende Speler"))

    def test_koppelaar_alias(self):
        k = NaamKoppelaar(["V Janssen"], {"vincent janssen": "V Janssen"})
        self.assertEqual(k.koppel("Vincent Janssen"), "V Janssen")


class FotmobZoektermTests(unittest.TestCase):
    def test_naam_varianten(self):
        from dvp.app import _naam_varianten
        v = _naam_varianten("Royale Union Saint-Gilloise")
        self.assertEqual(v[0], "Royale Union Saint-Gilloise")
        self.assertIn("Union St", v)                       # de handmatige alias
        self.assertNotIn("union", [x.lower() for x in v])  # te generiek, niet los

    def test_junk_filter(self):
        from dvp.sources.fotmob import _JUNK
        for junk in ["Arsenal (W)", "Ajax U21", "Bayern München II", "Jong PSV", "Real Madrid Youth"]:
            self.assertTrue(_JUNK.search(junk), junk)
        for ok in ["Arsenal", "Real Madrid", "Union St.Gilloise", "Inter", "Bayer 04 Leverkusen"]:
            self.assertFalse(_JUNK.search(ok), ok)


class MerkTests(unittest.TestCase):
    def _merk(self, inhoud):
        tmp = Path(tempfile.mkdtemp(prefix="dvp_merk_"))
        (tmp / "merk.json").write_text(json.dumps(inhoud), encoding="utf-8")
        import dvp.merk as m
        m.config.BASE_DIR = tmp
        m.merk.cache_clear()
        return m

    def test_geen_merk_json_is_dvp(self):
        tmp = Path(tempfile.mkdtemp(prefix="dvp_merk_"))
        import dvp.merk as m
        m.config.BASE_DIR = tmp
        m.merk.cache_clear()
        self.assertEqual(m.app_naam(), "De Vierkante Paal")
        self.assertFalse(m.toon_kiezer())
        self.assertTrue(m.toon_whoscored())     # DVP heeft WhoScored

    def test_generiek(self):
        m = self._merk({"app_naam": "Aftrap", "toon_kiezer": True, "whoscored": False})
        self.assertEqual(m.app_naam(), "Aftrap")
        self.assertTrue(m.toon_kiezer())
        self.assertFalse(m.toon_whoscored())

    def test_thema_dvp_is_none(self):
        tmp = Path(tempfile.mkdtemp(prefix="dvp_merk_"))
        import dvp.merk as m
        m.config.BASE_DIR = tmp
        m.merk.cache_clear()
        self.assertIsNone(m.thema())

    def test_thema_accent(self):
        m = self._merk({"app_naam": "Aftrap", "accent": "#2fd074"})
        t = m.thema()
        self.assertEqual(t["accent"], "#2fd074")
        self.assertEqual(t["accent_diep"], "#2fd074")   # geen accent_diep -> gelijk aan accent
        self.assertEqual(t["accent_zwak"], "rgba(47,208,116,0.14)")

    def test_thema_accent_gelijk_aan_dvp_is_none(self):
        m = self._merk({"app_naam": "Aftrap", "accent": "#ff4d67"})
        self.assertIsNone(m.thema())

    def test_utf8_bom(self):
        tmp = Path(tempfile.mkdtemp(prefix="dvp_merk_"))
        (tmp / "merk.json").write_bytes(b"\xef\xbb\xbf" + b'{"app_naam":"Aftrap"}')
        import dvp.merk as m
        m.config.BASE_DIR = tmp
        m.merk.cache_clear()
        self.assertEqual(m.app_naam(), "Aftrap")

    def tearDown(self):
        import dvp.merk as m
        m.config.BASE_DIR = config.BASE_DIR
        m.merk.cache_clear()


class PoortTests(unittest.TestCase):
    """DVP en Aftrap moeten naast elkaar kunnen draaien -> verschillende poort."""

    def setUp(self):
        self._orig = config.BASE_DIR
        self._env = config.os.environ.pop("DVP_PORT", None)

    def tearDown(self):
        config.BASE_DIR = self._orig
        if self._env is not None:
            config.os.environ["DVP_PORT"] = self._env

    def _tmp(self, **bestanden):
        tmp = Path(tempfile.mkdtemp(prefix="dvp_poort_"))
        for naam, inhoud in bestanden.items():
            (tmp / naam.replace("_", ".")).write_text(inhoud, encoding="utf-8")
        config.BASE_DIR = tmp
        return tmp

    def test_geen_merk_json_is_8756(self):
        self._tmp()
        self.assertEqual(config._poort(), 8756)

    def test_aftrap_merk_json_poort(self):
        self._tmp(merk_json=json.dumps({"app_naam": "Aftrap", "poort": 8757}))
        self.assertEqual(config._poort(), 8757)

    def test_merk_json_zonder_poort_is_8756(self):
        self._tmp(merk_json=json.dumps({"app_naam": "Aftrap"}))
        self.assertEqual(config._poort(), 8756)

    def test_poort_txt_wint(self):
        self._tmp(poort_txt="9001", merk_json=json.dumps({"poort": 8757}))
        self.assertEqual(config._poort(), 9001)

    def test_env_wint_altijd(self):
        self._tmp(merk_json=json.dumps({"poort": 8757}))
        config.os.environ["DVP_PORT"] = "12345"
        try:
            self.assertEqual(config._poort(), 12345)
        finally:
            config.os.environ.pop("DVP_PORT", None)


class PloegTests(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp(prefix="dvp_ploeg_"))
        config.DATA_DIR = tmp
        config.DB_PATH = tmp / "t.sqlite"
        from dvp import store
        store.init()
        import dvp.ploeg as p
        import dvp.merk as m
        m.config.BASE_DIR = tmp   # geen merk.json -> DVP-default
        m.merk.cache_clear()
        self.p = p

    def _ploeg(self, sid, naam):
        return {"naam": naam, "sofascore_id": sid, "fotmob_id": sid, "fotmob_ccode3": "BEL",
                "tm_id": sid, "tm_slug": naam.lower(),
                "competitie": {"naam": "Test", "sofascore_ut": 1, "tm_code": "X"}}

    def test_zet_actief_en_lijst(self):
        for sid, naam in [(1, "Een"), (2, "Twee"), (3, "Drie")]:
            self.p.zet_actief(self._ploeg(sid, naam), ververs=False)
        self.assertEqual(self.p.actieve()["sofascore_id"], 3)          # laatste = actief
        namen = [x["naam"] for x in self.p.lijst()]
        self.assertEqual(namen, ["Drie", "Twee", "Een"])              # nieuwste eerst

    def test_vastprikken(self):
        self.p.zet_actief(self._ploeg(1, "Een"), ververs=False)
        self.p.zet_actief(self._ploeg(2, "Twee"), ververs=False)
        self.p.prik(1, True)
        lijst = self.p.lijst()
        self.assertTrue(lijst[0]["vast"])
        self.assertEqual(lijst[0]["sofascore_id"], 1)                 # vastgeprikt bovenaan

    def test_bekend_en_verwijder(self):
        self.p.zet_actief(self._ploeg(7, "Zeven"), ververs=False)
        self.p.zet_actief(self._ploeg(8, "Acht"), ververs=False)
        self.assertIsNotNone(self.p.bekend(7))
        self.p.verwijder(7)
        self.assertIsNone(self.p.bekend(7))
        self.p.verwijder(8)                                            # actief -> blijft
        self.assertIsNotNone(self.p.bekend(8))

    def test_recent_gecapt_op_8(self):
        for sid in range(1, 13):
            self.p.zet_actief(self._ploeg(sid, f"P{sid}"), ververs=False)
        recent = [x for x in self.p.lijst() if not x["vast"]]
        self.assertEqual(len(recent), 8)


if __name__ == "__main__":
    unittest.main()
