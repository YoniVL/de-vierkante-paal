"""Elke fetch() zet een 'status'; app._controleer maakt er een BronLeegError van;
aggregate._bron_status vat het samen voor de stempel."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dvp import aggregate, app, config, store  # noqa: E402
from dvp.sources import fotmob, sofascore, transfermarkt  # noqa: E402
from tests.nep_http import NepHttp  # noqa: E402
from tests.opnemen import SCENARIOS  # noqa: E402


class StatusTests(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp(prefix="dvp_status_"))
        config.DATA_DIR = tmp
        config.DB_PATH = tmp / "t.sqlite"
        store.init()

    def test_status_ok_bij_echte_data(self):
        with NepHttp("antwerp"):
            self.assertEqual(sofascore.fetch(None, SCENARIOS["antwerp"])["status"], "ok")
            self.assertEqual(transfermarkt.fetch(ploeg=SCENARIOS["antwerp"])["status"], "ok")

    def test_transfermarkt_leeg_bij_lege_pagina(self):
        echt = transfermarkt.get_html
        transfermarkt.get_html = lambda *a, **k: "<html><body>geen tabel</body></html>"
        try:
            blob = transfermarkt.fetch(ploeg={"tm_id": 1, "tm_slug": "x"})
        finally:
            transfermarkt.get_html = echt
        self.assertEqual(blob["spelers"], [])
        self.assertEqual(blob["status"]["code"], "leeg")
        with self.assertRaises(app.BronLeegError):
            app._controleer(blob)

    def test_fotmob_leeg_bij_lege_response(self):
        echt = fotmob._get
        fotmob._get = lambda *a, **k: {}
        try:
            blob = fotmob.fetch(None, {"fotmob_id": 1})
        finally:
            fotmob._get = echt
        self.assertFalse(blob["beschikbaar"])
        self.assertEqual(blob["status"]["code"], "leeg")
        with self.assertRaises(app.BronLeegError):
            app._controleer(blob)

    def test_controleer_laat_ok_door(self):
        app._controleer({"status": "ok"})            # geen exception
        app._controleer({})                          # geen status -> geen exception

    def test_bron_status_overzicht(self):
        store.set_kv("bron:sofascore", {"status": "ok"})            # vers + ok
        store.set_kv("bron:transfermarkt", {"status": "ok"})
        store.set_kv("fouten", {"fotmob": {"kort": "stuk"}})        # fout
        st = aggregate._bron_status()
        self.assertEqual(st["sofascore"], "ok")
        self.assertEqual(st["fotmob"], "fout")
        self.assertEqual(st["voorbeschouwing"], "leeg")            # nooit opgehaald


if __name__ == "__main__":
    unittest.main()
