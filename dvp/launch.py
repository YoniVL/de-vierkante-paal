"""Onzichtbare starter voor de tool.

- Draait de tool al? -> open gewoon de browser.
- Nog niet? -> start de server volledig op de achtergrond (geen venster) en open de browser.

Bedoeld om aangeroepen te worden met ``pythonw.exe`` (geen console) via een
bureaublad-snelkoppeling of de Opstarten-map van Windows.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
HOST, PORT = "127.0.0.1", 8756
URL = f"http://{HOST}:{PORT}"


def _draait() -> bool:
    with socket.socket() as s:
        s.settimeout(0.4)
        return s.connect_ex((HOST, PORT)) == 0


def _vind_pythonw() -> Path | None:
    """Zoek de juiste pythonw.exe, ongeacht hoe de tool geïnstalleerd is.

    1. de meegebundelde Python (installatie via het installatieprogramma)
    2. de .venv (ontwikkelopstelling met start.bat)
    3. de Python waarmee dit script zelf draait
    """
    for kandidaat in (
        BASE / "python" / "pythonw.exe",
        BASE / ".venv" / "Scripts" / "pythonw.exe",
    ):
        if kandidaat.exists():
            return kandidaat

    huidig = Path(sys.executable)
    if huidig.name.lower().startswith("pythonw"):
        return huidig
    buur = huidig.with_name("pythonw.exe")
    return buur if buur.exists() else None


def _melding(tekst: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, tekst, "De Vierkante Paal", 0x40)
    except Exception:
        pass


def main() -> None:
    if _draait():
        webbrowser.open(URL)
        return

    pyw = _vind_pythonw()
    if pyw is None:
        _melding("De omgeving is nog niet geïnstalleerd.\n\n"
                 "Dubbelklik één keer op 'start.bat' om alles klaar te zetten "
                 "(of installeer de tool opnieuw).")
        return

    CREATE_NO_WINDOW = 0x08000000
    DETACHED_PROCESS = 0x00000008
    subprocess.Popen(
        [str(pyw), "-m", "dvp.app"],
        cwd=str(BASE),
        creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        close_fds=True,
    )

    for _ in range(60):  # max ~15s wachten tot de server luistert
        if _draait():
            break
        time.sleep(0.25)
    webbrowser.open(URL)


if __name__ == "__main__":
    sys.exit(main())
