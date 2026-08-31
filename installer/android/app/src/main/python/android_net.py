"""HTTP via Android's eigen netwerklaag (java.net.HttpURLConnection).

Android gebruikt Conscrypt/BoringSSL — dezelfde TLS-fingerprint als Chrome —
dus Sofascore, FotMob en Transfermarkt geraken hier gewoon door, zonder
curl_cffi en zonder WebView-omweg.
"""

from __future__ import annotations

import json
import urllib.error

_UA = ("Mozilla/5.0 (Linux; Android 14; Pixel 6) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36")
_TIMEOUT_MS = 25000


def _fetch(url: str, headers: dict[str, str]) -> bytes:
    from java.io import ByteArrayOutputStream
    from java.net import URL

    conn = URL(url).openConnection()
    conn.setConnectTimeout(_TIMEOUT_MS)
    conn.setReadTimeout(_TIMEOUT_MS)
    conn.setInstanceFollowRedirects(True)
    for k, v in headers.items():
        conn.setRequestProperty(k, v)

    code = int(conn.getResponseCode())
    stream = conn.getInputStream() if code < 400 else conn.getErrorStream()
    out = ByteArrayOutputStream()
    if stream is not None:
        chunk = bytearray(16384)
        while True:
            n = stream.read(chunk)
            if n < 0:
                break
            out.write(chunk, 0, n)
        stream.close()
    raw = bytes(out.toByteArray())
    if code >= 400:
        raise urllib.error.HTTPError(url, code, f"HTTP {code}", None, None)
    return raw


def get_json(url: str, key: str = "sofascore") -> dict:
    raw = _fetch(url, {
        "User-Agent": _UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "nl,en;q=0.8",
    })
    return json.loads(raw.decode("utf-8"))


def get_html(url: str, key: str = "transfermarkt") -> str:
    raw = _fetch(url, {
        "User-Agent": _UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "nl-BE,nl;q=0.9,en;q=0.7",
    })
    return raw.decode("utf-8", "replace")


def installeer() -> None:
    """De dvp-http-helpers naar deze backend laten wijzen."""
    from dvp import http_client
    http_client.json_backend = get_json
    http_client.html_backend = get_html
