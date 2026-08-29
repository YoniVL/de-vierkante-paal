"""Lokale webserver voor de voorbereidingstool. Start met: python -m dvp.app"""

from __future__ import annotations

import datetime as _dt
import json
import mimetypes
import os
import re
import sys
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import aggregate, assets, competities, config, export, mdrender, merk, ploeg, store
from .sources import fotmob, preview, sofascore, transfermarkt

_TEMPLATES = Path(__file__).parent / "templates"
_STATIC = Path(__file__).parent / "static"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES)),
    autoescape=select_autoescape(["html"]),
)


def _fmt_dt(waarde: str | None) -> str:
    if not waarde:
        return "nog niet opgehaald"
    try:
        return _dt.datetime.fromisoformat(waarde).strftime("%d/%m %H:%M")
    except ValueError:
        return waarde


_env.filters["dt"] = _fmt_dt


_MAX_CACHE_UUR = 24

# --- automatisch afsluiten als geen enkel tabblad meer open is --------------
# De pagina stuurt elke ~20s een "hartslag". Zien we 90s lang niets meer, dan
# is de tool nergens meer open en sluiten we ze af. Zet je in de tool
# "op de achtergrond laten draaien" aan, dan blijft ze draaien.
_HARTSLAG_TIMEOUT = int(os.environ.get("DVP_HARTSLAG_TIMEOUT", "90"))
_laatste_hartslag = time.monotonic()
_hartslag_gezien = False
_blijf_draaien = False


def _auto_afsluiter(srv) -> None:
    while True:
        time.sleep(15)
        if _blijf_draaien or not _hartslag_gezien:
            continue
        if time.monotonic() - _laatste_hartslag > _HARTSLAG_TIMEOUT:
            print("Geen tabblad meer open — de tool sluit zichzelf af.")
            srv.shutdown()
            return


def _do_sofascore() -> None:
    gekozen = store.get_kv("settings:vorige_event")
    store.set_kv("bron:sofascore", sofascore.fetch(gekozen, ploeg.actieve()))


def _do_fotmob() -> None:
    vorige = (store.get_kv("bron:sofascore", {}) or {}).get("vorige") or {}
    hint = {"datum": vorige.get("datum"),
            "thuis": (vorige.get("thuis") or {}).get("naam"),
            "uit": (vorige.get("uit") or {}).get("naam")} if vorige.get("datum") else None
    store.set_kv("bron:fotmob", fotmob.fetch(hint, ploeg.actieve()))


def _do_transfermarkt() -> None:
    data = transfermarkt.fetch(ploeg=ploeg.actieve())
    store.set_kv("bron:transfermarkt", data)
    store.save_stat_snapshot(aggregate.snapshot_rijen(data), ploeg.sleutel())


def _do_voorbeschouwing(*, forceer: bool = False) -> None:
    so = store.get_kv("bron:sofascore", {}) or {}
    volgende = so.get("volgende") or {}
    tegenstander = volgende.get("tegenstander") or {}
    bestaand = store.get_kv("bron:voorbeschouwing", {}) or {}
    if not forceer and bestaand:
        vers = store.get_kv_updated("bron:voorbeschouwing")
        try:
            oud_uur = (_dt.datetime.now() - _dt.datetime.fromisoformat(vers)).total_seconds() / 3600
        except (TypeError, ValueError):
            oud_uur = 999
        if oud_uur < _MAX_CACHE_UUR and bestaand.get("tegenstander_id") == tegenstander.get("id"):
            return  # cache nog goed
    tm_spelers = [s["speler"] for s in (store.get_kv("bron:transfermarkt", {}) or {}).get("spelers", [])]
    store.set_kv("bron:voorbeschouwing", preview.fetch(so, tm_spelers, ploeg.actieve()))


# --- bron verversen --------------------------------------------------------
_DOELEN = {
    "sofascore": _do_sofascore,
    "fotmob": _do_fotmob,
    "transfermarkt": _do_transfermarkt,
    "voorbeschouwing": lambda: _do_voorbeschouwing(forceer=True),
}
_STAP_LABEL = {"sofascore": "Sofascore", "transfermarkt": "Transfermarkt",
               "fotmob": "FotMob", "voorbeschouwing": "Voorbeschouwing"}


