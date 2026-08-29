#!/usr/bin/env python3
"""Bouwt "De Vierkante Paal (Mac).zip" -- op Windows, zonder Mac.

Draai op je eigen pc:

    py installer\\mac\\bouw-mac.py

Nodig: internet (eenmalig) en Python met pip. Geen Mac nodig.
Resultaat: installer/uit/De Vierkante Paal (Mac).zip  (delen met Mac-gebruikers,
samen met installer/uit/LEESMIJ-mac.txt).

LET OP: deze build kan niet op een echte Mac getest worden vanaf Windows.
Laat een Mac-gebruiker ze een keer uitproberen voor je ze breed verdeelt.
"""
from __future__ import annotations

import io
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

# --- vaste keuzes -----------------------------------------------------------
PBS_TAG = "20260825"                       # python-build-standalone release
PY_VER = "3.12.14"
_V = "install_only_stripped"               # gestript = kleinere binaries
ARCHES = {
    "arm64":  f"cpython-{PY_VER}+{PBS_TAG}-aarch64-apple-darwin-{_V}.tar.gz",
    "x86_64": f"cpython-{PY_VER}+{PBS_TAG}-x86_64-apple-darwin-{_V}.tar.gz",
}
PBS_BASE = ("https://github.com/astral-sh/python-build-standalone/releases/"
            f"download/{PBS_TAG}/")

# De Mac-build heeft lxml noch pillow nodig (bs4 gebruikt html.parser; het
# icoon-omzetten is enkel voor de Windows-snelkoppeling). Dat scheelt tientallen MB.
MAC_DEPS = ["curl_cffi>=0.7", "beautifulsoup4>=4.12", "jinja2>=3.1"]

PIP_PLATFORMS = {
    "arm64":  ["macosx_11_0_arm64", "macosx_12_0_arm64", "macosx_13_0_arm64",
               "macosx_14_0_arm64", "macosx_10_9_universal2"],
    "x86_64": ["macosx_10_12_x86_64", "macosx_10_13_x86_64", "macosx_11_0_x86_64",
               "macosx_12_0_x86_64", "macosx_10_9_universal2"],
}

INST = Path(__file__).resolve().parent            # installer/mac
PROJ = INST.parent.parent                          # projectmap
CACHE = INST.parent / "cache"
BUILD = INST.parent / "build-mac"
UIT = INST.parent / "uit"

VARIANT = "generiek" if "--variant" in sys.argv and "generiek" in sys.argv else "dvp"
APPNAAM = "Aftrap" if VARIANT == "generiek" else "De Vierkante Paal"
BUNDLE = f"{APPNAAM}.app"
VERSIE = date.today().strftime("%Y.%m.%d")


def stap(t: str) -> None:
    print(f"\n=== {t} ===")


