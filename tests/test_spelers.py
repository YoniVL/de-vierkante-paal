"""Spelersstatistieken: kerncijfers per positie, radar, FotMob-percentielen en een
volledige fetch() met nagebootste Sofascore/FotMob-antwoorden (geen netwerk)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dvp import aggregate, config, store  # noqa: E402
from dvp.sources import spelers  # noqa: E402


def _groep(kern, titel):
    return next(g for g in kern if g["groep"] == titel)


def _rij(groep, label):
    return next(r for r in groep["rijen"] if r["label"] == label)


class KernTests(unittest.TestCase):
    STATS = {"minutesPlayed": 450, "goals": 3, "expectedGoals": 2.5, "totalShots": 15,
             "accuratePassesPercentage": 71.234, "yellowCards": 2, "tacklesWon": 5}

    def test_aanvaller_toont_aanval_eerst_met_per_90(self):
        kern = spelers._kern("F", self.STATS)
        self.assertEqual(kern[0]["groep"], "Aanval")
        goals = _rij(_groep(kern, "Aanval"), "Goals")
        self.assertEqual(goals["waarde"], 3)
        self.assertEqual(goals["p90"], 0.6)
        self.assertEqual(_rij(_groep(kern, "Aanval"), "xG")["waarde"], 2.5)

    def test_percentage_en_totaal_hebben_geen_per_90(self):
        kern = spelers._kern("F", self.STATS)
        pas = _rij(_groep(kern, "Opbouw"), "Passnauwkeurigheid")
        self.assertEqual((pas["waarde"], pas["eenheid"], pas["p90"]), (71.2, "%", None))
        self.assertIsNone(_rij(_groep(kern, "Fysiek & discipline"), "Gele kaarten")["p90"])

    def test_verdediger_begint_met_verdedigen(self):
        self.assertEqual(spelers._kern("D", self.STATS)[0]["groep"], "Verdedigen")

    def test_per_90_vereist_minstens_90_minuten(self):
        kern = spelers._kern("F", {**self.STATS, "minutesPlayed": 60})
        self.assertIsNone(_rij(_groep(kern, "Aanval"), "Goals")["p90"])

    def test_ontbrekende_velden_geven_geen_rij(self):
        kern = spelers._kern("F", {"minutesPlayed": 450, "goals": 1})
        labels = [r["label"] for g in kern for r in g["rijen"]]
        self.assertEqual(labels, ["Goals"])

    def test_keeper_goals_voorkomen(self):
        kern = spelers._kern("G", {"minutesPlayed": 900, "saves": 30, "goalsConceded": 8,
                                   "expectedGoalsOnTargetConceded": 10.5})
        keepen = _groep(kern, "Keepen")
        self.assertEqual(keepen["rijen"][0]["label"], "Reddingen")
        self.assertEqual(_rij(keepen, "Goals voorkomen (xGOT − tegen)")["waarde"], 2.5)


class RadarTests(unittest.TestCase):
    BLOB = {
        "playerAttributeOverviews": [
            {"yearShift": 2, "attacking": 10, "technical": 10, "tactical": 10, "defending": 10, "creativity": 10},
            {"yearShift": 0, "attacking": 60, "technical": 62, "tactical": 43, "defending": 38, "creativity": 52},
        ],
        "averageAttributeOverviews": [
            {"yearShift": 0, "attacking": 61, "technical": 54, "tactical": 43, "defending": 32, "creativity": 45}],
    }

    def test_uitspeler_met_gemiddelde(self):
        r = spelers._radar("F", self.BLOB)
        self.assertEqual([l["tekst"] for l in r["labels"]][0], "Aanvallen")
        self.assertEqual(r["labels"][0]["waarde"], 60)             # yearShift 0, niet 2
        self.assertEqual(len(r["speler"].split()), 5)
        self.assertEqual(len(r["gem"].split()), 5)
        self.assertEqual(len(r["ringen"]), 4)

    def test_keeper_gebruikt_eigen_assen(self):
        blob = {"playerAttributeOverviews": [
            {"yearShift": 0, "saves": 59, "anticipation": 47, "ballDistribution": 62, "aerial": 58, "tactical": 49}]}
        r = spelers._radar("G", blob)
        self.assertEqual([l["tekst"] for l in r["labels"]][0], "Reddingen")
        self.assertIsNone(r["gem"])

    def test_geen_data_of_verkeerde_assen_geven_none(self):
        self.assertIsNone(spelers._radar("F", None))
        self.assertIsNone(spelers._radar("F", {"playerAttributeOverviews": []}))
        keeper_blob = {"playerAttributeOverviews": [{"yearShift": 0, "saves": 50}]}
        self.assertIsNone(spelers._radar("G", keeper_blob))


class FotmobTests(unittest.TestCase):
    DATA = {
        "statSeasons": [{"seasonName": "2026/2027", "tournaments": [{"name": "Belgian Pro League"}]}],
        "firstSeasonStats": {"statsSection": {"items": [
            {"localizedTitleId": "shooting", "title": "Shooting", "items": [
                {"localizedTitleId": "expected_goals", "title": "xG", "statValue": "3.5",
                 "per90": 0.5, "percentileRank": 60.0, "percentileRankPer90": 71.6},
                {"localizedTitleId": "onbekend_nieuw", "title": "Nieuwe stat", "statValue": "2",
                 "per90": None, "percentileRank": 40.2, "percentileRankPer90": None},
            ]},
            {"localizedTitleId": "discipline", "title": "Discipline", "items": [
                {"localizedTitleId": "red_cards", "title": "Red cards", "statValue": "0",
                 "per90": 0.0, "percentileRank": 90.0, "percentileRankPer90": 100.0}]},
        ]}},
    }

    def test_percentielen_nl_en_per_90_voorrang(self):
        fm = spelers._fm_percentielen(self.DATA)
        self.assertEqual(fm["competitie"], "Belgian Pro League")
        schieten = fm["secties"][0]
        self.assertEqual(schieten["titel"], "Schieten")
        self.assertEqual((schieten["rijen"][0]["label"], schieten["rijen"][0]["pct"]), ("xG", 72))
        # zonder per-90: gewoon het seizoenspercentiel; onbekende stat: Engelse titel
        self.assertEqual((schieten["rijen"][1]["label"], schieten["rijen"][1]["pct"]), ("Nieuwe stat", 40))
        self.assertEqual(fm["secties"][1]["rijen"][0]["label"], "Rode kaarten")

    def test_zonder_statistieken_geen_blok(self):
        self.assertIsNone(spelers._fm_percentielen({"firstSeasonStats": {"topStatCard": {}}}))
        self.assertIsNone(spelers._fm_percentielen({}))

    def test_blessure_tekst(self):
        self.assertIsNone(spelers._blessure(None))
        inj = {"name": "Knee injury", "expectedReturn": {"expectedReturnFallback": "Day to day"}}
        self.assertEqual(spelers._blessure(inj), "Knie blessure (terug: dag per dag)")
        self.assertEqual(spelers._blessure({"id": "14", "expectedReturn": "Day to day"}),
                         "geblesseerd (terug: dag per dag)")


# --- volledige fetch met nagebootste responses ------------------------------------------------
def _nep(url: str, *, key: str = "sofascore"):
    ss = spelers.SS
    antwoorden = {
        f"{ss}/team/1/players": {"players": [
            {"player": {"id": 11, "name": "Jan Peeters", "position": "F", "shirtNumber": 9,
                        "height": 180, "preferredFoot": "Right", "proposedMarketValue": 1_500_000,
                        "dateOfBirthTimestamp": 946684800, "country": {"name": "Belgium"}}},
            {"player": {"id": 12, "name": "Piet Bank", "position": "D"}},
        ]},
        f"{ss}/team/2/players": {"players": []},
        f"{ss}/player/11/unique-tournament/38/season/9/statistics/overall": {"statistics": {
            "appearances": 5, "matchesStarted": 4, "minutesPlayed": 450, "goals": 3, "assists": 1,
            "expectedGoals": 2.5, "expectedAssists": 0.8, "rating": 7.123}},
        f"{ss}/player/12/unique-tournament/38/season/9/statistics/overall": {"statistics": {}},
        f"{ss}/player/11/attribute-overviews": RadarTests.BLOB,
        f"{spelers.FM}/teams?id=100&ccode3=BEL": {"squad": {"squad": [
            {"title": "coach", "members": [{"id": 1, "name": "Trainer"}]},
            {"title": "attackers", "members": [{"id": 500, "name": "Jan Peeters"}]},
            {"title": "defenders", "members": [{"id": 501, "name": "Piet Bank",
                                                "injury": {"id": "14", "expectedReturn": "Day to day"}}]},
        ]}},
        f"{spelers.FM}/playerData?id=500": FotmobTests.DATA,
    }
    if url not in antwoorden:
        raise RuntimeError(f"onverwachte URL in test: {url}")
    return antwoorden[url]


def _nep_teamstats(url: str, **k):
    """teamstats leest enkel de FotMob-selectie en (voor de competitie van de tegenstander)
    de events van de tegenstander; die laatste laten we falen -> valt terug op onze competitie."""
    if "/events/" in url:
        raise RuntimeError("geen events in de test")
    return _nep(url, **k)


class FetchTests(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp(prefix="dvp_spelers_"))
        config.DATA_DIR = tmp
        config.DB_PATH = tmp / "t.sqlite"
        store.init()
        self.so = {"competitie": {"ut": 38, "seizoen": 9, "naam": "Pro League"},
                   "volgende": {"tegenstander": {"id": 2, "naam": "Tegenstander"}}}
        self.ploeg = {"sofascore_id": 1, "naam": "Eigen", "fotmob_id": 100, "fotmob_ccode3": "BEL"}
        store.set_kv("bron:teamstats", {"ploegen": [{"sofascore_id": 2, "fotmob_id": 200}]})

    def _fetch(self):
        with mock.patch("dvp.sources.spelers._get", _nep), \
             mock.patch("dvp.sources.teamstats._get", _nep_teamstats):
            return spelers.fetch(self.so, self.ploeg)

    def test_volledige_fetch(self):
        out = self._fetch()
        self.assertEqual(out["status"], "ok")
        self.assertEqual([p["wie"] for p in out["ploegen"]], ["eigen", "tegenstander"])
        eigen = out["ploegen"][0]
        jan, piet = eigen["spelers"]                      # Jan speelde -> staat eerst
        self.assertEqual((jan["naam"], jan["apps"], jan["minuten"], jan["goals"]), ("Jan Peeters", 5, 450, 3))
        self.assertEqual((jan["rating"], jan["xg"], jan["waarde_m"]), (7.12, 2.5, 1.5))
        self.assertTrue(jan["kern"] and jan["radar"] and jan["fm"])
        self.assertEqual(eigen["fm_gekoppeld"], 1)
        self.assertEqual(piet["apps"], 0)                 # niet gespeeld: geen details, wel blessure
        self.assertEqual(piet["kern"], [])
        self.assertEqual(piet["blessure"], "geblesseerd (terug: dag per dag)")
        self.assertEqual(out["ploegen"][1]["spelers"], [])

    def test_zonder_competitie_status_leeg(self):
        self.so = {}
        out = spelers.fetch(self.so, self.ploeg)
        self.assertEqual(out["status"]["code"], "leeg")

    def test_selectie_fout_wordt_status_leeg_met_oorzaak(self):
        def stuk(url, **k):
            raise ConnectionError("HTTP Error 403")
        with mock.patch("dvp.sources.spelers._get", stuk), \
             mock.patch("dvp.sources.teamstats._get", stuk):
            out = spelers.fetch(self.so, self.ploeg)
        self.assertEqual(out["status"]["code"], "leeg")
        self.assertIn("403", out["status"]["tekst"])

    def test_overzicht_bevat_spelers_en_status(self):
        store.set_kv("bron:spelers", self._fetch())
        o = aggregate.bouw_overzicht()
        self.assertEqual(len(o["spelers"]["ploegen"]), 2)
        self.assertEqual(aggregate._bron_status()["spelers"], "ok")
        self.assertTrue(o["tijdstippen"]["spelers"])


if __name__ == "__main__":
    unittest.main()