def _foutmelding(naam: str, exc: Exception) -> dict:
    bron = _STAP_LABEL.get(naam, naam)
    detail = f"{type(exc).__name__}: {exc}"
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)) or "timeout" in detail.lower() \
            or "connection" in detail.lower() or "resolve" in detail.lower():
        kort = f"{bron} was even niet bereikbaar. Controleer je internet en klik nog eens op verversen."
    elif "403" in detail or "429" in detail:
        kort = f"{bron} blokkeerde de aanvraag tijdelijk. Probeer over een paar minuten opnieuw."
    else:
        kort = f"Er ging iets mis bij {bron}. Klik nog eens op verversen; blijft het fout, dan is de site mogelijk aangepast."
    return {"kort": kort, "detail": detail}


_taak_lock = threading.Lock()
_taak: dict = {"bezig": False, "stappen": {}, "gestart": None, "klaar": None, "bron": None}


def _stappen(bron: str) -> list[tuple[str, object]]:
    if bron == "all":
        return [(n, _DOELEN[n]) for n in ("sofascore", "transfermarkt", "fotmob")] + [
            ("voorbeschouwing", lambda: _do_voorbeschouwing(forceer=False))
        ]
    if bron == "match":
        return [("sofascore", _DOELEN["sofascore"]), ("fotmob", _DOELEN["fotmob"])]
    if bron in _DOELEN:
        return [(bron, _DOELEN[bron])]
    return []


def _ververs(bron: str) -> None:
    """Synchroon verversen (voor tests / CLI)."""
    fouten = store.get_kv("fouten", {})
    for naam, fn in _stappen(bron):
        try:
            fn()
            fouten.pop(naam, None)
        except Exception as exc:  # noqa: BLE001
            fouten[naam] = _foutmelding(naam, exc)
            traceback.print_exc()
    store.set_kv("fouten", fouten)


def _start_ververs(bron: str) -> bool:
    """Start het verversen op de achtergrond. False = er loopt er al één."""
    stappen = _stappen(bron)
    if not stappen or not _taak_lock.acquire(blocking=False):
        return False

    def run() -> None:
        fouten = store.get_kv("fouten", {})
        _taak.update(bezig=True, bron=bron, gestart=_dt.datetime.now().isoformat(timespec="seconds"),
                     klaar=None, stappen={n: "wacht" for n, _ in stappen})
        try:
            for naam, fn in stappen:
                _taak["stappen"][naam] = "bezig"
                try:
                    fn()
                    fouten.pop(naam, None)
                    _taak["stappen"][naam] = "klaar"
                except Exception as exc:  # noqa: BLE001
                    fouten[naam] = _foutmelding(naam, exc)
                    _taak["stappen"][naam] = "fout"
                    traceback.print_exc()
            store.set_kv("fouten", fouten)
        finally:
            _taak.update(bezig=False, klaar=_dt.datetime.now().isoformat(timespec="seconds"))
            _taak_lock.release()

    threading.Thread(target=run, daemon=True).start()
    return True


def _data_verouderd() -> bool:
    """True als de data ontbreekt of de nieuwste bron > 8u oud is."""
    tijden = [store.get_kv_updated(k) for k in ("bron:sofascore", "bron:transfermarkt", "bron:fotmob")]
    if any(t is None for t in tijden):
        return True
    try:
        nieuwste = max(_dt.datetime.fromisoformat(t) for t in tijden if t)
    except ValueError:
        return True
    return (_dt.datetime.now() - nieuwste).total_seconds() > 8 * 3600


# --- rendering -------------------------------------------------------------
def _afleveringen_map() -> str:
    basis = store.AFLEVERINGEN_DIR
    return str(basis / ploeg.sleutel() if merk.toon_kiezer() else basis)


def _render_index() -> bytes:
    overzicht = aggregate.bouw_overzicht()
    actief = ploeg.actieve()
    context = {
        "o": overzicht,
        "fouten": store.get_kv("fouten", {}),
        "markdown": export.naar_markdown(overzicht),
        "episodes": store.list_episodes(ploeg.sleutel()),
        "afleveringen_map": _afleveringen_map(),
        "club": actief.get("naam") or merk.app_naam(),
        "eigen_naam": actief.get("naam") or config.CLUB_NAAM,
        "app_naam": merk.app_naam(),
        "toon_kiezer": merk.toon_kiezer(),
        "actieve_ploeg": actief,
        "favorieten": ploeg.favorieten(),
        "competitie_naam": (actief.get("competitie") or {}).get("naam", ""),
        "versie": config.versie(),
        "blijf_draaien": bool(store.get_kv("settings:blijf_draaien", False)),
        "nu": _dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "verversen_bezig": _taak["bezig"],
        "data_verouderd": _data_verouderd(),
    }
    return _env.get_template("overview.html").render(**context).encode("utf-8")


