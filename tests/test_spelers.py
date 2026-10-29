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
        r = spelers._radar(self.BLOB)
        self.assertEqual([l["tekst"] for l in r["labels"]][0], "Aanvallen")
        self.assertEqual(r["labels"][0]["waarde"], 60)             # yearShift 0, niet 2
        self.assertEqual(r["gem_label"], "positie")                # blob zonder 'position'
        self.assertEqual(len(r["speler"].split()), 5)
        self.assertEqual(len(r["gem"].split()), 5)
        self.assertEqual(len(r["ringen"]), 4)

    def test_keeper_gebruikt_eigen_assen(self):
        blob = {"playerAttributeOverviews": [
            {"yearShift": 0, "saves": 59, "anticipation": 47, "ballDistribution": 62, "aerial": 58, "tactical": 49}]}
        r = spelers._radar(blob)
        self.assertEqual([l["tekst"] for l in r["labels"]][0], "Reddingen")
        self.assertIsNone(r["gem"])

    def test_geen_data_of_verkeerde_assen_geven_none(self):
        self.assertIsNone(spelers._radar(None))
        self.assertIsNone(spelers._radar({"playerAttributeOverviews": []}))
        keeper_blob = {"playerAttributeOverviews": [{"yearShift": 0, "saves": 50}]}
        self.assertIsNone(spelers._radar(keeper_blob))


class RolTests(unittest.TestCase):
    def test_fotmob_hoofdrol_wint_van_sofascores_grove_letter(self):
        # Renders: Sofascore zegt D/DR, FotMob rangschikt RWB, RB, LB
        p = {"position": "D", "positionsDetailed": ["DR"]}
        rol, lijn, rest = spelers._rol(p, {"positionIdsDesc": "RWB,RB,LB", "_groep": "midfielders"})
        self.assertEqual((rol, lijn, rest), ("RWB", "D", ["RB", "LB"]))

    def test_spits_die_als_middenvelder_staat(self):
        p = {"position": "M", "positionsDetailed": ["ST"]}
        self.assertEqual(spelers._rol(p, None)[:2], ("ST", "F"))

    def test_buitenspeler_is_aanvaller(self):
        p = {"position": "M", "positionsDetailed": ["LW"]}
        self.assertEqual(spelers._rol(p, {"positionIdsDesc": "RW"})[:2], ("RW", "F"))

    def test_middenvelder_met_back_erbij_is_wingback(self):
        p = {"position": "M", "positionsDetailed": ["ML", "DL"]}
        self.assertEqual(spelers._rol(p, None)[:2], ("LWB", "D"))

    def test_zonder_rollen_val_terug_op_selectiegroep_dan_grove_letter(self):
        p = {"position": None, "positionsDetailed": None}
        self.assertEqual(spelers._rol(p, {"_groep": "defenders"}), (None, "D", []))
        self.assertEqual(spelers._rol({"position": "M"}, None), (None, "M", []))
        self.assertEqual(spelers._rol({}, None), (None, None, []))

    def test_keeper_zonder_grove_letter(self):
        p = {"position": None, "positionsDetailed": ["GK"]}
        self.assertEqual(spelers._rol(p, None)[:2], ("GK", "G"))


class NaamTests(unittest.TestCase):
    def test_achternaam_eerst(self):
        self.assertEqual(spelers.sorteernaam("Taishi Brandon Nozawa"), "nozawa taishi brandon")
        self.assertEqual(spelers.sorteernaam("Álvaro Cortés"), "cortes alvaro")
        self.assertEqual(spelers.sorteernaam("Rein Van Helden"), "van helden rein")
        self.assertEqual(spelers.sorteernaam("Hannes Van Der Bruggen"), "van der bruggen hannes")
        self.assertEqual(spelers.sorteernaam("Thomas Van den Keybus"), "van den keybus thomas")
        self.assertEqual(spelers.sorteernaam("Pelé"), "pele")
        self.assertEqual(spelers.sorteernaam(None), "")

    def test_sorteervolgorde(self):
        namen = ["Rein Van Helden", "Xander Dierckx", "Michael Frey"]
        self.assertEqual(sorted(namen, key=spelers.sorteernaam),
                         ["Xander Dierckx", "Michael Frey", "Rein Van Helden"])


