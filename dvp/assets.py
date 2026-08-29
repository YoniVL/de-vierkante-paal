"""Maakt van het logo (dvp/static/logo.png) een Windows-icoon voor de snelkoppeling."""

from __future__ import annotations

from pathlib import Path

STATIC = Path(__file__).parent / "static"
PNG = STATIC / "logo.png"
ICO = STATIC / "logo.ico"


def ensure_ico() -> Path | None:
    """Genereer logo.ico uit logo.png als die er nog niet is of ouder is."""
    if not PNG.exists():
        return None
    if ICO.exists() and ICO.stat().st_mtime >= PNG.stat().st_mtime:
        return ICO
    try:
        from PIL import Image

        img = Image.open(PNG).convert("RGBA")
        img.save(ICO, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        return ICO
    except Exception:
        return None


if __name__ == "__main__":
    print(ensure_ico() or "geen logo.png gevonden")