def _render_kies_ploeg() -> bytes:
    return _env.get_template("kies_ploeg.html").render(
        app_naam=merk.app_naam(),
        competities=competities.COMPETITIES,
        actieve_ploeg=ploeg.actieve() if ploeg.is_gekozen() else None,
    ).encode("utf-8")


def _render_instellingen() -> bytes:
    return _env.get_template("instellingen.html").render(
        app_naam=merk.app_naam(),
        actieve_ploeg=ploeg.actieve(),
        favorieten=ploeg.favorieten(),
        toon_kiezer=merk.toon_kiezer(),
        versie=config.versie(),
    ).encode("utf-8")


def _tm_uit_url(tekst: str) -> tuple[int, str] | None:
    """(verein-id, slug) uit een geplakte Transfermarkt-URL of '/slug/.../verein/123'."""
    m = re.search(r"/([a-z0-9-]+)/[a-z]+/verein/(\d+)", tekst or "")
    if m:
        return int(m.group(2)), m.group(1)
    m = re.search(r"verein/(\d+)", tekst or "")
    return (int(m.group(1)), "verein") if m else None


def _ploegen_in_competitie(ut: int) -> list[dict]:
    """Alle ploegen van een competitie (uit de huidige stand), alfabetisch."""
    seizoen = sofascore._huidig_seizoen(ut)
    if not seizoen:
        return []
    try:
        st = sofascore._get(
            f"{sofascore.API}/unique-tournament/{ut}/season/{seizoen}/standings/total"
        )
    except Exception:
        return []
    rows = (st.get("standings") or [{}])[0].get("rows", [])
    ploegen = [
        {"id": (r.get("team") or {}).get("id"), "naam": (r.get("team") or {}).get("name")}
        for r in rows
        if (r.get("team") or {}).get("id")
    ]
    return sorted(ploegen, key=lambda p: (p["naam"] or "").lower())