class RolOverrideTests(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp(prefix="dvp_rol_"))
        config.DATA_DIR = tmp
        config.DB_PATH = tmp / "t.sqlite"
        store.init()

    def test_standaard_uit_config_en_auto_zet_het_uit(self):
        self.assertEqual(spelers.rol_overrides().get("1920581"), "WF")          # Adekami
        store.set_kv("settings:speler_rollen", {"1920581": "auto", "7": "CB", "8": "onzin"})
        uit = spelers.rol_overrides()
        self.assertNotIn("1920581", uit)
        self.assertEqual(uit.get("7"), "CB")
        self.assertNotIn("8", uit)

    def test_flankaanvaller_is_aanvaller_en_herordent_groepen(self):
        blob = {"ploegen": [{"spelers": [{
            "id": 5, "pos": "D", "pos_nl": "Verdediger", "rol": "Linkse wingback", "rol_code": "LWB",
            "rol_alt": ["Linksback"], "kern": [{"groep": "Verdedigen"}, {"groep": "Aanval"}]}]}]}
        x = spelers.pas_rollen_toe(blob, {"5": "WF"})["ploegen"][0]["spelers"][0]
        self.assertEqual((x["pos"], x["rol"], x["rol_code"]), ("F", "Flankaanvaller", "WF"))
        self.assertEqual(x["rol_alt"], ["Linkse wingback", "Linksback"])
        self.assertEqual(x["kern"][0]["groep"], "Aanval")
        self.assertTrue(x["rol_handmatig"])
        self.assertEqual(blob["ploegen"][0]["spelers"][0]["pos"], "D")           # origineel onaangeroerd

    def test_zonder_overrides_blijft_blob_gelijk(self):
        blob = {"ploegen": []}
        self.assertIs(spelers.pas_rollen_toe(blob, {}), blob)


