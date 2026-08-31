"""Gedeelde HTTP-helpers.

Sofascore blokkeert 'gewone' Python-requests op TLS-niveau. Op de desktop lossen
we dat op met curl_cffi (Chrome-fingerprint); op Android zet ``android_start``
een eigen backend (``json_backend`` / ``html_backend``) die via Android's eigen
netwerklaag gaat — die heeft dezelfde fingerprint als Chrome.
"""

from __future__ import annotations

import gzip
import time
import urllib.request

from . import config

_last_call: dict[str, float] = {}

# Pauze (s) tussen opeenvolgende requests naar dezelfde bron.
_PAUZE = {"sofascore": 0.35, "fotmob": 0.5, "transfermarkt": 0.8}

# Optionele vervangers (bv. Android). None = de standaard-implementatie hieronder.
json_backend = None   # (url: str, key: str) -> dict
html_backend = None   # (url: str, key: str) -> str


def _throttle(key: str) -> None:
    pauze = _PAUZE.get(key, config.REQUEST_PAUSE)
    now = time.monotonic()
    wait = pauze - (now - _last_call.get(key, 0.0))
    if wait > 0:
        time.sleep(wait)
    _last_call[key] = time.monotonic()


def get_json_impersonated(url: str, *, key: str = "sofascore") -> dict:
    """GET een JSON-endpoint met een browser-fingerprint."""
    _throttle(key)
    if json_backend is not None:
        return json_backend(url, key)
    from curl_cffi import requests as creq  # lazy import (niet op Android)

    resp = creq.get(url, impersonate="chrome", timeout=config.REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def get_html(url: str, *, key: str = "transfermarkt") -> str:
    """GET een HTML-pagina met een browser-User-Agent."""
    _throttle(key)
    if html_backend is not None:
        return html_backend(url, key)
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