def rmtree(pad: Path) -> None:
    """Robuust verwijderen (read-only bestanden, OneDrive-vertraging)."""
    import os
    import time as _t

    def _onexc(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass

    for poging in range(4):
        if not pad.exists():
            return
        try:
            shutil.rmtree(pad, onexc=_onexc)
        except TypeError:                       # oudere Python: onerror i.p.v. onexc
            shutil.rmtree(pad, onerror=lambda f, p, e: _onexc(f, p, e))
        except OSError:
            pass
        if not pad.exists():
            return
        _t.sleep(1.0)
    if pad.exists():
        raise RuntimeError(f"kon {pad} niet verwijderen -- sluit programma's die er bestanden "
                           f"uit open hebben (of pauzeer OneDrive) en probeer opnieuw")


def download(naam: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    doel = CACHE / naam
    if doel.exists():
        return doel
    print(f"  downloaden: {naam}")
    req = urllib.request.Request(PBS_BASE + naam, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as r, open(doel, "wb") as f:
        shutil.copyfileobj(r, f)
    return doel


def ensure_pillow():
    try:
        import PIL  # noqa: F401
    except ImportError:
        print("  Pillow installeren (eenmalig, voor het app-icoon)...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                        "--disable-pip-version-check", "pillow"], check=True)


def maak_icns(png: Path) -> bytes:
    from PIL import Image
    resampling = getattr(Image, "Resampling", Image)
    src = Image.open(png).convert("RGBA")
    if src.width != src.height:               # vierkant maken
        z = max(src.size)
        canvas = Image.new("RGBA", (z, z), (0, 0, 0, 0))
        canvas.paste(src, ((z - src.width) // 2, (z - src.height) // 2))
        src = canvas
    # PNG-in-ICNS chunks (moderne macOS leest deze rechtstreeks)
    typen = [(b"ic07", 128), (b"ic08", 256), (b"ic09", 512), (b"ic10", 1024),
             (b"ic11", 32), (b"ic12", 64), (b"ic13", 256), (b"ic14", 512)]
    body = b""
    for code, size in typen:
        im = src.resize((size, size), resampling.LANCZOS)
        b = io.BytesIO()
        im.save(b, format="PNG")
        data = b.getvalue()
        body += code + (len(data) + 8).to_bytes(4, "big") + data
    return b"icns" + (len(body) + 8).to_bytes(4, "big") + body


def pip_target(arch: str, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    args = [sys.executable, "-m", "pip", "install", "--target", str(dest),
            "--python-version", "3.12", "--implementation", "cp", "--abi", "cp312",
            "--only-binary=:all:", "--no-compile", "--disable-pip-version-check",
            *MAC_DEPS]
    for p in PIP_PLATFORMS[arch]:
        args += ["--platform", p]
    subprocess.run(args, check=True)


class MacZip:
    """Zip met Unix-permissies + symlinks, zonder een echt Mac-bestandssysteem."""

    def __init__(self, pad: Path):
        self.z = zipfile.ZipFile(pad, "w", zipfile.ZIP_DEFLATED, compresslevel=6)

    def _zi(self, arcname: str, mode: int) -> zipfile.ZipInfo:
        zi = zipfile.ZipInfo(arcname)
        zi.create_system = 3                  # Unix -> macOS respecteert de mode-bits
        zi.external_attr = (mode & 0xFFFF) << 16
        return zi

    def file(self, arcname: str, data: bytes, mode: int = 0o644) -> None:
        self.z.writestr(self._zi(arcname, stat.S_IFREG | mode), data)

    def symlink(self, arcname: str, target: str) -> None:
        self.z.writestr(self._zi(arcname, stat.S_IFLNK | 0o777), target.encode("utf-8"))

    def close(self) -> None:
        self.z.close()


def add_tree(mz: MacZip, src: Path, arcbase: str, skip: set[str] | None = None) -> None:
    skip = skip or set()
    for p in sorted(src.rglob("*")):
        if p.is_dir() or "__pycache__" in p.parts or p.suffix == ".pyc":
            continue
        rel = p.relative_to(src).as_posix()
        if rel in skip:
            continue
        mz.file(f"{arcbase}/{rel}", p.read_bytes())


# Weglaten uit de ingebouwde Python: alles wat de tool niet nodig heeft
# (scheelt ~150 MB). rel = pad zonder de "python/"-voorloop.
_SKIP = re.compile(
    r"^(include/"
    r"|share/"
    r"|lib/pkgconfig/"
    r"|lib/(libtcl|libtk|libitcl|libtclstub|tcl8|tk8|tcl9|tk9|itcl|thread[0-9]|Tktable)"
    r"|lib/python3\.12/(test/|idlelib/|turtledemo/|tkinter/|lib2to3/|ensurepip/"
    r"|pydoc_data/|config-3\.12)"
    r"|lib/python3\.12/site-packages/(pip|setuptools|pkg_resources|_distutils_hack|wheel|pydoc)"
    r")"
)


# Losse bin-tools die de tool niet nodig heeft (+ hun symlinks).
_SKIP_BIN = {"idle3", "idle3.12", "2to3", "2to3-3.12", "pydoc3", "pydoc3.12",
             "pip", "pip3", "pip3.12", "python3-config", "python3.12-config"}


def _skip_pbs(rel: str) -> bool:
    if _SKIP.match(rel):
        return True
    if rel.endswith(".a"):                              # statische libs (libpython3.12.a)
        return True
    # de losse libpython-dylib is enkel voor "embedding"; de python-executable
    # heeft libpython statisch ingebouwd en werkt zelfstandig.
    if rel.startswith("lib/libpython3.12"):
        return True
    if rel.startswith("bin/") and rel[4:] in _SKIP_BIN:
        return True
    if rel.startswith("lib/python3.12/") and ("/test/" in rel or "/tests/" in rel):
        return True
    if "lib-dynload/" in rel and rel.rsplit("/", 1)[-1].startswith(("_tkinter", "_test", "xxlimited")):
        return True
    return False


def add_pbs(mz: MacZip, tgz: Path, arcbase: str) -> None:
    with tarfile.open(tgz, "r:gz") as tf:
        for m in tf.getmembers():
            parts = m.name.split("/", 1)     # "python/bin/..." -> "bin/..."
            if len(parts) < 2 or not parts[1] or _skip_pbs(parts[1]):
                continue
            arc = f"{arcbase}/{parts[1]}"
            if m.issym():
                mz.symlink(arc, m.linkname)
            elif m.isfile() or m.islnk():
                f = tf.extractfile(m)
                if f is not None:
                    mz.file(arc, f.read(), m.mode or 0o644)


def main() -> None:
    # standaard: beide Mac-types. "--arm64" of "--x86_64" = kleiner, maar één type.
    keuze = [a for a in ("arm64", "x86_64") if f"--{a}" in sys.argv]
    arches = keuze or list(ARCHES)

    rmtree(BUILD)
    BUILD.mkdir(parents=True)
    UIT.mkdir(parents=True, exist_ok=True)

    stap("1/5  Ingebouwde Python ophalen  (" + ", ".join(arches) + ")")
    tgz = {a: download(ARCHES[a]) for a in arches}

    stap("2/5  Dependencies cross-installeren (curl_cffi, beautifulsoup4, jinja2)")
    sp = {}
    for arch in arches:
        print(f"  {arch} ...")
        d = BUILD / f"sp-{arch}"
        pip_target(arch, d)
        sp[arch] = d

    stap(f"3/5  App-icoon (logo.icns)  [variant: {VARIANT}]")
    ensure_pillow()
    logo_png = (INST.parent / "assets" / "aftrap-logo.png") if VARIANT == "generiek" \
        else (PROJ / "dvp" / "static" / "logo.png")
    icns = maak_icns(logo_png)

    stap("4/5  De .app samenstellen")
    out = UIT / f"{APPNAAM} (Mac).zip"
    if out.exists():
        out.unlink()
    mz = MacZip(out)
    C = f"{BUNDLE}/Contents"
    plist = (INST / "Info.plist").read_text(encoding="utf-8").replace("__VERSIE__", VERSIE)
    mz.file(f"{C}/Info.plist", plist.encode("utf-8"))
    mz.file(f"{C}/PkgInfo", b"APPL????")
    launcher = (INST / "launcher.sh").read_text(encoding="utf-8").replace("\r\n", "\n")
    mz.file(f"{C}/MacOS/DeVierkantePaal", launcher.encode("utf-8"), 0o755)
    mz.file(f"{C}/Resources/logo.icns", icns)
    appdir = f"{C}/Resources/app"
    mz.file(f"{appdir}/versie.txt", VERSIE.encode("utf-8"))
    if VARIANT == "generiek":
        mz.file(f"{appdir}/merk.json",
                b'{ "app_naam": "Aftrap", "toon_kiezer": true, "vaste_ploeg": null }')
        add_tree(mz, PROJ / "dvp", f"{appdir}/dvp", skip={"static/logo.png"})
        mz.file(f"{appdir}/dvp/static/logo.png", logo_png.read_bytes())  # Aftrap-logo
    else:
        add_tree(mz, PROJ / "dvp", f"{appdir}/dvp")
    for arch in arches:
        print(f"  Python-{arch} inpakken ...")
        add_pbs(mz, tgz[arch], f"{appdir}/python-{arch}")
        add_tree(mz, sp[arch], f"{appdir}/python-{arch}/lib/python3.12/site-packages")
    mz.close()

    stap("5/5  Afronden")
    shutil.copy(INST / "LEESMIJ-mac.txt", UIT / "LEESMIJ-mac.txt")
    mb = out.stat().st_size / 1024 / 1024
    print(f"\nKLAAR.\nDeelbestand: {out}  ({mb:.1f} MB)")
    print("Deel dit + installer/uit/LEESMIJ-mac.txt met de Mac-gebruikers.")
    print("LET OP: niet op een echte Mac getest -- laat iemand met een Mac ze eerst proberen.")


if __name__ == "__main__":
    main()