class VergelijkTests(unittest.TestCase):
    @staticmethod
    def _pool():
        def e(i, goals):
            return {"id": i, "w": {"goals": goals}}
        return {"F": [e(1, 0.2), e(2, 0.4), e(3, 0.6), e(4, 0.8)],
                "M": [e(5, 0.1), e(6, 0.3)], "D": [e(7, 0.0)], "G": []}

    def test_percentiel_richting_en_gelijke_waarden(self):
        self.assertEqual(spelers._percentiel(5, [3, 4, 6, 7], "hoog"), 50)
        self.assertEqual(spelers._percentiel(5, [3, 4, 6, 7], "laag"), 50)
        self.assertEqual(spelers._percentiel(9, [3, 4, 6, 7], "hoog"), 100)
        self.assertEqual(spelers._percentiel(9, [3, 4, 6, 7], "laag"), 0)    # weinig = goed
        self.assertEqual(spelers._percentiel(5, [5, 5], "hoog"), 50)
        self.assertIsNone(spelers._percentiel(5, [], "hoog"))

    def test_percentielen_per_spelerstype(self):
        v = spelers._vergelijk("F", {"minutesPlayed": 900, "goals": 5}, 99, self._pool())  # 0.5/90
        self.assertEqual(v["secties"][0]["rijen"][0]["p"], {"F": 50, "M": 100, "D": 100, "A": 71})
        self.assertEqual(v["n"], {"F": 4, "M": 2, "D": 1, "A": 7})

    def test_zichzelf_telt_niet_mee(self):
        v = spelers._vergelijk("F", {"minutesPlayed": 900, "goals": 5}, 1, self._pool())
        self.assertEqual(v["secties"][0]["rijen"][0]["p"]["F"], 33)          # zonder zichzelf (0.2): 0.5 > enkel 0.4 van 0.4/0.6/0.8

    def test_te_weinig_minuten_of_geen_pool(self):
        self.assertIsNone(spelers._vergelijk("F", {"minutesPlayed": 90, "goals": 1}, 99, self._pool()))
        self.assertIsNone(spelers._vergelijk("F", {"minutesPlayed": 900, "goals": 1}, 99, {}))

    def test_keeper_enkel_t_o_v_keepers(self):
        pool = {"G": [{"id": 1, "w": {"saves": 2.0}}, {"id": 2, "w": {"saves": 4.0}}], "F": []}
        v = spelers._vergelijk("G", {"minutesPlayed": 900, "saves": 30}, 9, pool)   # 3.0/90
        self.assertEqual(list(v["n"]), ["G"])
        self.assertEqual(v["secties"][0]["rijen"][0]["p"], {"G": 50})


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

    # huurspeler: eerste toernooi van het seizoen = moederclub, mainLeague = huidige club
    HUUR = {
        "id": 9, "mainLeague": {"leagueId": 40},
        "statSeasons": [{"tournaments": [
            {"name": "Bundesliga", "tournamentId": 54, "entryId": "0-0"},
            {"name": "Belgian Pro League", "tournamentId": 40, "entryId": "0-1"}]}],
        "firstSeasonStats": {"topStatCard": {}},          # Bundesliga: geen cijfers
    }

    def test_huurspeler_kiest_toernooi_van_huidige_club(self):
        self.assertEqual(spelers._fm_club_toernooi(self.HUUR), ("0-1", "Belgian Pro League"))
        gevraagd = []

        def nep(url, key="sofascore"):
            gevraagd.append(url)
            return {"statsSection": {"items": [{"localizedTitleId": "shooting", "title": "Shooting", "items": [
                {"localizedTitleId": "goals", "title": "Goals", "statValue": "1",
                 "per90": 0.2, "percentileRank": 50.0, "percentileRankPer90": 60.0}]}]}}
        with mock.patch.object(spelers, "_json", nep):
            bron, naam = spelers._fm_stats(self.HUUR)
        self.assertEqual(gevraagd, [f"{spelers.FM}/playerStats?playerId=9&seasonId=0-1"])
        fm = spelers._fm_percentielen(bron, naam)
        self.assertEqual(fm["competitie"], "Belgian Pro League")
        self.assertEqual(fm["secties"][0]["rijen"][0]["pct"], 60)

    def test_gewone_speler_vraagt_geen_extra_stats_op(self):
        d = {**self.HUUR, "mainLeague": {"leagueId": 54}}
        with mock.patch.object(spelers, "_json", side_effect=AssertionError("geen extra call")):
            bron, naam = spelers._fm_stats(d)
        self.assertIs(bron, d)
        self.assertEqual(naam, "Bundesliga")

    def test_zonder_mainleague_val_terug_op_standaard(self):
        d = {"id": 1, "statSeasons": [], "firstSeasonStats": {}}
        self.assertIsNone(spelers._fm_club_toernooi(d))
        self.assertEqual(spelers._fm_stats(d), (d, None))

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
            {"title": "attackers", "members": [{"id": 500, "name": "Jan Peeters", "positionIdsDesc": "RW,ST"}]},
            {"title": "defenders", "members": [{"id": 501, "name": "Piet Bank",
                                                "injury": {"id": "14", "expectedReturn": "Day to day"}}]},
        ]}},
        f"{spelers.FM}/playerData?id=500": FotmobTests.DATA,
    }
    if f"{ss}/unique-tournament/38/season/9/statistics?" in url:
        lijn = url.split("position.in.")[1]
        return {"pages": 1, "results": [
            {"minutesPlayed": 900, "goals": g, "player": {"id": 1000 + i}}
            for i, g in enumerate((1, 2, 4, 8))] if lijn == "F" else []}
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
        self.assertEqual((jan["pos"], jan["rol"], jan["rol_alt"]), ("F", "Rechtsbuiten", ["Spits"]))
        self.assertEqual(eigen["fm_gekoppeld"], 1)
        self.assertEqual(jan["sorteer"], "peeters jan")
        v = jan["vergelijk"]                               # 3 goals in 450 min = 0.6/90
        self.assertEqual(v["n"]["F"], 4)
        goals = v["secties"][0]["rijen"][0]
        self.assertEqual((goals["label"], goals["waarde"]), ("Goals", 0.6))
        self.assertEqual(goals["p"]["F"], 75)              # peers: 0.1, 0.2, 0.4, 0.8 per 90 -> verslaat er 3 van de 4
        self.assertIsNone(piet["vergelijk"])
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
