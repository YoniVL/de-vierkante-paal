#!/bin/bash
# Entry point van "De Vierkante Paal.app".
# Kiest de juiste ingebouwde Python voor deze Mac en start de tool.
set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$HERE/../Resources/app"

case "$(uname -m)" in
  arm64) ARCH="arm64" ;;
  *)     ARCH="x86_64" ;;
esac

PYDIR="$APP/python-$ARCH"
if [ ! -d "$PYDIR" ]; then
  # gevraagde variant niet meegeleverd -> neem wat er wel is
  # (een Apple Silicon-Mac draait een Intel-build via Rosetta 2)
  for alt in arm64 x86_64; do
    if [ -d "$APP/python-$alt" ]; then PYDIR="$APP/python-$alt"; break; fi
  done
fi

PY="$PYDIR/bin/python3.12"
[ -x "$PY" ] || PY="$PYDIR/bin/python3"

if [ ! -x "$PY" ]; then
  osascript -e 'display alert "De Vierkante Paal" message "De ingebouwde Python is niet gevonden of wordt door macOS geblokkeerd. Lees het bestand LEESMIJ-mac.txt dat bij de download zat."' >/dev/null 2>&1 || true
  exit 1
fi

# bytecode-cache in een schrijfbare map (de .app-bundel is normaal alleen-lezen)
export PYTHONPYCACHEPREFIX="$HOME/Library/Caches/DeVierkantePaal/pyc"

cd "$APP"
exec "$PY" -m dvp.app --browser
