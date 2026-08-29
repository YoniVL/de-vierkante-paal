"""Gedeelde HTTP-helpers.

Sofascore blokkeert 'gewone' Python-requests op TLS-niveau; daarvoor gebruiken we
curl_cffi met een Chrome-fingerprint. Transfermarkt werkt met een gewone request
mits een browser-User-Agent.
"""

from __future__ import annotations

import gzip
import time
import urllib.request

from . import config

_last_call: dict[str, float] = {}

# Pauze (s) tussen opeenvolgende requests naar dezelfde bron.
_PAUZE = {"sofascore": 0.35, "fotmob": 0.5, "transfermarkt": 0.8}


def _throttle(key: str) -> None:
    pauze = _PAUZE.get(key, config.REQUEST_PAUSE)
    now = time.monotonic()
    wait = pauze - (now - _last_call.get(key, 0.0))
    if wait > 0:
        time.sleep(wait)
    _last_call[key] = time.monotonic()


def get_json_impersonated(url: str, *, key: str = "sofascore") -> dict:
    """GET een JSON-endpoint met een Chrome-fingerprint (curl_cffi)."""
    from curl_cffi import requests as creq  # lazy import

    _throttle(key)
    resp = creq.get(url, impersonate="chrome", timeout=config.REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def get_html(url: str, *, key: str = "transfermarkt") -> str:
    """GET een HTML-pagina met een gewone browser-User-Agent."""
    _throttle(key)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": config.USER_AGENT,
            "Accept-Language": "nl-BE,nl;q=0.9,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(req, timeout=config.REQUEST_TIMEOUT) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    return raw.decode("utf-8", "replace")