def _resolveer_ploeg(ut: int, sofascore_id: int, naam: str) -> dict:
    """Zoek de FotMob- en Transfermarkt-tegenhangers van een Sofascore-ploeg."""
    from .names import clubs_gelijk

    comp = competities.by_ut(ut) or {}
    fm_opties = fotmob.zoek_team(naam)
    fm_beste = next(
        (o for o in fm_opties if clubs_gelijk(o.get("competitie", ""), comp.get("naam", ""))),
        fm_opties[0] if fm_opties else None,
    )
    tm = transfermarkt.zoek_club(naam, comp.get("naam"))
    return {
        "naam": naam,
        "sofascore_id": int(sofascore_id),
        "competitie": {"naam": comp.get("naam"), "sofascore_ut": int(ut),
                       "tm_code": comp.get("tm_code")},
        "fotmob_ccode3": comp.get("fotmob_ccode3", "BEL"),
        "fotmob_id": fm_beste["id"] if fm_beste else None,
        "fotmob_naam": fm_beste["naam"] if fm_beste else None,
        "fotmob_competitie": fm_beste["competitie"] if fm_beste else None,
        "fotmob_opties": fm_opties,
        "tm_id": tm[0] if tm else None,
        "tm_slug": tm[1] if tm else None,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "DVP/1.0"

    def log_message(self, fmt, *args):  # stiller
        return

    def _stuur(self, body: bytes, status: int = 200, content_type: str = "text/html; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, naar: str = "/"):
        self.send_response(303)
        self.send_header("Location", naar)
        self.end_headers()

    def _body(self) -> dict[str, list[str]]:
        lengte = int(self.headers.get("Content-Length", 0) or 0)
        ruw = self.rfile.read(lengte).decode("utf-8") if lengte else ""
        return parse_qs(ruw, keep_blank_values=True)

    def do_GET(self):  # noqa: N802
        pad = urlparse(self.path).path
        try:
            if pad in ("/", "/index.html"):
                if merk.toon_kiezer() and not ploeg.is_gekozen():
                    self._redirect("/kies-ploeg")
                else:
                    self._stuur(_render_index())
            elif pad == "/kies-ploeg":
                self._stuur(_render_kies_ploeg())
            elif pad == "/instellingen":
                self._stuur(_render_instellingen())
            elif pad == "/api/ploegen":
                qs = parse_qs(urlparse(self.path).query)
                ut = int((qs.get("ut") or ["0"])[0])
                self._stuur(json.dumps(_ploegen_in_competitie(ut)).encode("utf-8"),
                            content_type="application/json; charset=utf-8")
            elif pad == "/api/fotmob-zoek":
                qs = parse_qs(urlparse(self.path).query)
                naam = (qs.get("naam") or [""])[0]
                self._stuur(json.dumps(fotmob.zoek_team(naam)).encode("utf-8"),
                            content_type="application/json; charset=utf-8")
            elif pad == "/print":
                md = export.naar_markdown(aggregate.bouw_overzicht())
                html = mdrender.pagina(f"{merk.app_naam()} — voorbereiding", md,
                                       licht=True, print_knop=True)
                self._stuur(html.encode("utf-8"))
            elif pad == "/export.md":
                md = export.naar_markdown(aggregate.bouw_overzicht())
                self._stuur(md.encode("utf-8"), content_type="text/markdown; charset=utf-8")
            elif pad == "/episode":
                qs = parse_qs(urlparse(self.path).query)
                ep = store.get_episode(int((qs.get("id") or ["0"])[0]))
                if ep:
                    self._stuur(mdrender.pagina(ep["title"], ep.get("markdown") or "").encode("utf-8"))
                else:
                    self._stuur(b"Aflevering niet gevonden", status=404, content_type="text/plain")
            elif pad == "/refresh-status":
                data = {**_taak, "labels": _STAP_LABEL}
                self._stuur(json.dumps(data).encode("utf-8"),
                            content_type="application/json; charset=utf-8")
            elif pad.startswith("/static/"):
                bestand = (_STATIC / pad[len("/static/"):]).resolve()
                if _STATIC in bestand.parents and bestand.is_file():
                    ct = mimetypes.guess_type(str(bestand))[0] or "application/octet-stream"
                    self._stuur(bestand.read_bytes(), content_type=ct)
                else:
                    self._stuur(b"", status=404, content_type="text/plain")
            elif pad == "/heartbeat":
                global _laatste_hartslag, _hartslag_gezien, _blijf_draaien
                qs = parse_qs(urlparse(self.path).query)
                nieuw = (qs.get("blijf") or ["0"])[0] == "1"
                if nieuw != _blijf_draaien:
                    _blijf_draaien = nieuw
                    store.set_kv("settings:blijf_draaien", nieuw)
                _laatste_hartslag = time.monotonic()
                _hartslag_gezien = True
                self._stuur(b"ok", content_type="text/plain")
            elif pad == "/health":
                self._stuur(b"ok", content_type="text/plain")
            else:
                self._stuur(b"Niet gevonden", status=404, content_type="text/plain")
        except Exception:  # noqa: BLE001
            self._stuur(traceback.format_exc().encode("utf-8"), status=500,
                        content_type="text/plain; charset=utf-8")

    def do_POST(self):  # noqa: N802
        pad = urlparse(self.path).path
        try:
            form = self._body()
            if pad == "/refresh":
                gestart = _start_ververs((form.get("bron") or ["all"])[0])
                self._stuur(json.dumps({"gestart": gestart}).encode("utf-8"),
                            content_type="application/json")
            elif pad == "/ratings":
                event_id = (form.get("event_id") or [""])[0]
                for sleutel, waarden in form.items():
                    if "__" not in sleutel:
                        continue
                    bron, player_key = sleutel.split("__", 1)
                    if bron != "whoscored":
                        continue
                    ruw = (waarden[0] or "").strip().replace(",", ".")
                    try:
                        rating = float(ruw) if ruw else None
                    except ValueError:
                        rating = None
                    store.save_manual_rating(event_id, player_key, bron, rating)
                self._redirect()
            elif pad == "/episode":
                titel = (form.get("titel") or [""])[0].strip() or f"Aflevering {_dt.date.today()}"
                notities = (form.get("notities") or [""])[0]
                overzicht = aggregate.bouw_overzicht()
                store.save_episode(
                    titel, overzicht, export.naar_markdown(overzicht), notities,
                    team=ploeg.sleutel(),
                    team_map=ploeg.sleutel() if merk.toon_kiezer() else "",
                )
                self._redirect()
            elif pad == "/kies-ploeg":
                ut = int((form.get("ut") or ["0"])[0])
                sid = int((form.get("sofascore_id") or ["0"])[0])
                naam = (form.get("naam") or [""])[0].strip()
                self._stuur(json.dumps(_resolveer_ploeg(ut, sid, naam)).encode("utf-8"),
                            content_type="application/json; charset=utf-8")
            elif pad == "/bevestig-ploeg":
                nieuw = {
                    "naam": (form.get("naam") or [""])[0].strip(),
                    "sofascore_id": int((form.get("sofascore_id") or ["0"])[0]),
                    "fotmob_id": int(form["fotmob_id"][0]) if (form.get("fotmob_id") or [""])[0] else None,
                    "fotmob_ccode3": (form.get("fotmob_ccode3") or ["BEL"])[0],
                    "tm_id": int(form["tm_id"][0]) if (form.get("tm_id") or [""])[0] else None,
                    "tm_slug": (form.get("tm_slug") or [""])[0].strip() or None,
                    "competitie": {
                        "naam": (form.get("competitie_naam") or [""])[0],
                        "sofascore_ut": int((form.get("ut") or ["0"])[0]),
                        "tm_code": (form.get("tm_code") or [""])[0] or None,
                    },
                }
                # een geplakte Transfermarkt-URL heeft voorrang
                geplakt = _tm_uit_url((form.get("tm_plak") or [""])[0])
                if geplakt:
                    nieuw["tm_id"], nieuw["tm_slug"] = geplakt
                ploeg.zet_actief(nieuw)
                _start_ververs("all")
                self._redirect("/")
            elif pad == "/wissel-ploeg":
                if (form.get("naar") or [""])[0] == "kiezer":
                    self._redirect("/kies-ploeg")
                else:
                    idx = int((form.get("index") or ["0"])[0])
                    favs = ploeg.favorieten()
                    if 0 <= idx < len(favs):
                        ploeg.zet_actief(favs[idx])
                        _start_ververs("all")
                    self._redirect("/")
            elif pad == "/favoriet":
                idx = int((form.get("index") or ["-1"])[0])
                favs = ploeg.favorieten()
                if (form.get("actie") or [""])[0] == "weg" and 0 <= idx < len(favs):
                    verwijderd = favs.pop(idx)
                    if verwijderd.get("sofascore_id") != ploeg.actieve().get("sofascore_id"):
                        store.set_kv("settings:favorieten", favs)
                self._redirect("/instellingen")
            elif pad == "/kies-match":
                keuze = (form.get("event_id") or [""])[0].strip()
                store.set_kv("settings:vorige_event", keuze if keuze and keuze != "auto" else None)
                _start_ververs("match")
                self._redirect()
            elif pad == "/alias":
                van = (form.get("van") or [""])[0].strip()
                naar = (form.get("naar") or [""])[0].strip()
                if van and naar:
                    from .names import normaliseer
                    aliassen = store.get_kv("aliassen", {}) or {}
                    aliassen[normaliseer(van)] = naar
                    store.set_kv("aliassen", aliassen)
                self._redirect()
            elif pad == "/afsluiten":
                self._stuur(b"<!doctype html><meta charset=utf-8>"
                            b"<body style='background:#0e1014;color:#e7e9ee;font-family:system-ui;padding:40px'>"
                            b"De tool is afgesloten. Je mag dit tabblad sluiten.</body>")
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                self._stuur(b"Niet gevonden", status=404, content_type="text/plain")
        except Exception:  # noqa: BLE001
            self._stuur(traceback.format_exc().encode("utf-8"), status=500,
                        content_type="text/plain; charset=utf-8")


def main(open_browser: bool = False) -> None:
    global _blijf_draaien
    store.init()
    store.backfill_team(ploeg.sleutel())  # oude rijen zonder ploeg -> huidige standaardploeg
    if sys.platform == "win32":
        assets.ensure_ico()  # enkel nodig voor de Windows-snelkoppeling
    _blijf_draaien = bool(store.get_kv("settings:blijf_draaien", False))
    try:
        srv = ThreadingHTTPServer((config.HOST, config.PORT), Handler)
    except OSError:
        # poort al bezet -> tool draait al
        if open_browser:
            webbrowser.open(f"http://{config.HOST}:{config.PORT}")
        return
    url = f"http://{config.HOST}:{config.PORT}"
    print(f"De Vierkante Paal — voorbereidingstool draait op {url}")
    threading.Thread(target=_auto_afsluiter, args=(srv,), daemon=True).start()
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main(open_browser="--browser" in sys.argv)
